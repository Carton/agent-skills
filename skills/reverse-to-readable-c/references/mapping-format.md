# Mapping Format

The bundled scripts expect a TSV mapping file by default.

## Columns

```text
input_path	output_path	old_symbol	new_symbol	address
```

Rules:

- `input_path`: required
- `output_path`: optional; if empty, keep the original basename
- `old_symbol`: optional
- `new_symbol`: optional
- `address`: optional; used for inserting provenance comments
- repeated rows for the same `output_path` are allowed when applying multiple symbol renames to one file

## Example

> **Important**: `output_path` is relative to `--output-root`, not an absolute or project-root-relative path.

```text
input_path	output_path	old_symbol	new_symbol	address
phase2/func_0x401000.c	app/core/startup.c	fcn.00401000	startup_main	0x401000
phase2/func_0x401230.c	app/session/session_core.c	fcn.00401230	session_core	0x401230
phase3/func_0x4018a0.c	app/network/error_converter.c			0x4018a0
```

## Typical Usage

Copy and rename files:

```bash
python3 scripts/apply_mapping.py --mapping mapping.tsv --output-root clean/src
```

Add address comments:

```bash
python3 scripts/add_address_comments.py --mapping mapping.tsv
```

Compare string literals between raw and cleaned files:

```bash
# Use --mapping when files have been renamed (Phase 4+):
python3 scripts/literal_diff.py --left-root phase2 --right-root clean/src --mapping mapping.tsv

# Without --mapping, files are matched by relative path (same filename in both trees):
python3 scripts/literal_diff.py --left-root clean/raw --right-root clean/src
```
