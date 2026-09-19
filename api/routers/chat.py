import os
import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth import get_current_user
from utils.dynamo import get_table, get_owned_agreement, get_chat_summary, save_chat_summary
from utils.qa_prompt import build_system_prompt, build_query_rewrite_prompt, build_summarization_prompt
from utils.rag import query_pinecone
from utils.tokens import count_tokens
from boto3.dynamodb.conditions import Key

router = APIRouter()
s3_client = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-east-1"))
S3_BUCKET = os.environ["S3_BUCKET_NAME"]

# Untuned starting point, not empirically validated against real usage.
HISTORY_TOKEN_BUDGET = 3000

class ChatRequest(BaseModel):
    # Uploads validate file size/count carefully; this had no bound at all
    # -- an empty or arbitrarily large question would still trigger a full
    # (billed) Nova call. 4000 chars is generous for a real question.
    question: str = Field(..., min_length=1, max_length=4000)

def _get_history_context(table, agreement_id: str, all_messages: list[dict]) -> tuple[list[dict], str | None]:
    """
    Returns (recent_messages, summary) for building the chat prompt.

    Rather than a flat "last N messages" window -- which abruptly forgets
    everything older the moment a conversation crosses that count, even
    though it's still sitting right there in DynamoDB -- this keeps as much
    recent history as fits in HISTORY_TOKEN_BUDGET tokens verbatim, and
    folds anything older that hasn't already been summarized into a rolling
    summary. That folding is incremental: it merges new turns into the
    *existing* summary rather than re-summarizing the whole conversation
    from scratch each time (the same approach LangChain's
    ConversationSummaryBufferMemory uses).
    """
    summary_item = get_chat_summary(table, agreement_id)
    existing_summary = summary_item.get("summary") if summary_item else None
    summarized_through = summary_item.get("summarized_through", 0) if summary_item else 0

    unsummarized = [
        m for m in all_messages
        if int(m["SK"].replace("CHAT#", "")) > summarized_through
    ]

    # Walk backward from the most recent message, keeping whatever fits in
    # budget. Always keep at least one message raw (the `and recent` guard)
    # even if it alone exceeds budget, so there's never zero immediate context.
    recent: list[dict] = []
    used_tokens = 0
    cutoff_index = 0
    for i in range(len(unsummarized) - 1, -1, -1):
        msg = unsummarized[i]
        msg_tokens = count_tokens(msg.get("question", "") + msg.get("answer", ""))
        if used_tokens + msg_tokens > HISTORY_TOKEN_BUDGET and recent:
            cutoff_index = i + 1
            break
        recent.insert(0, msg)
        used_tokens += msg_tokens
        cutoff_index = i

    aged_out = unsummarized[:cutoff_index]

    if aged_out:
        try:
            summarize_resp = bedrock.converse(
                modelId="amazon.nova-lite-v1:0",
                messages=[{"role": "user", "content": [{"text": build_summarization_prompt(existing_summary, aged_out)}]}],
                inferenceConfig={"temperature": 0.0, "maxTokens": 500}
            )
            existing_summary = summarize_resp["output"]["message"]["content"][0]["text"].strip()
            new_watermark = int(aged_out[-1]["SK"].replace("CHAT#", ""))
            save_chat_summary(table, agreement_id, existing_summary, new_watermark)
        except Exception as e:
            # Fail open: proceed with the recent window and whatever summary
            # already existed, rather than breaking the chat over compaction.
            print(f"Conversation compaction failed, continuing without folding older turns: {e}")

    return recent, existing_summary

_RETRYABLE_BEDROCK_ERRORS = {"ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException"}

def _call_nova_chat(system_text: str, messages: list[dict], retry: bool = True) -> dict:
    """Calls Nova via Bedrock Converse, retrying once for transient errors
    (throttling, temporary unavailability) -- these are worth one retry;
    anything else (bad request, access denied, etc.) never succeeds on
    retry, so it isn't worth the extra latency."""
    try:
        return bedrock.converse(
            modelId="amazon.nova-lite-v1:0",
            system=[{"text": system_text}],
            messages=messages,
            inferenceConfig={"temperature": 0.0, "maxTokens": 1000}
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if retry and code in _RETRYABLE_BEDROCK_ERRORS:
            print(f"Bedrock transient error ({code}), retrying once")
            return _call_nova_chat(system_text, messages, retry=False)
        raise

@router.post("/agreements/{agreement_id}/chat")
def ask_question(agreement_id: str, request: ChatRequest, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    # 0. Rate Limiting (Cooldown of 30 seconds per user) - Concurrency Safe
    now = datetime.now(timezone.utc).timestamp()
    # DynamoDB's resource-level API rejects native Python floats (it requires
    # Decimal) -- str() first to avoid binary-float rounding noise in the
    # Decimal conversion.
    now_decimal = Decimal(str(now))

    try:
        # Atomic Conditional Put: Fails instantly if a concurrent request already updated it
        table.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "RATELIMIT#CHAT",
                "last_request_time": now_decimal,
                "ttl": int(now) + 3600
            },
            ConditionExpression="attribute_not_exists(PK) OR last_request_time <= :limit",
            ExpressionAttributeValues={
                ":limit": now_decimal - Decimal("30.0")
            }
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait 30 seconds between messages.")
        # Otherwise log and continue so we don't break the chat if rate limiting fails
        print(f"Rate limit check failed unexpectedly: {e}")
    
    # 1. Verify ownership and status
    agreement = get_owned_agreement(table, user_id, agreement_id)
    if agreement.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="Analysis must be complete before chatting")
        
    s3_key = agreement.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=500, detail="Missing document text")

    # 2. Fetch full conversation history, then compact it: a recent raw
    # window (for the model's immediate context) plus a rolling summary of
    # anything older (see _get_history_context's docstring).
    history_resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"AGREEMENT#{agreement_id}",
            ":sk_prefix": "CHAT#"
        },
        ScanIndexForward=True # chronological order
    )
    all_messages = history_resp.get("Items", [])
    past_messages, conversation_summary = _get_history_context(table, agreement_id, all_messages)

    # 3. Fetch full document text from S3 OR chunks from Pinecone
    # Check if the document was indexed using Custom RAG
    rag_token_threshold = int(os.environ.get("RAG_TOKEN_THRESHOLD", 200000))
    is_custom_rag = agreement.get("has_rag", False) or agreement.get("bedrock_kb_id") == "CUSTOM_RAG" or agreement.get("token_count", 0) > rag_token_threshold

    if is_custom_rag:
        # A short follow-up ("what about for cause?") carries little meaning
        # on its own for search, so rewrite it into a standalone question
        # using recent history first. Only bother when there IS history;
        # skip on the first message. Retrieval-only: the user's original
        # question is still what gets shown, answered, and saved below.
        search_query = request.question
        if past_messages:
            try:
                rewrite_resp = bedrock.converse(
                    modelId="amazon.nova-lite-v1:0",
                    messages=[{"role": "user", "content": [{"text": build_query_rewrite_prompt(past_messages, request.question)}]}],
                    inferenceConfig={"temperature": 0.0, "maxTokens": 100}
                )
                search_query = rewrite_resp["output"]["message"]["content"][0]["text"].strip()
            except Exception as e:
                print(f"Query rewrite failed, falling back to raw question: {e}")

        try:
            chunks = query_pinecone(agreement_id, search_query, top_k=5)
            if not chunks:
                document_text = "No relevant context found in the document."
            else:
                document_text = "\n\n...[omitted]...\n\n".join(chunks)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve from Pinecone: {str(e)}")
    else:
        try:
            s3_resp = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            document_text = s3_resp["Body"].read().decode("utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read document from S3: {str(e)}")

    # 4. Build prompt and call Nova with Context Caching
    system_text = build_system_prompt(document_text, conversation_summary)
    user_text = request.question
    
    # Construct the Bedrock messages array
    messages = []
    for msg in past_messages:
        # Add past user question
        messages.append({"role": "user", "content": [{"text": msg.get("question", "")}]})
        # Add past AI response (just the plain text answer to save context)
        messages.append({"role": "assistant", "content": [{"text": msg.get("answer", "")}]})
        
    # Finally, append the new user question
    messages.append({"role": "user", "content": [{"text": user_text}]})
    
    try:
        nova_resp = _call_nova_chat(system_text, messages)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        print(f"Nova Error ({code}): {e}")
        if code in _RETRYABLE_BEDROCK_ERRORS:
            raise HTTPException(status_code=503, detail="The AI service is temporarily busy. Please try again in a moment.")
        raise HTTPException(status_code=500, detail="Failed to get valid response from AI")

    try:
        ai_text = nova_resp['output']['message']['content'][0]['text']
    except (KeyError, IndexError) as e:
        # Bedrock returns this shape when a response is content-filtered
        # (empty/absent message content) -- a distinct, expected condition,
        # not a bug, so it gets its own message instead of a generic 500.
        print(f"Nova returned no usable content (possibly content-filtered): {e}")
        raise HTTPException(status_code=502, detail="The AI could not generate a response for this question.")

    usage = nova_resp.get("usage", {})

    # Strip any accidental markdown formatting the AI might add
    ai_text = ai_text.strip()
    if ai_text.startswith("```json"):
        ai_text = ai_text[7:]
    if ai_text.startswith("```"):
        ai_text = ai_text[3:]
    if ai_text.endswith("```"):
        ai_text = ai_text[:-3]
    ai_text = ai_text.strip()

    # Parse the JSON from the AI
    try:
        ai_json = json.loads(ai_text)
    except json.JSONDecodeError:
        print(f"Nova did not return JSON. Falling back to plain text handling. Raw text: {ai_text}")
        ai_json = {
            "answer": ai_text,
            "answer_type": "general",
            "citations": [],
            "found_in_document": False
        }

    # 5. Generate timestamp and ID
    epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    message_id = f"chat-{epoch_ms}"
    
    # 6. Save to DynamoDB
    chat_item = {
        "PK": f"AGREEMENT#{agreement_id}",
        "SK": f"CHAT#{epoch_ms}",
        "messageId": message_id,
        "question": request.question,
        "answer": ai_json.get("answer", ""),
        "answer_type": ai_json.get("answer_type", "document"),
        "citations": ai_json.get("citations", []),
        "found_in_document": ai_json.get("found_in_document", False),
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Not surfaced anywhere yet -- this is the minimum needed for a
        # future per-user/per-document cost view, without building the
        # whole dashboard now. Bedrock already returns this; it was
        # previously just discarded.
        "input_tokens": usage.get("inputTokens"),
        "output_tokens": usage.get("outputTokens")
    }
    table.put_item(Item=chat_item)
    
    return {
        "messageId": message_id,
        "question": request.question,
        "answer": chat_item["answer"],
        "answer_type": chat_item["answer_type"],
        "citations": chat_item["citations"],
        "found_in_document": chat_item["found_in_document"]
    }

@router.get("/agreements/{agreement_id}/chat")
async def get_chat_history(agreement_id: str, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    # 1. Verify ownership
    get_owned_agreement(table, user_id, agreement_id)

    # 2. Query all chat messages
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"AGREEMENT#{agreement_id}") & Key("SK").begins_with("CHAT#")
    )
    
    messages = response.get("Items", [])
    
    return {
        "messages": [
            {
                "messageId": msg["messageId"],
                "question": msg.get("question", ""),
                "answer": msg.get("answer", ""),
                "answer_type": msg.get("answer_type", "document"),
                "citations": msg.get("citations", []),
                "found_in_document": msg.get("found_in_document", False),
                "created_at": msg.get("created_at")
            }
            for msg in messages
        ]
    }
