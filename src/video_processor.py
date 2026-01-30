"""Video processing module for loading videos, extracting audio, and generating thumbnails."""

import os
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2


@dataclass
class VideoMetadata:
    """Metadata extracted from a video file."""

    path: str
    duration: float  # seconds
    fps: float
    width: int
    height: int
    frame_count: int
    audio_sample_rate: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "duration": self.duration,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "audio_sample_rate": self.audio_sample_rate,
        }


class VideoProcessor:
    """Handles video loading, metadata extraction, and thumbnail generation."""

    def __init__(self, video_path: str, output_dir: str = "data/output"):
        """
        Initialize the video processor.

        Args:
            video_path: Path to the input video file
            output_dir: Directory for output files
        """
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self.metadata: Optional[VideoMetadata] = None
        self._cap: Optional[cv2.VideoCapture] = None

    def extract_metadata(self) -> VideoMetadata:
        """Extract video metadata using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(self.video_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        data = json.loads(result.stdout)

        # Find video stream
        video_stream = None
        audio_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream

        if video_stream is None:
            raise ValueError("No video stream found in file")

        # Parse frame rate (can be "30/1" or "29.97")
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = map(float, fps_str.split("/"))
            fps = num / den if den != 0 else 30.0
        else:
            fps = float(fps_str)

        duration = float(data.get("format", {}).get("duration", 0))

        self.metadata = VideoMetadata(
            path=str(self.video_path),
            duration=duration,
            fps=fps,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            frame_count=int(video_stream.get("nb_frames", int(duration * fps))),
            audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else None,
        )

        return self.metadata

    def extract_audio(self, output_path: Optional[str] = None) -> str:
        """
        Extract audio track from video to WAV file.

        Args:
            output_path: Optional path for output WAV file

        Returns:
            Path to the extracted audio file
        """
        if output_path is None:
            output_path = self.output_dir / f"{self.video_path.stem}_audio.wav"
        else:
            output_path = Path(output_path)

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(self.video_path),
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # PCM 16-bit
            "-ar", "22050",  # Sample rate suitable for audio analysis
            "-ac", "1",  # Mono
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")

        return str(output_path)

    def generate_thumbnails(
        self,
        num_thumbnails: int = 20,
        thumbnail_width: int = 160,
        output_dir: Optional[str] = None
    ) -> list[dict]:
        """
        Generate thumbnail images at regular intervals throughout the video.

        Args:
            num_thumbnails: Number of thumbnails to generate
            thumbnail_width: Width of each thumbnail (height scales proportionally)
            output_dir: Directory to save thumbnails

        Returns:
            List of dicts with timestamp and thumbnail path
        """
        if self.metadata is None:
            self.extract_metadata()

        if output_dir is None:
            thumb_dir = self.output_dir / "thumbnails"
        else:
            thumb_dir = Path(output_dir)
        thumb_dir.mkdir(parents=True, exist_ok=True)

        interval = self.metadata.duration / num_thumbnails
        thumbnails = []

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {self.video_path}")

        try:
            for i in range(num_thumbnails):
                timestamp = i * interval
                cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ret, frame = cap.read()

                if not ret:
                    continue

                # Resize thumbnail
                height = int(frame.shape[0] * thumbnail_width / frame.shape[1])
                thumbnail = cv2.resize(frame, (thumbnail_width, height))

                # Save thumbnail
                thumb_path = thumb_dir / f"thumb_{i:04d}_{timestamp:.2f}s.jpg"
                cv2.imwrite(str(thumb_path), thumbnail)

                thumbnails.append({
                    "index": i,
                    "timestamp": timestamp,
                    "path": str(thumb_path),
                })
        finally:
            cap.release()

        return thumbnails

    def generate_thumbnail_strip(
        self,
        num_frames: int = 50,
        frame_width: int = 80,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate a horizontal strip of thumbnails for timeline visualization.

        Args:
            num_frames: Number of frames in the strip
            frame_width: Width of each frame
            output_path: Path for the output image

        Returns:
            Path to the thumbnail strip image
        """
        if self.metadata is None:
            self.extract_metadata()

        if output_path is None:
            output_path = self.output_dir / f"{self.video_path.stem}_strip.jpg"
        else:
            output_path = Path(output_path)

        interval = self.metadata.duration / num_frames
        frames = []

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {self.video_path}")

        try:
            for i in range(num_frames):
                timestamp = i * interval
                cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ret, frame = cap.read()

                if not ret:
                    # Use blank frame if read fails
                    frame = np.zeros((90, frame_width, 3), dtype=np.uint8)
                else:
                    # Resize frame
                    height = int(frame.shape[0] * frame_width / frame.shape[1])
                    frame = cv2.resize(frame, (frame_width, height))

                frames.append(frame)
        finally:
            cap.release()

        # Ensure all frames have the same height
        max_height = max(f.shape[0] for f in frames)
        padded_frames = []
        for frame in frames:
            if frame.shape[0] < max_height:
                pad = np.zeros((max_height - frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
                frame = np.vstack([frame, pad])
            padded_frames.append(frame)

        # Concatenate horizontally
        strip = np.hstack(padded_frames)
        cv2.imwrite(str(output_path), strip)

        return str(output_path)

    def extract_frame_at_time(self, timestamp: float) -> np.ndarray:
        """
        Extract a single frame at a specific timestamp.

        Args:
            timestamp: Time in seconds

        Returns:
            Frame as numpy array (BGR format)
        """
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {self.video_path}")

        try:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()
            if not ret:
                raise RuntimeError(f"Could not read frame at timestamp {timestamp}")
            return frame
        finally:
            cap.release()

    def extract_clip(
        self,
        start_time: float,
        end_time: float,
        output_path: Optional[str] = None
    ) -> str:
        """
        Extract a clip from the video.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Path for the output clip

        Returns:
            Path to the extracted clip
        """
        if output_path is None:
            output_path = self.output_dir / f"{self.video_path.stem}_clip_{start_time:.1f}_{end_time:.1f}.mp4"
        else:
            output_path = Path(output_path)

        duration = end_time - start_time

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", str(self.video_path),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg clip extraction failed: {result.stderr}")

        return str(output_path)


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


import re


def extract_youtube_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL")


@dataclass
class YouTubeMetadata:
    """Metadata extracted from a YouTube video."""

    video_id: str
    title: str
    duration: float  # seconds
    fps: float
    thumbnail: str
    url: str
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "duration": self.duration,
            "fps": self.fps,
            "thumbnail": self.thumbnail,
            "url": self.url,
            "description": self.description,
        }


class YouTubeProcessor:
    """Handles YouTube video downloading and processing."""

    # Use /tmp for caching downloads across sessions
    CACHE_DIR = Path("/tmp/youtube-cache")

    def __init__(self, video_id: str, output_dir: str = "data/output"):
        """
        Initialize the YouTube processor.

        Args:
            video_id: YouTube video ID (11 characters)
            output_dir: Directory for output files (for compilation output)
        """
        self.video_id = video_id
        self.url = f"https://www.youtube.com/watch?v={video_id}"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Cache directory for this video
        self.cache_dir = self.CACHE_DIR / video_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.audio_path: Optional[str] = None
        self.video_path: Optional[str] = None
        self.metadata: Optional[YouTubeMetadata] = None

        # Check for existing cached files
        self._check_cached_files()

    def _check_cached_files(self):
        """Check for existing cached audio/video files."""
        audio_file = self.cache_dir / "audio.wav"
        video_file = self.cache_dir / "video.mp4"

        if audio_file.exists():
            self.audio_path = str(audio_file)
            print(f"[YouTubeProcessor] Found cached audio: {self.audio_path}")

        if video_file.exists():
            self.video_path = str(video_file)
            print(f"[YouTubeProcessor] Found cached video: {self.video_path}")

    def is_audio_cached(self) -> bool:
        """Check if audio is already downloaded."""
        return self.audio_path is not None and Path(self.audio_path).exists()

    def is_video_cached(self) -> bool:
        """Check if video is already downloaded."""
        return self.video_path is not None and Path(self.video_path).exists()

    def get_metadata(self) -> YouTubeMetadata:
        """Get video metadata via yt-dlp."""
        if self.metadata:
            return self.metadata

        cmd = ["yt-dlp", "--dump-json", "--no-download", self.url]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed to get metadata: {result.stderr}")

        info = json.loads(result.stdout)

        self.metadata = YouTubeMetadata(
            video_id=self.video_id,
            title=info.get("title", "Unknown"),
            duration=float(info.get("duration", 0)),
            fps=float(info.get("fps", 30) or 30),
            thumbnail=info.get("thumbnail", ""),
            url=self.url,
            description=info.get("description", ""),
        )

        return self.metadata

    def download_audio(self) -> str:
        """Download audio only (for analysis). Returns path to WAV file."""
        output = self.cache_dir / "audio.wav"

        # Check if already cached
        if output.exists():
            self.audio_path = str(output)
            print(f"[YouTubeProcessor] Using cached audio: {self.audio_path}")
            return self.audio_path

        print(f"[YouTubeProcessor] Downloading audio to: {output}")

        # Download as wav for librosa compatibility
        cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "-x",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", str(output),
            "--postprocessor-args", "ffmpeg:-ar 22050 -ac 1",
            self.url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp audio download failed: {result.stderr}")

        self.audio_path = str(output)
        print(f"[YouTubeProcessor] Audio downloaded: {self.audio_path}")
        return self.audio_path

    def download_video(self) -> str:
        """Download full video (for compilation). Returns path to MP4 file."""
        output = self.cache_dir / "video.mp4"

        # Check if already cached
        if output.exists():
            self.video_path = str(output)
            print(f"[YouTubeProcessor] Using cached video: {self.video_path}")
            return self.video_path

        print(f"[YouTubeProcessor] Downloading video to: {output}")

        cmd = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(output),
            self.url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp video download failed: {result.stderr}")

        self.video_path = str(output)
        print(f"[YouTubeProcessor] Video downloaded: {self.video_path}")
        return self.video_path

    def get_video_path(self) -> Optional[str]:
        """Get path to downloaded video, if available."""
        output = self.cache_dir / "video.mp4"
        if output.exists():
            self.video_path = str(output)
            return self.video_path
        return None

    def get_cache_info(self) -> dict:
        """Get information about cached files."""
        audio_file = self.cache_dir / "audio.wav"
        video_file = self.cache_dir / "video.mp4"

        def get_file_size(path: Path) -> Optional[str]:
            if path.exists():
                size = path.stat().st_size
                if size > 1024 * 1024 * 1024:
                    return f"{size / (1024*1024*1024):.1f} GB"
                elif size > 1024 * 1024:
                    return f"{size / (1024*1024):.1f} MB"
                elif size > 1024:
                    return f"{size / 1024:.1f} KB"
                return f"{size} B"
            return None

        return {
            "cache_dir": str(self.cache_dir),
            "audio_cached": audio_file.exists(),
            "audio_size": get_file_size(audio_file),
            "video_cached": video_file.exists(),
            "video_size": get_file_size(video_file),
        }
