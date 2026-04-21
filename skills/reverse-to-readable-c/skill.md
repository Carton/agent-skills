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

## Mandatory Deliverables [READ FIRST]

Every reverse engineering project using this skill MUST produce the following outputs:

### 1. Phase 1 Output (Required before Phase 2)
- **`phase1/function_classification.md`**
  - Function categorization (imported vs application)
  - Application function listing with addresses
  - Module grouping
  - Binary statistics

### 2. Phase 4 Output (Required before Phase 5)
- **`clean/raw/` directory** - Renamed and reorganized RAW decompiler output
- **`clean/src/` directory** - Same structure as raw/, will contain cleaned code
- **`mapping.tsv`** - File/function rename mapping
- **Structure verification**: Both trees must have identical filenames and directories

### 3. Phase 5 Output (Required for completion)
- **`scripts/verify_cleanup.sh`** - Automated cleanup verification script
- **All files in `clean/src/` cleaned** - Must differ from `clean/raw/`
- **Verification passing**: `./scripts/verify_cleanup.sh` must pass with "ALL CHECKS PASSED"
- **`docs/project_summary.md`** - Comprehensive project summary

### Quality Gates
You MUST NOT proceed to the next phase until:
- **Phase 1 → 2**: `phase1/function_classification.md` exists and is complete
- **Phase 4 → 5**: Both `clean/raw/` and `clean/src/` have identical structure
- **Phase 5 → Done**: `./scripts/verify_cleanup.sh` passes AND `docs/project_summary.md` exists

**Verification Checklist** (at project end):
- [ ] `phase1/function_classification.md` exists
- [ ] `clean/raw/` and `clean/src/` have identical structure
- [ ] `scripts/verify_cleanup.sh` exists and passes
- [ ] `docs/project_summary.md` exists
- [ ] All files in `clean/src/` are cleaned (verified by script)

---

## Principles

- Preserve originals. Raw outputs must remain available for diffing.
- Work one module at a time.
- Keep addresses stable until a module is understood.
- Rename in layers: files first, entry functions second, shared helpers later.
- Treat decompiled C as an intermediate artifact, not the final output.
- Do not abstract tables, strings, callbacks, or ownership/state logic away without checking the raw source again.

## Workflow Tracking (Mandatory)

To ensure stability and prevent redundant analysis in complex binary reversing, you MUST maintain a `progress.md` file in the project root. This is your "disk-based memory."

### 1. Initialize `progress.md`
Before Phase 1, create the file with this structure:
- **Project Goal**: (e.g., Reverse `crackme.exe` logic)
- **Current Phase**: (Phase 1/2/3/4/5)
- **Functions Analysed**: [Address] | [Raw Name] | [Clean Name] | [Status: Raw/Renamed/Cleaned]
- **Next Steps**: (Specific next 3 functions or tasks)

### 2. The "Update-Before-Act" Rule
- **Before** decompiling a new function: Check `progress.md` to see if it's already done.
- **After** decompiling/cleaning a function: IMMEDIATELY update its status in `progress.md`.
- **Phase Transition**: When moving from Phase 2 to 3, update the "Current Phase" and log the discovery of new modules.

### 3. Context Recovery
If the session length becomes excessive or you feel lost:
1. Stop all analysis.
2. Read `progress.md` and `mapping.tsv`.
3. Re-orient based on the "Next Steps" section.

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
│   └── project_summary.md    # [Phase 5] MANDATORY: Final project summary
├── phase1/                   # [Phase 1] exploratory analysis and reports
│   └── function_classification.md  # [Phase 1] MANDATORY: Function classification document
├── phase2/                   # [Phase 2] raw per-function decompilation output
├── clean/
│   ├── raw/                  # [Phase 4] Renamed + reorganized RAW decompiled code
│   │                         # IMPORTANT: Same filenames/structure as src/, but RAW content
│   └── src/                  # [Phase 4→5] Cleaned, readable source code
│   │                         # Same filenames/structure as raw/, but CLEANED content
├── scripts/                  # [Phase 4] Rename / annotation helpers
│   └── verify_cleanup.sh     # [Phase 5] MANDATORY: Cleanup verification script
└── mapping.tsv               # [Phase 4] File/function rename mapping
```

**CRITICAL**: The `clean/raw/` and `clean/src/` directories MUST have:
- **Identical directory structure**
- **Identical filenames**
- **Different content**: raw/ contains original decompiler output, src/ contains cleaned code

This design enables:
1. Easy comparison between raw and cleaned versions
2. Verification that no files were missed during cleanup
3. Detection of over-aggressive cleanup (files that became too small)

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

### Binary Identification [MANDATORY]

Start with basic file info and string survey:

```bash
file ./target_binary
strings ./target_binary | grep -iE "(usage|error|main|version|help|\.pdb|\.cpp)" | head -30
```

**Then load the platform-specific reference:**
**Do not skip this step even if you have general knowledge of the platform.**

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

### What to Produce [MANDATORY OUTPUTS]

You MUST generate the following documentation before proceeding to Phase 2:

1. **`phase1/function_classification.md`** [MANDATORY]
   - Function classification document
   - Separate imported functions from application code
   - List all application functions with addresses and likely roles
   - Document module groupings
   - Include statistics (total functions, imports, locals, application code)

   Template:
   ```markdown
   # Function Classification for <binary_name>

   ## Binary Overview
   - Type: ELF/PE, architecture, stripped/unstripped
   - Total Functions: N
   - Imported Functions: N
   - Local Functions: N
   - Application Functions: N

   ## Function Categories

   ### 1. Application Core (N functions)
   ### 2. CLI/Option Parsing (N functions)
   ### 3. I/O Operations (N functions)
   ### ...etc

   ## Module Map
   ## Application Functions Table
   ## Scope Configuration
   ## Next Steps
   ```

2. **Entry chain note** - How execution flows from entry point to main
3. **Module map** - First-pass grouping of functions into modules
4. **Function index** - All functions sorted by address with purpose
5. **Risk list** - Security-sensitive areas (parsers, auth, networking, etc.)

**DO NOT proceed to Phase 2 until `phase1/function_classification.md` is complete.**

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

Goal: reduce noise before semantic cleanup by organizing code into modules and applying meaningful names.

### Critical: Understanding raw/ vs src/

**IMPORTANT**: This phase creates TWO trees with IDENTICAL structure but DIFFERENT content:

1. **`clean/raw/`** - Renamed and reorganized RAW decompiler output
   - Same filenames and directory structure as `src/`
   - Contains ORIGINAL decompiler output (with all warnings, ugly variable names, etc.)
   - Purpose: Baseline for comparison and verification

2. **`clean/src/`** - Target for cleaned code (Phase 5)
   - Same filenames and directory structure as `raw/`
   - Will contain READABLE cleaned code after Phase 5
   - Purpose: Final maintainable source code

**Why this separation matters**:
- Prevents accidental overwriting of raw baseline
- Enables automated verification of cleanup completeness
- Makes it easy to spot over-aggressive cleanup (file size too small)

### Step-by-Step Process

#### Step 1: Create module directories in both raw/ and src/

```bash
# Create identical directory structure in both trees
mkdir -p clean/raw/{core,cli,io,convert,stats,utils}
mkdir -p clean/src/{core,cli,io,convert,stats,utils}
```

#### Step 2: Copy and rename files to BOTH trees

```bash
# For each function, copy to BOTH raw/ and src/ with the new name
# Example: Copy main function
cp phase2/func_0x00002990_main.c clean/raw/core/main.c
cp phase2/func_0x00002990_main.c clean/src/core/main.c

# Example: Copy usage helper
cp phase2/func_fcn.00004b50.c clean/raw/cli/usage_helper.c
cp phase2/func_fcn.00004b50.c clean/src/cli/usage_helper.c
```

**CRITICAL**: Every file MUST be copied to BOTH trees:
- `clean/raw/<module>/<name>.c` - Original decompiler output
- `clean/src/<module>/<name>.c` - Will be cleaned in Phase 5

#### Step 3: Create mapping.tsv

Create a TSV file documenting all renames:

```tsv
# Format: address	original_name	clean_name	module
0x00002990	main	main	core
0x00004b50	fcn.00004b50	usage_helper	cli
0x00005130	fcn.00005130	io_handler	io
...
```

This mapping is essential for:
- Reproducibility
- Understanding the provenance of each file
- Cross-referencing with original addresses

#### Step 4: Verify directory structure matches

```bash
# Verify both trees have the same structure
diff -q <(cd clean/raw && find . -type f | sort) \
         <(cd clean/src && find . -type f | sort)

# Should output nothing if structures match
```

### What NOT to do in Phase 4

- DO NOT modify the content of files in `clean/raw/` (keep them pristine)
- DO NOT yet clean files in `clean/src/` (that's Phase 5)
- DO NOT skip creating both trees
- DO NOT use different filenames in raw/ vs src/

### Using Bundled Scripts (Optional)

If project scripts exist and are generic, you may reuse:
- `scripts/apply_mapping.py` - Apply renaming from mapping.tsv
- `scripts/add_address_comments.py` - Add original address comments

Read [references/mapping-format.md](references/mapping-format.md) before using these scripts.

### Verification Checklist

Before proceeding to Phase 5, verify:

- [ ] `clean/raw/` and `clean/src/` have identical directory structure
- [ ] `clean/raw/` and `clean/src/` have identical filenames
- [ ] All files in `clean/raw/` are original decompiler output
- [ ] All files in `clean/src/` are copies (not yet cleaned)
- [ ] `mapping.tsv` documents all renames
- [ ] File count matches: `ls clean/raw/**/*.c | wc -l` == `ls clean/src/**/*.c | wc -l`

## Phase 5: AI Cleanup To Equivalent Readable C

Goal: turn raw decompiler output into readable, equivalent C without losing behavior.

**CRITICAL REQUIREMENT**: This phase MUST include automated verification to ensure ALL files are cleaned. Do NOT rely on manual inspection or AI self-reporting.

### Step 1: Create verification script [MANDATORY]

Before starting cleanup, create `scripts/verify_cleanup.sh`:

```bash
#!/bin/bash
# verify_cleanup.sh - Verify that all files in src/ have been cleaned
#
# This script compares clean/raw/ (original decompiler output) with
# clean/src/ (cleaned code) to ensure:
# 1. All files exist in both trees
# 2. Files in src/ are actually cleaned (different from raw/)
# 3. Files in src/ are not over-aggressively cleaned (not too small)

set -e

RAW_DIR="clean/raw"
SRC_DIR="clean/src"

echo "=== Cleanup Verification ==="
echo ""

# Check 1: Verify directory structures match
echo "Check 1: Verifying directory structures match..."
DIFF_OUTPUT=$(diff -q <(cd "$RAW_DIR" && find . -type f | sort) \
                      <(cd "$SRC_DIR" && find . -type f | sort) || true)
if [ -n "$DIFF_OUTPUT" ]; then
    echo "❌ FAIL: Directory structures do not match:"
    echo "$DIFF_OUTPUT"
    exit 1
fi
echo "✅ PASS: Directory structures match"
echo ""

# Check 2: Count files
echo "Check 2: Counting files..."
RAW_COUNT=$(find "$RAW_DIR" -name "*.c" | wc -l)
SRC_COUNT=$(find "$SRC_DIR" -name "*.c" | wc -l)
echo "  raw/ files: $RAW_COUNT"
echo "  src/ files: $SRC_COUNT"

if [ "$RAW_COUNT" -ne "$SRC_COUNT" ]; then
    echo "❌ FAIL: File count mismatch"
    exit 1
fi
echo "✅ PASS: File counts match ($RAW_COUNT files)"
echo ""

# Check 3: Verify each file is cleaned (different from raw)
echo "Check 3: Verifying files are actually cleaned..."
UNCLEAN_COUNT=0
TOTAL_SIZE_DIFF=0

while IFS= read -r -d '' RAW_FILE; do
    # Get relative path
    REL_PATH="${RAW_FILE#$RAW_DIR/}"
    SRC_FILE="$SRC_DIR/$REL_PATH"

    if [ ! -f "$SRC_FILE" ]; then
        echo "❌ FAIL: Missing in src/: $REL_PATH"
        exit 1
    fi

    # Check if files are identical (not cleaned)
    if cmp -s "$RAW_FILE" "$SRC_FILE"; then
        echo "⚠️  UNCLEANED: $REL_PATH"
        ((UNCLEAN_COUNT++))
    else
        # Files are different, check size difference
        RAW_SIZE=$(stat -c%s "$RAW_FILE")
        SRC_SIZE=$(stat -c%s "$SRC_FILE")
        SIZE_DIFF=$((RAW_SIZE - SRC_SIZE))
        TOTAL_SIZE_DIFF=$((TOTAL_SIZE_DIFF + SIZE_DIFF))

        # Warn if cleaned file is suspiciously small (< 30% of raw)
        SIZE_PERCENT=$((SRC_SIZE * 100 / RAW_SIZE))
        if [ "$SIZE_PERCENT" -lt 30 ]; then
            echo "⚠️  WARNING: $REL_PATH reduced to ${SIZE_PERCENT}% of original size"
            echo "    Raw: $RAW_SIZE bytes, Cleaned: $SRC_SIZE bytes"
        fi
    fi
done < <(find "$RAW_DIR" -name "*.c" -print0)

echo ""
if [ "$UNCLEAN_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $UNCLEAN_COUNT file(s) not yet cleaned"
    echo ""
    echo "Uncleaned files:"
    while IFS= read -r -d '' RAW_FILE; do
        REL_PATH="${RAW_FILE#$RAW_DIR/}"
        SRC_FILE="$SRC_DIR/$REL_PATH"
        if cmp -s "$RAW_FILE" "$SRC_FILE"; then
            echo "  - $REL_PATH"
        fi
    done < <(find "$RAW_DIR" -name "*.c" -print0)
    exit 1
fi

echo "✅ PASS: All files are cleaned (different from raw)"
echo ""

# Summary statistics
echo "=== Cleanup Summary ==="
echo "Total files: $RAW_COUNT"
echo "Total size reduction: $TOTAL_SIZE_DIFF bytes"
echo "Average reduction per file: $((TOTAL_SIZE_DIFF / RAW_COUNT)) bytes"
echo ""
echo "✅ ALL CHECKS PASSED - Cleanup is complete!"
exit 0
```

Make it executable:
```bash
chmod +x scripts/verify_cleanup.sh
```

### Step 2: Clean files module by module

Read [references/cleanup-phase.md](references/cleanup-phase.md) before doing large cleanup work.

Cleanup order inside one module:

1. identify the root function and direct state transitions
2. isolate opaque helpers with narrow semantic names
3. split giant functions into readable stages
4. keep raw constants, status codes, event names, and table data visible
5. move compiler/runtime junk behind wrappers or out of the application module

**IMPORTANT**: Clean files in `clean/src/` ONLY. Never modify files in `clean/raw/`.

### Step 3: Verify cleanup completeness [MANDATORY]

After cleaning, ALWAYS run the verification script:

```bash
./scripts/verify_cleanup.sh
```

**Expected outcomes**:

1. **If cleanup is complete**:
   ```
   ✅ PASS: Directory structures match
   ✅ PASS: File counts match (31 files)
   ✅ PASS: All files are cleaned (different from raw)
   ✅ ALL CHECKS PASSED - Cleanup is complete!
   ```

2. **If files are not cleaned**:
   ```
   ⚠️  UNCLEANED: cli/usage_helper.c
   ⚠️  UNCLEANED: core/main.c
   ❌ FAIL: 2 file(s) not yet cleaned
   ```
   → **Action required**: Clean the remaining files and re-run verification

3. **If over-aggressive cleanup**:
   ```
   ⚠️  WARNING: cli/usage_helper.c reduced to 15% of original size
       Raw: 8500 bytes, Cleaned: 1275 bytes
   ```
   → **Action required**: Review the file for missing content

### Step 4: Iterate until complete

**CRITICAL**: Do NOT consider Phase 5 complete until the verification script passes:

```bash
# Loop: Clean → Verify → Fix issues → Verify
until ./scripts/verify_cleanup.sh; do
    echo "Some files still need cleaning. Continuing..."
    # Clean the remaining files
done

echo "Phase 5 cleanup complete!"
```

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

### Definition Of Done (Phase 5)

Phase 5 is complete ONLY when ALL of the following are true:

- [ ] `./scripts/verify_cleanup.sh` passes with "ALL CHECKS PASSED"
- [ ] `clean/src/` is no longer raw decompiler output
- [ ] Main flows are readable in staged logic
- [ ] Variable names reflect behavior
- [ ] Important literals, option names, state branches, and error paths are preserved
- [ ] Raw outputs remain preserved in `clean/raw/`
- [ ] No suspicious file size reductions (< 30% of original)
- [ ] **`docs/project_summary.md` has been generated** [MANDATORY]

### Generate Project Summary [MANDATORY]

After Phase 5 is complete and verified, you MUST generate `docs/project_summary.md`:

```bash
# Create docs directory if it doesn't exist
mkdir -p docs

# Generate comprehensive project summary
cat > docs/project_summary.md << 'EOF'
# <Project Name> Reverse Engineering Project Summary

## Project Overview
[Brief description of what was reverse engineered]

## Binary Information
- **File**: <path_to_binary>
- **Type**: ELF/PE, architecture, stripped/unstripped
- **Total Functions**: N
- **Application Functions**: N
- **Modules**: N

## Analysis Workflow
### Phase 1: Exploratory Analysis
[Summary of findings]

### Phase 2: Decompilation
[Number of functions decompiled]

### Phase 3: Module Formation
[Modules identified and their purposes]

### Phase 4: Renaming and Organization
[How functions were organized]

### Phase 5: AI Cleanup
[Cleanup approach and results]

## Architecture
[High-level architecture description]

## Module Overview
### Module 1: <name>
- Purpose
- Key functions
- Responsibilities

### Module 2: <name>
...

## Key Findings
[Important discoveries about the binary]

## Statistics
- Total files: N
- Total lines of code: ~N
- Modules: N
- Cleanup reduction: X%

## Deliverables
1. phase1/function_classification.md
2. clean/raw/ - Original decompiled code (renamed)
3. clean/src/ - Cleaned source code
4. scripts/verify_cleanup.sh
5. mapping.tsv
6. docs/project_summary.md

## Quality Assurance
- All files verified by verify_cleanup.sh
- No missing strings or logic
- All original behavior preserved

## Conclusion
[Summary of project completion]
EOF
```

The project summary MUST include:
1. Binary information and statistics
2. Phase-by-phase summary of work done
3. Architecture overview
4. Module descriptions
5. Key findings
6. Deliverables checklist
7. Quality assurance results

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
6. **Generate `phase1/function_classification.md`** [MANDATORY].
7. Create a phased workspace with `clean/raw/` and `clean/src/` directories.
8. Export raw C for application functions only (from the classification).
9. Form modules (or use small binary fast-track).
10. **Copy files to BOTH `clean/raw/` and `clean/src/`** with renamed filenames.
11. **Verify both trees have identical structure** (same directories, same filenames).
12. Create `mapping.tsv` documenting all renames.
13. Create `scripts/verify_cleanup.sh` verification script.
14. Clean one module at a time in `clean/src/` ONLY.
15. **Run `./scripts/verify_cleanup.sh` after each cleanup batch**.
16. **Iterate until verification passes completely**.
17. **Generate `docs/project_summary.md`** [MANDATORY].
18. Final verification: All MANDATORY outputs present.

## Completion Criteria

A module is complete when:

- its main flow is readable
- raw backups still exist
- original addresses remain traceable
- key strings/tables/codes are preserved
- helper names match real semantics
- no known critical branches were dropped during abstraction
