"""Video compilation module for creating highlight reels."""

import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import json

from .highlight_scorer import ScoredRally


@dataclass
class CompilationConfig:
    """Configuration for video compilation."""

    context_before: float = 1.0  # Extra seconds before clip
    context_after: float = 1.5  # Extra seconds after clip
    transition_duration: float = 0.5  # Fade transition duration
    add_transitions: bool = True
    max_duration: float = 300.0  # 5 minutes max
    output_resolution: Optional[tuple[int, int]] = None  # None = keep original
    output_fps: Optional[float] = None  # None = keep original

    def to_dict(self) -> dict:
        return {
            "context_before": self.context_before,
            "context_after": self.context_after,
            "transition_duration": self.transition_duration,
            "add_transitions": self.add_transitions,
            "max_duration": self.max_duration,
            "output_resolution": self.output_resolution,
            "output_fps": self.output_fps,
        }


@dataclass
class ClipInfo:
    """Information about a clip to include in compilation."""

    rally_id: str
    start_time: float
    end_time: float
    score: float
    rank: int

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class VideoCompiler:
    """Compiles selected highlights into a final video."""

    def __init__(
        self,
        source_video: str,
        output_dir: str = "data/output",
        config: Optional[CompilationConfig] = None,
    ):
        """
        Initialize the video compiler.

        Args:
            source_video: Path to source video
            output_dir: Directory for output files
            config: Compilation configuration
        """
        self.source_video = Path(source_video)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or CompilationConfig()

        if not self.source_video.exists():
            raise FileNotFoundError(f"Source video not found: {source_video}")

        # Get video duration
        self.video_duration = self._get_video_duration()

    def _get_video_duration(self) -> float:
        """Get duration of source video."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(self.source_video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))

    def prepare_clips(
        self,
        scored_rallies: list[ScoredRally],
    ) -> list[ClipInfo]:
        """
        Prepare clip list from scored rallies.

        Args:
            scored_rallies: Selected highlights (already sorted)

        Returns:
            List of ClipInfo objects with adjusted times
        """
        clips = []
        total_duration = 0.0

        for sr in scored_rallies:
            # Apply context padding
            start = max(0, sr.rally.start_time - self.config.context_before)
            end = min(
                self.video_duration,
                sr.rally.end_time + self.config.context_after
            )

            clip = ClipInfo(
                rally_id=sr.rally.id,
                start_time=start,
                end_time=end,
                score=sr.score,
                rank=sr.rank,
            )

            # Check if we'd exceed max duration
            if total_duration + clip.duration > self.config.max_duration:
                break

            clips.append(clip)
            total_duration += clip.duration

        return clips

    def extract_clip(
        self,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> str:
        """
        Extract a single clip from the source video.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Path for output clip

        Returns:
            Path to extracted clip
        """
        duration = end_time - start_time

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", str(self.source_video),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-avoid_negative_ts", "make_zero",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg extraction failed: {result.stderr}")

        return output_path

    def compile_highlights(
        self,
        clips: list[ClipInfo],
        output_filename: Optional[str] = None,
    ) -> str:
        """
        Compile clips into a single highlight video.

        Args:
            clips: List of ClipInfo objects to include
            output_filename: Optional filename for output

        Returns:
            Path to compiled video
        """
        if not clips:
            raise ValueError("No clips to compile")

        if output_filename is None:
            output_filename = f"{self.source_video.stem}_highlights.mp4"

        output_path = self.output_dir / output_filename

        # Create temporary directory for intermediate clips
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract each clip
            clip_files = []
            for i, clip in enumerate(clips):
                clip_path = temp_path / f"clip_{i:04d}.mp4"
                self.extract_clip(
                    clip.start_time,
                    clip.end_time,
                    str(clip_path),
                )
                clip_files.append(clip_path)

            if self.config.add_transitions:
                # Compile with transitions using filter_complex
                output = self._compile_with_transitions(clip_files, str(output_path))
            else:
                # Simple concatenation
                output = self._compile_concat(clip_files, str(output_path))

        return output

    def _compile_concat(
        self,
        clip_files: list[Path],
        output_path: str,
    ) -> str:
        """Compile clips using simple concatenation."""
        # Create concat file
        concat_file = clip_files[0].parent / "concat.txt"
        with open(concat_file, "w") as f:
            for clip_path in clip_files:
                f.write(f"file '{clip_path}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")

        return output_path

    def _compile_with_transitions(
        self,
        clip_files: list[Path],
        output_path: str,
    ) -> str:
        """Compile clips with fade transitions between them."""
        if len(clip_files) == 1:
            # Just copy single clip
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(clip_files[0]),
                "-c", "copy",
                output_path
            ], check=True, capture_output=True)
            return output_path

        # For multiple clips, use xfade filter
        # Build filter complex for crossfade transitions
        n = len(clip_files)
        fade_duration = self.config.transition_duration

        # Build input arguments
        inputs = []
        for clip_path in clip_files:
            inputs.extend(["-i", str(clip_path)])

        # Build filter complex
        # This creates crossfade transitions between consecutive clips
        filter_parts = []
        audio_parts = []

        # Get all clip durations upfront
        clip_durations = [self._get_clip_duration(clip_path) for clip_path in clip_files]

        # Track cumulative duration of the output stream
        # After xfade, output duration = input1_duration + input2_duration - fade_duration
        cumulative_duration = clip_durations[0]

        for i in range(1, n):
            # xfade offset is when to start the transition on the CURRENT output stream
            # It should be the cumulative duration minus the fade duration
            offset = cumulative_duration - fade_duration

            if i == 1:
                filter_parts.append(
                    f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={offset}[v{i}]"
                )
                audio_parts.append(f"[0:a][1:a]acrossfade=d={fade_duration}[a{i}]")
            else:
                filter_parts.append(
                    f"[v{i-1}][{i}:v]xfade=transition=fade:duration={fade_duration}:offset={offset}[v{i}]"
                )
                audio_parts.append(f"[a{i-1}][{i}:a]acrossfade=d={fade_duration}[a{i}]")

            # Update cumulative duration: add new clip duration, subtract the overlap
            cumulative_duration = cumulative_duration + clip_durations[i] - fade_duration

        # Combine video and audio filters
        filter_complex = ";".join(filter_parts + audio_parts)

        # Build command
        cmd = ["ffmpeg", "-y"]
        cmd.extend(inputs)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", f"[v{n-1}]",
            "-map", f"[a{n-1}]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            output_path
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            # Fall back to simple concat if xfade fails
            return self._compile_concat(clip_files, output_path)

        return output_path

    def _get_clip_duration(self, clip_path: Path) -> float:
        """Get duration of a clip."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(clip_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 5.0  # Default fallback

        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 5.0))

    def create_preview_clip(
        self,
        rally_id: str,
        start_time: float,
        end_time: float,
    ) -> str:
        """
        Create a preview clip for a single rally (fast, lower quality for preview).

        Args:
            rally_id: ID of the rally (for filename)
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            Path to preview clip
        """
        preview_dir = self.output_dir / "previews"
        preview_dir.mkdir(exist_ok=True)

        output_path = preview_dir / f"preview_{rally_id}.mp4"

        # Return cached preview if exists
        if output_path.exists():
            return str(output_path)

        # Add context
        start = max(0, start_time - self.config.context_before)
        end = min(self.video_duration, end_time + self.config.context_after)
        duration = end - start

        # Fast preview extraction: lower quality, scaled down
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-i", str(self.source_video),
            "-t", str(duration),
            "-vf", "scale=640:-2",  # Scale to 640px width for speed
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "96k",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg preview failed: {result.stderr}")

        return str(output_path)

    def get_compilation_summary(self, clips: list[ClipInfo]) -> dict:
        """Get summary of planned compilation."""
        total_duration = sum(c.duration for c in clips)

        return {
            "num_clips": len(clips),
            "total_duration": float(total_duration),
            "total_duration_formatted": self._format_duration(total_duration),
            "clips": [
                {
                    "rally_id": c.rally_id,
                    "start": float(c.start_time),
                    "end": float(c.end_time),
                    "duration": float(c.duration),
                    "score": float(c.score),
                    "rank": int(c.rank),
                }
                for c in clips
            ],
            "config": self.config.to_dict(),
        }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
