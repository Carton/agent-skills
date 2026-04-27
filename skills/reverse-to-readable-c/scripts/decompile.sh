#!/bin/bash
# decompile.sh - Batch decompile functions using r2ghidra (parallel)
# Usage: ./decompile.sh <binary> <func_addr1> [func_addr2 ...]
#
# This is a thin wrapper around decompile.py which uses multiprocessing
# to saturate all available CPU cores.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

TARGET="$1"
shift

if [ -z "$TARGET" ] || [ $# -eq 0 ]; then
    echo "Usage: $0 <binary> <func_addr1> [func_addr2 ...]"
    exit 1
fi

exec python3 "$SCRIPT_DIR/decompile.py" "$TARGET" "$@"
