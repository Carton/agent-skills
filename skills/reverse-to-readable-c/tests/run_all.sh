#!/bin/bash
# tests/run_all.sh - Run all tests for the reverse-to-readable-c skill

set -e

# Always start from the skill root
SKILL_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$SKILL_ROOT"

echo "=== Running All Skill Tests ==="
./tests/test_bootstrap.sh
./tests/test_mapping.sh
./tests/test_verify_cleanup.sh

echo ""
echo "✨ ALL TESTS PASSED ✨"
