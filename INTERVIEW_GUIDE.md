# ClauseIQ: System Design Interview Guide

This document maps the top 20 most common System Design interview questions directly to the architecture of ClauseIQ. Studying this guide will prove to interviewers that you understand how to build and scale production-ready applications.

### 1. Database Design (Why DynamoDB?)
*   **Question:** Why NoSQL over SQL?
*   **Answer:** "I chose **DynamoDB** because ClauseIQ requires high-concurrency document reads with low latency. Instead of complex SQL joins, I used a **Single-Table Design**. By storing Agreements, Risks, and Clauses under a single Partition Key (`PK=USER#123`), I can fetch an entire dashboard of data in a single sub-10ms network request. DynamoDB inherently auto-shards across partitions, ensuring infinite scalability."

### 2. Caching (Why not Redis?)
*   **Question:** Your app gets 50k requests/min. What do you cache?
*   **Answer:** "For the data layer, DynamoDB already responds in single-digit milliseconds, making Redis overkill and an unnecessary source of cache-invalidation bugs. Instead, I focused caching on the most expensive bottleneck: the AI. I implemented **LLM Native Context Caching** in AWS Bedrock, freezing the 1,000-page document in AWS RAM. This reduced AI latency by 80% and costs by 90% without needing a separate Redis cluster."

### 3. Asynchronous Processing
*   **Question:** What if a task takes 60 seconds?
*   **Answer:** "To prevent API Gateway timeouts (29s limit), I built an **event-driven architecture**. When a user uploads a PDF, the API instantly returns a success message and drops a task into an **Amazon SQS Queue**. A background Lambda Worker independently pulls from the queue, processes the AI analysis, and updates the database, ensuring the main thread is never blocked."

### 4. Consistency & Race Conditions
*   **Question:** How do you prevent overselling or race conditions?
*   **Answer:** "I use **Optimistic Locking** via DynamoDB's `ConditionExpression`. For example, in my Rate Limiter, if a user's bot sends 10 concurrent messages at the exact same millisecond, DynamoDB locks the row at the hardware level and only allows the first update to succeed, throwing a `ConditionalCheckFailedException` for the others. This guarantees atomic thread safety."

### 5. High Availability & Fault Tolerance
*   **Question:** What if a server crashes?
*   **Answer:** "My entire backend is **Serverless**. AWS Lambda and DynamoDB inherently run across multiple Availability Zones (data centers). If a physical server dies, AWS reroutes the container instantly. If the AI provider (Bedrock) goes down, my SQS Queue safely holds the messages and automatically retries them later, ensuring zero data loss."

### 6. Load Balancing
*   **Question:** How is traffic distributed?
*   **Answer:** "I use **AWS API Gateway** as a fully managed load balancer. It acts as the front door, intelligently routing traffic to thousands of parallel Lambda containers while automatically dropping idle connections."

### 7. API Design
*   **Question:** How did you design your API?
*   **Answer:** "I built a standard **REST API** using FastAPI. I strictly used `POST` for mutations (uploading, chatting) and `GET` for fetching data. I ensured standard HTTP status codes (e.g., `429` for rate limits, `409` for conflict if the analysis isn't finished yet)."

### 8. Authentication & Authorization
*   **Question:** How do you secure user data?
*   **Answer:** "For authentication, I use **AWS Cognito** which issues secure JWT tokens. The React frontend handles **Refresh Tokens** automatically in the background so users are never unexpectedly logged out. For authorization, I strictly scope all DynamoDB queries using the user's cryptographically verified ID (`PK=USER#<id>`). This prevents **BOLA** (Broken Object Level Authorization), guaranteeing that User A can never access User B's documents."

### 9. Security
*   **Question:** How do you handle file security?
*   **Answer:** "I never expose public S3 URLs. Instead, my API generates cryptographic **S3 Pre-signed URLs** that are strictly scoped to the exact document file path and automatically expire after 1 hour (`ExpiresIn=3600`). I also implemented a DynamoDB-backed **Rate Limiter** to prevent DDoS-style spam on the AI endpoints."

### 10. CDN (Content Delivery Network)
*   **Question:** What if users worldwide access your app?
*   **Answer:** "My React frontend is compiled into static assets and deployed to **AWS CloudFront** (Amazon's global CDN). A user in London downloads the UI from a server in London, ensuring instant page loads globally."

### 11. Search
*   **Question:** How do you search through massive documents?
*   **Answer:** "Standard SQL `LIKE '%abc%'` is useless for finding legal nuances. I implemented **Vector Search** using Pinecone. By turning the text into mathematical embeddings, the system understands the *semantic meaning* of the query, allowing it to find relevant clauses even if the exact keywords don't match."

### 12. Storage
*   **Question:** Where do images/PDFs go?
*   **Answer:** "I strictly separate concerns: raw PDF files are stored in **Amazon S3**, and only the metadata and extracted text strings are stored in **DynamoDB**. Storing binary files in a database is an expensive anti-pattern."

### 13. Monitoring
*   **Question:** How do you detect problems?
*   **Answer:** "Because I use AWS Serverless, all Lambda execution logs, cold start metrics, and API Gateway error rates (like 500s or 429s) are automatically ingested into **AWS CloudWatch**."

### 14. Deployment
*   **Question:** How is your project deployed?
*   **Answer:** "I implemented a full **CI/CD pipeline using GitHub Actions**. Whenever I push to the `main` branch, the workflow automatically provisions an Ubuntu runner, configures AWS credentials via Secrets, runs `sam build`, and deploys the infrastructure as code (IaC) to AWS using the SAM CLI."

### 15. Performance
*   **Question:** How do you reduce response time?
*   **Answer:** "On the backend, I eliminate the N+1 database problem using DynamoDB Single-Table Design. On the frontend, I use **React Query Optimistic Updates**. When a user deletes a file, the UI updates instantly (0ms latency), assuming the server request will succeed, masking any network latency."

### 16. Cost Optimization
*   **Question:** How do you keep AWS bills low?
*   **Answer:** "My architecture scales to zero. I only pay for the exact milliseconds my Lambda functions run. I also optimized the most expensive part (LLM tokens) by implementing **Native Context Caching**, which cuts AI costs by 90% during multi-turn chats."

### 17. Trade-offs (The Senior Level Question)
*   **Question:** What architectural trade-offs did you make?
*   **Answer:** "The biggest trade-off was choosing **Long-Context LLMs over standard RAG**. RAG is cheaper, but it often misses information spread across multiple pages. By passing the full document into a Long-Context model (like Nova Lite), I maximized accuracy. To offset the high latency and cost of this trade-off, I implemented **AWS Prompt Caching**. I traded slightly more complex prompt engineering for massively superior semantic accuracy."
