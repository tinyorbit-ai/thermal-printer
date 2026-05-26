# Plan — thermal-printer

Part of [[index]]. Status: **locked (hardened 2026-05-26).** See the `## Review`
section at the bottom for what changed and why.

**Base branch:** `main`
**Discipline:** each phase runs on `phase/<n>-<slug>`; squash-merges back as ONE
commit after its verifiable gate is green; one [[build-log]] entry per phase.
Never commit directly on `main`.

## Build order at a glance

1. **Hello** — USB → paper. De-risk the riskiest layer first.
2. **Templates + Receipt builder** — the system grammar.
3. **Visual identity** — crab logo, serial counter, footer divider.
4. **Session stats** — read Claude Code's JSONL, render the deterministic facts.
5. **/receipt + Haiku narrative** — slash command + LLM summary; end-to-end.

Each phase is a vertical slice that leaves the project in a working, demoable
state. Phase 1 is the **thinnest end-to-end thing that runs** — paper coming out
of the printer, not "set up the project."

---

## Phase 1 — Hello: USB to paper
**Branch:** `phase/1-hello`
**Goal:** `thermal-print hello` opens the Star TSP 100III over raw USB, prints
the string `hello, matt`, and fires the cutter. The riskiest layer (libusb +
macOS USB permissions + vendor/product IDs) is de-risked before anything else.
**Verifiable gate:** From a clean checkout: `uv tool install . && thermal-print
hello` exits 0 **and** paper comes out of the printer reading `hello, matt`
**and** the cutter fires audibly. Manual observation — the central artifact of
this phase is physical paper. Photograph it for the build-log. In addition, the
build-log entry must record the **unproven-dependency receipts** so future-Matt
never has to rediscover them:

1. USB **vendor/product IDs** (output of `system_profiler SPUSBDataType` for the
   printer).
2. The USB **interface + endpoint** the code opens, and whether macOS required
   `detach_kernel_driver` / a CUPS-removal step.
3. The **command mode** the unit was in — ESC/POS or Star Line Mode (TSP 100III
   ships configurable; this is the project's single biggest "what if it doesn't
   work" risk).
4. The exact **cut-command byte sequence** that fired the cutter on this unit
   (e.g. `b"\x1b\x69"` for ESC/POS partial cut; record what actually worked).
5. The printer's **physical printable width** at font A — measured, not assumed.
   ADR 0004 calls the grid 32 chars; on an 80mm TSP 100III at font A it is
   closer to 48. Confirming the column ceiling here protects the layout
   constants in phase 2 (we keep the 32-char *design* grid even if hardware
   permits wider — the call is legibility, not density — but the *truth* of the
   max needs to be recorded).
**Work:**
- `pyproject.toml` with `uv` config, `requires-python = ">=3.11"`, deps:
  `python-escpos` **(pin exact version)**, `pyusb`, `Pillow`. Entry point
  `thermal-print = "thermal_print.cli:main"`.
- `src/thermal_print/cli.py` — minimal: one subcommand `hello`, no template
  system yet.
- `src/thermal_print/printer.py` — open TSP 100III by vendor/product ID
  constants, write `b"hello, matt\n"`, partial cut, close. Surface USB
  permission errors clearly; also handle the no-libusb-installed case with a
  pointer to `brew install libusb`.
- Verify USB IDs by running `system_profiler SPUSBDataType | grep -A 10 Star`
  before writing constants.
- README section: install path (`uv tool install .`) + Homebrew prerequisite
  (`brew install libusb`). Document any macOS permission step that came up.
- Update ADR 0004 if the measured column ceiling differs materially from the
  "80mm = 32 chars" claim (which it likely does — the claim is the design
  choice, not the hardware limit; the ADR should say so).
**Decisions:** [[decisions/0001-shape]], [[decisions/0002-cli-and-packaging]].

---

## Phase 2 — Templates + Receipt builder
**Branch:** `phase/2-templates`
**Goal:** The CLI becomes `thermal-print print <name>` and dispatches to
auto-discovered template modules. A `Receipt` builder enforces the 32-char
grid, headers, dividers, rows. Two templates (`hello`, `demo`) prove the
abstraction — `hello` is the phase-1 string moved into a template; `demo`
demonstrates the full visual grammar.
**Verifiable gate:**
1. `thermal-print print hello` and `thermal-print print demo` both succeed and
   print paper.
2. `demo` output includes: a double-height header, an `=` divider, two `row()`
   lines, an `-` divider, a body line, a footer line, and **exactly one** cut.
3. Snapshot test `pytest tests/test_receipt_layout.py` is green — the byte
   stream emitted by a known `Receipt` call sequence matches the checked-in
   fixture. The snapshot is paired with structural assertions: the byte stream
   contains **exactly one** cut command and no row exceeds the 32-column grid.
4. Auto-discovery test: (a) dropping `templates/_smoke.py` exposing
   `NAME = "_smoke"` + `render` makes `thermal-print print _smoke` work
   without code changes elsewhere; (b) a template with a syntax error makes
   the CLI exit non-zero with the offending filename in the message; (c) two
   templates sharing the same `NAME` raises at startup naming both files.
5. Cut-emission ownership: `printer.py` no longer issues a cut on close — the
   cut is exclusively a `Receipt.cut()` call in the template. The architecture
   diagram is updated to match.
**Work:**
- `templates/` directory with auto-discovery loader in `cli.py`. Loader
  rejects duplicate `NAME`s loudly.
- `receipt.py` with the API from [[decisions/0004-receipt-layout-grammar]] —
  `header / subheader / divider / row / text / spacer / footer / cut / send`.
  (No `.logo()` / `.serial()` yet — those land in phase 3.) Define the
  **overflow policy** explicitly: `row(label, value)` reserves space for the
  value and truncates the label from the right with `…`; `text(...)` word-wraps
  at 32 chars and hard-breaks tokens longer than that. Test both.
- `templates/hello.py` and `templates/demo.py`.
- `tests/` with `test_receipt_layout.py` (snapshot + structural assertions on
  width / cut-count / wrap behavior) and `test_template_discovery.py` (registry
  assertions, syntax-error path, duplicate-NAME path).
- `Receipt.send(printer)` flushes bytes once at the end — single USB write per
  print where possible. Cut is one of those bytes; `printer.py` does not
  re-emit cut on close.
**Decisions:** [[decisions/0003-template-plugin-mechanism]],
[[decisions/0004-receipt-layout-grammar]].

---

## Phase 3 — Visual identity: crab logo, serial, footer
**Branch:** `phase/3-visual`
**Goal:** Every receipt now feels like a designed object. The Claude Code crab
logo opens each receipt as a centered raster bitmap. A monotonically-increasing
serial `REC-#NNNN` persists across runs in `~/.thermal-printer/state.json`. A
styled footer divider + small footer text closes the receipt.
**Verifiable gate:**
1. Run `thermal-print print demo` **twice** in succession. Both receipts have
   the crab logo at the top, centered. Serial on receipt 1 is `REC-#NNNN`, on
   receipt 2 is `REC-#NNNN+1`.
2. `cat ~/.thermal-printer/state.json` shows the bumped counter.
3. Snapshot tests still green; new snapshot for `demo` includes logo command
   bytes + serial in the right position.
4. Objective visual checks (replaces the old "pin it on the wall" gate, which
   was subjective enough to pass through any regression): on the photographed
   receipt, **(a)** the logo is centered (no left/right bias visible),
   **(b)** the `REC-#NNNN` serial is fully legible and not clipped, **(c)**
   every `row()` line shows label + value on a single line with no wrap or
   truncation visible, and **(d)** there is exactly one cut at the bottom.
   Photo attached to the build-log entry.
5. State tests are hermetic — every test sets `THERMAL_PRINT_STATE` to a temp
   path; the suite must not be able to touch the real `~/.thermal-printer/`.
   CI-style guard: a test asserts that `THERMAL_PRINT_STATE` is set during the
   test run.
**Work:**
- `assets/crab.png` — source bitmap, sized to the printer's measured printable
  width at font A (recorded in Phase 1's build-log; for an 80mm head this is
  ~576 px, not 384). Pillow downscales if necessary.
- Receipt builder gains `.logo(name)` (raster via Pillow + `python-escpos`),
  `.serial()` (reads + bumps state.json), `.footer(text)` (small, centered).
- `state.py` — read/write `~/.thermal-printer/state.json`, env override via
  `THERMAL_PRINT_STATE`, atomic write (`tmp + rename`). **Concurrency note:**
  the read-modify-write is not locked; for this single-host single-user tool
  the race is accepted. Capture the accept-and-defer in ADR 0004's
  Consequences section so future-Matt sees it before it bites.
- Update `templates/demo.py` to use the new primitives so the demo is the
  showcase.
- Tests for `state.py` (env override required, increment, atomic write, lazy
  directory creation).
**Decisions:** updates ADR 0004 — (a) correct the "32 chars is the printer's
truth" wording to "32 chars is the design choice; the TSP 100III at font A
permits more" with the measured number from Phase 1; (b) add the serial-counter
race acceptance to Consequences.

---

## Phase 4 — Session stats from Claude Code JSONL
**Branch:** `phase/4-session`
**Goal:** Read the active Claude Code session's JSONL file and extract the
deterministic facts: input tokens, output tokens, cached tokens, wall-clock
time, files touched, tools called. A new `session` template renders these on
paper. Pure data layer — no LLM call yet.
**Verifiable gate:**
1. `thermal-print print session --session-id <SID> --cwd <PATH>` prints a
   receipt containing token totals, time, file count, tool-call count.
2. The token totals on the receipt match an independent `jq` extraction from
   the same JSONL file. The `usage` object lives on **`.message.usage`** on
   `type == "assistant"` lines only (verified by inspection on
   2026-05-26), so the verifier reads:
   ```
   jq -s '[.[]
            | select(.type=="assistant")
            | .message.usage.input_tokens // 0
          ] | add' <jsonl>
   ```
   …and the same shape for `output_tokens`, `cache_read_input_tokens`,
   `cache_creation_input_tokens`. The receipt must match each independently
   (not just a total).
3. `pytest tests/test_session_parser.py` is green — parser unit tests use a
   checked-in fixture JSONL (truncated real session, scrubbed). Tests must
   cover: **partial trailing line** (the JSONL is being appended to while the
   session is live; `parse` must skip a malformed last line without crashing),
   non-assistant lines (`file-history-snapshot`, `system`, `user`,
   `attachment`, `last-prompt` — all observed in real JSONL), and a JSONL
   with zero assistant messages (just started a session — receipt should
   render, not crash).
4. Encoded-cwd resolution: passing `--cwd /Users/USER/code/thermal-printer`
   correctly resolves to `~/.claude/projects/-Users-USER-code-thermal-printer/`.
   **Verify against the existing `~/.claude/projects/` directory** — the
   encoder is not pure `/`→`-` (observed `-Users-USER--dotconfig-instances-…`
   suggests dots/other separators also map to `-`). The implementation must
   discover the encoded folder by listing, not by guessing — given `cwd`,
   look for the folder whose name decodes to the given `cwd`, or whose name
   the same encoder produces. Test against a fixture set of real encoded
   directory names captured in this phase.
5. Session-file selection is **explicit by default**: `--session-id` is
   required. "Most recent" is a `--latest` flag for interactive debugging
   only. The `/receipt` slash command always passes `--session-id`, never
   relies on recency.
**Work:**
- `src/thermal_print/session.py` — pure function `parse(jsonl_path: Path) ->
  SessionStats` (dataclass: `input_tokens`, `output_tokens`,
  `cached_input_tokens` *(read)*, `cached_creation_tokens`, `duration_s`,
  `files: list[str]`, `tools: dict[str, int]`, `started_at`, `model`).
- Encoded-cwd helper: looks up the actual encoded directory by listing
  `~/.claude/projects/` rather than blindly applying `/`→`-`. If multiple
  candidate folders match, raise with a clear message.
- Session-file discovery: `--session-id` is the only way `/receipt` opens a
  file. `--latest` exists for interactive use.
- `templates/session.py` — render the stats as `row()` calls. Define an
  **empty-state visual**: if `input_tokens == 0` and `tools == {}`, render
  "(session just started)" instead of a table of zeros, so the receipt still
  feels intentional.
- `tests/fixtures/session-sample.jsonl` — scrubbed fixture. Replace
  `/Users/USER/` with a non-PII placeholder (`/Users/USER/`); same for any
  custom paths in tool arguments. Add a second fixture with a deliberately
  malformed trailing line for the partial-line test.
- **New ADR (in this phase):** `0005-session-stats-schema.md` — what fields we
  pull and *why those*, the JSONL key paths (including that `.usage` is at
  `.message.usage` on `assistant` lines), what we deliberately drop, and the
  partial-trailing-line handling rule.
**Decisions:** introduces ADR `0005-session-stats-schema`.

---

## Phase 5 — `/receipt` slash command + Haiku narrative
**Branch:** `phase/5-receipt`
**Goal:** Invoking `/receipt` from any Claude Code session produces a real
receipt: crab logo, project name, serial, deterministic stats from phase 4,
plus a 3–5 line narrative summary from Anthropic Haiku. End-to-end demo of the
whole brief.
**Verifiable gate:**
1. From an active Claude Code session in this repo, invoking `/receipt` prints
   paper containing: the project name (`thermal-printer`), the **exact**
   token counts that match the `jq` extraction from the same session JSONL
   (per Phase 4 gate 2 — not just "non-zero"), and a 3–5 line summary
   clearly written by the LLM (not boilerplate).
2. Photograph the receipt; attach to the [[build-log]] entry.
3. Stats are sacred; the summary is a bonus. The receipt must still print
   correctly under **all** of the following failure modes (each tested at
   least once during the phase, via a temporary `THERMAL_PRINT_LLM_FAULT`
   env var read by `llm.py`):
   - `ANTHROPIC_API_KEY` unset.
   - Simulated request timeout (no response within the hard deadline).
   - Simulated HTTP 401 (revoked key).
   - Simulated HTTP 429 (rate-limit) and 500 (server error).
   - Simulated malformed response body.

   In every case the summary section reads `(summary unavailable)`, the
   stats portion is unchanged, and the total wall-clock from invocation to
   paper-out stays inside the deadline declared in ADR 0006.
4. **Session-id resolution probe.** Before Phase 5 implementation work
   starts, run a one-shot Bash inside an active Claude Code session that
   prints whatever env vars / Claude-Code-provided substitutions are
   actually available (e.g. `env | grep -i claude`, `echo "$CLAUDE_*"`).
   Record the verified mechanism in the build-log. The slash command builds
   on that ground truth, not on the placeholder names in this plan.
5. Time-to-first-byte is informational: log `time_to_open_usb`,
   `time_to_llm_response`, `time_to_first_byte` to stderr for inspection.
**Work:**
- `.claude/commands/receipt.md` — slash command shim. Built against the
  *actually observed* Claude Code substitution mechanism (gate item 4),
  not the guessed env-var names. Passes session id and cwd to the CLI via
  **argv** (`thermal-print print receipt --session-id … --cwd …`), never via
  shell-interpolated string, so a malicious cwd cannot inject commands.
- `src/thermal_print/llm.py` — `summarize(stats: SessionStats, transcript_excerpt:
  str) -> str | None`. Anthropic SDK, **exact model ID pinned in ADR 0006**
  (e.g. `claude-haiku-4-5-20251001`, not the marketing label "Haiku 4.5").
  Define and document the hard request deadline. Handle and test the failure
  modes listed in gate 3. Catch exceptions broadly and return `None` — the
  receipt is the contract, not the SDK.
- `src/thermal_print/llm.py` — define the **transcript-excerpt slicing rule**
  in ADR 0006 (e.g. "last N user turns + last assistant turn, capped at K
  chars"). The full transcript will exceed Haiku's context for long sessions.
- `templates/receipt.py` — composes logo + project header + serial + stats
  rows + summary block + footer. Handles the `None` summary case. If the
  session is brand-new (zero assistant turns, no tools yet), defer to the
  Phase 4 empty-state visual.
- README "Daily use" section with a screenshot of the receipt and the slash
  command invocation.
- **New ADR (in this phase):** `0006-llm-summary.md` — model choice with the
  exact API ID, prompt shape, transcript-excerpt slicing rule, request
  deadline, the **fail-graceful** rule (stats are sacred; the summary is a
  bonus), and the trust-boundary note: the transcript excerpt is already
  going to Anthropic via the live Claude Code session, so re-sending it for
  the summary is a trust *extension* not a new exposure — but the ADR should
  state this explicitly so a future-Matt reading this doesn't have to
  re-reason about it.
**Decisions:** introduces ADR `0006-llm-summary`.

---

## Gate enforcement

Each phase's gate is the **only** thing that must be green before squash-merging
to `main`. Snapshot tests stay green across phases (any failure must be a
deliberate fixture update committed alongside). `forge-ship` reads the gate
from this file, verifies it, and writes the build-log entry.

## Hardening

Before the build loop unlocks, run `forge-harden` against this plan — it will
pressure-test the gates, the build order, and the open ADRs (0005, 0006) that
are deferred to their phases.

---

## Review

Hardened 2026-05-26. Angles run: **engineering**, **design/UX (receipt as the
UI surface)**, **DX (CLI ergonomics for single-user Matt)**, **security**, and
an **independent adversarial pass via Codex** (`codex exec`, auto-probed per
forge's reviewer-agents reference — no `wiki/.forge/config.yaml`, no
`FORGE_REVIEWER`).

### Strongest finding (everyone agreed)

**The TSP 100III's command dialect is the single unproven dependency the whole
project rests on.** The printer ships configurable between ESC/POS and Star
Line Mode; `python-escpos` will not drive it correctly in the wrong mode, and
nothing else in the plan matters if Phase 1 doesn't get paper out. The fix:
Phase 1's gate now requires the build-log entry to record the VID/PID,
interface/endpoint, command mode, working cut-bytes, and measured printable
width. Phase 1's purpose is to retire this risk — the documentation
*is* the receipt that proved it.

### Structural fixes applied directly

- **Single cut emitter.** Architecture said both `receipt.py` and `printer.py`
  emitted cut bytes. Codex flagged this; risk is two cuts per print. Fixed
  in `architecture.md` and Phase 2 gate 5 — `printer.py` no longer cuts;
  layout owns it; snapshot test asserts exactly one cut command in the stream.
- **Phase 2 overflow + auto-discovery rigor.** `Receipt.row` and
  `Receipt.text` now have a defined overflow policy (label truncation +
  word-wrap with hard-break fallback). Template loader rejects duplicate
  `NAME`s and surfaces syntax errors with the filename. All three behaviors
  are gated by tests.
- **Phase 3 gate 4 is now objective.** The old "looks like something you'd
  want to pin on the wall" gate could pass through any cosmetic regression.
  Replaced with four explicit visual checks (centered logo, legible serial,
  no row truncation, exactly one cut) plus the photo.
- **Phase 3 state tests are hermetic.** Tests must set `THERMAL_PRINT_STATE`
  to a temp path; a guard test asserts the env var is set during the run.
  Stops accidental writes to `~/.thermal-printer/state.json`.
- **Phase 4 `jq` verifier corrected.** The old `[.usage.input_tokens] | add`
  was broken — `.usage` lives on `.message.usage` on `assistant` lines only
  (verified by reading real JSONL on 2026-05-26). The gate now spells out
  the right shape, and the parser tests cover non-assistant line types
  (`file-history-snapshot`, `system`, `attachment`, `last-prompt`).
- **Phase 4 partial-line robustness.** The JSONL file is being appended to
  while `/receipt` reads it. Parser must skip a malformed trailing line.
  Now a gate item with a dedicated fixture.
- **Phase 4 encoded-cwd discovered, not guessed.** The encoder Claude Code
  uses is not pure `/`→`-` (real directories like
  `-Users-USER--dotconfig-instances-…` prove other characters also map to
  `-`). Implementation now lists `~/.claude/projects/` to find the right
  folder rather than blindly applying a substitution.
- **Phase 4 session selection is explicit.** `--session-id` required by
  default; "most recent" is opt-in via `--latest` for interactive debugging.
  `/receipt` always passes the id.
- **Phase 5 graceful-degrade gate widened.** Old gate only tested
  `ANTHROPIC_API_KEY` unset. Now also tests timeout, 401, 429, 500, and
  malformed-response paths — each must leave stats intact and print
  `(summary unavailable)` within the declared deadline.
- **Phase 5 slash-command resolution mechanism probed first.** Phase 5 now
  starts with a gate item that records the *actual* Claude Code substitution
  mechanism — env vars, slash-command argument syntax, whatever — before the
  shim is written against guessed names. The CLI is invoked via argv, never
  shell-interpolated, so a session-id / cwd cannot inject commands.
- **Phase 5 ADR 0006 spec strengthened.** Pin the exact Anthropic model ID
  (not the marketing label "Haiku 4.5"). Define the transcript-excerpt
  slicing rule (full transcripts will overflow Haiku context for long
  sessions). Note the trust-boundary: the excerpt is already going to
  Anthropic via the live session, so this is trust *extension*, not a new
  exposure.
- **ADR 0004 to be updated in Phase 1/3.** Two corrections:
  (a) "32 chars is the printer's truth" is misleading — TSP 100III at 80mm
      font A permits ~48 chars. 32 is the **design choice**, not the
      hardware limit. Phase 1 records the measurement; Phase 3 updates the
      ADR.
  (b) Add the serial-counter race to Consequences (`state.json` RMW is not
      locked; single-host single-user makes it acceptable but it's worth
      surfacing).

### Open taste decisions (resolved with the user)

1. **Phase 1 scope expansion → expand.** Phase 1's build-log entry now
   records VID/PID, endpoint, command mode, and working cut-bytes. Trades
   ~30 minutes against losing the breadcrumb later.
2. **Serial-counter `fcntl.flock` → defer.** Personal tool, single host,
   the race window is essentially impossible to hit. Document the accept;
   add the lock only if it ever bites.

### Reviewer disagreement carried (not reconciled)

Codex called the serial-counter race **HIGH** severity; we kept it as a
deferred accept (effectively LOW for this deployment context). If the tool
ever grows a second user or a background printer, revisit.

### Angles that found nothing meaningful to change

- **Security.** Trust boundaries are healthy: no network input, the JSONL is
  Claude Code's own file, the API key flows through env only, the slash
  command will pass argv (not shell-interpolated). The transcript-excerpt
  trust-extension note is captured in ADR 0006 rather than being a fix.
- **DX (Matt-as-user).** CLI surface is fine for one person. Help text and
  error messages will land naturally during build; not worth dedicated
  gating in a personal tool.

### Independent reviewer status

Selected: **Codex** (auto-probe; no project config, no `FORGE_REVIEWER`).
First invocation hung — likely a quoting/heredoc interaction in the wrapping
shell. Retried via stdin; came back with 14 findings ranked high/med/low.
Reconciled above. The full Codex output is preserved in the conversation
transcript that produced this hardening pass.

### Verdict

The plan is locked. Phase 1 is the only thing that can prove the central
assumption (printer talks the dialect we think it does); everything
downstream is shaped to surface a regression rather than smooth over it.
Return to `forge` for the build loop.
