# <Project Name> Reverse Engineering Project Summary

## Project Overview
[Brief description of what was reverse engineered]

## Binary Information
- **File**: <path_to_binary>
- **Type**: ELF/PE, architecture, stripped/unstripped
- **Total Functions**: N
- **Application Functions**: N
- **Modules**: N

## Analysis Workflow
### Phase 1: Exploratory Analysis
[Summary of findings]

### Phase 2: Decompilation
[Number of functions decompiled]

### Phase 3: Module Formation
[Modules identified and their purposes]

### Phase 4: Renaming and Organization
[How functions were organized]

### Phase 5: AI Cleanup
[Cleanup approach and results]

## Architecture
[High-level architecture description]

## Module Overview
### Module 1: <name>
- Purpose
- Key functions
- Responsibilities

### Module 2: <name>
...

## Key Findings
[Important discoveries about the binary]

## Statistics
- Total files: N
- Total lines of code: ~N
- Modules: N
- Cleanup reduction: X%

## Deliverables
1. phase1/function_classification.md
2. clean/raw/ - Original decompiled code (renamed)
3. clean/src/ - Cleaned source code
4. scripts/verify_cleanup.sh
5. mapping.tsv
6. docs/project_summary.md

## Quality Assurance
- Mechanical verification: command, result, address/digest coverage and any literal review exceptions
- Compilation: compiler/architecture, declared ABI, external dependencies and actual result
- Behavior checks: inputs/boundaries tested, mocks used, and actual result
- Evidence review: suspicious reductions, merged branches, missing parameters and inferred types
- Unverified behavior: unexecuted target paths, concurrency, invalid inputs and unresolved ABI differences

Report only checks actually performed. A mechanical pass, successful build or
stubbed dependency test does not establish complete original-binary equivalence.

## Conclusion
[Summary of project completion]
