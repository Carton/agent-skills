#!/bin/bash
# verify_cleanup.sh - Verify that all files in src/ have been cleaned
#
# This script compares clean/raw/ (original decompiler output) with
# clean/src/ (cleaned code) to ensure:
# 1. All files exist in both trees
# 2. Files in src/ are actually cleaned (different from raw/)
# 3. Files in src/ are not over-aggressively cleaned (not too small)

set -e

RAW_DIR="clean/raw"
SRC_DIR="clean/src"

if [ ! -d "$RAW_DIR" ] || [ ! -d "$SRC_DIR" ]; then
    echo "❌ FAIL: Directories '$RAW_DIR' or '$SRC_DIR' do not exist."
    echo "Please ensure you are running this script from the correct project root directory."
    exit 1
fi

echo "=== Cleanup Verification ==="
echo ""

# Check 1: Verify directory structures match
echo "Check 1: Verifying directory structures match..."
DIFF_OUTPUT=$(diff -q <(cd "$RAW_DIR" && find . -type f | sort) \
                      <(cd "$SRC_DIR" && find . -type f | sort) || true)
if [ -n "$DIFF_OUTPUT" ]; then
    echo "❌ FAIL: Directory structures do not match:"
    echo "$DIFF_OUTPUT"
    exit 1
fi
echo "✅ PASS: Directory structures match"
echo ""

# Check 2: Count files
echo "Check 2: Counting files..."
RAW_COUNT=$(find "$RAW_DIR" -name "*.c" | wc -l)
SRC_COUNT=$(find "$SRC_DIR" -name "*.c" | wc -l)
echo "  raw/ files: $RAW_COUNT"
echo "  src/ files: $SRC_COUNT"

if [ "$RAW_COUNT" -ne "$SRC_COUNT" ]; then
    echo "❌ FAIL: File count mismatch"
    exit 1
fi
echo "✅ PASS: File counts match ($RAW_COUNT files)"
echo ""

# Check 3: Verify each file is fully cleaned
echo "Check 3: Verifying files are fully cleaned..."
UNCLEAN_COUNT=0
INSUFFICIENT_REDUCTION_COUNT=0
GHIDRA_ARTIFACTS_COUNT=0
TOTAL_LINES_REDUCED=0

while IFS= read -r -d '' RAW_FILE; do
    # Get relative path
    REL_PATH="${RAW_FILE#$RAW_DIR/}"
    SRC_FILE="$SRC_DIR/$REL_PATH"

    if [ ! -f "$SRC_FILE" ]; then
        echo "❌ FAIL: Missing in src/: $REL_PATH"
        exit 1
    fi

    # Check if files are identical (not cleaned)
    if cmp -s "$RAW_FILE" "$SRC_FILE"; then
        UNCLEAN_COUNT=$((UNCLEAN_COUNT + 1))
    else
        # Files are different, check lines of code reduction
        RAW_LINES=$(wc -l < "$RAW_FILE")
        SRC_LINES=$(wc -l < "$SRC_FILE")
        
        # Prevent division by zero
        if [ "$RAW_LINES" -gt 0 ]; then
            REDUCTION_PERCENT=$(( (RAW_LINES - SRC_LINES) * 100 / RAW_LINES ))
        else
            REDUCTION_PERCENT=0
        fi

        TOTAL_LINES_REDUCED=$((TOTAL_LINES_REDUCED + RAW_LINES - SRC_LINES))

        # Must reduce by at least 90%
        if [ "$REDUCTION_PERCENT" -lt 90 ]; then
            echo "⚠️  INSUFFICIENT REDUCTION: $REL_PATH reduced by only ${REDUCTION_PERCENT}% (Raw: $RAW_LINES lines, Cleaned: $SRC_LINES lines. Expected >= 90%)"
            INSUFFICIENT_REDUCTION_COUNT=$((INSUFFICIENT_REDUCTION_COUNT + 1))
        fi
        
        # Check for Ghidra artifacts (fcn.XXXX, pcVar, puVar, unkbyte, etc)
        ARTIFACTS=$(grep -E -n 'fcn\.[0-9a-fA-F]+|\b[a-zA-Z]*Var[0-9]+\b|\bunkbyte[0-9]+\b' "$SRC_FILE" || true)
        if [ -n "$ARTIFACTS" ]; then
            echo "⚠️  GHIDRA ARTIFACTS FOUND in $REL_PATH:"
            echo "$ARTIFACTS" | sed 's/^/    /'
            GHIDRA_ARTIFACTS_COUNT=$((GHIDRA_ARTIFACTS_COUNT + 1))
        fi
    fi
done < <(find "$RAW_DIR" -name "*.c" -print0)

echo ""
FAIL=0

if [ "$UNCLEAN_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $UNCLEAN_COUNT file(s) identical to raw (not cleaned)"
    echo ""
    echo "Uncleaned files:"
    while IFS= read -r -d '' RAW_FILE; do
        REL_PATH="${RAW_FILE#$RAW_DIR/}"
        SRC_FILE="$SRC_DIR/$REL_PATH"
        if cmp -s "$RAW_FILE" "$SRC_FILE"; then
            echo "  - $REL_PATH"
        fi
    done < <(find "$RAW_DIR" -name "*.c" -print0)
    FAIL=1
fi

if [ "$INSUFFICIENT_REDUCTION_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $INSUFFICIENT_REDUCTION_COUNT file(s) did not meet the 90% size reduction requirement."
    FAIL=1
fi

if [ "$GHIDRA_ARTIFACTS_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $GHIDRA_ARTIFACTS_COUNT file(s) still contain Ghidra artifacts (e.g., fcn.XXXX, pcVar1, unkbyte)."
    FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "✅ PASS: All files are cleaned (sufficiently reduced and no Ghidra artifacts)"
echo ""

# Summary statistics
echo "=== Cleanup Summary ==="
echo "Total files: $RAW_COUNT"
echo "Total lines reduced: $TOTAL_LINES_REDUCED lines"
if [ "$RAW_COUNT" -gt 0 ]; then
    echo "Average line reduction per file: $((TOTAL_LINES_REDUCED / RAW_COUNT)) lines"
fi
echo ""
echo "✅ ALL CHECKS PASSED - Cleanup is complete!"
exit 0
