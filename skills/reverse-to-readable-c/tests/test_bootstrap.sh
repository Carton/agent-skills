#!/bin/bash
# tests/test_bootstrap.sh - Test the init-project.sh script

set -e

# Get the skill root directory (absolute path)
SKILL_ROOT=$(pwd)
TEST_DIR="$SKILL_ROOT/test_run"

echo "Running Bootstrap Test in $TEST_DIR..."

# 1. Prepare test directory
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# 2. Run the initialization script
# We need to call it via absolute path or relative to SKILL_ROOT
"$SKILL_ROOT/scripts/init-project.sh" /usr/bin/od phase1

# 3. Check directories
for dir in phase1 phase2 clean/raw clean/src context docs; do
    if [ ! -d "$dir" ]; then
        echo "FAIL: Directory $dir not created"
        exit 1
    fi
done

# 4. Check skeleton files
for file in mapping.tsv progress.md context/global_map.md phase1/types.h; do
    if [ ! -f "$file" ]; then
        echo "FAIL: File $file not created"
        exit 1
    fi
done

# 5. Check if decompilation produced output
FUNC_COUNT=$(ls phase2/*.c 2>/dev/null | wc -l)
if [ "$FUNC_COUNT" -eq 0 ]; then
    echo "FAIL: No decompiled functions in phase2/"
    exit 1
fi

echo "PASS: Bootstrap test successful ($FUNC_COUNT functions decompiled)"
