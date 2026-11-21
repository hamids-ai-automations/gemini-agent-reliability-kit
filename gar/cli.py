"""Command line interface: ``gar run``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .providers import build_provider
from .report import dumps_json, render_markdown, render_text
from .suite import load_suite, run_suite


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gar", description="Gemini Agent Reliability Kit")
    parser.add_argument("--version", action="version", version=f"gar {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a suite against a provider")
    run.add_argument("--suite", required=True, help="path to a JSON or YAML suite")
    run.add_argument("--provider", default="mock", choices=["mock", "gemini"])
    run.add_argument("--model", default="gemini-2.0-flash")
    run.add_argument("--gate", type=float, default=0.9, help="minimum pass rate (0-1)")
    run.add_argument("--report", help="write a markdown report to this path")
    run.add_argument("--json", dest="json_path", help="write machine-readable results to this path")
    run.add_argument("--fail-on-gate", action="store_true", help="exit 1 when the gate is missed (CI use)")
    run.add_argument("--quiet", action="store_true", help="suppress per-case progress output")
    run.add_argument("--mock-profile", default="good", help="failure profile for the mock provider")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "run":
        try:
            suite = load_suite(args.suite)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.provider == "mock":
            provider = build_provider("mock", profile=args.mock_profile, model="mock-1")
        else:
            provider = build_provider("gemini", model=args.model)

        result = run_suite(suite, provider, gate=args.gate, progress=not args.quiet)
        print()
        print(render_text(result))

        if args.report:
            path = Path(args.report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_markdown(result), encoding="utf-8")
            print(f"\nmarkdown report -> {path}")
        if args.json_path:
            path = Path(args.json_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dumps_json(result), encoding="utf-8")
            print(f"json results    -> {path}")

        if args.fail_on_gate and not result.summary["gate_passed"]:
            return 1
        return 0

    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
