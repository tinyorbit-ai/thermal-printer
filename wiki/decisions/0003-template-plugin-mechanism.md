# ADR 0003 — Template plugin mechanism

**Status:** accepted (Planning) · part of [[index]]

## Context

[[brief]] commits to a system of **printable rituals**, not a single `/receipt`
command — `/receipt` is the first template; future templates (morning intention,
ship receipt, end-of-day summary) plug in without forking the tool. We need to
pick how templates are registered and dispatched. Get this right once, then every
future ritual is "drop a file."

## Decision

- Templates live in `src/thermal_print/templates/`, one per file.
- Each template module exposes two attributes:
  - `NAME: str` — the dispatch key, e.g. `"receipt"`, `"morning"`, `"hello"`.
  - `render(ctx: dict, r: Receipt) -> None` — populates the `Receipt` builder
    from [[decisions/0004-receipt-layout-grammar]] using context from `ctx`.
- At CLI startup, the dispatcher walks `templates/`, imports each module, and
  builds the registry `{NAME: render}`. No central list to keep in sync.
- The CLI dispatches `thermal-print print <NAME> [args]` to the matching
  `render(ctx, r)`. `ctx` is built from CLI args + env (session id, cwd,
  user-supplied free text, etc.).
- A bad template module raises at import; we surface the offending filename and
  exit non-zero. Better noisy than silently dropping a template.

## Why

- **Zero friction for the next ritual.** Drop `templates/morning.py`, done. This
  matches the prototype-first ethos and removes the temptation to *not* add a
  template because of registration boilerplate.
- **One source of truth.** With auto-discovery, the filesystem is the registry.
  No drift between an explicit list and what's actually on disk.
- **Local-only scope.** Templates ship inside the package — no plugin lookup
  across `sys.path`, no entry-points indirection. Personal tool, single repo.

## Alternatives considered

- **Explicit registry in `templates/__init__.py`.** Every new template adds an
  import + a dict entry. Boilerplate per ritual, second source of truth that
  drifts. Rejected.
- **`if/elif` switch in `cli.py`.** Fastest to MVP, but undermines the
  template-system commitment from the brief. Rejected — we paid for the
  abstraction, we should use it from the start.
- **Python entry points (`[project.entry-points."thermal_print.templates"]`).**
  Right answer for external plugins; overkill when all templates live in this
  repo, and complicates dev installs. Rejected.
- **YAML/markdown DSL.** Templates as data, not code. Strong long-term play if
  template count explodes, but adds a renderer layer up front for no win at <5
  templates. Captured in [[improvements]] if it ever earns the right to land.

## Consequences

- Every CLI invocation imports every template at startup — keep template imports
  cheap (no module-level I/O, no LLM SDK import unless the module needs it).
- A syntactically broken template breaks the whole CLI until fixed. The
  discovery loader must raise with the filename, not a stack trace from the
  middle of an unrelated import.
- Each template owns its own `ctx` keys it cares about (`session_id`, `cwd`,
  `text`). The dispatcher passes `ctx` through unfiltered; templates ignore
  what they don't need. No per-template argparse subparser in phase 2 — revisit
  if templates start needing wildly different CLI flags.
- Tests can list `templates/` and assert each module exposes `NAME` + `render` —
  a cheap structural check.
