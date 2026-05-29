# Retrospectives

Part of [[index]]. Running synthesis appended by `forge-retro`. Newest on top. One
entry per retro: what shipped, recurring patterns, what went well, what to improve.

<!-- Entry shape:
## YYYY-MM-DD — Retro (phases A–B)
- **Shipped:** <the build story, not a changelog>
- **Patterns:** <recurring issue classes, citing phases/learnings>
- **Kept:** <what went well, worth reinforcing>
- **Improve:** <concrete process changes>
- **Open:** <unresolved threads> -->

## 2026-05-29 — Retro (phases 1–5 + the hardware pivot)

The whole arc, end to end: a personal CLI that prints Claude Code sessions as
physical receipts. Reading it back, one decision shaped everything that followed —
*when* we let the printer prove itself.

### Shipped

Five planned phases plus an unplanned sixth landed the brief in full. Phase 1 put
the CLI and the raw-USB seam in place; phase 2 turned the receipt grammar (ADR
0004) into real code with a single cut-emitter and a snapshot test; phase 3 made
each receipt a *designed object* — logo, persisted serial, footer; phase 4 read
Claude Code's own JSONL and rendered the deterministic session stats; phase 5
wired the `/receipt` slash command and an LLM narrative. All five passed their
code-only gates and squash-merged cleanly, one commit each.

Then phase 1's deferred hardware step ran — and rewrote the foundation. The
TSP143IIIU doesn't speak ESC/POS, StarPRNT, *or* Star Line Mode; it accepts only
Star Graphic raster bitmaps and silently drops everything else (see
[[notes/2026-05-27-tsp143iiiu-default-mode]]). `printer.py` and `Receipt` were
rewritten around a growing PIL canvas + reverse-engineered raster protocol; the
direct-Anthropic `llm.py` was deleted in favour of the parent agent writing the
summary from its own in-context transcript. The architecture's seams held — every
template was unchanged at the API level through both pivots.

### Patterns (the one most worth acting on first)

- **A correctly-identified risk was operationally de-fanged by deferring its
  gate.** The hardening review named the printer's command dialect *the* single
  unproven dependency the whole project rests on, and phase 1's gate was written
  to retire it ("paper coming out, not 'set up the project'"). Then hardware
  verification was deferred to the end of the loop — so phases 1–5 all went green
  on *code-only* gates (every build-log entry carries a ⏳ "Gate 1, hardware,
  deferred"), and ~3 hours of byte-level rework plus a `printer.py`/`Receipt`
  rewrite surfaced only after all five had "landed." The plan was right; the
  sequencing undid it. This is the prototype-first principle inverted: phase 1
  was supposed to be the thinnest thing that *physically runs*, and it became the
  thinnest thing that *type-checks*.
- **Robustness was invested before necessity was confirmed.** Phase 5 built
  `llm.py` with a five-way fault matrix (no-key / timeout / 401 / 429 / 500 /
  malformed), an ADR, and a dedicated test suite — then the pivot deleted the
  whole module on realizing the only real entry point (`/receipt` inside a live
  session) already has the transcript in context. We hardened a component before
  asking whether it sat on the only real path.
- **Guess-vs-verify, decided per field, predicted the outcome.** Where the build
  verified against ground truth it won; where it guessed it paid. Phase 4 checked
  token math against an independent `jq` extraction and discovered the encoded-cwd
  encoder by *listing* `~/.claude/projects/` instead of assuming `/`→`-`; the
  session-id mechanism was probed (`CLAUDE_CODE_SESSION_ID`) before the shim was
  written. Every one held. The guessed constants — PID `0x0017`, endpoint `0x01`,
  "it speaks ESC/POS" — were every one wrong (incident note's constants table).

### Kept (reinforce these)

- **Architecture seams earned their keep.** "Single device adapter, single layout
  module, templates compose into a builder" absorbed both a protocol rewrite and
  an LLM-path deletion without a single template changing shape. The discipline of
  keeping templates as pure layout is why.
- **Verify-against-truth gates.** The `jq` cross-check, the encoder-by-listing,
  the session-id probe — gates written to confront reality rather than restate the
  plan. They caught real drift and cost little.
- **ADR discipline survived the pivots.** Neither pivot was a silent overwrite:
  ADR 0006 was fully rewritten with its alternatives, ADR 0004's "32 chars" was
  re-cast as a rendering choice, and the incident got a full write-up. The *why*
  stayed honest even when the *what* changed underneath it.

### Improve (concrete)

- **A phase whose gate is physical cannot "land" on a code-only green.** Make the
  deferral explicit and *blocking*: forge-ship should refuse to mark such a phase
  fully green, and the phases that build on its unproven assumption shouldn't
  proceed as if it's settled. Had phase 1's paper-out gate blocked phase 2, the
  raster truth would have surfaced before four phases were built on ESC/POS.
- **Add a one-line "is this on the only real path?" check before hardening any
  component.** Cheap, and it would have caught `llm.py` before the fault matrix.
- **`learnings.md` went unused across all five review passes.** Either reviews
  didn't file, or the capture step was skipped — either way the running lesson log
  stayed empty while the build-log carried the real learnings. Wire forge-review to
  actually promote at least pivot-class lessons here.

### Open threads

- Phase 5 gate 5 (TTFB / open-USB / LLM-response timings to stderr) was demoted to
  a TODO — still pending.
- Serial-counter read-modify-write race: deferred accept (Codex called it HIGH);
  revisit only if a second user or background printer appears.
- Print log + replay: deliberate scope cut, still parked in [[improvements]].
