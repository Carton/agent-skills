#!/usr/bin/env python3
"""Conservative library/runtime triage for reverse-to-readable-c projects.

The script is layout-generic for this skill, not binary-generic. Built-in
rules intentionally stay small; project-specific markers belong in the JSON
rules file generated with --init-rules.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{6,16}")
FCN_RE = re.compile(r"fcn\.([0-9a-fA-F]{6,16})")
ARTIFACT_RE = re.compile(r"fcn\.[0-9a-fA-F]+|\b[a-zA-Z]*Var[0-9]+\b|\bunk(?:byte|uint|int)[0-9]+\b")

DEFAULT_RULES: dict[str, Any] = {
    "application_markers": [],
    "categories": {
        "cpp_stdlib": {
            "enabled": True,
            "patterns": [
                {"text": "basic_string", "score": 40},
                {"text": "std::", "score": 25},
                {"text": "__gnu_cxx", "score": 45},
                {"text": "bad_optional_access", "score": 45},
                {"text": "bad_any_cast", "score": 45},
                {"text": "filesystem_error", "score": 40},
                {"text": "cannot create std::vector", "score": 45},
                {"text": "_M_create", "score": 30},
                {"text": "_S_create", "score": 30},
                {"text": "_M_replace", "score": 30},
                {"text": "_S_construct", "score": 30},
                {"text": "GCC: (GNU)", "score": 25},
            ],
        },
        "json_example": {
            "enabled": False,
            "note": "Example only. Enable when strings/callgraph show a bundled JSON parser.",
            "patterns": [
                {"text": "parse_error", "score": 55},
                {"text": "syntax_error", "score": 55},
                {"text": "invalid_string", "score": 55},
                {"text": "invalid_number", "score": 55},
                {"text": "ill_formed_UTF_8", "score": 55},
                {"text": "missing_closing_quote", "score": 55},
            ],
        },
    },
}


@dataclass
class FunctionInfo:
    address: str
    original_name: str = ""
    clean_name: str = ""
    module: str = ""
    strings: set[str] = field(default_factory=set)
    callees: set[str] = field(default_factory=set)
    callers: set[str] = field(default_factory=set)
    rel_paths: set[str] = field(default_factory=set)
    raw_text: str = ""
    src_text: str = ""
    size: int = 0
    blocks: int = 0
    in_degree: int = 0
    out_degree: int = 0
    identical_to_raw: bool = False
    has_artifacts: bool = False
    category: str = "review"
    score: int = 0
    reasons: list[str] = field(default_factory=list)


def normalize_address(value: str) -> str:
    text = value.strip()
    if text.startswith("fcn."):
        text = "0x" + text.removeprefix("fcn.")
    if not text.startswith("0x"):
        text = "0x" + text
    return "0x" + text[2:].lower()


def name_to_address(name: str) -> str | None:
    if name.startswith("fcn."):
        return normalize_address(name)
    match = ADDRESS_RE.search(name)
    if match:
        return normalize_address(match.group(0))
    return None


def write_default_rules(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_instructions": [
            "AI agent: fill application_markers with product/project strings that indicate own code.",
            "Add or enable third-party categories only after reviewing all_strings, string_xref, and callgraph_summary.",
            "Keep rules conservative. This file drives a review report; it should not auto-edit mapping.tsv.",
        ],
        **DEFAULT_RULES,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_rules(path: Path | None) -> dict[str, Any]:
    rules = json.loads(json.dumps(DEFAULT_RULES))
    if path is None or not path.exists():
        return rules
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded.get("application_markers"), list):
        rules["application_markers"] = loaded["application_markers"]
    if isinstance(loaded.get("categories"), dict):
        for name, config in loaded["categories"].items():
            if isinstance(config, dict):
                rules["categories"][name] = config
    return rules


def read_mapping(path: Path) -> dict[str, FunctionInfo]:
    functions: dict[str, FunctionInfo] = {}
    if not path.exists():
        return functions
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            address = normalize_address(row["address"])
            info = functions.setdefault(address, FunctionInfo(address=address))
            info.original_name = row.get("original_name", "")
            info.clean_name = row.get("clean_name", "")
            info.module = row.get("module", "")
    return functions


def load_all_functions(path: Path, functions: dict[str, FunctionInfo]) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) < 4 or not parts[0].startswith("0x"):
            continue
        address = normalize_address(parts[0])
        info = functions.setdefault(address, FunctionInfo(address=address))
        try:
            info.blocks = int(parts[1])
            info.size = int(parts[2])
        except ValueError:
            pass
        if not info.original_name:
            info.original_name = parts[-1]


def load_callgraph(path: Path, functions: dict[str, FunctionInfo]) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for node in data:
        caller_address = name_to_address(node.get("name", ""))
        if caller_address is None:
            continue
        caller = functions.setdefault(caller_address, FunctionInfo(address=caller_address))
        imports = node.get("imports", [])
        caller.out_degree = len(imports)
        for callee_name in imports:
            callee_address = name_to_address(callee_name)
            if callee_address is None:
                continue
            callee = functions.setdefault(callee_address, FunctionInfo(address=callee_address))
            if not callee.original_name:
                callee.original_name = callee_name
            caller.callees.add(callee_address)
            callee.callers.add(caller_address)
    for info in functions.values():
        info.in_degree = len(info.callers)


def load_string_xrefs(path: Path, functions: dict[str, FunctionInfo]) -> None:
    if not path.exists():
        return
    line_re = re.compile(r":\s+(\S+)\s+->\s+str\.(.+)$")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = line_re.search(line)
        if not match:
            continue
        address = name_to_address(match.group(1))
        if address is None:
            continue
        functions.setdefault(address, FunctionInfo(address=address)).strings.add(match.group(2).replace("_", " "))


def load_all_xrefs(path: Path, functions: dict[str, FunctionInfo]) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                items = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                refname = item.get("refname", "")
                if not refname.startswith("str."):
                    continue
                fcn_name = item.get("fcn_name") or item.get("name", "").split("+", 1)[0]
                address = name_to_address(fcn_name)
                if address is None:
                    continue
                functions.setdefault(address, FunctionInfo(address=address)).strings.add(
                    refname.removeprefix("str.").replace("_", " ")
                )


def load_clean_trees(raw_dir: Path, src_dir: Path, functions: dict[str, FunctionInfo]) -> None:
    if not raw_dir.exists() or not src_dir.exists():
        return
    for raw_path in raw_dir.rglob("*.c"):
        rel_path = raw_path.relative_to(raw_dir).as_posix()
        src_path = src_dir / rel_path
        address = name_to_address(rel_path)
        raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        if address is None:
            match = FCN_RE.search(raw_text)
            address = normalize_address(match.group(1)) if match else None
        if address is None:
            continue
        info = functions.setdefault(address, FunctionInfo(address=address))
        info.rel_paths.add(rel_path)
        info.raw_text += "\n" + raw_text
        if src_path.exists():
            src_text = src_path.read_text(encoding="utf-8", errors="ignore")
            info.src_text += "\n" + src_text
            info.identical_to_raw = raw_path.read_bytes() == src_path.read_bytes()
            info.has_artifacts = bool(ARTIFACT_RE.search(src_text))


def score_function(info: FunctionInfo, functions: dict[str, FunctionInfo], rules: dict[str, Any]) -> None:
    evidence_text = "\n".join(
        [info.original_name, info.clean_name, info.module, " ".join(sorted(info.strings)), info.raw_text]
    )
    lower_text = evidence_text.lower()
    category_scores: Counter[str] = Counter()
    reasons: list[str] = []

    if info.module.startswith("[SKIP:"):
        category = info.module.removeprefix("[SKIP:").removesuffix("]").strip()
        category_scores[category] += 100
        reasons.append(f"mapping already marks {info.module}")

    if info.original_name.startswith("sub.msvcrt.dll_"):
        category_scores["msvcrt"] += 100
        reasons.append("import/runtime trampoline points to msvcrt")
    if info.original_name.startswith("sym.imp."):
        lib = info.original_name.split(".")[2] if "." in info.original_name else "winapi"
        category_scores[lib] += 100
        reasons.append("import symbol")

    for category, config in rules.get("categories", {}).items():
        if not isinstance(config, dict) or not config.get("enabled", True):
            continue
        for pattern in config.get("patterns", []):
            text = str(pattern.get("text", ""))
            weight = int(pattern.get("score", 0))
            if text and text.lower() in lower_text:
                category_scores[category] += weight
                reasons.append(f"matched string: {text}")

    skipped_callees = sum(
        1 for callee in info.callees if functions.get(callee, FunctionInfo(callee)).module.startswith("[SKIP:")
    )
    if info.out_degree and skipped_callees / max(info.out_degree, 1) >= 0.8 and info.out_degree <= 4:
        category_scores["library_wrapper"] += 25
        reasons.append("low-outdegree wrapper mostly calls known skip functions")

    if info.out_degree == 0 and info.in_degree >= 5 and not info.strings and info.size <= 80:
        category_scores["leaf_utility"] += 25
        reasons.append("small high-indegree leaf, likely runtime/helper")

    app_markers = [str(marker) for marker in rules.get("application_markers", []) if str(marker)]
    if any(marker.lower() in lower_text for marker in app_markers):
        category_scores["application"] += 70
        reasons.append("matched project application marker; keep out of automatic skip")

    if not category_scores:
        info.category = "review"
        info.score = 0
        info.reasons = []
        return

    category, score = category_scores.most_common(1)[0]
    if category == "application":
        info.category = "application_keep"
        info.score = min(100, score)
    else:
        app_penalty = category_scores.get("application", 0)
        info.category = category
        info.score = max(0, min(100, score - app_penalty // 2))
    info.reasons = reasons[:8]


def classify(functions: dict[str, FunctionInfo], rules: dict[str, Any]) -> None:
    for info in functions.values():
        score_function(info, functions, rules)


def action_for(info: FunctionInfo) -> str:
    if info.category == "application_keep":
        return "KEEP"
    if info.score >= 90:
        return "REVIEW_SKIP"
    if info.score >= 70:
        return "AI_REVIEW"
    return "MANUAL_REVIEW"


def write_tsv(path: Path, rows: list[FunctionInfo]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "address",
                "category",
                "score",
                "action",
                "module",
                "clean_name",
                "size",
                "in_degree",
                "out_degree",
                "identical_to_raw",
                "has_artifacts",
                "paths",
                "strings",
                "reasons",
            ]
        )
        for info in rows:
            writer.writerow(
                [
                    info.address,
                    info.category,
                    info.score,
                    action_for(info),
                    info.module,
                    info.clean_name,
                    info.size,
                    info.in_degree,
                    info.out_degree,
                    int(info.identical_to_raw),
                    int(info.has_artifacts),
                    ";".join(sorted(info.rel_paths)),
                    " | ".join(sorted(info.strings)[:8]),
                    " | ".join(info.reasons),
                ]
            )


def write_markdown(path: Path, rows: list[FunctionInfo], rules_path: Path | None) -> None:
    actions = Counter(action_for(info) for info in rows)
    high_conf_skip = [info for info in rows if action_for(info) == "REVIEW_SKIP"]
    medium_conf_skip = [info for info in rows if action_for(info) == "AI_REVIEW"]
    keep = [info for info in rows if action_for(info) == "KEEP"]
    suspected_application = [
        info
        for info in rows
        if action_for(info) in {"KEEP", "MANUAL_REVIEW"}
        and not info.module.startswith("[SKIP:")
        and not info.original_name.startswith(("sym.imp.", "sub."))
    ]

    lines = [
        "# Library/Runtime Triage Candidates",
        "",
        "This report is conservative. It does not modify `mapping.tsv`; review candidates before marking them `[SKIP:*]`.",
        "",
        "## Rules",
        "",
        f"- Rules file: `{rules_path}`" if rules_path else "- Rules file: built-in defaults only",
        "- Project-specific rules should be filled by the agent in `phase1/library_triage_rules.json` before relying on this report.",
        "",
        "## Summary",
        "",
        f"- Total rows: {len(rows)}",
        f"- Suspected application/local functions after triage: {len(suspected_application)}",
        f"- High-confidence skip candidates: {len(high_conf_skip)}",
        f"- Medium-confidence AI review candidates: {len(medium_conf_skip)}",
        f"- Application markers kept: {len(keep)}",
        "",
        "## Actions",
        "",
    ]
    for action, count in sorted(actions.items()):
        lines.append(f"- `{action}`: {count}")

    lines.extend(["", "## Review First", ""])
    lines.append("| Address | Category | Score | Action | Current module | Evidence |")
    lines.append("|---|---|---:|---|---|---|")
    for info in (high_conf_skip + medium_conf_skip)[:120]:
        reasons = "<br>".join(info.reasons[:4]).replace("|", "\\|")
        lines.append(
            f"| `{info.address}` | `{info.category}` | {info.score} | `{action_for(info)}` | `{info.module}` | {reasons} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Workflow",
            "",
            "1. Review `REVIEW_SKIP` candidates first and confirm they are not application logic.",
            "2. Inspect `AI_REVIEW` entries in small batches.",
            "3. Update `mapping.tsv` only after confirming the function is third-party/runtime code.",
            "4. Add confirmed interfaces to `context/global_map.md`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--phase-dir", type=Path, default=Path("phase1"))
    parser.add_argument("--mapping", type=Path, default=Path("mapping.tsv"))
    parser.add_argument("--rules", type=Path, default=None)
    parser.add_argument("--init-rules", type=Path, default=None, help="Write a fill-in rules JSON template and exit")
    parser.add_argument("--output-tsv", type=Path, default=Path("phase1/library_triage_candidates.tsv"))
    parser.add_argument("--output-md", type=Path, default=Path("phase1/library_triage_candidates.md"))
    parser.add_argument("--include-clean", action="store_true", help="Also inspect clean/raw and clean/src content")
    parser.add_argument("--only-unclean", action="store_true", help="With --include-clean, only report unchanged/artifact files")
    args = parser.parse_args()

    root = args.project_root
    if args.init_rules is not None:
        rules_path = root / args.init_rules
        write_default_rules(rules_path)
        print(f"Wrote rules template: {rules_path}")
        return

    phase_dir = root / args.phase_dir
    rules_path = root / args.rules if args.rules else None
    rules = load_rules(rules_path)

    functions = read_mapping(root / args.mapping)
    load_all_functions(phase_dir / "all_functions.txt", functions)
    load_callgraph(phase_dir / "callgraph.json", functions)
    load_string_xrefs(phase_dir / "string_xref.md", functions)
    load_all_xrefs(phase_dir / "all_xrefs.json", functions)
    if args.include_clean:
        load_clean_trees(root / "clean/raw", root / "clean/src", functions)
    classify(functions, rules)

    rows = list(functions.values())
    if args.include_clean and args.only_unclean:
        rows = [info for info in rows if info.rel_paths and (info.identical_to_raw or info.has_artifacts)]
    rows.sort(key=lambda item: (action_for(item), -item.score, item.category, item.address))

    output_tsv = root / args.output_tsv
    output_md = root / args.output_md
    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    write_tsv(output_tsv, rows)
    write_markdown(output_md, rows, rules_path)

    actions = Counter(action_for(info) for info in rows)
    categories = Counter(info.category for info in rows if action_for(info) in {"REVIEW_SKIP", "AI_REVIEW"})
    print(f"Wrote: {output_tsv}")
    print(f"Wrote: {output_md}")
    print("Action counts:", dict(actions))
    print("Candidate categories:", dict(categories.most_common()))


if __name__ == "__main__":
    main()
