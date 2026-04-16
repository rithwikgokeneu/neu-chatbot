"""
Live Indexer — continuously refreshes Pinecone with fresh data scraped
directly from NEU websites. Runs as a background thread every REFRESH_HOURS.

Pages are fetched, cleaned, chunked, and upserted so the vector index
always reflects current website content instead of a stale one-time crawl.
"""

import os
import re
import time
import hashlib
import logging
import threading
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# ─── Config ───────────────────────────────────────────────────────────────────

REFRESH_HOURS = 6          # re-index every 6 hours
CHUNK_WORDS   = 300        # words per chunk
OVERLAP_WORDS = 50         # word overlap between consecutive chunks
MAX_SUBPAGES  = 30         # extra linked pages to follow per seed
REQUEST_TIMEOUT = 12
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NEU-Assistant-Indexer/2.0; "
        "Educational chatbot for northeastern.edu)"
    )
}

PINECONE_INDEX = os.getenv("PINECONE_INDEX", "neu-chatbot")
EMBED_MODEL    = "all-MiniLM-L6-v2"

log = logging.getLogger("live_indexer")

# ─── Seed pages (all key NEU domains) ─────────────────────────────────────────

SEED_PAGES = [
    # ── Main & Service Portal ──────────────────────────────────────────────
    "https://www.northeastern.edu",
    "https://service.northeastern.edu/welcome",
    "https://service.northeastern.edu/kb",

    # ── Admissions ────────────────────────────────────────────────────────
    "https://admissions.northeastern.edu",
    "https://admissions.northeastern.edu/tuition-and-fees/",
    "https://admissions.northeastern.edu/first-year/",
    "https://admissions.northeastern.edu/transfer/",
    "https://graduate.northeastern.edu",
    "https://graduate.northeastern.edu/admissions/",

    # ── Registrar / Academic Calendar ─────────────────────────────────────
    "https://registrar.northeastern.edu",
    "https://registrar.northeastern.edu/faculty-staff/academic-calendar/",
    "https://registrar.northeastern.edu/students/registration/",
    "https://registrar.northeastern.edu/students/grades/",
    "https://registrar.northeastern.edu/students/transcript-requests/",

    # ── Course Catalog ────────────────────────────────────────────────────
    "https://catalog.northeastern.edu",
    "https://catalog.northeastern.edu/undergraduate/",
    "https://catalog.northeastern.edu/graduate/",

    # ── Financial Aid ─────────────────────────────────────────────────────
    "https://studentfinance.northeastern.edu",
    "https://studentfinance.northeastern.edu/paying-for-northeastern/financial-aid/",
    "https://studentfinance.northeastern.edu/paying-for-northeastern/scholarships/",
    "https://studentfinance.northeastern.edu/billing/",

    # ── Co-op & Careers ───────────────────────────────────────────────────
    "https://coop.northeastern.edu",
    "https://coop.northeastern.edu/students/",
    "https://coop.northeastern.edu/employers/",
    "https://careers.northeastern.edu",
    "https://careers.northeastern.edu/resources/",

    # ── Housing & Dining ──────────────────────────────────────────────────
    "https://housing.northeastern.edu",
    "https://housing.northeastern.edu/apply/",
    "https://housing.northeastern.edu/rates/",
    "https://nudining.com/public",
    "https://nudining.com/public/hours-of-operation",
    "https://nudining.com/public/menus",

    # ── Health, Wellness & Counseling ─────────────────────────────────────
    "https://health.northeastern.edu",
    "https://health.northeastern.edu/services/",
    "https://counseling.northeastern.edu",
    "https://counseling.northeastern.edu/services/",
    "https://recreation.northeastern.edu",
    "https://recreation.northeastern.edu/facilities/",

    # ── Student Life ──────────────────────────────────────────────────────
    "https://studentlife.northeastern.edu",
    "https://studentlife.northeastern.edu/orgs/",
    "https://alumni.northeastern.edu",

    # ── Events & News ────────────────────────────────────────────────────
    "https://events.northeastern.edu",
    "https://news.northeastern.edu",
    "https://news.northeastern.edu/research/",

    # ── Library ───────────────────────────────────────────────────────────
    "https://library.northeastern.edu",
    "https://library.northeastern.edu/services/",
    "https://library.northeastern.edu/research/",

    # ── IT Services ───────────────────────────────────────────────────────
    "https://its.northeastern.edu",
    "https://its.northeastern.edu/services/",
    "https://its.northeastern.edu/software/",

    # ── Parking & Transportation ──────────────────────────────────────────
    "https://parking.northeastern.edu",
    "https://parking.northeastern.edu/permits/",
    "https://parking.northeastern.edu/visitor-parking/",
    "https://transportation.northeastern.edu",
    "https://transportation.northeastern.edu/shuttle/",
    "https://transportation.northeastern.edu/mbta/",

    # ── Research ──────────────────────────────────────────────────────────
    "https://research.northeastern.edu",
    "https://research.northeastern.edu/funding/",

    # ── Global & International ────────────────────────────────────────────
    "https://international.northeastern.edu",
    "https://international.northeastern.edu/immigration/",
    "https://globalexperience.northeastern.edu",

    # ── Diversity & Inclusion ─────────────────────────────────────────────
    "https://diversity.northeastern.edu",

    # ── College pages ─────────────────────────────────────────────────────
    "https://coe.northeastern.edu",          # Engineering
    "https://cssh.northeastern.edu",         # Arts & Sciences
    "https://damore-mckim.northeastern.edu", # Business
    "https://law.northeastern.edu",          # Law
    "https://pharmacy.northeastern.edu",     # Pharmacy
    "https://bouve.northeastern.edu",        # Health Sciences
    "https://camd.northeastern.edu",         # Arts, Media & Design
    "https://khoury.northeastern.edu",       # Computer Science
]

# ─── Allowed domains (only follow links within these) ─────────────────────────

ALLOWED_DOMAINS = {
    "northeastern.edu",
    "nudining.com",
}

SKIP_PATTERNS = re.compile(
    r"\.(pdf|jpg|jpeg|png|gif|svg|ico|mp4|mp3|zip|exe|css|js|woff2?|ttf)$"
    r"|/login|/sso|/logout|/auth|/oauth"
    r"|canvas\.|mail\.|mymail\.|vpn\.|sharepoint\.",
    re.I,
)

# ─── Text helpers ──────────────────────────────────────────────────────────────

def _clean(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "footer",
                     "header", "aside", "form", "iframe", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r" {3,}", "  ", text)
    return text.strip()


def _chunk(text: str, url: str, title: str) -> list[dict]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step   = CHUNK_WORDS - OVERLAP_WORDS
    for i in range(0, len(words), step):
        part = " ".join(words[i : i + CHUNK_WORDS])
        if len(part) < 80:
            continue
        uid = hashlib.md5(f"{url}::{i}".encode()).hexdigest()[:16]
        chunks.append({
            "id":   uid,
            "text": part,
            "meta": {"url": url, "title": title, "chunk_i": i,
                     "indexed_at": datetime.utcnow().isoformat() + "Z"},
        })
    return chunks


def _is_allowed(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.netloc.lower()
        if SKIP_PATTERNS.search(url):
            return False
        return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


# ─── Per-page fetch ────────────────────────────────────────────────────────────

def _fetch_page(session: requests.Session, url: str) -> tuple[str, str, list[str]]:
    """
    Returns (title, clean_text, outgoing_links).
    Returns ("", "", []) on failure.
    """
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return "", "", []
        ct = r.headers.get("content-type", "")
        if "text/html" not in ct and "text/plain" not in ct:
            return "", "", []

        soup  = BeautifulSoup(r.text, "lxml")
        title = soup.title.string.strip() if (soup.title and soup.title.string) else url
        text  = _clean(soup)

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue
            abs_url = urljoin(url, href).split("#")[0].rstrip("/")
            if abs_url and _is_allowed(abs_url):
                links.append(abs_url)

        return title, text, links
    except Exception as e:
        log.debug(f"Fetch error {url}: {e}")
        return "", "", []


# ─── Upsert into ChromaDB ────────────────────────────────────────────────────

def _upsert_chunks(index, chunks: list[dict], model) -> int:
    if not chunks:
        return 0
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts).tolist()
    vectors = []
    for c, emb in zip(chunks, embeddings):
        vectors.append({
            "id": c["id"],
            "values": emb,
            "metadata": {
                "text":  c["text"][:40000],
                "url":   c["meta"].get("url", ""),
                "title": c["meta"].get("title", ""),
                "indexed_at": c["meta"].get("indexed_at", ""),
            },
        })
    # Pinecone max batch = 100
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i:i+100])
    return len(chunks)


# ─── Main indexer ─────────────────────────────────────────────────────────────

# Shared state readable from app.py
state = {
    "status":       "idle",   # idle | running | done | error
    "last_run":     None,     # datetime of last completed run
    "pages_indexed": 0,
    "chunks_upserted": 0,
    "error":        None,
}
_lock = threading.Lock()


def run_once():
    """Scrape all seed pages + subpages and upsert into ChromaDB."""
    with _lock:
        state["status"] = "running"
        state["error"]  = None

    log.info("Live indexer: starting refresh run")
    model = SentenceTransformer(EMBED_MODEL)
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(PINECONE_INDEX)

    session = requests.Session()
    session.headers.update(HEADERS)

    visited        = set()
    pages_indexed  = 0
    chunks_total   = 0

    for seed in SEED_PAGES:
        seed = seed.rstrip("/")
        if seed in visited:
            continue

        # Fetch seed
        title, text, links = _fetch_page(session, seed)
        visited.add(seed)
        if text and len(text) > 100:
            chunks = _chunk(text, seed, title)
            chunks_total += _upsert_chunks(index, chunks, model)
            pages_indexed += 1
            log.info(f"  indexed: {seed}  ({len(chunks)} chunks)")

        # Follow up to MAX_SUBPAGES unique links within the same domain
        sub_done = 0
        # Prioritise links that share the seed's path prefix
        seed_parsed = urlparse(seed)
        seed_prefix = seed_parsed.netloc + seed_parsed.path.rstrip("/")

        def priority(u):
            p = urlparse(u)
            return 0 if (p.netloc + p.path).startswith(seed_prefix) else 1

        sublinks = sorted(set(links) - visited, key=priority)

        for sub_url in sublinks:
            if sub_done >= MAX_SUBPAGES:
                break
            if sub_url in visited:
                continue
            visited.add(sub_url)

            s_title, s_text, _ = _fetch_page(session, sub_url)
            if s_text and len(s_text) > 100:
                s_chunks = _chunk(s_text, sub_url, s_title)
                chunks_total += _upsert_chunks(index, s_chunks, model)
                pages_indexed += 1
                sub_done += 1
                log.info(f"    sub: {sub_url}  ({len(s_chunks)} chunks)")

            time.sleep(0.3)   # polite delay between subpage requests

        time.sleep(0.5)   # polite delay between seed domains

    with _lock:
        state["status"]          = "done"
        state["last_run"]        = datetime.utcnow()
        state["pages_indexed"]   = pages_indexed
        state["chunks_upserted"] = chunks_total
        state["error"]           = None

    log.info(
        f"Live indexer: done — {pages_indexed} pages, {chunks_total} chunks upserted"
    )


def _loop(interval_seconds: int):
    while True:
        try:
            run_once()
        except Exception as e:
            with _lock:
                state["status"] = "error"
                state["error"]  = str(e)
            log.error(f"Live indexer error: {e}")
        time.sleep(interval_seconds)


def start(refresh_hours: float = REFRESH_HOURS):
    """Start the background indexer thread (daemon, won't block shutdown)."""
    t = threading.Thread(
        target=_loop,
        args=(int(refresh_hours * 3600),),
        daemon=True,
        name="live-indexer",
    )
    t.start()
    log.info(f"Live indexer started — refresh every {refresh_hours}h")
    return t
