# Cleanup Phase

This phase turns decompiler-shaped C into readable equivalent C.

## Target Style

- stage-based control flow
- narrow helper names
- stable constants and event names
- preserved tables and mappings
- preserved address provenance in comments where useful

## Preferred Refactoring Sequence

1. Mark the root function and its phases.
2. Replace repeated low-level noise with opaque helpers.
3. Rename state transitions before renaming generic helper internals.
4. Extract branch-local semantics only when repeated.
5. Keep tables and string maps concrete.

## Anti-Patterns

- Replacing a 300-line state machine with 5 vague helpers
- Hiding callback ownership / licensing / session / configuration side effects
- Dropping “boring” strings because they look like logs
- Rewriting converters into partial switch statements
- Mixing business code with runtime-support code in one file

## Common Reverse-Engineering Failure Modes

- Post-login or post-init validation code is easy to over-compress; watch for entitlement checks, metadata refreshes, capability probes, and ready-state validation.
- Launcher, configuration, service, and metadata modules often contain user-visible strings that act as semantic anchors.

## Post-Cleanup Checks

After each cleaned module:

- compare strings with raw source
- compare major status/error codes
- compare event names
- compare table size if table-driven
- confirm important branches still exist

## Decompiler Noise Pattern Reference

Common noise patterns produced by r2ghidra (and similar decompilers) when analyzing Linux/ELF binaries. Use this as a checklist during Phase 5 cleanup.

| Noise Pattern | Example | Action |
|---|---|---|
| Library function prefix | `sym.imp.write(...)` | Strip `sym.imp.` prefix → `write(...)` |
| Library function prefix (fortified) | `sym.imp.__printf_chk(...)` | Map to original: `printf(...)` |
| Library function prefix (fortified) | `sym.imp.__memcpy_chk(...)` | Map to original: `memcpy(...)` |
| Stack variable names | `var_30h`, `var_28h`, `uStack_40` | Rename to semantic names based on usage |
| Negative stack offsets | `stack0xffffffffffffffd0` | Rewrite as positive offset from base, or rename semantically |
| Bit concatenation | `CONCAT44(a, b)` | Replace with `(a << 32 \| b)` or expand inline |
| Code labels | `code_r0x4012a0`, `lab_0x4012a0` | Delete if trivial; rename to `label_<description>` if meaningful |
| r2 WARNING comments | `//WARNING: ...` | Delete after verifying no semantic content |
| noreturn annotation | `//WARNING: Subroutine does not return` | Convert to `__attribute__((noreturn))` comment or `_Noreturn` |
| Stack canary check | `*(in_FS_OFFSET + 0x28)` | Delete or mark as `/* stack canary */` |
| Global variable deref | `*0x00404020`, `obj.0x00404020` | Replace with semantic constant/variable name from analysis |
| Unresolved function names | `fcn.00401234`, `sub.00401234` | Rename based on call context and string references |
| i18n boilerplate | `setlocale(...)`, `bindtextdomain(...)`, `textdomain(...)` | Collapse to a single comment: `// i18n initialization` |
| Type casts from void* | `(long *)(void *)var` | Simplify to target type if source semantics are clear |
| Redundant casts | `(uint64_t)0x1` | Remove if type is already correct |
| GOT/PLT indirection | `[0x00403000]()` via `.got` | Simplify to direct function name call |
