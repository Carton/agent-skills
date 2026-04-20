#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


STRING_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


def collect(path: Path) -> set[str]:
    return set(STRING_RE.findall(path.read_text(encoding="utf-8")))


def iter_right_files(right_root: Path) -> list[Path]:
    return sorted(path for path in right_root.rglob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-root", required=True, type=Path)
    parser.add_argument("--right-root", required=True, type=Path)
    args = parser.parse_args()

    left_root = args.left_root.resolve()
    right_root = args.right_root.resolve()

    for right_path in iter_right_files(right_root):
        rel = right_path.relative_to(right_root)
        left_path = left_root / rel
        if not left_path.exists():
            continue

        left_literals = collect(left_path)
        right_literals = collect(right_path)
        missing = sorted(left_literals - right_literals)
        if missing:
            print(f"## {rel}")
            print(f"missing={len(missing)}")
            for item in missing[:20]:
                print(item)
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

