# Contributing to Agent Skills

Thank you for your interest in contributing to this collection of agent skills! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Skill Structure](#skill-structure)
- [SKILL.md Format](#skillmd-format)
- [Adding a New Skill](#adding-a-new-skill)
- [Testing Your Skill](#testing-your-skill)
- [Submission Guidelines](#submission-guidelines)
- [Code of Conduct](#code-of-conduct)

## Getting Started

### Prerequisites

- Basic understanding of Markdown
- Familiarity with AI coding assistants (Claude Code, Cursor, etc.)
- Git and GitHub knowledge

### Setting Up

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/carton/agent-skills.git
   cd agent-skills
   ```

3. Create a new branch:
   ```bash
   git checkout -b add-my-skill
   ```

## Skill Structure

Each skill should follow this directory structure:

```
skills/
└── your-skill/
    ├── SKILL.md          # Required: Main skill definition
    ├── assets/           # Optional: Images, diagrams, etc.
    ├── scripts/          # Optional: Helper scripts
    └── examples/         # Optional: Example files
```

## SKILL.md Format

Every `SKILL.md` file must start with YAML frontmatter:

```markdown
---
name: your-skill-name
description: A clear, concise description of when to use this skill (under 100 characters)
---

# Your Skill Title

A brief introduction to what this skill does.

## Usage

```bash
/example-command
```

## When to Use This Skill

Use this skill when:
- User needs to do X
- Working with Y technology
- Solving Z problem

## Features

- Feature 1
- Feature 2
- Feature 3

## Examples

### Example 1: Basic Usage

```bash
command with options
```

### Example 2: Advanced Usage

```bash
command with advanced options
```

## Requirements

- Prerequisite 1
- Prerequisite 2

## Configuration

If applicable, explain configuration options.

## Troubleshooting

Common issues and solutions.

## Resources

- [Official Documentation](link)
- [Related Tools](link)
```

### Required Frontmatter Fields

- **name**: Technical identifier (kebab-case, no spaces)
- **description**: When to use this skill (shown to AI)

### Description Best Practices

✅ Good descriptions:
- "Use when user wants to manage Epic Games library from terminal"
- "Convert PDF documents to markdown format with tables preserved"
- "Generate production-ready React components with Tailwind CSS"

❌ Bad descriptions:
- "A cool tool for games" (too vague)
- "This skill helps you do stuff" (not specific)
- "PDF converter" (missing context)

## Adding a New Skill

### Step 1: Create Directory

```bash
mkdir -p skills/your-skill-name
```

### Step 2: Create SKILL.md

Create a `SKILL.md` file following the format above.

### Step 3: Add Optional Files

If your skill needs additional resources:
- **assets/**: Images, diagrams
- **scripts/**: Helper scripts or tools
- **examples/**: Example usage files

### Step 4: Update marketplace.json

Add your skill to `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    {
      "name": "category-name",
      "description": "Category description",
      "source": "./",
      "strict": false,
      "skills": [
        "./skills/your-skill-name"
      ]
    }
  ]
}
```

### Step 5: Update README

Add your skill to the appropriate section in `README.md`:

```markdown
#### your-skill-name

Brief description of what this skill does.

**Use when:** When to use this skill.

**Features:**
- Feature 1
- Feature 2

**Documentation:** See [skills/your-skill-name/SKILL.md](skills/your-skill-name/SKILL.md)
```

## Testing Your Skill

### Local Testing

1. Create a symlink to test:
   ```bash
   ln -s $(pwd)/skills/your-skill-name ~/.claude/skills/
   ```

2. Open Claude Code and test your skill:
   ```
   Tell me about your-skill-name
   ```

3. Verify the AI can:
   - Load the skill
   - Understand when to use it
   - Follow the instructions

### Validation Checklist

Before submitting, ensure your skill:
- [ ] Has valid YAML frontmatter
- [ ] Includes `name` and `description` fields
- [ ] Description is clear and specific
- [ ] Follows the SKILL.md template
- [ ] Has been tested locally
- [ ] Is documented in README.md
- [ ] Is added to marketplace.json

## Submission Guidelines

### Pull Request Process

1. Update your branch with latest main:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. Commit your changes:
   ```bash
   git add .
   git commit -m "Add: new-skill-name skill"
   ```

3. Push and create PR:
   ```bash
   git push origin add-my-skill
   ```

4. Create a pull request with:
   - Title: `Add: [skill-name]`
   - Description: What the skill does and how to use it
   - Link to any relevant resources

### Review Criteria

PRs are reviewed based on:
- ✅ Follows skill structure
- ✅ Clear and useful description
- ✅ Well-documented with examples
- ✅ Tested and working
- ✅ Adds unique value

### What We're Looking For

We welcome skills that:
- Solve real problems
- Are well-documented
- Have clear use cases
- Work reliably
- Add value to the ecosystem

### What We Don't Accept

- Duplicate functionality (unless significantly better)
- Poorly documented skills
- Broken or untested code
- Controversial or harmful content

## Skill Categories

Consider organizing your skill into one of these categories:

### Development Tools
- Language-specific tools (Python, JavaScript, etc.)
- Framework helpers (React, Vue, etc.)
- Testing utilities
- Code generators

### Productivity
- Task automation
- File management
- Documentation tools
- Note-taking helpers

### Content Creation
- Writing assistants
- Image generation
- Video tools
- Audio processing

### Data & APIs
- API integrations
- Data processing
- Database tools
- Scraping utilities

### Gaming
- Game platform tools
- Mod management
- Launcher utilities

### System
- System administration
- DevOps tools
- Monitoring utilities
- Security tools

## Getting Help

If you need help:
- Open an issue with your question
- Join our discussions (link coming soon)
- Check existing skills for examples

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Credited in the skill's SKILL.md
- Mentioned in release notes

Thank you for contributing! 🎉

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn
- Follow GitHub's Community Guidelines

---

For questions, please open an issue or contact maintainers.
