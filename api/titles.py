from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import random
import urllib.parse
import re

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

RECIPE_SITES_EN = [
    "allrecipes.com",
    "foodnetwork.com",
    "simplyrecipes.com",
    "bonappetit.com",
    "delish.com",
    "tasty.co",
    "epicurious.com",
    "bbcgoodfood.com",
    "cookinglight.com",
    "seriouseats.com",
]


def clean_title(title):
    """Remove site names and extra info from title."""
    title = re.sub(r'\s*[-|–—]\s*(allrecipes|food network|simply recipes|bon app[eé]tit|delish|tasty|epicurious|bbc good food|serious eats|cooking light|recipe).*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*[-|–—]\s*\w+\.com.*$', '', title)
    title = re.sub(r'\brecipe\b\s*$', '', title, flags=re.IGNORECASE).strip()
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def search_titles_google(category, num_results=5):
    """Search Google for real recipe titles in a category."""
    query = f"best {category} recipes"
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded_query}&num={num_results + 10}&hl=en"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        seen_titles = set()

        for g in soup.select("div.g"):
            link = g.select_one("a")
            if link and link.get("href", "").startswith("http"):
                href = link["href"]
                title_el = g.select_one("h3")
                if not title_el:
                    continue
                raw_title = title_el.get_text()
                title = clean_title(raw_title)

                if not title or len(title) < 5:
                    continue
                if title.lower() in seen_titles:
                    continue
                if any(skip in title.lower() for skip in ["best", "top 10", "top 20", "list of", "collection"]):
                    continue

                seen_titles.add(title.lower())
                results.append({
                    "title": title,
                    "url": href,
                    "source": urllib.parse.urlparse(href).netloc
                })
                if len(results) >= num_results:
                    break

        return results
    except Exception as e:
        return {"error": f"Google search failed: {str(e)}"}


def search_titles_duckduckgo(category, num_results=5):
    """Search DuckDuckGo for real recipe titles (fallback)."""
    query = f"best {category} recipes"
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        seen_titles = set()

        for r in soup.select(".result"):
            link = r.select_one("a.result__a")
            if link:
                href = link.get("href", "")
                raw_title = link.get_text(strip=True)
                title = clean_title(raw_title)

                if not title or len(title) < 5:
                    continue
                if title.lower() in seen_titles:
                    continue
                if any(skip in title.lower() for skip in ["best", "top 10", "top 20", "list of", "collection"]):
                    continue

                seen_titles.add(title.lower())
                results.append({
                    "title": title,
                    "url": href,
                    "source": urllib.parse.urlparse(href).netloc
                })
                if len(results) >= num_results:
                    break

        return results
    except Exception as e:
        return {"error": f"DuckDuckGo search failed: {str(e)}"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        GET /api/titles?category=desserts&n=2
        Returns real recipe titles from the web for a given category.
        """
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        category = params.get("category", [None])[0]
        num_results = int(params.get("n", [2])[0])

        if not category:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Parameter 'category' missing. Usage: /api/titles?category=desserts&n=2"
            }).encode())
            return

        # Try Google first, DuckDuckGo as fallback
        results = search_titles_google(category, num_results)

        if isinstance(results, dict) and "error" in results:
            results = search_titles_duckduckgo(category, num_results)

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
            "category": category,
            "count": len(results),
            "titles": results
        }, ensure_ascii=False).encode())
