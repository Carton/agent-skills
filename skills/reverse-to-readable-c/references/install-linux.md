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

## Verify Installation

```bash
# Core tools
which r2 file python3 && r2 -v | head -1

# Decompiler
r2 -q -c "aaa; pdg @ main" /path/to/binary && echo "✓ r2ghidra works"
```
