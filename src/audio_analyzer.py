"""Audio analysis module for detecting ball hits, crowd noise, and audio patterns."""

import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import librosa


@dataclass
class AudioSegment:
    """Represents an audio segment with analysis results."""

    start_time: float  # seconds
    end_time: float  # seconds
    peak_amplitude: float
    mean_amplitude: float
    is_spike: bool = False
    spike_type: str = ""  # "hit", "crowd", "other"
    confidence: float = 0.0


@dataclass
class BallHit:
    """Represents a detected ball hit event."""

    timestamp: float  # seconds
    amplitude: float
    confidence: float
    frequency_profile: str = "unknown"  # "paddle", "table", "net"


@dataclass
class AudioAnalysis:
    """Complete audio analysis results."""

    duration: float
    sample_rate: int
    segments: list[AudioSegment] = field(default_factory=list)
    ball_hits: list[BallHit] = field(default_factory=list)
    volume_envelope: Optional[np.ndarray] = None
    volume_times: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        return {
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "num_segments": len(self.segments),
            "num_ball_hits": len(self.ball_hits),
            "segments": [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "peak_amplitude": s.peak_amplitude,
                    "is_spike": s.is_spike,
                    "spike_type": s.spike_type,
                }
                for s in self.segments
            ],
            "ball_hits": [
                {
                    "timestamp": h.timestamp,
                    "amplitude": h.amplitude,
                    "confidence": h.confidence,
                }
                for h in self.ball_hits
            ],
        }


class AudioAnalyzer:
    """Analyzes audio for ball hits, crowd noise, and patterns."""

    def __init__(self, audio_path: str):
        """
        Initialize the audio analyzer.

        Args:
            audio_path: Path to the audio file (WAV format)
        """
        self.audio_path = Path(audio_path)
        if not self.audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Load audio
        self.y, self.sr = librosa.load(str(self.audio_path), sr=22050, mono=True)
        self.duration = len(self.y) / self.sr

    def analyze(
        self,
        hit_threshold: float = 0.15,
        min_hit_interval: float = 0.2,
        segment_duration: float = 0.5,
    ) -> AudioAnalysis:
        """
        Perform complete audio analysis.

        Args:
            hit_threshold: Amplitude threshold for ball hit detection (0-1)
            min_hit_interval: Minimum time between hits in seconds
            segment_duration: Duration of analysis segments in seconds

        Returns:
            AudioAnalysis object with all results
        """
        analysis = AudioAnalysis(
            duration=self.duration,
            sample_rate=self.sr,
        )

        # Compute volume envelope for visualization
        analysis.volume_envelope, analysis.volume_times = self._compute_volume_envelope()

        # Detect ball hits
        analysis.ball_hits = self.detect_ball_hits(
            threshold=hit_threshold,
            min_interval=min_hit_interval,
        )

        # Analyze segments
        analysis.segments = self._analyze_segments(segment_duration)

        return analysis

    def _compute_volume_envelope(
        self,
        hop_length: int = 512,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute the volume envelope of the audio.

        Returns:
            Tuple of (envelope values, time values)
        """
        # RMS energy
        rms = librosa.feature.rms(y=self.y, hop_length=hop_length)[0]

        # Normalize to 0-1
        if rms.max() > 0:
            rms = rms / rms.max()

        # Compute time values
        times = librosa.frames_to_time(np.arange(len(rms)), sr=self.sr, hop_length=hop_length)

        return rms, times

    def detect_ball_hits(
        self,
        threshold: float = 0.15,
        min_interval: float = 0.2,
    ) -> list[BallHit]:
        """
        Detect ball hit sounds using onset detection and spectral analysis.

        Args:
            threshold: Amplitude threshold for hit detection
            min_interval: Minimum time between consecutive hits

        Returns:
            List of detected BallHit events
        """
        # Compute onset strength envelope
        onset_env = librosa.onset.onset_strength(
            y=self.y,
            sr=self.sr,
            hop_length=512,
            aggregate=np.median,
        )

        # Normalize
        if onset_env.max() > 0:
            onset_env = onset_env / onset_env.max()

        # Find peaks in onset envelope
        peaks = librosa.util.peak_pick(
            onset_env,
            pre_max=3,
            post_max=3,
            pre_avg=3,
            post_avg=5,
            delta=threshold,
            wait=int(min_interval * self.sr / 512),
        )

        # Convert to time
        peak_times = librosa.frames_to_time(peaks, sr=self.sr, hop_length=512)

        # Filter peaks by spectral characteristics (ball hits have specific frequency profile)
        hits = []
        for i, (peak_idx, peak_time) in enumerate(zip(peaks, peak_times)):
            # Get amplitude at peak
            amplitude = onset_env[peak_idx]

            # Analyze spectral content around the peak
            start_sample = max(0, int(peak_time * self.sr) - 512)
            end_sample = min(len(self.y), int(peak_time * self.sr) + 512)
            segment = self.y[start_sample:end_sample]

            # Check if it has the characteristic of a ball hit
            # Ball hits typically have:
            # - Sharp attack
            # - High frequency content (click/pop sound)
            # - Short duration
            confidence = self._compute_hit_confidence(segment, amplitude)

            # Higher threshold to filter out floor bounces
            if confidence > 0.4:
                hits.append(BallHit(
                    timestamp=peak_time,
                    amplitude=amplitude,
                    confidence=confidence,
                    frequency_profile="paddle",  # Passed the paddle hit test
                ))

        return hits

    def _compute_hit_confidence(self, segment: np.ndarray, amplitude: float) -> float:
        """
        Compute confidence that a segment contains a paddle ball hit (not floor bounce).

        Paddle hits: high frequency, sharp attack, short decay
        Floor bounces: lower frequency, more resonant, longer decay

        Args:
            segment: Audio segment around the potential hit
            amplitude: Onset amplitude

        Returns:
            Confidence score 0-1
        """
        if len(segment) < 256:
            return 0.0

        # Compute spectral centroid (paddle hits have HIGH frequency content)
        centroid = librosa.feature.spectral_centroid(y=segment, sr=self.sr)[0]
        mean_centroid = np.mean(centroid)

        # Paddle hits typically have centroid > 3000 Hz
        # Floor bounces typically have centroid < 2000 Hz
        if mean_centroid < 2000:
            return 0.0  # Likely a floor bounce, reject
        centroid_score = min(1.0, (mean_centroid - 2000) / 3000)

        # Compute spectral rolloff (frequency below which 85% of energy is contained)
        rolloff = librosa.feature.spectral_rolloff(y=segment, sr=self.sr, roll_percent=0.85)[0]
        mean_rolloff = np.mean(rolloff)

        # Paddle hits have higher rolloff (more high-freq energy)
        # Floor bounces have lower rolloff
        if mean_rolloff < 3000:
            return 0.0  # Likely a floor bounce
        rolloff_score = min(1.0, (mean_rolloff - 3000) / 5000)

        # Compute spectral flatness (paddle hits are more "clicky", less tonal)
        flatness = librosa.feature.spectral_flatness(y=segment)[0]
        mean_flatness = np.mean(flatness)
        # Higher flatness = more noise-like (good for paddle hits)
        flatness_score = min(1.0, mean_flatness * 5)

        # Compute zero crossing rate (high for percussive sounds)
        zcr = librosa.feature.zero_crossing_rate(segment)[0]
        mean_zcr = np.mean(zcr)
        zcr_score = min(1.0, mean_zcr * 5)

        # Combine scores with emphasis on high-frequency characteristics
        confidence = (
            amplitude * 0.2 +
            centroid_score * 0.3 +
            rolloff_score * 0.2 +
            flatness_score * 0.15 +
            zcr_score * 0.15
        )

        return float(confidence)

    def _analyze_segments(self, segment_duration: float) -> list[AudioSegment]:
        """
        Analyze audio in fixed-duration segments.

        Args:
            segment_duration: Duration of each segment in seconds

        Returns:
            List of AudioSegment objects
        """
        segments = []
        segment_samples = int(segment_duration * self.sr)
        num_segments = int(np.ceil(len(self.y) / segment_samples))

        for i in range(num_segments):
            start_sample = i * segment_samples
            end_sample = min((i + 1) * segment_samples, len(self.y))
            segment_audio = self.y[start_sample:end_sample]

            start_time = start_sample / self.sr
            end_time = end_sample / self.sr

            peak_amp = float(np.max(np.abs(segment_audio)))
            mean_amp = float(np.mean(np.abs(segment_audio)))

            segments.append(AudioSegment(
                start_time=start_time,
                end_time=end_time,
                peak_amplitude=peak_amp,
                mean_amplitude=mean_amp,
            ))

        # Mark spikes
        mean_peak = np.mean([s.peak_amplitude for s in segments])
        std_peak = np.std([s.peak_amplitude for s in segments])
        threshold = mean_peak + 1.5 * std_peak

        for segment in segments:
            if segment.peak_amplitude > threshold:
                segment.is_spike = True
                segment.spike_type = "activity"
                segment.confidence = min(1.0, (segment.peak_amplitude - threshold) / std_peak)

        return segments

    def detect_crowd_noise(self, window_size: float = 2.0) -> list[tuple[float, float, float]]:
        """
        Detect crowd noise/cheering moments.

        Args:
            window_size: Analysis window size in seconds

        Returns:
            List of (start_time, end_time, intensity) tuples
        """
        # Crowd noise characteristics:
        # - Sustained broadband noise
        # - Lower spectral centroid than ball hits
        # - Gradual attack/decay

        hop_length = 512
        window_samples = int(window_size * self.sr / hop_length)

        # Compute spectral features
        rms = librosa.feature.rms(y=self.y, hop_length=hop_length)[0]
        centroid = librosa.feature.spectral_centroid(y=self.y, sr=self.sr, hop_length=hop_length)[0]
        bandwidth = librosa.feature.spectral_bandwidth(y=self.y, sr=self.sr, hop_length=hop_length)[0]

        # Normalize
        if rms.max() > 0:
            rms = rms / rms.max()
        if centroid.max() > 0:
            centroid = centroid / centroid.max()
        if bandwidth.max() > 0:
            bandwidth = bandwidth / bandwidth.max()

        crowd_segments = []
        times = librosa.frames_to_time(np.arange(len(rms)), sr=self.sr, hop_length=hop_length)

        # Sliding window analysis
        for i in range(0, len(rms) - window_samples, window_samples // 2):
            window_rms = rms[i:i + window_samples]
            window_centroid = centroid[i:i + window_samples]
            window_bandwidth = bandwidth[i:i + window_samples]

            # Crowd noise: high RMS, moderate centroid, high bandwidth variance
            mean_rms = np.mean(window_rms)
            mean_centroid = np.mean(window_centroid)
            bandwidth_var = np.var(window_bandwidth)

            # Score based on characteristics
            if mean_rms > 0.3 and mean_centroid < 0.5 and bandwidth_var > 0.01:
                start_time = times[i]
                end_time = times[min(i + window_samples, len(times) - 1)]
                intensity = mean_rms

                # Merge with previous if overlapping
                if crowd_segments and start_time - crowd_segments[-1][1] < 0.5:
                    prev = crowd_segments.pop()
                    crowd_segments.append((prev[0], end_time, max(prev[2], intensity)))
                else:
                    crowd_segments.append((start_time, end_time, intensity))

        return crowd_segments

    def get_volume_data_for_visualization(self, num_points: int = 500) -> dict:
        """
        Get volume data suitable for web visualization.

        Args:
            num_points: Number of data points for the visualization

        Returns:
            Dict with times and volumes arrays
        """
        if self.duration <= 0:
            return {"times": [], "volumes": []}

        hop_length = max(1, int(len(self.y) / num_points))
        rms = librosa.feature.rms(y=self.y, hop_length=hop_length)[0]

        # Normalize to 0-1
        if rms.max() > 0:
            rms = rms / rms.max()

        times = librosa.frames_to_time(np.arange(len(rms)), sr=self.sr, hop_length=hop_length)

        return {
            "times": times.tolist(),
            "volumes": rms.tolist(),
        }
