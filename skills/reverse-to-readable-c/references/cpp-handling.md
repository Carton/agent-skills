# C++ Binary Handling

Guidance specific to C++ binaries, including identification, RTTI/type recovery, noise patterns, cleanup strategy, and output strategy.

## Identifying C++ Binaries

Signs of a C++ binary:

- Imported DLLs: `MSVCP140[D].dll`, `VCRUNTIME140[D].dll`, `ucrtbase[d].dll`
- Mangled imports: `__CxxThrowException`, `__std_exception_destroy`, `??1...`
- Source path strings from C++ headers: `<charconv>`, `<filesystem>`, `<xmemory>`, `<xlocale>`
- STL headers in strings: grep for `std::`, `<vector>`, `<string>`, `<map>`, `<memory>`

## C++ RTTI / Type Recovery

**For C++ binaries only.** Perform type recovery **before** decompilation. Recovered type information helps the decompiler produce more accurate output — function parameters get real types instead of `int`, virtual dispatch is correctly resolved, and `std::` container usage patterns become recognizable.

**Why before decompilation:** RTTI is objective metadata embedded by the compiler. Feeding it to the decompiler early means all subsequent decompilation benefits from correct type information. This reduces the "STL noise" problem where `std::vector::push_back` calls appear as anonymous `fcn.XXXX` invocations.

### Option A: Ghidra Headless (recommended)

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

### Option B: radare2 Built-in (basic)

r2 has built-in vtable and RTTI analysis commands — less comprehensive than Ghidra but requires no additional tools:

```bash
# Set ABI to MSVC, then search for vtables with RTTI resolution
r2 -q -e bin.relocs.apply=true -c "aaa; e anal.cpp.abi=msvc; avra" ./target_binary
```

- `av` — search data sections for vtables
- `avr @ addr` — attempt RTTI resolution at a specific vtable address
- `avra` — search all vtables and attempt RTTI resolution for each

**Limitation**: r2's MSVC RTTI support recovers class names and vtable addresses but does not rebuild full class hierarchies or member layouts.

### What RTTI Recovery Produces

| Artifact | Use in Reverse Engineering |
|----------|---------------------------|
| Class names (demangled) | Replace `fcn.XXXX` with meaningful names like `std::filesystem::path` |
| vtable addresses | Identify virtual dispatch; distinguish method calls from function pointer calls |
| Inheritance hierarchies | Understand class relationships; identify base class methods in derived classes |
| Member offsets (approximate) | Understand data layout of `this` pointer usage in decompiled output |

### Manual RTTI Inspection (fallback)

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

## C++ Noise Patterns

C++ binaries (especially MSVC debug builds) produce very large decompiled output due to:

- STL container inline expansion (`std::string`, `std::vector`, `std::filesystem::path`)
- Exception handling frames (`__CxxFrameHandler4`, cookie checks)
- Debug stack initialization (`0xcccccccc` fill loops)
- Template instantiation noise

For C++ targets, consider:

1. **Identify runtime vs business logic**: Mark functions that only call `MSVCP140D.dll` / `ucrtbased.dll` as runtime helpers early.
2. **Focus on call-graph roots**: Start from functions that reference application strings, not from every function.
3. **Batch-export selectively**: Only decompile functions that are 1-2 calls away from a business-critical root.

## Cleanup Strategy for C++

1. **Strip security cookie boilerplate**: Remove init-loops and cookie-check calls at function boundaries — they are compiler-generated, not business logic.
2. **Collapse STL wrappers**: Functions that only construct/destroy `std::string`, `std::vector`, `std::filesystem::path` can be replaced with a comment: `// std::string path_str(path_arg)`.
3. **Recover semantics from mangled names**: Use `afl` and `izz` to map mangled import names to their actual purpose before renaming.
4. **Preserve C++ idioms**: Keep `std::filesystem::path` operations as-is rather than expanding them into raw struct manipulation.

## Output Strategy

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
