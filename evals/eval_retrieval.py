"""
eval_retrieval.py
-----------------
Measures the Retrieval Hit Rate of our Pinecone RAG system.

For each question in the dataset:
  1. Embed the question using Amazon Titan v2 (same model used during ingestion)
  2. Query Pinecone for the top-5 most relevant chunks (filtered by document)
  3. Use Nova Lite as an 'LLM-as-a-Judge' to grade if the chunks contain the expected answer
  4. Print a pass/fail result per question and a final hit-rate score
"""

import sys
import os
import json
import boto3

# ─── Load local credentials from .env.local ───────────────────────────────────
from pathlib import Path
env_file = Path(__file__).parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ[key.strip()] = val.strip()

from pinecone import Pinecone

# ─── AWS clients ──────────────────────────────────────────────────────────────
# Titan v2 (for embeddings) is in ap-south-1; Nova Lite (judge) is in us-east-1
bedrock_embed = boto3.client("bedrock-runtime", region_name="ap-south-1")
bedrock_judge = boto3.client("bedrock-runtime", region_name="us-east-1")

# ─── Pinecone client ──────────────────────────────────────────────────────────
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(host=os.environ["PINECONE_INDEX_HOST"])


def embed_query(text: str) -> list[float]:
    """Embed a single query string using Amazon Titan v2."""
    body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    response = bedrock_embed.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body,
        accept="application/json",
        contentType="application/json"
    )
    return json.loads(response["body"].read())["embedding"]


def retrieve_chunks(question: str, doc_id: str, top_k: int = 5) -> list[str]:
    """
    Embed the question and query Pinecone.
    Filter results to only chunks from the specified document.
    Returns a list of the top-k retrieved text chunks.
    """
    query_vector = embed_query(question)
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        filter={"agreement_id": {"$eq": doc_id}},
        include_metadata=True
    )
    return [match["metadata"]["text"] for match in results["matches"]]


def llm_judge(question: str, expected_answer: str, retrieved_chunks: list[str]) -> dict:
    """
    Use Nova Lite as an impartial judge.
    Ask it whether the retrieved context contains enough information
    to answer the question correctly, given the expected answer.
    
    Returns a dict: { "verdict": "PASS" | "FAIL", "reason": "..." }
    """
    context = "\n\n---\n\n".join(retrieved_chunks)

    # For unanswerable questions, the expected answer contains "Unanswerable"
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

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def run_eval(dataset_path: str, doc_id: str):
    """Run the full evaluation for one dataset file."""
    print(f"\n{'='*60}")
    print(f"  EVALUATING: {os.path.basename(dataset_path)}")
    print(f"  Document  : {doc_id}")
    print(f"{'='*60}\n")

    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    total = len(dataset)
    passed = 0
    results = []

    for i, item in enumerate(dataset, 1):
        question = item["question"]
        expected = item["expected_answer"]

        print(f"[{i:02d}/{total}] Q: {question}")

        # Step 1: Retrieve top-5 chunks from Pinecone
        chunks = retrieve_chunks(question, doc_id, top_k=5)

        # Step 2: Ask Nova Lite to judge the result
        verdict = llm_judge(question, expected, chunks)

        status = verdict.get("verdict", "FAIL")
        reason = verdict.get("reason", "No reason provided")

        if status == "PASS":
            passed += 1
            print(f"         [PASS] {reason}\n")
        else:
            print(f"         [FAIL] {reason}")
            print(f"         Expected: {expected}\n")

        results.append({
            "question": question,
            "expected_answer": expected,
            "verdict": status,
            "reason": reason
        })

    hit_rate = (passed / total) * 100
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{total} passed")
    print(f"  HIT RATE: {hit_rate:.1f}%")
    print(f"{'='*60}\n")

    # Save detailed results to a JSON file
    out_path = dataset_path.replace(".json", "_results.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            "doc_id": doc_id,
            "hit_rate_pct": round(hit_rate, 1),
            "passed": passed,
            "total": total,
            "details": results
        }, f, indent=2)
    print(f"  Detailed results saved to: {out_path}\n")
    return hit_rate


if __name__ == "__main__":
    evals_dir = os.path.dirname(__file__)

    # Run evaluation for both documents
    doc1_rate  = run_eval(os.path.join(evals_dir, "test_qa_doc1.json"),   "doc1")
    openai_rate = run_eval(os.path.join(evals_dir, "test_qa_openai.json"), "openai")

    print("\n" + "="*60)
    print("  OVERALL SUMMARY")
    print("="*60)
    print(f"  doc1 (Employment Agreement) : {doc1_rate:.1f}%")
    print(f"  openai (Terms of Service)   : {openai_rate:.1f}%")
    print(f"  Average Hit Rate            : {(doc1_rate + openai_rate) / 2:.1f}%")
    print("="*60)
