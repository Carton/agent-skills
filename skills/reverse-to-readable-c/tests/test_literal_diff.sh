#!/bin/bash
# tests/test_literal_diff.sh - Test the literal_diff.py script

set -e

SKILL_ROOT=$(pwd)
TEST_DIR="$SKILL_ROOT/test_run"

echo "Running Literal Diff Test in $TEST_DIR..."

# Ensure we have a fresh bootstrapped project
rm -f "$TEST_DIR/mapping.tsv"
./tests/test_bootstrap.sh

cd "$TEST_DIR"

# 1. Pick a function
SAMPLE_FILE=$(ls phase2/func_fcn.*.c 2>/dev/null | head -n 1)
if [ -z "$SAMPLE_FILE" ]; then
    echo "FAIL: No decompiled functions found in phase2/"
    exit 1
fi

ORIG=$(basename "$SAMPLE_FILE" | sed 's/^func_//; s/\.c$//')
echo "  Testing with function: $ORIG"

# 2. Modify mapping.tsv to "clean" this specific function
sed -i "s/$ORIG\t\[TODO\]\t\[TODO\]/$ORIG\ttest_diff\tcore/" mapping.tsv

# 3. Ensure mapped file exists
"$SKILL_ROOT/scripts/apply-mapping.sh" > /dev/null

# 4. Modify the phase2 version so there is a diff reported (left - right)
echo '"missing_literal_test"' >> "$SAMPLE_FILE"

# 5. Run literal_diff.py and capture output
OUT=$(python3 "$SKILL_ROOT/scripts/literal_diff.py" --left-root phase2 --right-root clean/src --mapping mapping.tsv || true)

# 6. Verify
if echo "$OUT" | grep -q "missing_literal_test"; then
    echo "PASS: literal_diff.py successfully detected literal differences using mapping.tsv"
else
    echo "FAIL: literal_diff.py output did not contain 'missing_literal_test'"
    echo "Output was:"
    echo "$OUT"
    exit 1
fi
