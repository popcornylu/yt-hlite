# Cloud Deployment Guide - Static-First Architecture

This guide walks you through deploying the YouTube Highlights app as a static site with a Cloudflare Worker backend.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────┐
│  Static Site    │────▶│  Cloudflare Worker  │────▶│ YouTube API │
│  (GitHub Pages) │     │  /api/yt-metadata   │     │   v3        │
│  FREE           │     │  FREE (100k/day)    │     │  FREE tier  │
└─────────────────┘     └─────────────────────┘     └─────────────┘
         │                        │
         ▼                        ▼
   Custom Domain          Cloudflare KV (cache)
   (Cloudflare DNS)       FREE
```

**Total Cost: $0/month** (within free tier limits)

---

## Prerequisites

- GitHub account (for static hosting)
- Cloudflare account (free)
- YouTube Data API key (free, 10k quota/day)
- Domain name (optional, ~$10-15/year)

---

## Step 1: Get YouTube Data API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "yt-highlight-viewer")
3. Enable **YouTube Data API v3**:
   - Go to "APIs & Services" → "Library"
   - Search "YouTube Data API v3" → Enable
4. Create API key:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy the key (you'll add it to Cloudflare Worker)
5. (Optional) Restrict the API key:
   - Click on the key → "API restrictions"
   - Select "YouTube Data API v3" only

---

## Step 2: Deploy Cloudflare Worker

### 2.1 Install Wrangler CLI

```bash
npm install -g wrangler
```

### 2.2 Login to Cloudflare

```bash
wrangler login
```

### 2.3 Deploy the Worker

```bash
cd cloudflare-worker
wrangler deploy
```

### 2.4 Add YouTube API Key as Secret

```bash
wrangler secret put YOUTUBE_API_KEY
# Enter your YouTube API key from Step 1 when prompted
```

### 2.5 (Optional) Create KV Namespace for Caching

```bash
# Create the namespace
wrangler kv:namespace create YT_CACHE

# Copy the ID from the output and update wrangler.toml
# Then redeploy:
wrangler deploy
```

### 2.6 Test the Worker

Your worker URL will be: `https://yt-metadata.<your-subdomain>.workers.dev`

Test it:
```bash
curl "https://yt-metadata.<your-subdomain>.workers.dev/api/yt-metadata?v=dQw4w9WgXcQ"
```

Should return JSON with title, description, and parsed highlights.

---

## Step 3: Configure Static Site

Update `docs/js/config.js` with your Worker URL:

```javascript
const CONFIG = {
    WORKER_URL: 'https://yt-metadata.<your-subdomain>.workers.dev',
};
```

---

## Step 4: Deploy Static Site to GitHub Pages

### 4.1 Create GitHub Repository

1. Create a new repository on GitHub (e.g., `yt-highlights`)
2. Push the `docs/` contents to the repo:

```bash
cd docs
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<username>/yt-highlights.git
git push -u origin main
```

### 4.2 Enable GitHub Pages

1. Go to repo **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, folder: `/ (root)`
4. Click **Save**

Your site will be live at: `https://<username>.github.io/yt-highlights/`

### Local Testing

To test locally before deploying:

```bash
cd docs
python -m http.server 5252
```

Open http://localhost:5252 in your browser.

---

## Step 5: Custom Domain Setup (Optional)

### 5.1 Add Domain to Cloudflare

1. In Cloudflare dashboard, click **Add a Site**
2. Enter your domain name
3. Select **Free** plan
4. Cloudflare will scan existing DNS records
5. Update your domain's nameservers to Cloudflare's (at your registrar)

### 5.2 Configure DNS for GitHub Pages

In Cloudflare DNS, add these records:

| Type  | Name  | Content                  | Proxy   |
|-------|-------|--------------------------|---------|
| CNAME | `@`   | `<username>.github.io`   | Proxied |
| CNAME | `www` | `<username>.github.io`   | Proxied |

In GitHub repo **Settings** → **Pages**:
- Custom domain: `yourdomain.com`
- Check "Enforce HTTPS"

### 5.3 Configure Custom Domain for Worker (Optional)

If you want `api.yourdomain.com` instead of `*.workers.dev`:

1. In Cloudflare DNS, add:
   - Type: `AAAA`, Name: `api`, Content: `100::` (placeholder)
2. In Workers → your worker → **Triggers** → **Custom Domains**
3. Add: `api.yourdomain.com`
4. Update `config.js` with the new URL

---

## Summary Checklist

- [ ] Get YouTube Data API key from Google Cloud Console
- [ ] Install Wrangler CLI (`npm install -g wrangler`)
- [ ] Login to Cloudflare (`wrangler login`)
- [ ] Deploy Worker (`cd cloudflare-worker && wrangler deploy`)
- [ ] Add YouTube API key as secret (`wrangler secret put YOUTUBE_API_KEY`)
- [ ] (Optional) Set up KV namespace for caching
- [ ] Test Worker endpoint
- [ ] Update `docs/js/config.js` with Worker URL
- [ ] Push static site to GitHub
- [ ] Enable GitHub Pages
- [ ] (Optional) Set up custom domain

---

## Verification

1. Open your GitHub Pages URL (or custom domain)
2. Enter a YouTube video ID that has `[Highlights]` in description
3. Verify highlights load and video plays
4. Test bracket recording `[` / `]` in edit mode
5. Test "Copy for Description" export

---

## Cost Summary

| Service            | Free Tier           | Expected Usage    |
|--------------------|---------------------|-------------------|
| Cloudflare Worker  | 100,000 req/day     | ~100-1000/day     |
| Cloudflare KV      | 100,000 reads/day   | ~100-1000/day     |
| YouTube Data API   | 10,000 quota/day    | ~400/day (100 videos) |
| GitHub Pages       | Unlimited           | ✅                |
| Cloudflare DNS     | Free                | ✅                |

**Total: $0/month** (unless you exceed limits)

---

## Troubleshooting

### "Failed to fetch video metadata"
- Check that `config.js` has the correct Worker URL
- Verify the Worker is deployed (`wrangler deploy`)
- Check the Worker logs in Cloudflare dashboard

### "YouTube API error"
- Verify the YouTube API key is set as a secret
- Check that YouTube Data API v3 is enabled in Google Cloud Console
- Check API quota in Google Cloud Console

### "Video not found"
- The video ID might be invalid
- The video might be private or deleted

### CORS errors
- The Worker should handle CORS automatically
- Check browser console for specific error messages
