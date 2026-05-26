"""Entry point for the `thermal-print` CLI.

Phase 1: a single `hello` subcommand that opens the TSP 100III and prints
`hello, matt`. Future phases add `print <template>` dispatching to
auto-discovered template modules (see [[plan]] phase 2).
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .printer import print_hello


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thermal-print",
        description="Drive the Star TSP 100III thermal printer.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    sub.add_parser("hello", help="Print 'hello, matt' and cut.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "hello":
        print_hello()
        return 0

    # argparse `required=True` already rejects unknown commands; this is defensive.
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
