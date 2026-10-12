#!/usr/bin/env python3
"""decompile.py - Parallel batch decompilation using r2ghidra.

Replaces the sequential bash loop with Python multiprocessing to saturate
all available CPU cores.  Each function gets its own r2 subprocess so the
single-threaded r2 limitation is bypassed via process-level parallelism.

Every output file starts with an @evidence header (binary digest, engine
version, decompiler method used) so downstream phases and
verify_cleanup.sh can detect stale or degraded artifacts.

Analysis results are cached in an r2 project named r2c_<sha8> so repeated
batches skip `aaa` (set R2C_NO_PROJECT_CACHE=1 to disable).

Usage:
    python3 decompile.py <binary> <func_addr1> [func_addr2 ...]
    python3 decompile.py <binary> --file <func_list_file>
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Content lines that indicate real output (r2 prints log noise to stdout
# in some builds; a body shorter than this is treated as empty).
_MIN_BODY_LINES = 3


def _r2_version() -> str:
    try:
        out = subprocess.run(
            ["r2", "-v"], capture_output=True, text=True, timeout=30,
        )
        return out.stdout.splitlines()[0].strip()
    except Exception:
        return "radare2 (version unknown)"


def _project_name(binary: str) -> str:
    sha = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
    return f"r2c_{sha[:8]}"


def _ensure_project(binary: str, project: str) -> bool:
    """Create the analysis cache project if it does not exist yet.

    Returns True when the project can be used for this run.
    """
    try:
        listed = subprocess.run(
            ["r2", "-q", "-c", "P", "/dev/null"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if project not in listed.stdout:
            subprocess.run(
                ["r2", "-q", "-e", "scr.color=0", "-e", "bin.relocs.apply=true",
                 "-c", f"aaa; Ps {project}", binary],
                capture_output=True,
                text=True,
                timeout=1800,
            )
    except Exception:
        return False
    # Verify the project actually got saved (Ps can fail silently,
    # e.g. when git is unusable).
    try:
        listed = subprocess.run(
            ["r2", "-q", "-c", "P", "/dev/null"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return project in listed.stdout
    except Exception:
        return False


def _evidence_header(
    binary: str, sha256: str, engine: str, method: str, func: str,
) -> str:
    lines = [
        "/* @evidence",
        f" * binary: {binary}",
        f" * binary_sha256: {sha256}",
        f" * engine: {engine}",
        f" * method: {method}",
        f" * function: {func}",
        f" * generated: {datetime.datetime.now().isoformat(timespec='seconds')}",
    ]
    if method == "pdc":
        lines.append(
            " * WARNING: the Ghidra decompiler (pdg) failed on this function;"
            " pdc output is pseudo-disassembly. Verify control flow,"
            " call arguments and counters against `pdf` before trusting it."
        )
    lines.append(" */")
    return "\n".join(lines)


def _run_r2(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def _has_body(content: str) -> bool:
    return len(content.splitlines()) >= _MIN_BODY_LINES and "{" in content


def decompile_one(
    binary: str,
    func: str,
    output_dir: Path,
    sha256: str = "",
    engine: str = "",
    project: str = "",
) -> tuple[str, bool, str]:
    """Decompile a single function via r2.

    Returns (func, success, message).
    """
    out_path = output_dir / f"func_{func}.c"
    base = ["r2", "-q", "-e", "scr.color=0", "-e", "bin.relocs.apply=true"]

    # Try pdg (ghidra) first
    if project:
        content = _run_r2(base + ["-p", project, "-c", f"pdg @ {func}"])
    else:
        content = _run_r2(base + ["-c", f"aaa; pdg @ {func}", binary])
    method = "pdg" if _has_body(content) else ""

    # Fallback to pdc if pdg failed or produced empty output
    if not method:
        if project:
            content = _run_r2(base + ["-p", project, "-c", f"pdc @ {func}"])
        else:
            content = _run_r2(base + ["-c", f"aaa; pdc @ {func}", binary])
        method = "pdc" if _has_body(content) else ""

        if not method:
            return (func, False, "pdg and pdc both produced empty output")

    header = _evidence_header(binary, sha256, engine, method, func)
    out_path.write_text(header + "\n" + content + "\n", encoding="utf-8")
    return (func, True, method)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel batch decompilation using r2ghidra",
    )
    parser.add_argument("binary", help="Path to the target binary")
    parser.add_argument("funcs", nargs="*", help="Function addresses to decompile")
    parser.add_argument(
        "--file", "-f",
        dest="func_file",
        help="Read function list from file (one per line)",
    )
    parser.add_argument(
        "--output", "-o",
        default="phase2",
        help="Output directory (default: phase2)",
    )
    parser.add_argument(
        "--jobs", "-j",
        type=int,
        default=0,
        help="Max parallel jobs (default: all CPUs)",
    )
    args = parser.parse_args()

    binary = args.binary
    if not os.path.isfile(binary):
        print(f"Error: binary not found: {binary}", file=sys.stderr)
        sys.exit(1)

    # Collect function list
    funcs: list[str] = list(args.funcs) if args.funcs else []
    if args.func_file:
        path = Path(args.func_file)
        if not path.is_file():
            print(f"Error: function list file not found: {path}", file=sys.stderr)
            sys.exit(1)
        funcs.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    if not funcs:
        print("Error: no functions specified", file=sys.stderr)
        sys.exit(1)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_funcs: list[str] = []
    for f in funcs:
        if f not in seen:
            seen.add(f)
            unique_funcs.append(f)
    funcs = unique_funcs

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    max_workers = args.jobs if args.jobs > 0 else os.cpu_count() or 4

    sha256 = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
    engine = _r2_version()

    project = ""
    if os.environ.get("R2C_NO_PROJECT_CACHE") != "1":
        project = _project_name(binary)
        if not _ensure_project(binary, project):
            print(
                "Note: r2 project cache unavailable; "
                "falling back to per-function aaa."
            )
            project = ""

    print(f"Decompiling {len(funcs)} functions using {max_workers} parallel workers...")
    print(f"Output directory: {output_dir}")
    print()

    t0 = time.monotonic()
    success_count = 0
    fail_count = 0
    method_counts: dict[str, int] = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                decompile_one, binary, func, output_dir, sha256, engine, project,
            ): func
            for func in funcs
        }
        for future in as_completed(futures):
            func = futures[future]
            try:
                fname, ok, msg = future.result()
                if ok:
                    success_count += 1
                    method_counts[msg] = method_counts.get(msg, 0) + 1
                    print(f"  ✓ {fname} ({msg})")
                else:
                    fail_count += 1
                    print(f"  ✗ {fname} - {msg}")
            except Exception as exc:
                fail_count += 1
                print(f"  ✗ {func} - exception: {exc}")

    elapsed = time.monotonic() - t0
    print()
    print(
        f"Done in {elapsed:.1f}s — "
        f"{success_count} succeeded, {fail_count} failed. "
        f"Methods: {', '.join(f'{k}={v}' for k, v in sorted(method_counts.items())) or 'n/a'}. "
        f"Outputs in {output_dir}/"
    )


if __name__ == "__main__":
    main()
