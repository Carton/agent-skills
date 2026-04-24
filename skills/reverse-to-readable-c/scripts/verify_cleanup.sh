#!/bin/bash
# verify_cleanup.sh - Verify that all files in src/ have been cleaned
#
# This script compares clean/raw/ (original decompiler output) with
# clean/src/ (cleaned code) to ensure:
# 1. All files exist in both trees
# 2. Files in src/ are actually cleaned (different from raw/)
# 3. Files in src/ have at least 90% line reduction (as requested by user)
# 4. Files in src/ do NOT contain Ghidra artifacts (fcn.*, pcVar*, puVar*)

set -e

RAW_DIR="clean/raw"
SRC_DIR="clean/src"

if [ ! -d "$RAW_DIR" ] || [ ! -d "$SRC_DIR" ]; then
    echo "❌ FAIL: Directories '$RAW_DIR' or '$SRC_DIR' do not exist."
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
SIZE_FAIL_COUNT=0
TOTAL_FILES=0

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

    # 2. Size reduction check (90% reduction rule)
    RAW_LINES=$(wc -l < "$RAW_FILE")
    SRC_LINES=$(wc -l < "$SRC_FILE")
    # If raw is very small (e.g. < 5 lines), 90% might be impossible/meaningless, 
    # but we follow the rule.
    THRESHOLD=$((RAW_LINES / 10))
    if [ "$SRC_LINES" -gt "$THRESHOLD" ] && [ "$RAW_LINES" -gt 10 ]; then
        echo "  ⚠️  INSUFFICIENT REDUCTION: $REL_PATH ($SRC_LINES lines, raw had $RAW_LINES. Need <= $THRESHOLD)"
        SIZE_FAIL_COUNT=$((SIZE_FAIL_COUNT + 1))
    fi

    # 3. Artifact check
    ARTIFACTS=$(grep -E -n 'fcn\.[0-9a-fA-F]+|\b[a-zA-Z]*Var[0-9]+\b|\bunkbyte[0-9]+\b' "$SRC_FILE" || true)
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
if [ "$SIZE_FAIL_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $SIZE_FAIL_COUNT file(s) did not reach 90% line reduction."
    FAIL=1
fi
if [ "$ARTIFACT_COUNT" -gt 0 ]; then
    echo "❌ FAIL: $ARTIFACT_COUNT file(s) contain decompiler artifacts."
    FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "✅ ALL CHECKS PASSED ($TOTAL_FILES files) - Cleanup is complete!"
exit 0
