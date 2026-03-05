---
name: epic-cli
description: Epic Games library management CLI tool. Use when user wants to browse, install, launch, sync saves, or manage their Epic Games library from the terminal using Legendary - listing games, checking updates, downloading content, or managing cloud saves. Works on Linux, macOS, and Windows.
---

# Epic Games CLI (Legendary)

Legendary is a free and open-source command-line replacement for the Epic Games Launcher. Use this skill when the user wants to manage their Epic Games library from the terminal - installing games, launching titles, syncing cloud saves, or browsing their Epic collection.

## Installation

Prerequisites:
- Python 3.9+ (64-bit)
- pip package manager

Install via PyPI (recommended):
```bash
pip install legendary-gl
```

For web browser login support:
```bash
pip install legendary-gl[webview]
```

Alternative: Install from source
```bash
git clone https://github.com/derrod/legendary.git
cd legendary
pip install .
```

## Initial Setup

### Authentication

First, authenticate with your Epic Games account:

```bash
# Standard authentication (opens browser for login)
legendary auth

# Import existing session from Epic Games Launcher (logs you out of EGL)
legendary auth --import
```

The browser-based authentication will:
1. Open your default browser to Epic Games login
2. Prompt you to log in with your Epic credentials
3. Display an authentication code
4. Automatically save your session when you return to the terminal

### Verification

Verify you're logged in:
```bash
legendary whoami
```

Config is stored in `~/.config/legendary/config.ini` (Linux/macOS) or `%APPDATA%\legendary\config.ini` (Windows).

## Commands Overview

| Command | Description |
|---------|-------------|
| `legendary auth` | Authenticate with Epic Games |
| `legendary list` | List all games in your library |
| `legendary list-installed` | List installed games and check for updates |
| `legendary install <app>` | Install/download a game |
| `legendary launch <app>` | Launch/play a game |
| `legendary uninstall <app>` | Uninstall a game |
| `legendary sync-saves` | Sync cloud saves |
| `legendary egl-sync` | Sync with Epic Games Launcher |

## Common Use Cases

### Browse Your Game Library

```bash
# List all games in your Epic Games library
legendary list

# List with detailed information
legendary list --csv

# Force refresh metadata (useful if list seems outdated)
legendary list --force-refresh

# List only Unreal Engine content
legendary list --include-ue
```

### Manage Installed Games

```bash
# List installed games
legendary list-installed

# Check for updates on installed games
legendary list-installed --check-updates

# Update a specific game
legendary update <app-name>

# Update all installed games
legendary update --skip-dlc
```

### Install Games

```bash
# Install a game (use app name from list command)
legendary install Anemone

# Install to custom directory
legendary install <app-name> --base-path /path/to/games

# Install with specific platform
legendary install <app-name> --platform Windows

# Install game with DLC
legendary install <app-name> --include-dlc

# Install without selective download (gets all components)
legendary install <app-name> --disable-sdl

# Silent installation (no prompts)
legendary install <app-name> -y
```

### Launch Games

```bash
# Launch a game
legendary launch "world of goo"

# Launch in offline mode
legendary launch <app-name> --offline

# Show launch command without executing
legendary launch <app-name> --dry-run

# Launch with custom parameters
legendary launch <app-name> --override- exe "path/to/exe" --working-dir "path/to/dir"
```

### Cloud Saves Management

```bash
# Sync all cloud saves (upload and download)
legendary sync-saves

# Only download saves (don't upload)
legendary sync-saves --skip-upload

# Force download even if local is newer
legendary sync-saves --force-download

# Clean up old cloud saves
legendary clean-saves
```

### Game Information

```bash
# Get detailed info about a game
legendary info <app-name>

# List files in a game manifest
legendary list-files <app-name>

# List available cloud saves for a game
legendary list-saves <app-name>
```

### Import Existing Games

If you have games installed via Epic Games Launcher:

```bash
# Import a game from Epic Games Launcher
legendary import-game <app-name> "/path/to/epic/install/dir"

# One-time sync with Epic Games Launcher
legendary egl-sync --one-shot

# Continuous sync with EGL (not available on macOS)
legendary egl-sync
```

### Aliases for Convenience

Create aliases in `~/.config/legendary/config.ini`:

```ini
[Legendary.aliases]
; Alias = App Name
HITMAN 3 = Eider
gtav = 9d2d0eb64d5c44529cece33fe2a46482
```

Then use aliases in commands:
```bash
legendary launch HITMAN 3
legendary install gtav
```

## Command Reference

### `legendary list [options]`

| Option | Description |
|--------|-------------|
| `--platform <p>` | Filter by platform (Windows/Mac) |
| `--include-ue` | Include Unreal Engine content |
| `-T` | Disable terminal formatting |
| `--csv` | Output in CSV format |
| `--tsv` | Output in TSV format |
| `--json` | Output in JSON format |
| `--force-refresh` | Force refresh all metadata |

### `legendary install <app-name> [options]`

| Option | Description |
|--------|-------------|
| `--base-path <path>` | Custom installation directory |
| `--platform <p>` | Specific platform |
| `--include-dlc` | Install DLC |
| `--disable-sdl` | Disable selective download |
| `--reset-sdl` | Reset selective download choices |
| `--skip-dl` | Skip download, only install |
| `-y` | Auto-confirm all prompts |
| `--update` | Update if already installed |

### `legendary launch <app-name> [options]`

| Option | Description |
|--------|-------------|
| `--offline` | Launch in offline mode |
| `--dry-run` | Show command without executing |
| `--json` | Output launch info as JSON |
| `--override- exe <path>` | Custom executable |
| `--working-dir <path>` | Custom working directory |

### `legendary sync-saves [options]`

| Option | Description |
|--------|-------------|
| `--skip-upload` | Only download saves |
| `--force-download` | Force download overwriting local |
| `--force-upload` | Force upload overwriting remote |

## Advanced Features

### Cross-Platform Gaming

```bash
# Run Windows games on Linux via Proton/WINE
legendary install <app-name> --platform Windows
legendary launch <app-name> --wine

# Run via CrossOver (macOS)
legendary launch <app-name> --crossover-bottle <bottle-name>
```

### Selective Download

Legendary supports selective downloading to save disk space:

```bash
# Install with selective download enabled
legendary install <app-name>

# Reset SDL selection
legendary install <app-name> --reset-sdl

# Disable SDL (get all components)
legendary install <app-name> --disable-sdl
```

### Configuration

Edit `~/.config/legendary/config.ini`:

```ini
[Legendary]
max_memory = 2048           ; Max shared memory in MB
max_workers = 8             ; Max worker processes
install_dir = ~/Games       ; Default install directory
```

## Troubleshooting

### Authentication Issues

If authentication fails:
```bash
# Clear existing session
legendary auth --delete

# Re-authenticate
legendary auth
```

### Game Won't Launch

1. Check if game needs online authentication:
   ```bash
   legendary launch <app-name>
   ```

2. Try offline mode if DRM allows:
   ```bash
   legendary launch <app-name> --offline
   ```

3. Use `--dry-run` to see launch command:
   ```bash
   legendary launch <app-name> --dry-run
   ```

### Slow Downloads

Adjust max workers in config:
```ini
[Legendary]
max_workers = 16
max_memory = 4096
```

### Import from Epic Games Launcher

macOS version of EGL doesn't support import. Use:
```bash
# On Windows/Linux
legendary egl-sync
```

## Resources

- Official GitHub: https://github.com/derrod/legendary
- Documentation: https://github.com/derrod/legendary#readme
- PyPI Package: https://pypi.org/project/legendary-gl/
- License: GPL-3.0

## Limitations

- No game purchasing (can only download owned games)
- Cannot claim free games (must use web store or EGL)
- macOS EGL sync not supported (EGL limitation)
- Requires terminal usage (no GUI)

## Alternative Tools

For a GUI experience:
- **Heroic Games Launcher**: https://heroicgameslauncher.com/ (GUI frontend for Legendary)
- **Lutris**: https://lutris.net/ (Linux game manager with Legendary integration)
