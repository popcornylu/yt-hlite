# YouTube Highlight Editor

A web app for watching and editing highlights in YouTube videos. Mark the best moments, share them via the video description, and let viewers watch highlights automatically.

## Try It Online

**https://popcornylu.github.io/yt-hlite/**

No installation required. Just paste a YouTube URL and start editing highlights.

## Features

- **Watch Mode**: Auto-plays highlights sequentially from the video description
- **Edit Mode**: Mark highlights with `[` / `]` bracket keys at current playback position
- **Fullscreen**: Full-screen highlight playback with overlay, auto-enters on mobile
- **Draft Persistence**: Edit-mode changes auto-saved to localStorage and restored on reload
- **Timeline**: Visual timeline with highlight segments, playhead scrubbing, and zoom
- **Keyboard-Driven**: Full keyboard shortcut support for fast editing
- **Export**: Copy highlights to clipboard in YouTube description format
- **Stateless**: Highlights are stored in the YouTube video description, not on a server

## How It Works

1. **Creator** edits highlights and copies them to the YouTube video description
2. **Viewer** opens the watch URL — highlights are parsed from the description and auto-played
3. No backend state needed for viewing; all editing is client-side

### Highlights Format

Highlights are stored in the video description as simple timestamp ranges:

```
[Highlights]
0:20 - 0:25
0:36 - 0:38
1:15 - 1:22
```

## Architecture

```
Static Site (GitHub Pages) → Cloudflare Worker → YouTube Data API
       FREE                      FREE                FREE
```

- **Static Site** (`docs/`): HTML + CSS + JS served via GitHub Pages
- **Cloudflare Worker** (`cloudflare-worker/`): Proxies YouTube Data API to fetch video metadata and description (avoids CORS)
- **All editing is client-side**: No server state needed

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `[` | Set highlight start (edit mode) |
| `]` | Set highlight end (edit mode) |
| `\` | Cancel in-progress highlight |
| `←/→` | Jump ±5 seconds |
| `z/x` | Jump ±2 seconds |
| `↑/↓` | Prev/Next highlight |
| `⌘↑/⌘↓` | First/Last highlight |
| `Space` | Play/Pause |
| `d/s` | Speed +/- 0.1x |
| `r` | Toggle 1x/2x speed |
| `f` | Toggle fullscreen |
| `h` | Toggle highlights panel |
| `t` | Cycle timeline visibility |
| `e` | Enter edit mode |
| `Escape` | Back to watch / deselect / exit fullscreen |
| `Delete` | Delete selected highlight |

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full guide. Quick overview:

```bash
# 1. Deploy Cloudflare Worker
cd cloudflare-worker
wrangler login && wrangler deploy
wrangler secret put YOUTUBE_API_KEY

# 2. Update docs/js/config.js with your Worker URL
# 3. Push to GitHub and enable GitHub Pages from /docs folder
```

**Production URLs:**
- **Site:** https://popcornylu.github.io/yt-hlite/
- **Worker:** https://yt-metadata.popcorny.workers.dev

## Local Development

```bash
# Serve the static site locally
cd docs
python -m http.server 5252
```

For the Cloudflare Worker:
```bash
cd cloudflare-worker
wrangler dev
```

## Project Structure

```
yt-hlite/
├── docs/                     # Static site (GitHub Pages)
│   ├── index.html            # Home page (URL input)
│   ├── watch.html            # Watch/edit page
│   ├── css/style.css         # Styles
│   └── js/
│       ├── config.js         # Worker URL configuration
│       └── app.js            # Client-side application logic
├── cloudflare-worker/        # YouTube metadata API proxy
│   ├── worker.js             # Cloudflare Worker code
│   ├── wrangler.toml         # Wrangler configuration
│   └── README.md             # Worker setup instructions
├── CLAUDE.md                 # AI assistant context
├── DEPLOYMENT.md             # Full deployment guide
└── README.md                 # This file
```

## License

MIT License
