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
loader = importlib.machinery.SourceFileLoader("promptsill", os.path.join(ROOT, "promptsill"))
spec = importlib.util.spec_from_loader("promptsill", loader)
ps = importlib.util.module_from_spec(spec)
loader.exec_module(ps)

NOW = 1_791_381_600
DEMO = {
    "project": {"root": "/work/shop", "kinds": ["web", "mobile"], "ports": [3000, 5173], "node_dir": "/work/shop",
                "repo": "https://github.com/acme/shop"},
    "git": {"branch": "checkout-redesign", "ahead": 2, "behind": 0, "upstream": True, "changed": 3},
    "listeners": [{"pid": "1", "ports": [5173], "cwd": "/work/shop", "name": "vite"},
                  {"pid": "2", "ports": [3000], "cwd": "/work/api", "name": "node"}],
    "node": {"key": "node", "have": 20, "need": "22", "source": ".nvmrc"},
    "machine": {"total": 16 * ps.GB, "used": 14.6 * ps.GB, "swap": 2.1 * ps.GB, "daemons": 2,
                "daemon_mem": 1.9 * ps.GB, "sims": 1, "emulator": False},
}
DATA = {
    "model": {"display_name": "Opus"},
    "workspace": {"current_dir": "/work/shop"},
    "context_window": {"used_percentage": 42},
    "rate_limits": {"five_hour": {"used_percentage": 63, "resets_at": NOW + 3 * 3600},
                    "seven_day": {"used_percentage": 35, "resets_at": NOW + 4 * 86400}},
    "prompt_cache": {"caching_observed": True, "warm": True, "ttl": "5m", "expires_at": NOW + 44, "requests": 12},
    "pr": {"url": "https://github.com/acme/shop/pull/42"},
}
PALETTE = {"": "#d4d4d4", "2": "#7a7a7a", "31": "#f2777a", "32": "#99cc99", "33": "#ffcc66", "36": "#66cccc"}
CW, LH, PAD, FONT = 8.4, 22, 16, 14
TRACK_FILL = "#585858"
BLOCKS = {"█": 1, "▏": 1 / 8, "▎": 2 / 8, "▍": 3 / 8, "▌": 4 / 8, "▋": 5 / 8, "▊": 6 / 8, "▉": 7 / 8, "░": 1}


def lines(lang):
    ps.OPTS.update({"lang": lang, "ascii": False, "color": True, "links": True})
    ps.cached = lambda name, ttl, fn: DEMO[name.split("-")[0]]
    real = ps.time.time
    ps.time.time = lambda: NOW
    try:
        return [ps.fit(ps.claude_line(DATA, NOW), 0), ps.fit(ps.work_line(DATA), 0)]
    finally:
        ps.time.time = real


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
        rendered = lines(lang)
        with open(os.path.join(out, f"preview-{lang}.svg"), "w", encoding="utf-8") as f:
            f.write(svg([runs(line) for line in rendered]))
        print("\n".join(ps.ESCAPES.sub("", line) for line in rendered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
