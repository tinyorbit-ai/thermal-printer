# What I'd do with more time

Part of [[index]]. Running, honest list. Deliberate scope cuts go here too —
"deferred X for Y" is a positive signal, not an apology.

## 2026-05-26 — Deferred: lossless print log + replay

- **What:** Persist raw `.escpos` bytes + metadata for every print to `~/.thermal-printer/prints/`. Add `print --replay <serial>` and `print --preview` (render to image, don't physically print).
- **Why deferred:** Surfaced in the ambition check for the brief. Useful but pure engineering ambition — doesn't strengthen the "tactile, satisfying" feel that's driving the project. Personal tool earns the right to stay tight.
- **What it'd take to revisit:** First time I want to reprint a session receipt that's gone (cat ate it, lost, want to share). Or first time I'm debugging a layout regression and want a preview without burning paper.

## 2026-05-29 — Action items from the phases 1–5 retro

From [[retro]]. Concrete, not aspirational.

- **TTFB instrumentation (phase 5 gate 5, still pending).** Log
  `time_to_open_usb`, `time_to_llm_response` (now: `time_to_summary_arg`), and
  `time_to_first_byte` to stderr. Demoted from the gate as "informational";
  revisit if latency ever stops feeling sub-second.
- **Serial-counter `fcntl.flock` (deferred accept).** The `state.json`
  read-modify-write is unlocked; Codex called it HIGH, kept LOW for single-host
  single-user. Add the lock the first time a second writer (a second user, or a
  background printer process) becomes real.
- **Process: block downstream phases on an unproven physical gate.** Captured as a
  learning ([[learnings]]); the build-tooling change is to have forge-ship refuse a
  fully-green mark on a phase whose gate is physical/external until it's observed.
