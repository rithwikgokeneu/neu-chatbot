"""
Data Cleaner & Chunker
Reads raw JSON files from data/raw/, cleans text, splits into chunks,
and writes data/cleaned/chunks.jsonl — ready for embedding.
"""

import os
import re
import json
import logging
from datetime import datetime

# ─── Config ───────────────────────────────────────────────────────────────────

RAW_DIR     = "data/raw"
CLEANED_DIR = "data/cleaned"
OUTPUT_FILE = os.path.join(CLEANED_DIR, "chunks.jsonl")
LOG_DIR     = "logs"

CHUNK_SIZE    = 400   # words per chunk
CHUNK_OVERLAP = 50    # words overlap between consecutive chunks
MIN_CHUNK_LEN = 30    # words — discard shorter chunks

# ─── Logging ──────────────────────────────────────────────────────────────────

os.makedirs(CLEANED_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/cleaner_{datetime.now():%Y%m%d_%H%M%S}.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─── Text Cleaning ────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    # Remove non-printable / control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multiple spaces / tabs
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Collapse 3+ consecutive blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove lines that are pure symbols / very short noise
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < 3:
            continue
        # Skip lines that are entirely non-alphanumeric (nav separators, etc.)
        if re.fullmatch(r"[^a-zA-Z0-9]+", stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


# ─── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words  = text.split()
    chunks = []
    step   = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if len(chunk.split()) >= MIN_CHUNK_LEN:
            chunks.append(chunk)
    return chunks


# ─── Main ─────────────────────────────────────────────────────────────────────

def process() -> None:
    raw_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".json") and f != "_queue.json"]
    log.info(f"Processing {len(raw_files)} raw files → {OUTPUT_FILE}")

    total_chunks = 0
    skipped      = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for idx, fname in enumerate(raw_files, 1):
            fpath = os.path.join(RAW_DIR, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    doc = json.load(f)
            except Exception as e:
                log.warning(f"Could not read {fname}: {e}")
                skipped += 1
                continue

            url       = doc.get("url", "")
            title     = doc.get("title", "")
            subdomain = doc.get("subdomain", "")
            raw_text  = doc.get("text", "")

            cleaned = clean_text(raw_text)
            if not cleaned:
                skipped += 1
                continue

            chunks = chunk_text(cleaned)
            for i, chunk in enumerate(chunks):
                record = {
                    "chunk_id":  f"{fname[:-5]}_{i}",
                    "url":       url,
                    "title":     title,
                    "subdomain": subdomain,
                    "chunk_idx": i,
                    "text":      chunk,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

            if idx % 500 == 0:
                log.info(f"  {idx}/{len(raw_files)} files | {total_chunks} chunks so far")

    log.info(
        f"Done: {total_chunks} chunks written, "
        f"{skipped} files skipped → {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    process()
