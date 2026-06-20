# Learnings

## AWS SAM (Serverless Application Model)

* **What it is:** A framework and CLI tool by AWS used to build, test, and deploy serverless applications using Infrastructure as Code (IaC).
* **Why we use it:** To automate the creation of all our AWS resources (Lambda, DynamoDB, S3) reliably and keep our infrastructure version-controlled alongside our Python code.
* **Why not alternatives (like Terraform):** SAM is purpose-built by AWS for serverless and requires less boilerplate configuration than Terraform or plain CloudFormation for this specific stack.
* **Internal Working:** The SAM CLI reads our `template.yaml`, transforms it into standard AWS CloudFormation syntax, packages our code, and deploys it as a CloudFormation stack.
* **Role in this project:** It acts as the single source of truth for our infrastructure. It connects our API to Lambda, sets up permissions, and provisions our database and queues.
* **Security Considerations:** We define specific IAM permissions (Policies) directly inside the template for each Lambda function to enforce the Principle of Least Privilege.
* **Interview Question:** "How do you manage infrastructure and deployments for your serverless applications?"
* **Interview-Ready Answer:** "I use Infrastructure as Code to ensure deployments are repeatable. Specifically, I use AWS SAM. I define all my resources—like Lambda functions, API Gateways, and DynamoDB tables—in a `template.yaml` file. SAM simplifies the verbose CloudFormation syntax, and the SAM CLI handles the packaging and deployment process seamlessly."

## AWS Lambda

* **What it is:** A serverless compute service that runs code in response to events (triggers) and automatically manages the computing resources required.
* **Why we use it:** It allows us to run our backend microservices without managing servers. We only pay for the compute time we actually consume.
* **Why not alternatives (like EC2 or Docker):** AWS EC2 requires us to manage the server operating system, manually handle scaling, and we pay for idle time. Lambda scales automatically and costs zero when idle.
* **Internal Working:** When an event occurs, AWS spins up a micro-container, executes our function, and returns the response. If the function is large, downloading the code and starting the environment takes time—this latency is called a "Cold Start".
* **Role in this project:** Our entire backend logic (`api`, `dispatcher`, `worker`) runs as separate Lambda functions.
* **Scalability Considerations:** Lambda scales automatically by running thousands of concurrent instances of the function if traffic spikes.
* **Limitations:** Functions have a maximum execution time limit (15 minutes) and strict deployment package size limits.
* **Interview Question:** "What is a cold start in AWS Lambda, and how do you mitigate it?"
* **Interview-Ready Answer:** "A cold start occurs when AWS spins up a new instance of a Lambda function to handle a request, which involves downloading the code and initializing the runtime. This adds latency to the request. To mitigate it, I ensure my deployment packages are as lightweight as possible by only installing the dependencies that specific function needs."

## GitHub Actions
* **What it is:** A CI/CD (Continuous Integration and Continuous Deployment) service built into GitHub. It runs scripts on virtual servers whenever you push code.
* **Why we use it:** To automate our testing and deployments so we don't have to manually run `sam build` and `sam deploy` on our laptops every time we change a single line of code.
* **Interview-Ready Answer:** "We implemented CI/CD using GitHub Actions. Our workflow automatically provisions an Ubuntu runner, configures AWS credentials securely via Secrets, installs SAM CLI, builds the assets, and deploys directly to our AWS environments based on the branch being pushed."

## LLM Tokens

* **What it is:** A token is the fundamental unit of data processed by a Large Language Model (LLM). It is not exactly a word. A single word might be broken into multiple tokens (e.g., "hamburger" -> "ham", "bur", "ger"). 
* **Why we use it:** We are billed by AI providers (like OpenAI or Anthropic) based on the number of tokens we send, not the number of words. Additionally, every AI model has a strict "Context Window Limit" measured in tokens.
* **Role in this project:** We use the `tiktoken` library in our backend to count the exact number of tokens in a legal document *before* we send it to Claude. This ensures we don't exceed the model's limit and helps us estimate costs.
* **Interview Question:** "What is the difference between word count and token count when working with LLMs?"
* **Interview-Ready Answer:** "A word is a human linguistic unit, but an LLM processes text using tokens, which are sub-word pieces of text created by a tokenizer algorithm. On average in English, 1 token is roughly equivalent to 4 characters or 0.75 of a word. Tracking token count is critical because API costs and context window limits are strictly enforced at the token level, not the word level."

## AWS API Gateway

* **What it is:** A fully managed AWS service that acts as the "front door" or a "toll booth" for your application's backend.
* **Why we use it:** To safely expose our Python Lambda functions to the public internet. It handles HTTPS encryption, blocks malicious traffic, and routes requests to the correct Lambda function.
* **Role in this project:** When a user visits `https://cnyls7k9yj.execute-api.../agreements`, they are actually hitting API Gateway, which then silently forwards the data to our Python API.
* **Interview-Ready Answer:** "We use AWS API Gateway as the entry point for our backend. Instead of exposing our Lambda functions directly to the internet, API Gateway sits in front of them, providing a secure, scalable HTTPS endpoint. It handles request routing, payload size limits, and CORS before the request ever reaches our application logic."

## Core Architectural Decision: Asynchronous Processing (SQS + Lambda)

In this project, the upload API is decoupled from the AI processing engine using an Amazon SQS Queue. This event-driven architecture solves three critical engineering challenges:

1. **API Gateway Timeouts**
   * **The Problem:** AWS API Gateway is configured to drop any connection that takes longer than 29 seconds. Because AI models usually take 30 to 60 seconds to process a large document, connecting our API directly to the AI would cause the request to time out and fail.
   * **The Solution:** The SQS queue allows our API to quickly offload the task. It drops a ticket in the queue and returns a "Success" response to the user in less than 1 second, bypassing the timeout limit entirely.

2. **Reliability (Decoupling)**
   * **The Problem:** If the AI service temporarily goes down or a network error occurs during a synchronous request, the entire process fails and the user's uploaded data is lost.
   * **The Solution:** By separating the upload from the processing, the system becomes resilient. If the AI worker fails, the task remains safely in the SQS queue. SQS will automatically retry the task later until it succeeds, ensuring zero data loss.

3. **Handling Traffic and Rate Limits (Horizontal Scaling)**
   * **The Problem:** AWS Lambda scales horizontally. If 100 people upload documents simultaneously, AWS automatically spins up 100 parallel Lambda instances to process them instantly. However, AWS Bedrock strictly limits how many AI requests we can make per minute (Rate Limits). If 10,000 users upload documents, AWS Lambda would try to spin up 10,000 workers at once, hitting the Bedrock limit and causing system-wide errors.
   * **The Solution:** SQS acts as a buffer to control the scaling. Even though Lambda *can* scale infinitely, we use the SQS queue to configure a "Concurrency Limit". We tell AWS: "Only allow a maximum of 50 Lambdas to run at a time." This ensures we always respect Bedrock's rate limits, while the excess tasks wait safely in the queue to be processed at a steady pace.

## 4. DynamoDB Single-Table Design
- **What it is:** Instead of creating multiple tables (like an Agreements table and a Clauses table) with foreign keys like in SQL, we put all related entities into one massive table. We distinguish them using prefixes in the Sort Key (e.g., SK = #ANALYSIS, SK = CLAUSE#123, SK = RISK#456).
- **Why we use it:** DynamoDB is a NoSQL database designed to scale infinitely. It does not get 'full' or slow down. If we query PK = AGREEMENT#xyz, DynamoDB can instantly return the agreement, the analysis, and all 50 clauses in a single 10-millisecond network request, even if the table has 10 billion rows.
- **Interview Answer:** 'We chose DynamoDB Single-Table Design to minimize network requests. By pre-joining our Analysis, Risk, and Clause entities under the same Partition Key, our frontend can fetch the entire dashboard dataset in a single sub-10ms query, which is crucial for perceived performance.'

## 5. Constrained Generation vs Free-form AI
- **The Problem:** If you let an LLM 'freely think' and answer a question like 'What document is this?', it might return `"NDA"` one day, and `"Non-Disclosure Agreement"` the next. While both are human-readable, this breaks frontend code that expects a consistent, exact string to render UI icons or filter databases.
- **The Solution (Constrained Generation):** We explicitly restrict the AI in the prompt to pick from a hardcoded list (e.g., `["employment", "nda", "rental"]`). 
- **Interview Answer:** 'When integrating LLMs into a structured backend, I rely on Constrained Generation. By forcing the AI to map its semantic understanding to a strict set of Enums, I ensure the output is perfectly predictable and can be safely consumed by the frontend and database without formatting crashes.'

## Bedrock Knowledge Bases & Pinecone Serverless
- **What it is:** A managed RAG (Retrieval-Augmented Generation) pipeline by AWS. Pinecone is a highly scalable vector database.
- **Why we use it:** To support analyzing and querying large documents (>100k tokens) that cannot fit into an LLM's prompt window.
- **Role in this project:** Bedrock automatically chunks our S3 document, embeds it into math vectors, and stores it in Pinecone. During analysis or Q&A, we use  edrock-agent-runtime.retrieve() to fetch only the relevant text chunks.
- **Interview Answer:** "For large enterprise agreements exceeding 100k tokens, we implemented a hybrid AI strategy. We use AWS Bedrock Knowledge Bases to automate the chunking and embedding pipeline, backed by Pinecone Serverless. When a user asks a question, we execute a semantic vector search to retrieve the most relevant text chunks and inject them into the LLM prompt, ensuring high accuracy while respecting token limits."

## AWS Cognito (User Pools vs Client IDs)
- **What it is:** AWS Cognito is a managed identity service for handling user sign-up, sign-in, and access control.
- **The API URL:** The web address where our Python backend lives. When the frontend needs data, it sends a network request to this address.
- **The User Pool ID:** The ID of the database in AWS that physically stores the user emails, passwords, and profile data.
- **The App Client ID:** A specific configuration key that gives our React app permission to securely log users into that User Pool database.
- **Interview Answer:** "For authentication, we used AWS Cognito. We provisioned a Cognito User Pool to securely store user credentials. Our React frontend uses a specific App Client ID to communicate with this User Pool. Once authenticated, Cognito returns a JWT (JSON Web Token), which the frontend attaches to requests sent to our API Gateway URL to access protected endpoints."

## React State vs Browser Local Storage
- **The Concept:** When a user logs in via AWS Amplify, the JWT token is saved permanently in the browser's Local Storage. However, React is completely blind to Local Storage changes.
- **The Bug (Silent Kick-out):** If a user logs in, the token hits Local Storage, but React's `user` variable stays `null`. If you redirect the user to a protected page immediately, React will kick them out because it thinks they aren't logged in.
- **The Solution:** We must build a bridge (like `AuthContext.tsx`). After `signIn()`, we manually call a function (`checkUser()`) that reaches into Local Storage, grabs the new token, and saves it into a React `useState` variable. Because `useState` changed, React realizes the user is logged in and allows the redirect.

## 27. Optimistic Updates (Frontend UX Pattern)
- **What it is:** A UI pattern where the frontend assumes a server request (like a Delete or Like button) will succeed and updates the screen instantly, before the server actually responds.
- **Why we use it:** To completely eliminate "network latency" from the user's perspective, making the app feel incredibly fast (0ms response time).
- **What to say in an interview:** "To improve perceived performance, I implemented Optimistic Updates using React Query's `onMutate` callback. When a user deletes a document, the item is instantly removed from the UI cache. In the background, the API request executes. If the request fails, React Query automatically rolls back the cache to its previous state, ensuring UI consistency without sacrificing speed."

## 28. Native Context Caching (Prompt Caching)
- **What it is:** A feature provided by modern LLM APIs (like Amazon Bedrock and Anthropic) that allows you to "freeze" a large block of text (like a 1,000-page document) in the provider's ultra-fast RAM memory for a short period of time (e.g., 5 minutes). 
- **The Problem:** LLM APIs are stateless. If a user is chatting with a 1,000-page document, the application normally has to send the *entire document* over the internet for every single question. This incurs massive latency (e.g., 10+ seconds of reading time) and costs money for every input token.
- **The Solution:** By splitting the prompt and injecting an AWS `cachePoint` tag after the document text, AWS caches the document. When the user asks a second question within 5 minutes, AWS skips reading the document entirely.
- **When is it useful?** It is essential for any application that requires multi-turn conversations over massive documents (e.g., Legal PDF Chatbots, Coding Copilots, Document Analyzers). It is arguably the most critical optimization for scaling a Long-Context LLM app to 10,000 users.
- **What to say in an interview:** "To scale our conversational AI for 10,000 users, I utilized AWS Bedrock Context Caching. Instead of relying on a complex RAG pipeline, I leveraged Long-Context models to maximize accuracy. However, to mitigate the latency and cost of stateless API calls, I separated the document payload into a System Prompt and appended an AWS `cachePoint`. This reduced subsequent query latency by over 80% and input token costs by 90%, providing a sub-second chat experience over massive documents."

## 29. Modern System Design (How ClauseIQ Scales)
When asked how to scale a project for millions of users, ClauseIQ natively solves almost every classic system design challenge because it is built on an **AWS Serverless Architecture**. 

1. **Stateless Servers & Horizontal Scaling:** We do not use EC2 servers. Our backend runs on AWS Lambda. Lambda functions are perfectly stateless and scale horizontally automatically. If 10,000 users hit the API, AWS spins up 10,000 parallel Lambda containers instantly.
2. **Load Balancing & Rate Limiting:** AWS API Gateway acts as our intelligent front door (Load Balancer). It routes traffic, enforces rate limits, and drops idle connections before they ever reach our code.
3. **Asynchronous Processing:** AI tasks take 30+ seconds and would crash a normal synchronous API. We decoupled the system using **AWS SQS** (Message Queue) and a background Worker Lambda. The API responds instantly, and the worker processes the queue independently.
4. **Database Scaling & Efficient Queries:** Instead of Postgres + Connection Pools (which crash under high load), we use DynamoDB. DynamoDB is an HTTP-based NoSQL database that auto-shards data. By using **Single-Table Design**, we eliminated the "N+1 query problem"; we can fetch an Agreement and all its 50 Clauses in a single sub-10ms query.
5. **Caching:** Instead of Redis (which is overkill when DynamoDB already responds in 5ms), we implemented the hardest form of caching: **LLM Context Caching** in AWS Bedrock.
6. **Global CDN:** Our React frontend is compiled into static assets and deployed to a global CDN (AWS CloudFront / Amplify), meaning the UI loads instantly for users anywhere in the world.
7. **Monitoring:** All logs, metrics, and error rates are automatically ingested and monitored by AWS CloudWatch without any custom setup.

**Example System Design Interview Answer:**
> *"To support massive concurrent traffic, I architected my backend completely serverless. I placed stateless AWS Lambda functions behind an API Gateway to handle instant horizontal scaling and rate limiting. To prevent AI latency from blocking the main thread, I decoupled the heavy processing into an event-driven architecture using an SQS message queue and background workers. For the data layer, I used DynamoDB with a Single-Table Design, which auto-shards and eliminates the N+1 query problem, providing sub-10ms reads. Finally, I optimized the LLM costs by implementing Native Context Caching, and deployed the frontend to a global CDN."*