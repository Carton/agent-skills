#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MappingRow:
    input_path: Path
    output_path: Path | None
    old_symbol: str
    new_symbol: str
    address: str


def load_mapping(mapping_path: Path) -> list[MappingRow]:
    rows: list[MappingRow] = []
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            rows.append(
                MappingRow(
                    input_path=Path(row["input_path"]).expanduser(),
                    output_path=Path(row["output_path"]).expanduser()
                    if row.get("output_path")
                    else None,
                    old_symbol=(row.get("old_symbol") or "").strip(),
                    new_symbol=(row.get("new_symbol") or "").strip(),
                    address=(row.get("address") or "").strip(),
                )
            )
    return rows


def apply_symbol_rename(text: str, old_symbol: str, new_symbol: str) -> str:
    if not old_symbol or not new_symbol:
        return text

    if re.fullmatch(r"[A-Za-z_]\w*", old_symbol):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(old_symbol)}(?![A-Za-z0-9_])")
        return pattern.sub(new_symbol, text)

    return text.replace(old_symbol, new_symbol)


def resolve_output_path(
    row: MappingRow,
    output_root: Path | None,
) -> Path:
    if row.output_path is None:
        if output_root is None:
            return Path(row.input_path.name)
        return output_root / row.input_path.name

    if row.output_path.is_absolute() or output_root is None:
        return row.output_path
    return output_root / row.output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()

    base_dir = args.base_dir.resolve()
    output_root = args.output_root.resolve() if args.output_root else None
    outputs: dict[Path, tuple[Path, str]] = {}

    for row in load_mapping(args.mapping.resolve()):
        input_path = row.input_path
        if not input_path.is_absolute():
            input_path = base_dir / input_path
        output_path = resolve_output_path(row, output_root)
        if not output_path.is_absolute():
            output_path = base_dir / output_path

        if output_path in outputs:
            previous_input, text = outputs[output_path]
            if previous_input != input_path:
                raise ValueError(
                    f"conflicting inputs for {output_path}: {previous_input} vs {input_path}"
                )
        else:
            text = input_path.read_text(encoding="utf-8")

        text = apply_symbol_rename(text, row.old_symbol, row.new_symbol)
        outputs[output_path] = (input_path, text)

    for output_path, (input_path, text) in outputs.items():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(f"{input_path} -> {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
