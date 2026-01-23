# CLAUDE.md - Project Context for AI Assistants

## Project Overview

Table Tennis Highlight Generator - A human-in-the-loop system for generating highlight reels from table tennis match videos.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run web server (default port 5001)
python main.py

# Run with pre-loaded video
python main.py --video /path/to/video.mp4
```

Open http://127.0.0.1:5001 in browser.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI (Flask)                           │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐ │
│  │  Index   │→ │ Candidates │→ │   Review   │→ │  Download   │ │
│  │(upload)  │  │ (review)   │  │ (compile)  │  │ (output)    │ │
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
│  │ VideoProcessor  │                      │PreferenceLearner│  │
│  │ (metadata,      │                      │ (learn from     │  │
│  │  thumbnails)    │                      │  user feedback) │  │
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
│   ├── video_processor.py    # Video metadata, frame extraction
│   ├── video_compiler.py     # FFmpeg compilation with transitions
│   └── web_ui/
│       ├── __init__.py
│       ├── app.py            # Flask routes & API endpoints
│       ├── static/
│       │   └── style.css     # All CSS styles
│       └── templates/
│           ├── base.html     # Base template with nav
│           ├── index.html    # Home - video selection
│           ├── candidates.html # Main review interface
│           ├── review.html   # Final review & compile
│           └── timeline.html # (Legacy, redirects to candidates)
├── data/
│   ├── input/                # Uploaded videos
│   ├── output/               # Compiled highlights
│   └── feedback/             # User feedback JSON files
├── main.py                   # Entry point
├── requirements.txt
├── README.md
└── CLAUDE.md                 # This file
```

## Key Data Structures

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
| `/` | GET | Home page (video selection) |
| `/set-video` | POST | Set local video path `{path: string}` |
| `/browse-video` | GET | Open native macOS file picker |
| `/upload` | POST | Upload video file |
| `/candidates` | GET | Main review page |
| `/review` | GET | Final review & compile page |
| `/api/analyze` | POST | Start video analysis |
| `/api/rallies` | GET | Get all scored rallies |
| `/api/rally/<id>/feedback` | POST | Submit feedback `{rating, decision, is_highlight}` |
| `/api/rally/<id>/adjust` | POST | Adjust boundaries `{start_frame, end_frame}` |
| `/api/compile` | POST | Compile highlights `{rally_ids: []}` |
| `/video` | GET | Stream source video |
| `/highlights/<filename>` | GET | Download compiled video |

## Web UI Features

### Candidates Page (candidates.html)
- **Timeline**: Zoomable (Cmd+/Cmd-), shows all rallies color-coded
- **Video Player**: Click timeline to seek, plays selected rally
- **Rally Info Panel**: Shows stats, rating, keep/reject buttons
- **Keyboard Shortcuts**:
  - `←/→` - Previous/Next rally
  - `↑/↓` or `G/B` - Mark Good/Bad
  - `1-5` - Star rating
  - `Space` - Play/Pause
  - `Cmd+[/]` - Adjust start/end boundary
  - `Cmd+Plus/Minus` - Zoom timeline
- **Draggable Boundaries**: Drag handles on selected rally to adjust

### Review Page (review.html)
- **Timeline**: Shows selected highlights in green
- **Preview Simulation**: Plays through clips in sequence
- **Sidebar Drawer**: Toggle to show/hide selected list
- **Compile**: Generate final video with transitions

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
min_hits_per_rally: int = 3      # Minimum hits for valid rally
max_hit_interval: float = 2.0    # Max gap between hits (seconds)
min_rally_gap: float = 2.0       # Min gap between rallies
context_before: float = 1.5      # Context padding
context_after: float = 2.0       # Context padding
```

## State Management

**In-memory state** (lost on server restart):
```python
app.state = {
    "video_processor": VideoProcessor,
    "audio_analyzer": AudioAnalyzer,
    "audio_analysis": AudioAnalysis,  # Ball hits, crowd segments
    "rally_detector": RallyDetector,
    "rallies": list[Rally],
    "scored_rallies": list[ScoredRally],
    "highlight_scorer": HighlightScorer,
    "preference_learner": PreferenceLearner,
    "video_compiler": VideoCompiler,
    "volume_data": list[float],  # For waveform display
}
```

**Persistent storage** (data/feedback/):
- User feedback saved as JSON
- Preference weights learned across sessions

## Known Issues / TODOs

1. **State lost on restart**: Rally data is in-memory. Re-analyze required after server restart.
2. **Photos app access**: Cannot directly browse Photos library. User must export first.
3. **Large videos**: No streaming analysis - loads entire audio into memory.

## Common Modifications

### Change detection sensitivity
Edit `src/audio_analyzer.py`:
- `onset_threshold` - Lower = more sensitive
- `min_confidence` - Filter weak detections

### Change scoring weights
Edit `src/highlight_scorer.py`:
```python
default_weights = {
    "duration": 3.0,      # Rally length
    "hit_count": 2.5,     # Number of hits
    "crowd_intensity": 1.5,
    "motion_intensity": 1.0,
    "confidence": 0.5,
}
```

### Add new keyboard shortcut
Edit `src/web_ui/templates/candidates.html`:
```javascript
document.addEventListener('keydown', (e) => {
    // Add in the switch statement
});
```

## Time Format

All times displayed as `HH:MM:SS.cc` (hours:minutes:seconds.centiseconds)
```javascript
function formatTime(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const centis = Math.floor((seconds % 1) * 100);
    return `${hrs.toString().padStart(2,'0')}:${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}.${centis.toString().padStart(2,'0')}`;
}
```

## Dependencies

- **Flask**: Web framework
- **librosa**: Audio analysis
- **numpy/scipy**: Signal processing
- **ffmpeg** (external): Video processing
- **osascript** (macOS): Native file picker
