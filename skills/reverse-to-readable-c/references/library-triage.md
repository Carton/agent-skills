# Library/Runtime Triage

`scripts/triage_library_candidates.py` is a conservative second-pass filter for `reverse-to-readable-c` projects. It is designed for the standard skill workspace layout, not for arbitrary reverse-engineering directories.

The script itself intentionally contains only small generic rules. The agent must fill project-specific rules before relying on the report.

## Inputs

The script expects the normal Phase 1 artifacts:

- `mapping.tsv`
- `phase1/all_functions.txt`
- `phase1/callgraph.json`
- `phase1/string_xref.md`
- `phase1/all_xrefs.json`

With `--include-clean`, it can also inspect:

- `clean/raw/`
- `clean/src/`

## Rules File

Generate the fill-in template:

```bash
python3 scripts/triage_library_candidates.py --init-rules phase1/library_triage_rules.json
```

The agent should then edit:

- `application_markers`: product names, protocol names, domain strings, local event names, or other strings that indicate own code and should prevent automatic skip.
- `categories`: third-party/runtime categories confirmed from `all_strings.txt`, `string_xref.md`, and `callgraph_summary.md`.

Keep rules conservative. It is better to miss a library function than to skip application logic.

## Purpose

The graph classifier is high-recall: it assigns most functions to a plausible module so Phase 2 can start. Library/runtime triage is high-precision: it catches functions that look like standard-library, compiler-runtime, or third-party internals and produces a review queue.

Do not use this script as a full replacement for `classify_functions.py`.

## Actions

The report uses these actions:

- `REVIEW_SKIP`: high-confidence skip candidate; inspect and usually mark `[SKIP:<category>]`.
- `AI_REVIEW`: medium-confidence candidate; inspect in small batches.
- `KEEP`: contains application markers; avoid automatic skip even if it calls library helpers.
- `MANUAL_REVIEW`: no strong evidence.

## Workflow

1. Run `init-project.sh`; it automatically generates `phase1/library_triage_rules.json`.
2. Fill project-specific markers and third-party categories in the rules file.
3. Run `scripts/triage_library_candidates.py --rules phase1/library_triage_rules.json`.
4. Review `REVIEW_SKIP` first.
5. Confirm candidates against strings, callers/callees, and raw decompiler output when available.
6. Update `mapping.tsv` manually for confirmed third-party/runtime functions.
7. Add confirmed interfaces to `context/global_map.md`.

## Phase 5 Recheck

Before large cleanup batches, rerun the script with clean tree inspection:

```bash
python3 scripts/triage_library_candidates.py \
    --include-clean \
    --only-unclean \
    --output-tsv clean/library_triage_unclean.tsv \
    --output-md docs/library_triage_unclean.md
```

This helps find remaining unclean files that are probably library/runtime internals and should be skipped instead of cleaned.
