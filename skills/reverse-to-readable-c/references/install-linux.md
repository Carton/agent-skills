# Linux Install & Tooling

Complete installation and troubleshooting guide for all tools used by the reverse-to-readable-c skill.

## Prerequisites Check

**Before starting**, verify that required tools are installed:

```bash
#!/bin/bash
# Tool check script - save as check_tools.sh

check_tool () {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 not found"
        return 1
    else
        echo "✓ $1 installed: $(which $1)"
        return 0
    fi
}

echo "=== Required Tools ==="
check_tool r2 || { echo "Please install radare2 first"; exit 1; }
check_tool file || { echo "Please install file command first"; exit 1; }
check_tool python3 || { echo "Please install python3 first"; exit 1; }

echo ""
echo "=== Optional Tools ==="
check_tool jq || echo "⚠️  jq not installed (recommended for JSON processing)"
check_tool strings || echo "⚠️  strings not installed (part of binutils)"

echo ""
echo "=== r2ghidra Decompiler Check ==="
R2_VERSION=$(r2 -v | head -1 | awk '{print $2}')
echo "radare2 version: $R2_VERSION"

# Check if r2ghidra plugin is compiled
if [ -f ~/.local/share/radare2/r2pm/git/r2ghidra/src/core_ghidra.so ]; then
    echo "✓ r2ghidra plugin compiled"
else
    echo "❌ r2ghidra plugin not compiled"
    echo "Run: cd ~/.local/share/radare2/r2pm/git/r2ghidra && make && sudo make install"
fi

# Create test file to verify decompilation
echo "int main() { return 0; }" > /tmp/test_r2.c
gcc /tmp/test_r2.c -o /tmp/test_r2 2>/dev/null
if r2 -q -c "aaa; pdg @ main" /tmp/test_r2 &> /dev/null; then
    echo "✓ r2ghidra decompilation works"
else
    echo "❌ r2ghidra decompilation not working"
fi
rm -f /tmp/test_r2.c /tmp/test_r2
```

**Quick check** (one-liner):
```bash
check_tools () { which r2 && which file && which python3 && r2 -v | head -1; }; check_tools && echo "✓ Basic tools OK"
```

## Tooling Setup

Assume a Linux execution environment. Install a minimal baseline first, then add optional tools by target type.

### Minimal Baseline

Use the system package manager for core tooling:

```bash
sudo apt update
sudo apt install -y \
  build-essential pkg-config git patch curl unzip zip \
  python3 python3-pip file jq \
  gdb binutils strace ltrace \
  radare2
```

If your distribution splits headers into a separate package, install the radare2 development package too before building plugins.

Initialize and update `r2pm`, then install and compile `r2ghidra`:

```bash
# 1. Download r2ghidra source
r2pm init || true
r2pm -U
r2pm -ci r2ghidra

# 2. Build and install (IMPORTANT: must be done manually)
cd ~/.local/share/radare2/r2pm/git/r2ghidra
make
sudo make install

# 3. Verify installation
r2 -q -c "pdg --help" # requires a file to be opened, see verification below
```

### Verify Installation

Verify that the toolchain works correctly:

```bash
# Create test binary
echo 'int main() { return 0; }' > /tmp/test_r2.c
gcc /tmp/test_r2.c -o /tmp/test_r2 2>/dev/null

# Test radare2 basic functionality
r2 -q -c "aaa; afl" /tmp/test_r2 && echo "✓ radare2 analysis works"

# Test r2ghidra decompilation
r2 -q -c "pdg @ main" /tmp/test_r2 && echo "✓ r2ghidra decompilation works"

# Cleanup
rm -f /tmp/test_r2.c /tmp/test_r2
```

**Checklist**:
- [ ] `which r2` - radare2 executable exists
- [ ] `r2 -v` - shows version info
- [ ] `which file` - file command available
- [ ] `ls ~/.local/share/radare2/r2pm/git/r2ghidra/src/*.so` - r2ghidra compiled
- [ ] `r2 -q -c "pdg @ main" <binary>` - decompilation works

## Troubleshooting r2ghidra Installation

If `r2pm -ci r2ghidra` build fails, check for missing dependencies:

- `pkg-config`
- C/C++ compiler toolchain
- `git`
- `patch`
- `meson` / `ninja-build` or `make`

If needed:

```bash
sudo apt install -y meson ninja-build
```

## Optional & Target-Specific Tools

Depending on your target, you may need additional tools:

- **Analysis/Validation**: `ghidra` (highly recommended for validation and headless analysis)
- **Target Observation**: `wine` (for PE), `apktool` (for Android)
- **Unpacking/Utilities**: `upx`, `p7zip-full`, `cabextract`
- **Multi-arch Debugging**: `gdb-multiarch`

### Optional Ghidra

Install a supported JDK first, then extract Ghidra somewhere under your home directory or tool root.

Typical flow:

```bash
sudo apt install -y openjdk-21-jdk
tar -xf ghidra_<version>_PUBLIC_<platform>.tar.gz
./ghidra_<version>_PUBLIC/ghidraRun
```

For headless analysis:

```bash
./ghidra_<version>_PUBLIC/support/analyzeHeadless <project-dir> <project-name> \
  -import <binary>
```

### Optional Packages By Target Type

#### Packed binaries

```bash
sudo apt install -y upx
```

#### Windows PE runtime observation on Linux

```bash
sudo apt install -y wine
```

Use this only when static analysis is not enough and you need to observe PE startup, loader behavior, or basic file/config interactions under Linux.

#### Android packages

```bash
sudo apt install -y apktool
```

#### Extra archive formats and installers

```bash
sudo apt install -y p7zip-full cabextract
```

#### Cross-architecture ELF debugging

```bash
sudo apt install -y gdb-multiarch
```

## Notes

- `radare2` from distro packages is acceptable for a baseline, but newer releases may behave better with plugins and decompilation.
- For PE or ELF recovery-to-C workflows, `radare2 + r2ghidra` is a solid static-analysis baseline. Full Ghidra is recommended for validation and bulk/headless workflows, not because `r2ghidra` requires it.
- `r2ghidra` does not require the full Ghidra application.
- Full Ghidra is still useful for validation, project databases, datatype recovery, and headless batch analysis.
