"""
Embed & Index
Reads data/cleaned/chunks.jsonl, embeds each chunk using
sentence-transformers, and upserts them into Pinecone.

Run:  python embed.py
Re-run anytime after crawl finishes to refresh the index.

Requires env vars:
  PINECONE_API_KEY  — your Pinecone API key
  PINECONE_INDEX    — index name (default: neu-chatbot)
"""

import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# ─── Config ───────────────────────────────────────────────────────────────────

CHUNKS_FILE    = "data/cleaned/chunks.jsonl"
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "neu-chatbot")
EMBED_MODEL    = "all-MiniLM-L6-v2"   # 384-dim, fast, good quality
BATCH_SIZE     = 100                   # Pinecone max per upsert is 100
LOG_DIR        = "logs"

# ─── Logging ──────────────────────────────────────────────────────────────────

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/embed_{datetime.now():%Y%m%d_%H%M%S}.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ─── Main ─────────────────────────────────────────────────────────────────────

def build_index() -> None:
    # Load chunks
    log.info(f"Loading chunks from {CHUNKS_FILE} ...")
    chunks = []
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    log.info(f"Loaded {len(chunks)} chunks")

    # Connect to Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

    # Create index if it doesn't exist
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX not in existing:
        log.info(f"Creating Pinecone index '{PINECONE_INDEX}' ...")
        pc.create_index(
            name=PINECONE_INDEX,
            dimension=384,          # all-MiniLM-L6-v2 output dimension
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        log.info("Index created")
    else:
        log.info(f"Using existing index '{PINECONE_INDEX}'")

    index = pc.Index(PINECONE_INDEX)

    # Load embedding model
    log.info(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)

    # Upsert in batches
    total = len(chunks)
    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]

        texts = [c["text"] for c in batch]
        embeddings = model.encode(texts).tolist()

        vectors = []
        for c, emb in zip(batch, embeddings):
            vectors.append({
                "id": c["chunk_id"],
                "values": emb,
                "metadata": {
                    "text":      c["text"][:40000],   # Pinecone metadata limit
                    "url":       c.get("url", ""),
                    "title":     c.get("title", ""),
                    "subdomain": c.get("subdomain", ""),
                },
            })

        index.upsert(vectors=vectors)
        pct = min(i + BATCH_SIZE, total)
        log.info(f"  Indexed {pct}/{total} chunks")

    stats = index.describe_index_stats()
    log.info(f"Done — {total} chunks indexed. Total vectors: {stats.get('total_vector_count', 'unknown')}")


if __name__ == "__main__":
    build_index()
