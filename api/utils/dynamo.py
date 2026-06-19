import boto3
import os
from datetime import datetime, timezone

def get_table():
    """Connects to our DynamoDB table."""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def create_agreement(user_id: str, agreement_id: str, title: str, file_count: int, 
                     source_filenames: list, token_count: int, document_hash: str, s3_key: str, has_pdf: bool = False) -> None:
    """
    Saves a new Agreement record to the database.
    We set 'GSI1PK' so our API can verify ownership of the agreement later.
    """
    table = get_table()
    table.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": f"AGREEMENT#{agreement_id}",
        # GSI-1: lets any endpoint look up userId from just an agreementId
        "GSI1PK": f"AGREEMENT#{agreement_id}",
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

def get_hash_index(sha256_hash: str) -> dict | None:
    """
    Checks if we have ever processed this exact document before.
    """
    table = get_table()
    response = table.get_item(Key={"PK": f"HASH#{sha256_hash}", "SK": "#METADATA"})
    return response.get("Item")
