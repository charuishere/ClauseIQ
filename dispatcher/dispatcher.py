import boto3
import json
import os

# Initialize AWS SDK clients
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def handler(event, _context):
    """
    This function is automatically triggered by AWS S3 every time a new file is uploaded.
    """
    for record in event["Records"]:
        # 1. Get the exact path of the uploaded file
        s3_key = record["s3"]["object"]["key"]
        
        # The key looks like: documents/{userId}/{agreementId}/original.txt
        parts = s3_key.split("/")
        user_id = parts[1]
        agreement_id = parts[2]

        # 2. Fetch the token_count we saved to DynamoDB during the API upload
        response = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
        token_count = int(response.get("Item", {}).get("token_count", 0))

        # 3. Send a message to the SQS Queue to wake up the AI Worker
        sqs.send_message(
            QueueUrl=os.environ["SQS_QUEUE_URL"],
            MessageBody=json.dumps({
                "agreementId": agreement_id,
                "userId": user_id,
                "s3_key": s3_key,
                "token_count": token_count
            })
        )