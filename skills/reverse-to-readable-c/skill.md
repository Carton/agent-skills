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

### PDB / Debug Symbols

If the binary contains debug information (PDB path in strings or `.debug` sections), leverage it for better analysis:

**Check for PDB availability:**
```bash
# Check if PDB path is embedded in the PE
strings ./target_binary | grep -i "\.pdb"

# In r2, check debug info
r2 -q -c "i~pdb" ./target_binary
```

**PDB handling strategies:**

| Scenario | Approach |
|----------|----------|
| PDB file available locally | Load it into r2 or Ghidra for rich symbol names, types, and source lines |
| PDB path points to Microsoft Symbol Server | Use `e pdb.autoload=true` in r2 to auto-download |
| PDB is a local debug build (not published) | PDB path is informational only; proceed without PDB but use other debug indicators |
| No PDB / stripped binary | Standard workflow — recover names from strings and call-graph analysis |

**Loading PDB in radare2:**
```bash
# If PDB file is available locally
r2 -q -e pdb.autoload=true -c "aaa" ./target_binary

# PDB provides: function names, variable names, type info, source line mapping
# Check loaded symbols
r2 -q -c "aaa; is~main" ./target_binary
```

**Loading PDB in Ghidra:**
- GUI: `File → Parse PDB...` → select `.pdb` file
- Headless: Ghidra's `PdbUniversalAnalyzer` runs automatically during import if PDB is found alongside the binary or via Symbol Server configuration
- Configure Symbol Server path in Ghidra: `Edit → Tool Options → Symbol Server Path`

PDB symbols dramatically improve decompilation quality — function names, parameter types, and local variable names replace decompiler-generated names like `fcn.1400010a0` and `auStack_XXX`.

### C++ RTTI / Type Recovery

**For C++ binaries only.** If the binary was identified as C++ (see [Identifying C++ Binaries](#identifying-c-binaries)), perform type recovery **before** decompilation. Recovered type information helps the decompiler produce more accurate output — function parameters get real types instead of `int`, virtual dispatch is correctly resolved, and `std::` container usage patterns become recognizable.

**Why before decompilation:** RTTI is objective metadata embedded by the compiler. Feeding it to the decompiler early means all subsequent decompilation benefits from correct type information. This reduces the "STL noise" problem where `std::vector::push_back` calls appear as anonymous `fcn.XXXX` invocations.

#### Option A: Ghidra Headless (recommended)

Ghidra's built-in `RecoverClassesFromRTTIScript` recovers class names, vtables, and inheritance hierarchies from MSVC RTTI structures. Requires Ghidra 9.2+.

```bash
# Run RTTI recovery headless (no GUI needed)
<path_to_ghidra>/support/analyzeHeadless /tmp/ghidra_rtti ProjectName \
    -import ./target_binary \
    -postScript RecoverClassesFromRTTIScript.java \
    -deleteProject
```

This populates Ghidra's Data Type Manager with recovered class structures. To use these types in subsequent r2 analysis, export the recovered type information (e.g., as a C header) and reference it during manual cleanup.

**Known limitations:**
- Virtual inheritance may produce incorrect `vbtablePtr` placement
- Cross-DLL RTTI recovery is limited
- Only polymorphic types (classes with at least one `virtual` function) have RTTI

#### Option B: radare2 Built-in (basic)

r2 has built-in vtable and RTTI analysis commands — less comprehensive than Ghidra but requires no additional tools:

```bash
# Set ABI to MSVC, then search for vtables with RTTI resolution
r2 -q -e bin.relocs.apply=true -c "aaa; e anal.cpp.abi=msvc; avra" ./target_binary
```

- `av` — search data sections for vtables
- `avr @ addr` — attempt RTTI resolution at a specific vtable address
- `avra` — search all vtables and attempt RTTI resolution for each

**Limitation**: r2's MSVC RTTI support recovers class names and vtable addresses but does not rebuild full class hierarchies or member layouts.

#### What RTTI Recovery Produces

| Artifact | Use in Reverse Engineering |
|----------|---------------------------|
| Class names (demangled) | Replace `fcn.XXXX` with meaningful names like `std::filesystem::path` |
| vtable addresses | Identify virtual dispatch; distinguish method calls from function pointer calls |
| Inheritance hierarchies | Understand class relationships; identify base class methods in derived classes |
| Member offsets (approximate) | Understand data layout of `this` pointer usage in decompiled output |

#### Manual RTTI Inspection (fallback)

If automated tools are unavailable, RTTI structures can be found manually in MSVC binaries:

1. Search `.rdata` for class name strings: `.?AV` (classes with virtual functions), `.?AU` (non-virtual classes)
2. Cross-reference backward from `TypeDescriptor` to find `RTTICompleteObjectLocator`
3. Follow the locator chain:

```
vftable[-1] → RTTICompleteObjectLocator → TypeDescriptor (class name)
                                            → ClassHierarchyDescriptor → BaseClassArray
                                                                       → BaseClassDescriptor[] (inheritance)
```

> **Note**: RTTI is only generated for **polymorphic types** (classes with at least one `virtual` function). Non-polymorphic types and most STL internal types will not have RTTI. For C++ binaries with RTTI disabled (`/GR-`), this step produces no results — proceed with standard decompilation.

### Scope Configuration

**Before diving into analysis**, confirm the reverse-engineering scope with the user:

Ask the user these questions:

- If your environment provides a structured question tool, use it.
- If it does not, ask in a normal message.
- If the user does not specify scope, default to **application code only**.

1. **Reverse-engineering scope** (default: **application code only**):
   - **Application code only** (recommended) — Focus on custom business logic. Exclude standard library, runtime, and third-party library code.
   - **Application + uncertain functions** — Also include functions whose origin is unclear (e.g., no clear library signature).
   - **Full binary** — Reverse everything, including all runtime and library wrapper code.

2. **Is a PDB file available?** — If yes, use it to get symbol names and types automatically.

3. **Is this a debug or release build?** — Debug builds have more noise but also more information.

> **Default behavior**: Only reverse-engineer application code. Standard library wrappers, runtime support functions, and clearly identifiable third-party code should be cataloged but not decompiled unless the user explicitly requests it.

### Library vs Application Code Separation

This is a critical early step that reduces noise for all subsequent phases.

**Step 1: Classify all functions**

After `aaa`, classify functions into three categories:

```bash
# In r2 shell:
aaa

# 1. Imported functions (external library calls) — do NOT decompile
afl~sym.imp.
# These are calls TO external DLLs — just note their existence

# 2. Import wrappers (thin shims around DLL calls) — usually skip
afl~sub\.

# 3. Application functions (everything else) — THIS is what we reverse
afl~fcn\.
```

**Step 2: Identify known library patterns in application functions**

Look for function names or call patterns that indicate library wrappers even within local code:

```bash
# MSVC C++ runtime wrappers (within the binary, not imports)
afl~sub.MSVCP
afl~sub.VCRUNTIME
afl~sub.ucrtbase

# STL / exception handling patterns
afl~sub.*exception*
afl~sub.*locale*

# Named STL methods
afl~method.std::
```

**Step 2b: Filter real application functions via string cross-references**

> **This is the most important step.** Simply filtering by `fcn.` prefix is insufficient — C++ binaries typically have hundreds of `fcn.*` functions that are STL template expansions or compiler-generated code. The reliable way to find real business logic is to start from **application strings** and trace backwards.

```bash
# 1. Extract application-specific strings (Usage, error messages, brand names, etc.)
iz~Usage
iz~Error
iz~<program_name>
iz~<key_domain_string>

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

### Recommended Output Strategy for C++ Targets

> **Do NOT attempt to generate C++ code directly.** All mainstream decompilers (Ghidra, r2ghidra, IDA Hex-Rays) output C-like pseudocode regardless of the original source language. C++ abstractions (classes, templates, inheritance, vtables) are flattened at compile time and cannot be recovered automatically.

The recommended two-phase approach:

**Phase A — C pseudocode (what decompilers produce)**

- Accept that the raw output is C, not C++.
- Focus on **behavioral accuracy**: get the algorithm, control flow, and data flow right.
- Collapse STL noise into descriptive comments (e.g., `// std::vector<path> candidates`).
- Preserve all string literals, error codes, and state transitions.
- This phase produces the `clean/src/` tree.

**Phase B — Manual C++ reconstruction (optional, when original language is confirmed C++)**

- Use decompiler output from Phase A as the behavioral specification.
- Identify C++ patterns from clues: RTTI structures, vtable layouts, constructor/destructor pairs, `this` pointer passing conventions, `std::` container usage patterns.
- Use Ghidra's `RecoverClassesFromRTTIScript` (built-in, or headless via `analyzeHeadless -postScript`) to recover class hierarchies. See [C++ RTTI / Type Recovery](#c-rtti--type-recovery) for details.
- Manually rewrite in idiomatic C++ based on the behavioral specification.
- This is a **human-guided** step, not an automated one.

**Why not generate C++ directly:**

- Decompilers cannot distinguish a `std::vector::push_back` loop from a hand-rolled array append.
- Template instantiations produce dozens of near-identical functions that look like different code.
- RAII destructors are scattered across every branch exit and cannot be recovered from stack analysis alone.
- The result of forcing C++ output is often misleading — it looks like C++ but behaves incorrectly (wrong types, wrong class boundaries, missing virtual dispatch).

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
2. Identify the binary (file type, debug indicators, PDB availability).
3. **C++ only**: Run RTTI / type recovery (Ghidra headless or r2 `avra`) before decompilation.
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
