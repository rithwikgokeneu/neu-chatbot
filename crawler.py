"""
Northeastern University Website Crawler
Crawls all *.northeastern.edu pages and saves raw text + metadata to data/raw/
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

# ─── Config ──────────────────────────────────────────────────────────────────

SEED_URLS = [
    "https://service.northeastern.edu/welcome",
    "https://www.northeastern.edu/",
]

ALLOWED_DOMAIN_SUFFIX = "northeastern.edu"

# Subdomains to skip (login walls, irrelevant portals, etc.)
BLOCKED_SUBDOMAINS = {
    "mail", "mymail", "outlook", "login", "sso", "idp",
    "canvas", "blackboard", "webmail", "vpn", "remote",
    "sharepoint", "myapps", "adfs",
}

# File extensions to skip
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".exe", ".dmg",
    ".css", ".js", ".woff", ".woff2", ".ttf",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NEU-Chatbot-Scraper/1.0; "
        "Educational research bot)"
    )
}

REQUEST_DELAY   = 1.0   # seconds between requests (be polite)
REQUEST_TIMEOUT = 15    # seconds
MAX_PAGES       = 50000 # safety cap
MAX_RETRIES     = 2

OUTPUT_DIR  = "data/raw"
LOG_DIR     = "logs"

# ─── Logging ─────────────────────────────────────────────────────────────────

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/crawler_{datetime.now():%Y%m%d_%H%M%S}.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def url_id(url: str) -> str:
    """Short hash used as filename."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def is_allowed(url: str) -> bool:
    """Return True if the URL belongs to *.northeastern.edu and is scrapable."""
    try:
        parsed = urlparse(url)
        host   = parsed.netloc.lower().rstrip(".")

        # Must end with northeastern.edu
        if not (host == ALLOWED_DOMAIN_SUFFIX or host.endswith("." + ALLOWED_DOMAIN_SUFFIX)):
            return False

        # Skip blocked subdomains
        subdomain = host.replace("." + ALLOWED_DOMAIN_SUFFIX, "")
        if subdomain in BLOCKED_SUBDOMAINS:
            return False

        # Skip unwanted file types
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            return False

        # Skip anchors-only or javascript links
        if parsed.scheme not in ("http", "https"):
            return False

        return True
    except Exception:
        return False


def extract_text(soup: BeautifulSoup) -> str:
    """Extract clean visible text from parsed HTML."""
    # Remove noise tags
    for tag in soup(["script", "style", "noscript", "header",
                     "footer", "nav", "aside", "form", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Return all absolute URLs found on the page."""
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base_url, href)
        # Strip fragment
        absolute = absolute.split("#")[0].rstrip("/")
        if absolute:
            links.append(absolute)
    return links


def save_page(url: str, title: str, text: str, subdomain: str) -> None:
    """Save scraped page as JSON to data/raw/."""
    doc = {
        "url":       url,
        "title":     title,
        "subdomain": subdomain,
        "text":      text,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }
    fpath = os.path.join(OUTPUT_DIR, f"{url_id(url)}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


# ─── Robots.txt cache ────────────────────────────────────────────────────────

_robots_cache: dict[str, set] = {}

def get_disallowed_paths(base_url: str) -> set:
    """Fetch and cache disallowed paths from robots.txt."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin in _robots_cache:
        return _robots_cache[origin]

    disallowed = set()
    try:
        r = requests.get(f"{origin}/robots.txt", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            for line in r.text.splitlines():
                line = line.strip()
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed.add(path)
    except Exception:
        pass

    _robots_cache[origin] = disallowed
    log.info(f"robots.txt for {origin}: {len(disallowed)} disallowed paths")
    return disallowed


def is_robots_allowed(url: str) -> bool:
    """Return False if URL path is disallowed by robots.txt."""
    disallowed = get_disallowed_paths(url)
    path = urlparse(url).path
    for d in disallowed:
        if path.startswith(d):
            return False
    return True


# ─── Main Crawler ─────────────────────────────────────────────────────────────

QUEUE_FILE = os.path.join(OUTPUT_DIR, "_queue.json")


def save_queue(queue: deque) -> None:
    with open(QUEUE_FILE, "w") as f:
        json.dump(list(queue), f)


def crawl(seed_urls: list[str], max_pages: int = MAX_PAGES, resume: bool = False) -> None:
    visited: set[str] = set()
    queue:   deque    = deque()

    if resume:
        # Load already-scraped URLs into visited, and re-extract their links into queue
        log.info("Resuming — loading visited URLs and re-building queue from saved pages...")
        all_links: list[str] = []
        for fname in os.listdir(OUTPUT_DIR):
            if fname.endswith(".json") and fname != "_queue.json":
                fpath = os.path.join(OUTPUT_DIR, fname)
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                    visited.add(data["url"])
                    # Re-parse saved page text won't give links; use queue file instead
                except Exception:
                    pass

        # Prefer saved queue file (fastest resume)
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE) as f:
                saved_q = json.load(f)
            for url in saved_q:
                if url not in visited:
                    queue.append(url)
            log.info(f"Resuming — {len(visited)} visited, {len(queue)} URLs restored from queue file")
        else:
            # No queue file: re-fetch seed pages to rediscover links
            log.info(f"No queue file found — re-fetching seed URLs to rediscover links")
            session_tmp = requests.Session()
            session_tmp.headers.update(HEADERS)
            for seed in seed_urls:
                try:
                    resp = session_tmp.get(seed, timeout=REQUEST_TIMEOUT)
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in extract_links(soup, seed):
                        if link not in visited and is_allowed(link):
                            queue.append(link)
                except Exception as e:
                    log.warning(f"Could not re-fetch seed {seed}: {e}")
            log.info(f"Resuming — {len(visited)} visited, {len(queue)} links rediscovered")
    else:
        for url in seed_urls:
            clean = url.rstrip("/")
            if clean not in visited:
                queue.append(clean)

    session      = requests.Session()
    session.headers.update(HEADERS)
    pages_done   = 0
    errors       = 0

    log.info(f"Starting crawl from {len(seed_urls)} seed URLs (max={max_pages})")

    while queue and pages_done < max_pages:
        url = queue.popleft()

        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url):
            continue

        if not is_robots_allowed(url):
            log.debug(f"BLOCKED by robots.txt: {url}")
            continue

        # Fetch with retries
        html = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type and "text/plain" not in content_type:
                        log.debug(f"Skipping non-HTML: {url}")
                        break
                    html = resp.text
                    # Follow redirect — update url to final URL
                    url = resp.url.split("#")[0].rstrip("/")
                    break
                elif resp.status_code in (301, 302):
                    break  # requests handles redirects automatically
                elif resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 10))
                    log.warning(f"Rate limited on {url}, waiting {wait}s")
                    time.sleep(wait)
                elif resp.status_code in (403, 404, 410):
                    log.debug(f"HTTP {resp.status_code}: {url}")
                    break
                else:
                    log.warning(f"HTTP {resp.status_code} on {url} (attempt {attempt})")
                    time.sleep(2 * attempt)
            except requests.RequestException as e:
                log.warning(f"Request error [{attempt}] {url}: {e}")
                time.sleep(2 * attempt)

        if not html:
            errors += 1
            continue

        # Parse
        soup  = BeautifulSoup(html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text  = extract_text(soup)

        if len(text) < 50:
            log.debug(f"Skipping near-empty page: {url}")
            continue

        parsed    = urlparse(url)
        subdomain = parsed.netloc.lower()
        save_page(url, title, text, subdomain)
        pages_done += 1

        if pages_done % 100 == 0:
            log.info(f"Progress: {pages_done} pages | queue={len(queue)} | errors={errors}")
            save_queue(queue)  # checkpoint queue so resume works

        # Enqueue new links
        for link in extract_links(soup, url):
            if link not in visited and is_allowed(link):
                queue.append(link)

        time.sleep(REQUEST_DELAY)

    save_queue(queue)  # final checkpoint
    log.info(
        f"Crawl complete: {pages_done} pages saved, "
        f"{errors} errors, {len(visited)} URLs visited"
    )


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEU website crawler")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES,
                        help="Maximum pages to crawl (default: 50000)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip URLs already saved in data/raw/")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help="Seconds between requests (default: 1.0)")
    args = parser.parse_args()

    REQUEST_DELAY = args.delay
    crawl(SEED_URLS, max_pages=args.max_pages, resume=args.resume)
