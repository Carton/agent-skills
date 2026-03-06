# steam-games-cli Detailed Guide

Steam CLI (`steam-games-cli`) is a command-line tool for browsing, filtering, and discovering games in your personal Steam library.

## Table of Contents

- [Installation](#installation)
- [Initial Setup](#initial-setup)
- [Privacy Requirements](#privacy-requirements)
- [Commands](#commands)
- [Advanced Filtering](#advanced-filtering)
- [Output Formats](#output-formats)
- [Configuration](#configuration)
- [Use Cases](#use-cases)
- [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Node.js 18 or higher
- Steam Web API key (get one at https://steamcommunity.com/dev/apikey)
- Steam account with public game details

### Install

```bash
npm install -g steam-games-cli

# Verify installation
steam --help
```

## Initial Setup

Before using the tool, configure the API key and Steam user:

```bash
steam config set-key YOUR_API_KEY
steam config set-user YOUR_STEAM_ID
```

The Steam ID can be found in the URL of your Steam profile (e.g., `76561198012345678`).

### Alternative Setup Methods

**Config file** (`~/.steam-cli/config.json`):
```json
{
  "apiKey": "YOUR_API_KEY",
  "steamId": "YOUR_STEAM_ID"
}
```

**Environment variables**:
```bash
export STEAM_API_KEY="YOUR_API_KEY"
export STEAM_USER="YOUR_STEAM_ID"
```

## Privacy Requirements

The Steam profile's "Game details" must be set to Public:

1. Visit: https://steamcommunity.com/my/edit/settings
2. Privacy Settings → Game details → Public
3. Save changes

**Note**: This is required for the Steam Web API to access your library information.

## Commands

### whoami - Show Profile Information

Display your Steam profile and library statistics.

```bash
# Show profile and stats
steam whoami

# JSON output for scripting
steam whoami --json
```

**Output includes:**
- Steam ID and username
- Number of games owned
- Total playtime
- Account creation date

### library - Browse Game Library

The main command for browsing and filtering your game library.

```bash
# List all games
steam library

# Limit results
steam library --limit 20

# Sort by playtime (most played first)
steam library --sort playtime --limit 10

# Sort by name (alphabetical)
steam library --sort name
```

## Advanced Filtering

### Playtime Filtering

```bash
# Find unplayed games
steam library --unplayed --limit 20

# Games with 10-50 hours of playtime
steam library --min-hours 10 --max-hours 50

# Games you've played a lot
steam library --min-hours 100
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

### Steam Deck Filtering

```bash
# Show only games played on Steam Deck
steam library --deck --limit 10

# Sort by most-played on Deck
steam library --deck --sort deck

# Show Deck playtime column
steam library --deck-hours --limit 5
```

### Combining Filters

```bash
# Find hidden gems: well-reviewed, unplayed games
steam library --unplayed --min-reviews 8 --show-reviews --limit 20

# Games you might want to replay: 2-20 hours, good reviews
steam library --min-hours 2 --max-hours 20 --min-reviews 7 --show-reviews

# Steam Deck games you haven't played much
steam library --deck --max-hours 10 --sort deck
```

## Output Formats

### Table Format (Default)

```bash
steam library --limit 5
```

Output:
```
┌─────────────────────────────┬──────────┬──────────┐
│ Name                        │ Playtime │ Reviews  │
├─────────────────────────────┼──────────┼──────────┤
│ Game 1                      │ 120.5h   │ 9        │
│ Game 2                      │ 45.2h    │ 8        │
└─────────────────────────────┴──────────┴──────────┘
```

### Plain List Format

Great for scripting and parsing:

```bash
steam library --plain --limit 5
```

Output:
```
Game 1 (120.5h)
Game 2 (45.2h)
Game 3 (12.3h)
```

### JSON Format

For programmatic processing:

```bash
steam library --json --limit 5
```

Output:
```json
[
  {
    "name": "Game 1",
    "appid": 123456,
    "playtime": 120.5,
    "review_score": 9
  }
]
```

## Configuration

### Config Commands

```bash
# Set API key
steam config set-key YOUR_API_KEY

# Set Steam user ID
steam config set-user YOUR_STEAM_ID

# Show current configuration
steam config show
```

### Config File Location

Config is stored in:
- Linux/Mac: `~/.steam-cli/config.json`
- Windows: `%USERPROFILE%\.steam-cli\config.json`

### Environment Variables

Environment variables override config file settings:

```bash
export STEAM_API_KEY="YOUR_API_KEY"
export STEAM_USER="YOUR_STEAM_ID"
```

## Use Cases

### Use Case 1: Find Hidden Gems

Discover well-reviewed games you haven't played:

```bash
steam library --unplayed --min-reviews 8 --show-reviews --limit 20
```

### Use Case 2: Track Steam Deck Usage

See which games you play most on Steam Deck:

```bash
steam library --deck --sort deck --limit 10
```

### Use Case 3: Find Games to Replay

Find games you enjoyed but haven't played in a while:

```bash
steam library --min-hours 2 --max-hours 50 --min-reviews 7 --show-reviews
```

### Use Case 4: Export Library

Export your library for analysis:

```bash
# Export as JSON
steam library --json > my_library.json

# Count games by review score
steam library --json | jq '.[] | group_by(.review_score) | map({score: .[0].review_score, count: length})'
```

### Use Case 5: Statistics

Get insights about your gaming habits:

```bash
# Total number of games
steam library --json | jq 'length'

# Total playtime
steam library --json | jq '[.[].playtime] | add'

# Average playtime
steam library --json | jq '[.[].playtime] | add / length'
```

## Performance Tips

Review data requires individual API calls per game. For better performance:

```bash
# Fast: filters first, then fetches reviews for fewer games
steam library --min-hours 10 --reviews very-positive

# Slow: fetches reviews for all games
steam library --reviews very-positive
```

Apply other filters (playtime, unplayed, deck) before using review filters to reduce the number of API calls needed.

## Command Reference

### steam library [options]

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

### steam config <command>

| Command | Description |
|----------|-------------|
| `set-key <key>` | Set Steam Web API key |
| `set-user <id>` | Set Steam ID or username |
| `show` | Display current config |

### steam whoami [options]

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |

## Troubleshooting

### Empty Game List

**Symptom**: `steam library` returns no games

**Solutions**:
1. Ensure Steam profile's "Game details" is set to Public
   - Visit: https://steamcommunity.com/my/edit/settings
2. Verify API key is correctly configured: `steam config show`
3. Check Steam ID is correct (should be numeric, e.g., `76561198012345678`)

### Review Fetching is Slow

**Symptom**: Commands with `--reviews` flag are slow

**Solutions**:
1. Use other filters first to reduce the number of games
2. Use `--min-reviews` instead of `--reviews <category>` when possible
3. Consider using `--limit` to reduce results

### API Key Issues

**Symptom**: "Invalid API key" error

**Solutions**:
1. Get a new API key: https://steamcommunity.com/dev/apikey
2. Update config: `steam config set-key YOUR_NEW_KEY`
3. Verify key works: `steam whoami`

### Steam ID Issues

**Symptom**: "Invalid Steam ID" error

**Solutions**:
1. Find your Steam ID:
   - Visit your Steam profile
   - The URL contains your ID: `steamcommunity.com/profiles/76561198012345678`
   - Or use a custom URL converter
2. Update config: `steam config set-user YOUR_STEAM_ID`

### Rate Limiting

**Symptom**: Requests are being throttled

**Solutions**:
1. Steam Web API has rate limits
2. Use filters to reduce the number of API calls
3. Consider adding delays between commands in scripts

## Examples

### Example 1: What Should I Play Next?

```bash
# Find well-reviewed games you haven't played much
steam library --max-hours 5 --min-reviews 8 --show-reviews --limit 10
```

### Example 2: Game Library Statistics

```bash
# Get library overview
steam whoami

# Count games by playtime ranges
steam library --json | jq '
  [
    {range: "0-10h", count: [.[] | select(.playtime <= 10)] | length},
    {range: "10-50h", count: [.[] | select(.playtime > 10 and .playtime <= 50)] | length},
    {range: "50-100h", count: [.[] | select(.playtime > 50 and .playtime <= 100)] | length},
    {range: "100h+", count: [.[] | select(.playtime > 100)] | length}
  ]
'
```

### Example 3: Deck-Optimized Games

```bash
# Find games you play on Steam Deck
steam library --deck --sort deck --limit 20

# Find Deck games you haven't played much
steam library --deck --max-hours 5 --show-reviews
```

### Example 4: Backup Your Library

```bash
# Export full library
steam library --json > library_backup_$(date +%Y%m%d).json

# Export with review data
steam library --show-reviews --json > library_with_reviews.json
```

### Example 5: Find Similar Games

```bash
# Find all games with specific tags or genres
# (requires combining with other tools)
steam library --json | jq '.[] | select(.name | contains("RPG"))'
```

## More Resources

- GitHub Repository: https://github.com/mjrussell/steam-cli
- Author: Matt Russell
- License: MIT
- Steam Web API: https://steamcommunity.com/dev
