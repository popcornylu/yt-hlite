"""Rally detection module for identifying and analyzing table tennis rallies."""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .audio_analyzer import AudioAnalysis, BallHit


@dataclass
class Rally:
    """Represents a detected rally (point) in the video."""

    id: str
    start_frame: int  # frame number
    end_frame: int  # frame number
    fps: float  # frames per second for time conversion
    hit_count: int
    hits: list[BallHit] = field(default_factory=list)
    confidence: float = 0.0
    crowd_intensity: float = 0.0
    motion_intensity: float = 0.0

    # Feedback fields
    user_rating: Optional[int] = None  # 1-5 stars
    is_confirmed: Optional[bool] = None  # User confirmed this is a valid rally
    is_highlight: Optional[bool] = None  # User marked as highlight-worthy

    @property
    def start_time(self) -> float:
        """Start time in seconds (computed from frame)."""
        return self.start_frame / self.fps

    @property
    def end_time(self) -> float:
        """End time in seconds (computed from frame)."""
        return self.end_frame / self.fps

    @property
    def duration(self) -> float:
        """Duration of the rally in seconds."""
        return (self.end_frame - self.start_frame) / self.fps

    @property
    def duration_frames(self) -> int:
        """Duration of the rally in frames."""
        return self.end_frame - self.start_frame

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "fps": float(self.fps),
            "start_time": float(self.start_time),
            "end_time": float(self.end_time),
            "duration": float(self.duration),
            "duration_frames": int(self.duration_frames),
            "hit_count": int(self.hit_count),
            "confidence": float(self.confidence),
            "crowd_intensity": float(self.crowd_intensity),
            "motion_intensity": float(self.motion_intensity),
            "user_rating": self.user_rating,
            "is_confirmed": self.is_confirmed,
            "is_highlight": self.is_highlight,
            "hits": [
                {"timestamp": float(h.timestamp), "frame": int(h.timestamp * self.fps), "amplitude": float(h.amplitude), "confidence": float(h.confidence)}
                for h in self.hits
            ],
        }


class RallyDetector:
    """Detects rallies by analyzing ball hit patterns."""

    def __init__(
        self,
        min_hits_per_rally: int = 3,
        max_hit_interval: float = 2.0,
        min_rally_gap: float = 2.0,
        context_before: float = 1.5,
        context_after: float = 2.0,
    ):
        """
        Initialize the rally detector.

        Args:
            min_hits_per_rally: Minimum number of hits to consider a rally
            max_hit_interval: Maximum time between hits within a rally (seconds)
            min_rally_gap: Minimum gap between rallies (seconds)
            context_before: Seconds to include before first hit
            context_after: Seconds to include after last hit
        """
        self.min_hits_per_rally = min_hits_per_rally
        self.max_hit_interval = max_hit_interval
        self.min_rally_gap = min_rally_gap
        self.context_before = context_before
        self.context_after = context_after

    def detect_rallies(
        self,
        audio_analysis: AudioAnalysis,
        video_duration: float,
        fps: float,
    ) -> list[Rally]:
        """
        Detect rallies from audio analysis results.

        Args:
            audio_analysis: Audio analysis containing detected ball hits
            video_duration: Total video duration in seconds
            fps: Frames per second of the video

        Returns:
            List of detected Rally objects
        """
        hits = audio_analysis.ball_hits
        total_frames = int(video_duration * fps)

        if len(hits) < self.min_hits_per_rally:
            return []

        # Sort hits by timestamp
        sorted_hits = sorted(hits, key=lambda h: h.timestamp)

        # Group hits into rallies
        rallies = []
        current_rally_hits = [sorted_hits[0]]

        for hit in sorted_hits[1:]:
            time_since_last = hit.timestamp - current_rally_hits[-1].timestamp

            if time_since_last <= self.max_hit_interval:
                # Continue current rally
                current_rally_hits.append(hit)
            else:
                # End current rally and start new one
                if len(current_rally_hits) >= self.min_hits_per_rally:
                    rally = self._create_rally(
                        current_rally_hits,
                        len(rallies),
                        total_frames,
                        fps,
                    )
                    rallies.append(rally)

                current_rally_hits = [hit]

        # Don't forget the last rally
        if len(current_rally_hits) >= self.min_hits_per_rally:
            rally = self._create_rally(
                current_rally_hits,
                len(rallies),
                total_frames,
                fps,
            )
            rallies.append(rally)

        # Merge rallies that are too close together
        rallies = self._merge_close_rallies(rallies, total_frames, fps)

        return rallies

    def _create_rally(
        self,
        hits: list[BallHit],
        index: int,
        total_frames: int,
        fps: float,
    ) -> Rally:
        """Create a Rally object from a list of hits."""
        first_hit = hits[0].timestamp
        last_hit = hits[-1].timestamp

        # Add context and convert to frames
        start_time = max(0, first_hit - self.context_before)
        end_time = min(total_frames / fps, last_hit + self.context_after)

        start_frame = max(0, int(start_time * fps))
        end_frame = min(total_frames, int(end_time * fps))

        # Calculate confidence based on hit consistency
        if len(hits) > 1:
            intervals = [
                hits[i + 1].timestamp - hits[i].timestamp
                for i in range(len(hits) - 1)
            ]
            # Lower variance in intervals = higher confidence
            interval_variance = np.var(intervals)
            mean_interval = np.mean(intervals)

            # Typical table tennis interval is 0.3-1.0 seconds
            interval_score = 1.0 if 0.3 <= mean_interval <= 1.0 else 0.5

            # Lower variance is better
            variance_score = max(0, 1.0 - interval_variance)

            confidence = (interval_score + variance_score) / 2
        else:
            confidence = 0.5

        # Average hit confidence
        hit_confidence = np.mean([h.confidence for h in hits])
        confidence = (confidence + hit_confidence) / 2

        return Rally(
            id=f"rally_{index:04d}",
            start_frame=start_frame,
            end_frame=end_frame,
            fps=fps,
            hit_count=len(hits),
            hits=hits.copy(),
            confidence=float(confidence),
        )

    def _merge_close_rallies(
        self,
        rallies: list[Rally],
        total_frames: int,
        fps: float,
    ) -> list[Rally]:
        """Merge rallies that are closer than min_rally_gap."""
        if len(rallies) <= 1:
            return rallies

        merged = [rallies[0]]

        for rally in rallies[1:]:
            last_rally = merged[-1]
            gap = rally.start_time - last_rally.end_time

            if gap < self.min_rally_gap:
                # Merge with previous rally
                all_hits = last_rally.hits + rally.hits
                merged[-1] = self._create_rally(
                    all_hits,
                    int(last_rally.id.split("_")[1]),
                    total_frames,
                    fps,
                )
            else:
                merged.append(rally)

        # Re-number rallies
        for i, rally in enumerate(merged):
            rally.id = f"rally_{i:04d}"

        return merged

    def add_crowd_intensity(
        self,
        rallies: list[Rally],
        crowd_segments: list[tuple[float, float, float]],
    ) -> list[Rally]:
        """
        Add crowd intensity scores to rallies.

        Args:
            rallies: List of Rally objects
            crowd_segments: List of (start, end, intensity) from audio analysis

        Returns:
            Updated list of Rally objects
        """
        for rally in rallies:
            # Find overlapping crowd segments
            overlapping = []
            for start, end, intensity in crowd_segments:
                # Check for overlap
                if start <= rally.end_time and end >= rally.start_time:
                    overlapping.append(intensity)

            if overlapping:
                rally.crowd_intensity = float(np.mean(overlapping))

        return rallies

    def filter_by_confidence(
        self,
        rallies: list[Rally],
        min_confidence: float = 0.4,
    ) -> list[Rally]:
        """Filter rallies by confidence threshold."""
        return [r for r in rallies if r.confidence >= min_confidence]

    def get_rally_at_time(
        self,
        rallies: list[Rally],
        timestamp: float,
    ) -> Optional[Rally]:
        """Find the rally containing a specific timestamp."""
        for rally in rallies:
            if rally.start_time <= timestamp <= rally.end_time:
                return rally
        return None

    def get_rally_at_frame(
        self,
        rallies: list[Rally],
        frame: int,
    ) -> Optional[Rally]:
        """Find the rally containing a specific frame."""
        for rally in rallies:
            if rally.start_frame <= frame <= rally.end_frame:
                return rally
        return None

    def split_rally(
        self,
        rally: Rally,
        split_frame: int,
        total_frames: int,
        fps: float,
    ) -> tuple[Rally, Rally]:
        """
        Split a rally at a specific frame (user feedback action).

        Returns:
            Tuple of two new Rally objects
        """
        split_time = split_frame / fps
        hits_before = [h for h in rally.hits if h.timestamp < split_time]
        hits_after = [h for h in rally.hits if h.timestamp >= split_time]

        rally1 = self._create_rally(hits_before, 0, total_frames, fps) if hits_before else None
        rally2 = self._create_rally(hits_after, 1, total_frames, fps) if hits_after else None

        return rally1, rally2

    def merge_rallies(
        self,
        rally1: Rally,
        rally2: Rally,
        total_frames: int,
        fps: float,
    ) -> Rally:
        """
        Merge two rallies into one (user feedback action).

        Returns:
            New merged Rally object
        """
        all_hits = sorted(rally1.hits + rally2.hits, key=lambda h: h.timestamp)
        return self._create_rally(all_hits, 0, total_frames, fps)
