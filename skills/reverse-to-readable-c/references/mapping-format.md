# Mapping Format

The bundled scripts expect a TSV (Tab-Separated Values) mapping file named `mapping.tsv` by default. This file tracks the translation from raw decompiled functions to structured, renamed source files.

## Columns

```text
address	original_name	clean_name	module
```

Rules:

- `address`: The original address of the function in the binary (e.g., `0x401000`). Used for inserting provenance comments.
- `original_name`: The raw name produced by the decompiler (e.g., `fcn.00401000` or an imported symbol name).
- `clean_name`: The semantic name you want to give to the file and function (e.g., `startup_main`).
- `module`: The logical component or directory name where the cleaned file will reside. This column is the **Single Source of Truth** for what happens to the function:
  - `[TODO]`: Function has not been analyzed or categorized yet.
  - `[SKIP: <reason>]` (e.g., `[SKIP: stdlib]`): This marks the function as a Third-Party or System Library. Functions with this prefix in the module column will be **completely ignored** by `decompile.sh` and `apply-mapping.sh`, saving immense time and context length.
  - `<module_name>` (e.g., `core`, `network`): Application logic. This will be fully decompiled, moved to `clean/src/<module_name>/`, and cleaned by the agent.

> **Note**: Both `clean_name` and `module` will initially be set to `[TODO]` by `init-project.sh`. You must update these before running `apply-mapping.sh`.

## Example

```text
address	original_name	clean_name	module
0x401000	fcn.00401000	startup_main	core
0x401230	fcn.00401230	session_core	session
0x4018a0	fcn.004018a0	[TODO]	[TODO]
```

## Typical Usage

Copy and rename files (Phase 4):
This creates `clean/raw/<module>/<clean_name>.c` and `clean/src/<module>/<clean_name>.c`.
```bash
scripts/apply-mapping.sh
```

Add address comments:
This injects `// Original address: @fcn.XXXX` into the `clean/src/` files based on the mapping.
```bash
scripts/add-comments.sh
```

Compare string literals between raw and cleaned files:
```bash
# Use --mapping when files have been renamed (Phase 4+):
python3 scripts/literal_diff.py --left-root phase2 --right-root clean/src --mapping mapping.tsv

# Without --mapping, files are matched by relative path (same filename in both trees):
python3 scripts/literal_diff.py --left-root clean/raw --right-root clean/src
```
