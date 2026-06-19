# ClauseIQ — Day-by-Day Build Plan

## How to Use This Plan

Hand the LLM **this document + PRD v9** at the start of each day. Say:

> "We are on Day X. Follow the Day X instructions exactly. Reference PRD v9 for all specs, schemas, and code snippets."

The LLM must not jump ahead. Each day builds on the previous day's output exactly.

---

## Day 1 — Project Scaffold + AWS Infrastructure Bootstrap

**Goal:** Repo exists, SAM template is live, all AWS resources are provisioned, local dev works.

### 1.1 Create repo and folder structure
Create the following layout exactly as specified in PRD §21:
```
clauseiq/
├── template.yaml
├── samconfig.toml
├── api/
│   ├── main.py
│   ├── routers/
│   ├── auth.py
│   └── requirements.txt
├── dispatcher/
│   ├── dispatcher.py
│   └── requirements.txt
├── worker/
│   ├── worker.py
│   └── requirements.txt
├── user_initializer/
│   ├── user_initializer.py
│   └── requirements.txt
└── frontend/
    └── (empty for now)
```

### 1.2 Write template.yaml

Write the complete `template.yaml` below exactly as shown. Do not paraphrase or abbreviate — copy it verbatim.

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, prod]

Globals:
  Function:
    Runtime: python3.12
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: !Ref DynamoDBTable
        S3_BUCKET_NAME: !Ref DocumentsBucket
        COGNITO_USER_POOL_ID: !Ref UserPool
        COGNITO_APP_CLIENT_ID: !Ref UserPoolClient
        SQS_QUEUE_URL: !Ref AnalysisQueue
        BEDROCK_REGION: "us-east-1"   # Nova Lite only available in us-east-1 — never use !Ref AWS::Region here
        ENVIRONMENT: !Ref Environment

Resources:

  # ── API Lambda (FastAPI) ──
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      CodeUri: ./api/
      MemorySize: 256
      Timeout: 30
      Policies:
        - Statement:
            - Effect: Allow
              Action: [dynamodb:GetItem, dynamodb:PutItem, dynamodb:UpdateItem, dynamodb:DeleteItem, dynamodb:Query, dynamodb:BatchWriteItem]
              Resource: [!GetAtt DynamoDBTable.Arn, !Sub "${DynamoDBTable.Arn}/index/*"]
            - Effect: Allow
              Action: [s3:GetObject, s3:PutObject, s3:DeleteObject]
              Resource: !Sub "${DocumentsBucket.Arn}/*"
            - Effect: Allow
              Action: [bedrock:InvokeModel, bedrock-agent-runtime:Retrieve]
              Resource: "*"
      Events:
        Api:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi

  # ── Dispatcher Lambda (S3 event → SQS) ──
  DispatcherFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: dispatcher.handler
      CodeUri: ./dispatcher/
      MemorySize: 128
      Timeout: 10
      Policies:
        - Statement:
            - Effect: Allow
              Action: [dynamodb:GetItem]
              Resource: !GetAtt DynamoDBTable.Arn
            - Effect: Allow
              Action: [sqs:SendMessage]
              Resource: !GetAtt AnalysisQueue.Arn
      Events:
        S3Upload:
          Type: S3
          Properties:
            Bucket: !Ref DocumentsBucket
            Events: s3:ObjectCreated:*
            Filter:
              S3Key:
                Rules:
                  - Name: prefix
                    Value: documents/

  # ── AI Worker Lambda (SQS trigger) ──
  AiWorkerFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: worker.handler
      CodeUri: ./worker/
      MemorySize: 1024
      Timeout: 600
      Policies:
        - Statement:
            - Effect: Allow
              Action: [dynamodb:GetItem, dynamodb:PutItem, dynamodb:UpdateItem, dynamodb:Query, dynamodb:BatchWriteItem]
              Resource: [!GetAtt DynamoDBTable.Arn, !Sub "${DynamoDBTable.Arn}/index/*"]
            - Effect: Allow
              Action: [s3:GetObject]
              Resource: !Sub "${DocumentsBucket.Arn}/*"
            - Effect: Allow
              Action: [bedrock:InvokeModel, bedrock-agent-runtime:Retrieve]
              Resource: "*"
            - Effect: Allow
              Action: [bedrock-agent:CreateKnowledgeBase, bedrock-agent:DeleteKnowledgeBase, bedrock-agent:CreateDataSource, bedrock-agent:StartIngestionJob, bedrock-agent:GetIngestionJob]
              Resource: "*"
            - Effect: Allow
              Action: [iam:PassRole]
              Resource: !GetAtt BedrockKBServiceRole.Arn
            - Effect: Allow
              Action: [secretsmanager:GetSecretValue]
              Resource: !Ref PineconeSecret  # needed by bedrock_kb.py to fetch Pinecone API key + index host
      Environment:
        Variables:
          BEDROCK_KB_ROLE_ARN: !GetAtt BedrockKBServiceRole.Arn
          PINECONE_SECRET_ARN: !Ref PineconeSecret  # ARN fetched at runtime by bedrock_kb.py via os.environ
      Events:
        SQSTrigger:
          Type: SQS
          Properties:
            Queue: !GetAtt AnalysisQueue.Arn
            BatchSize: 1

  # ── User Initializer Lambda (Cognito Post-Confirmation trigger) ──
  UserInitializerFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: user_initializer.handler
      CodeUri: ./user_initializer/
      MemorySize: 128
      Timeout: 10
      Policies:
        - Statement:
            - Effect: Allow
              Action: [dynamodb:PutItem]
              Resource: !GetAtt DynamoDBTable.Arn

  # ── S3 Bucket (private) ──
  DocumentsBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub clauseiq-documents-${Environment}-${AWS::AccountId}
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  # Bucket policy allowing Bedrock to read documents for KB ingestion
  DocumentsBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref DocumentsBucket
      PolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: bedrock.amazonaws.com
            Action: s3:GetObject
            Resource: !Sub ${DocumentsBucket.Arn}/*

  # ── S3 Bucket (frontend static files — private, served via CloudFront) ──
  FrontendBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub clauseiq-frontend-${Environment}-${AWS::AccountId}
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  # CloudFront Origin Access Control — lets CloudFront read from the private FrontendBucket
  FrontendOAC:
    Type: AWS::CloudFront::OriginAccessControl
    Properties:
      OriginAccessControlConfig:
        Name: !Sub clauseiq-frontend-oac-${Environment}
        OriginAccessControlOriginType: s3
        SigningBehavior: always
        SigningProtocol: sigv4

  # Bucket policy granting CloudFront (via OAC) read access to frontend files
  FrontendBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref FrontendBucket
      PolicyDocument:
        Statement:
          - Effect: Allow
            Principal:
              Service: cloudfront.amazonaws.com
            Action: s3:GetObject
            Resource: !Sub ${FrontendBucket.Arn}/*
            Condition:
              StringEquals:
                AWS:SourceArn: !Sub arn:aws:cloudfront::${AWS::AccountId}:distribution/${FrontendDistribution}

  # CloudFront distribution — serves React frontend with HTTPS and global CDN
  FrontendDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        DefaultRootObject: index.html
        Origins:
          - Id: FrontendS3Origin
            DomainName: !GetAtt FrontendBucket.RegionalDomainName
            OriginAccessControlId: !GetAtt FrontendOAC.Id
            S3OriginConfig: {}
        DefaultCacheBehavior:
          TargetOriginId: FrontendS3Origin
          ViewerProtocolPolicy: redirect-to-https
          CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6  # AWS managed CachingOptimized policy
          AllowedMethods: [GET, HEAD]
        # SPA routing — return index.html for 403/404 so React Router handles the path
        CustomErrorResponses:
          - ErrorCode: 403
            ResponseCode: 200
            ResponsePagePath: /index.html
          - ErrorCode: 404
            ResponseCode: 200
            ResponsePagePath: /index.html
        HttpVersion: http2
        PriceClass: PriceClass_100  # US/Europe/Asia — cheapest tier covering main markets

  # Pinecone credentials — store {"api_key": "pc-xxxx", "index_host": "https://clauseiq-xxxxx.svc.pinecone.io"}
  # after creating your serverless index on pinecone.io (dimension: 1536, metric: cosine, cloud: AWS, region: us-east-1)
  PineconeSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub clauseiq-pinecone-${Environment}
      Description: Pinecone API key and index host URL for Bedrock KB vector storage

  # ── DynamoDB Table (single table, PAY_PER_REQUEST) ──
  DynamoDBTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub clauseiq-${Environment}
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: PK
          AttributeType: S
        - AttributeName: SK
          AttributeType: S
        - AttributeName: GSI1PK
          AttributeType: S
      KeySchema:
        - AttributeName: PK
          KeyType: HASH
        - AttributeName: SK
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: GSI1
          KeySchema:
            - AttributeName: GSI1PK
              KeyType: HASH
          Projection:
            ProjectionType: ALL

  # ── SQS Queue + Dead Letter Queue ──
  AnalysisQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub clauseiq-analysis-${Environment}
      VisibilityTimeout: 610
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt AnalysisDLQ.Arn
        maxReceiveCount: 3

  AnalysisDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub clauseiq-analysis-dlq-${Environment}

  # ── IAM Role for Bedrock Knowledge Base ──
  # Bedrock assumes this role to read documents from S3 during KB ingestion.
  # AI Worker passes this ARN when calling bedrock-agent:CreateKnowledgeBase.
  BedrockKBServiceRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub clauseiq-bedrock-kb-${Environment}
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: bedrock.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: BedrockKBReadS3
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: [s3:GetObject, s3:ListBucket]
                Resource:
                  - !GetAtt DocumentsBucket.Arn
                  - !Sub "${DocumentsBucket.Arn}/*"

  # ── Cognito User Pool ──
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub clauseiq-${Environment}
      AutoVerifiedAttributes:
        - email
      UsernameAttributes:
        - email
      LambdaConfig:
        PostConfirmation: !GetAtt UserInitializerFunction.Arn

  # Permission for Cognito to invoke User Initializer
  CognitoUserInitializerPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt UserInitializerFunction.Arn
      Action: lambda:InvokeFunction
      Principal: cognito-idp.amazonaws.com
      SourceArn: !GetAtt UserPool.Arn

  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      ClientName: !Sub clauseiq-client-${Environment}
      UserPoolId: !Ref UserPool
      GenerateSecret: false
      ExplicitAuthFlows:
        - ALLOW_USER_SRP_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH

  # ── API Gateway HTTP API ──
  HttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins:
          - https://clauseiq.com
          - http://localhost:5173
        AllowMethods:
          - GET
          - POST
          - DELETE
        AllowHeaders:
          - Authorization
          - Content-Type

Outputs:
  ApiUrl:
    Value: !Sub https://${HttpApi}.execute-api.${AWS::Region}.amazonaws.com
  UserPoolId:
    Value: !Ref UserPool
  UserPoolClientId:
    Value: !Ref UserPoolClient
  DynamoDBTableName:
    Value: !Ref DynamoDBTable
  DocumentsBucketName:
    Value: !Ref DocumentsBucket
  FrontendBucketName:
    Value: !Ref FrontendBucket
  CloudFrontURL:
    Value: !Sub https://${FrontendDistribution.DomainName}
  CloudFrontDistributionId:
    Value: !Ref FrontendDistribution
  PineconeSecretArn:
    Value: !Ref PineconeSecret
```

**Critical notes on this template:**
- `GSI1PK` is the attribute written on Agreement entities as `AGREEMENT#<agreementId>` — used to look up `userId` for ownership checks. When writing an Agreement to DynamoDB, always set `GSI1PK = f"AGREEMENT#{agreement_id}"` on the item.
- `VisibilityTimeout: 610` on SQS must be > Lambda timeout (600s) — otherwise SQS re-delivers the message while the worker is still running.
- The `CognitoUserInitializerPermission` resource is required — without it Cognito cannot invoke the Lambda and signups silently fail at the Post-Confirmation step.
- `DocumentsBucketPolicy` is required for Day 6 Bedrock KB ingestion — add it now so it's in place when needed.
- **Every Lambda has an explicit `Policies` block.** SAM's default execution role grants only CloudWatch Logs write access — nothing else. Without these policies, every call to DynamoDB, S3, SQS, or Bedrock throws `AccessDeniedException`. Do not remove or reduce these grants.
- **`BedrockKBServiceRole`** is the IAM role Bedrock assumes when ingesting documents into a Knowledge Base on Day 6. The AI Worker passes this ARN (via `BEDROCK_KB_ROLE_ARN` env var, injected at function level) when calling `bedrock-agent:CreateKnowledgeBase`. The `iam:PassRole` grant on the AI Worker authorises delegating this role to Bedrock. Without this role, KB creation fails with an IAM error before any Bedrock API is even reached.

### 1.3 Write samconfig.toml
Implement exactly as specified in PRD §21. Two environments: `dev` and `prod`. Region: `ap-south-1`.

### 1.4 Write stub Lambda handlers
Each Lambda needs a working stub that returns a valid response — no logic yet, just enough to deploy:

**api/main.py:**
```python
from fastapi import FastAPI
from mangum import Mangum
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

handler = Mangum(app)
```

**api/requirements.txt:**
```
fastapi
mangum
python-jose[cryptography]
boto3
PyMuPDF
python-docx
tiktoken
requests
```

> **Why `requests`:** `auth.py` uses `requests.get()` to fetch the Cognito JWKS endpoint at Lambda cold start. `requests` is not in the Python standard library — omitting it causes `ImportError` the first time any authenticated endpoint is hit.

**dispatcher/dispatcher.py:**
```python
def handler(event, context):
    print("Dispatcher stub called", event)
    return {"statusCode": 200}
```

**worker/worker.py:**
```python
def handler(event, context):
    print("Worker stub called", event)
    return {"statusCode": 200}
```

**user_initializer/user_initializer.py:**
```python
def handler(event, context):
    print("User initializer stub called", event)
    return event
```

Each `requirements.txt` for dispatcher, worker, user_initializer: `boto3` only for now.

### 1.5 Deploy to dev

**Platform note — IMPORTANT:** PyMuPDF (`fitz`) contains compiled C extensions that must match the Lambda Linux runtime. If you are running on **Mac or Windows**, always use `--use-container` for every `sam build` command — otherwise the binaries will be wrong and Lambda will crash with `Runtime.ImportModuleError` on the first PDF upload.

**BEDROCK_REGION note — CRITICAL:** The `BEDROCK_REGION` global env var in `template.yaml` must be hardcoded to `"us-east-1"` — never `!Ref AWS::Region`. Amazon Nova Lite is only available in `us-east-1`, `us-west-2`, and `eu-west-1`. If your primary stack deploys to `ap-south-1` and you use `!Ref AWS::Region`, every Nova call will fail with a `ModelNotFound` error. Cross-region Bedrock calls add ~50ms latency and are fully supported.

```bash
# Mac / Windows:
sam build --parallel --use-container
# Linux (including GitHub Actions ubuntu-latest runner):
sam build --parallel

sam deploy --config-env dev --guided   # first time only — guided prompts
```

After the first `sam deploy --guided` completes, note the **Outputs** printed to the terminal. You will need these values throughout the project:
- `ApiUrl` → your backend base URL (used as `VITE_API_BASE_URL` in frontend `.env.local` on Day 7)
- `UserPoolId` → paste into `VITE_COGNITO_USER_POOL_ID` on Day 7
- `UserPoolClientId` → paste into `VITE_COGNITO_APP_CLIENT_ID` on Day 7
- `DynamoDBTableName` → used in `env.json` for local SAM dev
- `DocumentsBucketName` → used in `env.json` for local SAM dev

Save these somewhere; `aws cloudformation describe-stacks --stack-name clauseiq-dev --query "Stacks[0].Outputs"` retrieves them again if needed.

Verify in AWS console:
- All 4 Lambda functions exist
- DynamoDB table exists with correct GSI
- S3 bucket exists
- SQS queue + DLQ exist
- Cognito User Pool exists
- API Gateway endpoint responds to GET /health

### 1.6 Set up GitHub repo and secrets
- Push to GitHub
- Add secrets per PRD §22: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `SAM_ARTIFACTS_BUCKET`
- Add backend CI/CD workflow file: `.github/workflows/deploy-backend.yml` (exact content from PRD §22)

**Day 1 done when:** `GET https://<api-gateway-url>/health` returns `{"status": "ok"}` and GitHub Actions deploy succeeds on push to `dev`.

**Critical checklist before closing Day 1:**
- [ ] `CognitoUserInitializerPermission` resource is present in `template.yaml` — without it Cognito cannot fire the Post-Confirmation trigger and every signup silently fails at Day 2 testing. Verify it exists in the deployed CloudFormation stack under Resources.
- [ ] `DocumentsBucketPolicy` resource is present in `template.yaml` — required for Bedrock KB ingestion on Day 6.
- [ ] `FrontendBucket`, `FrontendOAC`, `FrontendBucketPolicy`, `FrontendDistribution`, and `PineconeSecret` resources are all present in `template.yaml`.
- [ ] `AiWorkerFunction` has `PINECONE_SECRET_ARN: !Ref PineconeSecret` in its `Environment.Variables` block and `secretsmanager:GetSecretValue` on `!Ref PineconeSecret` in its `Policies` block — both are required for Day 6 `bedrock_kb.py` to fetch Pinecone credentials at runtime.
- [ ] `BEDROCK_REGION` is hardcoded to `"us-east-1"` in Globals — not `!Ref AWS::Region`.
- [ ] SQS `VisibilityTimeout` is 610 (must be > Lambda timeout of 600s).
- [ ] SAM Outputs are saved (ApiUrl, UserPoolId, UserPoolClientId, DynamoDBTableName, DocumentsBucketName, FrontendBucketName, CloudFrontURL, CloudFrontDistributionId, PineconeSecretArn).

---

## Day 2 — Auth: Cognito + JWT Validation + User Initializer

**Goal:** Users can sign up, verify email, log in. JWT validation works in FastAPI. User record is created in DynamoDB on signup.

### 2.1 Implement User Initializer Lambda
File: `user_initializer/user_initializer.py`

Triggered by Cognito Post-Confirmation event. Write User entity to DynamoDB per PRD §10.11:
```python
import boto3, os
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def handler(event, context):
    user_attrs = {a["Name"]: a["Value"] for a in event["request"]["userAttributes"]}
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
```

### 2.2 Implement JWT validation in FastAPI
File: `api/auth.py`

Write this file exactly as shown:

```python
import os
import requests
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"

# Cache JWKS at cold start — never re-fetch per request
_jwks = None

def get_jwks():
    global _jwks
    if _jwks is None:
        _jwks = requests.get(JWKS_URL).json()["keys"]
    return _jwks

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        # Decode header only (unverified) to get kid
        headers = jwt.get_unverified_headers(token)
        kid = headers["kid"]

        # Find matching public key
        jwks = get_jwks()
        key = next((k for k in jwks if k["kid"] == kid), None)
        if key is None:
            raise HTTPException(status_code=401, detail="Public key not found")

        # Verify and decode
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=APP_CLIENT_ID,
            options={"verify_exp": True}
        )

        # Validate claims
        expected_iss = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
        if claims.get("iss") != expected_iss:
            raise HTTPException(status_code=401, detail="Invalid issuer")
        if claims.get("token_use") != "id":
            raise HTTPException(status_code=401, detail="Not an ID token")

        return {"userId": claims["sub"], "email": claims.get("email", "")}

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
```

### 2.3 Add auth dependency to FastAPI
File: `api/main.py`

Add a protected test endpoint:
```python
@app.get("/me")
def me(user=Depends(get_current_user)):
    return {"userId": user["userId"]}
```

### 2.4 Configure CORS
In `api/main.py`, add FastAPI CORS middleware:
- Allow origins: `https://clauseiq.com` and `http://localhost:5173`
- Allow methods: GET, POST, DELETE
- Allow headers: Authorization, Content-Type

### 2.5 Deploy and test
```bash
# Mac/Windows: sam build --parallel --use-container && sam deploy --config-env dev
sam build --parallel && sam deploy --config-env dev
```

Test manually:
1. Sign up via Cognito hosted UI or AWS console
2. Verify email
3. Check DynamoDB — User entity must exist with correct PK/SK
4. Get ID token from Cognito
5. Call `GET /me` with `Authorization: Bearer <token>` — must return userId
6. Call `GET /me` without token — must return 401

**Day 2 done when:** Signup creates a User record in DynamoDB, and `GET /me` with a valid token returns the userId.

---

## Day 3 — Backend: Upload Endpoint + Text Extraction + S3 + DynamoDB

**Goal:** `POST /agreements` works end to end. Files are extracted, concatenated, hashed, stored in S3, and an Agreement record is created in DynamoDB.

### 3.1 Implement text extraction utilities
File: `api/utils/extraction.py`

Implement three functions:
- `extract_pdf(file_bytes: bytes) -> str` — PyMuPDF page-by-page with `[PAGE N]` markers per PRD §10.4
- `extract_docx(file_bytes: bytes) -> str` — python-docx paragraph extraction
- `concatenate_files(files: list[dict]) -> str` — joins extracted texts with `[FILE: filename]` separators per PRD §10.3a

For single file or pasted text: return text as-is (no `[FILE:]` wrapper needed).
For multiple files: wrap each with `[FILE: filename]\n` before concatenating.

### 3.2 Implement token counting + SHA-256 hashing
File: `api/utils/tokens.py`
- `count_tokens(text: str) -> int` — tiktoken `cl100k_base` encoding
- `compute_hash(text: str) -> str` — SHA-256 of UTF-8 encoded text

### 3.3 Implement DynamoDB helpers
File: `api/utils/dynamo.py`

```python
import boto3, os
from datetime import datetime, timezone

def get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def create_agreement(user_id, agreement_id, title, file_count, source_filenames,
                     token_count, document_hash, s3_key) -> None:
    table = get_table()
    table.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": f"AGREEMENT#{agreement_id}",
        # GSI-1: lets any endpoint look up userId from just an agreementId
        "GSI1PK": f"AGREEMENT#{agreement_id}",
        "agreementId": agreement_id,
        "userId": user_id,
        "title": title,
        "s3_key": s3_key,
        "status": "UPLOADED",
        "document_hash": document_hash,
        "token_count": token_count,
        "file_count": file_count,                        # int or None
        "source_filenames": source_filenames,            # list[str] or None
        "document_types": None,                          # set by AI Worker on COMPLETED
        "overall_risk": None,                            # set by AI Worker on COMPLETED
        "bedrock_kb_id": None,                           # set by AI Worker if RAG path
        "created_at": datetime.now(timezone.utc).isoformat()
    })

def get_hash_index(sha256_hash: str) -> dict | None:
    table = get_table()
    response = table.get_item(Key={"PK": f"HASH#{sha256_hash}", "SK": "#METADATA"})
    return response.get("Item")
```

**Why `GSI1PK` must be set here:** The GSI-1 index (`GSI1PK` → Agreement item) is how every API endpoint verifies ownership. If you forget to set `GSI1PK` when creating the Agreement, all ownership checks will fail with a 403 because the GSI lookup returns nothing.

### 3.4 Implement POST /agreements
File: `api/routers/agreements.py`

Implement the full upload flow per PRD §10.3:
1. Validate: files or text provided (not both, not neither), max 5 files, each ≤ 50MB, PDF/DOCX only
2. Extract text from each file using extraction utilities
3. Concatenate into one blob
4. Count tokens
5. Compute SHA-256 hash
6. Check DynamoDB Hash Index — if match found, copy analysis (stub for now, return 200 with existing agreementId)
7. Generate `agreementId = "agmt-" + uuid4().hex[:8]`
8. Save combined text to S3 at `documents/{userId}/{agreementId}/original.txt`
9. Create Agreement record in DynamoDB (status=UPLOADED)
10. Return 200 with response shape from PRD §11 POST /agreements

Return all error responses from PRD §11 with correct HTTP status codes (400, 413, 415).

### 3.5 Implement GET /agreements
File: `api/routers/agreements.py`

Query DynamoDB for all items where `PK = USER#<userId>` and `SK` begins with `AGREEMENT#`. Return list per PRD §11 GET /agreements response shape. `overall_risk` and `document_types` are null until COMPLETED.

### 3.6 Implement GET /agreements/:id
File: `api/routers/agreements.py`

Fetch single Agreement entity from DynamoDB. Verify ownership via GSI-1 (check `userId` matches). Return 403 if mismatch, 404 if not found. Return response shape per PRD §11.

### 3.7 Deploy and test
```bash
# Mac/Windows: sam build --parallel --use-container && sam deploy --config-env dev
sam build --parallel && sam deploy --config-env dev
```

Test with curl or Postman:
1. `POST /agreements` with a real PDF — verify S3 key exists, DynamoDB Agreement record exists with status=UPLOADED
2. `GET /agreements` — verify agreement appears in list
3. `GET /agreements/:id` — verify correct response shape
4. Upload same PDF again — verify hash match returns immediately (even if analysis copy is stub)
5. Test all error cases: missing file, wrong type, too large

**Day 3 done when:** Upload creates S3 object + DynamoDB record, and GET endpoints return correct data.

---

## Day 4 — Backend: Dispatcher Lambda + AI Worker (Analysis Pipeline)

**Goal:** Full async pipeline works. Upload triggers dispatcher → SQS → AI Worker → Nova → DynamoDB. Agreement status transitions correctly.

### 4.1 Implement Dispatcher Lambda
File: `dispatcher/dispatcher.py`

Read S3 ObjectCreated event. Extract `userId` and `agreementId` from S3 key path (`documents/{userId}/{agreementId}/original.txt`). Push SQS message per PRD §10.6 format. The `token_count` must be fetched from DynamoDB Agreement record (the API Lambda stored it there during upload).

```python
import boto3, json, os

sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE_NAME"])

def handler(event, context):
    for record in event["Records"]:
        s3_key = record["s3"]["object"]["key"]
        # key format: documents/{userId}/{agreementId}/original.txt
        parts = s3_key.split("/")
        user_id = parts[1]
        agreement_id = parts[2]

        # Fetch token_count from DynamoDB
        response = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"})
        token_count = response["Item"].get("token_count", 0)

        sqs.send_message(
            QueueUrl=os.environ["SQS_QUEUE_URL"],
            MessageBody=json.dumps({
                "agreementId": agreement_id,
                "userId": user_id,
                "s3_key": s3_key,
                "token_count": token_count
            })
        )
```

### 4.2 Implement Nova prompt
File: `worker/prompt.py`

Implement `build_analysis_prompt(document_text: str) -> str` — returns the exact prompt from PRD §12.1 with `{document_text}` substituted. Include all anchor clause lists and all 13 rules exactly as written in the PRD.

### 4.3 Implement Nova API call
File: `worker/nova.py`

Implement `call_nova(prompt: str) -> dict` using the exact boto3 call from PRD §10.8:
- Client: `bedrock-runtime`
- Method: `converse`
- Model ID: `amazon.nova-lite-v1:0`
- Response path: `response["output"]["message"]["content"][0]["text"]`
- Parse JSON response
- On JSON parse failure: retry once with explicit "fix JSON syntax" instruction
- On second failure: raise exception (caller sets status=FAILED)

### 4.4 Implement DynamoDB write helpers
File: `worker/dynamo.py`

Implement functions to write all analysis results:
- `set_status(agreement_id, user_id, status)` — updates Agreement entity status field
- `write_analysis(agreement_id, verdict, overall_risk, summary, financials, timeline, document_types)` — writes Analysis entity per PRD §16
- `write_risks(agreement_id, risks: list)` — writes one Risk entity per item per PRD §16
- `write_ambiguous_clauses(agreement_id, clauses: list)` — writes one Ambiguous Clause entity per item
- `write_clause_checks(agreement_id, clauses: list)` — writes one Clause Check entity per item
- `write_hash_index(sha256_hash, agreement_id)` — writes Hash Index entity

**Critical — update `document_types` and `overall_risk` on the Agreement entity when analysis completes.** Add `user_id` to the `write_analysis()` function signature so it can perform this update. The Agreement item (`PK=USER#<userId>`, `SK=AGREEMENT#<agreementId>`) must be updated to set `document_types` (JSON array from Nova output) and `overall_risk` (string). These two fields are returned by `GET /agreements` and `GET /agreements/:id` — they must be set on the Agreement entity, not just on the Analysis entity. Without this update, the sidebar risk badge and agreement type labels never render.

Updated function signature:
```python
def write_analysis(agreement_id, user_id, verdict, overall_risk, summary,
                   financials, timeline, document_types) -> None:
    # 1. Write Analysis entity (PK=AGREEMENT#<id>, SK=#ANALYSIS)
    table.put_item(Item={...})

    # 2. Stamp document_types + overall_risk onto the Agreement entity so
    #    GET /agreements and GET /agreements/:id return them correctly
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"},
        UpdateExpression="SET document_types = :dt, overall_risk = :or_val",
        ExpressionAttributeValues={":dt": document_types, ":or_val": overall_risk}
    )
```

The AI Worker (worker.py) has `user_id` from the SQS message and passes it to this function. Note: use `:or_val` (not `:or`) as the placeholder — `or` is a reserved word in DynamoDB expression syntax.

### 4.5 Implement AI Worker handler
File: `worker/worker.py`

Implement the full pipeline per PRD §10.8:
1. Parse SQS message body
2. Set agreement status = PROCESSING in DynamoDB
3. Fetch document text from S3 (`s3_key` from message)
4. If `token_count > 100000`: create Bedrock KB, index document, store KB ARN on Agreement entity. **For now, implement a stub that logs "RAG path - KB creation skipped" and proceeds with full context** — RAG is implemented on Day 6.
5. Build analysis prompt using `build_analysis_prompt()`
6. Call Nova via `call_nova()`
7. Parse response — extract all fields per PRD §12.1 output schema
8. Write all results to DynamoDB using write helpers
9. Set status = COMPLETED
10. On any exception: set status = FAILED, log full traceback to CloudWatch

Update `worker/requirements.txt`:
```
boto3
tiktoken
```

### 4.6 Deploy and test full pipeline
```bash
# Mac/Windows: sam build --parallel --use-container && sam deploy --config-env dev
sam build --parallel && sam deploy --config-env dev
```

End-to-end test:
1. Upload a real employment contract PDF via `POST /agreements`
2. Watch CloudWatch logs for Dispatcher Lambda — confirm SQS message sent
3. Watch CloudWatch logs for AI Worker — confirm Nova called, JSON parsed
4. Check DynamoDB — Analysis, Risk, Ambiguous Clause, Clause Check entities must all exist
5. Check Agreement status = COMPLETED
6. Check `document_types` array is populated on Agreement entity

**Day 4 done when:** Upload → analysis pipeline completes → all DynamoDB entities written → status = COMPLETED.

---

## Day 5 — Backend: Analysis Read + Chat Endpoints + Delete

**Goal:** All remaining API endpoints implemented. `GET /agreements/:id/analysis`, `POST /agreements/:id/chat`, `GET /agreements/:id/chat`, `DELETE /agreements/:id` all work.

### 5.1 Implement GET /agreements/:id/analysis
File: `api/routers/agreements.py`

1. Verify ownership (GSI-1 lookup)
2. Check status — return 409 if not COMPLETED
3. Fetch Analysis entity from DynamoDB (`PK=AGREEMENT#<id>`, `SK=#ANALYSIS`)
4. Fetch all Risk entities (`SK` begins with `RISK#`)
5. Fetch all Ambiguous Clause entities (`SK` begins with `AMBIGUOUS#`)
6. Fetch all Clause Check entities (`SK` begins with `CLAUSE#`)
7. Assemble and return full response per PRD §11 GET /agreements/:id/analysis response shape

### 5.2 Implement Q&A prompt
File: `api/utils/qa_prompt.py`

Implement `build_qa_prompt(document_text: str, question: str) -> str` — returns exact prompt from PRD §12.2. Must include the `[FILE: filename]` marker instruction (rule 5 in PRD §12.2).

### 5.3 Implement POST /agreements/:id/chat
File: `api/routers/chat.py`

Per PRD §10.9:
1. Fetch agreement from DynamoDB — verify ownership, verify status=COMPLETED
2. Return 409 if not COMPLETED
3. If `bedrock_kb_id` is null: fetch full document text from S3, build Q&A prompt, call Nova
4. If `bedrock_kb_id` is set: **stub for now** — fetch full text from S3 and use full context (RAG path implemented Day 6)
5. Parse Nova response — extract `answer`, `citations`, `found_in_document`
6. Generate `epoch_ms` and `messageId` **before** writing to DynamoDB:
   ```python
   from datetime import datetime, timezone
   epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
   message_id = f"chat-{epoch_ms}"  # e.g. "chat-1710498234567" — matches PRD §11 response shape
   ```
   Write Chat Message entity to DynamoDB per PRD §16. **The SK must be `CHAT#<epoch_ms>` where `epoch_ms` is integer milliseconds since Unix epoch** — DynamoDB sorts SKs lexicographically and this is the only timestamp format that sorts correctly. SK = `f"CHAT#{epoch_ms}"`. Do not use ISO strings or human-readable formats. Store `message_id` as an attribute on the entity so `GET /agreements/:id/chat` can return it in the response.
7. Return response per PRD §11 POST /agreements/:id/chat — include `messageId: message_id` in the response body.

### 5.4 Implement GET /agreements/:id/chat
File: `api/routers/chat.py`

Query all Chat Message entities for the agreement (`PK=AGREEMENT#<id>`, `SK` begins with `CHAT#`). DynamoDB returns them sorted by SK (timestamp) ascending — this is oldest-first which is correct. Return per PRD §11 response shape.

### 5.5 Implement DELETE /agreements/:id
File: `api/routers/agreements.py`

1. Verify ownership
2. Delete all DynamoDB entities for this agreement (Agreement, Analysis, all Risk, all Ambiguous Clause, all Clause Check, all Chat Message items) — use `batch_writer()`
3. Delete S3 object at `documents/{userId}/{agreementId}/original.txt`
4. If `bedrock_kb_id` is set: delete the Bedrock KB (**stub log for now**)
5. Return 200 `{"message": "Agreement deleted"}`

**Do NOT delete the Hash Index entry (`HASH#<sha256>`)** — it must outlive individual agreements. The hash index references the original analysis for dedup; other users may upload the same document in the future and need it. Stale hash entries (where the source agreement was later deleted) are handled gracefully in the dedup copy path (§5.6) and cause no harm.

### 5.6 Implement deduplication copy path
File: `api/routers/agreements.py`

Complete the stub from Day 3. When hash match is found:

1. Fetch the Analysis item from the original `agreementId` stored in the Hash Index (`PK=AGREEMENT#<original_id>`, `SK=#ANALYSIS`)
2. **If the Analysis item does NOT exist** (the original user deleted their agreement — stale Hash Index entry): treat this upload as a fresh document. Fall through to the normal pipeline: save to S3, create Agreement with status=`UPLOADED`, let the S3 event trigger the dispatcher. Do not write a new Hash Index entry yet — the AI Worker writes it on completion.
3. **If the Analysis item exists**: fetch all Risk, Ambiguous Clause, and Clause Check items for the original agreementId. Create a new Agreement record for this user (new `agreementId`, `status=COMPLETED` immediately). Copy all fetched items to the new `agreementId` using `batch_writer()`. Return 200 — no S3 write, no SQS job dispatched.

**Why check before creating the Agreement:** If you create the Agreement first (status=COMPLETED) and the copy then fails, the user sees a broken completed agreement with no analysis data. Always verify source items exist before committing the new record.

**Why the Hash Index is never deleted:** It serves future users. A stale entry is not a bug — it's a cache miss, handled above. Deleting it would be a race condition (another user might look it up concurrently) and buys nothing.

```python
from boto3.dynamodb.conditions import Key

def copy_analysis_for_dedup(table, original_agreement_id: str, new_agreement_id: str,
                             new_user_id: str, title: str, token_count: int,
                             document_hash: str, s3_key: str, file_count, source_filenames) -> bool:
    """
    Copy analysis from original_agreement_id to new_agreement_id.
    Returns True if copy succeeded, False if original analysis is gone (stale hash index).
    Caller should fall through to normal pipeline on False.
    """

    # Step 1: Check the Analysis entity exists (stale hash index guard)
    analysis_resp = table.get_item(
        Key={"PK": f"AGREEMENT#{original_agreement_id}", "SK": "#ANALYSIS"}
    )
    if "Item" not in analysis_resp:
        return False  # stale — original user deleted their agreement

    analysis_item = analysis_resp["Item"]

    # Step 2: Fetch all child entities for the original agreement
    # One Query call returns them all — Risk, Ambiguous Clause, Clause Check, Analysis
    child_resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"AGREEMENT#{original_agreement_id}")
    )
    source_items = child_resp["Items"]

    # Step 3: Create the new Agreement record (status=COMPLETED immediately — no pipeline)
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
        "bedrock_kb_id": None,   # never share a KB across users — Q&A will use full context
        "created_at": now
    })

    # Step 4: Batch-copy all child entities (Analysis + Risk + Ambiguous Clause + Clause Check)
    # Replace PK with new agreementId on every item. SK prefixes identify entity types.
    # batch_writer handles chunking into groups of 25 automatically.
    copy_sk_prefixes = {"#ANALYSIS", "RISK#", "AMBIGUOUS#", "CLAUSE#"}

    with table.batch_writer() as batch:
        for item in source_items:
            sk = item.get("SK", "")
            # Only copy entity types we want — skip CHAT# (chat history is not shared)
            if not any(sk.startswith(prefix) for prefix in copy_sk_prefixes):
                continue
            new_item = dict(item)
            new_item["PK"] = f"AGREEMENT#{new_agreement_id}"
            # Generate a new unique SK for Risk/Ambiguous/Clause items to avoid PK collisions
            # Analysis SK (#ANALYSIS) is stable — keep it as-is
            if sk != "#ANALYSIS":
                import uuid
                prefix = sk.split("#")[0] + "#"
                new_item["SK"] = prefix + uuid.uuid4().hex[:8]
            batch.put_item(Item=new_item)

    return True
```

Call site in `POST /agreements` (replacing the Day 3 stub):

```python
hash_hit = get_hash_index(document_hash)
if hash_hit:
    original_id = hash_hit["agreementId"]
    new_agreement_id = "agmt-" + uuid4().hex[:8]
    copied = copy_analysis_for_dedup(
        table, original_id, new_agreement_id,
        user["userId"], title, token_count, document_hash,
        f"documents/{user['userId']}/{new_agreement_id}/original.txt",
        file_count, source_filenames
    )
    if copied:
        return {"agreementId": new_agreement_id, "title": title, "status": "COMPLETED", ...}
    # else: fall through to normal pipeline below
```

### 5.7 Deploy and test all endpoints
```bash
# Mac/Windows: sam build --parallel --use-container && sam deploy --config-env dev
sam build --parallel && sam deploy --config-env dev
```

Test every endpoint:
1. `GET /agreements/:id/analysis` on a completed agreement — verify all cards present
2. `POST /agreements/:id/chat` — ask a question, verify answer + citations returned, Chat Message written to DynamoDB
3. `GET /agreements/:id/chat` — verify history returns in order
4. `DELETE /agreements/:id` — verify agreement + all child entities deleted from DynamoDB, S3 object deleted
5. Upload same document twice — verify deduplication: instant result, zero Nova calls

**Day 5 done when:** All 7 API endpoints work correctly and deduplication copy path is complete.

---

## Day 6 — Backend: RAG Path (Bedrock Knowledge Bases)

**Goal:** Full hybrid AI strategy implemented. Documents > 100k tokens use Bedrock Knowledge Bases for both initial analysis and Q&A.

### 6.1 Implement Bedrock KB creation in AI Worker
File: `worker/bedrock_kb.py`

Implement `create_kb_for_agreement(agreement_id: str, s3_bucket: str, s3_key: str) -> str` using the **exact boto3 sequence** below. The Bedrock KB API (`bedrock-agent`) is not the same client as `bedrock-runtime` — do not mix them.

**Vector store: Pinecone (serverless).** The `PineconeSecret` is already provisioned in `template.yaml` (Day 1). Before calling `create_knowledge_base`, the AI Worker fetches the Pinecone API key and index host URL from Secrets Manager using the `PINECONE_SECRET_ARN` env var. These two values are passed directly into the `storageConfiguration` — no collection ARN, no VPC, no encryption policies. Pinecone is pay-per-use with zero fixed hourly cost.

```python
import boto3
import json
import os
import time

bedrock_agent = boto3.client("bedrock-agent", region_name=os.environ["BEDROCK_REGION"])
secrets_client = boto3.client("secretsmanager", region_name=os.environ["BEDROCK_REGION"])

# Fetch Pinecone credentials once at cold start
def _get_pinecone_credentials() -> dict:
    """
    Fetch Pinecone API key and index host from Secrets Manager.
    Secret format: {"api_key": "pc-xxxx", "index_host": "https://clauseiq-xxxxx.svc.pinecone.io"}
    """
    response = secrets_client.get_secret_value(SecretId=os.environ["PINECONE_SECRET_ARN"])
    return json.loads(response["SecretString"])

def create_kb_for_agreement(agreement_id: str, s3_bucket: str, s3_key: str) -> str:
    """
    Create a Bedrock Knowledge Base for a single agreement document backed by Pinecone serverless.
    Returns the Knowledge Base ID (not ARN) — store this as bedrock_kb_id.

    Full sequence: fetch Pinecone creds → CreateKnowledgeBase → CreateDataSource → StartIngestionJob → poll GetIngestionJob
    Each step depends on the ID returned by the previous step.
    """

    # Fetch Pinecone credentials from Secrets Manager
    pinecone_creds = _get_pinecone_credentials()
    pinecone_api_key = pinecone_creds["api_key"]
    pinecone_index_host = pinecone_creds["index_host"]

    # Step 1 — Create the Knowledge Base backed by Pinecone serverless
    # storageConfiguration type is PINECONE — not OPENSEARCH_SERVERLESS.
    # Bedrock uses the agreementId as the namespace inside the shared Pinecone index,
    # so all agreements share one index but their vectors are fully isolated.
    # roleArn: the IAM role Bedrock assumes to read S3 — passed via BEDROCK_KB_ROLE_ARN env var.
    kb_response = bedrock_agent.create_knowledge_base(
        name=f"clauseiq-{agreement_id}",
        roleArn=os.environ["BEDROCK_KB_ROLE_ARN"],
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": f"arn:aws:bedrock:{os.environ['BEDROCK_REGION']}::foundation-model/amazon.titan-embed-text-v1"
            }
        },
        storageConfiguration={
            "type": "PINECONE",
            "pineconeConfiguration": {
                "connectionString": pinecone_index_host,   # e.g. https://clauseiq-xxxxx.svc.pinecone.io
                "credentialsSecretArn": os.environ["PINECONE_SECRET_ARN"],
                "namespace": agreement_id,                 # isolates this agreement's vectors
                "fieldMapping": {
                    "textField": "text",
                    "metadataField": "metadata"
                }
            }
        }
    )
    kb_id = kb_response["knowledgeBase"]["knowledgeBaseId"]

    # Step 2 — Create a Data Source pointing to the S3 object
    # The S3 URI must point to the exact file, not just the prefix.
    ds_response = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name=f"clauseiq-{agreement_id}-source",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{s3_bucket}",
                "inclusionPrefixes": [s3_key]   # scopes ingestion to just this document
            }
        },
        vectorIngestionConfiguration={
            "chunkingConfiguration": {
                "chunkingStrategy": "FIXED_SIZE",
                "fixedSizeChunkingConfiguration": {
                    "maxTokens": 300,
                    "overlapPercentage": 20
                }
            }
        }
    )
    ds_id = ds_response["dataSource"]["dataSourceId"]

    # Step 3 — Start the ingestion job (async — Bedrock reads S3, chunks, embeds, indexes into Pinecone)
    ingest_response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id
    )
    job_id = ingest_response["ingestionJob"]["ingestionJobId"]

    # Step 4 — Poll until ingestion completes (typically 30-120 seconds for a single document)
    # COMPLETE and FAILED are terminal states. IN_PROGRESS and STARTING are non-terminal.
    max_wait_seconds = 300
    poll_interval = 5
    elapsed = 0
    while elapsed < max_wait_seconds:
        job_status = bedrock_agent.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            ingestionJobId=job_id
        )
        status = job_status["ingestionJob"]["status"]
        if status == "COMPLETE":
            return kb_id
        if status == "FAILED":
            failure_reasons = job_status["ingestionJob"].get("failureReasons", [])
            raise RuntimeError(f"Bedrock KB ingestion failed: {failure_reasons}")
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Bedrock KB ingestion timed out after {max_wait_seconds}s")


def delete_kb(kb_id: str) -> None:
    """Delete a Knowledge Base. Called by DELETE /agreements/:id."""
    try:
        bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
    except bedrock_agent.exceptions.ResourceNotFoundException:
        pass  # already deleted — not an error
```

**No template.yaml changes needed for Day 6.** The `PineconeSecret` resource and `PINECONE_SECRET_ARN` environment variable are already defined in `template.yaml` from Day 1. The `BedrockKBServiceRole` is also already present. No OpenSearch Serverless collection, encryption policies, network policies, or data access policies are needed — Pinecone has no AWS-side infrastructure to provision. The only credential Bedrock needs is the Pinecone API key, which is already stored in Secrets Manager.

**IAM note:** The `AiWorkerFunction` needs `secretsmanager:GetSecretValue` on the `PineconeSecret` ARN. Add this to its `Policies` block in `template.yaml` if not already present:
```yaml
- Effect: Allow
  Action: [secretsmanager:GetSecretValue]
  Resource: !Ref PineconeSecret
```

Update `worker/requirements.txt` — no new packages needed (boto3 covers both bedrock-agent and secretsmanager).

**Day 6 cost note:** Pinecone serverless is pay-per-use with a free tier (2GB storage, 1M reads/month). There is **no fixed hourly charge** — unlike OpenSearch Serverless which costs ~$0.24/hour minimum regardless of usage. Development and testing cost is effectively zero within the free tier.

### 6.2 Wire KB creation into AI Worker
File: `worker/worker.py`

Replace the Day 4 stub:
```python
if token_count > 100000:
    s3_bucket = os.environ["S3_BUCKET_NAME"]
    # create_kb_for_agreement signature: (agreement_id, s3_bucket, s3_key) — no document_text
    kb_id = create_kb_for_agreement(agreement_id, s3_bucket, s3_key)
    # Store kb_id on Agreement entity
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"AGREEMENT#{agreement_id}"},
        UpdateExpression="SET bedrock_kb_id = :kb_id",
        ExpressionAttributeValues={":kb_id": kb_id}
    )
```

For large documents, use RAG retrieval instead of full text in the analysis prompt:
- Retrieve top-K relevant chunks from Bedrock KB using `bedrock-agent-runtime` `retrieve` API
- Concatenate retrieved chunks as `document_text` in the prompt
- All other pipeline steps unchanged

### 6.3 Wire RAG into Q&A endpoint
File: `api/routers/chat.py`

Replace the Day 5 stub in `POST /agreements/:id/chat`:
```python
if bedrock_kb_id:
    # Retrieve relevant chunks from Bedrock KB
    agent_runtime = boto3.client("bedrock-agent-runtime")
    response = agent_runtime.retrieve(
        knowledgeBaseId=bedrock_kb_id,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}}
    )
    chunks = [r["content"]["text"] for r in response["retrievalResults"]]
    document_text = "\n\n".join(chunks)
    # Build Q&A prompt with retrieved chunks instead of full text
```

### 6.4 Wire KB deletion into DELETE endpoint
File: `api/routers/agreements.py`

Replace the Day 5 stub:
```python
if bedrock_kb_id:
    delete_kb(bedrock_kb_id)
```

Import `delete_kb` — this needs to be a shared utility. Move `bedrock_kb.py` to a shared location or duplicate the delete function in the API Lambda.

### 6.5 Test RAG path
Test with a document that genuinely exceeds 100k tokens (a very long T&Cs document or concatenated bundle). Verify:
1. AI Worker creates Bedrock KB successfully
2. `bedrock_kb_id` is stored on Agreement entity in DynamoDB
3. Q&A calls retrieve from KB, not full S3 text
4. DELETE removes the KB
5. Full context path still works for small documents (no regression)

**Day 6 done when:** Hybrid AI strategy fully implemented. Small docs use full context. Large docs use Bedrock KB for both analysis and Q&A.

---

## Day 7 — Frontend: React Scaffold + Auth + 3-Panel Claude Shell

**Goal:** React app scaffolded, Cognito auth works, 3-panel Claude-style layout shell renders (Sidebar, Center Chat, Right Artifact Panel).

### 7.1 Scaffold React app
```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install tailwindcss @tailwindcss/vite
npm install @tanstack/react-query axios
npm install aws-amplify
npm install react-router-dom
npm install @radix-ui/react-dialog @radix-ui/react-tabs lucide-react
npx shadcn@latest init
```

Configure Tailwind in `vite.config.ts`. **Critically, implement the Claude-style color palette and typography from PRD §7 here** (warm cream `#F9F8F6` bg, dark charcoal `#252423` dark-mode bg, `Inter` and `Playfair Display` fonts).
Create `.env.local` in `frontend/` with the following variables. **The values come from the SAM Outputs printed at the end of Day 1.5 deploy** — retrieve them with `aws cloudformation describe-stacks --stack-name clauseiq-dev --query "Stacks[0].Outputs"` if you didn't save them:

```bash
# frontend/.env.local — never commit this file
VITE_API_BASE_URL=<ApiUrl from SAM Outputs, e.g. https://abc123.execute-api.ap-south-1.amazonaws.com>
VITE_COGNITO_USER_POOL_ID=<UserPoolId from SAM Outputs, e.g. ap-south-1_XXXXXXXXX>
VITE_COGNITO_APP_CLIENT_ID=<UserPoolClientId from SAM Outputs, e.g. 1a2b3c4d5e6f7g8h9i0j>
```

Add `frontend/.env.local` to `.gitignore` — these are environment-specific values, not secrets, but should not be committed.

### 7.2 Configure Amplify auth
File: `frontend/src/main.tsx`

```typescript
import { Amplify } from 'aws-amplify';
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_COGNITO_APP_CLIENT_ID,
    }
  }
});
```

### 7.3 Implement auth pages
File: `frontend/src/pages/LoginPage.tsx`
File: `frontend/src/pages/SignupPage.tsx`

Simple forms using Amplify `signIn()`, `signUp()`, `confirmSignUp()`. On successful login → redirect to `/dashboard`. On signup → show email verification input.

### 7.4 Implement auth context
File: `frontend/src/context/AuthContext.tsx`

React context that:
- Calls Amplify `getCurrentUser()` and `fetchAuthSession()` on mount
- Exposes `user`, `idToken`, `isLoading`, `signOut()`
- `idToken` is the Cognito ID token string — attached to every API request

### 7.5 Implement Axios instance
File: `frontend/src/lib/api.ts`

```typescript
import axios from 'axios';
import { fetchAuthSession } from 'aws-amplify/auth';

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL });

// Interceptors support async handlers — Axios awaits the returned Promise.
// fetchAuthSession() automatically refreshes an expired token before returning.
api.interceptors.request.use(async (config) => {
  try {
    const session = await fetchAuthSession();
    const token = session.tokens?.idToken?.toString();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // Not authenticated — request goes out without a token.
    // Protected endpoints return 401; the auth guard redirects to /login.
  }
  return config;
});

export default api;
```

**Why async:** `fetchAuthSession()` is always async — it reads from local storage and hits Cognito to refresh if the token is expired. A synchronous interceptor cannot await it, so `token` would always be `undefined` and every request would return 401 regardless of login state.

### 7.6 Implement 3-panel Claude layout shell
File: `frontend/src/pages/DashboardPage.tsx`

Render the Claude-style 3-panel layout:
- **Sidebar (Fixed Left)**: Sidebar for navigation and agreement history.
- **Center Panel**: The interactive chat / upload workspace.
- **Artifact Panel (Right)**: A collapsible drawer for rendering the structured analysis cards.

### 7.7 Set up routing
File: `frontend/src/App.tsx`

Routes:
- `/` → redirect to `/dashboard`
- `/login` → LoginPage
- `/signup` → SignupPage
- `/dashboard` → DashboardPage (protected — redirect to /login if not authenticated)
- `/agreements/:id` → DashboardPage with agreement selected (loads right panel content)

### 7.8 Add frontend CI/CD workflow
Add `.github/workflows/deploy-frontend.yml` per PRD §22. Add required GitHub secrets: `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `CLOUDFRONT_DISTRIBUTION_ID`.

**Day 7 done when:** App loads at localhost:5173, login/signup works with real Cognito, 3-panel shell renders, auth redirects work correctly.

---

## Day 8 — Frontend: Sidebar + Upload Modal + Polling

**Goal:** Sidebar lists real agreements from API. Upload modal works. Polling shows processing state and auto-renders when complete.

### 8.1 Implement API hooks
File: `frontend/src/hooks/useAgreements.ts`

Using TanStack Query:
```typescript
export function useAgreements() {
  return useQuery({
    queryKey: ['agreements'],
    queryFn: () => api.get('/agreements').then(r => r.data.agreements)
  });
}

export function useAgreementStatus(agreementId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['agreement', agreementId],
    queryFn: () => api.get(`/agreements/${agreementId}`).then(r => r.data),
    refetchInterval: (data) => {
      if (!data || data.status === 'UPLOADED' || data.status === 'PROCESSING') return 3000;
      return false; // stop polling when COMPLETED or FAILED
    },
    enabled
  });
}
```

### 8.2 Implement Sidebar component
File: `frontend/src/components/Sidebar.tsx`

- Call `useAgreements()` to fetch list
- Render each agreement as a clickable row: title + risk badge (color-coded: green=low, yellow=medium, red=high) + status badge
- Processing agreements show `🔄 Processing...` badge
- Clicking an agreement → navigate to `/agreements/:id`
- Currently selected agreement is highlighted
- "New Agreement" button at top opens upload modal
- Profile name + logout button at bottom
- Mobile: entire sidebar collapses behind a hamburger menu button

### 8.3 Implement Upload Modal
File: `frontend/src/components/UploadModal.tsx`

Implement per PRD §7.2:
- Tabs: "Upload Files" and "Paste Text"
- Upload Files tab: drag-and-drop zone + click to browse, accepts PDF/DOCX, max 5 files, 50MB each. Uploaded files listed below drop zone with ✕ to remove.
- Paste Text tab: textarea
- Optional title field on both tabs
- "Analyze Agreement" submit button
- On submit: call `POST /agreements` with `multipart/form-data` (files) or `application/json` (text)
- On success: close modal, add skeleton entry to sidebar, navigate to `/agreements/:id`, polling begins automatically
- Show inline error messages for validation failures (wrong file type, too large, etc.)

### 8.4 Implement processing state in main panel
File: `frontend/src/pages/DashboardPage.tsx`

When an agreement is selected and status is UPLOADED or PROCESSING:
- Show skeleton loaders in place of all analysis cards
- Display "Analyzing your agreement..." message
- Poll via `useAgreementStatus()` every 3 seconds
- When status flips to COMPLETED: stop polling, fetch full analysis, render cards
- When status is FAILED: show error state with "Try uploading again" retry button
- Polling timeout after 5 minutes: show "Taking longer than expected — refresh to check"

**Day 8 done when:** Upload modal works, sidebar populates from real API, processing state shows skeleton loaders, completed agreements auto-render when polling detects COMPLETED.

---

## Day 9 — Frontend: Analysis Cards in Artifact Panel (Verdict + Risks + Ambiguous Clauses)

**Goal:** Frontend reads analysis data from API and renders the Verdict, Risk, and Ambiguous Clause cards inside the Right (Artifact) Panel.

### 9.1 Implement analysis data hook
File: `frontend/src/hooks/useAnalysis.ts`

```typescript
export function useAnalysis(agreementId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['analysis', agreementId],
    queryFn: () => api.get(`/agreements/${agreementId}/analysis`).then(r => r.data),
    enabled,
    staleTime: Infinity // analysis never changes — cache forever
  });
}
```

### 9.2 Implement AI Verdict card
File: `frontend/src/components/analysis/VerdictCard.tsx`

Renders `verdict.decision` and `verdict.reason`. Three visual states:
- "Sign" → green background, ✅ icon
- "Proceed with Caution" → yellow background, ⚠️ icon
- "High Risk" → red background, 🔴 icon

Also renders overall risk badge (`low` / `medium` / `high`).

### 9.3 Implement Risk Analysis card
File: `frontend/src/components/analysis/RisksCard.tsx`

Renders list of risks from `analysis.risks`. Each risk card shows:
- Severity badge (High=red, Medium=yellow, Low=blue)
- Title
- Plain-English explanation
- Citation: `file_name` (if present) + `section_name` + `Page X, Line Y`

If `risks` is empty: show "No significant risks identified ✅"

Sort by severity: High first, then Medium, then Low.

### 9.4 Implement Ambiguous Clauses card
File: `frontend/src/components/analysis/AmbiguousCard.tsx`

Renders list of ambiguous clauses from `analysis.ambiguous_clauses`. Each card shows:
- Title with ⚠️ icon
- Exact `clause_text` in a styled blockquote
- `explanation` of why it's vague
- Citation
- Collapsible "Questions to ask" section showing `suggested_questions` as a numbered list

If `ambiguous_clauses` is empty: show "No ambiguous clauses detected ✅"

**Day 9 done when:** First three analysis cards render correctly with real data from the API.

---

## Day 10 — Frontend: Remaining Analysis Cards (Clauses + Financials + Timeline + Summary)

**Goal:** All remaining analysis cards complete. Full right panel renders end to end.

### 10.1 Implement Clause Completeness Check card
File: `frontend/src/components/analysis/ClausesCard.tsx`

Renders `analysis.clauses` as a two-column checklist:
- ✅ Found clauses: green checkmark + clause name + section/page citation (clickable to highlight)
- ❌ Missing clauses: red X + clause name + "Not found in this agreement"

Group by status: Found first, Missing below with a divider.

### 10.2 Implement Financial Terms card
File: `frontend/src/components/analysis/FinancialsCard.tsx`

Renders `analysis.financials` as a clean table:
| Item | Value | Location |
|---|---|---|
| Base Salary | ₹18,00,000 per annum | §4.1, Page 3 |

If `financials` is empty: show "No financial terms identified"

### 10.3 Implement Key Dates / Timeline card
File: `frontend/src/components/analysis/TimelineCard.tsx`

Renders `analysis.timeline` as a vertical timeline:
- Each event: date pill on left, event name on right, citation below
- Sorted chronologically by date
- If `timeline` is empty: show "No key dates identified"

### 10.4 Implement AI Summary card
File: `frontend/src/components/analysis/SummaryCard.tsx`

Renders `analysis.summary` as a plain paragraph. No special formatting — just clean readable text.

### 10.5 Assemble full analysis view
File: `frontend/src/pages/DashboardPage.tsx`

When analysis is loaded, render all cards in order per PRD §7.1:
1. VerdictCard
2. ClausesCard
3. RisksCard
4. AmbiguousCard
5. FinancialsCard
6. TimelineCard
7. SummaryCard
8. (Chat — Day 11)

**Day 10 done when:** Full analysis view renders end to end with all 7 cards for a completed agreement.

---

## Day 11 — Frontend: Chat Interface

**Goal:** Ask AI chat section works at the bottom of the analysis view. History loads, new questions work, citations display correctly.

### 11.1 Implement chat hooks
File: `frontend/src/hooks/useChat.ts`

```typescript
export function useChatHistory(agreementId: string) {
  return useQuery({
    queryKey: ['chat', agreementId],
    queryFn: () => api.get(`/agreements/${agreementId}/chat`).then(r => r.data.messages)
  });
}

export function useSendMessage(agreementId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (question: string) =>
      api.post(`/agreements/${agreementId}/chat`, { question }).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', agreementId] });
    }
  });
}
```

### 11.2 Implement Chat component
File: `frontend/src/components/Chat.tsx`

- Load chat history on mount via `useChatHistory()`
- Render messages in chronological order (oldest at top, newest at bottom)
- Each message pair (question + answer):
  - User question: right-aligned bubble
  - AI answer: left-aligned bubble with robot icon
  - Citations below the answer: each citation shows `file_name` + `section_name` + `Page X, Line Y` as small chips
  - If `found_in_document = false`: answer shown in italic, no citation chips
- Input bar at the bottom: textarea + send button
- Send button disabled while mutation is pending
- On send: optimistically append question bubble immediately, answer appears when mutation resolves
- Auto-scroll to bottom on new message
- Empty state: "Ask anything about this agreement — I'll answer based only on what's in the document."

### 11.3 Wire Chat into DashboardPage
Add `<Chat agreementId={id} />` below `SummaryCard` in the analysis view. Only render Chat when status = COMPLETED.

**Day 11 done when:** Chat loads history, sends questions, displays answers with citations, auto-scrolls correctly.

---

## Day 12 — Frontend: Polish + Mobile + Error States

**Goal:** All edge cases handled. Mobile layout works. Error states, empty states, and loading states are all implemented.

### 12.1 Mobile sidebar
File: `frontend/src/components/Sidebar.tsx`

- Below `md` breakpoint: sidebar hidden by default
- Hamburger menu button appears in top-left of main panel
- Clicking hamburger: sidebar slides in as an overlay with a backdrop
- Clicking backdrop or selecting an agreement: sidebar closes

### 12.2 Error boundary
File: `frontend/src/components/ErrorBoundary.tsx`

Wrap the entire app in a React error boundary. On uncaught error: show "Something went wrong — refresh the page" with a reload button.

### 12.3 Handle FAILED analysis state
In DashboardPage: when polling detects status=FAILED, show:
- Error icon + "We couldn't analyze this agreement"
- Suggested actions: "Try uploading a cleaner PDF" or "Try pasting the text instead"
- "Delete and try again" button that calls DELETE /agreements/:id then opens upload modal

### 12.4 Handle API errors in upload modal
- 413 response: "This file is too large (max 50MB)"
- 415 response: "Unsupported file type — upload PDF or DOCX only"
- 400 "Too many files": "Maximum 5 files per upload"
- Network error: "Upload failed — check your connection and try again"

### 12.5 Handle empty agreement list
Sidebar with no agreements: show the first-run CTA from PRD §7.3 inline in the sidebar below the "New Agreement" button.

### 12.6 Loading skeleton for sidebar
While `useAgreements()` is loading: show 3 skeleton rows in the sidebar (grey animated pulses) instead of empty space.

### 12.7 Page title and favicon
Set `<title>ClauseIQ</title>` and add a simple ⚖️ favicon.

**Day 12 done when:** App is fully usable on mobile. All error states display correctly. No blank screens on any edge case.

---

## Day 13 — Integration Testing + Bug Fixes + Security Hardening

**Goal:** Full end-to-end test of every flow. All bugs fixed. Security checklist complete.

### 13.1 End-to-end test checklist

Run through every flow manually:

**Auth:**
- [ ] Sign up with new email → verification email received → confirm → User record in DynamoDB
- [ ] Log in → dashboard loads → sidebar populated
- [ ] Expired token → 401 received → redirect to login
- [ ] Log out → session cleared → redirect to login

**Single file upload:**
- [ ] Upload employment PDF → skeleton shows → status polling → COMPLETED → all 7 cards render
- [ ] Upload DOCX → same flow
- [ ] Paste text (Spotify T&Cs) → same flow
- [ ] Upload same PDF again → instant result (dedup) → analysis identical

**Multi-file bundle:**
- [ ] Upload 3 files together (offer letter + NDA + IP assignment) → one sidebar entry → one analysis covering all files → citations include correct `file_name`
- [ ] Q&A: ask cross-document question → answer cites correct file

**Analysis cards:**
- [ ] Verdict shows correct decision + reason
- [ ] Risks sorted by severity, citations correct
- [ ] Ambiguous clauses show clause text + suggested questions
- [ ] Clause completeness shows FOUND and MISSING
- [ ] Financials show correct values
- [ ] Timeline sorted chronologically
- [ ] Summary readable and accurate

**Chat:**
- [ ] Ask question present in doc → correct answer + citation
- [ ] Ask question not in doc → "This agreement does not specify that"
- [ ] Chat history persists across page refresh

**Delete:**
- [ ] Delete agreement → removed from sidebar → DynamoDB entities gone → S3 object gone

**Security:**
- [ ] Try accessing another user's agreement ID → 403
- [ ] Try uploading .xlsx → 415 error
- [ ] Try uploading 51MB file → 413 error
- [ ] Check no S3 URLs exposed in any API response
- [ ] Check no secrets in CloudWatch logs

### 13.2 Fix all bugs found in 13.1

Fix every issue found. Re-test after each fix.

### 13.3 Rate limiting
In API Gateway console (or via SAM template): configure a usage plan with rate limiting:
- Rate: 10 requests/second per user
- Burst: 20 requests

This protects against accidental Nova abuse.

### 13.4 CloudWatch alarms (optional but good for interviews)
Set up basic CloudWatch alarms:
- AI Worker Lambda errors > 0 in 5 minutes → alert
- DLQ depth > 0 → alert (means jobs are failing permanently)

**Day 13 done when:** All checklist items pass. No known bugs. Security checklist complete.

---

## Day 14 — Production Deploy + README + Final Polish

**Goal:** App is live in production. README documents the architecture. Project is portfolio-ready.

### 14.1 Deploy to production
```bash
sam deploy --config-env prod
```

Add production GitHub secrets: `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `COGNITO_USER_POOL_ID_DEV`, `COGNITO_APP_CLIENT_ID_DEV`, `CLOUDFRONT_DISTRIBUTION_ID`.

Push to `main` branch → GitHub Actions deploys frontend to S3 + CloudFront automatically.

Verify:
- Production API returns 200 on `/health`
- Frontend loads at CloudFront URL
- Full signup → upload → analysis flow works in production

### 14.2 Write README.md

The README is what interviewers read. Write it to answer exactly the questions they'll have:

**Sections:**
1. **What it is** — one paragraph, plain English
2. **Live demo** — link to CloudFront URL
3. **Architecture diagram** — copy the ASCII diagram from PRD §10.1
4. **Tech stack table** — list every service + library with one-line reason
5. **Key engineering decisions** — 5-6 bullet points summarizing the most interesting ADRs (hybrid AI strategy, analyze-once cache, single-table DynamoDB, concatenation for bundles, deduplication via SHA-256)
6. **How to run locally** — exact commands: `sam build`, `sam local start-api`, `npm run dev`
7. **Project structure** — the folder tree from PRD §21

### 14.3 Final UI polish pass
- Consistent spacing and padding across all cards
- Tailwind dark/light: pick one and make it consistent throughout
- Verify all text is readable at mobile viewport (375px)
- Verify no layout breaks at desktop (1440px)
- Check all loading states look good (not janky)

### 14.4 Test production one final time
Repeat the core flow in production:
1. Sign up with a fresh email
2. Upload an employment contract
3. Wait for analysis
4. Ask 3 questions in chat
5. Delete the agreement
6. Confirm clean state

**Day 14 done when:** App is live in production. README is complete. Project is ready to show in any interview.

---

## Summary

| Day | Focus | Output |
|---|---|---|
| 1 | Scaffold + AWS infra | All resources live, /health works |
| 2 | Auth + JWT + User init | Signup → DynamoDB record, /me works |
| 3 | Upload endpoint + S3 + DynamoDB | POST /agreements end to end |
| 4 | Dispatcher + AI Worker + Nova | Full async pipeline, analysis in DynamoDB |
| 5 | Analysis read + Chat + Delete endpoints | All 7 API endpoints working |
| 6 | RAG (Bedrock Knowledge Bases) | Hybrid AI strategy fully implemented |
| 7 | React scaffold + Auth + 2-panel shell | App loads, login works, layout exists |
| 8 | Sidebar + Upload modal + Polling | Upload → skeleton → auto-render |
| 9 | Verdict + Risks + Ambiguous cards | Top 3 analysis cards with real data |
| 10 | Clauses + Financials + Timeline + Summary | Full analysis view complete |
| 11 | Chat interface | Q&A works with citations |
| 12 | Mobile + error states + polish | Production-quality UX |
| 13 | Integration testing + security | All flows verified, bugs fixed |
| 14 | Production deploy + README | Live app, portfolio-ready |
