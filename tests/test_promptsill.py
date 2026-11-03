import importlib.machinery
import importlib.util
import json
import os
import shutil
import socket
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


class Model(unittest.TestCase):
    def setUp(self):
        reset_opts()

    def test_effort_and_fast(self):
        d = {"model": {"display_name": "Opus 5.5"}, "effort": {"level": "xhigh"}, "fast_mode": True}
        part = ps.model_part(d)
        self.assertEqual(plain(part[1]), "Opus 5.5 xhigh fast")
        self.assertEqual(plain(part[2]), "Opus 5.5")

    def test_plain_model(self):
        self.assertEqual(plain(ps.model_part({"model": {"display_name": "Haiku"}, "fast_mode": False})[1]), "Haiku")
        self.assertIsNone(ps.model_part({}))


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

    def test_spend_limit_in_dollars(self):
        lim = {"used_percentage": 24, "resets_at": self.now + 20 * 86400, "used_usd": 12.4, "limit_usd": 50,
               "period": "monthly"}
        self.assertEqual(plain(ps.limit_part("spend_limit", lim, self.now)[1]), "spend $12/$50")
        lim = {"used_percentage": 80, "resets_at": self.now + 20 * 3600, "period": "daily"}
        text = plain(ps.limit_part("spend_limit", lim, self.now)[1])
        self.assertTrue(text.startswith("spend 80% +63%, runs out"), text)
        lim = {"used_percentage": 95, "resets_at": self.now + 3600}
        self.assertIn(ESC + "[31m", ps.limit_part("spend_limit", lim, self.now)[1])

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

    def test_expired_with_cost(self):
        c = {"caching_observed": True, "warm": False, "expires_at": None, "requests": 3,
             "recache_tokens_if_cold": 184000}
        part = ps.cache_part(c, 1000)
        self.assertEqual(plain(part[1]), "cache expired (184k tokens)")
        self.assertIn(ESC + "[33m", part[1])
        self.assertEqual(plain(part[2]), "cache expired")
        c["recache_tokens_if_cold"] = 20000
        self.assertIn(ESC + "[2m", ps.cache_part(c, 1000)[1])

    def test_recent_miss_with_cause(self):
        c = {"caching_observed": True, "warm": True, "ttl": "5m", "expires_at": 1000 + 250, "requests": 3,
             "last_miss_at": 1000 - 30, "last_miss_cause": {"causes": ["tools_changed", "unknown"]}}
        self.assertEqual(plain(ps.cache_part(c, 1000)[1]), "cache reset: tools changed")
        reset_opts(lang="ru")
        self.assertEqual(plain(ps.cache_part(c, 1000)[1]), "кэш сброшен: сменились инструменты")
        reset_opts()
        c["last_miss_at"] = 1000 - 600
        self.assertIsNone(ps.cache_part(c, 1000))
        c["last_miss_at"], c["last_miss_cause"] = 1000 - 30, {"causes": ["ttl_expired_5m"]}
        self.assertIsNone(ps.cache_part(c, 1000))

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

    def test_review_state(self):
        reset_opts()
        d = {"pr": {"number": 7, "url": "https://github.com/a/b/pull/7", "review_state": "changes_requested"}}
        part = ps.review_part(d)
        self.assertEqual(plain(part[1]), "changes requested")
        self.assertIn(ESC + "[31m", part[1])
        self.assertIn("pull/7", part[1])
        self.assertEqual(plain(ps.review_part({"pr": {"review_state": "approved"}})[1]), "approved")
        self.assertIsNone(ps.review_part({"pr": {"review_state": "pending"}}))
        self.assertIsNone(ps.review_part({}))

    def test_worktree(self):
        reset_opts()
        g = {"branch": "feat-x"}
        self.assertEqual(plain(ps.worktree_part({"worktree": {"name": "feat-x"}}, g)[1]), "worktree")
        self.assertEqual(plain(ps.worktree_part({"workspace": {"git_worktree": "wt2"}}, g)[1]), "worktree wt2")
        self.assertIsNone(ps.worktree_part({"workspace": {}}, g))

    def test_repo_from_claude_json(self):
        d = {"workspace": {"repo": {"host": "github.com", "owner": "o", "name": "r"}}}
        self.assertEqual(ps.repo_url(d, {"repo": None}), "https://github.com/o/r")


class Daemons(unittest.TestCase):
    def test_names(self):
        self.assertEqual(ps.daemon_names(2, 1), "Gradle 2 + Kotlin 1")
        self.assertEqual(ps.daemon_names(0, 1), "Kotlin 1")
        self.assertEqual(ps.daemon_names(3, 0), "Gradle 3")
        self.assertEqual(ps.daemon_names(0, 0), "")

    def test_counts_from_ps(self):
        out = ("2071552 /usr/bin/java -cp gradle-daemon-main-9.8.0.jar org.gradle.launcher.daemon.bootstrap.GradleDaemon 9.8.0\n"
               "30000 /usr/bin/java -cp kotlin-daemon.jar org.jetbrains.kotlin.daemon.KotlinCompileDaemon\n"
               "1000 /bin/zsh\n")
        real = ps.run
        ps.run = lambda cmd, **kw: out
        try:
            m = ps.processes()
        finally:
            ps.run = real
        self.assertEqual((m["gradle"], m["kotlin"]), (1, 1))
        self.assertEqual(m["daemon_mem"], (2071552 + 30000) * 1024)


class RemoteControl(unittest.TestCase):
    def setUp(self):
        reset_opts()
        self.dir = tempfile.mkdtemp(dir=TMP)
        os.makedirs(os.path.join(self.dir, "sessions"))
        os.environ["CLAUDE_CONFIG_DIR"] = self.dir
        os.environ.pop("CLAUDE_CODE_BRIDGE_SESSION_ID", None)

    def tearDown(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        os.environ.pop("CLAUDE_CODE_BRIDGE_SESSION_ID", None)

    def put(self, pid, **data):
        with open(os.path.join(self.dir, "sessions", f"{pid}.json"), "w") as f:
            json.dump({"pid": pid, **data}, f)

    def test_on_from_registry(self):
        self.put(os.getpid(), sessionId="s1", bridgeSessionId="session_01ABC", messagingSocketPath="/tmp/x.sock")
        sessions = ps.live_sessions()
        self.assertNotIn("messagingSocketPath", sessions[0])
        self.assertEqual(ps.remote_control({"session_id": "s1"}, sessions), "session_01ABC")

    def test_off_when_registry_has_no_bridge(self):
        self.put(os.getpid(), sessionId="s1")
        os.environ["CLAUDE_CODE_BRIDGE_SESSION_ID"] = "session_stale"
        self.assertIsNone(ps.remote_control({"session_id": "s1"}, ps.live_sessions()))

    def test_env_when_no_registry(self):
        os.environ["CLAUDE_CODE_BRIDGE_SESSION_ID"] = "session_01XYZ"
        self.assertEqual(ps.remote_control({"session_id": "s1"}, []), "session_01XYZ")

    def test_dead_and_broken_entries_skipped(self):
        dead = subprocess.Popen([sys.executable, "-c", ""])
        dead.wait()
        self.put(dead.pid, sessionId="s1", bridgeSessionId="session_dead")
        with open(os.path.join(self.dir, "sessions", "9.json"), "w") as f:
            f.write("{")
        self.assertEqual(ps.live_sessions(), [])

    def test_bad_id_ignored(self):
        self.assertIsNone(ps.remote_control({"session_id": "s1"},
                                            [{"sessionId": "s1", "bridgeSessionId": "../../evil?x=1"}]))

    def test_part_links_to_session(self):
        self.put(os.getpid(), sessionId="s1", bridgeSessionId="session_01ABC")
        ps.cached = lambda name, ttl, fn, real=ps.cached: fn() if name == "sessions" else real(name, ttl, fn)
        try:
            part = ps.remote_part({"session_id": "s1"})
        finally:
            ps.cached = ps.cached.__defaults__[0]
        self.assertEqual(plain(part[1]), "remote control")
        self.assertIn("https://claude.ai/code/session_01ABC", part[1])
        self.assertEqual(plain(part[2]), "RC")


class Proxy(unittest.TestCase):
    NAMES = ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "PROMPTSILL_PROXY_LABEL",
             "PROMPTSILL_PROXY_DETAIL", "PROMPTSILL_PROXY_URL", "TERM_PROGRAM")

    def setUp(self):
        reset_opts()
        self.saved = {k: os.environ.pop(k, None) for k in self.NAMES}

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_no_proxy(self):
        self.assertIsNone(ps.proxy_part())

    def test_target_parsing(self):
        os.environ["https_proxy"] = "http://user:pw@corp.example:8080"
        self.assertEqual(ps.proxy_target(), ("corp.example", 8080))
        os.environ["ALL_PROXY"] = "socks5h://[::1]:1080"
        del os.environ["https_proxy"]
        self.assertEqual(ps.proxy_target(), ("::1", 1080))

    def test_label_and_remote_proxy(self):
        os.environ["HTTPS_PROXY"] = "http://corp.example:8080"
        os.environ["PROMPTSILL_PROXY_LABEL"] = "KZ\x1b[31m"
        part = ps.proxy_part()
        self.assertEqual(plain(part[1]), "proxy KZ31m")
        self.assertIn(ESC + "[32m", part[1])

    def test_detail_inline_where_links_cannot_be_clicked(self):
        os.environ["HTTPS_PROXY"] = "http://corp.example:8080"
        os.environ["PROMPTSILL_PROXY_LABEL"] = "KZ"
        os.environ["PROMPTSILL_PROXY_DETAIL"] = "vless 203.0.113.7\x1b]8;;x"
        os.environ["PROMPTSILL_PROXY_URL"] = "file:///Users/me/.local/state/mnrh/proxy/exit.html"
        os.environ["TERM_PROGRAM"] = "Apple_Terminal"
        part = ps.proxy_part()
        self.assertEqual(plain(part[1]), "proxy KZ vless 203.0.113.78x")
        self.assertNotIn("]8;;", part[1])
        reset_opts(links=False)
        os.environ["PROMPTSILL_PROXY_DETAIL"] = "vless 203.0.113.7"
        os.environ["TERM_PROGRAM"] = "iTerm.app"
        self.assertEqual(plain(ps.proxy_part()[1]), "proxy KZ vless 203.0.113.7")

    def test_detail_behind_link_where_clickable(self):
        os.environ["HTTPS_PROXY"] = "http://corp.example:8080"
        os.environ["PROMPTSILL_PROXY_LABEL"] = "KZ"
        os.environ["PROMPTSILL_PROXY_DETAIL"] = "vless 203.0.113.7"
        os.environ["PROMPTSILL_PROXY_URL"] = "file:///Users/me/.local/state/mnrh/proxy/exit.html"
        os.environ["TERM_PROGRAM"] = "iTerm.app"
        part = ps.proxy_part()
        self.assertEqual(plain(part[1]), "proxy KZ")
        self.assertIn("]8;;file:///Users/me/.local/state/mnrh/proxy/exit.html", part[1])
        os.environ["PROMPTSILL_PROXY_URL"] = "javascript:alert(1)"
        self.assertEqual(plain(ps.proxy_part()[1]), "proxy KZ vless 203.0.113.7")

    def test_local_proxy_down_and_up(self):
        with socket.socket() as srv:
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            port = srv.getsockname()[1]
            os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{port}"
            os.environ["PROMPTSILL_PROXY_LABEL"] = "KZ"
            real = ps.cached
            ps.cached = lambda name, ttl, fn: fn()
            try:
                self.assertEqual(plain(ps.proxy_part()[1]), "proxy KZ")
                srv.close()
                part = ps.proxy_part()
            finally:
                ps.cached = real
        self.assertEqual(plain(part[1]), "proxy KZ down")
        self.assertEqual(part[0], 1)


class OtherSessions(unittest.TestCase):
    now = 1_800_000_000

    def setUp(self):
        reset_opts()

    def s(self, sid, status, ago, name=None, started_ago=3600):
        return {"sessionId": sid, "status": status, "name": name or sid, "cwd": "/w/" + sid,
                "statusUpdatedAt": (self.now - ago) * 1000, "startedAt": (self.now - started_ago) * 1000}

    def texts(self, sessions):
        return [plain(p[1]) for p in ps.others_parts({"session_id": "me"}, sessions, self.now)]

    def test_waiting_and_done(self):
        sessions = [self.s("me", "waiting", 5), self.s("kcalm", "waiting", 30), self.s("auth", "idle", 60),
                    self.s("old", "idle", 3600), self.s("busy", "busy", 10)]
        self.assertEqual(self.texts(sessions), ["kcalm waits for you", "auth done"])
        reset_opts(lang="ru")
        self.assertEqual(self.texts(sessions), ["kcalm ждет тебя", "auth закончила"])

    def test_fresh_idle_session_is_not_done(self):
        self.assertEqual(self.texts([self.s("new", "idle", 60, started_ago=61)]), [])

    def test_many_are_counted(self):
        sessions = [self.s(n, "waiting", 10) for n in ("a", "b", "c")] + [self.s(n, "idle", 10) for n in ("d", "e")]
        self.assertEqual(self.texts(sessions), ["3 sessions wait for you", "d, e done"])

    def test_name_falls_back_to_folder(self):
        s = self.s("x", "waiting", 10)
        s["name"] = None
        self.assertEqual(self.texts([s]), ["x waits for you"])


class Disk(unittest.TestCase):
    def setUp(self):
        reset_opts()

    def test_only_when_low(self):
        self.assertIsNone(ps.disk_part(100 * ps.GB))
        self.assertIsNone(ps.disk_part(None))
        part = ps.disk_part(12 * ps.GB)
        self.assertEqual(plain(part[1]), "disk 12.0 GB free")
        self.assertIn(ESC + "[33m", part[1])
        self.assertIn(ESC + "[31m", ps.disk_part(3 * ps.GB)[1])

    def test_reads_home(self):
        self.assertGreater(ps.disk_free(), 0)


class GitState(unittest.TestCase):
    def setUp(self):
        reset_opts()
        self.git_dir = tempfile.mkdtemp(dir=TMP)

    def write(self, *path, text=""):
        full = os.path.join(self.git_dir, *path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)

    def test_nothing_in_progress(self):
        self.assertIsNone(ps.git_op(self.git_dir))
        self.assertIsNone(ps.git_op(None))
        self.assertIsNone(ps.op_part(None, {"conflicts": 0}))

    def test_rebase_with_conflicts(self):
        self.write("rebase-merge", "head-name", text="refs/heads/feat\n")
        self.write("rebase-merge", "msgnum", text="3\n")
        self.write("rebase-merge", "end", text="7\n")
        op = ps.git_op(self.git_dir)
        self.assertEqual(op, {"op": "rebase", "branch": "feat", "step": "3/7"})
        g = {"branch": "(detached)", "ahead": 0, "behind": 0, "upstream": False, "changed": 2, "conflicts": 2}
        self.assertEqual(plain(ps.op_part(op, g)[1]), "rebasing 3/7, conflicts 2")
        self.assertIn(ESC + "[31m", ps.op_part(op, g)[1])
        self.assertTrue(plain(ps.branch_part(g, {"repo": None}, {}, op)[1]).startswith("feat ±2"))

    def test_merge(self):
        self.write("MERGE_HEAD", text="abc\n")
        op = ps.git_op(self.git_dir)
        self.assertEqual(plain(ps.op_part(op, {"conflicts": 0})[1]), "merging")
        reset_opts(lang="ru")
        self.assertEqual(plain(ps.op_part(op, {"conflicts": 1})[1]), "слияние, конфликты 1")

    def test_conflict_lines_counted(self):
        out = "# branch.head main\n1 .M N... 100644 100644 100644 a b f\nu UU N... 100644 100644 100644 100644 a b c g\n"
        real = ps.run
        ps.run = lambda cmd, **kw: out
        try:
            g = ps.git("/x")
        finally:
            ps.run = real
        self.assertEqual((g["changed"], g["conflicts"]), (2, 1))


class Power(unittest.TestCase):
    def setUp(self):
        reset_opts()

    def fake(self, outputs):
        real_run, real_platform = ps.run, ps.sys.platform
        ps.run = lambda cmd, **kw: outputs.get(" ".join(cmd[1:]), "")
        ps.sys.platform = "darwin"
        try:
            return ps.power()
        finally:
            ps.run, ps.sys.platform = real_run, real_platform

    def test_calm_mac(self):
        p = self.fake({"-g": " lowpowermode         0\n",
                       "-g therm": "Note: No thermal warning level has been recorded\n",
                       "-g batt": "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t100%; charged; 0:00 remaining\n"})
        self.assertEqual(p, {"low_power": False})
        self.assertEqual(ps.power_parts(p), [])

    def test_hot_slow_and_draining(self):
        p = self.fake({"-g": " lowpowermode         1\n",
                       "-g therm": "Thermal warning level set to 2.\n\tCPU_Speed_Limit \t= 70\n",
                       "-g batt": " -InternalBattery-0 (id=1)\t9%; discharging; 0:20 remaining\n"})
        self.assertEqual(p, {"low_power": True, "cpu_limit": 70, "hot": True, "battery": 9})
        texts = [plain(x[1]) for x in ps.power_parts(p)]
        self.assertEqual(texts, ["CPU slowed to 70%", "low power mode", "battery 9%"])
        self.assertIn(ESC + "[31m", ps.power_parts(p)[2][1])
        self.assertEqual([plain(x[1]) for x in ps.power_parts({"hot": True})], ["overheating"])

    def test_off_macos(self):
        real = ps.sys.platform
        ps.sys.platform = "linux"
        try:
            self.assertEqual(ps.power(), {})
        finally:
            ps.sys.platform = real


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
