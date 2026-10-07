---
description: Turn the promptsill status line on or off in ~/.claude/settings.json
disable-model-invocation: true
argument-hint: "[--force] [--lang en|ru] | uninstall"
allowed-tools: Bash(python3 *)
---

Run exactly one command with the Bash tool, then tell the user its result in one or two sentences.

- If the arguments are `uninstall`, run: `python3 "${CLAUDE_PLUGIN_ROOT}/promptsill" uninstall`
- Otherwise run: `python3 "${CLAUDE_PLUGIN_ROOT}/promptsill" install --plugin-data "${CLAUDE_PLUGIN_DATA}" $ARGUMENTS`

If install refuses because another statusLine is already set, show the user that command and ask whether to replace it. Only if they agree, run the same install command again with `--force` added. promptsill saves the replaced line, and `/promptsill:setup uninstall` puts it back.

Remind the user to run `/promptsill:setup uninstall` before uninstalling the plugin, because the status line runs from the plugin's data folder.
