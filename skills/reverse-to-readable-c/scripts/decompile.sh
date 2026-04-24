#!/bin/bash
# decompile.sh - Batch decompile functions using r2ghidra
# Usage: ./decompile.sh <binary> <func_addr1> [func_addr2 ...]

TARGET="$1"
shift

if [ -z "$TARGET" ] || [ $# -eq 0 ]; then
    echo "Usage: $0 <binary> <func_addr1> [func_addr2 ...]"
    exit 1
fi

mkdir -p phase2

for func in "$@"; do
    echo "Decompiling $func..."
    r2 -q -e scr.color=0 -e bin.relocs.apply=true -c "aaa; pdg @ $func" "$TARGET" 2>/dev/null > "phase2/func_$func.c"
    
    if [ ! -s "phase2/func_$func.c" ]; then
        echo "pdg failed or empty for $func, falling back to pdc..."
        r2 -q -e scr.color=0 -e bin.relocs.apply=true -c "aaa; pdc @ $func" "$TARGET" 2>/dev/null > "phase2/func_$func.c"
    fi
done

echo "Done. Outputs saved to phase2/"
