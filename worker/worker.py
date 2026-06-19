import boto3
import json
import os
import logging
from prompt import build_analysis_prompt
from nova import call_nova
from dynamo import (
    set_agreement_status,
    write_analysis_results,
    write_risks,
    write_ambiguous_clauses,
    write_discovered_clauses,
    write_normalized_checklist,
    set_rag_flag
)
from rag import index_document

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

def handler(event, _context):
    """
    Triggered by SQS. Coordinates the entire AI Analysis pipeline.
    """
    for record in event["Records"]:
        # 1. Parse the Job Ticket from the queue
        message = json.loads(record["body"])
        agreement_id = message["agreementId"]
        user_id = message["userId"]
        s3_key = message["s3_key"]
        token_count = message.get("token_count", 0)
        
        # SQS metadata tells us how many times this message has been retried
        receive_count = int(record.get("attributes", {}).get("ApproximateReceiveCount", 1))

        try:
            logger.info(f"Starting processing for agreement {agreement_id}")
            
            # 2. Tell the UI we are working on it
            exists = set_agreement_status(agreement_id, user_id, "PROCESSING")
            if not exists:
                logger.warning(f"Agreement {agreement_id} was deleted before processing started. Aborting.")
                return

            # 3. Download the actual text document from S3
            s3_obj = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            document_text = s3_obj["Body"].read().decode("utf-8")

            # 4. Check if document is too large (Nova Lite easily handles 200,000 tokens)
            if token_count > 200000:
                logger.info(f"Document {agreement_id} is >200k tokens. Triggering RAG pipeline.")
                
                # 4a. Index document into Pinecone using our Custom RAG script
                index_document(agreement_id, document_text)
                
                # 4b. We no longer have a Bedrock kb_id. We can mark it as having RAG in the database.
                set_rag_flag(agreement_id, user_id)
                
                # 4c. For the initial AI analysis (verdict, risks, etc.), we pass a large context to the AI.
                # Nova Lite supports 300,000 tokens (approx 1.2M characters).
                # We cap at 1,000,000 characters to prevent absolute massive files from timing out the Lambda.
                document_text = document_text[:1000000]
                logger.info("Indexed document and truncated text for initial analysis.")

            # 5. Build prompt and Call Nova
            prompt = build_analysis_prompt(document_text)
            ai_data = call_nova(prompt)

            # 6. Save everything to DynamoDB
            write_analysis_results(agreement_id, user_id, ai_data)
            write_risks(agreement_id, ai_data.get("risks", []))
            write_ambiguous_clauses(agreement_id, ai_data.get("ambiguous_clauses", []))
            write_discovered_clauses(agreement_id, ai_data.get("discovered_clauses", []))
            write_normalized_checklist(agreement_id, ai_data.get("normalized_checklist", []))

            # 7. Tell the UI we are finished!
            set_agreement_status(agreement_id, user_id, "COMPLETED")
            logger.info(f"Successfully processed agreement {agreement_id}")

        except Exception as e:
            logger.error(f"Error processing agreement {agreement_id}: {e}", exc_info=True)
            
            # SQS automatically retries messages if they fail (e.g. Bedrock rate limit).
            # We ONLY tell the frontend UI it "FAILED" if this is our absolute final attempt (e.g. 3rd try).
            # Otherwise, we leave the status as "PROCESSING" so the frontend UI keeps polling!
            if receive_count >= 3:
                exists = set_agreement_status(agreement_id, user_id, "FAILED")
                if not exists:
                    logger.warning(f"Agreement {agreement_id} was deleted before we could mark it FAILED.")
                    return # Don't raise the error, we don't want SQS to retry a deleted document
            
            # Re-raise the exception so SQS knows the job failed and can execute the retry
            raise e
