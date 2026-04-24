#!/bin/bash
# scripts/apply-mapping.sh - Apply renames from mapping.tsv to clean/ tree
# This script automates Phase 4 by creating module directories and
# copying files from phase2/ to clean/raw/ and clean/src/.

if [ ! -f "mapping.tsv" ]; then
    echo "Error: mapping.tsv not found."
    exit 1
fi

echo "Applying mapping from mapping.tsv..."

# Skip header line
# We use a while loop with IFS set to tab to parse the TSV correctly
tail -n +2 mapping.tsv | while IFS=$'\t' read -r addr orig clean mod; do
    # Skip entries that are still marked as [TODO]
    if [[ "$clean" == "[TODO]" ]] || [[ "$mod" == "[TODO]" ]] || [[ -z "$clean" ]] || [[ -z "$mod" ]]; then
        continue
    fi
    
    # Sanitize names (remove any trailing carriage returns if present from Windows editing)
    clean=$(echo "$clean" | tr -d '\r')
    mod=$(echo "$mod" | tr -d '\r')
    orig=$(echo "$orig" | tr -d '\r')

    echo "  -> Mapping $orig to $mod/$clean.c"
    
    mkdir -p "clean/raw/$mod" "clean/src/$mod"
    
    # Look for the source file in phase2/
    # The file name pattern is typically func_<original_name>.c
    SRC="phase2/func_$orig.c"
    
    if [ -f "$SRC" ]; then
        cp "$SRC" "clean/raw/$mod/$clean.c"
        cp "$SRC" "clean/src/$mod/$clean.c"
    else
        # Try a more flexible match if direct match fails
        SRC=$(find phase2 -name "*$orig.c" | head -n 1)
        if [ -n "$SRC" ] && [ -f "$SRC" ]; then
            cp "$SRC" "clean/raw/$mod/$clean.c"
            cp "$SRC" "clean/src/$mod/$clean.c"
        else
            echo "  ⚠️  Warning: Could not find source file for $orig in phase2/"
        fi
    fi
done

echo "Done. Workspace updated in clean/raw/ and clean/src/."
