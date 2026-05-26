# ADR 0002 — CLI name, entry point, and packaging

**Status:** accepted (Planning) · part of [[index]]

## Context

[[decisions/0001-shape]] locked Python 3 + `python-escpos` + raw USB + a
template-driven architecture, but left open the **name** you'll type, **how it
installs**, and **how the entry point is wired**. These shape every phase: the
slash command shim calls it, the README documents it, and the dev loop depends
on it. Worth locking before any code lands.

## Decision

- **CLI command name:** `thermal-print` (not `tp`, not `receipt`).
- **Packaging:** [`uv`](https://docs.astral.sh/uv/) + `pyproject.toml`. Single
  `[project.scripts]` entry: `thermal-print = "thermal_print.cli:main"`.
- **Install path:** `uv tool install .` from the repo root puts the binary on
  `PATH` for daily use. `uv run thermal-print …` from the checkout for dev.
- **Module layout (target):**
  ```
  src/thermal_print/
    __init__.py
    cli.py            # entry point, dispatcher
    printer.py        # USB open / write / cut
    receipt.py        # Receipt builder (32-char grid)
    state.py          # ~/.thermal-printer/state.json (serial counter)
    session.py        # Claude Code JSONL parser  (phase 4)
    llm.py            # Anthropic Haiku call      (phase 5)
    templates/        # auto-discovered .py files
      hello.py
      demo.py
      session.py
      receipt.py
    assets/
      crab.png        # logo bitmap (phase 3)
  ```

## Why

- **`thermal-print` over `tp`.** The brief emphasizes tactile, designed feel. A
  self-documenting command reads better in shell history, in README snippets,
  and in the slash-command shim. `tp` collides with `top` muscle memory and
  reads as a typo. Two extra syllables is not a cost worth saving.
- **`uv` over `pipx` / `requirements.txt`.** `uv` is the modern Python packaging
  story: one tool for venv + lockfile + install + run, ~10× faster than pip-based
  tooling. `uv tool install .` cleanly installs the binary on PATH; `uv sync` +
  `uv run` is the dev loop. No second tool, no shell shim, no `source venv/bin/activate`
  ritual.
- **Single entry point.** Keeping everything behind one binary keeps the slash
  command (`thermal-print print receipt …`) symmetric with the CLI surface. Future
  templates surface as `thermal-print print <name>`, not new binaries.

## Alternatives considered

- **`tp` (short name).** Rejected per above — typo-collision with `top`, no
  documentation benefit when you already see it 100 times a day in scrollback.
- **`receipt` (name after the first output).** Rejected — the CLI does more than
  receipts (morning card, ship receipt, end-of-day). Naming it after one
  template ages badly.
- **`pipx` + `pyproject.toml`.** Works the same way functionally but slower and
  requires the extra `pipx` dep. No reason to pick it over `uv`.
- **`requirements.txt` + venv + shell shim in `~/bin`.** Minimal but fragile —
  no lockfile, breaks on Python upgrades, ad-hoc PATH management. Rejected.
- **Multiple binaries (`thermal-print`, `tp-receipt`, etc.).** Rejected —
  defeats the template architecture; we want one dispatcher, not N binaries.

## Consequences

- Repo root grows: `pyproject.toml`, `uv.lock`, `src/thermal_print/`.
- README / CLAUDE.md must document the install path: `uv tool install .` (or
  `uv sync && uv run thermal-print …` from the checkout).
- `.claude/commands/receipt.md` shells out to `thermal-print …` — assumes the
  binary is on `PATH` after install. If it isn't, the slash command fails loudly.
- Pinning Python via `pyproject.toml`'s `requires-python = ">=3.11"` — chosen for
  modern syntax & libusb-friendly wheels.
