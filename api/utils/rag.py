import os
import json
import boto3
from pinecone import Pinecone

bedrock_runtime = boto3.client("bedrock-runtime")
secrets_client = boto3.client("secretsmanager")

# Must match worker/rag.py's EMBEDDING_MODEL_ID -- a query embedded with a
# different model than the one that indexed the chunks would still return a
# Pinecone similarity score, just a meaningless one.
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"

# Cohere Rerank 3.5 is available in us-east-1 -- the same region already used
# for Nova Lite (BEDROCK_REGION) -- so reranking needs no new region and no
# new vendor, just a different Bedrock client (bedrock-agent-runtime).
_RERANK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=_RERANK_REGION)
_RERANK_MODEL_ARN = f"arn:aws:bedrock:{_RERANK_REGION}::foundation-model/cohere.rerank-v3-5:0"

# Cached across warm invocations -- this is called on every RAG chat query,
# and re-fetching the secret plus rebuilding the Pinecone client on every
# request would add a needless Secrets Manager call and network round trip
# to the hot path.
_pinecone_index = None

def _get_pinecone_credentials() -> dict:
    # Use the same secret the worker uses
    response = secrets_client.get_secret_value(SecretId=os.environ["PINECONE_SECRET_ARN"])
    return json.loads(response["SecretString"])

def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        creds = _get_pinecone_credentials()
        pc = Pinecone(api_key=creds["pineconeApiKey"])
        host = creds["index_host"]
        if host.startswith("https://"):
            host = host[8:]
        _pinecone_index = pc.Index(host=host)
    return _pinecone_index

def query_pinecone(agreement_id: str, query_text: str, top_k: int = 5, min_score: float = 0.4,
                    candidate_pool: int = 20) -> list[str]:
    """Embed the query, pull a wider pool of Pinecone candidates, then
    rerank them with Bedrock's Cohere Rerank 3.5 before returning the final
    top_k.

    Cosine similarity between independently-computed embeddings is only an
    approximation of relevance; a reranker looks at the query and each
    candidate together for a more precise judgment. `min_score` is applied
    to the reranked scores (or, if the rerank call itself fails, to the
    original cosine scores as a fallback) so a genuinely irrelevant question
    still returns nothing rather than "whatever was closest". 0.4 is a
    conservative starting point, not a tuned value.
    """
    # 1. Embed query using Titan v2
    body = json.dumps({
        "inputText": query_text,
        "dimensions": 1024,
        "normalize": True
    })
    try:
        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            body=body,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response["body"].read())
        query_embedding = response_body["embedding"]
    except Exception as e:
        print(f"Embedding error: {e}")
        return []

    # 2. Query Pinecone for a wider candidate pool than we'll actually use
    index = _get_pinecone_index()
    results = index.query(
        vector=query_embedding,
        top_k=candidate_pool,
        include_metadata=True,
        filter={"agreement_id": {"$eq": agreement_id}}
    )
    candidates = [
        {"text": match["metadata"]["text"], "score": match.get("score", 0)}
        for match in results.get("matches", [])
        if "text" in match.get("metadata", {})
    ]
    if not candidates:
        return []

    # 3. Rerank for a more precise final ordering
    try:
        rerank_resp = bedrock_agent_runtime.rerank(
            queries=[{"type": "TEXT", "textQuery": {"text": query_text}}],
            sources=[
                {"type": "INLINE", "inlineDocumentSource": {"type": "TEXT", "textDocument": {"text": c["text"]}}}
                for c in candidates
            ],
            rerankingConfiguration={
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "modelConfiguration": {"modelArn": _RERANK_MODEL_ARN},
                    "numberOfResults": top_k
                }
            }
        )
        return [
            candidates[r["index"]]["text"]
            for r in rerank_resp["results"]
            if r["relevanceScore"] >= min_score
        ]
    except Exception as e:
        print(f"Reranking failed, falling back to raw vector similarity order: {e}")
        ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)
        return [c["text"] for c in ranked[:top_k] if c["score"] >= min_score]

def delete_document(agreement_id: str):
    """Delete all vectors for an agreement from Pinecone.

    Vector IDs are deterministic (f"{agreement_id}-chunk-{i}", see
    worker/rag.py's index_document), so we can list them by ID prefix and
    delete by ID rather than relying on metadata-filter deletion, which
    Pinecone serverless indexes don't support.
    """
    try:
        index = _get_pinecone_index()
        prefix = f"{agreement_id}-chunk-"
        ids_to_delete = [id_ for batch in index.list(prefix=prefix) for id_ in batch]
        if ids_to_delete:
            index.delete(ids=ids_to_delete)
            print(f"Deleted {len(ids_to_delete)} Pinecone vectors for {agreement_id}.")
        else:
            print(f"No Pinecone vectors found for {agreement_id}.")
    except Exception as e:
        print(f"Error during pinecone deletion: {e}")
