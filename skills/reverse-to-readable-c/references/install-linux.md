# Linux Install

This skill assumes Linux because radare2, r2pm, build tooling, and headless automation are easiest to manage there.

## Baseline

```bash
sudo apt update
sudo apt install -y \
  build-essential pkg-config git patch curl unzip zip \
  python3 python3-pip file jq \
  gdb binutils strace ltrace \
  radare2
```

If your distro provides `radare2-dev`, install it too when building `r2ghidra` from `r2pm`.

## r2pm and r2ghidra

```bash
r2pm init || true
r2pm -U
r2pm -ci r2ghidra
```

If `r2ghidra` build fails, check for missing:

- `pkg-config`
- C/C++ compiler toolchain
- `git`
- `patch`
- `meson` / `ninja-build` or `make`

If needed:

```bash
sudo apt install -y meson ninja-build
```

## Optional Ghidra

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

## Optional Packages By Target Type

### Packed binaries

```bash
sudo apt install -y upx
```

### Windows PE runtime observation on Linux

```bash
sudo apt install -y wine
```

Use this only when static analysis is not enough and you need to observe PE startup, loader behavior, or basic file/config interactions under Linux.

### Android packages

```bash
sudo apt install -y apktool
```

### Extra archive formats and installers

```bash
sudo apt install -y p7zip-full cabextract
```

### Cross-architecture ELF debugging

```bash
sudo apt install -y gdb-multiarch
```

## Notes

- `radare2` from distro packages is acceptable for a baseline, but newer releases may behave better with plugins and decompilation.
- For PE or ELF recovery-to-C workflows, `radare2 + r2ghidra` is a solid static-analysis baseline. Full Ghidra is recommended for validation and bulk/headless workflows, not because `r2ghidra` requires it.
- `r2ghidra` does not require the full Ghidra application.
- Full Ghidra is still useful for validation, project databases, datatype recovery, and headless batch analysis.
