# Continue from retained REA evidence

Use this route when `reverse-engineer-anything` already generated native function inventories and pseudocode. Importing is an offline file operation: it neither opens an engine nor executes the target. Read `progress.md`, `mapping.tsv`, and `context/global_map.md` first if the workspace already contains cleanup work.

## Input contract

Supply the binary, a coverage JSON, and the known address bias. Do not infer the bias from a filename. The coverage format is deliberately explicit:

```json
{
  "sha256": "<SHA-256 of the binary>",
  "defined_function_count": 2,
  "limitations": ["Static analysis only"],
  "functions": [
    {
      "original_address": "0x1234",
      "analysis_address": "0x101234",
      "name": "send_frame",
      "recovery": "ghidra-pseudocode",
      "code": "raw_c/send_frame.c",
      "evidence_id": "ev_supplied_by_REA"
    },
    {
      "original_address": "0x2345",
      "analysis_address": "0x102345",
      "name": "convert_frame",
      "recovery": "failed",
      "code": null,
      "evidence_id": null
    }
  ]
}
```

The existing `elf_address` / `ghidra_address` keys are supported aliases. Addresses must be default-space hex addresses (or nonnegative integers). External addresses such as `EXTERNAL:0x1` belong in the procedure inventory and must not be mistaken for code addresses. Function names must be unique and safe filenames; an explicit normalized name is required for unsupported symbol spellings. `code` is relative to `--source-root`, which defaults to the coverage file's parent. Missing/failed/unknown entries remain in the import manifest and mapping; use `code: null` for an explicitly unresolved function. Supplying a nonexistent source path is an error.

`--procedures` accepts an REA `list_procedures` result, either direct or under `structuredContent`, with `evidence.subject.digest.sha256`. Its complete result is retained without treating external functions, thunks, or third-party candidates as application functions. Each coverage function must exist at the stated analysis address in that inventory. The agent still decides module and library ownership from evidence; filenames do not determine classification.

The importer validates the binary hash against coverage and supplied procedure evidence, checks every address pair against `--address-bias`, rejects duplicate addresses/names and escaping source paths, and records source digests and evidence IDs. No evidence ID is invented. Manual recovery remains `method: manual`; failed or unknown recovery stays visible and requires later investigation.

## Import

From the intended project root, using its `.venv`:

```bash
.venv/bin/python /path/to/skill/scripts/import-rea.py \
  --binary ./libmsusb.so --coverage ./coverage.json \
  --procedures ./evidence/procedures.json \
  --address-bias 0x100000 --project-root .
```

Set `--original-namespace` and `--analysis-namespace` when the pair is not ELF VA / Ghidra default. These labels document namespaces; the supplied bias performs the numeric validation. The importer cannot establish that an operator-supplied coverage manifest is truthful or that raw C is correct. It does not recover missing ABI information.

Outputs:

- `phase2/func_<original_name>.c`: original bytes preceded by a digest-bound `@evidence` header.
- `phase1/rea_import_manifest.json`: import identity, per-function provenance, status, original/analysis addresses, source hashes, limitations.
- `phase1/rea_procedures.json`: unmodified inventory when supplied.
- `mapping.tsv`, `progress.md`, `context/global_map.md`, and classification skeletons, created only when missing. Existing mapping classifications are preserved; new rows are appended as `[TODO]`.
- Verification and prompt helpers are copied only when missing.

Repeated identical imports are idempotent. Existing conflicting raw imports or manifests cause a clear failure, before writes. Existing `clean/src` contents are never replaced. To add new evidence after a failed or changed import, preserve the old manifest/baseline in a versioned evidence directory and import to a new workspace, then reconcile deliberately; the importer does not silently upgrade the evidence source. It creates skeletons, not completed classification reports.

## Continue cleanup

1. Finish `phase1/function_classification.md` and conservative library triage from retained inventories, references, strings, and call paths. State the actual scope: exported functions are not automatically every local helper. Keep skipped interfaces in `context/global_map.md`.
2. Complete the architecture blueprint and assign semantic modules in `mapping.tsv`. A user who authorized continuing the prior scope has already authorized routine classification/cleanup; do not introduce another permission checkpoint.
3. Apply mappings without replacing cleaned files. Preserve raw sources. Verify that raw/src relative filenames match.
4. Recover shared structs, globals and ABI declarations. Pass only a narrow module to a cleanup agent:

```bash
scripts/generate-subagent-prompt.sh \
  --task-file ./context/frame_cleanup_task.md \
  clean/raw/frame/convert_frame.c clean/raw/frame/send_frame.c
```

The task file is a trusted agent-authored assignment with exact output ownership and permitted evidence paths. Each raw file remains an individually delimited untrusted data block. Merge new confirmed types into the global map before starting dependent modules. Verify manual/pdc reconstruction against assembly; query an engine only for missing evidence.

The explicit list controls scope. If the intended assignment is a whole narrow module, list all its files or use `--module-root clean/raw/frame` instead of positional inputs. This collects direct `.c` files, not nested modules. Do not provide only one input while writing “own all module files” in the trusted assignment: that mismatch can cause a worker to stop after the one enumerated file. `@fcn` traceability uses `@evidence original_address` (for example `6880`), while `analysis_address` (for example `0x106880`) is only an engine lookup address. The verifier checks the first traceability comment when the original address is recorded.

5. Run mechanical verification, compile the recovered C with real or explicitly documented dependency declarations, and test the recovered behavior at meaningful boundaries. Examples: byte layout, error returns, conversion output, JPEG quality forwarding, queue ownership and USB transfer splitting. Stubbed external dependencies can test local behavior but cannot prove complete device behavior. Do not substitute a regex pass for semantics.
6. Record per-function coverage, library boundaries, deliberate transformations (such as scalarized SIMD), unexecuted target paths and uncertainties in `docs/project_summary.md`.

## Literal review exceptions

The verifier fails when raw string literals disappear. If confirmed reconstruction moves a string into a shared helper or changes its spelling without changing its bytes, preserve it whenever practical. Otherwise, the reviewing agent may record `clean/literal_reviews.json`:

```json
{
  "frame/send_frame.c": {
    "raw_sha256": "<SHA-256 of clean/raw/frame/send_frame.c>",
    "missing_literals": ["\"original log text\""],
    "reason": "Moved to the shared logger at clean/src/frame/logger.c; reviewed call arguments against assembly."
  }
}
```

The missing literal multiset and raw digest must match exactly, and the reason must identify reviewed evidence. This is a review record, not an automatic equivalence claim. Keep the review in version control.

## Forward testing the route

Run `tests/test_resume_pipeline.py` with the project's `.venv`. It builds a small host ELF fixture, uses its actual exported symbol addresses and digest, imports explicitly manual retained pseudocode, classifies and maps two functions, generates one complete module prompt, checks that unchanged raw fails verification, applies fixture-controlled cleanup, compiles the result with warnings as errors, and compares the two functions across boundary inputs. This tests the import-to-cleanup plumbing and fixture behavior; it neither exercises an AI agent nor proves anything about the investigated target.

For an independent agent evaluation, prepare a new temporary workspace containing only the supplied binary, retained raw code, coverage, procedure evidence, and any trusted shared type declarations. Exclude previously cleaned code. Give the evaluating agent a realistic request without the expected implementation or suspected bug:

> Use `$reverse-to-readable-c` at the workspace skill path to continue this retained native investigation. Recover the selected narrow module into readable, compilable C, preserve the retained evidence, and report what remains unverified. Work only in the temporary workspace.

Review the resulting artifacts and tool transcript for mode choice (no repeated initial analysis), source/digest preservation, explicit complete module ownership, original-address traceability, compilability, meaningful behavior checks, and honestly stated coverage. Compare recovered branches, literals, and ownership against raw code/assembly. Keep the agent's independent findings distinct from the deterministic pipeline test, and improve only failures demonstrated by the run.
