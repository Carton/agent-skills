# ELF Binary Reference

Platform-specific guidance for Linux/ELF binaries.

## ELF Binary Identification

For Linux/ELF targets, use ELF-specific tools for initial analysis:

```bash
# ELF header and section overview
readelf -h ./target_binary          # file type, architecture, entry point
readelf -S ./target_binary          # section headers
readelf -l ./target_binary          # program headers (segments)

# Symbol tables
nm -D ./target_binary               # dynamic symbols (imports/exports)
readelf -s ./target_binary          # full symbol table (if non-stripped)

# Disassembly
objdump -d ./target_binary          # full disassembly
objdump -t ./target_binary          # symbol table
eu-readelf -s ./target_binary       # alternative readelf (often more readable)
```

**ELF binary type detection:**

| Check | Command | What It Tells You |
|-------|---------|-------------------|
| Stripped vs non-stripped | `readelf -s ./target_binary \| head -5` | Empty output = stripped |
| PIE (Position Independent Executable) | `readelf -h \| grep Type` | `DYN` = PIE, `EXEC` = non-PIE |
| RELRO | `readelf -l \| grep GNU_RELRO` | Present = partial/full RELRO |
| Stack canary | `readelf -s \| grep __stack_chk` | Present = stack protection enabled |
| Fortified functions | `nm -D \| grep __\*_chk` | Present = glibc FORTIFY_SOURCE |

## Fortified glibc Functions

Fortified glibc functions appear with a `__*_chk` suffix. Map them back to the original function name during cleanup:

| Fortified Name | Original | Notes |
|----------------|----------|-------|
| `__printf_chk` | `printf` | `__printf_chk(flag, fmt, ...)` |
| `__fprintf_chk` | `fprintf` | Extra `flag` parameter |
| `__sprintf_chk` | `sprintf` | Extra `flag` and `len` parameters |
| `__memcpy_chk` | `memcpy` | Extra `len` parameter |
| `__memmove_chk` | `memmove` | Extra `len` parameter |
| `__memset_chk` | `memset` | Extra `len` parameter |
| `__strcpy_chk` | `strcpy` | Extra `len` parameter |
| `__strncpy_chk` | `strncpy` | Extra `len` parameter |
| `__read_chk` | `read` | Extra `len` parameter |
| `__recv_chk` | `recv` | Extra `len` parameter |

## Debug Symbols (DWARF)

```bash
# Check for DWARF debug info
readelf --debug-dump=info ./target_binary | head -20
readelf -S ./target_binary | grep debug     # .debug_info, .debug_line, etc.

# Source file paths from debug info
readelf --debug-dump=line ./target_binary | grep -i '\.c$' | head -20
```

## Linux System Utility Patterns

GNU coreutils and glibc-linked programs share common patterns that appear frequently in decompiled output:

**i18n boilerplate (gettext):**
```c
setlocale(LC_ALL, "");
bindtextdomain(PACKAGE, LOCALEDIR);
textdomain(PACKAGE);
```
These are initialization calls that can be collapsed to a single comment: `// i18n initialization (gettext)`.

**Stack canary pattern (x86-64):**
```c
void *canary = *(void **)((int64_t)fs:0x28 + 0);
// ... function body ...
if (canary != *(void **)((int64_t)fs:0x28 + 0)) {
    __stack_chk_fail();
}
```
The canary setup and check are compiler-generated security code — remove during cleanup or mark with `/* stack canary */`.

**glibc fortified function calls:**
```c
// Instead of: printf(fmt, args...)
__printf_chk(1, fmt, args...)   // flag=1 means check stack buffer overflow
// Instead of: memcpy(dst, src, n)
__memcpy_chk(dst, src, n, dest_size)  // extra dest_size parameter
```
Map these back to the original function names. The extra `flag`/`size` parameter is injected by the compiler for buffer overflow detection and should be dropped.

**Source file path clues for system utilities:**

```bash
# For coreutils/glibc programs, source paths reveal the project
strings ./target_binary | grep -E '\.(c|h)$' | head -20
# e.g., "lib/quote.c", "src/cp.c", "gnulib/lib/error.c"

# Identify GNU coreutils version
strings ./target_binary | grep -i 'coreutils\|GNU\|PACKAGE_VERSION'
```

## ELF-Specific Scope Questions

When configuring scope for ELF binaries, ask these additional questions:

1. **Is DWARF debug info present?** — Check `readelf -S | grep debug`. If yes, use `readelf --debug-dump` for source lines and variable names.
2. **Is this a PIE binary?** — Check `readelf -h | grep Type`. PIE binaries (`DYN`) have different address layout; use `-e bin.relocs.apply=true` in r2.
3. **Is this a stripped binary?** — Stripped binaries have no symbol table; function classification relies more on string cross-references and call-graph analysis.
4. **Are fortified glibc functions used?** — `nm -D | grep __*_chk` reveals FORTIFY_SOURCE usage; these map to standard C functions (see [Fortified glibc Functions](#fortified-glibc-functions) above).
