---
name: reverse-to-readable-c
description: End-to-end workflow for reversing native binaries into organized, readable C code using phased analysis, radare2, r2ghidra, optional Ghidra, per-module batching, structured renaming, and AI-assisted cleanup. Use when the task is to explore a PE or ELF binary, identify modules, decompile functions into initial C, reorganize outputs into a better directory layout, rename files/functions, and iteratively convert decompiler output into equivalent readable C without overflowing context.
---

# Reverse To Readable C

Use this skill for full reverse-engineering projects where the goal is not just to inspect a binary, but to produce a maintainable source tree from it.

The workflow is phase-based and aggressively context-limited. Never try to load the whole reverse-engineering output at once.

## Prerequisites Check

**Before starting**, run a quick tool check:

```bash
check_tools() { which r2 && which file && which python3 && r2 -v | head -1; }; check_tools && echo "OK"
```

For full installation and troubleshooting, read [references/install-linux.md](references/install-linux.md).

---

## Principles

- Preserve originals. Raw outputs must remain available for diffing.
- Work one module at a time.
- Keep addresses stable until a module is understood.
- Rename in layers: files first, entry functions second, shared helpers later.
- Treat decompiled C as an intermediate artifact, not the final output.
- Do not abstract tables, strings, callbacks, or ownership/state logic away without checking the raw source again.

## Mandatory Context Hygiene

- Never load the entire decompiled tree into context.
- Limit each cleanup batch to one module or one narrow call-graph neighborhood.
- Prefer 1 root function plus its direct helper/converter files in a single pass.
- If a file is large, load only the relevant sections.
- Keep a raw backup tree for every cleanup target.
- Before replacing a large decompiled block with high-level helpers, verify that strings, lookup tables, event names, and error-code mappings are not being dropped.

Read [references/context-hygiene.md](references/context-hygiene.md) before large cleanup passes.

## Recommended Output Layout

Use a phased workspace. A practical layout is:

```text
project/
├── docs/                     # [Phase 1] findings, indexes, architecture notes
├── phase1/                   # [Phase 1] exploratory analysis and reports
├── phase2/                   # [Phase 2] raw per-function decompilation output
├── clean/
│   ├── raw/                  # [Phase 4] raw backup of all phase2 outputs
│   └── src/                  # [Phase 4→5] renamed + cleaned readable tree
├── scripts/                  # rename / annotation helpers
└── mapping.tsv               # [Phase 4] file/function rename mapping
```

If the repository already has a structure, preserve it and fit the workflow into it.

## Tooling Setup

See [references/install-linux.md](references/install-linux.md) for installation, r2ghidra setup, and target-specific optional tools (Ghidra, wine, etc.).

Quick verify after install:
```bash
r2 -q -c "aaa; pdg @ main" /tmp/test_r2 && echo "decompilation works"
```

---

## Phase 1: Exploratory Analysis

Goal: identify the binary shape, main entry chain, probable modules, and the first 20-50 functions worth tracking.

### Binary Identification

Start with basic file info and string survey:

```bash
file ./target_binary
strings ./target_binary | grep -iE "(usage|error|main|version|help|\.pdb|\.cpp)" | head -30
```

**Then load the platform-specific reference:**

| Detection | Action |
|-----------|--------|
| `file` output contains "PE32+" or "PE32" | Read [references/pe-binary.md](references/pe-binary.md) |
| `file` output contains "ELF" | Read [references/elf-binary.md](references/elf-binary.md) |
| C++ indicators found (MSVC DLLs, mangled names, `<stl>` headers) | Read [references/cpp-handling.md](references/cpp-handling.md) |

### Scope Configuration

**Before diving into analysis**, confirm scope with the user. Default: **application code only**.

1. **Scope**: application code only / application + uncertain / full binary
2. **Platform-specific questions**: load the platform reference above for detailed questions (PDB availability for PE, DWARF/PIE/stripped for ELF)
3. **Language-specific**: if C++ detected, load [references/cpp-handling.md](references/cpp-handling.md)

> **Default behavior**: Only reverse-engineer application code. Standard library wrappers, runtime support functions, and clearly identifiable third-party code should be cataloged but not decompiled unless the user explicitly requests it.

### Library vs Application Code Separation

This is a critical early step that reduces noise for all subsequent phases.

**Step 1: Classify all functions**

After `aaa`, classify functions into three categories.

> **Important**: r2's `~` operator uses **substring matching**, not regex. This means `\.` is treated literally as backslash + dot in bash, not as a regex escape. For reliable scripting, prefer piping through `grep`.

```bash
# === Method A: bash pipe (recommended for scripting) ===
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep 'sym\.imp\.'  # imports
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep -v 'sym\.imp\.' | grep -v 'entry'  # local functions

# === Method B: r2 internal grep (inside r2 interactive shell only) ===
# NOTE: r2 ~ uses substring match, NOT regex. '.' matches literal dot.
# This does NOT work correctly from bash -c due to escaping conflicts.
aaa
afl~sym.imp.       # imports — matches substring "sym.imp."
afl~fcn.           # local functions — matches substring "fcn."

# === Method C: r2 -c with jq for JSON processing ===
r2 -q -e bin.relocs.apply=true -c "aaa; aflj" ./target_binary | python3 -c "
import json, sys
data = json.load(sys.stdin)
imports = [f for f in data if f['name'].startswith('sym.imp')]
local = [f for f in data if not f['name'].startswith('sym.imp') and not f['name'].startswith('entry')]
print(f'imports={len(imports)} local={len(local)}')
"
```

**Step 2: Identify known library patterns in application functions**

Look for function names or call patterns that indicate library wrappers even within local code. Platform-specific patterns are documented in the platform references:

- [references/pe-binary.md](references/pe-binary.md) — MSVC runtime wrappers, STL patterns
- [references/elf-binary.md](references/elf-binary.md) — glibc patterns, fortified functions

**Step 2b: Filter real application functions via string cross-references**

> **This is the most important step.** Simply filtering by `fcn.` prefix is insufficient — C++ binaries typically have hundreds of `fcn.*` functions that are STL template expansions or compiler-generated code. The reliable way to find real business logic is to start from **application strings** and trace backwards.

```bash
# 1. Extract application-specific strings (Usage, error messages, brand names, etc.)
r2 -q -e bin.relocs.apply=true -c "aaa; iz" ./target_binary | grep -i 'Usage'
r2 -q -e bin.relocs.apply=true -c "aaa; iz" ./target_binary | grep -i 'Error'
r2 -q -e bin.relocs.apply=true -c "aaa; iz" ./target_binary | grep '<program_name>'
r2 -q -e bin.relocs.apply=true -c "aaa; iz" ./target_binary | grep '<key_domain_string>'

# 2. For each interesting string, find which function references it
axt @ <string_vaddr>
# Example: axt @ 0x1400366b0
# Output: fcn.1400010a0 0x140006dc5 [STRN] lea rdx, str.Usage:...

# 3. For each function found, extract its call targets to discover helpers
pdf @ fcn.1400010a0 | grep -oP 'fcn\.\w+' | sort -u
# Output: fcn.1400053a0, fcn.140001cad, fcn.140001276, ...
```

Repeat Step 2-3 for 2-3 rounds: from the root functions found in Step 2, decompile their helpers, discover new helpers, etc. Stop when newly discovered functions are clearly generic (path operations, string manipulation, security cookie).

> **Result**: From 900+ `fcn.*` functions, this technique typically narrows down to 5-20 real business functions.

**Step 3: Build a function classification document**

Produce a simple classification (in `phase1/function_classification.md`):

```markdown
# Function Classification

| Category | Count | Notes |
|----------|-------|-------|
| Imported (external DLL calls) | N | Listed in ii / iij |
| Runtime wrappers (MSVCP/VCRUNTIME/ucrtbase) | N | Thin shims around DLL calls |
| STL / exception support | N | __CxxThrowException, etc. |
| Application code (to reverse) | N | **This is the focus** |

## Application Functions (sorted by address)
| Address | Name (if known) | Size | Likely Role |
|---------|-----------------|------|-------------|
| 0x1400010a0 | fcn.1400010a0 | 150 | main (references Usage string) |
| ...
```

**Step 4: Only decompile application functions**

Use the classified list to drive Phase 2 decompilation. Never decompile imported functions or obvious runtime wrappers — they are already documented by their DLL name and symbol.

> **Why this matters**: A typical C++ binary may have 90%+ runtime/STL code. Classifying early means you only decompile the 10% that matters, saving enormous amounts of time and context.

### radare2 Discovery

Always use `aaa` (analyze all) and enable relocs for proper analysis:

```bash
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary
```

> **Note**: Use `aaa` (lowercase), not `-A` (uppercase). `-A` only runs a subset of analysis and may miss functions and cross-references. Always use `-e bin.relocs.apply=true` for PE binaries to resolve imports correctly.

Useful r2 queries:

- `afl` to list discovered functions
- `afll` or `aflj` for sortable inventories
- `izz` / `izj` for strings
- `axt @ <string_addr>` for cross-references from important strings
- `pdf @ addr` for assembly review
- `agf @ addr` or `agfj @ addr` for local graph shape
- `ii` / `iij` for imported functions

### Finding the Main Function

If no symbol table is available, find `main` via string cross-references:

```bash
# In r2 shell:
aaa
# Find usage/help strings (pipe through grep for reliability)
r2 -q -e bin.relocs.apply=true -c "aaa; iz" ./target_binary | grep -i 'Usage'
r2 -q -e bin.relocs.apply=true -c "aaa; iz" ./target_binary | grep -i 'help'
# Cross-reference to find which function uses them
axt @ <string_addr>
```

### What to Produce

- an entry-chain note
- a first-pass module map
- a function index by address
- a shortlist of business-critical roots
- a risk list: parsers, session/auth, networking, startup, configuration, service, update, teardown

Do not decompile everything yet.

## Phase 2: Raw Per-Function Decompilation

Goal: export initial C-like code for only the functions needed for the current module.

> **Important**: Only decompile functions classified as **application code** in Phase 1. Do not decompile imported functions, runtime wrappers, or third-party library code unless the user explicitly requested a broader scope.

Prefer `r2ghidra` through radare2 when available:

```bash
# Open binary once with full analysis
r2 -q -e bin.relocs.apply=true -c "aaa; pdg @ fcn.1400010a0" ./target_binary
```

> **Note**: Use `aaa` (lowercase), not `-A`. See Phase 1 for details.

### Handling ANSI Color Codes

`pdg` output contains ANSI escape codes by default. Strip them when saving to files:

```bash
# Method 1: disable colors explicitly (more portable)
r2 -q -e scr.color=false -e bin.relocs.apply=true -c "aaa; pdg @ fcn.1400010a0" ./target_binary > phase2/func_0x1400010a0.c 2>/dev/null

# Method 2: pipe through sed
r2 -q -e bin.relocs.apply=true -c "aaa; pdg @ fcn.1400010a0" ./target_binary | sed 's/\x1b\[[0-9;]*m//g' > phase2/func_0x1400010a0.c
```

When exporting machine-readable analysis output, write each command to a separate file. Do not concatenate `iI`, `iij`, `aflj`, and `izj` into one stream unless you explicitly want a mixed-format artifact for manual reading.

### Decompiler Crash Fallback

`pdg` (r2ghidra) may crash or produce empty output for certain functions, especially large ones or those with unusual control flow. Use a graduated fallback strategy:

```bash
# Level 1: r2ghidra decompiler (best quality)
timeout 60 r2 -q -e scr.color=false -e bin.relocs.apply=true \
  -c "aaa; pdg @ fcn.00401234" ./target_binary

# Level 2: r2 built-in pdc (less accurate, but more stable)
timeout 60 r2 -q -e scr.color=false -e bin.relocs.apply=true \
  -c "aaa; pdc @ fcn.00401234" ./target_binary

# Level 3: raw disassembly (always works, but requires manual interpretation)
timeout 60 r2 -q -e scr.color=false -e bin.relocs.apply=true \
  -c "aaa; pdf @ fcn.00401234" ./target_binary
```

**Batch decompilation with fallback:**

```bash
decompile_function() {
    local addr=$1
    local outfile="phase2/func_${addr}.c"
    # Try pdg first, fall back to pdc
    if ! timeout 60 r2 -q -e scr.color=false -e bin.relocs.apply=true \
        -c "aaa; pdg @ ${addr}" ./target_binary > "$outfile" 2>/dev/null \
        || [ ! -s "$outfile" ]; then
        echo "pdg failed for ${addr}, falling back to pdc"
        timeout 60 r2 -q -e scr.color=false -e bin.relocs.apply=true \
            -c "aaa; pdc @ ${addr}" ./target_binary > "$outfile" 2>/dev/null
    fi
}
```

> **Tip**: The `timeout` command prevents hanging on complex functions. Adjust the timeout (e.g., 30s for small functions, 120s for large ones) based on function size.

### C++ Binary Noise

For C++ targets, see [references/cpp-handling.md](references/cpp-handling.md) for noise patterns and cleanup strategy.

### File Organization

Useful patterns:

- one file per function
- filename must keep the original address
- examples: `func_0x14000e430.c`, `func_0x140015170.c`

Do not batch-export the whole binary unless you have no better option.

Export order:

1. root business functions
2. direct helpers required to understand them
3. converters / tables / callback helpers
4. generic runtime noise only if it blocks understanding

## Phase 3: Module Formation

Goal: convert an address bag into a module map.

### Small Binary Fast-Track

For simple utilities (single-purpose CLI tools, <50 real functions), skip formal module formation:

1. Identify the 1-3 core business functions (via string references from Phase 1)
2. Decompile only those + their direct helpers
3. Go directly to Phase 5 cleanup

Use this heuristic: if the program has a clear single-purpose `Usage:` string and fewer than 20 application-level functions (excluding runtime/STL), treat it as a small binary.

### Full Module Formation

For larger binaries, group functions by real behavior, not by decompiler order.

Typical buckets:

- `app/core`
- `app/session`
- `app/network`
- `app/config`
- `app/service`
- `app/storage`
- `app/cli`
- `platform`
- `runtime`
- `thirdparty`

Heuristics:

- shared application strings imply a module
- call-graph neighborhoods imply a module
- platform/process/network/CLI code should not be mixed with session logic
- compiler/runtime support should be isolated from application logic

Keep address provenance in docs even after grouping.

## Phase 4: Mechanical Renaming and Annotation

Goal: reduce noise before semantic cleanup.

If project scripts already exist, reuse them only if they are not hardcoded to one project layout. Otherwise prefer the generic scripts bundled with this skill:

- `scripts/apply_mapping.py`
- `scripts/add_address_comments.py`
- `scripts/literal_diff.py`

Recommended order:

1. copy raw decompiled files into a clean tree
2. rename files from address-based names to module-level names when confident
3. rename entry functions
4. add original address comments
5. rename high-frequency helpers only after multiple call sites confirm the meaning

Important:

- do not rename uncertain helpers too early
- keep original-address comments in cleaned files
- preserve a mapping document or script so the rename pass is reproducible

Read [references/mapping-format.md](references/mapping-format.md) before running the bundled scripts.

### Comparing Raw vs Clean

After renaming, use `literal_diff.py` with the `--mapping` option to compare files across directories:

```bash
# After Phase 4 renaming, files have different names in raw/ and src/
# Use the mapping file to correlate them:
python3 scripts/literal_diff.py \
  --left-root phase2 \
  --right-root clean/src \
  --mapping mapping.tsv
```

Without `--mapping`, the script matches files by relative path (original behavior), which only works if file names are the same in both trees.

## Phase 5: AI Cleanup To Equivalent Readable C

Goal: turn raw decompiler output into readable, equivalent C without losing behavior.

Read [references/cleanup-phase.md](references/cleanup-phase.md) before doing large cleanup work.

Cleanup order inside one module:

1. identify the root function and direct state transitions
2. isolate opaque helpers with narrow semantic names
3. split giant functions into readable stages
4. keep raw constants, status codes, event names, and table data visible
5. move compiler/runtime junk behind wrappers or out of the application module

### What To Preserve

Always preserve or explicitly re-home:

- status/event strings
- error-code mappings
- callback types
- configuration key names
- environment variable names
- CLI option names/help strings
- table-driven converters
- protocol verbs and message names
- session / license / startup / teardown state transitions

### What To Be Careful About

The most common cleanup failure is this:

- control flow becomes prettier
- but strings/tables/state branches disappear

Whenever a cleaned file becomes much smaller than the raw one, compare:

- string count
- file size
- key literal presence
- error/status code coverage

If the file is a converter or table-heavy module, prefer preserving the original table contents.

---

## Batch Size Rules

Use these as defaults:

- 1 main module per pass
- 1-3 root files plus a few direct helpers
- if a module is huge, split by sub-flow

Good examples:

- startup + config bootstrap
- session core only
- metadata loader only
- launch + teardown only
- config/service only

Bad examples:

- all `src/**/*.c`
- all session + launch + storage + config in one prompt
- all helper renames globally before module analysis

## Review Standard

When reviewing cleaned reverse-engineered code, prioritize:

1. missing logic
2. missing strings or tables
3. merged branches that should stay separate
4. wrong helper boundaries
5. hidden side effects

Do not declare a module “done” just because it reads better.

## Definition Of Done

Do not stop at Phase 4.

A cleaned reverse-engineering pass counts as done only when all of the following are true:

- `clean/src/` is no longer raw decompiler output with only renamed files/functions.
- The main flow is readable in staged logic, with variable names that reflect behavior.
- Important literals, option names, state branches, and error paths are still present or explicitly re-homed.
- Raw outputs remain preserved in a backup tree.
- A post-cleanup comparison has been run and any reported gaps have been reviewed.

## Minimal End-To-End Playbook

1. Check prerequisites (tools installed, r2ghidra working).
2. Identify the binary (file type). Load platform reference (PE/ELF) and language reference (C++ if applicable).
3. **C++ only**: Follow RTTI/type recovery steps in [references/cpp-handling.md](references/cpp-handling.md).
4. **Configure scope** — ask user: application code only (default) or full binary?
5. Analyze and classify functions — separate library/runtime from application code.
6. Create a phased workspace.
7. Export raw C for application functions only (from the classification).
8. Form modules (or use small binary fast-track).
9. Copy raw outputs into a clean tree and keep a raw backup tree.
10. Apply reproducible rename scripts.
11. Clean one module at a time into readable C.
12. Compare cleaned files against raw backups for missing strings/tables/branches.
13. Update docs, findings, and progress after each module.
14. Only then move to the next module.

## Completion Criteria

A module is complete when:

- its main flow is readable
- raw backups still exist
- original addresses remain traceable
- key strings/tables/codes are preserved
- helper names match real semantics
- no known critical branches were dropped during abstraction
