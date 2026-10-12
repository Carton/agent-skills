#!/bin/bash
# Preserve the historical single-file entry point and support narrow modules.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON=${R2C_PYTHON:-python3}
if [ -x .venv/bin/python ] && [ -z "${R2C_PYTHON:-}" ]; then
    PYTHON=.venv/bin/python
fi
exec "$PYTHON" "$SCRIPT_DIR/generate_subagent_prompt.py" "$@"
