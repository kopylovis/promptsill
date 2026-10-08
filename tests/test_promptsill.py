import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "promptsill")
TMP = tempfile.mkdtemp(prefix="promptsill-test-")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_STATE_HOME"] = os.path.join(TMP, "state")

loader = importlib.machinery.SourceFileLoader("promptsill", SCRIPT)
spec = importlib.util.spec_from_loader("promptsill", loader)
ps = importlib.util.module_from_spec(spec)
loader.exec_module(ps)

ESC = "\033"


def plain(text):
    return ps.ESCAPES.sub("", text)


def reset_opts(**kw):
    ps.OPTS.update({"lang": "en", "ascii": False, "color": True, "links": True}, **kw)


class Render(unittest.TestCase):
    def setUp(self):
        reset_opts()

    def test_labels_follow_language(self):
        d = {"context_window": {"used_percentage": 42}, "workspace": {"current_dir": TMP}}
        self.assertIn("context", plain(ps.render(d)))
        reset_opts(lang="ru")
        self.assertIn("контекст", plain(ps.render(d)))

    def test_language_from_locale_and_override(self):
        env = {k: os.environ.pop(k, None) for k in ("LC_ALL", "LC_MESSAGES", "LANG", "PROMPTSILL_LANG")}
        try:
            os.environ["LANG"] = "ru_RU.UTF-8"
            ps.configure()
            self.assertEqual(ps.OPTS["lang"], "ru")
            os.environ["LC_ALL"] = "en_US.UTF-8"
            ps.configure()
            self.assertEqual(ps.OPTS["lang"], "en")
            ps.configure("ru")
            self.assertEqual(ps.OPTS["lang"], "ru")
            os.environ["PROMPTSILL_LANG"] = "ru"
            ps.configure()
            self.assertEqual(ps.OPTS["lang"], "ru")
        finally:
            for k, v in env.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v

    def test_no_color(self):
        os.environ["NO_COLOR"] = "1"
        try:
            ps.configure("en")
            line = ps.render({"model": {"display_name": "Opus"}, "context_window": {"used_percentage": 90},
                              "workspace": {"current_dir": TMP}})
            self.assertNotIn(ESC + "[", line)
        finally:
            del os.environ["NO_COLOR"]

    def test_empty_input(self):
        self.assertIsInstance(ps.render({}), str)

    def test_fit_shortens_then_drops(self):
        parts = [(1, "context ██▏░░ 42%", "context 42%"), (4, "Opus"), (3, "week 35%")]
        self.assertEqual(plain(ps.fit(parts, 0)), "context ██▏░░ 42% · Opus · week 35%")
        self.assertEqual(plain(ps.fit(parts, 36)), "context 42% · Opus · week 35%")
        self.assertEqual(plain(ps.fit(parts, 30)), "context 42% · week 35%")
        self.assertEqual(plain(ps.fit(parts, 10)), "context 42%")

    def test_fit_ignores_link_width(self):
        reset_opts()
        linked = ps.link("main", "https://example.com/" + "x" * 200)
        self.assertEqual(ps.visible(linked), 4)
        self.assertEqual(plain(ps.fit([(1, linked), (2, "abc")], 20)), "main · abc")


class Bars(unittest.TestCase):
    def setUp(self):
        reset_opts(color=False)

    def test_eighths(self):
        self.assertEqual(ps.bar(0), "░░░░░")
        self.assertEqual(ps.bar(100), "█████")
        self.assertEqual(ps.bar(42), "██▏░░")
        self.assertEqual(ps.bar(50), "██▌░░")

    def test_colored_bar_uses_track_background(self):
        reset_opts(color=True)
        self.assertEqual(ps.bar(42, ps.RED), "\033[31;48;5;240m██▏  \033[0m")
        self.assertEqual(ps.visible(ps.bar(42)), 5)

    def test_ascii(self):
        reset_opts(color=False, ascii=True)
        self.assertEqual(ps.bar(42), "[##---]")


class Pace(unittest.TestCase):
    def setUp(self):
        reset_opts()

    def lim(self, pct, left):
        return {"used_percentage": pct, "resets_at": self.now + left}

    now = 1_800_000_000

    def test_heavy_early_use_is_red(self):
        p = ps.pace(self.lim(60, 4 * 3600), 5 * 3600, self.now)
        self.assertAlmostEqual(p["ahead"], 40)
        self.assertTrue(p["runs_out"] < self.now + 4 * 3600)
        self.assertEqual(ps.pace_level(60, p), ps.RED)

    def test_same_use_late_is_fine(self):
        p = ps.pace(self.lim(60, 600), 5 * 3600, self.now)
        self.assertLess(p["ahead"], 0)
        self.assertIsNone(p["runs_out"])
        self.assertEqual(ps.pace_level(60, p), "")

    def test_slightly_ahead_is_yellow(self):
        p = ps.pace(self.lim(65, 2.5 * 3600), 5 * 3600, self.now)
        self.assertEqual(ps.pace_level(65, p), ps.YELLOW)

    def test_too_early_falls_back_to_percent(self):
        self.assertIsNone(ps.pace(self.lim(10, 5 * 3600 - 300), 5 * 3600, self.now))
        self.assertEqual(ps.pace_level(10, None), "")
        self.assertEqual(ps.pace_level(75, None), ps.YELLOW)

    def test_limit_part_marks_pace(self):
        part = ps.limit_part("five_hour", self.lim(60, 4 * 3600), self.now)
        text = plain(part[1])
        self.assertIn("60% +40%", text)
        self.assertIn("runs out", text)
        self.assertIn("resets", text)
        self.assertEqual(plain(part[2]), "5h 60% +40%")

    def test_week_hides_reset_when_calm(self):
        part = ps.limit_part("seven_day", self.lim(20, 3 * 86400), self.now)
        self.assertEqual(plain(part[1]), "week 20%")


class Cache(unittest.TestCase):
    def setUp(self):
        reset_opts()

    def test_hidden_while_far_from_expiry(self):
        c = {"caching_observed": True, "warm": True, "ttl": "5m", "expires_at": 1000 + 200, "requests": 3}
        self.assertIsNone(ps.cache_part(c, 1000))

    def test_countdown_near_expiry(self):
        c = {"caching_observed": True, "warm": True, "ttl": "5m", "expires_at": 1000 + 40, "requests": 3}
        self.assertEqual(plain(ps.cache_part(c, 1000)[1]), "cache 40s")

    def test_one_hour_ttl_warns_earlier(self):
        c = {"caching_observed": True, "warm": True, "ttl": "1h", "expires_at": 1000 + 300, "requests": 3}
        self.assertEqual(plain(ps.cache_part(c, 1000)[1]), "cache 5m")

    def test_expired(self):
        c = {"caching_observed": True, "warm": False, "ttl": "5m", "expires_at": None, "requests": 3}
        self.assertEqual(plain(ps.cache_part(c, 1000)[1]), "cache expired")

    def test_no_caching(self):
        self.assertIsNone(ps.cache_part({"caching_observed": False}, 1000))
        self.assertIsNone(ps.cache_part(None, 1000))


class Links(unittest.TestCase):
    def test_remote_to_web(self):
        self.assertEqual(ps.web_url("git@github.com:kopylovis/promptsill.git"), "https://github.com/kopylovis/promptsill")
        self.assertEqual(ps.web_url("https://user:token@github.com/a/b.git"), "https://github.com/a/b")
        self.assertEqual(ps.web_url("ssh://git@gitlab.com:2222/g/sub/r.git"), "https://gitlab.com/g/sub/r")
        self.assertIsNone(ps.web_url("/local/path/repo"))
        self.assertIsNone(ps.web_url(""))

    def test_branch_url(self):
        self.assertEqual(ps.branch_url("https://github.com/a/b", "feat/x", True), "https://github.com/a/b/tree/feat/x")
        self.assertEqual(ps.branch_url("https://gitlab.com/a/b", "dev", True), "https://gitlab.com/a/b/-/tree/dev")
        self.assertEqual(ps.branch_url("https://github.com/a/b", "local", False), "https://github.com/a/b")

    def test_pr_link_wins(self):
        reset_opts()
        g = {"branch": "feat", "ahead": 0, "behind": 0, "upstream": True, "changed": 0}
        d = {"pr": {"url": "https://github.com/a/b/pull/7"}}
        self.assertIn("pull/7", ps.branch_part(g, {"repo": "https://github.com/a/b"}, d)[1])
        reset_opts(links=False)
        self.assertNotIn(ESC + "]8", ps.branch_part(g, {"repo": "https://github.com/a/b"}, d)[1])

    def test_repo_from_claude_json(self):
        d = {"workspace": {"repo": {"host": "github.com", "owner": "o", "name": "r"}}}
        self.assertEqual(ps.repo_url(d, {"repo": None}), "https://github.com/o/r")


class Platform(unittest.TestCase):
    def test_memory_skipped_off_macos(self):
        real = ps.sys.platform
        ps.sys.platform = "linux"
        try:
            self.assertEqual(ps.memory(), {})
        finally:
            ps.sys.platform = real


def cli(*args, stdin=None, env=None):
    full = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, SCRIPT, *args], input=stdin, capture_output=True, text=True, env=full)


class Install(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(dir=TMP)
        self.settings = os.path.join(self.dir, "settings.json")
        self.env = {"XDG_CONFIG_HOME": os.path.join(self.dir, "config")}

    def read(self):
        with open(self.settings) as f:
            return json.load(f)

    def write(self, data):
        with open(self.settings, "w") as f:
            json.dump(data, f)

    def run_cli(self, *args):
        return cli(*args, "--settings", self.settings, env=self.env)

    def test_fresh_install_and_uninstall(self):
        r = self.run_cli("install")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = self.read()["statusLine"]
        self.assertIn("promptsill", line["command"])
        self.assertEqual(line["refreshInterval"], 10)
        r = self.run_cli("uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("statusLine", self.read())

    def test_keeps_other_settings_and_backs_up(self):
        self.write({"model": "opus", "hooks": {"Stop": []}})
        self.assertEqual(self.run_cli("install").returncode, 0)
        data = self.read()
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["hooks"], {"Stop": []})
        with open(self.settings + ".promptsill-backup") as f:
            self.assertEqual(json.load(f), {"model": "opus", "hooks": {"Stop": []}})

    def test_foreign_statusline_needs_force_and_comes_back(self):
        foreign = {"type": "command", "command": "~/bin/my-line.sh", "padding": 1}
        self.write({"statusLine": foreign})
        r = self.run_cli("install")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.read()["statusLine"], foreign)
        self.assertEqual(self.run_cli("install", "--force").returncode, 0)
        self.assertIn("promptsill", self.read()["statusLine"]["command"])
        self.assertEqual(self.run_cli("uninstall").returncode, 0)
        self.assertEqual(self.read()["statusLine"], foreign)

    def test_reinstall_updates_own_entry(self):
        self.write({"statusLine": {"type": "command", "command": "/old/promptsill", "refreshInterval": 30}})
        self.assertEqual(self.run_cli("install", "--lang", "ru").returncode, 0)
        line = self.read()["statusLine"]
        self.assertTrue(line["command"].endswith("--lang ru"))
        self.assertEqual(line["refreshInterval"], 30)

    def test_broken_json_is_left_alone(self):
        with open(self.settings, "w") as f:
            f.write("{not json")
        r = self.run_cli("install")
        self.assertEqual(r.returncode, 1)
        with open(self.settings) as f:
            self.assertEqual(f.read(), "{not json")

    def test_uninstall_leaves_foreign_line(self):
        self.write({"statusLine": {"type": "command", "command": "other"}})
        self.assertEqual(self.run_cli("uninstall").returncode, 0)
        self.assertEqual(self.read()["statusLine"]["command"], "other")

    def test_plugin_data_copy_and_sync(self):
        data = os.path.join(self.dir, "plugin-data")
        self.assertEqual(self.run_cli("install", "--plugin-data", data).returncode, 0)
        copy = os.path.join(data, "promptsill")
        self.assertTrue(os.access(copy, os.X_OK))
        self.assertEqual(self.read()["statusLine"]["command"], copy)
        with open(copy, "a") as f:
            f.write("\n# stale\n")
        self.assertEqual(cli("_sync", data).returncode, 0)
        with open(copy) as a, open(SCRIPT) as b:
            self.assertEqual(a.read(), b.read())


class Badges(unittest.TestCase):
    def setUp(self):
        reset_opts()
        shutil.rmtree(ps.BADGES, ignore_errors=True)
        os.makedirs(ps.BADGES)

    def put(self, name, **data):
        with open(os.path.join(ps.BADGES, name + ".json"), "w") as f:
            json.dump(data, f)

    def texts(self, d=None, cwd="/work/app"):
        return [plain(p[1]) for p in ps.badges(d or {"session_id": "s1"}, cwd)]

    def test_shows_text_with_color(self):
        self.put("mode", text="humanize", color="green")
        parts = ps.badges({}, "/work")
        self.assertEqual(plain(parts[0][1]), "humanize")
        self.assertIn(ESC + "[32m", parts[0][1])

    def test_filters_session_folder_and_expiry(self):
        self.put("a", text="mine", session="s1")
        self.put("b", text="other session", session="s2")
        self.put("c", text="here", cwd="/work")
        self.put("d", text="elsewhere", cwd="/other")
        self.put("e", text="old", expires=time.time() - 1)
        self.put("f", text="fresh", expires=time.time() + 60)
        self.assertEqual(self.texts(), ["mine", "here", "fresh"])

    def test_bad_files_are_skipped(self):
        self.put("empty", text="")
        self.put("weird", text="a\x1b[31mb", priority="high", color="purple")
        with open(os.path.join(ps.BADGES, "broken.json"), "w") as f:
            f.write("{")
        self.assertEqual(self.texts(), ["a[31mb"])

    def test_no_folder(self):
        shutil.rmtree(ps.BADGES)
        self.assertEqual(ps.badges({}, "/"), [])

    def test_cli_set_list_clear(self):
        env = {"XDG_STATE_HOME": os.environ["XDG_STATE_HOME"]}
        self.assertEqual(cli("badge", "set", "mnrh-x", "hello", "world", "--color", "cyan", "--ttl", "60",
                             env=env).returncode, 0)
        data = json.load(open(os.path.join(ps.BADGES, "mnrh-x.json")))
        self.assertEqual(data["text"], "hello world")
        self.assertEqual(data["color"], "cyan")
        self.assertIn("mnrh-x", cli("badge", "list", env=env).stdout)
        self.assertEqual(cli("badge", "set", "bad/name", "x", env=env).returncode, 2)
        self.assertEqual(cli("badge", "set", "x", "y", "--color", "pink", env=env).returncode, 2)
        self.assertEqual(cli("badge", "clear", "mnrh-x", env=env).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(ps.BADGES, "mnrh-x.json")))


class Cli(unittest.TestCase):
    def test_stdin_json(self):
        d = {"workspace": {"current_dir": TMP}, "context_window": {"used_percentage": 5}}
        r = cli(stdin=json.dumps(d), env={"COLUMNS": "20", "LC_ALL": "en_US.UTF-8"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("context", r.stdout)

    def test_garbage_stdin(self):
        self.assertEqual(cli(stdin="junk").returncode, 0)

    def test_preview_and_version(self):
        self.assertEqual(cli("preview", "--lang", "ru", "--width", "200").returncode, 0)
        self.assertEqual(cli("--version").stdout.strip(), ps.VERSION)
        self.assertEqual(cli("bogus").returncode, 2)


if __name__ == "__main__":
    unittest.main()
