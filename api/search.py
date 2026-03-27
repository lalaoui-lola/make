from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import random
import urllib.parse

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

RECIPE_SITES = [
    "marmiton.org",
    "cuisineaz.com",
    "750g.com",
    "journal des femmes.com",
    "ptitchef.com",
    "recette de cuisine.com",
]


def search_google(query, num_results=3):
    """Recherche Google et retourne les URLs des résultats."""
    encoded_query = urllib.parse.quote(f"recette {query}")
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 5}&hl=fr"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
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
                results.append({
                    "url": href,
                    "title": title,
                    "snippet": snippet
                })
                if len(results) >= num_results:
                    break

        return results
    except Exception as e:
        return {"error": str(e)}


def search_duckduckgo(query, num_results=3):
    """Recherche DuckDuckGo comme fallback si Google bloque."""
    encoded_query = urllib.parse.quote(f"recette {query}")
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
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
                results.append({
                    "url": href,
                    "title": title,
                    "snippet": snippet
                })
                if len(results) >= num_results:
                    break

        return results
    except Exception as e:
        return {"error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """GET /api/search?q=tarte+aux+pommes&n=3"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        query = params.get("q", [None])[0]
        num_results = int(params.get("n", [3])[0])

        if not query:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Parameter 'q' missing. Usage: /api/search?q=chocolate+cake"
            }).encode())
            return

        # Essayer Google d'abord, DuckDuckGo en fallback
        results = search_google(query, num_results)

        if isinstance(results, dict) and "error" in results:
            results = search_duckduckgo(query, num_results)

        if isinstance(results, dict) and "error" in results:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(results).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "query": query,
            "count": len(results),
            "results": results
        }, ensure_ascii=False).encode())

    def do_POST(self):
        """POST /api/search avec body JSON {"query": "tarte aux pommes", "num_results": 3}"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "JSON invalide"}).encode())
            return

        query = data.get("query")
        num_results = data.get("num_results", 3)

        if not query:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Champ 'query' manquant"}).encode())
            return

        results = search_google(query, num_results)

        if isinstance(results, dict) and "error" in results:
            results = search_duckduckgo(query, num_results)

        if isinstance(results, dict) and "error" in results:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(results).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "query": query,
            "count": len(results),
            "results": results
        }, ensure_ascii=False).encode())
