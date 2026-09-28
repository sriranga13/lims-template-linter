"""CLI: lint lab template JSON files against governance rules.

Exit codes:
    0 - no findings that fail the build (errors, or warnings with --strict)
    1 - findings that fail the build
    2 - usage errors (no files, unreadable paths, bad flags)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from template_linter.rules import (
    LintReport,
    finding_to_dict,
    format_text,
    lint_documents,
)
from template_linter.schema import load_document


def collect_paths(inputs: list[str]) -> tuple[list[str], list[str]]:
    """Expand files and directories into a sorted list of JSON file paths."""
    files: list[str] = []
    problems: list[str] = []
    for raw in inputs:
        p = Path(raw)
        if not p.exists():
            problems.append(f"{raw}: no such file or directory")
            continue
        if p.is_dir():
            found = sorted(str(x) for x in p.rglob("*.json"))
            if not found:
                problems.append(f"{raw}: directory contains no .json files")
            files.extend(found)
        elif p.is_file():
            files.append(str(p))
        else:
            problems.append(f"{raw}: not a file or directory")
    return files, problems


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="lims-template-lint",
        description="Lint lab template JSON definitions against governance rules.",
    )
    ap.add_argument("paths", nargs="+",
                    help="template JSON file(s) or directories containing them")
    ap.add_argument("--format", choices=("text", "json"), default="text",
                    help="report format (default: text)")
    ap.add_argument("--strict", action="store_true",
                    help="fail on warnings as well as errors")
    ap.add_argument("--quiet", action="store_true",
                    help="only print the summary line (text format)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    files, problems = collect_paths(args.paths)
    if problems:
        for p in problems:
            print(f"lims-template-lint: error: {p}", file=sys.stderr)
        return 2
    if not files:
        print("lims-template-lint: error: no template files to check",
              file=sys.stderr)
        return 2

    docs = [load_document(f) for f in files]
    report = lint_documents(docs)

    if args.format == "json":
        payload = {
            "files_checked": report.files_checked,
            "entities_checked": report.entities_checked,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "ok": report.ok(strict=args.strict),
            "findings": [finding_to_dict(f) for f in report.findings],
        }
        print(json.dumps(payload, indent=2))
    elif args.quiet:
        print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    else:
        print(format_text(report))

    return 0 if report.ok(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
