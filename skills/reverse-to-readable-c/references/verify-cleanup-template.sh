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

# Check 3: Verify each file is cleaned (different from raw)
echo "Check 3: Verifying files are actually cleaned..."
UNCLEAN_COUNT=0
TOTAL_SIZE_DIFF=0

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
        echo "⚠️  UNCLEANED: $REL_PATH"
        ((UNCLEAN_COUNT++))
    else
        # Files are different, check size difference
        RAW_SIZE=$(stat -c%s "$RAW_FILE")
        SRC_SIZE=$(stat -c%s "$SRC_FILE")
        SIZE_DIFF=$((RAW_SIZE - SRC_SIZE))
        TOTAL_SIZE_DIFF=$((TOTAL_SIZE_DIFF + SIZE_DIFF))

        # Warn if cleaned file is suspiciously small (< 30% of raw)
        SIZE_PERCENT=$((SRC_SIZE * 100 / RAW_SIZE))
        if [ "$SIZE_PERCENT" -lt 30 ]; then
            echo "⚠️  WARNING: $REL_PATH reduced to ${SIZE_PERCENT}% of original size"
            echo "    Raw: $RAW_SIZE bytes, Cleaned: $SRC_SIZE bytes"
        fi
    fi
done < <(find "$RAW_DIR" -name "*.c" -print0)

echo ""
if [ "$UNCLEAN_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $UNCLEAN_COUNT file(s) not yet cleaned"
    echo ""
    echo "Uncleaned files:"
    while IFS= read -r -d '' RAW_FILE; do
        REL_PATH="${RAW_FILE#$RAW_DIR/}"
        SRC_FILE="$SRC_DIR/$REL_PATH"
        if cmp -s "$RAW_FILE" "$SRC_FILE"; then
            echo "  - $REL_PATH"
        fi
    done < <(find "$RAW_DIR" -name "*.c" -print0)
    exit 1
fi

echo "✅ PASS: All files are cleaned (different from raw)"
echo ""

# Summary statistics
echo "=== Cleanup Summary ==="
echo "Total files: $RAW_COUNT"
echo "Total size reduction: $TOTAL_SIZE_DIFF bytes"
echo "Average reduction per file: $((TOTAL_SIZE_DIFF / RAW_COUNT)) bytes"
echo ""
echo "✅ ALL CHECKS PASSED - Cleanup is complete!"
exit 0
