#!/bin/bash
# scripts/generate-subagent-prompt.sh
# Usage: ./scripts/generate-subagent-prompt.sh <raw_c_file>
#
# Generates a complete prompt for the sub-agent by combining the global context map
# with the specific raw C file to be cleaned.

if [ -z "$1" ] || [ ! -f "$1" ]; then
    echo "Usage: $0 <path_to_raw_c_file>" >&2
    echo "Example: $0 clean/raw/cli/main.c" >&2
    exit 1
fi

RAW_FILE="$1"
GLOBAL_MAP="context/global_map.md"

cat <<EOF
You are a C code cleanup expert. Please convert the following decompiled output into clean, readable C code.

## Global Context (from global_map.md)
This context contains known structures, function signatures, and global state.
**CRITICAL**: You MUST use these type definitions and signatures to rename variables and apply correct types in the raw code.

$(if [ -f "$GLOBAL_MAP" ]; then cat "$GLOBAL_MAP"; else echo "(No global map found)"; fi)

---

## Raw C Code to Clean
File: $RAW_FILE

\`\`\`c
$(cat "$RAW_FILE")
\`\`\`

---

## Task Requirements
1. **Remove Decompiler Noise**: Remove all Ghidra/decompiler artifacts (e.g., fcn.XXXX, pcVar1, puVar2).
2. **Context-Aware Renaming**: Use meaningful variable names based on the Global Context and your analysis.
3. **Preserve Logic**: Preserve ALL string literals, error handling logic, and state transitions. Do not abstract them away.
4. **Headers**: Add necessary C headers (e.g., #include <stdio.h>) at the top.
5. **Output**: Return ONLY the cleaned C code. 
6. **New Discoveries**: If you discover new types, structs, or global variables that should be added to the global map, list them clearly AFTER the code block.
EOF
