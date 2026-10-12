# Installation & Tooling

## Prerequisites

### Linux (apt):
```bash
apt update
apt install -y radare2 binutils python3 python3-pip file jq build-essential git
```

### macOS (Homebrew):
```bash
brew install radare2 binutils python3 jq
```

### radare2 plugins:
```bash
r2pm init
r2pm -U
r2pm -ci r2ghidra   # Native Ghidra decompiler for radare2
```

### Optional but recommended: REA + full Ghidra (top engine level)

The workflow's best decompiler level drives a full Ghidra install through
the REA (`rea-agents`) MCP server. Install once per machine:

```bash
# 1. rea-agents CLI (Node >= 24.11)
npm install --global rea-agents

# 2. Ghidra 12.1.x (needs JDK 21+), then export the install dir, e.g. in ~/.zshenv
export GHIDRA_INSTALL_DIR="$HOME/tools/ghidra_12.1.4_PUBLIC"

# 3. register the MCP server for your agent + install the companion skill
rea setup --client codex --yes     # or your agent's name
```

Without REA/Ghidra the skill degrades gracefully to r2ghidra (`pdg`) and
radare2 (`pdc`); with it, each batch opens one shared `rea mcp` session and
decompiles via the `ghidra` method first (see SKILL.md "Engine Ladder").

## Verify Installation

```bash
# Core tools
which r2 file python3 && r2 -v | head -1

# Decompiler ladder: r2ghidra level
r2 -q -c "aaa; pdg @ main" /path/to/binary && echo "✓ r2ghidra works"

# Decompiler ladder: REA/Ghidra level (optional)
which rea && rea --version && rea doctor 2>&1 | grep -E "ghidra" | head -3
```
