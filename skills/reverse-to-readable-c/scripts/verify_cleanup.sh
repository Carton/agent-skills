#!/bin/bash
# Mechanical checks complement compilation and behavior tests; they do not prove equivalence.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON=${R2C_PYTHON:-python3}
if [ -x .venv/bin/python ] && [ -z "${R2C_PYTHON:-}" ]; then
    PYTHON=.venv/bin/python
fi
exec "$PYTHON" "$SCRIPT_DIR/verify_cleanup.py" "$@"
