<p align="center"><img src="docs/icon.png" width="128" alt="promptsill icon"></p>

<h1 align="center">promptsill</h1>

<p align="center">A status line for <a href="https://code.claude.com">Claude Code</a> that knows about your dev machine, not just your session.</p>

<a href="docs/preview-en.png"><img src="docs/preview-en.svg" alt="promptsill status line in four situations. An ordinary hour: context with token counts, limit pace, cache timer, an approved pull request. A web project: Remote Control, a session waiting for you, a dev server, a port held by another folder, the wrong node version. An Android build on a busy Mac: Claude's todo progress and running tool, a rebase with conflicts, memory, swap, Gradle and Kotlin daemons, the emulator. Back from a break: a proxy, an expired cache, a newer Claude Code installed, a guard badge, overheating, low battery, low disk, a large session file"></a>

```text
Opus high · context ██▏   42% 84k/200k · 5h ███▏  63% +23%, runs out at 15:10, resets at 17:00 · week 35% · cache 44s
checkout-redesign ↑2 ±3 · approved · memory 9.4/16 GB
```

## What it shows that others don't

The second line is about the project you're in and the machine it runs on. Apart from the branch, each part appears only when it has something to say:

- **Git branch** with commits ahead and behind, `not pushed` and the number of changed files. It's clickable: it opens the pull request when one is open, otherwise the branch page. Next to it, `approved` or `changes requested` once the pull request has a review, and `worktree` when the session runs in a linked git worktree.
- **Unfinished git operations.** `rebasing 3/7, conflicts 2` in the middle of a rebase, and likewise `merging`, `cherry-picking`, `reverting` or `bisecting`. During a rebase the branch shows its own name instead of `(detached)`.
- **Your dev servers.** `vite :5173` when this project's server is running, clickable to open it in the browser.
- **Busy ports.** `:3000 taken: api` when the port your project needs is held by another folder's server.
- **Node version.** `node 20, need 22 (.nvmrc)` when the active `node` doesn't match `.nvmrc`, `.node-version` or `engines`.
- **Memory pressure** on macOS. Used memory and swap, yellow or red when free memory runs low or swap grows.
- **Gradle and Kotlin daemons**, counted separately, with the RAM they hold together: `Gradle 2 + Kotlin 1 (1.9 GB)`. Shown in JVM and Android projects, or anywhere when memory is tight or the daemons hold 1.5 GB or more.
- **iOS simulators and the Android emulator** in mobile projects, so you notice the ones you forgot to close.
- **A slowed-down Mac.** `CPU slowed to 70%` when macOS throttles the CPU, `overheating` on a thermal warning, `low power mode`, and `battery 15%` when the battery is at 20% or less and not charging. A build that suddenly takes twice as long usually has one of these behind it.
- **Low disk space.** `disk 12.0 GB free` once less than 15 GB is left on the home volume, red under 5 GB. Xcode's DerivedData, simulators and Gradle caches eat it quietly.
- **A huge session file**, from 50 MB up.

## The Claude part

The first line is about Claude Code itself.

- **Model, effort and fast mode.** `Opus xhigh fast`. On a narrow terminal only the model name stays.
- **Session name** from `--name`, `/rename` or Claude's own title, so parallel sessions are easy to tell apart.
- **Modes that differ from a plain session:** the vim mode (`NORMAL`, `INSERT`), `agent security-reviewer` when started with `--agent`, `style Explanatory` for a custom output style, and `thinking off`. `install` sets `hideVimModeIndicator`, so the vim mode isn't shown twice.
- **Context** as a bar with 1/8-cell precision, followed by the tokens in the window and its size: `42% 420k/1M`. With a 1M window the percentage alone hides how much room is left.
- **Limit pace.** For the 5-hour and weekly limits, promptsill compares how much you've used with how much of the window has passed. 60% in the first hour of five is a problem; 60% in the last hour is fine. Colors follow the pace, not the raw percentage. `+23%` means you're 23 points ahead of an even pace, and `runs out at 15:10` says when you'll hit the limit if you keep going like this.
- **Spend limit** behind a Claude gateway that sets one: `spend $12/$50`, or a percentage when the gateway doesn't report dollars. Colored by the same pace as the other limits when the gateway says whether the period is a day, a week or a month.
- **Prompt cache timer.** `cache 44s` shortly before the cache expires, and `cache expired (184k tokens)` after it has. The next message after expiry re-reads the whole conversation, here 184k tokens, which costs more of your limit; from 100k up it turns yellow. When the cache was rebuilt for another reason, promptsill says why for five minutes: `cache reset: tools changed`, `system prompt changed`, `model changed`, `history rewritten` or `server side`.
- **Remote Control.** `remote control` while the session is reachable from claude.ai or the Claude app, clickable to open it there. Claude Code doesn't pass this to status lines, so promptsill reads it from Claude Code's own session files in `~/.claude/sessions/`. That's an internal format; if a future version changes it, the label just stops appearing.
- **Proxy.** `proxy KZ` when the session's network goes through a proxy (`HTTPS_PROXY` or `ALL_PROXY` in the environment Claude Code runs with), red `proxy KZ down` when a proxy on this machine stops answering. The country comes from `PROMPTSILL_PROXY_LABEL`, which the tool that starts the proxy sets after checking the exit; promptsill itself makes no requests to find it out. Without the variable it just says `proxy`. `PROMPTSILL_PROXY_DETAIL` (say `vless 203.0.113.7`) and `PROMPTSILL_PROXY_URL` (an `http(s)://` or `file://` page about the exit) are optional. In a terminal that can click links the label links to that page and the detail stays off the line; in macOS Terminal, with `links` off or without a URL, the detail goes right after the label.
- **Cache health.** `cache hits 72%, 2 misses` once cache reads drop under 80% of the input or three requests have missed, yellow, red under 50%. A cache that keeps missing burns the limit with nothing else on screen.
- **What Claude is doing.** `todo 1/3: Running tests` while a TodoWrite list is open, and the tool call still waiting for its result, dimmed: `Bash: Run the test suite`, `Edit: app.py`, `github: create_pull_request`. promptsill reads the last 512 KB of the transcript for this.
- **A newer Claude Code.** `2.1.300 installed, restart` when `claude --version` is newer than the version the session runs. The check runs in the background once an hour, never while the line is drawn.
- **Lines and time.** `+156 −23` lines changed and how long the session has run, `2h 15m`. The first to go on a narrow terminal.
- **Your other sessions.** `kcalm waits for you` when another Claude Code session on this machine is stuck on a permission prompt or a question, and `authmeister done` for ten minutes after one finishes its turn. Three or more are counted: `3 sessions wait for you`. This also comes from `~/.claude/sessions/`.

When the terminal is narrow, promptsill shortens the parts first, then drops the least important ones. The limits, context and branch stay. CJK characters and emoji count as two columns.

## Subagent rows

Claude Code lists running subagents below the prompt. `install` also sets `subagentStatusLine`, and promptsill draws those rows:

```text
Explore · Find config files · Sonnet 5.5 high · 1m · ▁▄█ 68k 34%
```

That is who, what it is doing, the model and effort, how long it has run, a sparkline of its last token counts and its share of its context window, colored like the main context bar. Finished tasks say `done`, `failed` or `stopped`. When the panel is narrow, the description is cut first. If another tool already owns `subagentStatusLine`, `install` leaves it alone.

## Install

### Homebrew (macOS, Linux)

```bash
brew install kopylovis/tap/promptsill
promptsill install
```

### Claude Code plugin

```text
/plugin marketplace add kopylovis/promptsill
/plugin install promptsill@promptsill
/promptsill:setup
```

The plugin keeps its copy of promptsill up to date on every session start. Run `/promptsill:setup uninstall` before you uninstall the plugin.

### By hand

```bash
curl -fsSL https://raw.githubusercontent.com/kopylovis/promptsill/main/promptsill -o ~/.local/bin/promptsill
chmod +x ~/.local/bin/promptsill
promptsill install
```

promptsill is a single Python file with no dependencies. It needs `python3` 3.9 or newer, and uses `git`, `lsof`, `ps` and, on macOS, `pmset` when they're available. The cache timer needs Claude Code 2.1.251 or newer; everything else works with older versions.

## Commands

```text
promptsill install [--force] [--lang en|ru]   add the statusLine to ~/.claude/settings.json
promptsill uninstall                          remove it, and bring back the one it replaced
promptsill preview [--lang en|ru] [--width N] render sample data for the current folder
promptsill subagents [--lang en|ru]           rows for the agent panel, set up by install
promptsill badge set|clear|list ...           labels from hooks and scripts, see below
promptsill --version
```

`install` never replaces another status line unless you pass `--force`. When you do, the old one is saved and `uninstall` restores it. Before every change, `settings.json` is copied to `settings.json.promptsill-backup`. `CLAUDE_CONFIG_DIR` is respected.

## Settings

Labels are in English by default, and in Russian when your locale (`LC_ALL`, `LC_MESSAGES` or `LANG`) is Russian. To choose explicitly, use `install --lang ru`, the `PROMPTSILL_LANG` environment variable, or the config file.

Optional `~/.config/promptsill/config.json`:

```json
{
  "lang": "en",
  "links": true,
  "color": true,
  "ascii": false
}
```

- `links`: clickable links on the branch, review state, dev servers, Remote Control and badges ([OSC 8](https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda); iTerm2, Kitty, WezTerm, Ghostty and others, usually with Cmd-click or Ctrl-click; macOS Terminal doesn't support them).
- `color`: `false` turns colors off; so does the `NO_COLOR` environment variable.
- `ascii`: `[##---]` bars for fonts without block characters; also `PROMPTSILL_ASCII=1`.

## Badges from hooks and scripts

Any hook or script can put a short label on the second line, for example to show that a mode is on. A badge is a JSON file in `~/.local/state/promptsill/badges/` (or `$XDG_STATE_HOME/promptsill/badges/`), one file per badge. promptsill shows it on the next refresh and stops showing it when the file is gone.

```json
{"text": "humanize", "color": "green"}
```

Only `text` is required. The other fields:

- `color`: `green`, `yellow`, `red`, `cyan` or `dim`.
- `session`: show the badge only in the Claude Code session with this `session_id`. Hooks get it in their input.
- `cwd`: show it only in this folder and below.
- `expires`: Unix time after which the badge is ignored.
- `url`: makes the badge a clickable link.
- `priority`: 1 to 5, default 2. When the line doesn't fit, higher numbers are dropped first.

The same from the command line:

```bash
promptsill badge set build-mode release --color yellow --cwd ~/app --ttl 3600
promptsill badge clear build-mode
promptsill badge list
```

Names may contain letters, digits, `.`, `_` and `-`. Prefix them with your tool's name so they don't clash. promptsill shows at most 8 badges and strips control characters from the text.

## Privacy

promptsill runs locally and makes no network requests. It reads the JSON Claude Code sends it, the badge files, Claude Code's list of running sessions and the end of the session transcript, runs `git status`, `lsof`, `ps`, `pmset` and once an hour `claude --version`, and keeps a short cache in `~/.cache/promptsill`. Slow parts of it are refreshed by a detached `promptsill _refresh` process, so drawing the line never waits for them.

## Development

```bash
make test               # unit tests and smoke checks
./promptsill preview    # see the line for the current folder
python3 docs/preview.py # regenerate the pictures in docs/
```

## License

[MIT](LICENSE)
