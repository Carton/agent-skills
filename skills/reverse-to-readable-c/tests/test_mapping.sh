#!/bin/bash
# tests/test_mapping.sh - Test the apply-mapping.sh script

set -e

SKILL_ROOT=$(pwd)
TEST_DIR="$SKILL_ROOT/test_run"

echo "Running Mapping Application Test in $TEST_DIR..."

# Ensure we have a fresh bootstrapped project in test_run
rm -f "$TEST_DIR/mapping.tsv"
./tests/test_bootstrap.sh

cd "$TEST_DIR"

# 1. Pick a function that is ACTUALLY in phase2/
# Find a func_fcn.XXXXXXXX.c file
SAMPLE_FILE=$(ls phase2/func_fcn.*.c | head -n 1)
if [ -z "$SAMPLE_FILE" ]; then
    echo "FAIL: No decompiled functions found in phase2/ to test mapping"
    exit 1
fi

# Extract the original name from filename: phase2/func_fcn.XXXXXXXX.c -> fcn.XXXXXXXX
ORIG=$(basename "$SAMPLE_FILE" | sed 's/^func_//; s/\.c$//')

echo "  Testing with function: $ORIG"

# 2. Modify mapping.tsv to "clean" this specific function
# Rewrite the whole row regardless of its current clean_name/module
# (the step-8.5 auto-classifier may already have filled them in)
ADDR=$(awk -F'\t' -v f="$ORIG" '$2==f {print $1}' mapping.tsv)
awk -i inplace -F'\t' -v OFS='\t' -v addr="$ADDR" \
    '$1==addr { $3="test_func"; $4="core" } 1' mapping.tsv

# 3. Run apply-mapping.sh
"$SKILL_ROOT/scripts/apply-mapping.sh"

# 4. Verify
if [ ! -f "clean/raw/core/test_func.c" ]; then
    echo "FAIL: clean/raw/core/test_func.c not created for $ORIG"
    ls -la clean/raw/core/
    exit 1
fi

if [ ! -f "clean/src/core/test_func.c" ]; then
    echo "FAIL: clean/src/core/test_func.c not created for $ORIG"
    exit 1
fi

echo "PASS: Mapping application test successful"
