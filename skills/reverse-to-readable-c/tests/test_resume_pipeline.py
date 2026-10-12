"""Forward-test the documented retained-result route on a compiled local fixture."""

from __future__ import annotations

import ctypes
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"


class ResumePipelineTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("cc") and shutil.which("nm"), "Requires local C compiler and nm"
    )
    def test_import_prompt_cleanup_compile_and_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target_source = root / "target.c"
            target_source.write_text(
                "unsigned limit_quality(unsigned quality) { return quality > 100 ? 100 : quality; }\n"
                "unsigned quality_from_config(unsigned byte) { return 80 + ((byte & 240) >> 4); }\n"
            )
            binary = root / "target.so"
            subprocess.run(
                ["cc", "-shared", "-fPIC", str(target_source), "-o", str(binary)],
                check=True,
                capture_output=True,
            )
            symbol_output = subprocess.run(
                ["nm", "-D", "--defined-only", str(binary)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            symbols = {
                parts[2]: int(parts[0], 16)
                for line in symbol_output.splitlines()
                if len(parts := line.split()) == 3
            }
            raw_dir = root / "retained"
            raw_dir.mkdir()
            raw_bodies = {
                "limit_quality": "uint limit_quality(uint uVar1) { return uVar1 > 100 ? 100 : uVar1; }\n",
                "quality_from_config": "uint quality_from_config(uint uVar1) { return 80 + ((uVar1 & 240) >> 4); }\n",
            }
            functions = []
            for name, body in raw_bodies.items():
                (raw_dir / f"{name}.c").write_text(body)
                functions.append(
                    {
                        "original_address": hex(symbols[name]),
                        "analysis_address": hex(symbols[name] + 0x100000),
                        "name": name,
                        "recovery": "manual-pseudocode",
                        "code": f"retained/{name}.c",
                        "evidence_id": None,
                    }
                )
            coverage = root / "coverage.json"
            coverage.write_text(
                json.dumps(
                    {
                        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                        "functions": functions,
                        "limitations": [
                            "Synthetic manual test fixture; not an engine-produced REA result"
                        ],
                    }
                )
            )
            project = root / "project"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_ROOT / "import-rea.py"),
                    "--binary",
                    str(binary),
                    "--coverage",
                    str(coverage),
                    "--address-bias",
                    "0x100000",
                    "--project-root",
                    str(project),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            mapping = project / "mapping.tsv"
            mapping.write_text(
                mapping.read_text()
                .replace("\t[TODO]\t[TODO]", "\tlimit_quality\tquality", 1)
                .replace(
                    "quality_from_config\t[TODO]\t[TODO]",
                    "quality_from_config\tquality_from_config\tquality",
                )
            )
            subprocess.run(
                ["bash", str(SCRIPT_ROOT / "apply-mapping.sh")],
                cwd=project,
                check=True,
                capture_output=True,
            )
            prompt = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_ROOT / "generate_subagent_prompt.py"),
                    "--module-root",
                    "clean/raw/quality",
                ],
                cwd=project,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(prompt.count("[UNTRUSTED_CODE_START]"), 2)
            self.assertIn("clean/src/quality/quality_from_config.c", prompt)
            initial = subprocess.run(
                [sys.executable, str(SCRIPT_ROOT / "verify_cleanup.py")],
                cwd=project,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(initial.returncode, 0)
            # A fixture-controlled cleanup stands in for agent transformation; provenance is retained.
            clean_bodies = target_source.read_text().splitlines()
            for index, name in enumerate(raw_bodies):
                (project / f"clean/src/quality/{name}.c").write_text(
                    f"// Original address: @fcn.{symbols[name]:x}\n{clean_bodies[index]}\n"
                )
            verified = subprocess.run(
                [sys.executable, str(SCRIPT_ROOT / "verify_cleanup.py")],
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verified.returncode, 0, verified.stdout)
            clean_binary = root / "recovered.so"
            subprocess.run(
                [
                    "cc",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-shared",
                    "-fPIC",
                    *map(str, (project / "clean/src/quality").glob("*.c")),
                    "-o",
                    str(clean_binary),
                ],
                check=True,
                capture_output=True,
            )
            original, recovered = (
                ctypes.CDLL(str(binary)),
                ctypes.CDLL(str(clean_binary)),
            )
            for name in raw_bodies:
                before, after = getattr(original, name), getattr(recovered, name)
                for function in (before, after):
                    function.argtypes = [ctypes.c_uint]
                    function.restype = ctypes.c_uint
                for value in (0, 1, 70, 90, 100, 101, 240, 255, 0xFFFFFFFF):
                    self.assertEqual(before(value), after(value))


if __name__ == "__main__":
    unittest.main()
