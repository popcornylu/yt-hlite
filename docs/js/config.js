// Configuration for the static site
// Update this URL after deploying your Cloudflare Worker

const CONFIG = {
    // Cloudflare Worker URL for fetching YouTube metadata
    // Replace with your deployed worker URL:
    // - Default: https://yt-metadata.<your-subdomain>.workers.dev
    // - Custom domain: https://api.yourdomain.com
    WORKER_URL: 'https://yt-metadata.popcorny.workers.dev',

    // For local development, uncomment this:
    // WORKER_URL: 'http://localhost:8787',
};
