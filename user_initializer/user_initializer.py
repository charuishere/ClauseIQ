import boto3, os
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def handler(event, context):
    user_attrs = event["request"]["userAttributes"]
    user_id = user_attrs["sub"]
    
    table.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "#METADATA",
        "name": user_attrs.get("name", ""),
        "email": user_attrs.get("email", ""),
        "cognito_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return event  # Cognito requires returning the event unchanged
