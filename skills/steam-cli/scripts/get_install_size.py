#!/usr/bin/env python3
"""Estimate required disk space from Steam's published system requirements."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STORE_API_URL = "https://store.steampowered.com/api/appdetails"
REQUEST_TIMEOUT = 20.0
STORAGE_PATTERN = re.compile(
    r"^\s*(?:Storage|Hard Drive|存储空间|硬盘)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)


class QueryError(RuntimeError):
    """Raised when Steam cannot provide a usable storage estimate."""


class RequirementsHTMLParser(HTMLParser):
    """Convert Steam's system-requirements HTML into line-oriented text."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"div", "li", "p", "ul"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def parse_app_id(value: str) -> int:
    try:
        app_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("App ID must be an integer") from error
    if app_id <= 0:
        raise argparse.ArgumentTypeError("App ID must be positive")
    return app_id


def fetch_app_details(app_id: int) -> dict[str, Any]:
    query = urlencode({"appids": app_id, "l": "english", "cc": "us"})
    request = Request(
        f"{STORE_API_URL}?{query}",
        headers={"User-Agent": "steam-cli-skill/1.0"},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise QueryError(f"Failed to query Steam for App ID {app_id}: {error}") from error

    result = payload.get(str(app_id))
    if not isinstance(result, dict) or not result.get("success"):
        raise QueryError(f"Steam returned no store details for App ID {app_id}")

    data = result.get("data")
    if not isinstance(data, dict):
        raise QueryError(f"Steam returned invalid store details for App ID {app_id}")
    return data


def extract_storage(requirements: object) -> dict[str, str]:
    if isinstance(requirements, str):
        sections = {"minimum": requirements}
    elif isinstance(requirements, dict):
        sections = {
            str(name): html
            for name, html in requirements.items()
            if isinstance(html, str)
        }
    else:
        return {}

    storage: dict[str, str] = {}
    for section, requirements_html in sections.items():
        parser = RequirementsHTMLParser()
        parser.feed(requirements_html)
        for line in parser.text().splitlines():
            match = STORAGE_PATTERN.match(line)
            if match:
                storage[section] = " ".join(match.group(1).split())
                break
    return storage


def build_estimate(app_id: int) -> dict[str, Any]:
    requested = fetch_app_details(app_id)
    source_app_id = app_id
    source = requested
    storage = extract_storage(requested.get("pc_requirements"))

    fullgame = requested.get("fullgame")
    inherited = False
    if not storage and isinstance(fullgame, dict):
        parent_id = fullgame.get("appid")
        if isinstance(parent_id, (int, str)) and str(parent_id).isdigit():
            source_app_id = int(parent_id)
            source = fetch_app_details(source_app_id)
            storage = extract_storage(source.get("pc_requirements"))
            inherited = True

    if not storage:
        raise QueryError(
            "Steam does not publish a PC storage requirement for "
            f"{requested.get('name', 'this app')} ({app_id})"
        )

    return {
        "estimate_type": "publisher_required_free_space",
        "requested": {
            "app_id": app_id,
            "name": requested.get("name"),
            "type": requested.get("type"),
        },
        "source": {
            "app_id": source_app_id,
            "name": source.get("name"),
            "type": source.get("type"),
        },
        "inherited_from_base_game": inherited,
        "minimum": storage.get("minimum"),
        "recommended": storage.get("recommended"),
    }


def print_human(estimate: dict[str, Any]) -> None:
    requested = estimate["requested"]
    source = estimate["source"]
    print(f"{requested['name']} ({requested['app_id']})")
    print("Publisher-declared required free space:")
    if estimate["minimum"]:
        print(f"  Minimum: {estimate['minimum']}")
    if estimate["recommended"]:
        print(f"  Recommended: {estimate['recommended']}")
    if estimate["inherited_from_base_game"]:
        print(
            "  Source: "
            f"{source['name']} ({source['app_id']}), inherited from the base game"
        )
    print("Note: This is a system-requirements estimate, not exact depot size.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate required disk space from Steam's published PC system requirements."
        )
    )
    parser.add_argument("app_id", type=parse_app_id, help="Steam App ID")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print structured JSON",
    )
    args = parser.parse_args()

    try:
        estimate = build_estimate(args.app_id)
    except QueryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(estimate, ensure_ascii=False, indent=2))
    else:
        print_human(estimate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
