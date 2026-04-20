#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


def collect(path: Path) -> set[str]:
    return set(STRING_RE.findall(path.read_text(encoding="utf-8")))


def iter_right_files(right_root: Path) -> list[Path]:
    return sorted(path for path in right_root.rglob("*") if path.is_file())


def load_mapping(mapping_path: Path) -> list[tuple[str, str]]:
    """Load mapping file and return list of (input_path, output_path) pairs."""
    pairs: list[tuple[str, str]] = []
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            input_path = (row.get("input_path") or "").strip()
            output_path = (row.get("output_path") or input_path).strip()
            if input_path:
                pairs.append((input_path, output_path))
    return pairs


def diff_pair(left_path: Path, right_path: Path, label: str) -> None:
    if not left_path.exists() or not right_path.exists():
        return

    left_literals = collect(left_path)
    right_literals = collect(right_path)
    missing = sorted(left_literals - right_literals)
    if missing:
        print(f"## {label}")
        print(f"missing={len(missing)}")
        for item in missing[:20]:
            print(item)
        print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-root", required=True, type=Path)
    parser.add_argument("--right-root", required=True, type=Path)
    parser.add_argument("--mapping", type=Path,
                        help="TSV mapping file to correlate left/right files by name "
                             "(input_path -> output_path). When set, files are matched "
                             "via mapping instead of relative path.")
    args = parser.parse_args()

    left_root = args.left_root.resolve()
    right_root = args.right_root.resolve()

    if args.mapping:
        mapping_path = args.mapping.resolve()
        for input_path, output_path in load_mapping(mapping_path):
            left = left_root / input_path
            right = right_root / output_path
            diff_pair(left, right, f"{input_path} <-> {output_path}")
    else:
        for right_path in iter_right_files(right_root):
            rel = right_path.relative_to(right_root)
            left_path = left_root / rel
            if not left_path.exists():
                continue
            diff_pair(left_path, right_path, str(rel))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
