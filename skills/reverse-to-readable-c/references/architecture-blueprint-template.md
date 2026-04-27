# Architecture Blueprint: <Project Name>

This document designs the target source tree structure before physical files are renamed and moved. It ensures a logical, maintainable architecture based on function behavior and dependencies.

## 1. Target Directory Tree
(Design your ideal directory structure here)

```text
src/
├── core/             # Application entry, main loop, and state management
├── network/          # Socket handling, protocol parsing, telemetry
├── auth/             # Login logic, crypto helpers, session validation
├── common/           # Generic utilities, string helpers, logging wrappers
└── platform/         # OS-specific abstractions (WinAPI/Posix wrappers)
```

## 2. Module Definitions

### Module: <module_name>
- **Purpose**: [e.g., Handles all encrypted communication with the backend]
- **Directory**: `src/<path>`
- **Anchor Functions**: (The "Seed" functions that define this module)
  - `fcn.00401234` (@fcn.login_handler)
  - `sym.imp.CryptEncrypt` (System dependency)
- **Naming Convention**: [e.g., `crypto_<name>.c`]

## 3. Cross-Module Dependencies
(How do these modules interact? Use this to spot logic leaks)
- `auth` calls `network` for packet delivery.
- `core` initializes `common` logging first.

## 4. Verification Checklist (Anti-Leak)
- [ ] Every non-skipped function in `phase1/callgraph_summary.md` is assigned to a module.
- [ ] No "orphan" functions left in `[TODO]` module.
- [ ] Directory structure avoids "flat-folder" anti-pattern (>30 files in one folder).
- [ ] Naming follows the blueprint convention.
