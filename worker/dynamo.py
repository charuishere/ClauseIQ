import boto3
import os
import uuid
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def set_agreement_status(agreement_id: str, user_id: str, status: str):
    """Updates the status of the agreement (PROCESSING, COMPLETED, FAILED)."""
    try:
        table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"},
            UpdateExpression="SET #status = :s",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":s": status},
            ConditionExpression="attribute_exists(PK)"
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        # The agreement was deleted by the user, so don't recreate a ghost row
        return False

def set_rag_flag(agreement_id: str, user_id: str):
    """Sets the has_rag flag on the parent Agreement entity."""
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"},
        UpdateExpression="SET has_rag = :val",
        ExpressionAttributeValues={":val": True}
    )

def write_analysis_results(agreement_id: str, user_id: str, ai_data: dict):
    """
    Writes the root Analysis entity and updates the main Agreement entity
    with the document_types and overall_risk.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    update_expr = "SET document_types = :dt, overall_risk = :orisk"
    expr_vals = {
        ":dt": ai_data.get("document_types", []),
        ":orisk": ai_data.get("overall_risk", "low")
    }
    
    if ai_data.get("document_title"):
        update_expr += ", title = :title"
        expr_vals[":title"] = ai_data.get("document_title")

    # 1. Update the parent Agreement entity with high-level fields
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_vals
    )

    # 2. Write the core Analysis entity
    table.put_item(
        Item={
            "PK": f"AGREEMENT#{agreement_id}",
            "SK": "#ANALYSIS",
            "verdict": ai_data.get("verdict", {}),
            "summary": ai_data.get("summary", ""),
            "financial_terms": ai_data.get("financial_terms", []),
            "timeline": ai_data.get("timeline", []),
            "completed_at": now
        }
    )

def write_risks(agreement_id: str, risks: list):
    with table.batch_writer() as batch:
        for risk in risks:
            risk_item = {
                "PK": f"AGREEMENT#{agreement_id}",
                "SK": f"RISK#{uuid.uuid4().hex}",
                **risk
            }
            batch.put_item(Item=risk_item)

def write_ambiguous_clauses(agreement_id: str, ambiguous_clauses: list):
    with table.batch_writer() as batch:
        for clause in ambiguous_clauses:
            clause_item = {
                "PK": f"AGREEMENT#{agreement_id}",
                "SK": f"AMBIGUOUS#{uuid.uuid4().hex}",
                **clause
            }
            batch.put_item(Item=clause_item)

def write_discovered_clauses(agreement_id: str, discovered_clauses: list):
    with table.batch_writer() as batch:
        for clause in discovered_clauses:
            clause_item = {
                "PK": f"AGREEMENT#{agreement_id}",
                "SK": f"DISCOVERED#{uuid.uuid4().hex}",
                **clause
            }
            batch.put_item(Item=clause_item)

def write_normalized_checklist(agreement_id: str, normalized_checklist: list):
    with table.batch_writer() as batch:
        for check in normalized_checklist:
            check_item = {
                "PK": f"AGREEMENT#{agreement_id}",
                "SK": f"NORMALIZED#{uuid.uuid4().hex}",
                **check
            }
            batch.put_item(Item=check_item)
