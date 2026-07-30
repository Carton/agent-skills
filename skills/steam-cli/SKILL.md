---
name: steam-cli
description: Steam game library management and store-query CLI tools. Use when the user wants to export or manage their self-owned Steam games (browse, filter, search, find unplayed games, check playtime), query Steam store information (search games, get details, check prices), or estimate a game's required installation disk space by App ID. Covers steam-games-cli, steam-game-query, explicit-config library export, and a bundled install-size helper.
---

# Steam CLI Tools

This skill provides guidance for two complementary Steam CLI tools and two bundled helpers:

1. **steam-games-cli** - Manage the self-owned games returned by Steam Web API
2. **steam-game-query** - Query Steam store game information (no login required)
3. **export_owned_games.py** - Export a complete self-owned library from an explicit config
4. **get_install_size.py** - Estimate publisher-declared required disk space by App ID

## When to Use Each Tool

### Use steam-games-cli when:
- Browsing the self-owned games visible through Steam Web API
- Finding unplayed games in your collection
- Checking playtime statistics
- Filtering games by review scores
- Managing Steam Deck playtime tracking
- Getting user profile statistics

### Use export_owned_games.py when:
- Exporting every API-visible self-owned game to JSON or CSV
- Selecting a specific `steam-games-cli` config without changing global configuration
- Verifying that Steam's reported `game_count` matches the returned game list

### Use steam-game-query when:
- Searching for games on the Steam store
- Getting detailed game information (price, release date, developer, etc.)
- Checking regional pricing
- Querying game details without Steam login
- Batch querying multiple games
- Researching games before purchase

### Use get_install_size.py when:
- Estimating required free disk space before installation
- Looking up a storage requirement by Steam App ID
- Resolving a DLC's requirement through its base game

## Quick Reference

### steam-games-cli (User Library)

Requires: Node.js 18+, Steam Web API key, public Steam profile

```bash
# Installation
npm install -g steam-games-cli

# Setup
steam config set-key YOUR_API_KEY
steam config set-user YOUR_STEAM_ID

# Common commands
steam whoami                    # Show profile stats
steam library                   # List API-visible self-owned games
steam library --unplayed        # Find unplayed games
steam library --sort playtime   # Most played games
```

`GetOwnedGames` does not include Steam Families shared games. Do not describe its result as the
complete playable library when family sharing may be involved.

### Explicit-Config Library Export

Requires: Python 3.10+, a `steam-games-cli` config containing `apiKey` and `steamId`

```bash
# Run from the steam-cli skill directory
python3 scripts/export_owned_games.py --format csv --output steam-games.csv

# Select another environment's config without overwriting the default config
python3 scripts/export_owned_games.py \
  --config /path/to/.steam-cli/config.json \
  --format json \
  --output steam-games.json
```

### steam-game-query (Store Queries)

Requires: Python 3.10+, no login/API key needed

```bash
# Installation
pip install steam-game-query

# Common commands
steam-query search "Elden Ring"              # Search games
steam-query lookup 1245620                   # Get game details by App ID
steam-query lookup -q "Hollow Knight"        # Search and lookup by name
steam-query batch "Game1" "Game2" -o out.json  # Batch query
```

### Install Size Estimate

Requires: Python 3.10+, no third-party packages or Steam login

```bash
# Run from the steam-cli skill directory
python3 scripts/get_install_size.py 1113000
python3 scripts/get_install_size.py 2612950 --json
```

## Decision Guide

| Task | Tool |
|------|------|
| "Show my self-owned games" | steam-games-cli |
| "Export all owned games from a specific config" | export_owned_games.py |
| "Find unplayed games in my library" | steam-games-cli |
| "Search Steam store for games" | steam-game-query |
| "Check price of a game" | steam-game-query |
| "Get my playtime stats" | steam-games-cli |
| "Get game details (developer, genres, etc.)" | steam-game-query |
| "Estimate required installation disk space" | get_install_size.py |
| "Filter my library by reviews" | steam-games-cli |
| "Compare regional pricing" | steam-game-query |

## Common Workflows

### Workflow 1: Research and Purchase Decision

Use steam-game-query to research games before purchasing:

```bash
# Search for games
steam-query search "action RPG" -l 20

# Get detailed info
steam-query lookup -q "Elden Ring"

# Check pricing in different regions
steam-query lookup 1245620 --country US --json | jq '.price'
steam-query lookup 1245620 --country CN --json | jq '.price'
```

### Workflow 2: Manage Your Library

Use steam-games-cli to manage your existing games:

```bash
# Find hidden gems (well-reviewed, unplayed games)
steam library --unplayed --min-reviews 8 --show-reviews

# Check Steam Deck playtime
steam library --deck --sort deck

# See your profile stats
steam whoami
```

### Workflow 3: Batch Export Your Library

```bash
# Export from the default config
python3 scripts/export_owned_games.py --output my_library.json

# Export from an explicit config without changing `steam config`
python3 scripts/export_owned_games.py \
  --config /path/to/.steam-cli/config.json \
  --format csv \
  --output my_library.csv
```

### Workflow 4: Compare Store vs Your Library

```bash
# Check if you own a game
steam library | grep "Game Name"

# Get store info for a game
steam-query lookup -q "Game Name"

# Batch check multiple games from other platforms
steam-query batch -i epic_games.txt -o steam_equivalent.json
```

### Workflow 5: Estimate Required Disk Space

Use the bundled helper with a numeric App ID:

```bash
python3 scripts/get_install_size.py 1113000
```

For DLC without its own PC requirements, the helper follows Steam's `fullgame.appid` and reports
the base game's requirement as inherited:

```bash
python3 scripts/get_install_size.py 2612950
```

Treat the result as publisher-declared free-space guidance. It is not the current depot download
size or an exact post-install byte count, which can vary by platform, language, branch, and DLC.

## Installation

### steam-games-cli

```bash
npm install -g steam-games-cli

# Get API key: https://steamcommunity.com/dev/apikey
steam config set-key YOUR_API_KEY
steam config set-user YOUR_STEAM_ID

# Set profile to Public: https://steamcommunity.com/my/edit/settings
```

### steam-game-query

```bash
pip install steam-game-query

# No setup required - works immediately
```

## Configuration

### steam-games-cli

Config stored in `~/.steam-cli/config.json` or via environment variables:

```bash
steam config set-key YOUR_API_KEY
steam config set-user YOUR_STEAM_ID
```

### steam-game-query

Optional country/region configuration:

```bash
# CLI parameter
steam-query lookup 1245620 --country US

# Environment variable
export STEAM_QUERY_COUNTRY=JP

# Config file
mkdir -p ~/.steam-query
echo '[steam-query]' > ~/.steam-query/config.toml
echo 'country = "US"' >> ~/.steam-query/config.toml
```

## Getting Detailed Help

For comprehensive command reference and advanced usage:

- **steam-games-cli**: See `references/steam-games-cli-guide.md`
- **steam-game-query**: See `references/steam-game-query-guide.md`

## Troubleshooting

### steam-games-cli Issues

**Empty game list:**
- Ensure Steam profile "Game details" is set to Public
- Verify API key: `steam config show`

**Game count is unexpectedly small:**
- Run `steam whoami` and verify the displayed SteamID before trusting the export
- Check for separate config files across WSL, Linux, and Windows
- Use `scripts/export_owned_games.py --config PATH` to select the intended config explicitly
- Remember that `GetOwnedGames` returns self-owned games, not Steam Families shared games

**Slow review fetching:**
- Apply other filters first to reduce API calls
- Use `--min-reviews` instead of `--reviews` when possible

### steam-game-query Issues

**Game not found:**
- Check game name spelling
- Try partial keywords
- Confirm game exists on Steam store

**Network errors:**
- Check network connection
- Reduce request rate: `--rate-limit 0.5`
- Steam API might be temporarily unavailable

## Resources

- **steam-games-cli**: https://github.com/mjrussell/steam-cli (Author: Matt Russell, License: MIT)
- **steam-game-query**: https://github.com/carton/steam-query (Author: Carton He, License: MIT)

## Quick Command Reference

### steam-games-cli

| Command | Description |
|---------|-------------|
| `steam whoami` | Show user profile and stats |
| `steam library` | Browse and filter game library |
| `steam library --unplayed` | Find unplayed games |
| `steam library --sort playtime` | Sort by playtime |
| `steam library --reviews very-positive` | Filter by reviews |
| `steam config` | Manage configuration |

### steam-game-query

| Command | Description |
|---------|-------------|
| `steam-query search "query"` | Search Steam store |
| `steam-query lookup <app_id>` | Get game details by ID |
| `steam-query lookup -q "name"` | Search and lookup by name |
| `steam-query batch games... -o out.json` | Query multiple games |
| `steam-query lookup <id> --country US` | Query with regional pricing |

### Install-size helper

| Command | Description |
|---------|-------------|
| `python3 scripts/get_install_size.py <app_id>` | Show publisher-declared required free space |
| `python3 scripts/get_install_size.py <app_id> --json` | Return the estimate and source as JSON |
