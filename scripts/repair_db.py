import boto3
import os
import sys

def repair_database():
    print("Connecting to DynamoDB...")
    dynamodb = boto3.resource("dynamodb")
    
    # We need to get the table name. If not in env, we can try to guess it based on CloudFormation or ask the user.
    # The CloudFormation template uses clauseiq-${Environment}. Let's assume clauseiq-dev if not set.
    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "clauseiq-dev")
    print(f"Using table: {table_name}")
    table = dynamodb.Table(table_name)
    
    try:
        # Scan for all agreements
        print("Scanning for agreements...")
        response = table.scan(
            FilterExpression="begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={":sk_prefix": "AGREEMENT#"}
        )
        agreements = response.get("Items", [])
        print(f"Found {len(agreements)} total agreements.")
        
        fixed_count = 0
        for agreement in agreements:
            if agreement.get("status") == "FAILED":
                pk = agreement["PK"]
                # The agreement's ID
                agreement_id = agreement["agreementId"]
                
                # Check if this agreement actually has an #ANALYSIS record
                # The Analysis record lives at PK: AGREEMENT#{agreement_id}, SK: #ANALYSIS
                analysis_resp = table.get_item(
                    Key={
                        "PK": f"AGREEMENT#{agreement_id}",
                        "SK": "#ANALYSIS"
                    }
                )
                
                if "Item" in analysis_resp:
                    # It has an analysis! The FAILED status is a lie.
                    print(f"Fixing corrupted agreement: {agreement_id}")
                    table.update_item(
                        Key={"PK": pk, "SK": agreement["SK"]},
                        UpdateExpression="SET #s = :c",
                        ExpressionAttributeNames={"#s": "status"},
                        ExpressionAttributeValues={":c": "COMPLETED"}
                    )
                    fixed_count += 1
                else:
                    print(f"Agreement {agreement_id} is legitimately FAILED (no analysis found).")
                    
        print(f"Repair complete! Fixed {fixed_count} corrupted documents.")
    except Exception as e:
        print(f"Error during repair: {e}")

if __name__ == "__main__":
    repair_database()
