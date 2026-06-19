import os
import uuid
import boto3
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import List, Optional
from boto3.dynamodb.conditions import Key
from auth import get_current_user
from utils.extraction import extract_pdf, extract_docx, concatenate_files
from utils.tokens import count_tokens, compute_hash
import fitz
from utils.dynamo import create_agreement, get_hash_index, get_table

router = APIRouter()
s3_client = boto3.client("s3")
S3_BUCKET = os.environ["S3_BUCKET_NAME"]

def copy_analysis_for_dedup(table, original_agreement_id: str, new_agreement_id: str,
                             new_user_id: str, title: str, token_count: int,
                             document_hash: str, s3_key: str, file_count, source_filenames, has_pdf: bool) -> bool:
    # 1. Check if the original Analysis entity still exists
    analysis_resp = table.get_item(Key={"PK": f"AGREEMENT#{original_agreement_id}", "SK": "#ANALYSIS"})
    if "Item" not in analysis_resp:
        return False  # stale

    analysis_item = analysis_resp["Item"]

    # 2. Fetch all child entities for the original agreement
    child_resp = table.query(KeyConditionExpression=Key("PK").eq(f"AGREEMENT#{original_agreement_id}"))
    source_items = child_resp["Items"]

    # 3. Create the new Agreement record (status=COMPLETED immediately)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "PK": f"USER#{new_user_id}",
        "SK": f"AGREEMENT#{new_agreement_id}",
        "GSI1PK": f"AGREEMENT#{new_agreement_id}",
        "agreementId": new_agreement_id,
        "userId": new_user_id,
        "title": title,
        "s3_key": s3_key,
        "status": "COMPLETED",
        "document_hash": document_hash,
        "token_count": token_count,
        "file_count": file_count,
        "source_filenames": source_filenames,
        "document_types": analysis_item.get("document_types"),
        "overall_risk": analysis_item.get("overall_risk"),
        "has_rag": False,
        "has_pdf": has_pdf,
        "created_at": now
    })

    # 4. Batch-copy all child entities
    copy_sk_prefixes = {"#ANALYSIS", "RISK#", "AMBIGUOUS#", "CLAUSE#"}
    with table.batch_writer() as batch:
        for item in source_items:
            sk = item.get("SK", "")
            if not any(sk.startswith(prefix) for prefix in copy_sk_prefixes):
                continue
                
            new_item = dict(item)
            new_item["PK"] = f"AGREEMENT#{new_agreement_id}"
            
            if sk != "#ANALYSIS":
                prefix = sk.split("#")[0] + "#"
                new_item["SK"] = prefix + uuid.uuid4().hex[:8]
                
            batch.put_item(Item=new_item)

    return True

@router.post("/agreements")
def upload_agreement(
    text: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    user: dict = Depends(get_current_user)
):
    user_id = user["userId"]

    # 1. Validate Input
    if text and files:
        raise HTTPException(status_code=400, detail="Provide either text or files, not both")
    if not text and not files:
        raise HTTPException(status_code=400, detail="No files or text provided")

    extracted_items = []
    source_filenames = []

    has_pdf = False
    pdf_bytes = None

    # 2. Extract Text
    if text:
        words = text.split()
        if not words:
            raise HTTPException(status_code=400, detail="Pasted text is empty")
        
        title_snippet = " ".join(words[:5])
        if len(words) > 5:
            title_snippet += "..."
            
        extracted_items.append({"filename": "pasted_text.txt", "text": text})
        source_filenames = [title_snippet]
    else:
        if len(files) > 5:
            raise HTTPException(status_code=413, detail="Maximum 5 files allowed")
        
        merged_pdf = None
        has_pdf = False

        for file in files:
            file_bytes = file.file.read()
            
            if file.filename.lower().endswith(".pdf"):
                has_pdf = True
                if merged_pdf is None:
                    merged_pdf = fitz.open(stream=file_bytes, filetype="pdf")
                else:
                    pdf = fitz.open(stream=file_bytes, filetype="pdf")
                    merged_pdf.insert_pdf(pdf)
                
            if len(file_bytes) > 50 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"File {file.filename} exceeds 50MB limit")
                
            if file.filename.lower().endswith(".pdf"):
                raw_text = extract_pdf(file_bytes)
            elif file.filename.lower().endswith(".docx"):
                raw_text = extract_docx(file_bytes)
            else:
                raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.filename}. Only PDF and DOCX are allowed.")
                
            extracted_items.append({"filename": file.filename, "text": raw_text})
            source_filenames.append(file.filename)
            
        if has_pdf and merged_pdf is not None:
            pdf_bytes = merged_pdf.write()

    # 3. Concatenate and Compute Metrics
    combined_text = concatenate_files(extracted_items)
    token_count = count_tokens(combined_text)
    document_hash = compute_hash(combined_text)

    # 4. Check for duplicates in DynamoDB
    existing = get_hash_index(document_hash)
    if existing:
        original_id = existing["agreementId"]
        new_agreement_id = f"agmt-{uuid.uuid4().hex[:8]}"
        new_s3_key = f"documents/{user_id}/{new_agreement_id}/original.txt"
        
        table = get_table()
        copied = copy_analysis_for_dedup(
            table=table,
            original_agreement_id=original_id,
            new_agreement_id=new_agreement_id,
            new_user_id=user_id,
            title=source_filenames[0] if len(source_filenames) == 1 else "Combined Documents",
            token_count=token_count,
            document_hash=document_hash,
            s3_key=new_s3_key,
            file_count=len(source_filenames),
            source_filenames=source_filenames,
            has_pdf=has_pdf
        )
        
        if copied:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=new_s3_key,
                Body=combined_text.encode("utf-8")
            )
            
            if has_pdf and pdf_bytes:
                pdf_key = f"documents/{user_id}/{new_agreement_id}/original.pdf"
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=pdf_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf"
                )
                
            return {
                "agreementId": new_agreement_id,
                "status": "COMPLETED",
                "message": "Files successfully uploaded and analysis retrieved from cache"
            }

    # 5. Generate ID and Save to S3
    agreement_id = f"agmt-{uuid.uuid4().hex[:8]}"
    s3_key = f"documents/{user_id}/{agreement_id}/original.txt"
    
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=combined_text.encode("utf-8")
    )
    
    if has_pdf and pdf_bytes:
        pdf_key = f"documents/{user_id}/{agreement_id}/original.pdf"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=pdf_key,
            Body=pdf_bytes,
            ContentType="application/pdf"
        )

    # 6. Save metadata to DynamoDB
    create_agreement(
        user_id=user_id,
        agreement_id=agreement_id,
        title=source_filenames[0] if len(source_filenames) == 1 else "Combined Documents",
        file_count=len(source_filenames),
        source_filenames=source_filenames,
        token_count=token_count,
        document_hash=document_hash,
        s3_key=s3_key,
        has_pdf=has_pdf
    )

    # 7. Return Response
    return {
        "agreementId": agreement_id,
        "status": "UPLOADED",
        "message": "Files successfully uploaded and extraction started"
    }

@router.get("/agreements")
def list_agreements(user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("AGREEMENT#")
    )
    return response.get("Items", [])


@router.get("/agreements/{agreement_id}")
def get_agreement(agreement_id: str, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    response = table.get_item(
        Key={
            "PK": f"USER#{user_id}",
            "SK": f"AGREEMENT#{agreement_id}"
        }
    )
    
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Agreement not found")
        
    return item

@router.get("/agreements/{agreement_id}/analysis")
def get_analysis(agreement_id: str, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    agreement_resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    agreement = agreement_resp.get("Item")
    
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
        
    if agreement.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail={"error": "Analysis not yet complete", "status": agreement.get("status")})
        
    child_resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"AGREEMENT#{agreement_id}")
    )
    items = child_resp.get("Items", [])
    
    analysis_data = {}
    risks = []
    ambiguous = []
    discovered = []
    normalized = []
    
    for item in items:
        sk = item.get("SK", "")
        if sk == "#ANALYSIS":
            analysis_data = item
        elif sk.startswith("RISK#"):
            item["riskId"] = sk.replace("RISK#", "")
            risks.append(item)
        elif sk.startswith("AMBIGUOUS#"):
            item["ambiguousId"] = sk.replace("AMBIGUOUS#", "")
            ambiguous.append(item)
        elif sk.startswith("DISCOVERED#"):
            item["clauseId"] = sk.replace("DISCOVERED#", "")
            discovered.append(item)
        elif sk.startswith("NORMALIZED#"):
            item["normalizedId"] = sk.replace("NORMALIZED#", "")
            normalized.append(item)
            
    if not analysis_data:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    return {
        "verdict": analysis_data.get("verdict", {}),
        "overall_risk": analysis_data.get("overall_risk"),
        "summary": analysis_data.get("summary", ""),
        "risks": risks,
        "ambiguous_clauses": ambiguous,
        "discovered_clauses": discovered,
        "normalized_checklist": normalized,
        "financial_terms": analysis_data.get("financial_terms", []),
        "timeline": analysis_data.get("timeline", []),
        "is_legal_document": analysis_data.get("is_legal_document", True)
    }

@router.delete("/agreements/{agreement_id}")
def delete_agreement(agreement_id: str, user: dict = Depends(get_current_user)):
    user_id = user["userId"]
    table = get_table()
    
    agreement_resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    agreement = agreement_resp.get("Item")
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
        
    child_resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"AGREEMENT#{agreement_id}")
    )
    items = child_resp.get("Items", [])
    
    with table.batch_writer() as batch:
        batch.delete_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
            
    s3_key = agreement.get("s3_key")
    if s3_key:
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        except Exception as e:
            print(f"Failed to delete S3 object: {e}")
            
    has_rag = agreement.get("has_rag", False) or agreement.get("bedrock_kb_id") == "CUSTOM_RAG"
    if has_rag:
        from utils.rag import delete_document
        delete_document(agreement_id)
            
    return {"message": "Agreement deleted"}

@router.get("/agreements/{agreement_id}/document")
async def get_document_content(agreement_id: str, user: dict = Depends(get_current_user)):
    """Fetch the raw text content of the document from S3 and return it directly."""
    user_id = user["userId"]
    table = get_table()
    
    # 1. Verify ownership
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Agreement not found")
        
    # 2. Get the S3 Key
    s3_key = item.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # 3. Fetch the text content directly from S3
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        text_content = response['Body'].read().decode('utf-8')
        return {"text": text_content}
    except Exception as e:
        print(f"Error fetching document content: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch document content")

@router.get("/agreements/{agreement_id}/viewer_data")
async def get_viewer_data(agreement_id: str, user: dict = Depends(get_current_user)):
    """Smart endpoint to return either a PDF presigned URL or raw text."""
    user_id = user["userId"]
    table = get_table()
    
    resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
    item = resp.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Agreement not found")
        
    has_pdf = item.get("has_pdf", False)
    
    if has_pdf:
        pdf_key = f"documents/{user_id}/{agreement_id}/original.pdf"
        try:
            url = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': S3_BUCKET,
                    'Key': pdf_key,
                    'ResponseContentDisposition': 'inline',
                    'ResponseContentType': 'application/pdf'
                },
                ExpiresIn=3600
            )
            return {"type": "pdf", "url": url}
        except Exception as e:
            print(f"Error generating presigned URL for PDF: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate PDF link")
            
    else:
        # Fallback to Text
        s3_key = item.get("s3_key")
        if not s3_key:
            raise HTTPException(status_code=404, detail="Document text not found")
            
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            text_content = response['Body'].read().decode('utf-8')
            return {"type": "text", "content": text_content}
        except Exception as e:
            print(f"Error fetching document content: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch document text")
