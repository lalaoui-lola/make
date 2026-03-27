from flask import Flask, request, jsonify
import requests as http_requests
from bs4 import BeautifulSoup
import random
import urllib.parse
import re

app = Flask(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def clean_title(title):
    title = re.sub(r'\s*[-|–—]\s*(allrecipes|food network|simply recipes|bon app[eé]tit|delish|tasty|epicurious|bbc good food|serious eats|cooking light|recipe).*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*[-|–—]\s*\w+\.com.*$', '', title)
    title = re.sub(r'\brecipe\b\s*$', '', title, flags=re.IGNORECASE).strip()
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def search_titles_google(category, num_results=5):
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
        response = http_requests.get(url, headers=headers, timeout=10)
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
                results.append({"title": title, "url": href, "source": urllib.parse.urlparse(href).netloc})
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return {"error": f"Google search failed: {str(e)}"}


def search_titles_duckduckgo(category, num_results=5):
    query = f"best {category} recipes"
    encoded_query = urllib.parse.quote(query)
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
                results.append({"title": title, "url": href, "source": urllib.parse.urlparse(href).netloc})
                if len(results) >= num_results:
                    break
        return results
    except Exception as e:
        return {"error": f"DuckDuckGo search failed: {str(e)}"}


@app.route("/api/titles", methods=["GET"])
def titles():
    category = request.args.get("category")
    num_results = int(request.args.get("n", 2))

    if not category:
        resp = jsonify({"error": "Parameter 'category' missing. Usage: /api/titles?category=desserts&n=2"})
        resp.status_code = 400
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    results = search_titles_google(category, num_results)
    if isinstance(results, dict) and "error" in results:
        results = search_titles_duckduckgo(category, num_results)

    if isinstance(results, dict) and "error" in results:
        resp = jsonify(results)
        resp.status_code = 500
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    resp = jsonify({"category": category, "count": len(results), "titles": results})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
