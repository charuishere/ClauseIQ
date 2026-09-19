import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_current_user
from utils.dynamo import get_table, get_owned_agreement

router = APIRouter()

class ShareResponse(BaseModel):
    share_id: str

@router.post("/agreements/{agreement_id}/share", response_model=ShareResponse)
def create_share_link(agreement_id: str, user: dict = Depends(get_current_user)):
    """Creates a public, read-only snapshot of the current chat."""
    user_id = user["userId"]
    table = get_table()
    
    # 1. Fetch the agreement to make sure it exists and belongs to the user
    agreement = get_owned_agreement(table, user_id, agreement_id)

    # 2. Fetch the current chat history
    chat_resp = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"AGREEMENT#{agreement_id}",
            ":sk_prefix": "CHAT#"
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
    
    # Save the public snapshot, plus an index item under the agreement's own
    # PK so delete_agreement (which already queries AGREEMENT#{id} children)
    # can find and delete it too -- otherwise the public snapshot outlives
    # the agreement it was shared from.
    with table.batch_writer() as batch:
        batch.put_item(Item=snapshot_item)
        batch.put_item(Item={
            "PK": f"AGREEMENT#{agreement_id}",
            "SK": f"SHARELINK#{share_id}",
        })

    return {"share_id": share_id}

@router.get("/share/{share_id}")
def get_shared_chat(share_id: str):
    """Public endpoint to retrieve a shared chat snapshot."""
    table = get_table()
    resp = table.get_item(Key={"PK": f"SHARE#{share_id}", "SK": f"SHARE#{share_id}"})
    
    if "Item" not in resp:
        raise HTTPException(status_code=404, detail="Shared chat not found")
        
    return resp["Item"]
