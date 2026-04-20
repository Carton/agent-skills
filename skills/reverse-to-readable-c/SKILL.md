---
name: reverse-to-readable-c
description: End-to-end workflow for reversing native binaries into organized, readable C code using phased analysis, radare2, r2ghidra, optional Ghidra, per-module batching, structured renaming, and AI-assisted cleanup. Use when the task is to explore a PE or ELF binary, identify modules, decompile functions into initial C, reorganize outputs into a better directory layout, rename files/functions, and iteratively convert decompiler output into equivalent readable C without overflowing context.
---

# Reverse To Readable C

Use this skill for full reverse-engineering projects where the goal is not just to inspect a binary, but to produce a maintainable source tree from it.

The workflow is phase-based and aggressively context-limited. Never try to load the whole reverse-engineering output at once.

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
│   ├── src/                  # current readable tree
│   ├── task_plan.md
│   ├── findings.md
│   └── progress.md
└── scripts/                  # rename / annotation helpers
```

If the repository already has a structure, preserve it and fit the workflow into it.

## Phase 1: Exploratory Analysis

Goal: identify the binary shape, main entry chain, probable modules, and the first 20-50 functions worth tracking.

Use radare2 for discovery first. Typical actions:

```bash
r2 -A ./target_binary
afl
izz
axt @@ sym.*
```

Useful r2 queries:

- `afl` to list discovered functions
- `afll` or `aflj` for sortable inventories
- `izz` / `izj` for strings
- `axt` for cross-references from important strings
- `pdf @ addr` for assembly review
- `agf @ addr` or `agfj @ addr` for local graph shape

What to produce in phase 1:

- an entry-chain note
- a first-pass module map
- a function index by address
- a shortlist of business-critical roots
- a risk list: parsers, session/auth, networking, startup, configuration, service, update, teardown

Do not decompile everything yet.

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

Initialize and update `r2pm`, then install `r2ghidra`:

```bash
r2pm init || true
r2pm -U
r2pm -ci r2ghidra
```

### Recommended Optional Tools

- `ghidra`: useful for GUI validation and headless analysis passes
- `gdb-multiarch`: useful for non-native ELF targets
- `wine`: useful for observing PE executables or DLL loaders on Linux
- `upx`: useful when the binary may be packed
- `apktool`: only for Android APK/DEX/JAR workflows
- archive/unpacker tools such as `p7zip-full`, `cabextract`, `unar`: useful for installers and embedded payloads

### Ghidra

Ghidra is optional but strongly recommended for validation and headless bulk analysis. Install a supported JDK, then extract the official Ghidra release and use `analyzeHeadless` for scripted analysis.

Read [references/install-linux.md](references/install-linux.md) before first-time setup.

## Phase 2: Raw Per-Function Decompilation

Goal: export initial C-like code for only the functions needed for the current module.

Prefer `r2ghidra` through radare2 when available:

```bash
r2 -A ./target_binary
pdg @ 0x14000e430
pdg @ 0x140015170
```

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

Group functions by real behavior, not by decompiler order.

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
