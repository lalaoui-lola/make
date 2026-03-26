from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "service": "recipe-scraper",
            "version": "1.0.0",
            "endpoints": {
                "health": "/api/health",
                "titles": "/api/titles?category=desserts&n=2",
                "search": "/api/search?q=chocolate+cake&n=3",
                "scrape": "/api/scrape?url=https://example.com/recipe",
                "full": "/api/full?q=banana+bread&n=2"
            }
        }, ensure_ascii=False).encode())
