from flask import Flask, request, jsonify
import requests as http_requests
from bs4 import BeautifulSoup
import random
import urllib.parse

app = Flask(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def search_google(query, num_results=3):
    encoded_query = urllib.parse.quote(f"recipe {query}")
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 5}&hl=en"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    try:
        response = http_requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for g in soup.select("div.g"):
            link = g.select_one("a")
            if link and link.get("href", "").startswith("http"):
                href = link["href"]
                title_el = g.select_one("h3")
                title = title_el.get_text() if title_el else ""
                snippet_el = g.select_one("div.VwiC3b, span.aCOpRe")
                snippet = snippet_el.get_text() if snippet_el else ""
                results.append({"url": href, "title": title, "snippet": snippet})
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return {"error": str(e)}


def search_duckduckgo(query, num_results=3):
    encoded_query = urllib.parse.quote(f"recipe {query}")
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = http_requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for r in soup.select(".result"):
            link = r.select_one("a.result__a")
            if link:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                snippet_el = r.select_one(".result__snippet")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                results.append({"url": href, "title": title, "snippet": snippet})
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return {"error": str(e)}


@app.route("/api/search", methods=["GET"])
def search():
    query = request.args.get("q")
    num_results = int(request.args.get("n", 3))

    if not query:
        resp = jsonify({"error": "Parameter 'q' missing. Usage: /api/search?q=chocolate+cake"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    results = search_google(query, num_results)
    if isinstance(results, dict) and "error" in results:
        results = search_duckduckgo(query, num_results)

    if isinstance(results, dict) and "error" in results:
        resp = jsonify(results)
        resp.status_code = 500
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    resp = jsonify({"query": query, "count": len(results), "results": results})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
