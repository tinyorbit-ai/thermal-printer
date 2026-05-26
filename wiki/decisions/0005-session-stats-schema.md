# ADR 0005 — Session stats schema

**Status:** accepted (Phase 4) · part of [[index]]

## Context

`/receipt` needs to render the **deterministic** facts of a Claude Code
session: tokens, time, files, tools. The narrative summary is a phase-5
bonus; this is the contract that must always print, even when the LLM
call fails (see [[decisions/0006-llm-summary]] for the trust line).

Real Claude Code JSONL files (verified on `~/.claude/projects/-Users-USER-code-thermal-printer/*.jsonl`, 2026-05-26) contain multiple line types:
`assistant`, `user`, `system`, `attachment`, `last-prompt`, `ai-title`,
`file-history-snapshot`. **Only `assistant` lines carry `.message.usage`.**
The file is appended to *live* while `/receipt` reads it.

## Decision

### What the receipt shows

`SessionStats` (`src/thermal_print/session.py`) is the receipt's contract:

| Field                       | Source                                                          |
|-----------------------------|-----------------------------------------------------------------|
| `input_tokens`              | sum of `.message.usage.input_tokens` on `type=="assistant"`     |
| `output_tokens`             | sum of `.message.usage.output_tokens` on `type=="assistant"`    |
| `cached_input_tokens`       | sum of `.message.usage.cache_read_input_tokens`                 |
| `cached_creation_tokens`    | sum of `.message.usage.cache_creation_input_tokens`             |
| `duration_s`                | `last - first` of any line's `.timestamp` (ISO 8601)            |
| `files`                     | unique values of `tool_use.input.{file_path,path,notebook_path}` |
| `tools`                     | count of `tool_use.name` per tool, across all assistant content |
| `started_at`                | first `.timestamp` seen                                         |
| `model`                     | last `.message.model` seen on `type=="assistant"`               |
| `assistant_turns`           | count of `type=="assistant"` lines                              |

### What we drop, on purpose

- **`server_tool_use`, `service_tier`, `cache_creation`, `inference_geo`.**
  Present in the real `usage` object; not surfaced on the receipt. Tokens
  + cache reads + cache creations are already four numbers — adding more
  pushes the table off the legibility cliff.
- **Sidechain context**, `parentUuid`, `requestId`, `entrypoint`, etc.
  Useful for debugging Claude Code, not for a celebration receipt.
- **`subagent` tool details.** Tool *names* and counts are surfaced;
  argument bodies are not (would leak transcript content).

### Robustness rules

1. **Partial trailing line.** The JSONL is being appended to. `parse()`
   skips any line that fails `json.loads`, which absorbs the truncated
   last line without crashing.
2. **Empty session.** A brand-new session has zero `assistant` turns;
   `parse()` still returns a populated `SessionStats` with zeros, and the
   `session` template renders `(session just started)` instead of a
   table of zeros.
3. **Tolerant typing.** `.message.usage.input_tokens` *might* be missing,
   null, or non-int in a future schema change; coerced via
   `int(... or 0)` so an unexpected absence reads as zero rather than
   raising.

### Encoded-cwd resolution

Claude Code stores sessions at
`~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. The encoder
replaces any non-`[a-zA-Z0-9-]` character with `-`, so
`/Users/USER/.dotconfig/instances/default` becomes
`-Users-USER--dotconfig-instances-default` (the leading `/` and the `.`
both collapse to `-`, producing `--`). `find_project_dir()` encodes the
given cwd and looks up the matching directory — listing-based per the
hardened plan.

### Session selection

`--session-id` is **required** by default — `/receipt` always knows the
id, so always passes it. `--latest` exists as an interactive escape
hatch when the operator is debugging from the CLI manually.

## Why

- **Match what the eye expects.** The receipt models the four numbers
  the developer would describe verbally: how many tokens in, how many
  out, how much cache, how long. Adding `server_tool_use` adds friction
  for almost no recognition payoff.
- **The receipt is sacred.** Every robustness rule is in service of the
  same invariant: a receipt always prints — even mid-write, even on a
  brand-new session, even when a schema field shifts.
- **Explicit > recent.** Defaulting to "most recent" silently couples
  `/receipt` to whatever session happens to have touched disk last,
  which is the kind of bug that's invisible until it ruins a celebration
  receipt. `--session-id` makes the binding explicit.

## Alternatives considered

- **Surface every `usage` field.** Rejected — table density vs. legibility.
- **Pure `/`→`-` cwd encoding.** Rejected — real `~/.claude/projects/`
  entries prove the encoder collapses `.` and other non-alphanumeric chars
  to `-` too. Using pure `/`→`-` would silently miss the right directory.
- **Default to `--latest`.** Rejected — see above.
- **`SessionStats` as a dict instead of a dataclass.** Rejected — the
  template touches every field; a dataclass gives autocomplete, typed
  access, and a clear schema in this ADR's table.

## Consequences

- Any future schema change in Claude Code's JSONL that moves
  `.message.usage` will silently zero out our totals. The mitigation is
  the integration test (`test_can_resolve_this_project_if_present`) and
  the gate's `jq` cross-check — both will catch a structural shift before
  it hides on a printed receipt.
- The "drop server_tool_use" choice is reviewable: the data is in the
  JSONL; if a future receipt design wants it, it's a `SessionStats`
  field away.
- The encoded-cwd edge case (two different cwds encoding to the same
  directory) is a known lossy collision. For a single-user personal
  tool with a single `~/.claude/projects/` namespace, the probability is
  vanishingly small; documented here so future-Matt sees it before it
  bites.
