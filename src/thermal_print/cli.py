"""Entry point for the ``thermal-print`` CLI.

Phase 2: ``thermal-print print <name>`` dispatches to auto-discovered template
modules in :mod:`thermal_print.templates`. A bad template (syntax error,
missing attributes, duplicate ``NAME``) is fatal at startup with the
offending filename.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .printer import open_printer
from .receipt import Receipt

Render = Callable[[dict[str, Any], Receipt], None]


def _discover_in_path(path: Path, package_name: str | None) -> dict[str, Render]:
    """Walk ``path`` for ``.py`` files, import each, build ``{NAME: render}``.

    If ``package_name`` is given, modules are imported under that package
    namespace (production path). Otherwise each file is loaded as a
    free-standing module (test path).

    Fatal errors print a single-line message naming the offending file and
    raise :class:`SystemExit(2)` — better noisy than silently dropping a
    template.
    """
    registry: dict[str, tuple[str, Render]] = {}
    for py_file in sorted(path.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        stem = py_file.stem

        try:
            if package_name:
                module = importlib.import_module(f"{package_name}.{stem}")
            else:
                spec = importlib.util.spec_from_file_location(stem, py_file)
                if spec is None or spec.loader is None:
                    raise ImportError(f"could not load spec for {py_file}")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
        except SyntaxError as e:
            print(
                f"error: template {py_file.name} has a syntax error: {e.msg} "
                f"(line {e.lineno})",
                file=sys.stderr,
            )
            raise SystemExit(2)
        except Exception as e:
            print(
                f"error: template {py_file.name} failed to import: {e}",
                file=sys.stderr,
            )
            raise SystemExit(2)

        name = getattr(module, "NAME", None)
        render = getattr(module, "render", None)
        if not isinstance(name, str) or not callable(render):
            print(
                f"error: template {py_file.name} must define NAME: str and "
                "render(ctx, r)",
                file=sys.stderr,
            )
            raise SystemExit(2)

        if name in registry:
            prev_filename = registry[name][0]
            print(
                f"error: duplicate template NAME={name!r} in "
                f"{py_file.name} and {prev_filename}",
                file=sys.stderr,
            )
            raise SystemExit(2)

        registry[name] = (py_file.name, render)

    return {name: render for name, (_, render) in registry.items()}


def discover_templates() -> dict[str, Render]:
    """Discover templates shipped inside the package."""
    from . import templates as templates_pkg

    return _discover_in_path(Path(templates_pkg.__path__[0]), "thermal_print.templates")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thermal-print",
        description="Drive the Star TSP 100III thermal printer.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    p_print = sub.add_parser("print", help="Print a template.")
    p_print.add_argument(
        "template",
        help="Template name (one of the auto-discovered modules in templates/).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "print":
        templates = discover_templates()
        if args.template not in templates:
            available = ", ".join(sorted(templates)) or "(none)"
            print(
                f"error: unknown template {args.template!r}. Available: {available}",
                file=sys.stderr,
            )
            return 2

        ctx: dict[str, Any] = {}  # phase 2: empty; later phases populate
        r = Receipt()
        templates[args.template](ctx, r)

        printer = open_printer()
        r.send(printer)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
