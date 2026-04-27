#!/usr/bin/env python3
"""decompile.py - Parallel batch decompilation using r2ghidra.

Replaces the sequential bash loop with Python multiprocessing to saturate
all available CPU cores.  Each function gets its own r2 subprocess so the
single-threaded r2 limitation is bypassed via process-level parallelism.

Usage:
    python3 decompile.py <binary> <func_addr1> [func_addr2 ...]
    python3 decompile.py <binary> --file <func_list_file>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def decompile_one(
    binary: str,
    func: str,
    output_dir: Path,
) -> tuple[str, bool, str]:
    """Decompile a single function via r2.

    Returns (func, success, message).
    """
    out_path = output_dir / f"func_{func}.c"

    # Try pdg (ghidra) first
    cmd_pdg = [
        "r2", "-q",
        "-e", "scr.color=0",
        "-e", "bin.relocs.apply=true",
        "-c", f"aaa; pdg @ {func}",
        binary,
    ]
    try:
        result = subprocess.run(
            cmd_pdg,
            capture_output=True,
            text=True,
            timeout=300,
        )
        content = result.stdout.strip()
    except subprocess.TimeoutExpired:
        content = ""

    # Fallback to pdc if pdg failed or produced empty output
    if not content:
        cmd_pdc = [
            "r2", "-q",
            "-e", "scr.color=0",
            "-e", "bin.relocs.apply=true",
            "-c", f"aaa; pdc @ {func}",
            binary,
        ]
        try:
            result = subprocess.run(
                cmd_pdc,
                capture_output=True,
                text=True,
                timeout=300,
            )
            content = result.stdout.strip()
        except subprocess.TimeoutExpired:
            return (func, False, "timeout on both pdg and pdc")

        if not content:
            return (func, False, "pdg and pdc both produced empty output")

        out_path.write_text(content + "\n", encoding="utf-8")
        return (func, True, "fallback to pdc")

    out_path.write_text(content + "\n", encoding="utf-8")
    return (func, True, "pdg")


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

    print(f"Decompiling {len(funcs)} functions using {max_workers} parallel workers...")
    print(f"Output directory: {output_dir}")
    print()

    t0 = time.monotonic()
    success_count = 0
    fail_count = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(decompile_one, binary, func, output_dir): func
            for func in funcs
        }
        for future in as_completed(futures):
            func = futures[future]
            try:
                fname, ok, msg = future.result()
                if ok:
                    success_count += 1
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
        f"Outputs in {output_dir}/"
    )


if __name__ == "__main__":
    main()
