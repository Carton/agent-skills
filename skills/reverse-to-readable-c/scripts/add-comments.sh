#!/bin/bash
# scripts/add-comments.sh - Batch add original address comments to clean/src files
# This script uses mapping.tsv and add_address_comments.py to inject comments.

if [ ! -f "mapping.tsv" ]; then
    echo "Error: mapping.tsv not found."
    exit 1
fi

# Get script directory to find the python script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_SCRIPT="$SCRIPT_DIR/add_address_comments.py"

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: $PYTHON_SCRIPT not found."
    exit 1
fi

echo "Injecting address comments into clean/src/ ..."

# We can run the python script directly. 
# We need to make sure it knows where the src files are.
# add_address_comments.py usually expects a mapping file.
# Let's check how add_address_comments.py works.
python3 "$PYTHON_SCRIPT" --mapping mapping.tsv --base-dir .

echo "Done."
