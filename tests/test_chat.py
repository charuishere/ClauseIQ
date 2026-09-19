"""
Tests for api/routers/chat.py: completion gating, ownership, the RAG vs
direct-S3 retrieval branch, malformed-AI-output fallback, and the real
DynamoDB conditional-write rate limiter (not mocked -- moto enforces the
actual ConditionExpression semantics, so this test would fail if that
logic broke).
"""
import json

import pytest


def _bedrock_response(payload: dict) -> dict:
    return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}


def _seed_chat_message(dynamo_table, agreement_id, epoch_ms, question, answer):
    dynamo_table.put_item(Item={
        "PK": f"AGREEMENT#{agreement_id}",
        "SK": f"CHAT#{epoch_ms}",
        "messageId": f"chat-{epoch_ms}",
        "question": question,
        "answer": answer,
        "answer_type": "document",
        "citations": [],
        "found_in_document": True,
    })


def _text_over_n_tokens(n: int) -> str:
    """Repeats a sentence until it reliably exceeds `n` tokens, measured
    with the actual tokenizer chat.py uses -- avoids guessing at a
    chars-per-token ratio that could make a test flaky."""
    from utils.tokens import count_tokens
    sentence = "This is a long previous answer about termination clauses and payment terms. "
    text = sentence
    while count_tokens(text) < n:
        text += sentence
    return text


@pytest.fixture
def mock_bedrock_converse(monkeypatch):
    """
    Patches the module-level `bedrock` client in api/routers/chat.py.
    Returns a small controller object so tests can set what the "model"
    replies with, and assert on what it was called with.
    """
    import routers.chat as chat_module

    calls = []

    class _Controller:
        response_payload = {
            "answer": "The termination notice period is 30 days.",
            "answer_type": "document",
            "citations": [{"section_name": "12.1 Termination", "page_number": 3}],
            "found_in_document": True,
        }
        raw_text_override = None  # when set, bypasses response_payload entirely

    controller = _Controller()

    def _fake_converse(**kwargs):
        calls.append(kwargs)
        text = controller.raw_text_override
        if text is None:
            text = json.dumps(controller.response_payload)
        return {"output": {"message": {"content": [{"text": text}]}}}

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)
    controller.calls = calls
    return controller


# ---------------------------------------------------------------------------
# Gating: must be COMPLETED, must belong to caller
# ---------------------------------------------------------------------------

def test_chat_rejected_before_analysis_complete(client, auth_headers, seed_agreement, mock_bedrock_converse):
    seed_agreement("test-user-id", "agmt-pending", completed=False)
    resp = client.post(
        "/agreements/agmt-pending/chat", json={"question": "What is the term?"}, headers=auth_headers
    )
    assert resp.status_code == 409


def test_chat_404_for_nonexistent_agreement(client, auth_headers, dynamo_table, mock_bedrock_converse):
    resp = client.post(
        "/agreements/agmt-does-not-exist/chat", json={"question": "hi"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_chat_404_for_another_users_agreement(client, make_token, seed_agreement, mock_bedrock_converse):
    seed_agreement("owner-user", "agmt-private", text="Confidential terms.", completed=True, ai_data={})
    attacker_token = make_token(sub="attacker-user")
    resp = client.post(
        "/agreements/agmt-private/chat",
        json={"question": "What are the terms?"},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Direct-S3 path (small, non-RAG document)
# ---------------------------------------------------------------------------

def test_chat_direct_path_returns_citations_and_persists_history(
    client, auth_headers, seed_agreement, mock_bedrock_converse, dynamo_table
):
    seed_agreement(
        "test-user-id", "agmt-small", text="Section 12.1: 30 days notice required to terminate.",
        completed=True, ai_data={}
    )

    resp = client.post(
        "/agreements/agmt-small/chat",
        json={"question": "How much notice is required to terminate?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "The termination notice period is 30 days."
    assert body["found_in_document"] is True
    assert body["citations"] == [{"section_name": "12.1 Termination", "page_number": 3}]

    # The document text actually sent to the model came from S3, not Pinecone.
    sent_system_prompt = mock_bedrock_converse.calls[0]["system"][0]["text"]
    assert "30 days notice required to terminate" in sent_system_prompt

    # Persisted to chat history for real -- verified via the GET endpoint.
    history = client.get("/agreements/agmt-small/chat", headers=auth_headers)
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["question"] == "How much notice is required to terminate?"


# ---------------------------------------------------------------------------
# RAG path: large / has_rag documents query Pinecone instead of S3
# ---------------------------------------------------------------------------

def test_chat_rag_path_uses_pinecone_chunks_not_full_document(
    client, auth_headers, seed_agreement, mock_bedrock_converse, monkeypatch
):
    seed_agreement(
        "test-user-id", "agmt-large", text="irrelevant full text that should NOT be sent",
        completed=True, ai_data={}
    )
    # Flip on the RAG flag the way worker.py's set_rag_flag() does.
    import dynamo as worker_dynamo

    worker_dynamo.set_rag_flag("agmt-large", "test-user-id")

    import routers.chat as chat_module

    captured_args = {}

    def _fake_query_pinecone(agreement_id, query_text, top_k=5):
        captured_args["agreement_id"] = agreement_id
        captured_args["query_text"] = query_text
        return ["Relevant chunk: Section 5.2 caps liability at $10,000."]

    monkeypatch.setattr(chat_module, "query_pinecone", _fake_query_pinecone)

    resp = client.post(
        "/agreements/agmt-large/chat", json={"question": "What is the liability cap?"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert captured_args["agreement_id"] == "agmt-large"
    assert captured_args["query_text"] == "What is the liability cap?"

    sent_system_prompt = mock_bedrock_converse.calls[0]["system"][0]["text"]
    assert "Section 5.2 caps liability at $10,000" in sent_system_prompt
    assert "irrelevant full text that should NOT be sent" not in sent_system_prompt


def test_chat_rag_path_rewrites_followup_question_before_retrieval(
    client, auth_headers, seed_agreement, dynamo_table, monkeypatch
):
    """
    A short follow-up like "what about for cause?" carries little meaning
    on its own for a vector search. chat.py should rewrite it into a
    standalone question (using recent history) before calling
    query_pinecone -- but still answer, save, and return the user's
    original question untouched.
    """
    seed_agreement("test-user-id", "agmt-followup", completed=True, ai_data={})
    import dynamo as worker_dynamo

    worker_dynamo.set_rag_flag("agmt-followup", "test-user-id")

    # A prior exchange, written the way chat.py itself persists messages.
    dynamo_table.put_item(Item={
        "PK": "AGREEMENT#agmt-followup",
        "SK": "CHAT#1",
        "messageId": "chat-1",
        "question": "What is the termination clause?",
        "answer": "Either party may terminate with 30 days notice.",
        "answer_type": "document",
        "citations": [],
        "found_in_document": True,
    })

    import routers.chat as chat_module

    captured = {}
    monkeypatch.setattr(
        chat_module, "query_pinecone",
        lambda agreement_id, query_text, top_k=5: captured.setdefault("search_query", query_text) or [
            "Termination for cause requires 24 hours written notice."
        ],
    )

    def _fake_converse(**kwargs):
        if "system" not in kwargs:
            # The query-rewrite call has no system prompt -- just the rewrite instruction.
            return {"output": {"message": {"content": [{"text": "What is the termination for cause clause?"}]}}}
        payload = {
            "answer": "Termination for cause requires 24 hours written notice.",
            "answer_type": "document",
            "citations": [],
            "found_in_document": True,
        }
        return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)

    resp = client.post(
        "/agreements/agmt-followup/chat", json={"question": "What about for cause?"}, headers=auth_headers
    )
    assert resp.status_code == 200
    # Retrieval used the rewritten, standalone question...
    assert captured["search_query"] == "What is the termination for cause clause?"
    # ...but the user's original question is still what gets answered and saved.
    assert resp.json()["question"] == "What about for cause?"


# ---------------------------------------------------------------------------
# Conversation compaction: a rolling summary once history exceeds the token
# budget, instead of a flat "last N messages" cutoff that abruptly forgets
# everything older mid-conversation.
# ---------------------------------------------------------------------------

def test_chat_short_history_never_triggers_compaction(
    client, auth_headers, seed_agreement, dynamo_table, mock_bedrock_converse
):
    seed_agreement("test-user-id", "agmt-shortchat", completed=True, ai_data={})
    _seed_chat_message(dynamo_table, "agmt-shortchat", 1000, "Hi", "Hello!")

    resp = client.post(
        "/agreements/agmt-shortchat/chat", json={"question": "Another question"}, headers=auth_headers
    )
    assert resp.status_code == 200
    # Only one Bedrock call (the real answer) -- no compaction call, since
    # this tiny history is nowhere near HISTORY_TOKEN_BUDGET.
    assert len(mock_bedrock_converse.calls) == 1
    assert dynamo_table.get_item(
        Key={"PK": "AGREEMENT#agmt-shortchat", "SK": "#CHAT_SUMMARY"}
    ).get("Item") is None


def test_chat_compacts_old_history_once_token_budget_exceeded(
    client, auth_headers, seed_agreement, dynamo_table, monkeypatch
):
    seed_agreement("test-user-id", "agmt-longchat", completed=True, ai_data={})

    long_answer = _text_over_n_tokens(900)  # 5 of these comfortably exceeds the 3000-token budget
    for i in range(5):
        _seed_chat_message(dynamo_table, "agmt-longchat", 1000 + i, f"Question {i}?", long_answer)

    import routers.chat as chat_module

    captured = {"summarize_prompt": None, "final_system_prompt": None}

    def _fake_converse(**kwargs):
        if "system" not in kwargs:
            # No system prompt -- this is the compaction/summarization call.
            captured["summarize_prompt"] = kwargs["messages"][0]["content"][0]["text"]
            return {"output": {"message": {"content": [{"text": "Prior discussion covered termination clauses."}]}}}
        captured["final_system_prompt"] = kwargs["system"][0]["text"]
        payload = {"answer": "Final answer.", "answer_type": "document", "citations": [], "found_in_document": True}
        return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)

    resp = client.post(
        "/agreements/agmt-longchat/chat", json={"question": "One more question"}, headers=auth_headers
    )
    assert resp.status_code == 200
    # A summarization call actually happened...
    assert captured["summarize_prompt"] is not None
    # ...and its result made it into the final answer's system prompt.
    assert "Prior discussion covered termination clauses." in captured["final_system_prompt"]

    # The rolling summary was persisted for next time.
    summary_item = dynamo_table.get_item(
        Key={"PK": "AGREEMENT#agmt-longchat", "SK": "#CHAT_SUMMARY"}
    ).get("Item")
    assert summary_item is not None
    assert summary_item["summary"] == "Prior discussion covered termination clauses."
    assert summary_item["summarized_through"] >= 1000


def test_chat_compaction_only_folds_in_messages_after_existing_watermark(
    client, auth_headers, seed_agreement, dynamo_table, monkeypatch
):
    """Once a summary exists, a later compaction pass must only fold in
    messages newer than the stored watermark -- not the whole history again,
    which is the whole point of incremental (vs. from-scratch) compaction."""
    seed_agreement("test-user-id", "agmt-incremental", completed=True, ai_data={})

    # Only messages 1002-1004 are "unsummarized" (after the watermark below),
    # so those 3 alone need to comfortably exceed the 3000-token budget.
    long_answer = _text_over_n_tokens(1300)
    for i in range(5):
        _seed_chat_message(dynamo_table, "agmt-incremental", 1000 + i, f"Old question {i}?", long_answer)

    # Pretend messages 1000 and 1001 were already folded into an existing summary.
    dynamo_table.put_item(Item={
        "PK": "AGREEMENT#agmt-incremental",
        "SK": "#CHAT_SUMMARY",
        "summary": "Earlier summary covering the first two questions.",
        "summarized_through": 1001,
    })

    import routers.chat as chat_module

    captured = {"summarize_prompt": None}

    def _fake_converse(**kwargs):
        if "system" not in kwargs:
            captured["summarize_prompt"] = kwargs["messages"][0]["content"][0]["text"]
            return {"output": {"message": {"content": [{"text": "Updated summary."}]}}}
        payload = {"answer": "Final answer.", "answer_type": "document", "citations": [], "found_in_document": True}
        return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)

    resp = client.post(
        "/agreements/agmt-incremental/chat", json={"question": "New question"}, headers=auth_headers
    )
    assert resp.status_code == 200
    # The existing summary was carried forward to be merged, not discarded...
    assert "Earlier summary covering the first two questions." in captured["summarize_prompt"]
    # ...and messages already folded in before (0, 1) never reappear.
    assert "Old question 0?" not in captured["summarize_prompt"]
    assert "Old question 1?" not in captured["summarize_prompt"]
    # Only messages after the watermark (2, and whichever of 3/4 also aged
    # out under the token budget) were newly folded in.
    assert "Old question 2?" in captured["summarize_prompt"]


def test_chat_rag_path_skips_rewrite_on_first_message(
    client, auth_headers, seed_agreement, mock_bedrock_converse, monkeypatch
):
    """No prior history means nothing to rewrite from -- skip the extra
    Bedrock call entirely rather than spending it on a no-op."""
    seed_agreement("test-user-id", "agmt-first", completed=True, ai_data={})
    import dynamo as worker_dynamo

    worker_dynamo.set_rag_flag("agmt-first", "test-user-id")

    import routers.chat as chat_module

    monkeypatch.setattr(chat_module, "query_pinecone", lambda *a, **k: ["Some relevant chunk."])

    resp = client.post(
        "/agreements/agmt-first/chat", json={"question": "What is the notice period?"}, headers=auth_headers
    )
    assert resp.status_code == 200
    # Exactly one Bedrock call (the real answer) -- no rewrite call was made.
    assert len(mock_bedrock_converse.calls) == 1


def test_chat_rag_path_with_zero_pinecone_matches(
    client, auth_headers, seed_agreement, mock_bedrock_converse, monkeypatch
):
    seed_agreement("test-user-id", "agmt-empty-rag", completed=True, ai_data={})
    import dynamo as worker_dynamo

    worker_dynamo.set_rag_flag("agmt-empty-rag", "test-user-id")

    import routers.chat as chat_module

    monkeypatch.setattr(chat_module, "query_pinecone", lambda *a, **k: [])

    resp = client.post(
        "/agreements/agmt-empty-rag/chat", json={"question": "anything?"}, headers=auth_headers
    )
    assert resp.status_code == 200  # degrades gracefully, doesn't 500
    sent_system_prompt = mock_bedrock_converse.calls[0]["system"][0]["text"]
    assert "No relevant context found in the document." in sent_system_prompt


# ---------------------------------------------------------------------------
# Malformed model output
# ---------------------------------------------------------------------------

def test_chat_falls_back_to_plain_text_on_invalid_json(
    client, auth_headers, seed_agreement, mock_bedrock_converse
):
    seed_agreement("test-user-id", "agmt-malformed", completed=True, ai_data={})
    mock_bedrock_converse.raw_text_override = "Sorry, I can't format that as JSON right now."

    resp = client.post(
        "/agreements/agmt-malformed/chat", json={"question": "hi"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Sorry, I can't format that as JSON right now."
    assert body["answer_type"] == "general"
    assert body["citations"] == []
    assert body["found_in_document"] is False


# ---------------------------------------------------------------------------
# Rate limiting: real DynamoDB conditional-write semantics via moto, not mocked
# ---------------------------------------------------------------------------

def test_second_message_within_30_seconds_is_rate_limited(
    client, auth_headers, seed_agreement, mock_bedrock_converse
):
    seed_agreement("test-user-id", "agmt-ratelimit", completed=True, ai_data={})

    first = client.post(
        "/agreements/agmt-ratelimit/chat", json={"question": "First question"}, headers=auth_headers
    )
    assert first.status_code == 200

    second = client.post(
        "/agreements/agmt-ratelimit/chat", json={"question": "Second question, too soon"}, headers=auth_headers
    )
    assert second.status_code == 429


# ---------------------------------------------------------------------------
# Question validation
# ---------------------------------------------------------------------------

def test_chat_rejects_empty_question(client, auth_headers, seed_agreement, mock_bedrock_converse):
    seed_agreement("test-user-id", "agmt-validate", completed=True, ai_data={})
    resp = client.post("/agreements/agmt-validate/chat", json={"question": ""}, headers=auth_headers)
    assert resp.status_code == 422
    assert mock_bedrock_converse.calls == []  # rejected before ever reaching Bedrock


def test_chat_rejects_overlong_question(client, auth_headers, seed_agreement, mock_bedrock_converse):
    seed_agreement("test-user-id", "agmt-validate2", completed=True, ai_data={})
    resp = client.post(
        "/agreements/agmt-validate2/chat", json={"question": "x" * 4001}, headers=auth_headers
    )
    assert resp.status_code == 422
    assert mock_bedrock_converse.calls == []


# ---------------------------------------------------------------------------
# Bedrock error handling: transient errors retry once, others don't, and a
# content-filtered (empty) response gets its own message instead of a
# generic 500 -- previously one bare `except Exception` covered all three.
# ---------------------------------------------------------------------------

def test_chat_retries_once_on_throttling_then_succeeds(
    client, auth_headers, seed_agreement, monkeypatch
):
    from botocore.exceptions import ClientError
    import routers.chat as chat_module

    seed_agreement("test-user-id", "agmt-throttle", completed=True, ai_data={})

    call_count = {"n": 0}

    def _fake_converse(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ClientError({"Error": {"Code": "ThrottlingException", "Message": "Too many requests"}}, "Converse")
        payload = {"answer": "Recovered answer.", "answer_type": "document", "citations": [], "found_in_document": True}
        return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)

    resp = client.post("/agreements/agmt-throttle/chat", json={"question": "Will this retry?"}, headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["answer"] == "Recovered answer."
    assert call_count["n"] == 2  # failed once, retried once, succeeded


def test_chat_does_not_retry_non_transient_bedrock_error(
    client, auth_headers, seed_agreement, monkeypatch
):
    from botocore.exceptions import ClientError
    import routers.chat as chat_module

    seed_agreement("test-user-id", "agmt-denied", completed=True, ai_data={})

    call_count = {"n": 0}

    def _fake_converse(**kwargs):
        call_count["n"] += 1
        raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}}, "Converse")

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)

    resp = client.post("/agreements/agmt-denied/chat", json={"question": "Any question"}, headers=auth_headers)

    assert resp.status_code == 500
    assert call_count["n"] == 1  # no retry for a non-transient error


def test_chat_handles_content_filtered_response_gracefully(
    client, auth_headers, seed_agreement, monkeypatch
):
    """Bedrock returns an empty/absent message content list when a response
    is content-filtered -- this used to raise an unhandled IndexError caught
    only by the generic except-all."""
    import routers.chat as chat_module

    seed_agreement("test-user-id", "agmt-filtered", completed=True, ai_data={})

    monkeypatch.setattr(
        chat_module.bedrock, "converse",
        lambda **kwargs: {"output": {"message": {"content": []}}}
    )

    resp = client.post("/agreements/agmt-filtered/chat", json={"question": "Trigger a filter"}, headers=auth_headers)

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Token usage: previously discarded entirely; now persisted for a future
# cost view
# ---------------------------------------------------------------------------

def test_chat_persists_token_usage_from_bedrock_response(
    client, auth_headers, seed_agreement, dynamo_table, monkeypatch
):
    import routers.chat as chat_module

    seed_agreement("test-user-id", "agmt-usage", completed=True, ai_data={})

    def _fake_converse(**kwargs):
        payload = {"answer": "An answer.", "answer_type": "document", "citations": [], "found_in_document": True}
        return {
            "output": {"message": {"content": [{"text": json.dumps(payload)}]}},
            "usage": {"inputTokens": 123, "outputTokens": 45}
        }

    monkeypatch.setattr(chat_module.bedrock, "converse", _fake_converse)

    resp = client.post("/agreements/agmt-usage/chat", json={"question": "Track my usage"}, headers=auth_headers)
    assert resp.status_code == 200

    message_id = resp.json()["messageId"]
    epoch_ms = message_id.replace("chat-", "")
    stored = dynamo_table.get_item(
        Key={"PK": "AGREEMENT#agmt-usage", "SK": f"CHAT#{epoch_ms}"}
    )["Item"]
    assert stored["input_tokens"] == 123
    assert stored["output_tokens"] == 45
