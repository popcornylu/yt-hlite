# CLAUDE.md - Project Context for AI Assistants

## Project Overview

Table Tennis Highlight Generator - A human-in-the-loop system for generating highlight reels from table tennis match videos. Supports both local video files and YouTube URLs.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run web server (default port 5252)
python main.py
```

Open http://127.0.0.1:5252 in browser, then paste a YouTube URL or use a local video file.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WORKFLOW                                │
│                                                                 │
│  YouTube URL → yt-dlp (audio only) → Audio Analysis → Rallies  │
│       ↓                                                         │
│  YouTube iframe ← Timeline ← Rally Detection                    │
│       ↓                                                         │
│  Preview (seek iframe to timestamps)                            │
│       ↓                                                         │
│  Export Options:                                                │
│    1. Timecodes (instant) → clipboard                           │
│    2. Compile Video → yt-dlp download → ffmpeg cut → MP4        │
└─────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI (Flask)                           │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐ │
│  │  Index   │→ │ Candidates │→ │   Review   │→ │  Export     │ │
│  │(YouTube) │  │ (review)   │  │ (compile)  │  │ (output)    │ │
│  └──────────┘  └────────────┘  └────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Core Modules                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ AudioAnalyzer   │→ │ RallyDetector   │→ │HighlightScorer  │ │
│  │ (ball hits,     │  │ (group hits     │  │ (rank rallies)  │ │
│  │  crowd noise)   │  │  into rallies)  │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           ↓                                         ↓          │
│  ┌─────────────────┐                      ┌─────────────────┐  │
│  │YouTubeProcessor │                      │PreferenceLearner│  │
│  │ (yt-dlp audio   │                      │ (learn from     │  │
│  │  & video DL)    │                      │  user feedback) │  │
│  └─────────────────┘                      └─────────────────┘  │
│                              ↓                                  │
│                    ┌─────────────────┐                         │
│                    │ VideoCompiler   │                         │
│                    │ (ffmpeg concat) │                         │
│                    └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
tt-highlight/
├── src/
│   ├── __init__.py
│   ├── audio_analyzer.py     # Ball hit detection via spectrogram
│   ├── rally_detector.py     # Group hits into Rally objects
│   ├── highlight_scorer.py   # Score & rank rallies (ScoredRally)
│   ├── preference_learner.py # Learn weights from user feedback
│   ├── video_processor.py    # Video/YouTube processing, metadata
│   ├── video_compiler.py     # FFmpeg compilation with transitions
│   └── web_ui/
│       ├── __init__.py
│       ├── app.py            # Flask routes & API endpoints
│       ├── static/
│       │   └── style.css     # All CSS styles
│       └── templates/
│           ├── base.html     # Base template with nav
│           ├── index.html    # Home - YouTube URL input
│           ├── candidates.html # Main review interface
│           └── review.html   # Final review & export
├── data/
│   ├── output/               # Downloaded audio/video, compiled highlights
│   └── feedback/             # User feedback JSON files
├── main.py                   # Entry point
├── requirements.txt
├── README.md
└── CLAUDE.md                 # This file
```

## Key Data Structures

### YouTubeProcessor (video_processor.py)
```python
class YouTubeProcessor:
    video_id: str              # YouTube video ID (11 chars)
    url: str                   # Full YouTube URL
    audio_path: str            # Path to downloaded WAV
    video_path: str            # Path to downloaded MP4 (on-demand)
    metadata: YouTubeMetadata  # Title, duration, fps, thumbnail

    def get_metadata() -> YouTubeMetadata   # Get video info via yt-dlp
    def download_audio() -> str             # Download audio only (fast)
    def download_video() -> str             # Download full video (for compile)
```

### Rally (rally_detector.py)
```python
@dataclass
class Rally:
    id: str                    # "rally_0001"
    start_frame: int           # Frame number (use for tracking)
    end_frame: int             # Frame number
    fps: float                 # For time conversion
    hit_count: int
    hits: list[BallHit]
    confidence: float          # 0-1
    crowd_intensity: float     # 0-1
    motion_intensity: float    # 0-1
    user_rating: Optional[int] # 1-5 stars
    is_confirmed: Optional[bool]
    is_highlight: Optional[bool]

    # Computed properties
    start_time -> float        # start_frame / fps
    end_time -> float          # end_frame / fps
    duration -> float          # seconds
```

### ScoredRally (highlight_scorer.py)
```python
@dataclass
class ScoredRally:
    rally: Rally
    score: float               # Weighted score
    rank: int
    component_scores: dict     # Individual component scores
    is_selected: bool          # Auto-selected for highlights
    user_decision: Optional[str]  # "keep" | "reject" | None
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page (YouTube URL input) |
| `/set-youtube` | POST | Set YouTube URL `{url: string}` |
| `/api/youtube-info` | GET | Get YouTube video metadata |
| `/candidates` | GET | Main review page |
| `/review` | GET | Final review & export page |
| `/api/analyze` | POST | Start video analysis (downloads audio) |
| `/api/rallies` | GET | Get all scored rallies |
| `/api/rally/<id>/adjust` | POST | Adjust boundaries `{start_frame, end_frame}` |
| `/api/export-timecodes` | GET | Export timecodes as text |
| `/api/compile` | POST | Compile highlights `{rally_ids: []}` (downloads video) |
| `/highlights/<filename>` | GET | Download compiled video |

## Web UI Features

### Index Page (index.html)
- **YouTube URL Input**: Paste any YouTube URL format
- **Video Preview**: Shows thumbnail and title after URL validation

### Candidates Page (candidates.html)
- **YouTube Player**: Embedded iframe with YouTube IFrame API
- **Timeline**: Zoomable (Cmd+/Cmd-), shows all rallies color-coded
- **Rally Info Panel**: Shows stats, rating, keep/reject buttons
- **Keyboard Shortcuts**:
  - `←/→` - Previous/Next rally
  - `↑/↓` - Adjust playback speed
  - `1-5` - Star rating
  - `Space` - Play/Pause
  - `Cmd+[/]` - Set start/end boundary at current position
  - `Cmd+Plus/Minus` - Zoom timeline

### Review Page (review.html)
- **YouTube Player**: Embedded iframe for preview
- **Timeline**: Shows selected highlights in green
- **Preview Simulation**: Plays through clips in sequence
- **Export Options**:
  - **Export Timecodes**: Instant - copies timestamps to clipboard
  - **Compile Video**: Downloads video, compiles MP4 with transitions

## State Management

**In-memory state** (lost on server restart):
```python
app.state = {
    "youtube_processor": YouTubeProcessor,  # For YouTube mode
    "video_processor": VideoProcessor,      # For local video mode
    "audio_analyzer": AudioAnalyzer,
    "audio_analysis": AudioAnalysis,
    "rally_detector": RallyDetector,
    "rallies": list[Rally],
    "scored_rallies": list[ScoredRally],
    "highlight_scorer": HighlightScorer,
    "preference_learner": PreferenceLearner,
    "video_compiler": VideoCompiler,
    "volume_data": list[float],
}

app.config = {
    "SOURCE_TYPE": "youtube" | "local",
    "YOUTUBE_VIDEO_ID": str | None,
    "VIDEO_PATH": str | None,
}
```

## YouTube URL Parsing

Supported URL formats:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://www.youtube.com/v/VIDEO_ID`

```python
def extract_youtube_video_id(url: str) -> str:
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
    ]
    # Returns 11-character video ID
```

## Dependencies

- **Flask**: Web framework
- **librosa**: Audio analysis
- **numpy/scipy**: Signal processing
- **ffmpeg** (external): Video processing
- **yt-dlp**: YouTube downloading

## Timecode Export Format

```
0:20.22-0:25.36
0:36.11-0:38.02
1:15.00-1:22.45
```

## Compilation Config (video_compiler.py)

```python
@dataclass
class CompilationConfig:
    context_before: float = 1.0   # Seconds before rally
    context_after: float = 1.5    # Seconds after rally
    transition_duration: float = 0.5  # Fade transition
    add_transitions: bool = True
    max_duration: float = 300.0   # 5 min max
```

## Detection Parameters (rally_detector.py)

```python
min_hits_per_rally: int = 4      # Minimum hits for valid rally
max_hit_interval: float = 1.2    # Max gap between hits (seconds)
min_rally_gap: float = 4.0       # Min gap between rallies
context_before: float = 1.0      # Context padding
context_after: float = 1.5       # Context padding
```

## Notes

- **Audio download is fast** (~10-30 seconds for typical video)
- **Video download only when compiling** (on-demand)
- **YouTube iframe seek precision** ~0.5s (acceptable for highlights)
- **Boundary adjustment** uses time inputs (frame-accurate not possible with YouTube)
