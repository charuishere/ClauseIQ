"""
Tests for api/utils/rag.py's query_pinecone(): retrieves a wide candidate
pool from Pinecone, reranks it with Bedrock's Cohere Rerank 3.5, and applies
a relevance-score threshold -- falling back to raw cosine-similarity order
if the rerank call itself fails, so a Bedrock hiccup degrades gracefully
instead of breaking retrieval outright.

Bedrock and Pinecone are monkeypatched directly (moto doesn't model Bedrock
model invocation, the Rerank API, or Pinecone), matching the pattern already
used for mocking Bedrock calls in test_chat.py.
"""
import json


def _patch_embedding(monkeypatch, rag_module):
    """Bedrock's embedding call just needs to return *something* -- the
    actual vector values don't matter since Pinecone itself is faked below."""
    class _FakeBody:
        def read(self):
            return json.dumps({"embedding": [0.1] * 1024}).encode("utf-8")

    monkeypatch.setattr(
        rag_module.bedrock_runtime, "invoke_model", lambda **kwargs: {"body": _FakeBody()}
    )


def _patch_pinecone_matches(monkeypatch, rag_module, matches):
    class _FakeIndex:
        def query(self, **kwargs):
            return {"matches": matches}

    monkeypatch.setattr(rag_module, "_get_pinecone_index", lambda: _FakeIndex())


def _patch_rerank(monkeypatch, rag_module, results):
    """`results`: list of {"index": int, "relevanceScore": float} in the
    order Bedrock's Rerank API would return them (best first)."""
    monkeypatch.setattr(
        rag_module.bedrock_agent_runtime, "rerank", lambda **kwargs: {"results": results}
    )


def _import_rag_module():
    # api/utils/rag.py -- NOT worker/rag.py, which is also importable as the
    # bare name "rag" since both api/ and worker/ are on sys.path in tests.
    import utils.rag as rag_module
    return rag_module


def test_query_pinecone_uses_reranked_order_and_threshold(monkeypatch):
    rag_module = _import_rag_module()

    _patch_embedding(monkeypatch, rag_module)
    # Raw cosine similarity would rank index 0 first...
    _patch_pinecone_matches(monkeypatch, rag_module, [
        {"score": 0.5, "metadata": {"text": "Loosely related by embedding similarity."}},
        {"score": 0.45, "metadata": {"text": "Actually answers the question."}},
    ])
    # ...but the reranker (which looks at query + candidate together, not
    # just embedding distance) correctly flips that, and scores the other
    # candidate below the relevance threshold.
    _patch_rerank(monkeypatch, rag_module, [
        {"index": 1, "relevanceScore": 0.9},
        {"index": 0, "relevanceScore": 0.1},
    ])

    chunks = rag_module.query_pinecone("agmt-1", "What is the termination clause?", top_k=5, min_score=0.4)

    assert chunks == ["Actually answers the question."]


def test_query_pinecone_falls_back_to_cosine_order_if_rerank_fails(monkeypatch):
    rag_module = _import_rag_module()

    _patch_embedding(monkeypatch, rag_module)
    _patch_pinecone_matches(monkeypatch, rag_module, [
        {"score": 0.85, "metadata": {"text": "Clearly relevant chunk about termination."}},
        {"score": 0.12, "metadata": {"text": "Unrelated chunk about something else entirely."}},
    ])

    def _broken_rerank(**kwargs):
        raise RuntimeError("Bedrock Rerank unavailable")

    monkeypatch.setattr(rag_module.bedrock_agent_runtime, "rerank", _broken_rerank)

    chunks = rag_module.query_pinecone("agmt-1", "What is the termination clause?", top_k=5, min_score=0.4)

    # Degrades to the pre-rerank behavior: raw cosine order, still filtered
    # by min_score, rather than the whole chat request failing outright.
    assert chunks == ["Clearly relevant chunk about termination."]


def test_query_pinecone_returns_empty_when_nothing_meets_threshold(monkeypatch):
    rag_module = _import_rag_module()

    _patch_embedding(monkeypatch, rag_module)
    _patch_pinecone_matches(monkeypatch, rag_module, [
        {"score": 0.2, "metadata": {"text": "Loosely related at best."}},
    ])
    _patch_rerank(monkeypatch, rag_module, [
        {"index": 0, "relevanceScore": 0.2},
    ])

    chunks = rag_module.query_pinecone("agmt-1", "Something not in the document", min_score=0.4)

    assert chunks == []
