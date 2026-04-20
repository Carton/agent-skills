# Context Hygiene

This workflow fails when too much reverse-engineering output is loaded at once.

## Hard Rules

- Never load the whole project tree.
- Never clean multiple large business modules in one pass.
- Never trust a summary of a giant decompiled file without spot-checking the raw file.
- Keep the raw tree and cleaned tree side by side.

## Safe Batch Shapes

Preferred:

- 1 root function
- 1 module
- 2-8 files in a pass
- direct helpers only

Fallback:

- if a file exceeds context comfort, load only the relevant line ranges
- if a module is too large, split it by state machine stage

## Escalation Triggers

Split the work further if any of these are true:

- one cleaned file shrank drastically
- strings disappeared
- table modules were abstracted into short switch/helper code
- callback/state logic feels “too simple” compared to raw source
- the agent starts inventing helper semantics from names alone

## Practical Pattern

For each module:

1. read docs for the module
2. read the current cleaned file
3. read the raw backup for the same file
4. inspect direct helper files only if needed
5. make the change
6. mechanically compare strings/tables again

