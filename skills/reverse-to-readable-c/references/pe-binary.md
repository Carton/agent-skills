# PE Binary Reference

Platform-specific guidance for Windows PE (PE32/PE32+) binaries.

## PDB / Debug Symbols

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

## MSVC Debug Build Artifacts

Debug builds add significant noise:

- **Stack cookie init loops**: `for (iVar = 0xNN; iVar != 0; iVar = iVar + -1) { *ptr = 0xcccccccc; }`
- **Security cookie checks**: `uStack_10 = *0x140044040 ^ auStack_d8;` at function entry, `fcn.14000188e(uStack_10 ^ auStack_d8);` at exit
- **Local variable names**: `auStack_XXX`, `iStack_XXX`, `puVarN`, `cVar1` (decompiler-generated)

**Cleanup**: Remove init-loops and cookie-check calls at function boundaries — they are compiler-generated, not business logic.

## PE-Specific Scope Questions

When configuring scope for PE binaries, ask these additional questions:

1. **Is a PDB file available?** — If yes, use it to get symbol names and types automatically.
2. **Is this a debug or release build?** — Debug builds have more noise but also more information.
3. **Are MSVC C++ runtime DLLs linked?** — `MSVCP140[D].dll`, `VCRUNTIME140[D].dll`, `ucrtbase[d].dll` indicate C++ linkage.

## Debug Build Indicators

- Stack cookie pattern: `0xcccccccc` fill values in decompiled output
- PDB path strings: `D:\...\xxx.pdb`
- Mangled C++ symbols with debug info (e.g. `MSVCP140D.dll`, `ucrtbased.dll`)
- Source file path strings in `.rdata`

## Library Pattern Detection (PE-specific)

```bash
# MSVC C++ runtime wrappers (within the binary, not imports)
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep 'sub\.MSVCP'
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep 'sub\.VCRUNTIME'
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep 'sub\.ucrtbase'

# STL / exception handling patterns
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep -i 'exception'
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep -i 'locale'

# Named STL methods
r2 -q -e bin.relocs.apply=true -c "aaa; afl" ./target_binary | grep 'method\.std::'
```
