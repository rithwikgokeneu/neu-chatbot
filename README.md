# NEU Chatbot — Data Pipeline

Scrapes all `*.northeastern.edu` pages, cleans the text, and prepares
chunked data ready for embedding + RAG.

## Project Structure

```
neu_chatbot/
├── crawler.py        # Web crawler
├── cleaner.py        # Text cleaner & chunker
├── requirements.txt
├── data/
│   ├── raw/          # One JSON per scraped page
│   └── cleaned/
│       └── chunks.jsonl   # Final chunked output
└── logs/             # Crawl & clean logs
```

## Setup

```bash
cd neu_chatbot
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 1 — Crawl

```bash
# Default run (up to 50,000 pages, 1s delay)
python crawler.py

# Faster (smaller delay, e.g. for testing)
python crawler.py --max-pages 500 --delay 0.5

# Resume a previously interrupted crawl
python crawler.py --resume
```

Each page is saved as `data/raw/<hash>.json`:
```json
{
  "url": "https://www.northeastern.edu/about/",
  "title": "About | Northeastern University",
  "subdomain": "www.northeastern.edu",
  "text": "...",
  "scraped_at": "2026-03-17T10:00:00Z"
}
```

## Step 2 — Clean & Chunk

```bash
python cleaner.py
```

Produces `data/cleaned/chunks.jsonl` — one JSON object per line:
```json
{"chunk_id": "abc123_0", "url": "...", "title": "...", "subdomain": "...", "chunk_idx": 0, "text": "..."}
```

## Step 3 — Embed & Build Vector DB (next phase)

```bash
pip install langchain chromadb sentence-transformers anthropic
```

```python
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
import json

chunks = [json.loads(l) for l in open("data/cleaned/chunks.jsonl")]
texts  = [c["text"] for c in chunks]
metas  = [{"url": c["url"], "title": c["title"]} for c in chunks]

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectordb   = Chroma.from_texts(texts, embeddings, metadatas=metas,
                                persist_directory="./chroma_db")
vectordb.persist()
print("Vector DB ready!")
```

## Notes

- The crawler respects `robots.txt` and adds a 1-second delay between requests.
- Login-walled subdomains (canvas, mail, sso, etc.) are automatically skipped.
- Run `--resume` to pick up where you left off after an interruption.
