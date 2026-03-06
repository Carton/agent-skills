---
name: steam-cli
description: Steam game library management CLI tools. Use when user wants to manage their Steam library (browse, filter, search, find unplayed games, check playtime) or query Steam store game information (search games, get detailed info, check prices). Covers both user library management (steam-games-cli) and store game queries (steam-game-query).
---

# Steam CLI Tools

This skill provides guidance for two complementary Steam CLI tools:

1. **steam-games-cli** - Manage your personal Steam game library
2. **steam-game-query** - Query Steam store game information (no login required)

## When to Use Each Tool

### Use steam-games-cli when:
- Browsing your own game library
- Finding unplayed games in your collection
- Checking playtime statistics
- Filtering games by review scores
- Managing Steam Deck playtime tracking
- Getting user profile statistics

### Use steam-game-query when:
- Searching for games on the Steam store
- Getting detailed game information (price, release date, developer, etc.)
- Checking regional pricing
- Querying game details without Steam login
- Batch querying multiple games
- Researching games before purchase

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
steam library                   # List all games
steam library --unplayed        # Find unplayed games
steam library --sort playtime   # Most played games
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

## Decision Guide

| Task | Tool |
|------|------|
| "Show my games" | steam-games-cli |
| "Find unplayed games in my library" | steam-games-cli |
| "Search Steam store for games" | steam-game-query |
| "Check price of a game" | steam-game-query |
| "Get my playtime stats" | steam-games-cli |
| "Get game details (developer, genres, etc.)" | steam-game-query |
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
# Export your library as JSON
steam library --json > my_library.json

# Find games you might want to replay
steam library --min-hours 2 --max-hours 20 --show-reviews
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
