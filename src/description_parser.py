"""Parse and format highlights for YouTube video descriptions."""

import re
from typing import Optional


def format_timestamp_for_description(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS (whole seconds, YouTube-clickable)."""
    total_secs = int(round(seconds))
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_highlights_for_description(highlights: list[dict]) -> str:
    """
    Format highlights as text suitable for a YouTube video description.

    Args:
        highlights: List of highlight dicts with start_time and end_time (seconds).

    Returns:
        Formatted string with [Highlights] header and timestamp lines.
    """
    if not highlights:
        return ""

    sorted_highlights = sorted(highlights, key=lambda h: h["start_time"])

    lines = ["[Highlights]"]
    for h in sorted_highlights:
        start = format_timestamp_for_description(h["start_time"])
        end = format_timestamp_for_description(h["end_time"])
        lines.append(f"{start} - {end}")

    return "\n".join(lines)


def parse_timestamp(ts: str) -> Optional[float]:
    """
    Parse a timestamp string into seconds.

    Supports:
        M:SS      -> minutes:seconds
        H:MM:SS   -> hours:minutes:seconds

    Returns:
        Seconds as float, or None if parsing fails.
    """
    ts = ts.strip()

    # H:MM:SS
    match = re.match(r'^(\d+):(\d{1,2}):(\d{1,2})$', ts)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return float(h * 3600 + m * 60 + s)

    # M:SS
    match = re.match(r'^(\d+):(\d{1,2})$', ts)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return float(m * 60 + s)

    return None


def parse_highlights_from_description(description: str) -> list[dict]:
    """
    Parse highlights from a YouTube video description.

    Looks for a [Highlights] section and parses timestamp range lines
    in the format "M:SS - M:SS" or "H:MM:SS - H:MM:SS".

    Only parses lines within the [Highlights] section (stops at the next
    blank line or section header).

    Args:
        description: The full video description text.

    Returns:
        List of dicts with start_time and end_time (seconds).
    """
    if not description:
        return []

    lines = description.split('\n')
    highlights = []
    in_section = False

    # Pattern for timestamp range: "M:SS - M:SS" or "H:MM:SS - H:MM:SS"
    range_pattern = re.compile(
        r'^(\d+:\d{1,2}(?::\d{1,2})?)\s*-\s*(\d+:\d{1,2}(?::\d{1,2})?)$'
    )

    for line in lines:
        stripped = line.strip()

        if stripped == '[Highlights]':
            in_section = True
            continue

        if not in_section:
            continue

        # Stop at empty line or another section header
        if not stripped or (stripped.startswith('[') and stripped.endswith(']')):
            break

        match = range_pattern.match(stripped)
        if match:
            start = parse_timestamp(match.group(1))
            end = parse_timestamp(match.group(2))
            if start is not None and end is not None and end > start:
                highlights.append({
                    "start_time": start,
                    "end_time": end,
                })

    return highlights
