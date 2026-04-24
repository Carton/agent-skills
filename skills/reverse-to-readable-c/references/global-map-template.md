# Global Context Map

This file serves as the "lightweight memory" for sub-agents cleaning individual files.
It prevents context overflow by summarizing the global state, structures, and function signatures without holding their implementations.

**IMPORTANT: This file must be dynamically updated by the Main Agent whenever a sub-agent discovers new struct definitions or global variable meanings.**

## 1. Core Data Structures

Define `struct`, `enum`, and `typedef` declarations discovered so far.

```c
// Example:
// struct AppConfig {
//     int is_debug;
//     char* config_path;
// };
```

## 2. Global Variables

Map raw addresses to their semantic meanings.

| Raw Address/Name | Semantic Name | Type | Known Purpose |
|------------------|---------------|------|---------------|
| `obj.0x00404020` | `g_app_config`| `AppConfig*` | Holds the main configuration loaded at startup |

## 3. Function Signatures

List the semantic signatures of functions that are called across different files.
Do NOT include the function bodies here.

```c
// Example:
// int init_app_config(AppConfig* config, const char* path);
// void cleanup_app_config(AppConfig* config);
```

## 4. Sub-Agent Notes & Conventions

Any project-specific rules or conventions that sub-agents should follow when converting raw C to readable C.
- e.g., "Always return -1 on error."
- e.g., "Use standard `stdbool.h` for booleans."

