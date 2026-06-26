import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from utils.dynamo import get_table

router = APIRouter()

class ShareResponse(BaseModel):
    share_id: str

@router.post("/agreements/{agreement_id}/share", response_model=ShareResponse)
def create_share_link(agreement_id: str, user: dict = Depends(get_current_user)):
    """Creates a public, read-only snapshot of the current chat."""
    user_id = user["userId"]
    table = get_table()
    
    # 1. Fetch the agreement to make sure it exists and belongs to the user
    agreement_resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    if "Item" not in agreement_resp:
        raise HTTPException(status_code=404, detail="Agreement not found")
    agreement = agreement_resp["Item"]

    # 2. Fetch the current chat history
    chat_resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":sk_prefix": f"CHAT#{agreement_id}#"
        }
    )
    
    # 3. Generate a unique share ID and create the snapshot
    share_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    snapshot_item = {
        "PK": f"SHARE#{share_id}",
        "SK": f"SHARE#{share_id}",
        "agreement_id": agreement_id,
        "title": agreement.get("title", "Shared Document"),
        "created_at": now,
        "messages": chat_resp.get("Items", [])
    }
    
    # Save the snapshot to DynamoDB
    table.put_item(Item=snapshot_item)
    
    return {"share_id": share_id}

@router.get("/share/{share_id}")
def get_shared_chat(share_id: str):
    """Public endpoint to retrieve a shared chat snapshot."""
    table = get_table()
    resp = table.get_item(Key={"PK": f"SHARE#{share_id}", "SK": f"SHARE#{share_id}"})
    
    if "Item" not in resp:
        raise HTTPException(status_code=404, detail="Shared chat not found")
        
    return resp["Item"]
