#!/usr/bin/env python3
"""Import retained REA outputs without running a decompiler or changing clean code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


class ImportFailure(ValueError):
    """The supplied evidence cannot safely be reused."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ImportFailure(f"Expected JSON object: {path}")
    return data


def address(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ImportFailure(f"Invalid {label}: {value!r}")
    if isinstance(value, str) and not re.fullmatch(r"0x[0-9a-fA-F]+", value):
        raise ImportFailure(f"{label} must be a default-space 0x address: {value}")
    result = int(value, 0) if isinstance(value, str) else value
    if result < 0:
        raise ImportFailure(f"Negative {label}")
    return result


def evidence_object(data: dict[str, Any]) -> dict[str, Any]:
    structured = data.get("structuredContent", data)
    if not isinstance(structured, dict):
        raise ImportFailure("structuredContent must be an object")
    evidence = structured.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ImportFailure("evidence must be an object")
    return evidence


def expected_evidence_digest(data: dict[str, Any]) -> str | None:
    return evidence_object(data).get("subject", {}).get("digest", {}).get("sha256")


def ensure_same(path: Path, content: bytes) -> None:
    if path.exists() and (not path.is_file() or path.read_bytes() != content):
        raise ImportFailure(f"Refusing to overwrite existing artifact: {path}")


def write_new(path: Path, content: bytes) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def import_outputs(args: argparse.Namespace) -> dict[str, Any]:
    binary = args.binary.resolve(strict=True)
    coverage_path = args.coverage.resolve(strict=True)
    source_root = (args.source_root or coverage_path.parent).resolve(strict=True)
    project = args.project_root.resolve()
    coverage = load_object(coverage_path)
    actual_digest = digest(binary)
    if coverage.get("sha256", coverage.get("binary_sha256")) != actual_digest:
        raise ImportFailure("Binary SHA-256 does not match the coverage manifest")
    functions = coverage.get("functions")
    if not isinstance(functions, list) or not functions:
        raise ImportFailure("Coverage must contain a nonempty functions list")
    declared_count = coverage.get("defined_function_count")
    if declared_count is not None and declared_count != len(functions):
        raise ImportFailure("defined_function_count does not match the functions list")

    procedures: dict[str, Any] | None = None
    procedure_index: dict[str, dict[str, Any]] = {}
    if args.procedures:
        procedures = load_object(args.procedures.resolve(strict=True))
        if expected_evidence_digest(procedures) != actual_digest:
            raise ImportFailure("Procedure evidence SHA-256 does not match the binary")
        structured = procedures.get("structuredContent", procedures)
        inventory = structured.get("result")
        if not isinstance(inventory, list):
            raise ImportFailure("Procedure evidence must contain a result list")
        for item in inventory:
            if not isinstance(item, dict) or "address" not in item:
                raise ImportFailure("Invalid procedure inventory entry")
            procedure_index[item["address"]] = item

    outputs: dict[Path, bytes] = {}
    records: list[dict[str, Any]] = []
    mapping_rows: list[list[str]] = []
    seen_addresses: set[int] = set()
    seen_names: set[str] = set()
    for item in functions:
        if not isinstance(item, dict):
            raise ImportFailure("Each function must be an object")
        original = address(
            item.get("original_address", item.get("elf_address")), "original_address"
        )
        analysis = address(
            item.get("analysis_address", item.get("ghidra_address")), "analysis_address"
        )
        if analysis - original != args.address_bias:
            raise ImportFailure(
                f"Address bias mismatch at {original:#x}: {analysis:#x}"
            )
        name = item.get("name")
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_.$@?]*", name
        ):
            raise ImportFailure(
                f"Unsafe or missing function name: {name!r}; provide an explicit safe name"
            )
        if original in seen_addresses or name in seen_names:
            raise ImportFailure(
                f"Duplicate function address or name: {original:#x} {name}"
            )
        seen_addresses.add(original)
        seen_names.add(name)
        if procedures:
            procedure = procedure_index.get(hex(analysis))
            if procedure is None:
                raise ImportFailure(
                    f"Function absent from procedure inventory: {analysis:#x}"
                )
            if procedure.get("procedure", {}).get("external"):
                raise ImportFailure(
                    f"Default-space source function marked external: {analysis:#x}"
                )
        recovery = str(item.get("recovery", item.get("method", "unknown")))
        method = {
            "ghidra-pseudocode": "ghidra",
            "manual-pseudocode": "manual",
            "manual-reconstruction": "manual",
        }.get(recovery, recovery)
        if not re.fullmatch(r"[a-z][a-z0-9-]*", method):
            raise ImportFailure(f"Invalid recovery method: {recovery!r}")
        code = item.get("code")
        record: dict[str, Any] = {
            "original_address": hex(original),
            "analysis_address": hex(analysis),
            "name": name,
            "method": method,
            "source_recovery": recovery,
            "evidence_id": item.get("evidence_id"),
            "status": "missing",
        }
        if code is not None:
            if not isinstance(code, str) or Path(code).is_absolute():
                raise ImportFailure(
                    f"code must be a source-root-relative path: {code!r}"
                )
            source = (source_root / code).resolve()
            if not source.is_relative_to(source_root):
                raise ImportFailure(f"Source path escapes source root: {code}")
            if not source.is_file():
                raise ImportFailure(
                    f"Missing supplied source: {source}; use code: null for an unresolved entry"
                )
            body = source.read_bytes()
            if not body.strip():
                raise ImportFailure(f"Empty supplied source: {source}")
            source_digest = hashlib.sha256(body).hexdigest()
            filename = Path("phase2") / f"func_{name}.c"
            header = (
                "/* @evidence\n"
                f" * binary: {binary}\n"
                f" * binary_sha256: {actual_digest}\n"
                " * engine: retained-rea\n"
                f" * method: {method}\n"
                f" * original_address: {original:#x}\n"
                f" * analysis_address: {analysis:#x}\n"
                f" * address_bias: {args.address_bias:#x}\n"
                f" * source: {source}\n"
                f" * source_sha256: {source_digest}\n"
                f" * evidence_id: {item.get('evidence_id') or 'none (not supplied)'}\n"
                " * limitations: Imported static output; compilation and equivalence not established.\n"
                " */\n\n"
            ).encode()
            outputs[project / filename] = header + body
            record.update(
                {
                    "source": str(source),
                    "source_sha256": source_digest,
                    "output": str(filename),
                    "status": "imported-manual" if method == "manual" else "imported",
                }
            )
        records.append(record)
        mapping_rows.append([hex(original), name, "[TODO]", "[TODO]"])

    # Preserve classifications already reviewed by the agent; append only new rows.
    mapping = project / "mapping.tsv"
    header_line = "address\toriginal_name\tclean_name\tmodule\n"
    old_rows: dict[int, list[str]] = {}
    mapping_text = header_line
    if mapping.exists():
        mapping_text = mapping.read_text(encoding="utf-8")
        if not mapping_text.startswith(header_line):
            raise ImportFailure("Existing mapping.tsv has an unsupported header")
        for line in mapping_text.splitlines()[1:]:
            row = line.split("\t")
            if len(row) != 4:
                raise ImportFailure("Existing mapping.tsv contains a malformed row")
            key = address(row[0], "mapping address")
            if key in old_rows:
                raise ImportFailure("Existing mapping.tsv contains duplicate addresses")
            old_rows[key] = row
    additions: list[str] = []
    for row in mapping_rows:
        prior = old_rows.get(address(row[0], "mapping address"))
        if prior and prior[1] != row[1]:
            raise ImportFailure(
                f"Existing mapping conflicts with imported symbol: {row[0]}"
            )
        if prior is None:
            additions.append("\t".join(row) + "\n")

    manifest = {
        "schema_version": 1,
        "binary": str(binary),
        "binary_sha256": actual_digest,
        "coverage": str(coverage_path),
        "coverage_sha256": digest(coverage_path),
        "original_address_namespace": args.original_namespace,
        "analysis_address_namespace": args.analysis_namespace,
        "address_bias": hex(args.address_bias),
        "functions": records,
        "limitations": coverage.get("limitations", []),
        "procedure_inventory": "phase1/rea_procedures.json" if procedures else None,
        "procedure_inventory_sha256": digest(args.procedures)
        if args.procedures
        else None,
    }
    outputs[project / "phase1/rea_import_manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    if procedures:
        outputs[project / "phase1/rea_procedures.json"] = args.procedures.read_bytes()
    for path, content in outputs.items():
        ensure_same(path, content)
    # No writes precede validation, and no existing clean/src file is touched.
    for directory in (
        "phase1",
        "phase2",
        "clean/raw",
        "clean/src",
        "context",
        "docs",
        "scripts",
    ):
        (project / directory).mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        write_new(path, content)
    if additions or not mapping.exists():
        mapping.write_text(
            mapping_text.rstrip("\n") + "\n" + "".join(additions), encoding="utf-8"
        )
    progress = (
        "# Progress\n\nCurrent phase: retained REA import; classification review pending.\n\n"
        "Importing existing output did not analyze or execute the binary.\n"
        "Complete classification and architecture before mapping to clean/raw.\n\n"
        + "\n".join(
            f"- [{record['status']}] {record['original_address']} {record['name']} ({record['method']})"
            for record in records
        )
        + "\n"
    )
    write_new(project / "progress.md", progress.encode())
    write_new(
        project / "context/global_map.md",
        b"# Global Map\n\n## Confirmed Types and State\n\n## Third-Party Interfaces\n\n## Unknowns\n\nImported pseudocode still requires type, ABI, and behavior recovery.\n",
    )
    write_new(
        project / "phase1/function_classification.md",
        (
            "# Function Classification\n\n[TODO] Agent review required; filenames do not establish library ownership.\n\n"
            f"Binary SHA-256: `{actual_digest}`\n\nImported scope: {len(records)} functions; "
            f"available code: {sum(record['status'] != 'missing' for record in records)}.\n\n"
            "See `rea_import_manifest.json`, `rea_procedures.json` when supplied, and `mapping.tsv`.\n"
        ).encode(),
    )
    for helper in (
        "verify_cleanup.sh",
        "verify_cleanup.py",
        "generate-subagent-prompt.sh",
        "generate_subagent_prompt.py",
        "apply-mapping.sh",
    ):
        source_helper = Path(__file__).parent / helper
        if source_helper.is_file():
            destination = project / "scripts" / helper
            write_new(destination, source_helper.read_bytes())
            destination.chmod(destination.stat().st_mode | 0o100)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--procedures", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--address-bias", type=lambda value: int(value, 0), required=True
    )
    parser.add_argument("--original-namespace", default="elf-va")
    parser.add_argument("--analysis-namespace", default="ghidra-default")
    args = parser.parse_args()
    try:
        manifest = import_outputs(args)
    except (ImportFailure, OSError, ValueError, TypeError) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Imported {len(manifest['functions'])} function records; no analysis performed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
