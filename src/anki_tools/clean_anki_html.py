#!/usr/bin/env python3
"""Remove HTML markup from selected Anki note fields through AnkiConnect.

The command is dry-run by default. Pass --apply only after reviewing its preview.
Anki must be running with the AnkiConnect add-on enabled.
"""

from __future__ import annotations

import argparse
import html
import sys
from collections.abc import Iterator, Sequence
from typing import Any

import requests
from bs4 import BeautifulSoup


DEFAULT_ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DEFAULT_DECK = "Chinese::1 - Vocabulary"
DEFAULT_FIELDS = ("Hanzi",)
API_VERSION = 6
NOTES_INFO_BATCH_SIZE = 500
PREVIEW_LIMIT = 20


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect cannot complete an action."""


class AnkiConnect:
    def __init__(self, url: str, timeout: float = 30) -> None:
        self.url = url
        self.timeout = timeout

    def invoke(self, action: str, **params: Any) -> Any:
        try:
            response = requests.post(
                self.url,
                json={"action": action, "version": API_VERSION, "params": params},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AnkiConnectError(
                f"Could not call AnkiConnect at {self.url}: {exc}. "
                "Make sure Anki is open and AnkiConnect is installed."
            ) from exc

        if not isinstance(payload, dict) or "result" not in payload or "error" not in payload:
            raise AnkiConnectError(f"Invalid response for AnkiConnect action {action!r}")
        if payload["error"] is not None:
            raise AnkiConnectError(f"AnkiConnect {action!r} failed: {payload['error']}")
        return payload["result"]


def batched(values: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def quote_search_value(value: str) -> str:
    """Quote a value for Anki's search syntax."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def deck_query(deck: str) -> str:
    # Anki's deck search includes the named deck and all of its subdecks.
    return f"deck:{quote_search_value(deck)}"


def clean_html(value: str) -> str:
    """Return the visible text in an Anki HTML field, safely HTML-escaped.

    Escaping special characters is necessary because Anki field values are HTML:
    literal text such as ``<3`` must not become a new tag after cleanup.
    """
    soup = BeautifulSoup(value, "html.parser")
    for unwanted in soup(["script", "style"]):
        unwanted.decompose()

    text = soup.get_text().replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    return html.escape(text.strip(), quote=False)


def load_notes(client: AnkiConnect, note_ids: Sequence[int]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for batch in batched(note_ids, NOTES_INFO_BATCH_SIZE):
        result = client.invoke("notesInfo", notes=list(batch))
        if not isinstance(result, list):
            raise AnkiConnectError("AnkiConnect returned an invalid notesInfo result")
        notes.extend(result)
    return notes


def collect_updates(
    notes: Sequence[dict[str, Any]], fields: Sequence[str]
) -> tuple[list[tuple[int, dict[str, str], dict[str, tuple[str, str]]]], dict[str, int]]:
    updates: list[tuple[int, dict[str, str], dict[str, tuple[str, str]]]] = []
    missing_counts = {field: 0 for field in fields}

    for note in notes:
        note_id = int(note["noteId"])
        note_fields = note.get("fields", {})
        changed_fields: dict[str, str] = {}
        changes: dict[str, tuple[str, str]] = {}

        for field in fields:
            field_data = note_fields.get(field)
            if not isinstance(field_data, dict) or "value" not in field_data:
                missing_counts[field] += 1
                continue
            before = str(field_data["value"])
            after = clean_html(before)
            if after != before:
                changed_fields[field] = after
                changes[field] = (before, after)

        if changed_fields:
            updates.append((note_id, changed_fields, changes))

    return updates, missing_counts


def one_line(value: str, limit: int = 80) -> str:
    value = value.replace("\n", "\\n")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def print_preview(
    updates: Sequence[tuple[int, dict[str, str], dict[str, tuple[str, str]]]],
) -> None:
    for note_id, _fields, changes in updates[:PREVIEW_LIMIT]:
        for field, (before, after) in changes.items():
            print(f"note {note_id} / {field}: {one_line(before)!r} -> {one_line(after)!r}")
    remaining = len(updates) - PREVIEW_LIMIT
    if remaining > 0:
        print(f"... plus {remaining} more changed notes")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove HTML markup from selected fields in an Anki deck and its subdecks."
    )
    parser.add_argument(
        "--deck",
        default=DEFAULT_DECK,
        help=f"parent deck to process (default: {DEFAULT_DECK!r})",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=list(DEFAULT_FIELDS),
        metavar="FIELD",
        help="one or more field names (default: Hanzi)",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_ANKI_CONNECT_URL,
        help=f"AnkiConnect endpoint (default: {DEFAULT_ANKI_CONNECT_URL})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the displayed changes; without this flag, only preview them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = AnkiConnect(args.url)

    # A lightweight call gives a clearer connection/API error before doing work.
    client.invoke("version")
    query = deck_query(args.deck)
    note_ids = client.invoke("findNotes", query=query)
    if not isinstance(note_ids, list):
        raise AnkiConnectError("AnkiConnect returned an invalid findNotes result")

    notes = load_notes(client, note_ids)
    updates, missing_counts = collect_updates(notes, args.fields)

    print(f"Matched {len(notes)} notes in {args.deck!r} and its subdecks.")
    print_preview(updates)
    print(f"{len(updates)} notes need cleanup.")
    for field, count in missing_counts.items():
        if count:
            print(f"Warning: {count} matched notes do not have a {field!r} field.")

    if not args.apply:
        print("Dry run only; no notes were changed. Re-run with --apply to write these updates.")
        return 0

    for note_id, fields, _changes in updates:
        client.invoke("updateNoteFields", note={"id": note_id, "fields": fields})
    print(f"Updated {len(updates)} notes.")
    return 0


def cli() -> int:
    try:
        return main()
    except (AnkiConnectError, KeyError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
