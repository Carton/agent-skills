#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


FUNCTION_RE = re.compile(
    r"^(?!#include)(?!typedef)(?!struct\b)(?!enum\b)(?!//)([A-Za-z_.][\w.\s\*]*\([^;]*\))\s*\{?\s*$",
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

    match = FUNCTION_RE.search(text)
    if match is None:
        return False

    line_start = text.rfind("\n", 0, match.start())
    insert_at = 0 if line_start == -1 else line_start + 1
    updated = text[:insert_at] + marker + "\n" + text[insert_at:]
    file_path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()

    base_dir = args.base_dir.resolve()
    for output_path, address in load_mapping(args.mapping.resolve()):
        if not output_path.is_absolute():
            output_path = base_dir / output_path
        if insert_comment_if_missing(output_path, address):
            print(f"updated {output_path}")
        else:
            print(f"skipped {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

