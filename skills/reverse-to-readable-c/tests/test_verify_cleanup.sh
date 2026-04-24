#!/bin/bash
# tests/test_verify_cleanup.sh - Test the verify_cleanup.sh script

set -e

SKILL_ROOT=$(pwd)
TEST_DIR="$SKILL_ROOT/test_run"

echo "Running Cleanup Verification Test in $TEST_DIR..."

# Ensure we have a mapped project
if [ ! -d "$TEST_DIR/clean/src" ]; then
    ./tests/test_mapping.sh
fi

cd "$TEST_DIR"

# 1. Initially it should FAIL because files are identical to raw
echo "Checking initial failure (identical files)..."
if "$SKILL_ROOT/scripts/verify_cleanup.sh" > /dev/null 2>&1; then
    echo "FAIL: verify_cleanup.sh should have failed on identical files"
    exit 1
fi
echo "  Passed: Correctly failed on identical files."

# 2. Simulate cleaning one file correctly
CLEAN_FILE=$(find clean/src -name "test_func.c")
RAW_FILE=$(find clean/raw -name "test_func.c")

# Make the raw file large enough so we can reduce it by 90%
# 40 lines. 10% is 4 lines.
echo "void fcn.00000000() {" > "$RAW_FILE"
for i in {1..38}; do
    echo "  // decompiler noise line $i" >> "$RAW_FILE"
done
echo "}" >> "$RAW_FILE"

# Sync the src file initially
cp "$RAW_FILE" "$CLEAN_FILE"

# Now clean it: reduce to 3 lines and remove fcn.
echo -e "void test_func() {\n  // Cleaned\n}" > "$CLEAN_FILE"

# 3. isolate for verification
mkdir -p tmp_raw tmp_src
cp "$RAW_FILE" tmp_raw/test_func.c
cp "$CLEAN_FILE" tmp_src/test_func.c
rm -rf clean/raw/* clean/src/*
mkdir -p clean/raw/core clean/src/core
mv tmp_raw/test_func.c clean/raw/core/test_func.c
mv tmp_src/test_func.c clean/src/core/test_func.c

echo "Checking success after cleanup..."
if "$SKILL_ROOT/scripts/verify_cleanup.sh"; then
    echo "PASS: Cleanup verification test successful"
else
    echo "FAIL: verify_cleanup.sh failed even after cleanup"
    exit 1
fi
