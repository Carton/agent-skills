---
name: reverse-to-readable-c
description: End-to-end workflow for reversing native binaries into organized, readable C code using phased analysis, radare2, r2ghidra, optional Ghidra, per-module batching, structured renaming, and AI-assisted cleanup. Use when the task is to explore a PE or ELF binary, identify modules, decompile functions into initial C, reorganize outputs into a better directory layout, rename files/functions, and iteratively convert decompiler output into equivalent readable C without overflowing context.
---

# Reverse To Readable C

Use this skill for full reverse-engineering projects where the goal is not just to inspect a binary, but to produce a maintainable source tree from it.

The workflow is phase-based and aggressively context-limited. Never try to load the whole reverse-engineering output at once.

## Prerequisites Check

**Before starting**, verify that required tools are installed:

```bash
#!/bin/bash
# Tool check script - save as check_tools.sh

check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 not found"
        return 1
    else
        echo "✓ $1 installed: $(which $1)"
        return 0
    fi
}

echo "=== Required Tools ==="
check_tool r2 || { echo "Please install radare2 first"; exit 1; }
check_tool file || { echo "Please install file command first"; exit 1; }
check_tool python3 || { echo "Please install python3 first"; exit 1; }

echo ""
echo "=== Optional Tools ==="
check_tool jq || echo "⚠️  jq not installed (recommended for JSON processing)"
check_tool strings || echo "⚠️  strings not installed (part of binutils)"

echo ""
echo "=== r2ghidra Decompiler Check ==="
R2_VERSION=$(r2 -v | head -1 | awk '{print $2}')
echo "radare2 version: $R2_VERSION"

# Check if r2ghidra plugin is compiled
if [ -f ~/.local/share/radare2/r2pm/git/r2ghidra/src/core_ghidra.so ]; then
    echo "✓ r2ghidra plugin compiled"
else
    echo "❌ r2ghidra plugin not compiled"
    echo "Run: cd ~/.local/share/radare2/r2pm/git/r2ghidra && make && sudo make install"
fi

# Create test file to verify decompilation
echo "int main() { return 0; }" > /tmp/test_r2.c
gcc /tmp/test_r2.c -o /tmp/test_r2 2>/dev/null
if r2 -q -c "aaa; pdg @ main" /tmp/test_r2 &> /dev/null; then
    echo "✓ r2ghidra decompilation works"
else
    echo "❌ r2ghidra decompilation not working"
fi
rm -f /tmp/test_r2.c /tmp/test_r2
```

**Quick check** (one-liner):
```bash
check_tools() { which r2 && which file && which python3 && r2 -v | head -1; }; check_tools && echo "✓ Basic tools OK"
```

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
├── docs/                     # findings, indexes, architecture notes
├── phase1/                   # exploratory analysis and reports
├── phase2/                   # raw per-function decompilation output
├── phase3/                   # secondary helper/support decompilation output
├── phase4/                   # extra passes / delayed helper recovery
├── clean/
│   ├── raw/                  # raw backup copied from phased outputs
│   └── src/                  # current readable tree
└── scripts/                  # rename / annotation helpers
```

If the repository already has a structure, preserve it and fit the workflow into it.

## Linux Tooling Setup

Assume a Linux execution environment. Install a minimal baseline first, then add optional tools by target type.

### Minimal Baseline

Use the system package manager for core tooling:

```bash
sudo apt update
sudo apt install -y \
  build-essential pkg-config git patch curl unzip zip \
  python3 python3-pip file jq \
  gdb binutils strace ltrace \
  radare2
```

If your distribution splits headers into a separate package, install the radare2 development package too before building plugins.

Initialize and update `r2pm`, then install and compile `r2ghidra`:

```bash
# 1. Download r2ghidra source
r2pm init || true
r2pm -U
r2pm -ci r2ghidra

# 2. Build and install (IMPORTANT: must be done manually)
cd ~/.local/share/radare2/r2pm/git/r2ghidra
make
sudo make install

# 3. Verify installation
r2 -q -c "pdg --help" # requires a file to be opened, see verification below
```

### Optional & Target-Specific Tools

Depending on your target, you may need additional tools:

- **Analysis/Validation**: `ghidra` (highly recommended for validation and headless analysis)
- **Target Observation**: `wine` (for PE), `apktool` (for Android)
- **Unpacking/Utilities**: `upx`, `p7zip-full`, `cabextract`
- **Multi-arch Debugging**: `gdb-multiarch`

For detailed installation steps and troubleshooting, see [references/install-linux.md](references/install-linux.md).

### Verify Installation

Verify that the toolchain works correctly:

```bash
# Create test binary
echo 'int main() { return 0; }' > /tmp/test_r2.c
gcc /tmp/test_r2.c -o /tmp/test_r2 2>/dev/null

# Test radare2 basic functionality
r2 -q -c "aaa; afl" /tmp/test_r2 && echo "✓ radare2 analysis works"

# Test r2ghidra decompilation
r2 -q -c "pdg @ main" /tmp/test_r2 && echo "✓ r2ghidra decompilation works"

# Cleanup
rm -f /tmp/test_r2.c /tmp/test_r2
```

**Checklist**:
- [ ] `which r2` - radare2 executable exists
- [ ] `r2 -v` - shows version info
- [ ] `which file` - file command available
- [ ] `ls ~/.local/share/radare2/r2pm/git/r2ghidra/src/*.so` - r2ghidra compiled
- [ ] `r2 -q -c "pdg @ main" <binary>` - decompilation works

---

## Phase 1: Exploratory Analysis

Goal: identify the binary shape, main entry chain, probable modules, and the first 20-50 functions worth tracking.

### Binary Identification

Start with basic file info and string survey:

```bash
file ./target_binary
strings ./target_binary | grep -iE "(usage|error|main|version|help|\.pdb|\.cpp)" | head -30
```

Check for debug build indicators:

- Stack cookie pattern: `0xcccccccc` fill values in decompiled output
- PDB path strings: `D:\...\xxx.pdb`
- Mangled C++ symbols with debug info (e.g. `MSVCP140D.dll`, `ucrtbased.dll`)
- Source file path strings in `.rdata`

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
# Find usage/help strings
iz~Usage
iz~help
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

Prefer `r2ghidra` through radare2 when available:

```bash
# Open binary once with full analysis
r2 -q -e bin.relocs.apply=true -c "aaa; pdg @ fcn.1400010a0" ./target_binary
```

> **Note**: Use `aaa` (lowercase), not `-A`. See Phase 1 for details.

### Handling ANSI Color Codes

`pdg` output contains ANSI escape codes by default. Strip them when saving to files:

```bash
# Method 1: use r2 -- option (disables colors)
r2 -- -q -e bin.relocs.apply=true -c "aaa; pdg @ fcn.1400010a0" ./target_binary > phase2/func_0x1400010a0.c

# Method 2: pipe through sed
r2 -q -e bin.relocs.apply=true -c "aaa; pdg @ fcn.1400010a0" ./target_binary | sed 's/\x1b\[[0-9;]*m//g' > phase2/func_0x1400010a0.c
```

### C++ Binary Noise

C++ binaries (especially MSVC debug builds) produce very large decompiled output due to:

- STL container inline expansion (`std::string`, `std::vector`, `std::filesystem::path`)
- Exception handling frames (`__CxxFrameHandler4`, cookie checks)
- Debug stack initialization (`0xcccccccc` fill loops)
- Template instantiation noise

For C++ targets, consider:

1. **Identify runtime vs business logic**: Mark functions that only call `MSVCP140D.dll` / `ucrtbased.dll` as runtime helpers early.
2. **Focus on call-graph roots**: Start from functions that reference application strings, not from every function.
3. **Batch-export selectively**: Only decompile functions that are 1-2 calls away from a business-critical root.

See [C++ Binary Handling](#c-binary-handling) for detailed strategies.

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

## C++ Binary Handling

C++ binaries require extra care due to template expansion, STL inlining, and name mangling.

### Identifying C++ Binaries

Signs of a C++ binary:

- Imported DLLs: `MSVCP140[D].dll`, `VCRUNTIME140[D].dll`, `ucrtbase[d].dll`
- Mangled imports: `__CxxThrowException`, `__std_exception_destroy`, `??1...`
- Source path strings from C++ headers: `<charconv>`, `<filesystem>`, `<xmemory>`, `<xlocale>`

### MSVC Debug Build Artifacts

Debug builds add significant noise:

- **Stack cookie init loops**: `for (iVar = 0xNN; iVar != 0; iVar = iVar + -1) { *ptr = 0xcccccccc; }`
- **Security cookie checks**: `uStack_10 = *0x140044040 ^ auStack_d8;` at function entry, `fcn.14000188e(uStack_10 ^ auStack_d8);` at exit
- **Local variable names**: `auStack_XXX`, `iStack_XXX`, `puVarN`, `cVar1` (decompiler-generated)

### Cleanup Strategy for C++

1. **Strip security cookie boilerplate**: Remove init-loops and cookie-check calls at function boundaries — they are compiler-generated, not business logic.
2. **Collapse STL wrappers**: Functions that only construct/destroy `std::string`, `std::vector`, `std::filesystem::path` can be replaced with a comment: `// std::string path_str(path_arg)`.
3. **Recover semantics from mangled names**: Use `afl` and `izz` to map mangled import names to their actual purpose before renaming.
4. **Preserve C++ idioms**: Keep `std::filesystem::path` operations as-is rather than expanding them into raw struct manipulation.

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

## Minimal End-To-End Playbook

1. Analyze the binary and identify roots.
2. Create a phased workspace.
3. Export raw C for a small address set.
4. Form modules.
5. Copy raw outputs into a clean tree and keep a raw backup tree.
6. Apply reproducible rename scripts.
7. Clean one module at a time into readable C.
8. Compare cleaned files against raw backups for missing strings/tables/branches.
9. Update docs, findings, and progress after each module.
10. Only then move to the next module.

## Completion Criteria

A module is complete when:

- its main flow is readable
- raw backups still exist
- original addresses remain traceable
- key strings/tables/codes are preserved
- helper names match real semantics
- no known critical branches were dropped during abstraction
