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
