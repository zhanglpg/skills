"""Append-only log operations for the knowledge wiki."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def _ensure_log(log_path: Path) -> None:
    """Create the log file with a header if it does not exist."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text(
            "---\n"
            "title: Wiki Log\n"
            "type: log\n"
            "---\n\n"
            "# Wiki Activity Log\n\n"
            "> Append-only chronological record of wiki activity.\n\n",
            encoding="utf-8",
        )


def append_log(
    log_path: str | Path,
    event_type: str,
    title: str,
    details: Optional[list[str]] = None,
    timestamp: Optional[datetime] = None,
) -> None:
    """Append a structured entry to the wiki log.

    Args:
        log_path: Path to log.md (absolute or with ~ expansion).
        event_type: One of 'ingest', 'query', 'lint', 'concept-create',
                    'concept-update', 'name-create', 'name-update',
                    'index-rebuild'.
        title: Primary description (e.g. paper title, query text).
        details: Optional list of sub-bullet details (e.g. touched pages).
        timestamp: Override timestamp (defaults to now).
    """
    path = Path(os.path.expanduser(str(log_path)))
    _ensure_log(path)

    ts = timestamp or datetime.now()
    date_str = ts.strftime("%Y-%m-%d")
    time_str = ts.strftime("%H:%M")

    # Check if today's date heading already exists
    existing = path.read_text(encoding="utf-8")
    date_heading = f"## {date_str}"

    entry_lines: list[str] = []

    if date_heading not in existing:
        entry_lines.append(f"\n{date_heading}\n")

    entry_lines.append(f"- **{time_str}** — {event_type}: {title}")

    if details:
        for detail in details:
            entry_lines.append(f"  - {detail}")

    entry_lines.append("")

    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(entry_lines))


def read_log(log_path: str | Path, last_n: int = 20) -> str:
    """Read the last N entries from the log.

    Returns raw markdown text of the trailing entries.
    """
    path = Path(os.path.expanduser(str(log_path)))
    if not path.exists():
        return "*No log file found.*"

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Return last N non-empty lines (approximate)
    tail = lines[-last_n * 3:] if len(lines) > last_n * 3 else lines
    return "\n".join(tail)
