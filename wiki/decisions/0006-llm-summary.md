# ADR 0006 — Narrative summary on the receipt

**Status:** accepted (revised 2026-05-27) · part of [[index]]

## Context

`/receipt` is the end-to-end test of the whole brief: stats + Claude
logo + project header + serial + a 3-5 line **narrative** summary that
makes the receipt feel less like a dashboard and more like a
celebration. The stats are deterministic and sacred (ADR 0005). The
narrative is freeform text.

The **first version of this ADR** (2026-05-26) wired the narrative to a
direct Anthropic Haiku API call from inside `thermal_print/llm.py`:
pinned model id, hard request deadline, transcript-excerpt slicing
rule, graceful-degrade matrix (`ANTHROPIC_API_KEY` unset, timeout, 401,
429, 500, malformed response). About 150 lines of code, an extra
runtime dep, an extra environment variable, and a per-invocation API
cost.

That design solved a problem that doesn't exist for this project: it
treated `thermal-print` as a self-contained CLI that needed to work
from cron jobs, scripts, and arbitrary contexts. The brief has only
one entry point — `/receipt` from inside a live Claude Code session.

## Decision

**The narrative is generated in the parent Claude Code session, not by
`thermal-print`.** The `/receipt` slash command is a Claude Code prompt
that:

1. Reads its own current transcript (already in context — no JSONL read,
   no excerpt slicing).
2. Writes a 3-5 line summary (each line ≤ 32 chars) directly.
3. Invokes `thermal-print print receipt --session-id <id> --cwd <pwd>
   --summary "<lines>"` via argv.

The CLI does the deterministic stats portion (reads JSONL, parses
tokens/files/tools, renders bitmap, sends Star Graphic raster). It
does **not** call any LLM.

If `--summary` is not provided (or is empty), the receipt prints
`(summary unavailable)` and the stats are unchanged. This is the
graceful-degrade path for any non-slash-command invocation.

## Why this is better

- **No `ANTHROPIC_API_KEY`.** No env var to configure, no key rotation
  to manage, no "wait did I source my dotenv".
- **Zero marginal cost.** The narrative uses the existing Claude Code
  subscription instead of incurring a per-call Anthropic API charge.
- **Higher-quality summary.** The parent agent has the full session
  transcript in context — the original ADR's "last 3 user turns + last
  assistant turn, capped at 8000 chars" slicing rule was a workaround
  for a context limit that doesn't apply here.
- **Drops the `anthropic` runtime dep** (and ~5 transitive packages).
- **Drops ~150 lines of fault-handling code.** The whole
  graceful-degrade matrix collapses to one case: `--summary` absent →
  `(summary unavailable)`.
- **Right place for taste decisions.** The slash command markdown is
  the single source of truth for tone, line count, length limits, what
  counts as boilerplate. Tweaking the narrative voice is editing one
  prompt file, not redeploying Python.

## Trade-off accepted

`thermal-print print receipt` invoked outside Claude Code (e.g. a cron
job, a shell script, an automation) prints `(summary unavailable)`.
The brief's only intended entry point is `/receipt` from a live Claude
Code session, so this is a non-cost for this tool — but if a second
caller ever appears it'll need to generate its own narrative and pass
it via `--summary`.

## Trust-boundary note (unchanged)

The slash command writes a narrative based on the live session
transcript and passes it back to the local CLI. No new network call,
no new trust boundary — the transcript stays inside the
already-authenticated Claude Code session.

The CLI invocation is **argv, not shell-interpolated**: a malicious
`cwd` cannot inject a command into the Bash that runs the receipt.

## Slash command shape

`.claude/commands/receipt.md` is a single-shot prompt with one
`allowed-tools: [Bash]` line. It instructs the parent agent to:

1. Write the 3-5 line summary directly from its context.
2. Invoke `thermal-print print receipt --session-id "$CLAUDE_CODE_SESSION_ID"
   --cwd "$PWD" --summary "<lines>"`.

Session-id mechanism: `$CLAUDE_CODE_SESSION_ID`, probed and verified
live on 2026-05-27 — see [[build-log]] phase 5 entry.

## Alternatives considered

- **Original ADR (direct Anthropic API).** See "Context" above —
  solved a non-problem. Superseded.
- **Subagent via Task tool.** Could spawn a separate Claude Code agent
  for the summary, but the parent already has the transcript and the
  taste; spawning is just overhead. Rejected.
- **CLI calls a local-only LLM (Ollama / llama.cpp).** Adds a heavy
  runtime dep for a 3-5 line task. Rejected — the parent agent is
  already running.
- **Hand-coded summary template ("Used N tokens, ran M tools…").**
  That's just the stats rows in prose form. The point of a narrative
  is the *taste*, which a template can't provide. Rejected.

## Consequences

- `src/thermal_print/llm.py` was deleted in the same change that
  accepted this ADR (2026-05-27).
- `anthropic` removed from `pyproject.toml`.
- `tests/test_llm.py` deleted; `tests/test_receipt_template.py`
  collapses its fault-mode matrix to a single
  "no `--summary` → `(summary unavailable)`" test plus a
  "valid `--summary` prints" test.
- `.claude/commands/receipt.md` rewritten to generate the narrative
  in-context and pass via `--summary`.
- README updated to drop `ANTHROPIC_API_KEY` mention.
