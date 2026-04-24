#!/bin/bash
# init-project.sh - Fast binary analysis and workspace bootstrap for reverse-to-readable-c skill
# 
# This script performs all Phase 1 analysis in a single pass, avoiding
# repeated r2 invocations, collecting all necessary information, and
# bootstrapping the standard workspace (directories, skeletons, auto-decompilation).
#
# Usage: ./init-project.sh <binary_path> [output_dir]
# Example: ./init-project.sh /usr/bin/od phase1

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <binary_path> [output_dir]" >&2
    echo "Example: $0 /usr/bin/od analysis_output" >&2
    exit 1
fi

TARGET="$1"
OUTPUT_DIR="${2:-phase1}"

# Validate input
if [ ! -f "$TARGET" ]; then
    echo "Error: Binary file not found: $TARGET" >&2
    exit 1
fi

# Create workspace directories
mkdir -p "$OUTPUT_DIR" phase2 clean/raw clean/src context docs scripts

echo "=== Quick Binary Analysis ===" 
echo "Target: $TARGET"
echo "Output: $OUTPUT_DIR"
echo ""

# 1. Basic binary information
echo "1/6: Collecting basic binary info..."
{
    echo "# Basic Binary Information"
    echo ""
    echo "## File Type"
    file "$TARGET"
    echo ""
    echo "## ELF Header"
    readelf -h "$TARGET" 2>/dev/null | head -10
    echo ""
    echo "## Section Headers (debug info only)"
    readelf -S "$TARGET" 2>/dev/null | grep -E "(debug|sym)" | head -15
} > "$OUTPUT_DIR/basic_info.txt"

# 2. Core r2 analysis (Single Pass)
echo "2/6: Running core binary analysis (this may take a moment)..."
cat > "$OUTPUT_DIR/analyze.r2" << EOF
e scr.color=0
aaa
afl > $OUTPUT_DIR/all_functions.txt
iz > $OUTPUT_DIR/all_strings.txt
axtj @@ str.* > $OUTPUT_DIR/all_xrefs.json
ts > $OUTPUT_DIR/types.h
EOF

r2 -q -e bin.relocs.apply=true -i "$OUTPUT_DIR/analyze.r2" "$TARGET" 2>/dev/null


# Count and classify functions
TOTAL=$(wc -l < "$OUTPUT_DIR/all_functions.txt")
IMPORTS=$(grep -c 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" || echo 0)
LOCAL=$(grep -v 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | grep -v 'entry' | wc -l)

{
    echo "# Function Classification"
    echo ""
    echo "## Summary"
    echo "- Total Functions: $TOTAL"
    echo "- Imported Functions: $IMPORTS"
    echo "- Local Functions: $LOCAL"
    echo "- Application Functions (estimated): $((LOCAL - IMPORTS / 2))"
    echo ""
    echo "## Imported Functions (sym.imp.*)"
    grep 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | head -20
    if [ $IMPORTS -gt 20 ]; then
        echo "... and $((IMPORTS - 20)) more"
    fi
    echo ""
    echo "## Local Functions (fcn.*)"
    grep -v 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | grep -v 'entry' | awk '{print $1, $2, $3, $NF}'
} > "$OUTPUT_DIR/function_classification.md"

# 3. String analysis
echo "3/6: Extracting key strings..."
{
    echo "# Key String References"
    echo ""
    echo "## Usage/Help Strings"
    grep -iE "(usage|help)" "$OUTPUT_DIR/all_strings.txt" | head -10 || echo "None found."
    echo ""
    echo "## Error Messages"
    grep -iE "(error|invalid|fail)" "$OUTPUT_DIR/all_strings.txt" | head -10 || echo "None found."
    echo ""
    echo "## Version/Brand Strings"
    grep -iE "(version|copyright|gnu)" "$OUTPUT_DIR/all_strings.txt" | head -10 || echo "None found."
} > "$OUTPUT_DIR/key_strings.md"

# 4. String cross-reference mapping
echo "4/6: Building string xref map..."
{
    echo "# String Cross-References"
    echo ""
    echo "## Format: address: referencing_function -> string"
    echo ""
    python3 -c "
import sys, json
keywords = ['usage', 'error', 'invalid', 'help', 'version']
try:
    with open('$OUTPUT_DIR/all_xrefs.json') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                arr = json.loads(line)
                for xref in arr:
                    refname = str(xref.get('refname', ''))
                    if any(k in refname.lower() for k in keywords):
                        fr = hex(xref.get('from', 0))
                        fcn = str(xref.get('fcn_name', 'None'))
                        print(f'{fr}: {fcn} -> {refname}')
            except:
                pass
except Exception as e:
    print(f'Error processing xrefs: {e}')
"
} > "$OUTPUT_DIR/string_xref.md"

# 5. Import summary
echo "5/6: Summarizing imports..."
{
    echo "# Imported Functions Summary"
    echo ""
    echo "## Standard Library Calls"
    grep 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | \
        grep -oE '\.(printf|fprintf|scanf|malloc|free|open|read|write|close|fopen|fclose)' | \
        sort | uniq -c | sort -rn
    echo ""
    echo "## Internationalization"
    grep 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | \
        grep -E '(gettext|locale|textdomain)' || echo "None"
    echo ""
    echo "## Fortified Functions (FORTIFY_SOURCE)"
    grep 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | \
        grep -E '(_chk|__stack)' || echo "None"
} > "$OUTPUT_DIR/imports_summary.md"

# 6. Quick recommendations
echo "6/6: Generating recommendations..."
{
    echo "# Analysis Complete - Next Steps"
    echo ""
    echo "## Quick Start"
    echo "The following files have been generated:"
    echo ""
    echo "- \`all_functions.txt\` - Complete function list"
    echo "- \`function_classification.md\` - Categorized functions"
    echo "- \`key_strings.md\` - Important string literals"
    echo "- \`string_xref.md\` - String to function mapping"
    echo "- \`imports_summary.md\` - Library dependency overview"
    echo ""
    echo "## Recommended Phase 2 Targets"
    echo ""
    echo "Based on string cross-references, start with:"
    echo ""
    grep -oE 'fcn\.[0-9a-f]+' "$OUTPUT_DIR/string_xref.md" 2>/dev/null | sort -u | head -5 || \
        echo "Run: grep -oE 'fcn\.[0-9a-f]+' all_functions.txt | head -10"
    echo ""
    echo "## Decompilation Commands"
    echo ""
    echo "# Single function:"
    echo "r2 -q -e scr.color=0 -e bin.relocs.apply=true -c \"aaa; pdg @ <function>\" \"$TARGET\""
    echo ""
    echo "# Batch decompile (use with care):"
    echo "for func in \$(cat <function_list>); do"
    echo "  r2 -q -e scr.color=0 -e bin.relocs.apply=true -c \"aaa; pdg @ \$func\" \"$TARGET\" 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' > phase2/func_\$func.c"
    echo "done"
} > "$OUTPUT_DIR/next_steps.md"

# 7. Generate Workspace Skeletons
echo "7/8: Generating workspace skeletons (progress.md, mapping.tsv, global_map.md)..."

# Extract local application functions
LOCAL_FUNCS=$(grep -v 'sym\.imp\.' "$OUTPUT_DIR/all_functions.txt" | grep -v 'entry' | awk '{print $4}' | grep '^fcn\.')

# Generate mapping.tsv
echo -e "address\toriginal_name\tclean_name\tmodule" > mapping.tsv
for f in $LOCAL_FUNCS; do
    addr=$(echo "$f" | grep -oE '[0-9a-f]+$')
    echo -e "0x$addr\t$f\t[TODO]\t[TODO]" >> mapping.tsv
done

# Generate global_map.md
cat > context/global_map.md << 'EOF'
# Global Context Map

## Identified Modules
- core
- (Add others based on Phase 1 classification)

## Global State / Config
- (TODO: Add suspected global structs or state variables)

## Key Data Types (from phase1/types.h)
- (TODO)

## Strings of Interest
EOF
cat "$OUTPUT_DIR/string_xref.md" >> context/global_map.md

# Generate progress.md
ROOT_FUNCS=$(grep -oE 'fcn\.[0-9a-f]+' "$OUTPUT_DIR/string_xref.md" 2>/dev/null | sort -u)

cat > progress.md << EOF
# Progress Tracking

**Project Goal**: Reverse engineering
**Current Phase**: Phase 2 (Raw Decompilation) / Phase 4 (Renaming)

## Next Steps
1. Review \`phase1/function_classification.md\` and \`context/global_map.md\`.
2. Clean the root functions listed below.

## Functions Analysed

| Address | Raw Name | Clean Name | Status |
|---------|----------|------------|--------|
EOF

for f in $ROOT_FUNCS; do
    addr=$(echo "$f" | grep -oE '[0-9a-f]+$')
    echo "| 0x$addr | $f | [TODO] | Raw |" >> progress.md
done

# 8. Batch Decompile Root Functions
echo "8/8: Auto-decompiling root functions to phase2/ ..."
if [ -n "$ROOT_FUNCS" ] && [ -x "scripts/decompile.sh" ]; then
    ./scripts/decompile.sh "$TARGET" $ROOT_FUNCS
else
    echo "No root functions found or scripts/decompile.sh not present/executable."
fi

echo ""
echo "✅ Analysis & Bootstrap complete!"
echo ""
echo "Generated files:"
ls -lh "$OUTPUT_DIR"/*.txt "$OUTPUT_DIR"/*.md 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo ""
echo "Start with: cat $OUTPUT_DIR/next_steps.md"
