# Automated Function Classification

## Overview

The reverse-to-readable-c skill now includes **automated function classification** as part of the Phase 1 analysis (`init-project.sh`).

This feature uses a **multi-layer classification strategy** to automatically categorize functions into:
- **Application modules** (e.g., `steam_errors`, `json_parser`, `core`)
- **System/Third-party libraries** (marked as `[SKIP:*]` for easy exclusion)

## How It Works

### Layer 1: Pattern Matching (Highest Priority)

System library functions are identified by naming patterns:
```
sub.msvcrt.dll_*  → [SKIP: msvcrt]
sym.imp.*          → [SKIP: <dll_name>]
sub.*              → [SKIP: thirdparty]
```

### Layer 2: String Content Matching

Functions are classified based on string literals they reference:
```
References "Invalid_Password", "Steam"        → steam_errors
References "parse_error", "syntax_error"    → json_parser
References "Usage:", "--help"                → cli_parser
```

### Layer 3: Propagation (Optional, Limited)

Functions are classified based on their relationship to already-classified "seed functions":
- **Upward propagation**: If `func_A` calls `func_B` (which is `steam_errors`), `func_A` may also be steam-related
- **Downward propagation**: If `func_A` (which is `steam_errors`) calls `func_C`, `func_C` may also be steam-related

**Constraints** (to avoid over-propagation):
- Propagation depth: 1 (direct neighbors only)
- Maximum propagated functions: 50
- Only propagates to low-degree functions (avoid affecting hub nodes)

### Layer 4: Graph Structure Analysis

Fallback classification based on call graph patterns:
```
High inbound (50+), zero outbound → [SKIP: library_leaf]
High outbound (20+)                → core (orchestrator)
High inbound (50+), low outbound   → [SKIP: wrapper]
etc.
```

## Usage

### Automatic (Recommended)

Just run `init-project.sh` as usual:

```bash
scripts/init-project.sh ./binary phase1
```

The classifier will automatically:
1. Analyze the callgraph and string references
2. Classify all functions
3. Generate `mapping.tsv` with classifications
4. Create `phase1/classification_summary.md` with statistics

`init-project.sh` also creates a fill-in rules file for conservative library/runtime triage after the graph classifier:

```bash
python3 scripts/triage_library_candidates.py \
    --init-rules phase1/library_triage_rules.json
```

The executing agent must fill project-specific rules, then run:

```bash
python3 scripts/triage_library_candidates.py \
    --rules phase1/library_triage_rules.json \
    --output-tsv phase1/library_triage_candidates.tsv \
    --output-md phase1/library_triage_candidates.md
```

This pass is advisory. Built-in rules are intentionally small and focus on generic C/C++ runtime signals. Project-specific third-party rules and application markers belong in `phase1/library_triage_rules.json`. The script does **not** modify `mapping.tsv`.

### Manual (Advanced)

If you want to re-run classification with different parameters:

```bash
# With string references
python3 scripts/classify_functions.py \
    phase1/callgraph.json \
    phase1/string_xref.md \
    mapping.tsv \
    mapping.tsv.new

# Without string references (graph-only)
python3 scripts/classify_functions.py \
    phase1/callgraph.json \
    none \
    mapping.tsv \
    mapping.tsv.new
```

## Output Format

### mapping.tsv

```
address           original_name         clean_name              module
0x140001131      fcn.140001131         orchestrator            core
0x14002bc70      sub.msvcrt.dll_malloc malloc                  [SKIP: msvcrt]
0x1400035c0      fcn.1400035c0         steam_errors_func       steam_errors
0x14015e770      fcn.14015e770         library_function        [SKIP: library_leaf]
```

- **address**: Function address
- **original_name**: Name from r2 (e.g., `fcn.140001131`)
- **clean_name**: Human-readable name for documentation
- **module**:
  - `[SKIP:*]`: System/third-party (can be skipped in Phase 2)
  - Application module names (core, steam_errors, etc.)
  - `unknown`: Needs further analysis

### classification_summary.md

Generated report with:
- Category statistics
- Top functions per category
- Coverage percentages

## Configuration

### Adjusting Propagation Parameters

Edit `scripts/classify_functions.py`:

```python
# Around line 180-190
max_depth = 1          # Propagation depth (1 = direct neighbors)
max_propagated = 50    # Max functions to propagate
in_degree_limit = 10   # Max callers for upward propagation
out_degree_limit = 5  # Max callees for downward propagation
```

### Custom Module Keywords

Edit the `module_keywords` dictionary (around line 60):

```python
self.module_keywords = {
    'your_module': {
        'required': ['keyword1', 'keyword2'],  # Must match
        'optional': ['keyword3']                 # Optional match
    },
}
```

## Classification Categories

### System/Third-Party (Marked [SKIP:*])

| Category | Description | Examples |
|----------|-------------|----------|
| `[SKIP: msvcrt]` | MSVCRT standard library | malloc, free, strlen |
| `[SKIP: KERNEL32]` | Windows API | CreateFile, ReadFile |
| `[SKIP: WS2_32]` | Windows Sockets | WSAStartup, socket |
| `[SKIP: library_leaf]` | High inbound, no outbound | Utility functions |
| `[SKIP: wrapper]` | High inbound, low outbound | Library wrappers |

### Application Modules

| Category | Description | Typical Functions |
|----------|-------------|------------------|
| `core` | Main orchestration | main, orchestrator, initializer |
| `steam_errors` | Steam API error handling | Invalid_Password handlers |
| `json_parser` | JSON parsing | parse_error, syntax_error handlers |
| `cli_parser` | Command-line interface | Usage: display, --help |
| `filesystem` | File operations | File I/O, path handling |
| `config` | Configuration management | Config file loading |
| `network` | Network operations | Socket operations |
| `logging` | Logging functionality | Log message formatting |

## Tips & Best Practices

### 1. Review Classification Before Phase 2

Always review `mapping.tsv` and the library triage report before proceeding to Phase 2:

```bash
# Check classification coverage
cut -f4 mapping.tsv | sort | uniq -c | sort -rn

# Review specific categories
grep $'\tsteam_errors$' mapping.tsv
grep $'\tcore$' mapping.tsv
grep $'\[SKIP:' mapping.tsv
```

Review order:

1. Fill `phase1/library_triage_rules.json` with project-specific `application_markers` and confirmed third-party patterns.
2. Run `scripts/triage_library_candidates.py --rules phase1/library_triage_rules.json`.
3. Confirm `REVIEW_SKIP` entries in `phase1/library_triage_candidates.md`.
4. Inspect `AI_REVIEW` entries in small batches.
5. Update `mapping.tsv` only after confirming the function is not application logic.
6. Add confirmed third-party/runtime signatures to `context/global_map.md`.

### 2. Adjust for Your Binary

If classification doesn't match your binary:

1. **Add custom keywords** - Edit `module_keywords` in the script
2. **Adjust propagation** - Lower `max_propagated` for tighter control
3. **Review callgraph** - Check `phase1/callgraph_summary.md` for patterns

### 3. Quality Checks

- **Good**: < 30% unknown, < 20% [SKIP:*]
- **Acceptable**: 30-50% unknown
- **Poor**: > 50% unknown (may need manual adjustment)

## Troubleshooting

### Classification Failed

**Error**: `classification failed, using basic mapping`

**Solutions**:
1. Check if `callgraph.json` exists: `ls phase1/callgraph.json`
2. Verify Python 3.6+ is available: `python3 --version`
3. Check for Python syntax errors in the script

### Over-Propagation

**Symptom**: Too many functions classified into one module

**Solution**:
1. Lower `max_propagated` (line 190)
2. Reduce `max_depth` to 1 (line 188)
3. Increase `in_degree_limit` and `out_degree_limit` (lines 280-285)

### Poor Classification

**Symptom**: Too many "unknown" functions

**Possible Causes**:
1. Binary is heavily stripped (no string references)
2. Unusual architecture (not following common patterns)

**Solutions**:
1. Manually classify a few "seed functions" and re-run
2. Adjust `module_keywords` to match your binary
3. Use graph-only mode (no string references)

## Examples

### Example 1: Steam Client

```bash
scripts/init-project.sh ./steam.exe phase1

# Results:
# - steam_errors: 16 functions
# - json_parser: 12 functions
# - core: 390 functions
# - [SKIP: msvcrt]: 90 functions
# - Unknown: 307 functions (21%)
```

### Example 2: Stripped Binary

```bash
scripts/init-project.sh ./stripped_binary phase1

# Results:
# - No string references → graph-only classification
# - core: 450 functions
# - [SKIP: library_leaf]: 30 functions
# - Unknown: 600 functions (40%)
```

## See Also

- `Phase 1 Exploratory Analysis` - Overall Phase 1 workflow
- `mapping.tsv` - Function classification mapping
- `phase1/callgraph_summary.md` - Call graph analysis for classification
- `Phase 2: Raw Decompilation` - How to use classification results
