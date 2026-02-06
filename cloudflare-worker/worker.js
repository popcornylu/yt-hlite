// Cloudflare Worker: YouTube Metadata API
// Fetches video description and parses highlights

const CACHE_TTL = 3600; // Cache for 1 hour (seconds)

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return handleCORS();
    }

    const url = new URL(request.url);

    // Only handle /api/yt-metadata endpoint
    if (url.pathname !== "/api/yt-metadata") {
      return new Response("Not Found", { status: 404 });
    }

    const videoId = url.searchParams.get("v");
    if (!videoId || !/^[a-zA-Z0-9_-]{11}$/.test(videoId)) {
      return jsonResponse({ error: "Invalid video ID" }, 400);
    }

    try {
      // Check cache first (if KV is configured)
      if (env.YT_CACHE) {
        const cached = await env.YT_CACHE.get(videoId, "json");
        if (cached) {
          return jsonResponse(cached);
        }
      }

      // Fetch from YouTube API
      const apiUrl = `https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${videoId}&key=${env.YOUTUBE_API_KEY}`;
      const ytResponse = await fetch(apiUrl);

      if (!ytResponse.ok) {
        const error = await ytResponse.text();
        return jsonResponse({ error: "YouTube API error", details: error }, 502);
      }

      const data = await ytResponse.json();

      if (!data.items || data.items.length === 0) {
        return jsonResponse({ error: "Video not found" }, 404);
      }

      const snippet = data.items[0].snippet;
      const description = snippet.description || "";

      // Parse highlights from description
      const highlights = parseHighlightsFromDescription(description);

      const result = {
        videoId,
        title: snippet.title,
        description,
        highlights,
        channelTitle: snippet.channelTitle,
        publishedAt: snippet.publishedAt,
      };

      // Cache the result (if KV is configured)
      if (env.YT_CACHE) {
        await env.YT_CACHE.put(videoId, JSON.stringify(result), {
          expirationTtl: CACHE_TTL,
        });
      }

      return jsonResponse(result);
    } catch (err) {
      return jsonResponse({ error: "Internal error", message: err.message }, 500);
    }
  },
};

// Parse [Highlights] section from description
function parseHighlightsFromDescription(description) {
  if (!description) return [];

  const lines = description.split("\n");
  const highlights = [];
  let inSection = false;

  // Pattern: "M:SS - M:SS" or "H:MM:SS - H:MM:SS"
  const rangePattern = /^(\d+:\d{1,2}(?::\d{1,2})?)\s*-\s*(\d+:\d{1,2}(?::\d{1,2})?)$/;

  for (const line of lines) {
    const stripped = line.trim();

    if (stripped === "[Highlights]") {
      inSection = true;
      continue;
    }

    if (!inSection) continue;

    // Stop at empty line or another section header
    if (!stripped || (stripped.startsWith("[") && stripped.endsWith("]"))) {
      break;
    }

    const match = stripped.match(rangePattern);
    if (match) {
      const startTime = parseTimestamp(match[1]);
      const endTime = parseTimestamp(match[2]);
      if (startTime !== null && endTime !== null && endTime > startTime) {
        highlights.push({ start_time: startTime, end_time: endTime });
      }
    }
  }

  return highlights;
}

// Parse timestamp string to seconds
function parseTimestamp(ts) {
  const parts = ts.trim().split(":");
  if (parts.length === 2) {
    // M:SS
    return parseInt(parts[0]) * 60 + parseInt(parts[1]);
  } else if (parts.length === 3) {
    // H:MM:SS
    return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
  }
  return null;
}

// JSON response helper with CORS headers
function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

// CORS preflight handler
function handleCORS() {
  return new Response(null, {
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
