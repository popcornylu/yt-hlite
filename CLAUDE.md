# CLAUDE.md - Project Context for AI Assistants

## Project Overview

Table Tennis Highlight Generator - A human-in-the-loop system for generating highlight reels from table tennis match videos. Supports both local video files and YouTube URLs.

## Live Site

**https://popcornylu.github.io/yt-hlite/** - No installation required.

## Quick Start

### Option 1: Local Development (Flask Server)

```bash
# Install dependencies
pip install -r requirements.txt

# Run web server (default port 5252)
python main.py
```

Open http://127.0.0.1:5252 in browser, then paste a YouTube URL or use a local video file.

### Option 2: Cloud Deployment (Static Site + Cloudflare Worker)

See `DEPLOYMENT.md` for full instructions. Quick overview:

```bash
# 1. Deploy Cloudflare Worker
cd cloudflare-worker
wrangler login
wrangler deploy
wrangler secret put YOUTUBE_API_KEY

# 2. Update config and deploy static site
# Edit docs/js/config.js with your Worker URL
# Push to GitHub and enable GitHub Pages from /docs folder
```

**Production URLs:**
- **Site:** https://popcornylu.github.io/yt-hlite/
- **Worker:** https://yt-metadata.popcorny.workers.dev

**Architecture:**
```
Static Site (GitHub Pages) → Cloudflare Worker → YouTube Data API
       FREE                      FREE                FREE
```

## Architecture

Two-page design: `/` (URL input) and `/watch?v=<id>` (watch + edit).

```
┌─────────────────────────────────────────────────────────────────┐
│                         WORKFLOW                                │
│                                                                 │
│  1. Creator edits highlights, copies to YouTube description     │
│  2. Viewer opens /watch?v=<id> → highlights parsed from desc   │
│  3. Watch mode: auto-plays highlights sequentially              │
│  4. Edit mode: bracket recording, delete, auto-detect           │
│  5. Export: "Copy for Description" → clipboard                  │
│     or: Compile Video → yt-dlp download → ffmpeg cut → MP4     │
└─────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web UI (Flask) - Two Pages                   │
│                                                                 │
│  ┌──────────────┐    ┌────────────────────────────────────────┐ │
│  │  /           │ →  │  /watch?v=<id>                        │ │
│  │  URL input   │    │  ┌─────────────┬────────────────────┐ │ │
│  │  (index.html)│    │  │ Watch mode  │ Edit mode          │ │ │
│  └──────────────┘    │  │ (read-only, │ (bracket record,   │ │ │
│                      │  │  auto-play) │  delete, detect)   │ │ │
│                      │  └─────────────┴────────────────────┘ │ │
│                      │  (watch.html)                          │ │
│                      └────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Core Modules                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ AudioAnalyzer   │  │ RallyDetector   │  │DescriptionParser│ │
│  │ (ball hits,     │  │ (group hits     │  │ (parse/format   │ │
│  │  crowd noise)   │  │  into rallies)  │  │  highlights)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           ↓                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │YouTubeProcessor │  │ VideoCompiler   │  │HighlightDetector│ │
│  │ (yt-dlp audio   │  │ (ffmpeg concat) │  │ (Highlight      │ │
│  │  & video DL)    │  │                 │  │  dataclass)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
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
│   ├── highlight_detector.py # Highlight dataclass & create_highlight()
│   ├── description_parser.py # Parse/format highlights in YouTube descriptions
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
│           ├── index.html    # Home - YouTube URL input (redirects to /watch)
│           ├── watch.html    # Main page - watch/edit mode with YouTube player
│           ├── editor.html   # (legacy, redirects to /watch)
│           ├── preview.html  # (legacy, redirects to /watch)
│           ├── export.html   # (legacy, redirects to /watch)
│           ├── candidates.html # (legacy, redirects to /watch)
│           └── review.html   # (legacy, redirects to /watch)
├── data/
│   ├── output/               # Downloaded audio/video, compiled highlights
│   └── feedback/             # User feedback JSON files
├── docs/                     # Cloud deployment - static site (GitHub Pages)
│   ├── index.html            # Home page (URL input)
│   ├── watch.html            # Watch/edit page
│   ├── css/style.css         # All styles
│   └── js/
│       ├── config.js         # Worker URL configuration
│       └── app.js            # Client-side application logic
├── cloudflare-worker/        # Cloud deployment - API worker
│   ├── worker.js             # Cloudflare Worker code
│   ├── wrangler.toml         # Wrangler configuration
│   └── README.md             # Worker setup instructions
├── main.py                   # Entry point (Flask server)
├── requirements.txt
├── README.md
├── DEPLOYMENT.md             # Cloud deployment guide
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

### Highlight (highlight_detector.py)
```python
@dataclass
class Highlight:
    id: str                    # "highlight_0001"
    start_time: float          # Seconds
    end_time: float            # Seconds
    source: str                # "manual" | "auto" | "description"
    label: Optional[str]

    def to_dict() -> dict
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

### Description Format (description_parser.py)
```python
parse_highlights_from_description(text) -> list[dict]   # Extract from YouTube description
format_highlights_for_description(highlights) -> str     # Format for YouTube description
```

## API Endpoints

### Pages
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page (YouTube URL input) |
| `/watch?v=<id>` | GET | Watch/edit page (stateless, parses highlights from description) |
| `/editor`, `/preview`, `/export`, `/candidates`, `/review`, `/timeline` | GET | Legacy redirects → `/watch` |

### Watch/Edit APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/watch/init` | POST | Lazy backend init for edit mode `{video_id, highlights}` |
| `/api/highlights` | GET | Get all highlights |
| `/api/highlight` | POST | Create highlight `{start_time, end_time}` |
| `/api/highlight/<id>` | PUT | Update highlight `{start_time, end_time}` |
| `/api/highlight/<id>` | DELETE | Delete highlight |
| `/api/auto-detect` | POST | Auto-detect highlights via audio analysis |
| `/api/export-highlight-description` | GET | Export highlights for YouTube description |
| `/api/compile-highlights` | POST | Compile highlights into video `{highlight_ids}` |

### Legacy/Shared APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/set-youtube` | POST | Set YouTube URL `{url: string}` |
| `/api/youtube-info` | GET | Get YouTube video metadata |
| `/api/analyze` | POST | Start video analysis (downloads audio) |
| `/api/rallies` | GET | Get all scored rallies |
| `/api/compile` | POST | Compile rallies into video `{rally_ids: []}` |
| `/highlights/<filename>` | GET | Download compiled video |

## Web UI Features

### Index Page (`/`, index.html)
- **YouTube URL Input**: Paste any YouTube URL format, client-side video ID extraction
- Navigates directly to `/watch?v=<id>` (no server round-trip)

### Watch Page (`/watch?v=<id>`, watch.html)
- **Stateless page load**: Highlights parsed from YouTube description server-side
- **YouTube Player**: Embedded iframe with YouTube IFrame API
- **Two modes** toggled via `data-mode` attribute on `<body>`:

#### Watch Mode (default when highlights exist)
- **Auto-play**: Highlights play sequentially on page load
- **Read-only sidebar**: Shows highlight list, active clip highlighted
- **Play All / Stop** controls

#### Edit Mode (default when no highlights)
- **Bracket recording**: `[` starts, `]` ends a highlight at current playback position
- **Delete**: Remove individual highlights (× button)
- **Auto-detect**: Run audio analysis to find highlights automatically
- **Copy for Description**: Export watch URL + highlights to clipboard (also in watch mode)
- **Lazy backend init**: `/api/watch/init` called only on first edit mode entry

#### Keyboard Shortcuts
- `e` - Enter edit mode
- `Escape` - Return to watch mode / deselect
- `[` / `]` - Start/end bracket (edit mode)
- `\` - Cancel in-progress bracket
- `←/→` - Navigate highlights
- `↑/↓` - Adjust playback speed
- `h` - Toggle highlights panel
- `t` - Cycle timeline visibility
- `Space` - Play/Pause

## State Management

The `/watch` page loads **statelessly** — highlights are parsed from the YouTube description on each request. Backend `app.state` is only initialized lazily when entering edit mode (via `/api/watch/init`).

**In-memory state** (lost on server restart, initialized lazily):
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
    "highlights": list[Highlight],         # Manual highlight editing
    "highlight_counter": int,              # For generating unique IDs
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

## Export Formats

### Copy for Description (clipboard)
```
https://example.com/watch?v=VIDEO_ID

[Highlights]
0:20 - 0:25
0:36 - 0:38
1:15 - 1:22
```

### Timecode Export (legacy)
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

- **Two-page architecture**: `/` (URL input) → `/watch?v=<id>` (watch + edit)
- **Stateless watch page**: Highlights parsed from YouTube description on each load, no backend state needed for read-only viewing
- **Lazy backend init**: `app.state` only populated when user enters edit mode
- **Audio download is fast** (~10-30 seconds for typical video)
- **Video download only when compiling** (on-demand)
- **YouTube iframe seek precision** ~0.5s (acceptable for highlights)
- **Legacy templates** (editor, preview, export, candidates, review) still exist but all routes redirect to `/watch`
