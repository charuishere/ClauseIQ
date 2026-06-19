import boto3
import json
import os
import logging
from pinecone import Pinecone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# We use bedrock-runtime for invoking the model directly
# Since Titan v2 is in ap-south-1, we use the default Lambda region
bedrock_runtime = boto3.client("bedrock-runtime")
secrets_client = boto3.client("secretsmanager")

def _get_pinecone_credentials() -> dict:
    """Fetch Pinecone API key and index host from Secrets Manager."""
    response = secrets_client.get_secret_value(SecretId=os.environ["PINECONE_SECRET_ARN"])
    return json.loads(response["SecretString"])

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """
    Split text into chunks of approximately `chunk_size` characters with `overlap`.
    A basic implementation of sliding window chunking.
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + chunk_size, text_length)
        
        # Try to find a reasonable boundary like a newline or period
        if end < text_length:
            boundary_idx = max(text.rfind('\n', start, end), text.rfind('. ', start, end))
            if boundary_idx > start + chunk_size // 2:
                end = boundary_idx + 1 # Include the boundary character
                
        chunks.append(text[start:end].strip())
        if end >= text_length:
            break
        start = end - overlap
        
        # Prevent infinite loop if overlap is too large
        if start <= end - chunk_size:
            start = end
            
    return chunks

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings for a list of texts using Amazon Titan v2."""
    embeddings = []
    
    # Process chunks one by one
    for text in texts:
        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
        try:
            response = bedrock_runtime.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=body,
                accept="application/json",
                contentType="application/json"
            )
            response_body = json.loads(response["body"].read())
            embeddings.append(response_body["embedding"])
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            raise
    return embeddings

def index_document(agreement_id: str, document_text: str):
    """
    Chunk the document, get embeddings, and upsert to Pinecone.
    """
    logger.info(f"Starting custom RAG indexing for {agreement_id}")
    
    # 1. Chunk the document
    chunks = chunk_text(document_text)
    logger.info(f"Split document into {len(chunks)} chunks.")
    
    if not chunks:
        logger.warning("No text to index.")
        return
        
    # 2. Get embeddings
    embeddings = get_embeddings(chunks)
    logger.info(f"Generated {len(embeddings)} embeddings.")
    
    # 3. Upsert to Pinecone
    creds = _get_pinecone_credentials()
    
    # Pinecone SDK initialization
    pc = Pinecone(api_key=creds["pineconeApiKey"])
    
    # Target our specific index host
    host = creds["index_host"]
    if host.startswith("https://"):
        host = host[8:]
        
    index = pc.Index(host=host)
    
    vectors_to_upsert = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = f"{agreement_id}-chunk-{i}"
        vectors_to_upsert.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "agreement_id": agreement_id,
                "text": chunk
            }
        })
        
    # Batch upsert to Pinecone
    batch_size = 100
    for i in range(0, len(vectors_to_upsert), batch_size):
        batch = vectors_to_upsert[i:i + batch_size]
        index.upsert(vectors=batch)
        
    logger.info(f"Successfully upserted {len(vectors_to_upsert)} vectors to Pinecone for {agreement_id}.")

