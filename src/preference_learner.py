"""Preference learning module for adjusting highlight detection based on user feedback."""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

from .highlight_scorer import ScoringWeights, ScoredRally
from .rally_detector import Rally


@dataclass
class FeedbackEntry:
    """A single piece of user feedback."""

    rally_id: str
    timestamp: str  # ISO format
    feedback_type: str  # "rating", "confirm", "reject", "split", "merge", "adjust_bounds"
    value: dict = field(default_factory=dict)  # Feedback-specific data

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedbackSession:
    """All feedback from a single analysis session."""

    session_id: str
    video_path: str
    created_at: str
    entries: list[FeedbackEntry] = field(default_factory=list)
    weights_before: Optional[dict] = None
    weights_after: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "video_path": self.video_path,
            "created_at": self.created_at,
            "entries": [e.to_dict() for e in self.entries],
            "weights_before": self.weights_before,
            "weights_after": self.weights_after,
        }


class PreferenceLearner:
    """
    Learns user preferences from feedback to improve highlight detection.

    Stores feedback history and adjusts scoring weights over time.
    """

    def __init__(self, feedback_dir: str = "data/feedback"):
        """
        Initialize the preference learner.

        Args:
            feedback_dir: Directory to store feedback data
        """
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        self.weights_file = self.feedback_dir / "weights.json"
        self.history_file = self.feedback_dir / "history.json"

        self.current_session: Optional[FeedbackSession] = None
        self.weights = self._load_weights()

    def _load_weights(self) -> ScoringWeights:
        """Load saved weights or return defaults."""
        if self.weights_file.exists():
            with open(self.weights_file) as f:
                data = json.load(f)
                return ScoringWeights.from_dict(data)
        return ScoringWeights()

    def save_weights(self) -> None:
        """Save current weights to disk."""
        with open(self.weights_file, "w") as f:
            json.dump(self.weights.to_dict(), f, indent=2)

    def start_session(self, video_path: str) -> str:
        """
        Start a new feedback session.

        Args:
            video_path: Path to the video being analyzed

        Returns:
            Session ID
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session = FeedbackSession(
            session_id=session_id,
            video_path=video_path,
            created_at=datetime.now().isoformat(),
            weights_before=self.weights.to_dict(),
        )

        return session_id

    def record_rating(self, rally_id: str, rating: int) -> None:
        """
        Record a user rating for a rally.

        Args:
            rally_id: ID of the rated rally
            rating: Rating from 1-5
        """
        if self.current_session is None:
            raise RuntimeError("No active feedback session")

        entry = FeedbackEntry(
            rally_id=rally_id,
            timestamp=datetime.now().isoformat(),
            feedback_type="rating",
            value={"rating": rating},
        )
        self.current_session.entries.append(entry)

    def record_confirmation(self, rally_id: str, is_highlight: bool) -> None:
        """
        Record user confirmation/rejection of a rally as highlight.

        Args:
            rally_id: ID of the rally
            is_highlight: True if confirmed as highlight, False if rejected
        """
        if self.current_session is None:
            raise RuntimeError("No active feedback session")

        entry = FeedbackEntry(
            rally_id=rally_id,
            timestamp=datetime.now().isoformat(),
            feedback_type="confirm" if is_highlight else "reject",
            value={"is_highlight": is_highlight},
        )
        self.current_session.entries.append(entry)

    def record_boundary_adjustment(
        self,
        rally_id: str,
        new_start: float,
        new_end: float,
    ) -> None:
        """
        Record user adjustment of rally boundaries.

        Args:
            rally_id: ID of the rally
            new_start: New start time in seconds
            new_end: New end time in seconds
        """
        if self.current_session is None:
            raise RuntimeError("No active feedback session")

        entry = FeedbackEntry(
            rally_id=rally_id,
            timestamp=datetime.now().isoformat(),
            feedback_type="adjust_bounds",
            value={"new_start": new_start, "new_end": new_end},
        )
        self.current_session.entries.append(entry)

    def record_split(self, rally_id: str, split_time: float) -> None:
        """
        Record user splitting a rally into two.

        Args:
            rally_id: ID of the original rally
            split_time: Time at which to split
        """
        if self.current_session is None:
            raise RuntimeError("No active feedback session")

        entry = FeedbackEntry(
            rally_id=rally_id,
            timestamp=datetime.now().isoformat(),
            feedback_type="split",
            value={"split_time": split_time},
        )
        self.current_session.entries.append(entry)

    def record_merge(self, rally_id_1: str, rally_id_2: str) -> None:
        """
        Record user merging two rallies.

        Args:
            rally_id_1: ID of first rally
            rally_id_2: ID of second rally
        """
        if self.current_session is None:
            raise RuntimeError("No active feedback session")

        entry = FeedbackEntry(
            rally_id=rally_id_1,
            timestamp=datetime.now().isoformat(),
            feedback_type="merge",
            value={"merged_with": rally_id_2},
        )
        self.current_session.entries.append(entry)

    def record_missed_rally(self, start_time: float, end_time: float) -> None:
        """
        Record a rally that the system missed but user identified.

        Args:
            start_time: Start time of missed rally
            end_time: End time of missed rally
        """
        if self.current_session is None:
            raise RuntimeError("No active feedback session")

        entry = FeedbackEntry(
            rally_id="user_added",
            timestamp=datetime.now().isoformat(),
            feedback_type="add_missed",
            value={"start_time": start_time, "end_time": end_time},
        )
        self.current_session.entries.append(entry)

    def apply_feedback_to_rallies(
        self,
        scored_rallies: list[ScoredRally],
    ) -> list[ScoredRally]:
        """
        Apply recorded feedback to rallies.

        Args:
            scored_rallies: List of scored rallies

        Returns:
            Updated rallies with feedback applied
        """
        if self.current_session is None:
            return scored_rallies

        # Build rally lookup
        rally_lookup = {sr.rally.id: sr for sr in scored_rallies}

        # Apply feedback
        for entry in self.current_session.entries:
            if entry.rally_id not in rally_lookup:
                continue

            sr = rally_lookup[entry.rally_id]

            if entry.feedback_type == "rating":
                sr.rally.user_rating = entry.value.get("rating")

            elif entry.feedback_type in ("confirm", "reject"):
                sr.rally.is_highlight = entry.value.get("is_highlight")
                sr.rally.is_confirmed = True

            elif entry.feedback_type == "adjust_bounds":
                sr.rally.start_time = entry.value.get("new_start", sr.rally.start_time)
                sr.rally.end_time = entry.value.get("new_end", sr.rally.end_time)

        return scored_rallies

    def learn_from_session(
        self,
        scored_rallies: list[ScoredRally],
        learning_rate: float = 0.1,
    ) -> ScoringWeights:
        """
        Update weights based on session feedback.

        Args:
            scored_rallies: Rallies with feedback applied
            learning_rate: How aggressively to update weights

        Returns:
            Updated ScoringWeights
        """
        # Get rallies with ratings
        rated = [sr for sr in scored_rallies if sr.rally.user_rating is not None]

        if len(rated) < 3:
            return self.weights  # Not enough data

        # Calculate correlations between features and ratings
        features = {
            "rally_length": [sr.rally.duration for sr in rated],
            "hit_count": [sr.rally.hit_count for sr in rated],
            "crowd_intensity": [sr.rally.crowd_intensity for sr in rated],
            "motion_intensity": [sr.rally.motion_intensity for sr in rated],
        }

        ratings = [sr.rally.user_rating for sr in rated]

        import numpy as np

        # Update weights based on correlation with ratings
        for feature_name, values in features.items():
            if np.std(values) > 0 and np.std(ratings) > 0:
                correlation = np.corrcoef(values, ratings)[0, 1]

                if not np.isnan(correlation):
                    current_weight = getattr(self.weights, feature_name)
                    # Positive correlation means this feature predicts good highlights
                    adjustment = correlation * learning_rate
                    new_weight = max(0.1, current_weight * (1 + adjustment))
                    setattr(self.weights, feature_name, new_weight)

        return self.weights

    def end_session(self, scored_rallies: list[ScoredRally]) -> None:
        """
        End the current feedback session and save results.

        Args:
            scored_rallies: Final rallies with all feedback
        """
        if self.current_session is None:
            return

        # Learn from feedback
        self.learn_from_session(scored_rallies)

        # Record final weights
        self.current_session.weights_after = self.weights.to_dict()

        # Save session to history
        self._save_session()

        # Save updated weights
        self.save_weights()

        self.current_session = None

    def _save_session(self) -> None:
        """Save current session to history file."""
        if self.current_session is None:
            return

        # Load existing history
        history = []
        if self.history_file.exists():
            with open(self.history_file) as f:
                history = json.load(f)

        # Append current session
        history.append(self.current_session.to_dict())

        # Save
        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

    def get_session_summary(self) -> dict:
        """Get summary of current session feedback."""
        if self.current_session is None:
            return {"active": False}

        entries = self.current_session.entries
        return {
            "active": True,
            "session_id": self.current_session.session_id,
            "total_feedback": len(entries),
            "ratings": len([e for e in entries if e.feedback_type == "rating"]),
            "confirmations": len([e for e in entries if e.feedback_type == "confirm"]),
            "rejections": len([e for e in entries if e.feedback_type == "reject"]),
            "boundary_adjustments": len([e for e in entries if e.feedback_type == "adjust_bounds"]),
            "splits": len([e for e in entries if e.feedback_type == "split"]),
            "merges": len([e for e in entries if e.feedback_type == "merge"]),
            "missed_rallies": len([e for e in entries if e.feedback_type == "add_missed"]),
        }

    def get_learning_history(self) -> list[dict]:
        """Get history of weight changes over time."""
        if not self.history_file.exists():
            return []

        with open(self.history_file) as f:
            history = json.load(f)

        # Extract weight evolution
        evolution = []
        for session in history:
            evolution.append({
                "session_id": session["session_id"],
                "created_at": session["created_at"],
                "feedback_count": len(session.get("entries", [])),
                "weights_before": session.get("weights_before"),
                "weights_after": session.get("weights_after"),
            })

        return evolution

    def reset_weights(self) -> ScoringWeights:
        """Reset weights to defaults."""
        self.weights = ScoringWeights()
        self.save_weights()
        return self.weights
