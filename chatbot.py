"""
NEU Chatbot — RAG powered by Pinecone + Ollama (local, free, no API key)
Usage:
    python chatbot.py                  # interactive terminal chat
    python chatbot.py --query "..."    # single question mode
    python chatbot.py --model llama3   # choose a different model
"""

import os
import argparse
import logging

import ollama
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# ─── Config ───────────────────────────────────────────────────────────────────

PINECONE_INDEX = os.getenv("PINECONE_INDEX", "neu-chatbot")
EMBED_MODEL    = "all-MiniLM-L6-v2"
TOP_K          = 5
MODEL          = "llama3.2"   # fast 2GB model already on your machine

SYSTEM_PROMPT = (
    "You are an official assistant for Northeastern University. "
    "Answer questions using ONLY the provided context excerpts from the NEU website. "
    "Be concise and helpful. Always mention the source URL at the end of your answer. "
    "If the context doesn't have enough information, say so and suggest visiting "
    "northeastern.edu or contacting the relevant office."
)

logging.basicConfig(level=logging.WARNING)

# ─── Vector DB ────────────────────────────────────────────────────────────────

def load_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index(PINECONE_INDEX)


def load_embed_model():
    return SentenceTransformer(EMBED_MODEL)


def retrieve(index, embed_model, query: str) -> list[dict]:
    query_vec = embed_model.encode(query).tolist()
    results = index.query(vector=query_vec, top_k=TOP_K, include_metadata=True)
    chunks = []
    for match in results.get("matches", []):
        score = match.get("score", 0)
        meta = match.get("metadata", {})
        chunks.append({
            "text": meta.get("text", ""),
            "meta": {"title": meta.get("title", ""), "url": meta.get("url", "")},
            "score": round(score, 3),
        })
    return chunks


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        title = c["meta"].get("title", "")
        url   = c["meta"].get("url", "")
        parts.append(f"[{i}] {title}\nURL: {url}\n{c['text']}")
    return "\n\n---\n\n".join(parts)

# ─── Chat ─────────────────────────────────────────────────────────────────────

def ask(index, embed_model, query: str, history: list[dict], model: str) -> tuple[str, list[dict]]:
    chunks  = retrieve(index, embed_model, query)
    context = build_context(chunks)

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{
            "role": "user",
            "content": (
                f"Context from Northeastern University website:\n\n"
                f"{context}\n\n---\n\nQuestion: {query}"
            ),
        }]
    )

    response = ollama.chat(model=model, messages=messages)
    answer   = response["message"]["content"]

    updated_history = history + [
        {"role": "user",      "content": query},
        {"role": "assistant", "content": answer},
    ]
    return answer, updated_history

# ─── CLI ──────────────────────────────────────────────────────────────────────

def interactive(index, embed_model, model: str) -> None:
    history: list[dict] = []
    print(f"\n{'='*48}")
    print(f"  Northeastern University Chatbot")
    print(f"  Model: {model}")
    print(f"  Type 'exit' to quit")
    print(f"{'='*48}\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "bye"):
            print("Goodbye!")
            break

        print("\nNEU Bot: ", end="", flush=True)
        answer, history = ask(index, embed_model, query, history, model)
        print(answer)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="NEU RAG Chatbot (Pinecone + Ollama)")
    parser.add_argument("--query", type=str, help="Single question (non-interactive)")
    parser.add_argument("--model", type=str, default=MODEL,
                        help=f"Ollama model to use (default: {MODEL})")
    args = parser.parse_args()

    # Check Ollama is running
    try:
        ollama.list()
    except Exception:
        print("ERROR: Ollama is not running. Start it with:\n  ollama serve")
        raise SystemExit(1)

    print("Loading vector index...", end=" ", flush=True)
    try:
        index = load_index()
        embed_model = load_embed_model()
        stats = index.describe_index_stats()
        print(f"OK ({stats.get('total_vector_count', '?')} vectors)")
    except Exception as e:
        print(f"\nERROR: Could not connect to Pinecone — check PINECONE_API_KEY\n{e}")
        raise SystemExit(1)

    if args.query:
        answer, _ = ask(index, embed_model, args.query, [], args.model)
        print(f"\nAnswer:\n{answer}")
    else:
        interactive(index, embed_model, args.model)


if __name__ == "__main__":
    main()
