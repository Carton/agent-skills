#!/usr/bin/env python3
"""Run focused Python checks synchronously, including under restricted sandboxes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = [
        "scripts/import-rea.py",
        "scripts/generate_subagent_prompt.py",
        "scripts/verify_cleanup.py",
        "scripts/check-tools.py",
        "tests/test_retained_rea.py",
        "tests/test_resume_pipeline.py",
    ]
    commands = [
        ["ruff", "check", "--fix", *files],
        ["ruff", "format", *files],
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
