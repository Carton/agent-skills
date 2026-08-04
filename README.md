# Agent Skills

English | [简体中文](README.zh.md)

> A collection of useful agent skills for AI-powered development tools.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/carton/agent-skills?style=social)](https://github.com/carton/agent-skills)

## Overview

This repository contains a collection of reusable agent skills designed to extend the capabilities of AI coding assistants like Claude Code, Cursor, and other compatible tools.

## Quick Start

### Installation

#### Option 1: Using npx skills (Recommended)

```bash
npx skills add carton/agent-skills
```

#### Option 2: Register as Plugin Marketplace

Run the following command in Claude Code:

```
/plugin marketplace add carton/agent-skills
```

Then browse and install available skills:

```
/plugin
```

Navigate to **Marketplaces** tab → Select **agent-skills** → Install desired skills

#### Option 3: Manual Installation

```bash
# Clone the repository
git clone https://github.com/carton/agent-skills.git

# Copy skills to your Claude skills directory
cp -r agent-skills/skills/* ~/.claude/skills/
```

### Usage

Once installed, skills are automatically available. You can invoke them by name:

```
Please help me manage my Epic Games library
```

Claude will automatically load and use the appropriate skill.

## Available Skills

### 🎮 Game libraries and store tools

#### [epic-cli](skills/epic-cli/SKILL.md)

Manage an Epic Games library from the terminal with Legendary.

**Use when:** Browsing owned Epic games, installing or launching a title, checking updates, or syncing cloud saves.

#### [steam-cli](skills/steam-cli/SKILL.md)

Work with a self-owned Steam library, Steam store data, and installation-size estimates.

**Use when:** Finding unplayed games, checking playtime, exporting an owned-game list, researching store details or regional prices, or checking the disk space a game needs.

### 📱 Android diagnostics

#### [android-logcat-analyzer](skills/android-logcat-analyzer/SKILL.md)

Analyze Android logcat output to identify crashes, ANRs, memory issues, and performance problems.

**Use when:** An Android app crashes, freezes with an ANR, is killed unexpectedly, leaks memory, or suffers from stutter or lag.

### 🔧 Development workflow

#### [commit-message](skills/commit-message/SKILL.md)

Create accurate Conventional Commit messages from the actual Git diff.

**Use when:** Writing or reviewing a commit subject and body, or preparing a squash commit message.

#### [reverse-to-readable-c](skills/reverse-to-readable-c/SKILL.md)

Turn a native PE or ELF binary into an organized, maintainable C source tree through a phased reverse-engineering workflow.

**Use when:** Exploring a binary, classifying functions, decompiling modules, renaming symbols, or cleaning decompiler output into readable C.

### 📝 Content archiving

#### [make-bilibili-notes](skills/make-bilibili-notes/SKILL.md)

Convert a Bilibili video into a timestamped, traceable Obsidian Markdown note.

**Use when:** Summarizing, transcribing, fact-checking, or archiving a Bilibili video; the workflow prioritizes official subtitles, then hard-subtitle OCR, then audio transcription.

## Development

### Local Testing

To test skills locally:

```bash
# Create a symlink to your skills directory
ln -s /path/to/agent-skills/skills/* ~/.claude/skills/
```

### Validation

Skills are automatically validated to ensure:
- Valid frontmatter format
- Required fields (name, description)
- Proper markdown structure

## Roadmap

- [ ] Add more gaming platform integrations
- [ ] Add development tooling skills
- [ ] Add content generation skills
- [ ] Add automation utilities

## Inspiration

This repository is inspired by:
- [baoyu-skills](https://github.com/JimLiu/baoyu-skills) by Jim Liu
- [agent-skills](https://github.com/vercel-labs/agent-skills) by Vercel Labs

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built for the Claude Code ecosystem
- Powered by the [Agent Skills Specification](https://github.com/agent-skills/spec)
- Part of the broader skills marketplace ecosystem

---

Made with ❤️ by [Carton He](https://github.com/carton)
