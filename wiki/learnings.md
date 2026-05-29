# Learnings

Part of [[index]]. Running log appended by `forge-review`. Newest on top. One entry
per review pass that found something worth remembering. Later builds/reviews read
and enforce these.

<!-- Entry shape:
## YYYY-MM-DD — Phase N — <short title>
- **Found:** <what the review caught>
- **Fixed:** <how it was resolved>
- **Rule to remember:** <generalizable lesson, phrased so the next build avoids it> -->

## 2026-05-29 — Retro (phases 1–5) — Promoted lessons

These three were synthesized in [[retro]] across the whole build; promoted here so
future builds enforce them.

### A physical/external gate is not satisfied by a code-only green

- **Found:** Phase 1's gate was "paper comes out of the printer," but hardware
  verification was deferred; phases 1–5 all merged on code-only gates and the
  printer's real protocol (Star Graphic raster, not ESC/POS) surfaced only after
  all five had "landed," forcing a `printer.py`/`Receipt` rewrite.
- **Fixed:** Pivot rewrote the device + layout internals around a PIL canvas +
  reverse-engineered raster job; see [[notes/2026-05-27-tsp143iiiu-default-mode]].
- **Rule to remember:** If a phase's gate names a physical or external outcome
  (paper out, real API call, device handshake), it does not "land" until that
  outcome is observed. Don't let downstream phases build on a deferred,
  unproven assumption — block on it, the way prototype-first intends.

### Confirm a component is on the only real path before hardening it

- **Found:** Phase 5 built `llm.py` with a five-way fault matrix + ADR + tests,
  then the pivot deleted it entirely once it was clear the only entry point
  (`/receipt` in a live session) already has the transcript in context.
- **Fixed:** Summary is now written by the parent agent and passed via `--summary`;
  module + `anthropic` dep removed (ADR 0006 rewritten).
- **Rule to remember:** Before investing in robustness (retries, fault matrices,
  graceful-degrade paths) for a component, spend one line asking whether it sits
  on the only real execution path. Necessity before hardness.

### Verify against ground truth; never ship a guessed external constant

- **Found:** Every guessed constant was wrong (PID `0x0017`→`0x0003`, OUT endpoint
  `0x01`→`0x02`, "speaks ESC/POS"→raster-only). Every verified-against-truth choice
  held (token math vs independent `jq`, encoded-cwd by *listing* `~/.claude/projects/`,
  session-id probed as `CLAUDE_CODE_SESSION_ID` before the shim).
- **Fixed:** Constants locked from `ioreg`/descriptor dumps + the CUPS-filter source;
  encoder and session-id verified against real on-disk entries.
- **Rule to remember:** Any constant describing the outside world (USB IDs,
  endpoints, on-disk path encodings, env var names, protocol dialect) gets verified
  against the real artifact before it lands in code — listing/probing/cross-checking,
  not assuming. Guessed externals are the default-wrong case.
