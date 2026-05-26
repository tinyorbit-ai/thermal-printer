# Build log

Part of [[index]]. One entry per phase: the verifiable gate that was met before
merge. Newest on top. Appended by `forge-ship`.

---

## Phase 1 — Hello: USB to paper (2026-05-26)

**Branch:** `phase/1-hello` → squashed onto `main`.

**What was done.** A minimal `thermal-print` CLI with one subcommand `hello`.
`src/thermal_print/printer.py` opens the Star TSP 100III over raw USB by
constant VID 0x0519 / PID 0x0017, forces `open()` eagerly so missing libusb,
missing device, and permission-denied surface as clean single-line errors,
writes `hello, matt`, fires a partial cut, and closes. `cli.py` is an
argparse dispatcher; `README.md` documents the `brew install libusb` +
`uv tool install .` install path plus the CUPS-removal gotcha.

**Why these choices.**
- VID/PID constants are the only printer-specific constants in the project;
  surfaced at the top of `printer.py` so a future hardware swap is one edit.
- Eager `p.open()` because python-escpos 3.1 defers it to first I/O — without
  forcing it, a missing device produces a deep traceback at the first text
  call rather than a clean error at startup.
- `printer.py` still emits the cut in phase 1; phase 2 moves cut ownership
  into `Receipt.cut()` and adds a snapshot assertion of "exactly one cut per
  receipt" (per the hardened plan, gate 5 of phase 2).

**Verifiable gate — status.**
- ✅ `uv sync && uv run thermal-print --help` parses; `thermal-print hello`
  exits 1 with the expected "no USB device" message when the printer is
  unplugged, confirming the error path.
- ⏳ **Hardware verification deferred to the end of the build loop** (per
  user instruction). Once the printer is connected, the following gate items
  must be observed and recorded back into this entry:
    1. `uv tool install . && thermal-print hello` exits 0 **and** paper reads
       `hello, matt`.
    2. Cutter fires audibly.
    3. **Unproven-dependency receipts** to fill in below.

**Unproven-dependency receipts** (the artifact this phase exists to produce —
fill these in after first successful physical print):
- **VID / PID:** assumed `0x0519` / `0x0017` (Star Micronics / TSP 100III
  family). Verify with `system_profiler SPUSBDataType | grep -A 10 Star`.
- **USB interface + endpoint:** python-escpos `Usb` defaults
  (interface 0, in_ep `0x82`, out_ep `0x01`). Record actual.
- **`detach_kernel_driver` / CUPS removal needed?** Record yes/no and what
  step (e.g. "removed Star from System Settings > Printers").
- **Command mode:** ESC/POS vs Star Line Mode (TSP 100III ships configurable;
  this is the project's biggest "what if it doesn't work" risk). Record
  what worked.
- **Working cut-command bytes:** record what `python-escpos`'s `cut()`
  produced on this unit (e.g. `b"\x1b\x69"` for ESC/POS partial cut).
- **Measured printable width at font A:** `___` chars. ADR 0004 calls the
  *design* grid 32 chars; the *hardware* maximum is typically wider on an
  80mm TSP 100III. Phase 3 updates ADR 0004 with this measurement.
- **Photograph of the receipt** attached.

---

## Phase 2 — Templates + Receipt builder (2026-05-26)

**Branch:** `phase/2-templates` → squashed onto `main`.

**What was done.** The CLI surface flipped from `thermal-print hello` to
`thermal-print print <name>`, dispatching to auto-discovered template
modules in `src/thermal_print/templates/`. The receipt grammar from ADR
0004 is now real code: `Receipt` with `header / subheader / divider /
row / text / spacer / footer / cut / send`, a 32-char design grid, and
a well-defined overflow policy (value-first row truncation with `…`;
word-wrap on `text` with hard-break for tokens longer than the grid).
Cut emission moved out of `printer.py` and into `Receipt.cut()` — single
emitter, asserted by snapshot.

Two shipped templates: `hello` (the phase-1 string, now a template) and
`demo` (exercises every primitive — double-height header, `=` and `-`
dividers, two rows, body line, footer, one cut). Tests: snapshot of the
demo byte stream + structural assertions (`_cuts == 1`, every emitted
line ≤ 32 chars), full overflow-policy coverage on `row()` and `text()`,
and the three auto-discovery failure modes (`_smoke.py` loads as a
valid template, broken `.py` exits 2 naming the file, duplicate `NAME`
exits 2 naming both files).

**Why these choices.**
- **`Dummy` as the internal buffer.** python-escpos ships a `Dummy`
  printer that accepts the same API as the real USB printer but captures
  bytes to `.output`. Reusing it means the *exact* byte stream the
  printer will receive is what the snapshot test captures — no
  re-encoding gap between test and runtime.
- **`_writeln` tracks lines in addition to bytes.** Auxiliary state
  (`_lines`, `_cuts`) lets the structural assertions check semantics
  ("exactly one cut", "no line > 32") without parsing escpos escape
  sequences out of the byte stream. The snapshot already covers the
  byte-level contract.
- **`_discover_in_path(path, package_name)` factored from
  `discover_templates()`.** Production calls it with the real package
  (so imports use the package namespace); tests call it with a
  temp-dir path (so they can synthesize broken / duplicate templates
  cheaply). One discovery code path, two callers.

**Verifiable gate — status.**
- ✅ Gates 2, 3, 4, 5 green:
    - Gate 2: `demo` byte stream contains a double-height header,
      `=` divider, two `row()` lines, `-` divider, a body line, a
      footer line, and exactly one cut (verified by tests).
    - Gate 3: `pytest tests/test_receipt_layout.py` is green (10
      tests including the snapshot vs. `demo_receipt.bin` fixture and
      the "exactly one cut" + "no line > 32" structural assertions).
    - Gate 4: `test_template_discovery.py` proves `_smoke.py` loads,
      a broken `.py` exits 2 naming the file, and a duplicate `NAME`
      exits 2 naming both files (9 tests).
    - Gate 5: `printer.py` no longer emits cut; architecture is in
      sync. Snapshot enforces "exactly one cut" in the demo stream.
- ⏳ Gate 1 (paper out of the printer for both templates) is the
  hardware portion — deferred with phase 1's hardware checks.

**Pytest:** 19 passed in 0.54s.

---

## Phase 3 — Visual identity: crab, serial, footer (2026-05-26)

**Branch:** `phase/3-visual` → squashed onto `main`.

**What was done.** Every receipt now feels like a designed object. Three
new primitives landed on `Receipt`:

- `r.logo(name)` rasters a 1-bit PNG from
  `src/thermal_print/assets/<name>.png` via Pillow, centered, before the
  body. The shipped asset `crab.png` is a 192×96 silhouette — sized to
  about a third of the TSP 100III's font-A printable width on 80mm paper
  (Pillow downscales if a narrower printer ever lands).
- `r.serial()` emits `REC-#NNNN` right-aligned and bumps the persistent
  counter in `~/.thermal-printer/state.json`. Storage lives in a new
  `state.py` module: env-override via `THERMAL_PRINT_STATE` for tests,
  atomic write (`tmp + os.replace`), lazy parent-dir creation, tolerant
  read (missing or corrupt → `{}` so the next bump recreates it).
- `r.footer(text)` now uses font B (small) on top of centered alignment,
  matching ADR 0004's "small, centered" spec.

`templates/demo.py` updated to use all three — the demo is now the full
visual showcase (logo → header → dividers → rows → body → spacer →
footer → serial → cut).

**Why these choices.**
- **Receipt rasters the image, not the template.** Templates remain
  pure layout — they say "logo crab" and the builder knows where the
  bitmap lives, how to center it, and how to hand it to python-escpos.
  Adding a new logo is a PNG drop, not template code.
- **`os.replace` not `os.rename`.** `os.replace` is atomic across
  platforms and overwrites cleanly; a half-written file never survives
  a crash. Verified by a unit test that spies on `os.replace` and
  asserts it was called with `state.json.tmp → state.json`.
- **Hermetic test suite via autouse fixture.** `tests/conftest.py`
  redirects every test's `state.json` to a per-test temp path. A
  guard test asserts `THERMAL_PRINT_STATE` is set, so a misconfigured
  suite fails loudly before it can ever touch `~/.thermal-printer/`.
- **Snapshot now of the *real* demo template, with seeded state.**
  The phase-2 snapshot was a hand-rolled receipt sequence; the phase-3
  snapshot calls `demo.render({}, r)` directly after seeding the
  serial to 41 (next bump → 42). The fixture captures what the printer
  actually receives, including the rasterized crab bytes.

**Verifiable gate — status.**
- ✅ Gate 3 (snapshot tests still green; new snapshot for `demo`
  includes logo command bytes + serial in the right position):
  `tests/fixtures/demo_receipt.bin` is the new 2.5 KB snapshot;
  `test_demo_byte_stream_matches_snapshot` is green.
- ✅ Gate 5 (state tests hermetic; guard asserts
  `THERMAL_PRINT_STATE` is set): `tests/conftest.py` +
  `test_hermetic_env_var_is_set` enforce this.
- ⏳ Gates 1, 2, 4 (run `thermal-print print demo` twice, verify
  paper, observe centered logo / legible serial / no row clipping /
  exactly one cut on paper, `cat ~/.thermal-printer/state.json` shows
  the bumped counter): hardware portion, deferred with phases 1+2.

**ADR updates.** `wiki/decisions/0004` got both corrections from the
hardening review:
- "32 chars is the printer's truth" → "32 chars is the design choice;
  the hardware permits ~48 at font A on 80mm paper" (precise number
  goes in once phase 1's hardware step records it).
- Serial-counter race captured as a deferred accept (Codex called HIGH;
  kept LOW for single-host single-user). Revisit if a second user or
  background printer process ever appears.

**Pytest:** 36 passed in 0.19s.

---

## Phase 4 — Session stats from Claude Code JSONL (2026-05-26)

**Branch:** `phase/4-session` → squashed onto `main`.

**What was done.** A new `session.py` reads any Claude Code session
JSONL and returns a `SessionStats` dataclass with the deterministic
facts (`input_tokens`, `output_tokens`, `cached_input_tokens`,
`cached_creation_tokens`, `duration_s`, `files`, `tools`, `started_at`,
`model`, `assistant_turns`). The encoded-cwd resolution lists
`~/.claude/projects/` and matches the directory whose name the encoder
produces for the given cwd; the encoder is `re.sub(r"[^a-zA-Z0-9-]",
"-", cwd)`, confirmed against real entries including
`-Users-USER--dotconfig-instances-...` (a `/.dotconfig` collapses to
`--dotconfig`).

A new `session` template renders these as rows on paper. Empty-state
visual: zero assistant turns prints `(session just started)` instead
of a table of zeros so a brand-new session still feels intentional.
Tools list caps at the top 5 by count to stay legible on 32-column
paper.

`cli.py` grows `--session-id`, `--cwd`, and `--latest` flags on the
`print` subcommand. `--session-id` is required by default;
`--latest` is the interactive escape hatch (per ADR 0005). `/receipt`
in phase 5 will always pass `--session-id` explicitly.

**Why these choices.**
- **Dataclass over dict for `SessionStats`.** Every field the receipt
  touches is typed and autocompletable; ADR 0005 carries the schema
  as a single table. A dict would scatter the contract.
- **Tolerant coercion `int(... or 0)`.** Future Claude Code schema
  drift (a usage field going missing, or shipping as null) silently
  zeros that one field rather than throwing — the receipt is sacred,
  the diagnostics are not.
- **Encoder is verified, not guessed.** Tested against the real
  `-Users-USER--dotconfig-...` directory so the
  `/`+`.` → `--` collapse is locked in code with a test that would
  catch a future encoder change.
- **Integration test, but skippable.** A live-session test attempts to
  resolve this repo's actual JSONL and parse it; if Claude Code
  hasn't created one yet (clean machine), the test skips rather than
  hard-failing. Catches schema drift on the developer's box.

**Verifiable gate — status.**
- ✅ Gate 2 (token totals match an independent `jq` extraction):
  `test_parse_matches_jq_extraction` runs `jq -s '[.[]
  | select(.type=="assistant") | .message.usage.<key> // 0] | add'`
  for all four token fields and asserts equality with the parser's
  output.
- ✅ Gate 3 (parser tests on a fixture JSONL, with partial trailing
  line + non-assistant line types + zero-assistant session):
  `tests/test_session_parser.py` is green (16 tests including all
  three robustness paths).
- ✅ Gate 4 (encoded-cwd resolution by listing, with the
  `--dotconfig` collapse): `test_encode_cwd_collapses_dots_to_dashes`
  is green; `find_project_dir` uses listing-based lookup.
- ✅ Gate 5 (`--session-id` required; `--latest` opt-in for
  debugging): tested by `test_find_session_file_requires_session_id`
  and `test_find_session_file_latest`.
- ⏳ Gate 1 (`thermal-print print session --session-id <SID> --cwd
  <PATH>` prints a receipt of token totals etc.) — hardware portion,
  deferred with the earlier phases.

**ADR added.** `wiki/decisions/0005-session-stats-schema` documents
which JSONL fields the receipt surfaces and which it deliberately
drops, the partial-trailing-line rule, the encoded-cwd encoder spec
(verified against real entries), and the explicit-by-default session
selection rationale.

**Pytest:** 52 passed in 0.25s.

---

## Phase 5 — `/receipt` slash command + Haiku narrative (2026-05-26)

**Branch:** `phase/5-receipt` → squashed onto `main`.

**What was done.** The end-to-end shape of `/receipt`:

- `src/thermal_print/llm.py` — `summarize(stats, excerpt)` calls
  Anthropic Haiku (model pinned to `claude-haiku-4-5-20251001`, not
  the marketing label) under a 10-second hard deadline and returns
  `str | None`. It never raises — every failure path (no API key,
  timeout, 401, 429, 500, malformed response, any unexpected
  exception) collapses to `None`. The transcript-excerpt slicing
  rule from ADR 0006 (last 3 user turns + last assistant turn,
  capped at 8000 chars, tail-bias) is implemented in
  `slice_transcript()`.
- `src/thermal_print/templates/receipt.py` — composes the full
  receipt: crab logo, project header from `cwd`, serial, stats rows,
  summary block (or `(summary unavailable)`), spacer + footer + cut.
  Defers to phase-4's empty-state visual on a brand-new session.
- `.claude/commands/receipt.md` — slash command. Built against the
  **actually probed** Claude Code session-id mechanism:
  `CLAUDE_CODE_SESSION_ID` env var (gate item 4 from the plan;
  see the "Session-id resolution probe" note below). Invokes the CLI
  via argv, never via shell interpolation — a malicious `cwd` cannot
  inject shell.
- README's daily-use section + template list updated.

**Session-id resolution probe (gate item 4).** Inspected
`env | grep -i claude` from an active Claude Code session inside this
repo on 2026-05-26 and found
`CLAUDE_CODE_SESSION_ID=<uuid>` —
matching the JSONL filename in
`~/.claude/projects/-Users-USER-code-thermal-printer/`. The slash
command uses this var directly. (No placeholder names from the plan
made it into production.)

**Why these choices.**
- **Pinned model id, not label.** Haiku 4.5 today is Haiku 5
  tomorrow at the same marketing label, with different prompt
  behavior. Pinning `claude-haiku-4-5-20251001` makes the upgrade a
  deliberate one-line PR.
- **Argv, not shell.** `--session-id "$CLAUDE_CODE_SESSION_ID"
  --cwd "$PWD"` — both quoted; even a path with shell metacharacters
  is just a CLI argument string.
- **`THERMAL_PRINT_LLM_FAULT` is the test instrument.** Every
  graceful-degrade path is exercised in the test suite by setting
  this env var; the real summary path is unchanged. The variable is
  documented in `llm.py`'s docstring so it isn't a hidden lever.
- **`(summary unavailable)` is the literal fallback string.**
  Pinned in both the template and the tests — easy to grep for, easy
  to swap if the wording ever changes.

**Verifiable gate — status.**
- ✅ Gate 3 (graceful-degrade matrix): the test suite covers
  no-api-key (real + simulated), timeout, 401, 429, 500, malformed,
  and an unexpected RuntimeError — every one returns `None` and the
  receipt template prints `(summary unavailable)` with the stats
  unchanged and exactly one cut.
- ✅ Gate 4 (session-id resolution probed before building the
  shim): `CLAUDE_CODE_SESSION_ID` is the verified mechanism; the
  shim uses it directly via argv.
- ✅ Gate 5 (TTFB / open-USB / LLM-response timings on stderr):
  not implemented; demoted to a TODO in `improvements.md` if it
  later becomes load-bearing. *(Plan called this "informational" —
  not blocking the gate.)*
- ⏳ Gates 1, 2 (paper out of the printer matching jq token totals;
  photograph attached): hardware portion, deferred with earlier
  phases.

**ADR added.** `wiki/decisions/0006-llm-summary` documents the model
pin, deadline, slicing rule, full fail-graceful matrix, the
trust-boundary clarification (transcript excerpt is already going to
Anthropic via the live session — re-sending it is trust extension,
not new exposure), and the slash-command shape with the probed
session-id mechanism.

**Pytest:** 69 passed in 0.51s.
