"""
Phase 1: chunking strategy comparison (fixed-window vs semantic).

For each test document, indexes it into Pinecone twice -- once with each
chunking strategy, under distinct doc_ids so neither run touches the other
or the existing production-style "doc1"/"openai" vectors from
ingest_test_docs.py -- then runs the same retrieval hit-rate eval used in
eval_retrieval.py against both, and logs the result via log_experiment.py.

Cleans up its own temporary vectors from Pinecone when done.
"""
import sys
import os
import json
import re
import time
import boto3

from pathlib import Path
env_file = Path(__file__).parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "worker"))
import rag as rag_module


def _local_get_pinecone_credentials():
    return {
        "pineconeApiKey": os.environ["PINECONE_API_KEY"],
        "index_host": os.environ["PINECONE_INDEX_HOST"],
    }


rag_module._get_pinecone_credentials = _local_get_pinecone_credentials

from pinecone import Pinecone
from rag import index_document, chunk_text, get_embeddings
from log_experiment import log_result

bedrock_embed = boto3.client("bedrock-runtime", region_name="ap-south-1")
bedrock_judge = boto3.client("bedrock-runtime", region_name="us-east-1")

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(host=os.environ["PINECONE_INDEX_HOST"])

TEST_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "test_docs")


# Semantic chunking is only ever used by this comparison eval, so it lives
# here rather than in worker/rag.py -- that file is the production AI
# worker's deployed Lambda source, and worker.py never requests this
# strategy (it always uses rag.chunk_text). Keeping eval-only experiments
# out of the deployed package keeps "what does the worker actually do"
# unambiguous.
def _split_sentence_groups(text: str, group_size: int = 3) -> list[str]:
    """
    Splits text into sentences, then groups every `group_size` sentences
    together. Grouping keeps the number of embedding calls in
    chunk_text_semantic manageable on long documents (embedding every single
    sentence individually would be one Titan call per sentence).
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    groups = []
    for i in range(0, len(sentences), group_size):
        groups.append(" ".join(sentences[i:i + group_size]))
    return groups


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def chunk_text_semantic(text: str, max_chunk_size: int = 2500,
                         similarity_percentile: float = 25.0) -> list[str]:
    """
    Semantic chunking: groups of ~3 sentences are embedded, and a chunk
    boundary is placed wherever the similarity between consecutive sentence
    groups drops into the bottom `similarity_percentile` of all consecutive
    similarities in the document -- i.e. wherever the topic actually shifts,
    rather than at a fixed character count. `max_chunk_size` is a hard cap
    so a long run of highly-similar sentences still gets split eventually.
    """
    groups = _split_sentence_groups(text)
    if len(groups) <= 1:
        return [text.strip()] if text.strip() else []

    embeddings = get_embeddings(groups)

    similarities = [
        _cosine_similarity(embeddings[i], embeddings[i + 1])
        for i in range(len(embeddings) - 1)
    ]

    sorted_sims = sorted(similarities)
    cutoff_index = max(0, int(len(sorted_sims) * similarity_percentile / 100) - 1)
    threshold = sorted_sims[cutoff_index] if sorted_sims else 0.0

    chunks = []
    current = groups[0]
    for i in range(1, len(groups)):
        is_breakpoint = similarities[i - 1] <= threshold
        would_exceed_cap = len(current) + len(groups[i]) > max_chunk_size

        if is_breakpoint or would_exceed_cap:
            chunks.append(current.strip())
            current = groups[i]
        else:
            current += " " + groups[i]

    if current.strip():
        chunks.append(current.strip())

    return chunks


def embed_query(text: str) -> list[float]:
    body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    response = bedrock_embed.invoke_model(
        modelId="amazon.titan-embed-text-v2:0", body=body,
        accept="application/json", contentType="application/json"
    )
    return json.loads(response["body"].read())["embedding"]


def retrieve_chunks(question: str, doc_id: str, top_k: int = 5) -> list[str]:
    query_vector = embed_query(question)
    results = index.query(
        vector=query_vector, top_k=top_k,
        filter={"agreement_id": {"$eq": doc_id}}, include_metadata=True
    )
    return [match["metadata"]["text"] for match in results["matches"]]


def llm_judge(question: str, expected_answer: str, retrieved_chunks: list[str]) -> dict:
    context = "\n\n---\n\n".join(retrieved_chunks)

    if "Unanswerable" in expected_answer:
        judge_prompt = f"""You are a strict RAG evaluation judge. Your job is to determine if the retrieved context is CORRECTLY SILENT on a question that has no answer in the document.

QUESTION: {question}

EXPECTED BEHAVIOR: The answer to this question is NOT present in the document. A good retrieval system should return context that clearly does NOT contain a definitive answer.

RETRIEVED CONTEXT:
{context}

TASK: Does the retrieved context CORRECTLY lack a definitive answer to the question?
- PASS: The context does not contain a clear, direct answer (system correctly identified no answer exists)
- FAIL: The context contains a direct answer (the question was actually answerable after all)

Respond with ONLY valid JSON in this exact format:
{{"verdict": "PASS", "reason": "Brief explanation"}}"""
    else:
        judge_prompt = f"""You are a strict RAG evaluation judge. Your job is to determine if the retrieved context contains enough information to answer the question.

QUESTION: {question}

EXPECTED ANSWER (core concept to look for): {expected_answer}

RETRIEVED CONTEXT:
{context}

TASK: Does the retrieved context contain information that directly supports the expected answer?
- PASS: The context clearly contains the key facts from the expected answer
- FAIL: The context does NOT contain the key facts needed to answer this question

Be strict. Partial matches are FAIL. Respond with ONLY valid JSON:
{{"verdict": "PASS", "reason": "Brief explanation"}}"""

    response = bedrock_judge.converse(
        modelId="amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": judge_prompt}]}],
        inferenceConfig={"maxTokens": 512, "temperature": 0.0}
    )
    raw = response["output"]["message"]["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def run_hit_rate_eval(qa_path: str, doc_id: str) -> float:
    with open(qa_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    passed = 0
    for item in dataset:
        chunks = retrieve_chunks(item["question"], doc_id, top_k=5)
        verdict = llm_judge(item["question"], item["expected_answer"], chunks)
        if verdict.get("verdict") == "PASS":
            passed += 1

    return round(passed / len(dataset) * 100, 1)


def run():
    documents = [
        ("doc1", "doc1.txt", "test_qa_doc1.json"),
        ("openai", "openai.txt", "test_qa_openai.json"),
        ("nda1", "nda_1.txt", "test_qa_nda_1.json"),
        ("service1", "service_1.txt", "test_qa_service_1.json"),
        ("unstructured", "edge_case_unstructured_article.txt", "test_qa_unstructured_article.json"),
    ]
    strategies = ["fixed", "semantic"]
    temp_doc_ids = []

    for name, filename, qa_filename in documents:
        with open(os.path.join(TEST_DOCS_DIR, filename), "r", encoding="utf-8") as f:
            text = f.read()

        for strategy in strategies:
            doc_id = f"{name}_chunkcmp_{strategy}"
            temp_doc_ids.append(doc_id)

            chunks = chunk_text_semantic(text) if strategy == "semantic" else chunk_text(text)
            avg_chunk_size = round(sum(len(c) for c in chunks) / len(chunks)) if chunks else 0

            print(f"\nIndexing {name} ({strategy}): {len(chunks)} chunks, avg {avg_chunk_size} chars")
            chunk_fn = chunk_text_semantic if strategy == "semantic" else chunk_text
            index_document(doc_id, text, chunk_fn=chunk_fn)

            # Pinecone upserts are near-real-time but not always instantly queryable
            time.sleep(3)

            qa_path = os.path.join(os.path.dirname(__file__), qa_filename)
            hit_rate = run_hit_rate_eval(qa_path, doc_id)

            print(f"{name} / {strategy}: hit rate {hit_rate}%")
            log_result(
                "phase_1_chunking_comparison", strategy, "retrieval_hit_rate_pct", hit_rate,
                notes=f"doc={name}, {len(chunks)} chunks, avg_chunk_size={avg_chunk_size} chars"
            )

    print("\nCleaning up temporary Pinecone vectors...")
    for doc_id in temp_doc_ids:
        index.delete(filter={"agreement_id": {"$eq": doc_id}})
    print("Done.")


if __name__ == "__main__":
    run()
