from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/api/health", methods=["GET"])
def health():
    resp = jsonify({
        "status": "ok",
        "service": "recipe-scraper",
        "version": "2.0.0",
        "endpoints": {
            "health": "/api/health",
            "titles": "/api/titles?category=desserts&n=2",
            "search": "/api/search?q=chocolate+cake&n=3",
            "scrape": "/api/scrape?url=https://example.com/recipe",
            "full": "/api/full?q=banana+bread&n=2"
        }
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
