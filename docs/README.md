# YouTube Highlights - Static Site

A static web app for watching and editing highlights in YouTube videos. Highlights are stored in the YouTube video description using a simple text format.

## Files

```
static-site/
├── index.html      # Home page (YouTube URL input)
├── watch.html      # Watch/edit page
├── css/
│   └── style.css   # All styles
└── js/
    ├── config.js   # Configuration (Worker URL)
    └── app.js      # Main application logic
```

## Configuration

Before deploying, update `js/config.js` with your Cloudflare Worker URL:

```javascript
const CONFIG = {
    WORKER_URL: 'https://yt-metadata.YOUR_SUBDOMAIN.workers.dev',
};
```

## Local Development

```bash
cd static-site
python -m http.server 5252
```

Open http://localhost:5252 in your browser.

## Deployment

### Option 1: GitHub Pages

1. Create a new GitHub repository
2. Push this `static-site/` directory to the repo
3. Go to Settings > Pages
4. Set Source to "Deploy from a branch"
5. Select `main` branch and `/ (root)` folder
6. Your site will be live at `https://USERNAME.github.io/REPO/`

### Option 2: Cloudflare Pages

1. Connect your GitHub repo to Cloudflare Pages
2. Set build output directory to `/` (or wherever static-site contents are)
3. Deploy

### Option 3: Any Static Host

Upload the contents of this directory to any static hosting service:
- Netlify
- Vercel
- AWS S3 + CloudFront
- Firebase Hosting
- etc.

## Usage

1. Open the site
2. Paste a YouTube URL
3. If the video description contains `[Highlights]`, they'll be auto-loaded
4. Press `e` to enter edit mode
5. Use `[` and `]` keys to mark highlight start/end
6. Click "Copy for Description" to export

## Highlights Format

Highlights are stored in the YouTube video description:

```
[Highlights]
0:20 - 0:25
0:36 - 0:38
1:15 - 1:22
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `[` | Set highlight start (edit mode) |
| `]` | Set highlight end (edit mode) |
| `\` | Cancel in-progress highlight |
| `←/→` | Jump ±5 seconds |
| `z/x` | Jump ±2 seconds |
| `↑/↓` | Prev/Next highlight |
| `Space` | Play/Pause |
| `d/s` | Speed +/- 0.1x |
| `r` | Toggle 1x/2x speed |
| `h` | Toggle highlights panel |
| `t` | Cycle timeline visibility |
| `e` | Enter edit mode |
| `Escape` | Back to watch / deselect |
| `Delete` | Delete selected highlight |
