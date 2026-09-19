import sys
import os
import json
import logging
import boto3

# ─── Load local credentials from .env.local (bypasses AWS Secrets Manager) ───
from pathlib import Path
env_file = Path(__file__).parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()

# ─── Patch rag.py's credential fetcher to use local env vars ─────────────────
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'worker'))

# We monkey-patch the credentials function BEFORE importing rag
import rag as rag_module

def _local_get_pinecone_credentials():
    return {
        "pineconeApiKey": os.environ["PINECONE_API_KEY"],
        "index_host": os.environ["PINECONE_INDEX_HOST"]
    }

rag_module._get_pinecone_credentials = _local_get_pinecone_credentials

from rag import index_document

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def ingest_tests():
    base = os.path.join(os.path.dirname(__file__), '..')

    docs = [
        ("doc1",   os.path.join(base, "test_docs", "doc1.txt")),
        ("openai", os.path.join(base, "test_docs", "openai.txt")),
    ]

    for doc_id, path in docs:
        path = os.path.normpath(path)
        print(f"\n[READING] {path}")
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        print(f"   -> {len(text)} characters")
        print(f"   Indexing '{doc_id}' into Pinecone...")
        index_document(doc_id, text)
        print(f"   [DONE] '{doc_id}' indexed successfully!")

    print("\n[SUCCESS] All documents ingested into Pinecone!")

if __name__ == "__main__":
    ingest_tests()
