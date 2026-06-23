import os
import json
import boto3
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from utils.dynamo import get_table
from utils.qa_prompt import build_system_prompt, build_user_prompt
from utils.rag import query_pinecone

router = APIRouter()
s3_client = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-east-1"))
S3_BUCKET = os.environ["S3_BUCKET_NAME"]

class ChatRequest(BaseModel):
    question: str

@router.post("/agreements/{agreement_id}/chat")
def ask_question(agreement_id: str, request: ChatRequest, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    # 0. Rate Limiting (Cooldown of 5 seconds per user) - Concurrency Safe
    now = datetime.now(timezone.utc).timestamp()
    
    try:
        # Atomic Conditional Put: Fails instantly if a concurrent request already updated it
        table.put_item(
            Item={
                "PK": f"USER#{user_id}", 
                "SK": "RATELIMIT#CHAT",
                "last_request_time": now,
                "ttl": int(now) + 3600
            },
            ConditionExpression="attribute_not_exists(PK) OR last_request_time <= :limit",
            ExpressionAttributeValues={
                ":limit": now - 5.0
            }
        )
    except boto3.client("dynamodb").exceptions.ConditionalCheckFailedException:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait 5 seconds between messages.")
    except Exception as e:
        # If it's the generic ClientError for conditional check failed
        if e.__class__.__name__ == 'ClientError' and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait 5 seconds between messages.")
        # Otherwise log and continue so we don't break the chat if rate limiting fails
        pass
    
    # 1. Verify ownership and status
    agreement_resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    agreement = agreement_resp.get("Item")
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
        
    if agreement.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="Analysis must be complete before chatting")
        
    s3_key = agreement.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=500, detail="Missing document text")

    # 2. Fetch full document text from S3 OR chunks from Pinecone
    # Check if the document was indexed using Custom RAG
    is_custom_rag = agreement.get("has_rag", False) or agreement.get("bedrock_kb_id") == "CUSTOM_RAG" or agreement.get("token_count", 0) > 200000
    
    if is_custom_rag:
        try:
            chunks = query_pinecone(agreement_id, request.question, top_k=5)
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

    # 3. Fetch past conversation history
    history_resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"AGREEMENT#{agreement_id}",
            ":sk_prefix": "CHAT#"
        },
        ScanIndexForward=True # chronological order
    )
    past_messages = history_resp.get("Items", [])[-10:] # Keep last 10 messages for context window
    
    # 4. Build prompt and call Nova with Context Caching
    system_text = build_system_prompt(document_text)
    user_text = build_user_prompt(request.question)
    
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
        nova_resp = bedrock.converse(
            modelId="amazon.nova-lite-v1:0",
            system=[{"text": system_text}],
            messages=messages,
            inferenceConfig={"temperature": 0.0, "maxTokens": 1000}
        )
        ai_text = nova_resp['output']['message']['content'][0]['text']
        
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
    except Exception as e:
        print(f"Nova Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get valid response from AI")

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
        "created_at": datetime.now(timezone.utc).isoformat()
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

from boto3.dynamodb.conditions import Key

@router.get("/agreements/{agreement_id}/chat")
async def get_chat_history(agreement_id: str, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    # 1. Verify ownership
    agreement_resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    if not agreement_resp.get("Item"):
        raise HTTPException(status_code=404, detail="Agreement not found")
        
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
