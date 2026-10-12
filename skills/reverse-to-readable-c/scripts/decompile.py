#!/usr/bin/env python3
"""decompile.py - Parallel batch decompilation with an engine ladder.

Engine ladder (first level that produces output wins, per function):
    1. ghidra  - REA (rea-agents) MCP server driving a full Ghidra install
                 (best correctness: recovers varargs, rotated loops and
                 stripped-binary internals that r2ghidra loses)
    2. pdg     - r2ghidra through radare2
    3. pdc     - radare2 built-in pseudo-disassembly (last resort)

The Ghidra level shares ONE `rea mcp` stdio session across the whole batch
(one JVM + one analysis pass, then ~sub-second decompiles), and falls back
per-function to radare2 whenever REA/Ghidra is unavailable or fails.

Every output file starts with an @evidence header (binary digest, engine
version, decompiler method used) so downstream phases and
verify_cleanup.sh can detect stale or degraded artifacts.

Analysis results for the radare2 levels are cached in an r2 project named
r2c_<sha8> so repeated batches skip `aaa` (set R2C_NO_PROJECT_CACHE=1 to
disable). Set R2C_DECOMPILER=ghidra|pdg|pdc to pin one engine level.

Usage:
    python3 decompile.py <binary> <func_addr1> [func_addr2 ...]
    python3 decompile.py <binary> --file <func_list_file>
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Content lines that indicate real output (r2 prints log noise to stdout
# in some builds; a body shorter than this is treated as empty).
_MIN_BODY_LINES = 3

# Per-MCP-call read timeout (seconds). The first call includes Ghidra's
# lazy auto-analysis, so it needs a much larger budget than later calls.
_MCP_OPEN_TIMEOUT = 1800
_MCP_CALL_TIMEOUT = 600


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


def _rea_available() -> bool:
    if os.environ.get("R2C_NO_REA") == "1":
        return False
    return shutil.which("rea") is not None


def _rea_version() -> str:
    try:
        out = subprocess.run(
            ["rea", "--version"], capture_output=True, text=True, timeout=30,
        )
        return out.stdout.strip().splitlines()[-1]
    except Exception:
        return "unknown"


class ReaGhidraSession:
    """One `rea mcp` stdio session used to batch-decompile via Ghidra.

    Keeping a single session alive amortizes the JVM + Ghidra analysis cost
    across the whole batch (the first tool call triggers the lazy analysis;
    later calls return in well under a second).
    """

    def __init__(self, binary: str):
        self._id = 0
        self._buf = b""
        self.proc = subprocess.Popen(
            ["rea", "mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # log noise
        )
        self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "reverse-to-readable-c", "version": "1"},
        }, timeout=60)
        self._notify("notifications/initialized")
        resp = self._tool("open_binary", {"path": binary}, timeout=_MCP_OPEN_TIMEOUT)
        if resp is None or "error" in resp:
            raise RuntimeError(f"open_binary failed for {binary}")

    # --- stdio JSON-RPC plumbing -------------------------------------

    def _readline(self, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        fd = self.proc.stdout.fileno()
        while b"\n" not in self._buf:
            remain = deadline - time.monotonic()
            if remain <= 0:
                raise TimeoutError("rea mcp read timeout")
            ready, _, _ = select.select([fd], [], [], min(remain, 5.0))
            if not ready:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                raise RuntimeError("rea mcp closed stdout")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line

    def _call(self, method: str, params: dict, timeout: float) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "method": method, "id": self._id, "params": params}
        self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
        self.proc.stdin.flush()
        while True:
            resp = json.loads(self._readline(timeout))
            if resp.get("id") == self._id:
                return resp

    def _notify(self, method: str) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
        self.proc.stdin.flush()

    def _tool(self, name: str, arguments: dict, timeout: float) -> dict | None:
        resp = self._call(
            "tools/call", {"name": name, "arguments": arguments}, timeout,
        )
        content = (resp.get("result") or {}).get("content") or []
        for item in content:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except json.JSONDecodeError:
                    return None
        return None

    # --- engine operations --------------------------------------------

    def resolve(self, name: str) -> str | None:
        resp = self._tool(
            "procedure_address", {"procedure": name}, timeout=_MCP_CALL_TIMEOUT,
        )
        if resp and isinstance(resp.get("result"), str) and not resp.get("error"):
            return resp["result"]
        return None

    def sections(self) -> dict[str, int]:
        """Section name -> REA-side address (loader-level, no analysis)."""
        resp = self._tool("binary_overview", {}, timeout=_MCP_CALL_TIMEOUT)
        result = (resp or {}).get("result") or {}
        out: dict[str, int] = {}
        for seg in result.get("segments") or []:
            name, start = seg.get("name"), seg.get("start")
            if name and start:
                try:
                    out[name] = int(start, 16) if isinstance(start, str) else int(start)
                except (ValueError, TypeError):
                    continue
        return out

    def pseudocode(self, procedure: str) -> str | None:
        resp = self._tool(
            "procedure_pseudo_code", {"procedure": procedure},
            timeout=_MCP_CALL_TIMEOUT,
        )
        if resp and isinstance(resp.get("result"), str) and not resp.get("error"):
            code = resp["result"]
            return code if _has_body(code) else None
        return None

    def close(self) -> None:
        try:
            self._tool("close_binary", {}, timeout=60)
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()


def _r2_function_map(binary: str) -> dict[str, int]:
    """Map r2 function names (as used in mapping.tsv) to vaddrs."""
    try:
        out = subprocess.run(
            ["r2", "-q", "-e", "scr.color=0", "-c", "aaa; aflj", binary],
            capture_output=True, text=True, timeout=1800,
        )
        funcs = json.loads(out.stdout or "[]")
        # r2 6.x uses "addr"; older releases used "offset".
        result: dict[str, int] = {}
        for f in funcs:
            name = f.get("name")
            addr = f.get("addr", f.get("offset", 0))
            if name and addr:
                result[name] = int(addr, 16) if isinstance(addr, str) else int(addr)
        return result
    except Exception:
        return {}


def _r2_section_map(binary: str) -> dict[str, int]:
    """Section name -> r2 vaddr (no analysis required)."""
    try:
        out = subprocess.run(
            ["r2", "-q", "-e", "scr.color=0", "-c", "iSj", binary],
            capture_output=True, text=True, timeout=120,
        )
        secs = json.loads(out.stdout or "[]")
        result: dict[str, int] = {}
        for s in secs:
            name, addr = s.get("name"), s.get("vaddr", s.get("addr"))
            if name and addr:
                result[name] = int(addr, 16) if isinstance(addr, str) else int(addr)
        return result
    except Exception:
        return {}


def _rea_batch(
    binary: str,
    funcs: list[str],
    output_dir: Path,
    sha256: str,
) -> tuple[list[str], list[str], str]:
    """Decompile via one REA/Ghidra session.

    Returns (succeeded, remaining, engine_string). Functions the Ghidra
    level cannot handle (engine failure, unresolvable token) are returned
    as `remaining` so the radare2 ladder can take them.
    """
    engine = f"rea-agents {_rea_version()} (ghidra provider)"
    succeeded: list[str] = []
    remaining: list[str] = []

    session = ReaGhidraSession(binary)
    try:
        r2map = _r2_function_map(binary)

        def plain_name(token: str) -> str | None:
            """Pipeline tokens are r2 names; Ghidra knows plain symbols."""
            if token.startswith(("sym.", "dbg.", "loc.")):
                base = token.split(".", 1)[1]
                return base or None
            if token.startswith("fcn.") or token.startswith("0x"):
                return None
            return token

        # PIE/DSO translation: Ghidra loads at a different base than r2.
        # Derive the delta once from any shared exported symbol; for fully
        # stripped binaries with no exports, fall back to matching section
        # addresses between the two loaders.
        base_delta: int | None = None
        for f in funcs:
            name = plain_name(f)
            addr = r2map.get(f)
            if name and addr and not name.startswith("imp."):
                rea_addr = session.resolve(name)
                if rea_addr:
                    try:
                        base_delta = int(rea_addr, 16) - addr
                        break
                    except ValueError:
                        continue
        if base_delta is None:
            rea_secs = session.sections()
            r2_secs = _r2_section_map(binary)
            for sec_name in (".text", ".rodata", ".data"):
                if sec_name in rea_secs and sec_name in r2_secs:
                    base_delta = rea_secs[sec_name] - r2_secs[sec_name]
                    break

        for f in funcs:
            target: str | None = None
            name = plain_name(f)
            if name:
                target = session.resolve(name)
            if target is None:
                r2addr = r2map.get(f)
                if r2addr is None and f.startswith("0x"):
                    try:
                        r2addr = int(f, 16)
                    except ValueError:
                        r2addr = None
                if r2addr is not None and base_delta is not None:
                    target = hex(r2addr + base_delta)
            if os.environ.get("R2C_DEBUG"):
                print(
                    f"    [dbg] {f}: name={name!r} resolved={target!r} "
                    f"r2addr={r2map.get(f)!r} base_delta={base_delta!r}",
                    file=sys.stderr,
                )
            code = session.pseudocode(target) if target else None
            if code is None:
                remaining.append(f)
                continue
            header = _evidence_header(binary, sha256, engine, "ghidra", f)
            (output_dir / f"func_{f}.c").write_text(
                header + "\n" + code.strip() + "\n", encoding="utf-8",
            )
            succeeded.append(f)
    finally:
        session.close()
    return succeeded, remaining, engine


def decompile_one(
    binary: str,
    func: str,
    output_dir: Path,
    sha256: str = "",
    engine: str = "",
    project: str = "",
    skip_pdg: bool = False,
) -> tuple[str, bool, str]:
    """Decompile a single function via the radare2 ladder (pdg -> pdc).

    Returns (func, success, message).
    """
    out_path = output_dir / f"func_{func}.c"
    base = ["r2", "-q", "-e", "scr.color=0", "-e", "bin.relocs.apply=true"]

    # Try pdg (r2ghidra) unless a pinned engine level skips it
    content = ""
    method = ""
    if not skip_pdg:
        if project:
            content = _run_r2(base + ["-p", project, "-c", f"pdg @ {func}"])
        else:
            content = _run_r2(base + ["-c", f"aaa; pdg @ {func}", binary])
        method = "pdg" if _has_body(content) else ""

    # Fallback to pdc if pdg failed, was skipped, or produced empty output
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
        description="Parallel batch decompilation (engine ladder: REA/Ghidra -> r2ghidra -> pdc)",
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

    level = os.environ.get("R2C_DECOMPILER", "auto").strip().lower()
    if level not in ("auto", "ghidra", "pdg", "pdc"):
        print(f"Warning: unknown R2C_DECOMPILER={level!r}; using auto.")
        level = "auto"

    results: list[tuple[str, bool, str]] = []
    remaining = list(funcs)

    # Engine level 1: REA (Ghidra provider) over one shared MCP session
    if level in ("auto", "ghidra"):
        if _rea_available():
            t0 = time.monotonic()
            try:
                succeeded, remaining, _engine_str = _rea_batch(
                    binary, funcs, output_dir, sha256,
                )
                results += [(f, True, "ghidra") for f in succeeded]
                note = (
                    f"; {len(remaining)} fall back to radare2"
                    if remaining and level == "auto"
                    else f"; {len(remaining)} failed" if remaining else ""
                )
                print(
                    f"Ghidra level: {len(succeeded)} decompiled "
                    f"in {time.monotonic() - t0:.1f}s{note}."
                )
            except Exception as exc:
                print(f"Note: REA/Ghidra level unavailable ({exc}); using radare2.")
                remaining = list(funcs)
        elif level == "ghidra":
            print("Error: R2C_DECOMPILER=ghidra but `rea` was not found on PATH.")
            sys.exit(1)
        else:
            print("Note: `rea` not found; Ghidra level disabled (r2ghidra only).")

    # Engine levels 2-3: radare2 ladder (pdg -> pdc) for the remainder
    if remaining and level in ("auto", "pdg", "pdc"):
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

        print(
            f"radare2 level: {len(remaining)} functions, "
            f"{max_workers} parallel workers..."
        )
        skip_pdg = level == "pdc"
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    decompile_one, binary, func, output_dir,
                    sha256, engine, project, skip_pdg,
                ): func
                for func in remaining
            }
            for future in as_completed(futures):
                func = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append((func, False, f"exception: {exc}"))
    elif remaining:  # engine pinned to ghidra: no fallback for failures
        results += [(f, False, "ghidra failed") for f in remaining]

    success_count = sum(1 for _, ok, _ in results if ok)
    fail_count = len(results) - success_count
    method_counts: dict[str, int] = {}
    for fname, ok, msg in results:
        method_counts[msg] = method_counts.get(msg, 0) + 1
        print(f"  {'✓' if ok else '✗'} {fname} ({msg})")

    print()
    print(
        f"Done — {success_count} succeeded, {fail_count} failed. "
        f"Methods: {', '.join(f'{k}={v}' for k, v in sorted(method_counts.items())) or 'n/a'}. "
        f"Outputs in {output_dir}/"
    )


if __name__ == "__main__":
    main()
