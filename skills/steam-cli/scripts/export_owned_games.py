#!/usr/bin/env python3
"""Export every game returned by Steam GetOwnedGames."""

from __future__ import annotations

import argparse
import csv
from io import StringIO
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OWNED_GAMES_API_URL = (
    "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
)
REQUEST_TIMEOUT = 30.0
DEFAULT_CONFIG_PATH = Path.home() / ".steam-cli" / "config.json"
CSV_FIELDS = (
    "appId",
    "name",
    "playtime",
    "playtimeLastTwoWeeks",
    "playtimeDeck",
    "imgIconUrl",
)


class QueryError(RuntimeError):
    """Raised when Steam cannot provide a complete owned-games response."""


def load_config(config_path: Path) -> tuple[str, str]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise QueryError(f"Steam CLI config not found: {config_path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise QueryError(f"Failed to read Steam CLI config {config_path}: {error}") from error

    api_key = config.get("apiKey")
    steam_id = config.get("steamId")
    if not isinstance(api_key, str) or not api_key:
        raise QueryError(f"Steam API key is missing from {config_path}")
    if not isinstance(steam_id, str) or not steam_id.isdigit():
        raise QueryError(f"Steam ID is missing or invalid in {config_path}")
    return api_key, steam_id


def fetch_owned_games(api_key: str, steam_id: str) -> list[dict[str, Any]]:
    query = urlencode(
        {
            "key": api_key,
            "steamid": steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        }
    )
    request = Request(
        f"{OWNED_GAMES_API_URL}?{query}",
        headers={"User-Agent": "steam-cli-skill/1.0"},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise QueryError(f"Failed to query Steam owned games: {error}") from error

    response = payload.get("response")
    if not isinstance(response, dict):
        raise QueryError("Steam returned an invalid owned-games response")

    games = response.get("games", [])
    game_count = response.get("game_count", 0)
    if not isinstance(games, list) or not isinstance(game_count, int):
        raise QueryError("Steam returned invalid owned-games fields")
    if len(games) != game_count:
        raise QueryError(
            f"Steam reported {game_count} games but returned {len(games)}; "
            "refusing to export a partial library"
        )

    normalized = [
        {
            "appId": game.get("appid"),
            "name": game.get("name", ""),
            "playtime": game.get("playtime_forever", 0),
            "playtimeLastTwoWeeks": game.get("playtime_2weeks", 0),
            "playtimeDeck": game.get("playtime_deck_forever", 0),
            "imgIconUrl": game.get("img_icon_url", ""),
        }
        for game in games
        if isinstance(game, dict) and isinstance(game.get("appid"), int)
    ]
    if len(normalized) != game_count:
        raise QueryError("Steam returned one or more games without a valid App ID")
    return sorted(normalized, key=lambda game: (str(game["name"]).casefold(), game["appId"]))


def render_json(games: list[dict[str, Any]]) -> str:
    return f"{json.dumps(games, ensure_ascii=False, indent=2)}\n"


def render_csv(games: list[dict[str, Any]]) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(games)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export all self-owned games returned by Steam GetOwnedGames. "
            "Family-shared games are not included."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"steam-games-cli config path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--steam-id",
        help="override the target SteamID64 while using the API key from --config",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="output format (default: json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write to this file instead of standard output",
    )
    args = parser.parse_args()

    try:
        api_key, configured_steam_id = load_config(args.config)
        steam_id = args.steam_id or configured_steam_id
        if not steam_id.isdigit():
            raise QueryError("Steam ID must be a numeric SteamID64")
        games = fetch_owned_games(api_key, steam_id)
    except QueryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    rendered = render_csv(games) if args.format == "csv" else render_json(games)
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8", newline="")
        except OSError as error:
            print(f"Error: failed to write {args.output}: {error}", file=sys.stderr)
            return 1
        print(f"Exported {len(games)} owned games to {args.output}", file=sys.stderr)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
