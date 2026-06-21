# ClauseIQ: Technical System Design Interview Guide

This guide provides deep, technical explanations for the 20 most common System Design interview topics. It explains exactly how ClauseIQ implements each concept using concrete examples from our codebase.

---

### 1. Database Design (DynamoDB Single-Table Design)
**The Concept:** SQL databases use multiple tables and foreign keys, requiring heavy compute for `JOIN` operations. NoSQL databases (like DynamoDB) optimize for high-speed reads by pre-joining data.
**ClauseIQ Implementation:** We use DynamoDB with a "Single-Table Design". 
**Concrete Example:** Instead of querying an `Agreements` table and a `Clauses` table separately, we store them in one table under the same Partition Key.
```python
# Fetches the agreement, analysis, and all 50 clauses in one 5ms request
table.query(
    KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("AGREEMENT#")
)
```

### 2. Caching (Native LLM Context Caching)
**The Concept:** Caching prevents the system from doing the same expensive work twice. 
**ClauseIQ Implementation:** DynamoDB reads are already single-digit milliseconds, so adding Redis is an anti-pattern. Instead, our most expensive bottleneck is the AI (reading 1,000 pages takes 10 seconds). We implemented **Prompt Caching** in AWS Bedrock.
**Concrete Example:** In `api/routers/chat.py`, we separate the document into a system prompt and append a `cachePoint`. AWS freezes the document in RAM for 5 minutes. Subsequent questions skip the 10-second reading phase, reducing latency and cutting input token costs by 90%.
```python
"system": [
    {"text": document_text},
    {"cachePoint": {"type": "default"}}
]
```

### 3. Asynchronous Processing (SQS + Lambda)
**The Concept:** APIs should never block the main thread waiting for a slow task (like AI processing or sending an email) to finish.
**ClauseIQ Implementation:** We decouple the upload API from the AI engine using an Amazon SQS message queue.
**Concrete Example:** When a user uploads a PDF, the API uploads it to S3, sends a JSON message `{"agreement_id": "123", "s3_key": "path/file.pdf"}` to SQS, and immediately returns a `200 OK`. A background Lambda Worker triggers off the SQS queue, runs the 60-second AI analysis, and saves the result to DynamoDB without blocking the user's browser.

### 4. Consistency & Concurrency (Optimistic Locking)
**The Concept:** If multiple threads modify the same data simultaneously, race conditions occur (e.g., double-spending money).
**ClauseIQ Implementation:** We use DynamoDB's `ConditionExpression` to enforce atomic, hardware-level locks during write operations.
**Concrete Example:** In our Rate Limiter (`chat.py`), if a bot sends 10 concurrent requests, DynamoDB executes a Conditional Put. It only allows the write if `last_request_time <= now - 5.0`. The 9 losing threads receive a `ConditionalCheckFailedException`, blocking the spam instantly.

### 5. High Availability & Stateless Servers
**The Concept:** A system must remain online even if a server crashes.
**ClauseIQ Implementation:** We do not use persistent EC2 servers. Our backend consists of stateless AWS Lambda functions. 
**Concrete Example:** Because Lambdas store zero state in memory, AWS can instantly terminate a frozen container and spin up a new one in a different Availability Zone. The system is inherently multi-AZ and highly available by default.

### 6. Load Balancing & Rate Limiting
**The Concept:** Distributing incoming traffic safely across backend resources.
**ClauseIQ Implementation:** AWS API Gateway acts as our load balancer and ingress controller.
**Concrete Example:** Before a request reaches our Python code, API Gateway handles SSL termination, CORS validation, and drops idle connections. It also enforces API-wide rate limits (e.g., 10,000 requests/second) to protect the backend from DDoS attacks.

### 7. API Design (RESTful)
**The Concept:** Standardized communication between frontend and backend.
**ClauseIQ Implementation:** We built a REST API using Python FastAPI.
**Concrete Example:** 
- `POST /agreements` (Mutates state: Uploads a document)
- `GET /agreements/{id}` (Idempotent: Fetches a document)
- We strictly return HTTP 429 for Rate Limit errors and HTTP 404 for Not Found.

### 8. Authentication (JWT & AWS Cognito)
**The Concept:** Verifying *who* the user is securely without managing passwords in our own database.
**ClauseIQ Implementation:** We use AWS Cognito to handle passwords and issue JSON Web Tokens (JWTs).
**Concrete Example:** In `api/auth.py`, we intercept the JWT header and mathematically verify its RSA signature against Amazon's public JWKS keys. The React frontend uses AWS Amplify to automatically refresh the token in the background before it expires.

### 9. Authorization (Tenant Isolation)
**The Concept:** Verifying *what* the authenticated user is allowed to access (preventing Broken Object Level Authorization).
**ClauseIQ Implementation:** Every database query strictly includes the authenticated user's ID.
**Concrete Example:** If User A tries to guess User B's agreement ID, the query `table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{guessed_id}"})` will return null, because the `PK` enforces strict tenant isolation at the database level.

### 10. Security (S3 Pre-signed URLs)
**The Concept:** Protecting private files from public internet access.
**ClauseIQ Implementation:** The S3 bucket containing the PDFs is entirely private. 
**Concrete Example:** When the React UI needs to display the PDF, our API generates a cryptographic Pre-signed URL. This URL grants temporary read access exactly to that specific file, and expires precisely 3600 seconds (1 hour) after creation.

### 11. Search (Semantic Vector Search)
**The Concept:** SQL `LIKE '%keyword%'` fails if the user searches for "termination" but the document says "cancellation".
**ClauseIQ Implementation:** For documents over 200k tokens, we use Vector Databases (Pinecone) and Retrieval-Augmented Generation (RAG).
**Concrete Example:** The document is chunked and converted into mathematical vectors (embeddings). When the user asks a question, we convert the question into a vector and use cosine similarity to find the most semantically relevant chunks, regardless of exact keyword matches.

### 12. Storage (Object Storage vs Database)
**The Concept:** Databases are designed for structured text, not large binary files.
**ClauseIQ Implementation:** Separation of concerns.
**Concrete Example:** The raw 50MB PDF file is saved directly to Amazon S3 (Object Storage). The database (DynamoDB) only stores a string reference to the file's location (`s3_key: "documents/123/file.pdf"`) and the extracted JSON metadata.

### 13. Monitoring & Observability
**The Concept:** Detecting failures in a distributed system.
**ClauseIQ Implementation:** Native integration with AWS CloudWatch.
**Concrete Example:** Because we use AWS Lambda, every `print()` statement in Python, every stack trace, and every memory consumption metric is automatically streamed to CloudWatch Logs and Dashboards without configuring external agents like Prometheus.

### 14. Deployment (CI/CD)
**The Concept:** Automating code deployments to prevent human error.
**ClauseIQ Implementation:** We use GitHub Actions and AWS SAM (Serverless Application Model).
**Concrete Example:** Pushing code to the `main` branch triggers a workflow that provisions a sterile Ubuntu environment, builds the Python dependencies, translates our `template.yaml` into CloudFormation, and safely updates the live AWS infrastructure.

### 15. Performance (Optimistic Updates)
**The Concept:** Eliminating perceived network latency on the frontend.
**ClauseIQ Implementation:** React Query `onMutate` callbacks.
**Concrete Example:** When a user clicks "Delete Agreement", we instantly remove the agreement from the React DOM before the API request finishes. If the API request fails, we roll back the UI cache. To the user, the app feels like it has 0ms latency.

### 16. Cost Optimization
**The Concept:** Architecting systems to minimize cloud bills.
**ClauseIQ Implementation:** A 100% Serverless architecture.
**Concrete Example:** If the application receives zero traffic at 3:00 AM, the AWS bill is exactly $0.00 because Lambda and API Gateway scale to zero. We also save 90% on AI costs using Context Caching during chat sessions.

### 17. System Design Trade-offs
**The Concept:** Engineering is about choosing the right compromise.
**ClauseIQ Implementation:** Long-Context LLMs vs RAG.
**Concrete Example:** RAG is significantly cheaper because it only sends 5 paragraphs to the AI. However, RAG fails to answer questions requiring synthesis across 50 different pages. We traded cost for accuracy by passing the entire document to a Long-Context LLM (Amazon Nova). We then mitigated the cost penalty by implementing AWS Prompt Caching.
