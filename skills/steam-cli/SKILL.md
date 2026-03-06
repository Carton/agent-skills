---
name: steam-cli
description: Steam game library management CLI tool. Use when user wants to browse, filter, search, or manage their Steam game library from the terminal - finding unplayed games, checking playtime, filtering by reviews, or discovering hidden gems. Also covers Steam Deck playtime tracking and user profile statistics.
---

# Steam CLI

Steam CLI (`steam-games-cli`) is a command-line tool for browsing, filtering, and discovering games in a Steam library. Use this skill when the user wants to find hidden gems, track playtime, manage their Steam collection, or get game statistics from the terminal.

## Installation

Prerequisites:
- Node.js 18+
- Steam Web API key (get one at https://steamcommunity.com/dev/apikey)

Install globally:
```bash
npm install -g steam-games-cli
```

## Initial Setup

Before using the tool, configure the API key and Steam user:

```bash
steam config set-key YOUR_API_KEY
steam config set-user YOUR_STEAM_ID
```

The Steam ID can be found in the URL of the user's Steam profile (e.g., `76561198012345678`).

Config is stored in `~/.steam-cli/config.json` or via `STEAM_API_KEY` environment variable.

## Privacy Requirement

The Steam profile's "Game details" must be set to Public:
- Visit: https://steamcommunity.com/my/edit/settings
- Privacy Settings → Game details → Public

## Commands Overview

| Command | Description |
|---------|-------------|
| `steam whoami` | Show current user profile and stats |
| `steam library` | Browse and filter game library |
| `steam tags` | List all Steam tags (instant) |
| `steam genres` | List all Steam genres (instant) |
| `steam config` | Manage configuration |

## Common Use Cases

### Profile Information

```bash
# Show Steam profile and library stats
steam whoami

# JSON output for scripting
steam whoami --json
```

### Basic Library Browsing

```bash
# List all games
steam library

# Show top 10 most-played games
steam library --sort playtime --limit 10

# Find unplayed games (hidden gems)
steam library --unplayed --limit 20

# Games with 10-50 hours of playtime
steam library --min-hours 10 --max-hours 50
```

### Review-Based Filtering

Review categories (score 1-9 scale):
- `overwhelmingly-positive` (9)
- `very-positive` (8)
- `positive` (7)
- `mostly-positive` (6)
- `mixed` (5)
- `mostly-negative` (4)
- `negative` (3)
- `very-negative` (2)
- `overwhelmingly-negative` (1)

```bash
# Show only Very Positive games
steam library --reviews very-positive --limit 10

# Show Overwhelmingly Positive with reviews column
steam library --reviews overwhelmingly-positive --show-reviews

# Filter by review score (1-9 scale)
steam library --min-reviews 7 --show-reviews --limit 10

# Sort by review score (best first)
steam library --sort reviews --show-reviews --limit 10

# Combine: well-reviewed games you haven't played much
steam library --max-hours 5 --min-reviews 8 --show-reviews
```

### Steam Deck Commands

```bash
# Show only games played on Steam Deck
steam library --deck --limit 10

# Sort by most-played on Deck
steam library --deck --sort deck

# Show Deck playtime column
steam library --deck-hours --limit 5
```

### Output Formats

```bash
# Table format (default)
steam library --limit 5

# Plain list (great for scripting)
steam library --plain --limit 5

# JSON output
steam library --json --limit 5
```

## Command Reference

### `steam library [options]`

| Option | Description |
|--------|-------------|
| `-l, --limit <n>` | Limit number of results |
| `--unplayed` | Show only unplayed games |
| `--min-hours <h>` | Minimum playtime in hours |
| `--max-hours <h>` | Maximum playtime in hours |
| `--deck` | Only games played on Steam Deck |
| `--deck-hours` | Show Deck playtime column |
| `--reviews <cat>` | Filter by review category |
| `--min-reviews <n>` | Minimum review score (1-9) |
| `--max-reviews <n>` | Maximum review score (1-9) |
| `--show-reviews` | Show review column |
| `--sort <field>` | Sort by: name, playtime, deck, reviews |
| `--plain` | Plain list output |
| `--json` | JSON output |

### `steam config <command>`

| Command | Description |
|----------|-------------|
| `set-key <key>` | Set Steam Web API key |
| `set-user <id>` | Set Steam ID or username |
| `show` | Display current config |

## Performance Tips

Review data requires individual API calls per game. For better performance:

```bash
# Fast: filters first, then fetches reviews for fewer games
steam library --min-hours 10 --reviews very-positive

# Slow: fetches reviews for all games
steam library --reviews very-positive
```

Apply other filters (playtime, unplayed, deck) before using review filters to reduce the number of API calls needed.

## Troubleshooting

### Empty game list
- Ensure Steam profile's "Game details" is set to Public
- Verify API key is correctly configured with `steam config show`

### Review fetching is slow
- Use other filters first to reduce the number of games before fetching reviews

## Resources

For more detailed command examples and advanced usage, see:
- GitHub repository: https://github.com/mjrussell/steam-cli
- Author: Matt Russell
- License: MIT
