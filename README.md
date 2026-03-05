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

### 🎮 Gaming Tools

#### epic-cli

Epic Games library management CLI tool. Browse, install, launch, sync saves, and manage your Epic Games library from the terminal using Legendary.

**Use when:** You want to manage Epic Games, install games, sync cloud saves, or browse your Epic collection.

**Features:**
- List and browse your Epic Games library
- Install and launch games
- Sync cloud saves
- Check for updates
- Cross-platform support (Linux, macOS, Windows)

**Documentation:** See [skills/epic-cli/SKILL.md](skills/epic-cli/SKILL.md) for detailed usage.

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
