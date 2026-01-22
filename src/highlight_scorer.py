"""Highlight scoring module for ranking rallies by excitement/interest."""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .rally_detector import Rally


@dataclass
class ScoringWeights:
    """Weights for different scoring factors."""

    rally_length: float = 3.0  # Longer rallies score higher
    hit_count: float = 2.5  # More hits = more exciting
    crowd_intensity: float = 1.5  # Crowd reactions
    motion_intensity: float = 1.0  # Visual action
    confidence: float = 0.5  # Detection confidence bonus

    def to_dict(self) -> dict:
        return {
            "rally_length": self.rally_length,
            "hit_count": self.hit_count,
            "crowd_intensity": self.crowd_intensity,
            "motion_intensity": self.motion_intensity,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScoringWeights":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ScoredRally:
    """A rally with its calculated highlight score."""

    rally: Rally
    score: float
    score_breakdown: dict = field(default_factory=dict)
    rank: int = 0

    def to_dict(self) -> dict:
        result = self.rally.to_dict()
        result.update({
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "rank": self.rank,
        })
        return result


class HighlightScorer:
    """Scores and ranks rallies for highlight potential."""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        Initialize the highlight scorer.

        Args:
            weights: Scoring weights (uses defaults if not provided)
        """
        self.weights = weights or ScoringWeights()

    def score_rally(self, rally: Rally) -> ScoredRally:
        """
        Calculate highlight score for a single rally.

        Args:
            rally: Rally to score

        Returns:
            ScoredRally with calculated score
        """
        breakdown = {}

        # Rally length score (longer is better, normalized to ~10 seconds)
        length_score = min(rally.duration / 10.0, 2.0) * self.weights.rally_length
        breakdown["rally_length"] = length_score

        # Hit count score (more hits = more exciting, normalized to ~15 hits)
        hit_score = min(rally.hit_count / 15.0, 2.0) * self.weights.hit_count
        breakdown["hit_count"] = hit_score

        # Crowd intensity score (0-1 from audio analysis)
        crowd_score = rally.crowd_intensity * self.weights.crowd_intensity
        breakdown["crowd_intensity"] = crowd_score

        # Motion intensity score (0-1 from motion analysis)
        motion_score = rally.motion_intensity * self.weights.motion_intensity
        breakdown["motion_intensity"] = motion_score

        # Confidence bonus
        confidence_score = rally.confidence * self.weights.confidence
        breakdown["confidence"] = confidence_score

        # Calculate total score (normalize to 0-100)
        raw_score = sum(breakdown.values())

        # Max possible score (for normalization)
        max_score = (
            2.0 * self.weights.rally_length +
            2.0 * self.weights.hit_count +
            1.0 * self.weights.crowd_intensity +
            1.0 * self.weights.motion_intensity +
            1.0 * self.weights.confidence
        )

        normalized_score = (raw_score / max_score) * 100 if max_score > 0 else 0

        return ScoredRally(
            rally=rally,
            score=float(normalized_score),
            score_breakdown=breakdown,
        )

    def score_all(self, rallies: list[Rally]) -> list[ScoredRally]:
        """
        Score all rallies and return sorted by score.

        Args:
            rallies: List of Rally objects

        Returns:
            List of ScoredRally objects sorted by score (highest first)
        """
        scored = [self.score_rally(rally) for rally in rallies]

        # Sort by score (descending)
        scored.sort(key=lambda x: x.score, reverse=True)

        # Assign ranks
        for i, sr in enumerate(scored):
            sr.rank = i + 1

        return scored

    def select_highlights(
        self,
        scored_rallies: list[ScoredRally],
        target_duration: float = 180.0,  # 3 minutes
        max_highlights: int = 15,
        min_score: float = 30.0,
    ) -> list[ScoredRally]:
        """
        Select the best highlights within duration constraints.

        Args:
            scored_rallies: List of ScoredRally objects (already sorted)
            target_duration: Target total duration in seconds
            max_highlights: Maximum number of highlights to include
            min_score: Minimum score threshold

        Returns:
            List of selected highlights
        """
        selected = []
        total_duration = 0.0

        for sr in scored_rallies:
            if len(selected) >= max_highlights:
                break

            if sr.score < min_score:
                continue

            if total_duration + sr.rally.duration > target_duration * 1.2:  # 20% buffer
                continue

            selected.append(sr)
            total_duration += sr.rally.duration

        return selected

    def update_weights_from_feedback(
        self,
        scored_rallies: list[ScoredRally],
        learning_rate: float = 0.1,
    ) -> ScoringWeights:
        """
        Adjust weights based on user feedback.

        Uses user ratings to adjust weights so that highly-rated rallies
        would score higher with the new weights.

        Args:
            scored_rallies: Rallies with user ratings
            learning_rate: How much to adjust weights

        Returns:
            Updated ScoringWeights
        """
        rated_rallies = [
            sr for sr in scored_rallies
            if sr.rally.user_rating is not None
        ]

        if len(rated_rallies) < 3:
            return self.weights  # Not enough feedback

        # Normalize ratings to -1 to 1 (3 is neutral)
        rating_diffs = []
        for sr in rated_rallies:
            expected_rating = 1 + (sr.score / 25)  # Map 0-100 score to 1-5 rating
            actual_rating = sr.rally.user_rating
            diff = actual_rating - expected_rating
            rating_diffs.append((sr, diff))

        # Calculate feature correlations with rating differences
        features = {
            "rally_length": [],
            "hit_count": [],
            "crowd_intensity": [],
            "motion_intensity": [],
            "confidence": [],
        }

        for sr, diff in rating_diffs:
            features["rally_length"].append(sr.score_breakdown.get("rally_length", 0))
            features["hit_count"].append(sr.score_breakdown.get("hit_count", 0))
            features["crowd_intensity"].append(sr.score_breakdown.get("crowd_intensity", 0))
            features["motion_intensity"].append(sr.score_breakdown.get("motion_intensity", 0))
            features["confidence"].append(sr.score_breakdown.get("confidence", 0))

        diffs = [d for _, d in rating_diffs]

        # Update weights based on correlation with rating differences
        new_weights = ScoringWeights(
            rally_length=self.weights.rally_length,
            hit_count=self.weights.hit_count,
            crowd_intensity=self.weights.crowd_intensity,
            motion_intensity=self.weights.motion_intensity,
            confidence=self.weights.confidence,
        )

        for feature_name, values in features.items():
            if np.std(values) > 0:
                correlation = np.corrcoef(values, diffs)[0, 1]
                if not np.isnan(correlation):
                    adjustment = correlation * learning_rate
                    current_weight = getattr(self.weights, feature_name)
                    new_weight = max(0.1, current_weight + adjustment)
                    setattr(new_weights, feature_name, new_weight)

        self.weights = new_weights
        return new_weights

    def apply_user_overrides(
        self,
        scored_rallies: list[ScoredRally],
    ) -> list[ScoredRally]:
        """
        Apply user feedback overrides to scoring.

        - User-confirmed highlights get score boost
        - User-rejected rallies get score penalty
        - User ratings directly influence ranking

        Args:
            scored_rallies: List of ScoredRally objects

        Returns:
            Re-sorted list with adjustments
        """
        for sr in scored_rallies:
            # Apply confirmation bonus/penalty
            if sr.rally.is_highlight is True:
                sr.score = min(100, sr.score * 1.5)  # 50% boost for confirmed highlights
            elif sr.rally.is_highlight is False:
                sr.score = sr.score * 0.3  # Significant penalty for rejected

            # Apply rating adjustment
            if sr.rally.user_rating is not None:
                # Rating 5 = +20%, Rating 1 = -40%
                rating_multiplier = 0.8 + (sr.rally.user_rating - 1) * 0.15
                sr.score = sr.score * rating_multiplier

        # Re-sort
        scored_rallies.sort(key=lambda x: x.score, reverse=True)

        # Re-assign ranks
        for i, sr in enumerate(scored_rallies):
            sr.rank = i + 1

        return scored_rallies

    def get_score_summary(self, scored_rallies: list[ScoredRally]) -> dict:
        """Get summary statistics for scored rallies."""
        if not scored_rallies:
            return {
                "count": 0,
                "mean_score": 0,
                "max_score": 0,
                "min_score": 0,
                "total_duration": 0,
            }

        scores = [sr.score for sr in scored_rallies]
        durations = [sr.rally.duration for sr in scored_rallies]

        return {
            "count": len(scored_rallies),
            "mean_score": float(np.mean(scores)),
            "max_score": float(max(scores)),
            "min_score": float(min(scores)),
            "std_score": float(np.std(scores)),
            "total_duration": float(sum(durations)),
            "mean_duration": float(np.mean(durations)),
            "mean_hit_count": float(np.mean([sr.rally.hit_count for sr in scored_rallies])),
        }
