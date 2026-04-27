#!/bin/bash
# decompile.sh - Batch decompile functions using r2ghidra (parallel)
# Usage: ./decompile.sh <binary> <func_addr1> [func_addr2 ...]
#
# This is a thin wrapper around decompile.py which uses multiprocessing
# to saturate all available CPU cores. It also filters out functions marked
# as [SKIP:*] in mapping.tsv.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

TARGET="$1"
shift

if [ -z "$TARGET" ] || [ $# -eq 0 ]; then
    echo "Usage: $0 <binary> <func_addr1> [func_addr2 ...]"
    exit 1
fi

# Filter out skipped functions
VALID_FUNCS=()
for func in "$@"; do
    if [ -f "mapping.tsv" ]; then
        # Check if this function is marked to be skipped
        # mapping.tsv format: address \t original_name \t clean_name \t module
        SKIP_MATCH=$(awk -v f="$func" '$1 == f || $2 == f {print $4}' mapping.tsv | grep -i '^\[SKIP:')
        if [ -n "$SKIP_MATCH" ]; then
            echo "Skipping $func (marked as $SKIP_MATCH in mapping.tsv)"
            continue
        fi
    fi
    VALID_FUNCS+=("$func")
done

if [ ${#VALID_FUNCS[@]} -eq 0 ]; then
    echo "No valid functions to decompile (all were skipped or none provided)."
    exit 0
fi

exec python3 "$SCRIPT_DIR/decompile.py" "$TARGET" "${VALID_FUNCS[@]}"
