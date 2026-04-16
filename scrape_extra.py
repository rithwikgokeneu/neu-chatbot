"""
Extra Site Scraper
Crawls any additional website and saves pages into the same data/raw/
directory so they get picked up by cleaner.py + embed.py.

Usage:
    python scrape_extra.py --url https://masparc.com/
    python scrape_extra.py --url https://example.com/ --max-pages 200
"""

import os
import re
import json
import time
import hashlib
import logging
import argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque

import requests
from bs4 import BeautifulSoup

OUTPUT_DIR      = "data/raw"
LOG_DIR         = "logs"
REQUEST_DELAY   = 0.5
REQUEST_TIMEOUT = 15
MAX_RETRIES     = 2

SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".zip", ".tar", ".gz", ".exe",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".pdf",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Research-Bot/1.0; Educational use)"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/extra_scrape_{datetime.now():%Y%m%d_%H%M%S}.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def url_id(url):
    return "extra_" + hashlib.md5(url.encode()).hexdigest()[:12]


def is_valid(url, allowed_netloc):
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        if p.netloc.lstrip("www.") != allowed_netloc.lstrip("www."):
            return False
        if any(p.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
            return False
        return True
    except Exception:
        return False


def extract_text(soup):
    for tag in soup(["script", "style", "noscript", "nav", "footer", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 3]
    return "\n".join(lines)


def extract_links(soup, base_url):
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith(("#", "mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href).split("#")[0].rstrip("/")
        if absolute:
            links.append(absolute)
    return links


def crawl(seed_url, max_pages):
    parsed       = urlparse(seed_url)
    allowed_host = parsed.netloc
    visited      = set()
    queue        = deque([seed_url.rstrip("/")])
    session      = requests.Session()
    session.headers.update(HEADERS)
    pages_done   = 0
    errors       = 0

    log.info(f"Crawling {allowed_host} (max={max_pages})")

    while queue and pages_done < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not is_valid(url, allowed_host):
            continue

        html = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "text/html" not in ct:
                        break
                    html = resp.text
                    url  = resp.url.split("#")[0].rstrip("/")
                    break
                elif resp.status_code in (403, 404, 410):
                    break
                elif resp.status_code == 429:
                    time.sleep(int(resp.headers.get("Retry-After", 10)))
                else:
                    time.sleep(2 * attempt)
            except requests.RequestException as e:
                log.warning(f"[{attempt}] {url}: {e}")
                time.sleep(2 * attempt)

        if not html:
            errors += 1
            continue

        soup  = BeautifulSoup(html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text  = extract_text(soup)

        if len(text) < 50:
            continue

        doc = {
            "url":        url,
            "title":      title,
            "subdomain":  allowed_host,
            "text":       text,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
        }
        fpath = os.path.join(OUTPUT_DIR, f"{url_id(url)}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)

        pages_done += 1
        log.info(f"[{pages_done}] {url}")

        for link in extract_links(soup, url):
            if link not in visited and is_valid(link, allowed_host):
                queue.append(link)

        time.sleep(REQUEST_DELAY)

    log.info(f"Done: {pages_done} pages saved, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",       required=True, help="Seed URL to crawl")
    parser.add_argument("--max-pages", type=int, default=500)
    args = parser.parse_args()
    crawl(args.url, args.max_pages)
