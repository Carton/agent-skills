#!/usr/bin/env python3
"""Check evidence freshness, real token changes, artifacts, and retained literals."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


LEXEME = re.compile(
    r"(?P<comment>/\*.*?\*/|//[^\n]*)"
    r'|(?P<string>(?:u8|[LuU])?"(?:\\.|[^"\\])*")'
    r"|(?P<char>(?:[LuU])?'(?:\\.|[^'\\])*')"
    r"|(?P<word>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<number>(?:0[xX][0-9a-fA-F]+|[0-9]+)(?:\.[0-9]*)?[A-Za-z]*)"
    r"|(?P<punct>[^\s])",
    re.DOTALL,
)
ARTIFACT = re.compile(
    r"\bfcn\.[0-9a-fA-F]+\b|\b[A-Za-z]*Var[0-9]+\b|\bunkbyte[0-9]+\b"
    r"|\bundefined[0-9]*\b|\bcode\s+\*|\b_?(?:DAT|FUN|LAB)_[0-9a-fA-F]+\b"
    r"|\b(?:unaff|extraout|in_stack)_[A-Za-z0-9_]+\b"
    r"|\b(?:CONCAT[0-9]+|SUB[0-9]+|ZEXT[0-9]+|SEXT[0-9]+)\b"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokenize(text: str) -> tuple[list[str], Counter[str], str]:
    tokens: list[str] = []
    strings: Counter[str] = Counter()
    code: list[str] = []
    for match in LEXEME.finditer(text):
        kind = match.lastgroup
        token = match.group()
        if kind == "comment":
            continue
        tokens.append(token)
        if kind == "string":
            strings[token] += 1
            code.append(" ")
        elif kind == "char":
            code.append(" ")
        else:
            code.append(token)
    # Join words with whitespace, but retain fcn.HEX for detection.
    code_text = " ".join(code)
    code_text = re.sub(r"\bfcn\s+\.\s+([0-9a-fA-F]+)", r"fcn.\1", code_text)
    return tokens, strings, code_text


def evidence(text: str) -> dict[str, str]:
    if not text.startswith("/* @evidence"):
        return {}
    end = text.find("*/")
    return dict(re.findall(r"^ \* ([a-z_0-9]+): (.*)$", text[:end], re.MULTILINE))


def main() -> int:
    raw_root, src_root = Path("clean/raw"), Path("clean/src")
    if not raw_root.is_dir() or not src_root.is_dir():
        print(
            "❌ FAIL: clean/raw or clean/src does not exist; run from the project root."
        )
        return 1
    raw_files = {
        path.relative_to(raw_root) for path in raw_root.rglob("*") if path.is_file()
    }
    src_files = {
        path.relative_to(src_root) for path in src_root.rglob("*") if path.is_file()
    }
    if raw_files != src_files:
        print("❌ FAIL: Directory structures do not match:")
        for path in sorted(raw_files ^ src_files):
            print(f"  - {path}")
        return 1
    c_files = sorted(path for path in raw_files if path.suffix == ".c")
    if not c_files:
        print("❌ FAIL: No C files to verify.")
        return 1
    print("✅ PASS: Directory structures match")
    logs: dict[str, list[str]] = {
        "unclean_files": [],
        "artifact_files": [],
        "artifact_details": [],
        "stale_files": [],
        "no_evidence_files": [],
        "literal_loss_files": [],
        "address_files": [],
    }
    review_path = Path("clean/literal_reviews.json")
    try:
        reviews = json.loads(review_path.read_text()) if review_path.is_file() else {}
        if not isinstance(reviews, dict):
            raise ValueError("literal_reviews must be an object")
    except (OSError, ValueError) as error:
        print(f"❌ FAIL: Invalid literal review file: {error}")
        return 1
    digest_cache: dict[Path, str] = {}
    for relative in c_files:
        raw_path, src_path = raw_root / relative, src_root / relative
        raw, src = raw_path.read_text(), src_path.read_text()
        fields = evidence(raw)
        if original_address := fields.get("original_address"):
            comments = "\n".join(
                match.group()
                for match in LEXEME.finditer(src)
                if match.lastgroup == "comment"
            )
            traces = re.findall(r"@fcn\.([0-9a-fA-F]+)\b", comments)
            if not traces or int(traces[0], 16) != int(original_address, 16):
                logs["address_files"].append(
                    f"{relative}: first @fcn comment must use original_address {original_address}, not analysis_address"
                )
        if source_digest := fields.get("source_sha256"):
            _, separator, payload = raw_path.read_bytes().partition(b" */\n\n")
            if not separator or hashlib.sha256(payload).hexdigest() != source_digest:
                logs["stale_files"].append(
                    f"{relative}: retained raw payload digest mismatch"
                )
        expected, binary_name = fields.get("binary_sha256"), fields.get("binary")
        if not expected:
            logs["no_evidence_files"].append(str(relative))
        elif not binary_name or not Path(binary_name).is_file():
            logs["stale_files"].append(f"{relative}: recorded binary unavailable")
        else:
            binary = Path(binary_name)
            if binary not in digest_cache:
                digest_cache[binary] = sha256(binary)
            if digest_cache[binary] != expected:
                logs["stale_files"].append(f"{relative}: binary digest mismatch")
        raw_tokens, raw_strings, _ = tokenize(raw)
        src_tokens, src_strings, src_code = tokenize(src)
        if raw_tokens == src_tokens:
            logs["unclean_files"].append(str(relative))
        if artifacts := ARTIFACT.findall(src_code):
            logs["artifact_files"].append(str(relative))
            logs["artifact_details"].append(
                f"{relative}: {', '.join(sorted(set(artifacts)))}"
            )
        missing = raw_strings - src_strings
        if missing:
            review = reviews.get(str(relative), {})
            approved = (
                isinstance(review, dict)
                and review.get("raw_sha256") == sha256(raw_path)
                and isinstance(review.get("reason"), str)
                and bool(review["reason"].strip())
                and Counter(review.get("missing_literals", [])) == missing
            )
            if not approved:
                logs["literal_loss_files"].append(
                    f"{relative}: missing {dict(missing)!r}; preserve logs/literals or record a digest-bound review"
                )
        if raw_tokens and len(src_tokens) < len(raw_tokens) * 0.3:
            print(
                f"⚠️ WARNING: {relative} retains fewer than 30% of raw code tokens; review behavior manually."
            )
    for name, entries in logs.items():
        path = Path("clean") / f"{name}.log"
        if entries:
            path.write_text("\n".join(entries) + "\n")
        else:
            path.unlink(missing_ok=True)
    fail = False
    for name, description in (
        ("unclean_files", "unchanged code tokens (comments/formatting do not count)"),
        ("artifact_files", "decompiler artifacts"),
        ("stale_files", "STALE or unverifiable raw evidence"),
        ("literal_loss_files", "lost string literals"),
        ("address_files", "incorrect or missing original address traceability"),
    ):
        if entries := logs[name]:
            fail = True
            print(f"❌ FAIL: {len(entries)} file(s): {description}")
            for entry in entries[:20]:
                print(f"  - {entry}")
    if logs["no_evidence_files"]:
        print(
            f"⚠️ WARNING: {len(logs['no_evidence_files'])} raw file(s) lack an @evidence header (legacy compatibility)."
        )
    if fail:
        return 1
    print(
        f"✅ ALL CHECKS PASSED - {len(c_files)} C files passed mechanical cleanup checks."
    )
    print("Compilation and semantic equivalence require separate validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
