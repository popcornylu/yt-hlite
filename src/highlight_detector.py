"""Highlight detection and management for YouTube video editing."""

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class Highlight:
    """Represents a highlight segment in the video."""

    id: str
    start_time: float  # seconds
    end_time: float  # seconds
    source: str = "manual"  # "manual" or "auto"
    label: Optional[str] = None  # user-defined label

    @property
    def duration(self) -> float:
        """Duration of the highlight in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_time": float(self.start_time),
            "end_time": float(self.end_time),
            "duration": float(self.duration),
            "source": self.source,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Highlight":
        """Create a Highlight from a dictionary."""
        return cls(
            id=data["id"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            source=data.get("source", "manual"),
            label=data.get("label"),
        )


def generate_highlight_id(index: int) -> str:
    """Generate a unique highlight ID."""
    return f"highlight_{index:04d}"


def create_highlight(
    start_time: float,
    end_time: float,
    index: int,
    source: str = "manual",
    label: Optional[str] = None,
) -> Highlight:
    """Create a new highlight with generated ID."""
    return Highlight(
        id=generate_highlight_id(index),
        start_time=start_time,
        end_time=end_time,
        source=source,
        label=label,
    )


def convert_rally_to_highlight(rally_dict: dict, index: int) -> Highlight:
    """Convert a rally (from auto-detection) to a highlight."""
    return Highlight(
        id=generate_highlight_id(index),
        start_time=rally_dict["start_time"],
        end_time=rally_dict["end_time"],
        source="auto",
        label=None,
    )
