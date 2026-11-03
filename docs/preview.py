import importlib.machinery
import importlib.util
import os
import re
import sys
import time
from html import escape

os.environ["TZ"] = "UTC"
time.tzset()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader("promptsill", os.path.join(ROOT, "promptsill"))
spec = importlib.util.spec_from_loader("promptsill", loader)
ps = importlib.util.module_from_spec(spec)
loader.exec_module(ps)

NOW = 1_791_381_600
ps.BADGES = os.path.join(ROOT, "docs", "no-badges")
GIT = {"branch": "checkout-redesign", "ahead": 2, "behind": 0, "upstream": True, "changed": 3}
CALM = {"total": 16 * ps.GB, "used": 9.4 * ps.GB, "swap": 0, "gradle": 0, "kotlin": 0, "daemon_mem": 0, "sims": 0,
        "emulator": False}
BASE_DEMO = {
    "project": {"root": "/work/shop", "kinds": [], "ports": [], "node_dir": None,
                "repo": "https://github.com/acme/shop"},
    "git": GIT, "listeners": [], "node": None, "disk": 200 * ps.GB, "power": {}, "machine": CALM, "size": 0,
    "sessions": [{"sessionId": "demo", "status": "busy"}], "proxy": True,
}
BASE = {
    "session_id": "demo",
    "model": {"display_name": "Opus"},
    "effort": {"level": "high"},
    "workspace": {"current_dir": "/work/shop"},
    "context_window": {"used_percentage": 42},
    "rate_limits": {"five_hour": {"used_percentage": 63, "resets_at": NOW + 3 * 3600},
                    "seven_day": {"used_percentage": 35, "resets_at": NOW + 4 * 86400}},
    "prompt_cache": {"caching_observed": True, "warm": True, "ttl": "5m", "expires_at": NOW + 44, "requests": 12},
}
# Each scene is one snapshot of both lines, narrow enough that GitHub shows it near full size.
SCENES = [
    {"caption": {"en": "an ordinary hour: limit pace, cache timer, a reviewed pull request",
                 "ru": "обычный час: темп лимита, таймер кэша, PR с одобрением"},
     "data": {"pr": {"url": "https://github.com/acme/shop/pull/42", "review_state": "approved"}}},
    {"caption": {"en": "a web project: dev server, a port held by another folder, the wrong node",
                 "ru": "веб-проект: dev-сервер, порт занят другой папкой, не та версия node"},
     "data": {"model": {"display_name": "Sonnet"}, "effort": None, "context_window": {"used_percentage": 18},
              "rate_limits": {"five_hour": {"used_percentage": 12, "resets_at": NOW + 4 * 3600},
                              "seven_day": {"used_percentage": 35, "resets_at": NOW + 4 * 86400}},
              "prompt_cache": None},
     "demo": {"project": {"root": "/work/shop", "kinds": ["web"], "ports": [3000, 5173], "node_dir": "/work/shop",
                          "repo": "https://github.com/acme/shop"},
              "listeners": [{"pid": "1", "ports": [5173], "cwd": "/work/shop", "name": "vite"},
                            {"pid": "2", "ports": [3000], "cwd": "/work/api", "name": "node"}],
              "node": {"key": "node", "have": 20, "need": "22", "source": ".nvmrc"},
              "sessions": [{"sessionId": "demo", "bridgeSessionId": "session_01demo", "status": "busy"},
                           {"sessionId": "other", "name": "kcalm", "status": "waiting"}]}},
    {"caption": {"en": "an Android build on a busy Mac: a rebase with conflicts, swap, daemons, emulator",
                 "ru": "сборка Android на загруженном Mac: rebase с конфликтами, swap, демоны, эмулятор"},
     "data": {"context_window": {"used_percentage": 71}, "prompt_cache": None,
              "rate_limits": {"five_hour": {"used_percentage": 30, "resets_at": NOW + 2 * 3600},
                              "seven_day": {"used_percentage": 35, "resets_at": NOW + 4 * 86400}}},
     "demo": {"project": {"root": "/work/app", "kinds": ["mobile"], "ports": [], "node_dir": None,
                          "repo": "https://github.com/acme/app", "git_dir": "/work/app/.git"},
              "git": {"branch": "(detached)", "ahead": 0, "behind": 0, "upstream": False, "changed": 4, "conflicts": 2},
              "machine": {"total": 16 * ps.GB, "used": 14.6 * ps.GB, "swap": 2.1 * ps.GB, "gradle": 1, "kotlin": 1,
                          "daemon_mem": 1.9 * ps.GB, "sims": 0, "emulator": True},
              "sessions": [{"sessionId": "demo", "status": "busy"},
                           {"sessionId": "done", "name": "authmeister", "status": "idle",
                            "statusUpdatedAt": (NOW - 120) * 1000, "startedAt": (NOW - 3600) * 1000}]},
     "git_op": {"op": "rebase", "branch": "login-fix", "step": "3/7"}},
    {"caption": {"en": "back from a break: the cache expired, a proxy, a hot Mac, a full disk",
                 "ru": "после перерыва: кэш истек, прокси, Mac греется, диск почти полон"},
     "data": {"context_window": {"used_percentage": 64},
              "rate_limits": {"five_hour": {"used_percentage": 6, "resets_at": NOW + 4.5 * 3600},
                              "seven_day": {"used_percentage": 41, "resets_at": NOW + 4 * 86400}},
              "prompt_cache": {"caching_observed": True, "warm": False, "ttl": "5m", "requests": 40,
                               "recache_tokens_if_cold": 184000},
              "transcript_path": "/work/demo.jsonl"},
     "demo": {"git": {"branch": "main", "ahead": 0, "behind": 0, "upstream": True, "changed": 0},
              "power": {"hot": True, "battery": 15}, "disk": 12 * ps.GB, "size": 180 * ps.MB},
     "proxy": "KZ", "badges": [(2, ps.color("guard", ps.GREEN))]},
]


PALETTE = {"": "#d4d4d4", "2": "#7a7a7a", "31": "#f2777a", "32": "#99cc99", "33": "#ffcc66", "36": "#66cccc"}
CW, LH, PAD, FONT = 8.4, 22, 16, 14
TRACK_FILL = "#585858"
BLOCKS = {"█": 1, "▏": 1 / 8, "▎": 2 / 8, "▍": 3 / 8, "▌": 4 / 8, "▋": 5 / 8, "▊": 6 / 8, "▉": 7 / 8, "░": 1}


def scene_lines(scene, lang):
    ps.OPTS.update({"lang": lang, "ascii": False, "color": True, "links": True})
    demo = dict(BASE_DEMO, **scene.get("demo", {}))
    data = {k: v for k, v in dict(BASE, **scene.get("data", {})).items() if v is not None}
    saved = {name: getattr(ps, name) for name in ("cached", "git_op", "badges")}
    saved_env = {k: os.environ.pop(k, None) for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy",
                                                       "PROMPTSILL_PROXY_LABEL", "PROMPTSILL_PROXY_DETAIL",
                                                       "PROMPTSILL_PROXY_URL")}
    if scene.get("proxy"):
        os.environ.update(HTTPS_PROXY="http://127.0.0.1:7890", PROMPTSILL_PROXY_LABEL=scene["proxy"])
    ps.cached = lambda name, ttl, fn: demo[name.split("-")[0]]
    ps.git_op = lambda git_dir: scene.get("git_op")
    ps.badges = lambda d, cwd, now=None: list(scene.get("badges", []))
    real = ps.time.time
    ps.time.time = lambda: NOW
    try:
        return [ps.fit(ps.claude_line(data, NOW), 0), ps.fit(ps.work_line(data), 0)]
    finally:
        ps.time.time = real
        for name, fn in saved.items():
            setattr(ps, name, fn)
        for k in ("HTTPS_PROXY", "PROMPTSILL_PROXY_LABEL"):
            os.environ.pop(k, None)
        os.environ.update({k: v for k, v in saved_env.items() if v is not None})


def runs(line):
    line = re.sub(r"\033\]8;;[^\a]*\a", "", line)
    code, out = "", []
    for piece in re.split(r"(\033\[[0-9;]*m)", line):
        m = re.fullmatch(r"\033\[([0-9;]*)m", piece)
        if m:
            code = "" if m.group(1) in ("", "0") else m.group(1)
        elif piece:
            out.append((code, piece))
    return out


def style(code):
    bg = TRACK_FILL if code.endswith("48;5;240") else None
    fg = next((c for c in code.replace("48;5;240", "").split(";") if c in PALETTE), "")
    return PALETTE[fg], bg


def svg(rows):
    width = int(max(sum(len(t) for _, t in r) for r in rows) * CW + PAD * 2)
    height = int(len(rows) * LH + PAD * 2 - 6)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}">',
             f'<rect width="100%" height="100%" rx="8" fill="#1e1e1e"/>',
             f'<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="{FONT}">']
    for i, row in enumerate(rows):
        y = PAD + 14 + i * LH
        col = 0
        for code, text in row:
            fill, bg = style(code)
            if bg:
                parts.append(f'<rect x="{PAD + col * CW:.1f}" y="{y - 12}" width="{len(text) * CW:.1f}" height="15" '
                             f'fill="{bg}"/>')
            for m in re.finditer(r"[█▏▎▍▌▋▊▉░]|[^█▏▎▍▌▋▊▉░ ]+", text):
                chunk, x = m.group(0), PAD + (col + m.start()) * CW
                if chunk in BLOCKS:
                    opacity = ' opacity="0.45"' if chunk == "░" else ""
                    parts.append(f'<rect x="{x:.1f}" y="{y - 12}" width="{CW * BLOCKS[chunk]:.1f}" height="15" '
                                 f'fill="{fill}"{opacity}/>')
                else:
                    xs = " ".join(f"{x + j * CW:.1f}" for j in range(len(chunk)))
                    parts.append(f'<text x="{xs}" y="{y}" fill="{fill}">{escape(chunk)}</text>')
            col += len(text)
    parts.append("</g></svg>")
    return "\n".join(parts) + "\n"


def main():
    out = os.path.join(ROOT, "docs")
    for lang in ("en", "ru"):
        rows, text = [], []
        for i, scene in enumerate(SCENES):
            if i:
                rows.append([])
            rows.append([("2", "# " + scene["caption"][lang])])
            for line in scene_lines(scene, lang):
                rows.append(runs(line))
                text.append(ps.ESCAPES.sub("", line))
        with open(os.path.join(out, f"preview-{lang}.svg"), "w", encoding="utf-8") as f:
            f.write(svg(rows))
        print("\n".join(text))
        print(f"widest: {max(len(t) for t in text)} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
