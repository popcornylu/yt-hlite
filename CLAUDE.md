# CLAUDE.md - Project Context for AI Assistants

## Project Overview

YouTube Highlight Editor - A web app for watching and editing highlights in YouTube videos. Highlights are stored in the YouTube video description using a simple text format.

## Live Site

**https://popcornylu.github.io/yt-hlite/** - No installation required.

## Quick Start

### Static Site (Local Dev)

```bash
cd docs
python -m http.server 5252
```

Open http://localhost:5252 in browser, then paste a YouTube URL.

### Cloudflare Worker (Local Dev)

```bash
cd cloudflare-worker
wrangler dev
```

Update `docs/js/config.js` to point to `http://localhost:8787` for local worker.

### Full Deployment

See `DEPLOYMENT.md` for complete instructions.

**Production URLs:**
- **Site:** https://popcornylu.github.io/yt-hlite/
- **Worker:** https://yt-metadata.popcorny.workers.dev

## Architecture

Two-page static site with a Cloudflare Worker for YouTube API proxy.

```
┌─────────────────────────────────────────────────────────────────┐
│                         WORKFLOW                                │
│                                                                 │
│  1. Creator edits highlights, copies to YouTube description     │
│  2. Viewer opens /watch?v=<id> → highlights parsed from desc   │
│  3. Watch mode: auto-plays highlights sequentially              │
│  4. Edit mode: bracket recording, delete                        │
│  5. Export: "Copy for Description" → clipboard                  │
└─────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────┐
│                  Static Site (GitHub Pages)                      │
│                                                                 │
│  ┌──────────────┐    ┌────────────────────────────────────────┐ │
│  │  /           │ →  │  /watch?v=<id>                        │ │
│  │  URL input   │    │  ┌─────────────┬────────────────────┐ │ │
│  │ (index.html) │    │  │ Watch mode  │ Edit mode          │ │ │
│  └──────────────┘    │  │ (read-only, │ (bracket record,   │ │ │
│                      │  │  auto-play) │  delete)            │ │ │
│                      │  └─────────────┴────────────────────┘ │ │
│                      │  (watch.html + app.js)                 │ │
│                      └────────────────────────────────────────┘ │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    fetch /api/yt-metadata?v=<id>
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               Cloudflare Worker (yt-metadata)                   │
│                                                                 │
│  - Proxies YouTube Data API v3                                  │
│  - Returns title, description, parsed highlights                │
│  - Optional KV caching (1 hour TTL)                             │
│  - CORS headers for cross-origin access                         │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
yt-hlite/
├── docs/                     # Static site (GitHub Pages)
│   ├── index.html            # Home page (URL input)
│   ├── watch.html            # Watch/edit page
│   ├── css/style.css         # All styles
│   ├── js/
│   │   ├── config.js         # Worker URL configuration
│   │   └── app.js            # Client-side application logic (~1000 lines)
│   └── README.md             # Static site docs
├── cloudflare-worker/        # YouTube metadata API proxy
│   ├── worker.js             # Cloudflare Worker code
│   ├── wrangler.toml         # Wrangler configuration
│   └── README.md             # Worker setup instructions
├── CLAUDE.md                 # This file
├── DEPLOYMENT.md             # Full deployment guide
└── README.md                 # Project README
```

## Key Components

### Static Site (`docs/`)

#### `index.html` - Home Page
- YouTube URL input form
- Client-side video ID extraction (regex)
- Navigates to `watch.html?v=<id>`

#### `watch.html` - Watch/Edit Page
- YouTube IFrame player
- Draggable splitter between video and highlights panel
- Timeline with segments and playhead
- Loading/error/empty states
- Keyboard shortcuts help panel

#### `app.js` - Application Logic (~1000 lines)
- `VideoPlayer` interface wrapping YouTube IFrame API
- Highlight CRUD (all client-side, no server calls for editing)
- Sequential playback (watch mode)
- Bracket recording (`[` start, `]` end)
- Timeline rendering and zoom
- Splitter drag
- Keyboard shortcuts
- Copy for Description export

#### `config.js` - Configuration
```javascript
const CONFIG = {
    WORKER_URL: 'https://yt-metadata.popcorny.workers.dev',
};
```

### Cloudflare Worker (`cloudflare-worker/`)

#### `worker.js` - YouTube Metadata Proxy
- Single endpoint: `GET /api/yt-metadata?v=<videoId>`
- Fetches from YouTube Data API v3 (requires `YOUTUBE_API_KEY` secret)
- Parses `[Highlights]` section from description
- Optional KV caching (`YT_CACHE` namespace)
- Returns: `{ videoId, title, description, highlights, channelTitle, publishedAt }`

## Web UI Features

### Watch Mode (default when highlights exist)
- **Auto-play**: Highlights play sequentially on page load
- **Read-only sidebar**: Shows highlight list, active clip highlighted
- **Play All / Stop** controls

### Edit Mode (default when no highlights)
- **Bracket recording**: `[` starts, `]` ends a highlight at current playback position
- **Delete**: Remove individual highlights (× button)
- **Copy for Description**: Export watch URL + highlights to clipboard

### Keyboard Shortcuts
- `e` - Enter edit mode
- `Escape` - Return to watch mode / deselect
- `[` / `]` - Start/end bracket (edit mode)
- `\` - Cancel in-progress bracket
- `←/→` - Jump ±5 seconds
- `z/x` - Jump ±2 seconds
- `↑/↓` - Prev / Next highlight
- `⌘↑/⌘↓` - First / Last highlight
- `Space` - Play/Pause
- `d/s` - Speed +/- 0.1x
- `r` - Toggle 1x/2x
- `h` - Toggle highlights panel
- `t` - Cycle timeline visibility
- `Delete` - Delete selected highlight (edit mode)

## State Management

The app is **fully stateless on the server side**. All state is client-side in `app.js`:

```javascript
// Core state (in app.js)
let highlights = [];           // Array of highlight objects
let selectedHighlightId = null;
let recordingStart = null;     // Bracket recording in progress
let mode = 'watch';            // 'watch' | 'edit'
let highlightCounter = 0;      // For generating unique IDs

// Playback state
let isPlayingAll = false;
let playAllClipIndex = 0;
let playAllClips = [];
```

### Highlight Object
```javascript
{
    id: 'desc_1' | 'manual_1',     // Unique ID
    start_time: 20.0,               // Seconds
    end_time: 25.0,                 // Seconds
    duration: 5.0,                   // Computed
    source: 'description' | 'manual',
    label: null,
}
```

## API

### Cloudflare Worker Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/yt-metadata?v=<id>` | GET | Fetch YouTube video metadata + parsed highlights |

### Response Format
```json
{
    "videoId": "abc123def45",
    "title": "Video Title",
    "description": "Full description text...",
    "highlights": [
        { "start_time": 20, "end_time": 25 },
        { "start_time": 36, "end_time": 38 }
    ],
    "channelTitle": "Channel Name",
    "publishedAt": "2024-01-01T00:00:00Z"
}
```

## YouTube URL Parsing

Supported URL formats (client-side regex in `index.html`):
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://www.youtube.com/v/VIDEO_ID`
- Bare 11-character video ID

## Export Format

### Copy for Description (clipboard)
```
https://popcornylu.github.io/yt-hlite/watch.html?v=VIDEO_ID

[Highlights]
0:20 - 0:25
0:36 - 0:38
1:15 - 1:22
```

## Notes

- **Two-page architecture**: `index.html` (URL input) → `watch.html?v=<id>` (watch + edit)
- **Fully client-side editing**: No server calls for CRUD — highlights managed in JS array
- **Stateless**: Highlights parsed from YouTube description on each load via Worker
- **YouTube iframe seek precision** ~0.5s (acceptable for highlights)
- **No build step**: Plain HTML/CSS/JS, no bundler or framework
