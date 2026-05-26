---
description: Print a thermal-printer receipt for the current Claude Code session.
allowed-tools: [Bash]
---

Print a physical thermal-printer receipt for **this** Claude Code session.

The session id is exposed by Claude Code in `$CLAUDE_CODE_SESSION_ID`
(verified on 2026-05-26). The cwd is `$PWD`. Both are passed via argv
to keep a malicious cwd from injecting shell.

Run exactly this command (no rephrasing, no expansion):

```bash
thermal-print print receipt --session-id "$CLAUDE_CODE_SESSION_ID" --cwd "$PWD"
```

If it exits non-zero, surface the stderr output to the user verbatim
and stop — do not try to print again or work around the error.
