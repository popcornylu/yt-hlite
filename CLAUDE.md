# CLAUDE.md - Project Context for AI Assistants

## Project Overview

YouTube Highlight Editor - A web app for watching and editing highlights in YouTube videos. Highlights are stored in the YouTube video description using a simple text format.

**Live Site:** https://popcornylu.github.io/yt-hlite/

## Quick Start

```bash
cd docs && python -m http.server 5252    # Static site at http://localhost:5252
cd cloudflare-worker && wrangler dev     # Worker at http://localhost:8787
```

Update `docs/js/config.js` to point to local worker for dev. See `DEPLOYMENT.md` for full deployment.

**Production:** Site → https://popcornylu.github.io/yt-hlite/ | Worker → https://yt-metadata.popcorny.workers.dev

## Architecture

Two-page static site (GitHub Pages) + Cloudflare Worker (YouTube API proxy). No build step, no framework.

- `index.html` — URL input → extracts video ID → navigates to `watch.html?v=<id>`
- `watch.html` + `app.js` (~1300 lines) — Player, highlight CRUD, playback, timeline, fullscreen
- `cloudflare-worker/worker.js` — Proxies YouTube Data API v3, parses `[Highlights]` from description, optional KV caching (1hr TTL)

## File Structure

```
docs/index.html            # Home page (URL input, video ID regex extraction)
docs/watch.html            # Watch/edit page (player, sidebar, timeline, modals)
docs/css/style.css         # All styles (~1200 lines)
docs/js/config.js          # Worker URL + version
docs/js/app.js             # All client-side logic (~1300 lines)
cloudflare-worker/worker.js  # YouTube API proxy + highlight parser
```

## Features

### Watch Mode (default on page load)
- Auto-plays highlights sequentially (Play All / Stop controls)
- Read-only sidebar with highlight list, active clip highlighted
- Fullscreen overlay with progress bar; auto-enters on mobile

### Edit Mode (via Edit button or `e` key)
- Bracket recording: `[` sets start, `]` sets end at current playback position
- Delete highlights (× button or `Delete` key)
- Overlap validation (prevents overlapping highlights)
- Done → saves and returns to watch mode; Cancel → discards changes
- Draft persistence: auto-saves to localStorage on every edit; restored on reload

### Export
- Export modal with watch URL + `[Highlights]` formatted text
- Copy to clipboard button; preview toggle for playback

### Keyboard Shortcuts
- `e` — Enter edit mode | `Escape` — Watch mode / deselect / exit fullscreen
- `[` / `]` — Start/end bracket | `\` — Cancel bracket
- `←/→` — Jump ±5s | `z/x` — Jump ±2s
- `↑/↓` — Prev/Next highlight | `⌘↑/⌘↓` — First/Last highlight
- `Space` — Play/Pause | `d/s` — Speed ±0.1x | `r` — Toggle 1x/2x
- `f` — Fullscreen | `h` — Toggle sidebar | `t` — Cycle timeline zoom
- `Delete` — Delete selected highlight (edit mode)

## State Management

All state is client-side in `app.js` module scope. Server is stateless.

**Core state:** `highlights[]`, `selectedHighlightId`, `recordingStart`, `mode` ('watch'|'edit'), `highlightCounter`
**Playback:** `isPlayingAll`, `playAllClipIndex`, `playAllClips[]`
**UI:** `isFullscreen`, `highlightsPanelVisible`, `currentZoomMode`, `pixelsPerSecond`

### Highlight Object
```javascript
{ id: 'desc_1'|'manual_1', start_time: 20.0, end_time: 25.0, duration: 5.0, source: 'description'|'manual', label: null }
```

### Draft Persistence
- Key: `yt-hlite-draft-{videoId}` in localStorage
- Stores: `{ highlights, highlightCounter }`
- Auto-saves on every add/update/delete in edit mode
- Restored on page load → enters edit mode with toast; cleared by Done/Cancel

### VideoPlayer Interface
Wraps YouTube IFrame API: `getCurrentTime()`, `setCurrentTime(t)`, `play()`, `pause()`, `isPaused()`, `getDuration()`, `getPlaybackRate()`, `setPlaybackRate(r)`. Returns safe defaults when player not ready.

## API

**Endpoint:** `GET /api/yt-metadata?v=<videoId>`

**Response:**
```json
{ "videoId": "...", "title": "...", "description": "...", "highlights": [{"start_time": 20, "end_time": 25}], "channelTitle": "...", "publishedAt": "..." }
```

**Errors:** 404 (not found), 502 (YouTube API error), 500 (internal)

## Export Format

```
https://popcornylu.github.io/yt-hlite/watch.html?v=VIDEO_ID

[Highlights]
0:20 - 0:25
0:36 - 0:38
```

## URL Parsing (index.html)

Supported: `youtube.com/watch?v=ID`, `youtu.be/ID`, `youtube.com/embed/ID`, `youtube.com/v/ID`, bare 11-char ID

## Key app.js Sections (by line region)

| Region | Section |
|--------|---------|
| 1-40 | State variables and constants |
| 42-74 | VideoPlayer interface |
| 76-158 | Initialization + loadVideoData (fetch + draft restore) |
| 160-220 | YouTube IFrame API setup |
| 222-272 | Mode management (setMode, enterEdit, save, cancel) |
| 274-367 | Sequential playback |
| 368-428 | Export modal and clipboard |
| 430-505 | Splitter drag + timeline zoom |
| 506-570 | Toast notifications + draft persistence |
| 572-616 | Speed indicator + panel toggles |
| 617-770 | Keyboard shortcuts |
| 771-944 | Highlight CRUD (bracket record, create, update, delete, select) |
| 945-1132 | Rendering (highlights list, timeline, playhead, time display) |
| 1133-1152 | Time formatting + mobile detection |
| 1154-1316 | Fullscreen mode |

## Notes

- **No build step**: Plain HTML/CSS/JS, no bundler or framework
- **YouTube iframe seek precision** ~0.5s (acceptable for highlights)
- **Mobile**: Auto-enters fullscreen on player ready; CSS-only fullscreen (no native API)
- **Overlap prevention**: `wouldOverlap()` validates before creating/updating highlights
