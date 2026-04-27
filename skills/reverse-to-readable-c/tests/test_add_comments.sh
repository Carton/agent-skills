#!/bin/bash
# tests/test_add_comments.sh - Test the add-comments.sh script

set -e

SKILL_ROOT=$(pwd)
TEST_DIR="$SKILL_ROOT/test_run"

echo "Running Add Comments Test in $TEST_DIR..."

# Ensure we have a fresh bootstrapped project
rm -f "$TEST_DIR/mapping.tsv"
./tests/test_bootstrap.sh

cd "$TEST_DIR"

# 1. Pick a function that is ACTUALLY in phase2/
SAMPLE_FILE=$(ls phase2/func_fcn.*.c 2>/dev/null | head -n 1)
if [ -z "$SAMPLE_FILE" ]; then
    echo "FAIL: No decompiled functions found in phase2/"
    exit 1
fi

ORIG=$(basename "$SAMPLE_FILE" | sed 's/^func_//; s/\.c$//')
ADDR=$(grep -P "^0x[0-9a-f]+\t$ORIG" mapping.tsv | awk '{print $1}' | head -n 1)
if [ -z "$ADDR" ]; then
    ADDR=$ORIG
fi

echo "  Testing with function: $ORIG (Address: $ADDR)"

# 2. Modify mapping.tsv to "clean" this specific function
sed -i "s/$ORIG\t\[TODO\]\t\[TODO\]/$ORIG\ttest_comment\tcore/" mapping.tsv

# 3. Ensure the mapped file exists in clean/src/
"$SKILL_ROOT/scripts/apply-mapping.sh" > /dev/null

if [ ! -f "clean/src/core/test_comment.c" ]; then
    echo "FAIL: test_comment.c not created, apply-mapping failed."
    exit 1
fi

# 4. Run add-comments.sh
"$SKILL_ROOT/scripts/add-comments.sh" > /dev/null

# 5. Verify
if grep -q "Original address:" "clean/src/core/test_comment.c"; then
    echo "PASS: Address comment successfully injected into clean/src/core/test_comment.c"
else
    echo "FAIL: Address comment NOT injected!"
    head -n 5 "clean/src/core/test_comment.c"
    exit 1
fi
