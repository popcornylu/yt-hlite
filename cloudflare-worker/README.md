# Cloudflare Worker: YouTube Metadata API

This worker fetches YouTube video metadata and parses highlights from the video description.

## Setup

### 1. Install Wrangler CLI

```bash
npm install -g wrangler
```

### 2. Login to Cloudflare

```bash
wrangler login
```

### 3. Set YouTube API Key

```bash
wrangler secret put YOUTUBE_API_KEY
# Enter your YouTube Data API v3 key when prompted
```

### 4. (Optional) Create KV Namespace for Caching

```bash
# Create the namespace
wrangler kv:namespace create YT_CACHE

# Copy the ID from the output and update wrangler.toml:
# [[kv_namespaces]]
# binding = "YT_CACHE"
# id = "<your-namespace-id>"
```

### 5. Deploy

```bash
wrangler deploy
```

## API Endpoint

`GET /api/yt-metadata?v=<video_id>`

### Response

```json
{
  "videoId": "dQw4w9WgXcQ",
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

## Highlights Format

The worker parses highlights from the video description in this format:

```
[Highlights]
0:20 - 0:25
0:36 - 0:38
1:15 - 1:22
```

## Costs

- **Workers Free Plan**: 100,000 requests/day
- **KV Free Plan**: 100,000 reads/day, 1,000 writes/day
- **YouTube Data API**: 10,000 quota units/day (1 unit per video lookup)
