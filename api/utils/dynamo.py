import boto3
import os
from datetime import datetime, timezone
from fastapi import HTTPException

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def get_table():
    """Returns our DynamoDB table, built once per cold start."""
    return _table

def get_owned_agreement(table, user_id: str, agreement_id: str) -> dict:
    """Fetches an agreement the caller owns, or raises 404. Shared by every
    endpoint that needs ownership-scoped access to a single agreement."""
    item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"}).get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Agreement not found")
    return item

def create_agreement(user_id: str, agreement_id: str, title: str, file_count: int,
                     source_filenames: list, token_count: int, document_hash: str, s3_key: str, has_pdf: bool = False) -> None:
    """Saves a new Agreement record to the database."""
    # No try/except here: if this write fails, the caller (upload_agreement)
    # must see the exception and return an error, not a false "UPLOADED"
    # response for a document that was never actually recorded.
    table = get_table()
    with table.batch_writer() as batch:
        # 1. Main Agreement Record
        batch.put_item(Item={
            "PK": f"USER#{user_id}",
            "SK": f"AGREEMENT#{agreement_id}",
            "agreementId": agreement_id,
            "userId": user_id,
            "title": title,
            "s3_key": s3_key,
            "status": "UPLOADED",
            "document_hash": document_hash,
            "token_count": token_count,
            "file_count": file_count,
            "source_filenames": source_filenames,
            "document_types": None,       # set later by AI Worker
            "overall_risk": None,         # set later by AI Worker
            "has_rag": False,        # set to True if we use custom RAG
            "has_pdf": has_pdf,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        # 2. Hash Record for deduplication
        batch.put_item(Item={
            "PK": f"HASH#{document_hash}",
            "SK": "#METADATA",
            "agreementId": agreement_id,
            "userId": user_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

def get_hash_index(sha256_hash: str) -> dict | None:
    """
    Checks if we have ever processed this exact document before.
    """
    table = get_table()
    response = table.get_item(Key={"PK": f"HASH#{sha256_hash}", "SK": "#METADATA"})
    return response.get("Item")

def get_chat_summary(table, agreement_id: str) -> dict | None:
    """Fetches the rolling chat-history summary for an agreement, if one has
    been built yet (see api/routers/chat.py's compaction logic)."""
    return table.get_item(Key={"PK": f"AGREEMENT#{agreement_id}", "SK": "#CHAT_SUMMARY"}).get("Item")

def save_chat_summary(table, agreement_id: str, summary: str, summarized_through: int) -> None:
    """
    Persists the rolling chat summary. `summarized_through` is the epoch_ms
    of the newest message already folded into `summary` -- a watermark so
    later requests only fold in messages after this point, instead of
    re-summarizing the whole conversation from scratch each time.

    Lives under the agreement's own PK, so it's automatically swept up by
    delete_agreement's existing "delete every child item" query -- no
    separate cleanup needed.
    """
    table.put_item(Item={
        "PK": f"AGREEMENT#{agreement_id}",
        "SK": "#CHAT_SUMMARY",
        "summary": summary,
        "summarized_through": summarized_through
    })
