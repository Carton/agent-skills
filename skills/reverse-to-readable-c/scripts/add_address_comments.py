#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


# Matches a function definition line:
#   - must NOT start with preprocessor (#), C comment (//, /*), or typedef/struct/enum
#   - optional return type (e.g. "int ", "void ", "char ** ")
#   - function name: identifier starting with letter or underscore
#   - parameter list in parens
#   - optional opening brace
FUNCTION_RE = re.compile(
    r"^(?!#)(?!//)(?!/\*)(?:[A-Za-z_][\w\s\*]*\s+)?"
    r"([A-Za-z_]\w*)\s*"
    r"\([^;]*\)\s*(?:\{)?$",
    re.MULTILINE,
)

# Fallback: first non-empty, non-comment line (after stripping leading whitespace)
FIRST_CODE_LINE_RE = re.compile(
    r"^(?!#)(?!//)(?!/\*)(?!\s*$)(.+)$",
    re.MULTILINE,
)


def load_mapping(mapping_path: Path) -> list[tuple[Path, str]]:
    results: list[tuple[Path, str]] = []
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            output_path = row.get("output_path") or row.get("input_path")
            address = (row.get("address") or "").strip()
            if output_path and address:
                results.append((Path(output_path).expanduser(), address))
    return results


def insert_comment_if_missing(file_path: Path, address: str) -> bool:
    text = file_path.read_text(encoding="utf-8")
    marker = f"// Original address: {address}"
    if marker in text:
        return False

    insert_at = _find_function_start(text)
    if insert_at is None:
        print(f"  warning: no function signature found in {file_path}, skipping", file=sys.stderr)
        return False

    updated = text[:insert_at] + marker + "\n" + text[insert_at:]
    file_path.write_text(updated, encoding="utf-8")
    return True


def _find_function_start(text: str) -> int | None:
    """Find the insert position before the first function definition.

    Returns the character offset where an address comment should be inserted,
    or None if no suitable position is found.
    """
    # Strategy 1: match a function definition line
    match = FUNCTION_RE.search(text)
    if match is not None:
        line_start = text.rfind("\n", 0, match.start())
        return 0 if line_start == -1 else line_start + 1

    # Strategy 2: fallback to first non-empty, non-comment line
    match = FIRST_CODE_LINE_RE.search(text)
    if match is not None:
        line_start = text.rfind("\n", 0, match.start())
        return 0 if line_start == -1 else line_start + 1

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Add original address comments to decompiled C files")
    parser.add_argument("--mapping", required=True, type=Path, help="path to mapping TSV file")
    parser.add_argument("--base-dir", type=Path, default=Path.cwd(), help="base directory for relative paths")
    args = parser.parse_args()

    base_dir = args.base_dir.resolve()
    for output_path, address in load_mapping(args.mapping.resolve()):
        if not output_path.is_absolute():
            output_path = base_dir / output_path
        if not output_path.exists():
            print(f"  error: file not found: {output_path}", file=sys.stderr)
            continue
        if insert_comment_if_missing(output_path, address):
            print(f"updated {output_path}")
        else:
            print(f"skipped {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
