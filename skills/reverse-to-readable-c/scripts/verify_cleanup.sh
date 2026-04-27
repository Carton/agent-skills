#!/bin/bash
# verify_cleanup.sh - Verify that all files in src/ have been cleaned
#
# This script compares clean/raw/ (original decompiler output) with
# clean/src/ (cleaned code) to ensure:
# 1. All files exist in both trees
# 2. Files in src/ are actually cleaned (different from raw/)
# 3. Files in src/ do NOT contain Ghidra artifacts (fcn.HEX_ADDR, pcVar*, puVar*)
#    Note: Comments starting with @fcn. are preserved for traceability and ignored.

set -e

RAW_DIR="clean/raw"
SRC_DIR="clean/src"

if [ ! -d "$RAW_DIR" ] || [ ! -d "$SRC_DIR" ]; then
    echo "❌ FAIL: Directories '$RAW_DIR' or '$SRC_DIR' do not exist."
    echo "Please ensure you are running this script from the project root."
    exit 1
fi

echo "=== Cleanup Verification ==="
echo ""

# Check 1: Verify directory structures match
DIFF_OUTPUT=$(diff -q <(cd "$RAW_DIR" && find . -type f | sort) \
                      <(cd "$SRC_DIR" && find . -type f | sort) || true)
if [ -n "$DIFF_OUTPUT" ]; then
    echo "❌ FAIL: Directory structures do not match:"
    echo "$DIFF_OUTPUT"
    exit 1
fi
echo "✅ PASS: Directory structures match"

# Check 2: Verify each file
echo "Check 2: Verifying files are fully cleaned..."
UNCLEAN_COUNT=0
ARTIFACT_COUNT=0
TOTAL_FILES=0
TOTAL_LINES_REDUCED=0

while IFS= read -r -d '' RAW_FILE; do
    REL_PATH="${RAW_FILE#$RAW_DIR/}"
    SRC_FILE="$SRC_DIR/$REL_PATH"
    TOTAL_FILES=$((TOTAL_FILES + 1))

    # 1. Identical check
    if cmp -s "$RAW_FILE" "$SRC_FILE"; then
        echo "  ⚠️  NOT CLEANED: $REL_PATH (Identical to raw)"
        UNCLEAN_COUNT=$((UNCLEAN_COUNT + 1))
        continue
    fi

    RAW_LINES=$(wc -l < "$RAW_FILE")
    SRC_LINES=$(wc -l < "$SRC_FILE")
    TOTAL_LINES_REDUCED=$((TOTAL_LINES_REDUCED + RAW_LINES - SRC_LINES))

    # 3. Artifact check
    # We look for fcn. but ignore those prefixed with @ (traceability comments)
    ARTIFACTS=$(grep -E -n 'fcn\.[0-9a-fA-F]+|\b[a-zA-Z]*Var[0-9]+\b|\bunkbyte[0-9]+\b' "$SRC_FILE" | grep -v '@fcn\.' || true)
    if [ -n "$ARTIFACTS" ]; then
        echo "  ⚠️  ARTIFACTS FOUND in $REL_PATH:"
        echo "$ARTIFACTS" | head -n 3 | sed 's/^/    /'
        ARTIFACT_COUNT=$((ARTIFACT_COUNT + 1))
    fi

done < <(find "$RAW_DIR" -name "*.c" -print0)

echo ""
FAIL=0
if [ "$UNCLEAN_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $UNCLEAN_COUNT file(s) identical to raw."
    FAIL=1
fi
if [ "$ARTIFACT_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $ARTIFACT_COUNT file(s) contain decompiler artifacts."
    FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "=== Cleanup Summary ==="
echo "Total files verified: $TOTAL_FILES"
echo "Total lines removed: $TOTAL_LINES_REDUCED"
if [ "$TOTAL_FILES" -gt 0 ]; then
    echo "Average reduction: $((TOTAL_LINES_REDUCED / TOTAL_FILES)) lines/file"
fi
echo ""
echo "✅ ALL CHECKS PASSED - Cleanup is complete!"
exit 0
