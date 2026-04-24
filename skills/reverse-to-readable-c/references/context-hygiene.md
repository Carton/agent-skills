# Context Hygiene

This workflow fails when too much reverse-engineering output is loaded at once.

## The Map-and-Subagent Strategy [NEW]

To safely process a large codebase without losing context:
1. **Maintain a Lightweight Global Map**: Extract only signatures, `struct` definitions, and confirmed global variable semantics into `context/global_map.md`.
2. **Use Sub-Agents**: When cleaning a specific file, invoke a sub-agent (e.g., `invoke_agent` with a `generalist` sub-agent) to perform the task.
3. **Pass Minimal Context**: Give the sub-agent ONLY `context/global_map.md` and the raw source of the specific file being cleaned. DO NOT load the entire decompiled tree.
4. **Dynamic Update**: When the sub-agent identifies the true meaning of an opaque pointer or struct, the Main Agent updates `global_map.md` to propagate this knowledge to future sub-agents.

## Hard Rules

- Never load the whole project tree.
- Never clean multiple large business modules in one pass in the main agent's context. Delegate to sub-agents one by one.
- Never trust a summary of a giant decompiled file without spot-checking the raw file.
- Keep the raw tree and cleaned tree side by side.

## Safe Batch Shapes

Preferred (when dealing with sub-agents):

- 1 root function / file per sub-agent invocation.
- Pass `context/global_map.md` to provide structural context.

Fallback:

- if a file exceeds a sub-agent's context comfort, load only the relevant line ranges
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
2. invoke sub-agent to clean a specific file, providing `global_map.md` and the raw file.
3. sub-agent returns cleaned file and any new struct/global definitions.
4. main agent writes cleaned file to `clean/src/`.
5. main agent updates `global_map.md` with new discoveries.
6. mechanically compare strings/tables to ensure no data loss.
