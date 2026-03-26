# Recipe Scraper API

Recipe scraper deployed on Vercel (free). Built for Make.com automation.

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Check API status |
| `GET /api/titles?category=desserts&n=2` | Find real recipe titles for a category |
| `GET /api/search?q=chocolate+cake&n=3` | Search recipe URLs on Google/DuckDuckGo |
| `GET /api/scrape?url=https://...` | Scrape a recipe page (ingredients, steps, etc) |
| `GET /api/full?q=banana+bread&n=2` | Search + Scrape in one call (AI-ready) |

## Deploy to Vercel

1. Push to GitHub
2. Go to https://vercel.com/new
3. Import the GitHub repo
4. Click **Deploy**
5. Open your URL — you'll see the web interface

## Usage in Make.com

Use **HTTP > Make a Request** module:
- **URL**: `https://your-url.vercel.app/api/full?q={{recipe_title}}`
- **Method**: GET
- **Parse response**: Yes

The `context_for_ai` field contains text ready for AI prompts.
