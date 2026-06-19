# ClauseIQ — Product Requirements Document

## 1. Product Overview

**ClauseIQ** is an AI-powered legal agreement analysis platform for everyday users. Users upload any legal agreement — employment contracts, NDAs, rental agreements, T&Cs, privacy policies, service agreements, enterprise licenses, loan agreements — and receive structured, plain-English insights instantly. No legal background required.

**Core insight:** Most people sign documents without fully understanding them. ClauseIQ fixes that.

**Target user:** Anyone who has ever signed a document without fully reading it — students, freshers, freelancers, working professionals, and anyone dealing with large or complex agreements.

**Out of scope (MVP):**

- Legal advice or jurisdiction-specific guidance
- E-signature functionality
- Enterprise contract portfolio management

---

## 2. Problem Statement

When a person receives an employment offer, rental agreement, franchise agreement, or terms & conditions document, they face four problems:

1. **Complexity** — Legal language is dense and hard to understand
2. **Risk blindness** — They don't know what clauses are dangerous
3. **Vague clauses** — Some clauses exist but are written so loosely they're meaningless or dangerous
4. **No structured view** — Everything is buried in paragraphs across dozens of pages

Existing solutions either require legal expertise (lawyers) or are generic (ChatGPT) — no structure, no persistence, no purpose-built experience for agreements.

---

## 3. Product Goals

- Instantly surface what matters in any agreement, large or small
- Present insights in a structured, scannable UI — not walls of text
- Store agreements persistently so users can revisit and chat anytime
- Ground every insight in the actual document — no hallucination
- Cite exact page, section, and line number for every finding
- Flag vague or ambiguous clauses and suggest questions to ask
- Keep costs low through smart AI invocation strategy

---

## 4. Supported Document Types

| Type       | Examples                                                                                     |
| ---------- | -------------------------------------------------------------------------------------------- |
| Employment | Offer letters, employment agreements, internship contracts                                   |
| NDA        | Non-disclosure agreements, confidentiality agreements                                        |
| Rental     | Lease agreements, rental contracts                                                           |
| Service    | Freelance contracts, consulting agreements, SOWs                                             |
| Platform   | Terms & Conditions, Privacy Policies, EULAs                                                  |
| Financial  | Loan agreements, mortgage documents, insurance policies                                      |
| Enterprise | Software license agreements, franchise agreements, partnership agreements, commercial leases |

---

## 5. Input Sources

| Source      | Details                                                    |
| ----------- | ---------------------------------------------------------- |
| PDF upload  | Most common format for formal agreements — small and large |
| DOCX upload | Common for employer-issued contracts                       |
| Paste text  | For T&Cs, email agreements, or any copied text             |

All inputs are normalized to plain text before entering the AI pipeline. The pipeline has no knowledge of the original source format — ingestion is completely decoupled from analysis.

**Text extraction libraries:**

- PDF → PyMuPDF (`fitz`)
- DOCX → `python-docx`
- Pasted text → accepted as-is, no extraction needed

---

## 6. Core Features

### 6.1 Agreement Import

Users upload one or more related files (PDF/DOCX, up to 5 files, 50MB each) or paste text. The system:

- Extracts and normalizes text from each file using PyMuPDF (PDF) or python-docx (DOCX)
- Concatenates all files into a single text blob with `[FILE: filename]` separators (see §10.3)
- Counts tokens on the combined text to determine processing path (full context vs RAG)
- Checks SHA-256 hash of the combined text for duplicate — skips analysis pipeline if match found
- Creates a single agreement record in DynamoDB with status `UPLOADED`
- Returns 200 immediately — user never waits

**Agreement title:** For a single file, defaults to the filename without extension. For multiple files, defaults to the first filename without extension (e.g. `"offer_letter_google"`). User can provide a custom title in the upload modal. Title is stored on the Agreement entity.

**Why concatenation:** All files are merged into one text blob before any analysis. Nova sees one document, produces one analysis, and all findings (risks, clauses, ambiguous items) cite exactly which file and page a clause came from. No new Lambda, no new schema entity, no new pipeline step — everything downstream is unchanged.

### 6.2 AI Analysis Pipeline (async)

Triggered automatically after upload. Runs entirely in the background. Every finding includes exact page number, section name, and line number where extractable.

- **AI Verdict** — Should you sign? (Sign / Proceed with Caution / High Risk) with a one-line reason
- **Clause Completeness Check** — Nova checks which standard clauses are present or missing for the detected document type. No hardcoded checklists in code — Nova uses per-type anchor lists embedded in the prompt (see §12.1) as a baseline, then adds any additional clauses it deems relevant. Each clause listed as ✅ Found (with location) or ❌ Missing.
- **Risk Analysis** — Clauses that are dangerous or unfavourable to the user. Each risk includes: title, severity (High / Medium / Low), plain-English explanation, exact citation. A risk is a clear-cut finding — "this clause is bad for you." Vague clauses that could go either way are NOT risks; they go in Ambiguous Clause Detection instead.
- **Ambiguous Clause Detection** — Clauses that exist in the document but are written so vaguely or loosely that their meaning or enforceability is unclear. Separate from risks. Each flagged with: the exact clause text, why it's ambiguous, and 2-3 specific questions the user should ask before signing. A clause can be ambiguous without being a risk (e.g. a vague bonus clause — unclear scope, not dangerous). A clause can be a risk without being ambiguous (e.g. a crystal-clear 2-year non-compete — perfectly legible, just unfavourable).
- **Financial Terms** — Salary, penalties, deposits, payment schedules, auto-renewal costs — anything money-related, with exact location
- **Key Dates / Timeline** — Effective date, probation end, renewal date, expiry — structured as a timeline
- **Plain English Summary** — Short, jargon-free overview of the entire agreement

### 6.3 AI Q&A (Chat)

After analysis, users can ask any question about their agreement:

- Answers grounded only in the uploaded document — never from general legal knowledge
- Explicit "This agreement does not specify that" when information is absent — never fabricates
- Every answer cites exact section, page number, and line number
- Full chat history stored per agreement — accessible anytime from sidebar
- For large documents (> 100k tokens): relevant chunks retrieved via RAG before answering

### 6.4 Ambiguous Clause Questions (Suggested Questions)

See §6.2 — Ambiguous Clause Detection. Each ambiguous clause card in the UI shows the exact clause text, why it is vague, and 2–3 specific questions the user should ask the other party before signing. Ambiguous clauses are strictly separate from risks — a clause is flagged here because it is unclear, not because it is harmful.

---

## 7. UI/UX Aesthetic & Layout (Claude Clone)

The frontend must visually replicate the Claude AI interface (Anthropic) to provide a premium, trustworthy experience. This is not just a color change; it dictates the entire layout structure.

**1. Three-Pane "Artifacts" Layout:**
- **Left Sidebar**: Collapsible. Contains Chat/Agreement history and a "New Analysis" button.
- **Center Panel (Primary)**: The Chat Interface. This is the main focus of the application. The user uploads agreements here and chats here.
- **Right Panel (Artifact View)**: Opens side-by-side with the chat when an analysis is completed or selected. This panel contains the structured ClauseIQ Analysis (Verdict, Risks, Ambiguous Clauses, Timeline, Financials). It is collapsible.

**2. Typography:**
- **Branding & Headers**: An elegant serif font (e.g., `Playfair Display`, `ui-serif`). Used for app titles, verdicts, and section headers.
- **Body & Chat**: A clean, highly legible sans-serif (e.g., `Inter`, `system-ui`). Used for all reading text, analysis details, and chat messages.

**3. Color Palette (Warm Minimalism):**
- **Light Mode**: Warm cream/off-white background (e.g., `#F9F8F6` or `#FDFDF9`), dark charcoal text (`#1a1918` — never pure black), and soft taupe borders.
- **Dark Mode**: Deep muted charcoal background (`#252423`), soft off-white text.
- **Accents**: Muted terracotta, peach, or soft ochre for primary actions (never bright generic blue/green).

**4. Component Styling (shadcn/ui overrides):**
- **Input Box**: Prominent, bottom-pinned, auto-expanding rounded rectangle with a soft drop-shadow. Attachment clip on the left, send arrow on the right.
- **Chat Messages**: Minimalist. No generic colored chat bubbles. AI messages are left-aligned with a logo icon. User messages are right-aligned (or left-aligned with initials).
- **Cards & Borders**: Generous padding, soft rounded corners (`rounded-xl` or `rounded-2xl`), and very subtle, low-contrast borders (`border-stone-200`).

---

## 8. Frontend Tech Stack

| Concern                 | Choice                       | Reason                                                                                         |
| ----------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------- |
| Framework               | React 18 + TypeScript        | Type safety catches frontend/backend contract mismatches at compile time                       |
| Build tool              | Vite                         | Fast dev server, minimal config, standard for modern React                                     |
| Styling                 | TailwindCSS                  | Utility-first, no separate CSS files to manage                                                 |
| Component library       | shadcn/ui                    | Accessible, unstyled components — no visual lock-in                                            |
| Data fetching + polling | TanStack Query (React Query) | `refetchInterval` makes polling trivial — one config to poll every 3s, auto-stops on condition |
| Routing                 | React Router v6              | Routes: `/` → redirect to `/dashboard`, `/dashboard`, `/agreements/:id`                        |
| HTTP client             | Axios                        | Interceptor attaches Cognito JWT to every outbound request automatically                       |
| Auth                    | aws-amplify                  | Handles Cognito token refresh, storage, hosted UI redirect, and sign-out                       |

---

## 9. Backend Tech Stack

| Concern         | Choice                        | Notes                                                                                                                                                                                                                    |
| --------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Framework       | FastAPI                       | Async, Pydantic validation, automatic OpenAPI docs                                                                                                                                                                       |
| Lambda adapter  | **Mangum**                    | **Required.** FastAPI is an ASGI app; Lambda speaks neither ASGI nor WSGI. Mangum wraps the FastAPI app as the Lambda handler: `handler = Mangum(app)`. Without Mangum the Lambda invocation never reaches FastAPI.      |
| JWT validation  | **python-jose[cryptography]** | Validates Cognito ID tokens on every request. See Section 17.1 for the exact validation flow.                                                                                                                            |
| AWS SDK         | boto3                         | S3, DynamoDB, SQS, Bedrock, Secrets Manager                                                                                                                                                                              |
| PDF extraction  | PyMuPDF (`fitz`)              | Page-by-page extraction with page markers (see Section 10.4)                                                                                                                                                             |
| DOCX extraction | python-docx                   | Extracts paragraph text from DOCX files                                                                                                                                                                                  |
| Token counting  | tiktoken (cl100k_base)        | Counts tokens at upload to decide full-context vs RAG path                                                                                                                                                               |
| IaC             | **AWS SAM**                   | Single `template.yaml` defines all Lambda functions, API Gateway, S3 triggers, and SQS bindings. SAM CLI handles local dev (`sam local start-api`) and deployment (`sam deploy`). See Section 21 for template structure. |

---

## 10. Architecture

### 10.1 Full System Architecture

```
React (Frontend)
        │
        ▼
  CloudFront + S3
  (static hosting)
        │
        ▼
   API Gateway
   (rate limiting,
    auth integration)
        │
        ▼
  Lambda (FastAPI)
   │          │
   ▼          ▼
  S3        DynamoDB
(raw files) (agreement
             metadata +
             status)
        │
        ▼ (S3 event trigger)
     Lambda
   (job dispatcher)
        │
        ▼
       SQS
   (job queue +
    DLQ for failures)
        │
        ▼
  Lambda (AI Worker)
        │
   Token count check
   ┌────┴────────────┐
   ▼                 ▼
< 100k tokens    > 100k tokens
Full context     Bedrock Knowledge
→ Nova           Bases (RAG)
                 → Nova
        │
        ▼
    DynamoDB
  (analysis results:
   verdict, risks,
   clauses, chat)
```

### 10.2 S3 Key Structure

All agreements — single file, multi-file bundle, or pasted text — are stored as a single extracted text file:

```
documents/{userId}/{agreementId}/original.txt

Examples:
  documents/user-abc123/agmt-xyz789/original.txt   ← single PDF, extracted text
  documents/user-abc123/agmt-def456/original.txt   ← 3-file bundle, concatenated text
  documents/user-abc123/agmt-ghi012/original.txt   ← pasted text
```

**Why always `.txt`:** FastAPI extracts text from every uploaded file before writing to S3. The AI Worker never deals with raw PDF or DOCX bytes — it always reads extracted plain text. Storing the extracted text (not the original binary) means the S3 key format is identical for all input types: single file, multi-file bundle, or paste. The S3 event notification fires on `documents/` prefix; the dispatcher extracts `userId` and `agreementId` from the key path and pushes the job to SQS. Nothing in the dispatcher or AI Worker changes for bundles.

### 10.3 Upload Flow

```
User uploads 1–5 files (PDF/DOCX) or pastes text
→ FastAPI validates each file:
    MIME type + extension must be PDF or DOCX
    Each file ≤ 50MB
    Total files ≤ 5
    Text: non-empty string check only
→ Extracts and normalizes text from each input:
    PDF  → PyMuPDF page-by-page with [PAGE N] markers (see §10.4)
    DOCX → python-docx paragraph extraction
    Text → accepted as-is (no extraction step)
→ Concatenates all extracted texts into one blob:
    Single file or paste → text as-is
    Multiple files → joined with [FILE: filename] separators (see §10.3a)
→ Counts tokens on the combined text (tiktoken, cl100k_base)
→ Computes SHA-256 hash of the combined text (UTF-8 encoded)
→ Checks DynamoDB Hash Index for existing hash
  → if match: creates Agreement record, copies existing analysis, returns 200 (no SQS job)
  → if no match: continues below
→ Saves combined text to S3 at documents/{userId}/{agreementId}/original.txt (UTF-8)
    ← REQUIRED: S3 write fires the event trigger for dispatcher Lambda
→ Creates Agreement record in DynamoDB (status = UPLOADED, file_count = N,
    source_filenames = ["offer_letter.pdf", "nda.pdf", ...])
→ Returns 200 immediately — user sees skeleton loaders + polling begins
→ S3 event triggers dispatcher Lambda
→ Dispatcher pushes job to SQS (unchanged — same message format as §10.6)
→ AI Worker picks up job → sets status = PROCESSING immediately
→ Runs full analysis pipeline on combined text (unchanged)
→ Stores all results in DynamoDB
→ Updates status = COMPLETED
→ Frontend polling detects COMPLETED → renders analysis cards
```

### 10.3a Multi-File Concatenation Format

When multiple files are uploaded, FastAPI joins their extracted texts with explicit file markers:

```
[FILE: offer_letter.pdf]
[PAGE 1]
This Employment Agreement ("Agreement") is entered into between...

[PAGE 2]
4.1 Compensation. The Employee shall receive a base salary...

[FILE: nda.pdf]
[PAGE 1]
NON-DISCLOSURE AGREEMENT entered into as of the date signed below...

[FILE: ip_assignment.docx]
Intellectual Property Assignment Agreement...
```

**Why this format works:**

- Nova reads the `[FILE: ...]` markers the same way it reads `[PAGE N]` markers — as structural context
- Every citation in the analysis output includes `file_name`, `section_name`, `page_number`, and `line_number` — users know exactly which document a finding came from
- The AI Worker, SQS message, Nova prompt, and DynamoDB schema are all completely unchanged — they see one text blob regardless of how many files contributed to it
- Deduplication works correctly — the hash is computed on the full combined text, so the same set of files uploaded in the same order always produces the same hash

### 10.4 PDF Text Extraction — Page Markers Required

PyMuPDF extracts text page by page. **All pages must be concatenated with explicit page markers** before the text is stored in S3 or passed to Nova. Without markers, Nova has no way to determine which text appears on which page, making all `page_number` fields in the output null or hallucinated.

**Required extraction format:**

```python
import fitz  # PyMuPDF

doc = fitz.open(stream=file_bytes, filetype="pdf")
pages = []
for i, page in enumerate(doc, start=1):
    text = page.get_text()
    pages.append(f"\n[PAGE {i}]\n{text}")
document_text = "".join(pages)
```

**Result:**

```
[PAGE 1]
This Employment Agreement ("Agreement") is entered into...

[PAGE 2]
4.1 Compensation. The Employee shall receive a base salary...
```

Nova reads these markers and uses them to populate `page_number` in its JSON output. This is how every citation in the analysis and Q&A maps back to a verifiable page in the original document.

**DOCX:** `python-docx` extracts paragraph text only — it has no concept of pages. For DOCX files, `page_number` and `line_number` will be `null` in Nova's output. This is acceptable — section citations remain accurate.

**Pasted text:** No page markers added. Page citations will be `null`. Section and line citations are still possible if the text contains section headings.

### 10.5 Processing Status Polling

The frontend has no persistent connection to the backend. Once upload returns 200, polling begins:

```
POST /agreements (upload)
→ Returns 200 + { agreementId, status: "UPLOADED" }
→ Frontend renders skeleton loaders

Every 3 seconds (via TanStack Query refetchInterval):
GET /agreements/:id
→ if status == "UPLOADED"    → continue polling
→ if status == "PROCESSING"  → continue polling
→ if status == "COMPLETED"   → call GET /agreements/:id/analysis, render cards, stop polling
→ if status == "FAILED"      → show error state with retry option, stop polling

Timeout: stop polling after 5 minutes, show "Taking longer than expected — refresh to check" message
```

**Why polling over WebSockets/SSE:** Analysis runs in a background Lambda — there is no persistent server process to push events from. Polling a single DynamoDB key lookup is stateless, cheap, and sufficient for a process completing in under 90 seconds for most documents.

### 10.6 SQS Message Format

The dispatcher Lambda pushes this JSON payload to SQS. The AI Worker expects exactly this structure:

```json
{
  "agreementId": "agmt-xyz789",
  "userId": "user-abc123",
  "s3_key": "documents/user-abc123/agmt-xyz789/original.txt",
  "token_count": 42000
}
```

- `token_count` is computed at upload time and passed through so the AI Worker does not need to re-fetch and re-count the document
- The AI Worker sets `agreement.status = PROCESSING` in DynamoDB before calling Nova

### 10.7 Bedrock Knowledge Base Strategy

**One Knowledge Base per agreement — never a shared KB.**

A shared KB would mix all users' document content with no retrieval isolation. Each agreement that exceeds the 100k token threshold gets its own dedicated KB.

**Vector store: Pinecone (serverless)**

Bedrock Knowledge Bases supports pluggable vector store backends. This project uses Pinecone serverless as the vector store. Reasons:

- Pinecone serverless is pay-per-use with a generous free tier (2GB storage, 1M reads/month) — zero fixed hourly cost, more than sufficient for all development and testing
- Pinecone is the most recognisable dedicated vector database name in the industry — strong interview signal
- The Bedrock KB API (`bedrock-agent`) supports Pinecone as a `storageConfiguration` type — the integration is first-class and fully managed
- No VPC, no collection provisioning, no encryption/network/access policies to manage — Pinecone credentials are a single Secrets Manager secret

**One shared Pinecone index, namespace-isolated per agreement.** Pinecone serverless does not bill per index — you create one index for the entire project and use the `agreementId` as the namespace for each document's vectors. Bedrock handles namespace management internally when given the index host. The Pinecone API key and index host URL are stored together in a single Secrets Manager secret (see §14 `PINECONE_SECRET_ARN`).

**Lifecycle:**

- **Created:** AI Worker creates a Bedrock KB backed by Pinecone and indexes the extracted document text when `token_count > 100k`
- **KB ID stored:** `bedrock_kb_id` attribute on the Agreement entity (null for full-context documents)
- **Used for:** every Q&A call on that agreement where `bedrock_kb_id` is not null
- **Deleted:** when user deletes the agreement via `DELETE /agreements/:id`

For documents under 100k tokens: no KB is created, `bedrock_kb_id = null`, full document text is passed directly to Nova in every call.

### 10.8 Analysis Pipeline (AI Worker)

```
Job received from SQS
→ Set agreement status = PROCESSING in DynamoDB immediately
→ Fetch document text from S3
→ if token_count > 100k: create Bedrock KB, index document, store KB ARN
→ Run analysis via Nova (see Section 12 for prompt + output schema):
   - AI Verdict
   - Clause Completeness Check
   - Risk Analysis (with page + section + line citations)
   - Ambiguous Clause Detection + Suggested Questions
   - Financial Terms
   - Key Dates / Timeline
   - Plain English Summary
→ Parse Nova JSON response
→ Write all results to DynamoDB (Analysis + Risk + Ambiguous Clause + Clause Check items)
→ Update agreement status = COMPLETED
→ On any unrecoverable error: set status = FAILED, log to CloudWatch
```

**Bedrock / Nova Lite API call format — exact specification:**

Nova Lite's API differs from Claude and from older Bedrock models. Use the wrong client or method and the call fails silently or throws an obscure error.

```python
import boto3
import json

client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

response = client.converse(                        # ← method is `converse`, NOT `invoke_model`
    modelId="amazon.nova-lite-v1:0",               # ← exact model ID
    messages=[
        {
            "role": "user",
            "content": [{"text": prompt}]          # ← Nova converse format
        }
    ]
)

# Extract text response
output_text = response["output"]["message"]["content"][0]["text"]
result = json.loads(output_text)
```

- **boto3 client:** `bedrock-runtime` (not `bedrock`)
- **Method:** `converse` (not `invoke_model` — that uses a different request/response format)
- **Model ID:** `amazon.nova-lite-v1:0`
- **Response path:** `response["output"]["message"]["content"][0]["text"]`

### 10.9 Q&A Flow

```
User asks question
→ Fetch agreement from DynamoDB — verify ownership
→ if bedrock_kb_id is null (token_count < 100k):
     fetch document text from S3
     send full text + question → Nova
→ if bedrock_kb_id is set (token_count > 100k):
     retrieve relevant chunks from Bedrock KB → Nova
→ Parse Nova JSON response (answer + citations)
→ Store Q&A pair in DynamoDB (Chat Message entity)
→ Return answer + citations to frontend
```

### 10.10 Document Deduplication

```
Upload received
→ Extract and concatenate all file texts (same process as §10.3)
→ Compute SHA-256 hash of the combined extracted text (UTF-8 encoded):
    Single file → hash of extracted plain text
    Multiple files → hash of full concatenated blob (including [FILE:] markers)
    Pasted text → hash of the raw input string
→ Query DynamoDB Hash Index (PK: HASH#<sha256>)
→ if match found:
     create new Agreement record for this user (new agreementId)
     copy all existing Analysis + Risk + Ambiguous Clause + Clause Check items to new agreementId
     set status = COMPLETED immediately
     return 200 — zero Nova calls, instant result for user
→ if no match:
     proceed with full analysis pipeline
     write HASH#<sha256> to Hash Index on completion
```

**Scope:** Hash lookup is global across all users. Two different users uploading the same Spotify T&Cs share one analysis run — each user still gets their own Agreement record and agreementId (their sidebar entry is independent), but Nova is called only once ever for that document.

### 10.11 User Record Creation

**When:** A DynamoDB User record is created exactly once per user — at signup, via a **Cognito Post-Confirmation Lambda trigger**. It is never created in the FastAPI upload flow.

**How it works:**

1. User completes Cognito signup and verifies their email
2. Cognito fires the **Post-Confirmation** trigger, invoking a dedicated Lambda (`user-initializer`)
3. The Lambda writes the User entity to DynamoDB:
   ```json
   {
     "PK": "USER#<cognito-sub>",
     "SK": "#METADATA",
     "name": "<from Cognito attributes>",
     "email": "<from Cognito attributes>",
     "cognito_id": "<sub>",
     "created_at": "<ISO timestamp>"
   }
   ```
4. If the write fails, the Lambda logs to CloudWatch. The user can still log in — the User record is only required for agreement ownership lookups, not authentication.

**What NOT to do:** Do not create the User record in `POST /agreements`. By the time the user uploads, they are already confirmed — the record must already exist. Attempting creation at upload time leads to race conditions and duplicate-write errors.

---

## 11. API Contract

**Base URL:** `https://api.clauseiq.com/v1`

**Auth:** All endpoints require `Authorization: Bearer <cognito_id_token>` header. FastAPI validates the token against the Cognito User Pool on every request. Requests without a valid token return `401`.

**CORS:** API Gateway configured to allow origin `https://clauseiq.com` (and `http://localhost:5173` for local dev), methods GET/POST/DELETE, header Authorization.

---

### GET /health

Liveness check. No auth required. Used by GitHub Actions deploy verification and monitoring.

**Response 200:**

```json
{ "status": "ok" }
```

No error responses — if the Lambda is unreachable, API Gateway returns a 502 or 504.

---

### POST /agreements

Upload a new agreement (one or more related files, or pasted text) and trigger analysis.

**Request:** `multipart/form-data`
| Field | Type | Required | Notes |
|---|---|---|---|
| `files` | file[] | conditional | One or more PDF or DOCX files. Up to 5 files, 50MB each. Required if `text` not provided. |
| `text` | string | conditional | Pasted plain text. Required if `files` not provided. |
| `title` | string | optional | Custom name. Defaults to first filename (single or multi-file) or "Untitled Agreement" (paste). |

Multiple files are accepted as repeated `files` fields in the multipart form (standard HTML multi-file input behaviour). FastAPI reads them as `List[UploadFile]`.

**Response 200:**

```json
{
  "agreementId": "agmt-xyz789",
  "title": "Google Offer Package",
  "file_count": 3,
  "source_filenames": ["offer_letter.pdf", "nda.pdf", "ip_assignment.docx"],
  "status": "UPLOADED",
  "created_at": "2025-03-15T10:23:00Z"
}
```

`file_count` is 1 for single-file uploads and null for pasted text. `source_filenames` is null for pasted text.

**Error responses:**

```
400 — { "error": "Provide either files or text, not both" }
400 — { "error": "No files or text provided" }
400 — { "error": "Too many files — maximum 5 per upload" }
413 — { "error": "File exceeds 50MB limit", "filename": "large_contract.pdf" }
415 — { "error": "Unsupported file type. Upload PDF or DOCX only.", "filename": "contract.xlsx" }
```

---

### GET /agreements

List all agreements for the authenticated user. Used to populate the sidebar.

**Response 200:**

```json
{
  "agreements": [
    {
      "agreementId": "agmt-xyz789",
      "title": "Google Offer Letter",
      "document_types": ["employment", "nda", "enterprise"],
      "status": "COMPLETED",
      "overall_risk": "medium",
      "created_at": "2025-03-15T10:23:00Z"
    },
    {
      "agreementId": "agmt-abc123",
      "title": "Spotify T&Cs",
      "document_types": ["platform"],
      "status": "PROCESSING",
      "overall_risk": null,
      "created_at": "2025-03-15T11:00:00Z"
    }
  ]
}
```

`overall_risk` is `null` until status is `COMPLETED`. `document_types` is `null` until the AI Worker detects them — set to an array on `COMPLETED`.

---

### GET /agreements/:id

Get a single agreement's metadata and current status. This is the polling endpoint.

**Response 200:**

```json
{
  "agreementId": "agmt-xyz789",
  "title": "Google Offer Letter",
  "document_types": ["employment", "nda"],
  "status": "PROCESSING",
  "overall_risk": null,
  "created_at": "2025-03-15T10:23:00Z"
}
```

`status` values: `UPLOADED` | `PROCESSING` | `COMPLETED` | `FAILED`

```
403 — { "error": "Access denied" }       (agreement belongs to another user)
404 — { "error": "Agreement not found" }
```

---

### GET /agreements/:id/analysis

Get the full analysis result. Only call after status == `COMPLETED`.

**Response 200:**

```json
{
  "verdict": {
    "decision": "Proceed with Caution",
    "reason": "Non-compete clause is overly broad and may restrict future employment."
  },
  "overall_risk": "medium",
  "summary": "This employment package consists of three documents: an offer letter, NDA, and IP assignment...",
  "risks": [
    {
      "riskId": "risk-001",
      "title": "Overly Broad Non-Compete",
      "severity": "High",
      "explanation": "Section 12.1 prohibits working at any tech company for 2 years after leaving.",
      "file_name": "nda.pdf",
      "section_name": "12.1 Non-Compete",
      "page_number": 8,
      "line_number": 142
    }
  ],
  "ambiguous_clauses": [
    {
      "ambiguousId": "ambig-001",
      "title": "Vague Termination Clause",
      "clause_text": "Employment may be terminated at the discretion of the employer.",
      "explanation": "This clause gives the employer unrestricted termination rights with no defined grounds, process, or notice requirement.",
      "file_name": "offer_letter.pdf",
      "section_name": "8.2 Termination",
      "page_number": 5,
      "line_number": 23,
      "suggested_questions": [
        "What specific grounds constitute termination for cause?",
        "Is there a performance improvement process before termination?",
        "What severance is provided if terminated without cause?"
      ]
    }
  ],
  "clauses": [
    {
      "clauseId": "clause-001",
      "clause_name": "Termination Clause",
      "status": "FOUND",
      "file_name": "offer_letter.pdf",
      "section_name": "8. Termination",
      "page_number": 5,
      "line_number": 89
    },
    {
      "clauseId": "clause-002",
      "clause_name": "Severance Terms",
      "status": "MISSING",
      "file_name": null,
      "section_name": null,
      "page_number": null,
      "line_number": null
    }
  ],
  "financials": [
    {
      "item": "Base Salary",
      "value": "₹18,00,000 per annum",
      "file_name": "offer_letter.pdf",
      "section_name": "4.1 Compensation",
      "page_number": 3,
      "line_number": 47
    }
  ],
  "timeline": [
    {
      "event": "Start Date",
      "date": "2025-04-01",
      "file_name": "offer_letter.pdf",
      "section_name": "2.1 Commencement",
      "page_number": 1,
      "line_number": 12
    },
    {
      "event": "Probation End",
      "date": "2025-07-01",
      "file_name": "offer_letter.pdf",
      "section_name": "3.1 Probation Period",
      "page_number": 2,
      "line_number": 34
    }
  ]
}
```

```
404 — { "error": "Analysis not found" }
409 — { "error": "Analysis not yet complete", "status": "PROCESSING" }
```

---

### DELETE /agreements/:id

Delete an agreement, its full analysis, chat history, and associated Bedrock KB (if any).

**Response 200:**

```json
{ "message": "Agreement deleted" }
```

```
403 — { "error": "Access denied" }
404 — { "error": "Agreement not found" }
```

---

### POST /agreements/:id/chat

Ask a question about a specific agreement.

**Request:** `application/json`

```json
{
  "question": "What is the notice period for resignation?"
}
```

**Response 200:**

```json
{
  "messageId": "chat-1710498234567",
  "question": "What is the notice period for resignation?",
  "answer": "The notice period is 60 days as stated in Section 9.2.",
  "citations": [
    {
      "file_name": "offer_letter.pdf",
      "section_name": "9.2 Notice Period",
      "page_number": 6,
      "line_number": 103
    }
  ],
  "found_in_document": true
}
```

If the information is not in the document:

```json
{
  "messageId": "chat-1710498234600",
  "question": "What is the bonus structure?",
  "answer": "This agreement does not specify a bonus structure.",
  "citations": [],
  "found_in_document": false
}
```

```
404 — { "error": "Agreement not found" }
409 — { "error": "Analysis must be complete before chatting" }
```

---

### GET /agreements/:id/chat

Get full chat history for an agreement, sorted oldest to newest.

**Response 200:**

```json
{
  "messages": [
    {
      "messageId": "chat-1710498234567",
      "question": "What is the notice period?",
      "answer": "60 days as per Section 9.2.",
      "citations": [
        {
          "file_name": "offer_letter.pdf",
          "section_name": "9.2 Notice Period",
          "page_number": 6,
          "line_number": 103
        }
      ],
      "found_in_document": true,
      "created_at": "2025-03-15T11:05:34Z"
    }
  ]
}
```

---

## 12. Nova Prompt & Output Schema

The AI Worker sends **one prompt** to Nova that returns **one JSON object** covering all analysis dimensions. Nova must never return free text — the worker parses the JSON directly and writes it to DynamoDB.

### 12.1 Analysis Prompt

**Four design decisions embedded in this prompt:**

**1. `document_types` is detected by Nova, not passed as input.** The preamble says "legal agreement" because the types are unknown at call time. Nova detects all types present and returns them as a JSON array — the first field in the output. The AI Worker stores this array on the Agreement entity after parsing. Never pass `{document_types}` in the prompt — it is an output, not an input. For single-document uploads this is typically a one-element array (e.g. `["employment"]`). For bundles it may contain multiple types (e.g. `["employment", "nda", "enterprise"]`).

**2. Risks and ambiguous clauses are separated into two distinct analytical passes.** A risk is a clause that is demonstrably unfavourable to the user (clear finding). An ambiguous clause is one that exists but is written so vaguely its meaning or enforceability is unclear (open question). These require different reasoning and produce different UI output. Asking Nova to make both judgments in one pass produces muddled results — the prompt separates them explicitly.

**3. Clause anchor lists are embedded in the prompt, not hardcoded in application code.** Each document type has a baseline list of clauses Nova must always check. Nova can and should add additional clauses it finds relevant beyond the anchor list. The anchor list exists purely to prevent run-to-run inconsistency — without it, Nova omits different clauses on every call for the same document type.

**4. `file_name` is included in every citation field.** For single-file uploads this is the one filename. For multi-file bundles it tells the user exactly which document a risk, clause, or finding came from. Nova reads the `[FILE: filename]` markers in the text (see §10.3a) and uses them to populate `file_name`. Never omit `file_name` — it defaults to null for pasted text but must always be present in the schema.

```
You are a legal document analyst. Analyze the following legal agreement and return ONLY a valid JSON object. No preamble, no explanation, no markdown formatting, no code fences. Just the raw JSON.

The document text may contain [FILE: filename] markers indicating multiple related files that form one agreement package. Treat the entire text as one cohesive agreement. For every finding, record which file it came from using the file_name field.

Document text:
{document_text}

Return this exact JSON structure:

{
  "document_types": ["<employment | nda | rental | service | platform | financial | enterprise>"],
  "verdict": {
    "decision": "<Sign | Proceed with Caution | High Risk>",
    "reason": "<one sentence explaining the verdict>"
  },
  "overall_risk": "<low | medium | high>",
  "summary": "<3-5 sentence plain English overview of the entire agreement package>",
  "risks": [
    {
      "title": "<short descriptive title>",
      "severity": "<High | Medium | Low>",
      "explanation": "<plain English explanation of why this clause is harmful or unfavourable to the signing party, 1-2 sentences>",
      "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
      "section_name": "<exact section number and name, e.g. '12.1 Non-Compete'>",
      "page_number": <integer, or null if not determinable>,
      "line_number": <integer, or null if not determinable>
    }
  ],
  "ambiguous_clauses": [
    {
      "title": "<short descriptive title of the clause>",
      "clause_text": "<exact verbatim text of the clause as written in the document>",
      "explanation": "<why this clause is vague, one-sided, or unclear — 1-2 sentences>",
      "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
      "section_name": "<exact section number and name>",
      "page_number": <integer, or null if not determinable>,
      "line_number": <integer, or null if not determinable>,
      "suggested_questions": ["<question 1>", "<question 2>", "<question 3>"]
    }
  ],
  "clauses": [
    {
      "clause_name": "<clause name>",
      "status": "<FOUND | MISSING>",
      "file_name": "<filename if FOUND, else null>",
      "section_name": "<exact section if FOUND, else null>",
      "page_number": <integer if FOUND, else null>,
      "line_number": <integer if FOUND, else null>
    }
  ],
  "financials": [
    {
      "item": "<what this financial term represents>",
      "value": "<exact value or amount as written in the document>",
      "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
      "section_name": "<section name>",
      "page_number": <integer or null>,
      "line_number": <integer or null>
    }
  ],
  "timeline": [
    {
      "event": "<name of the date or deadline>",
      "date": "<date exactly as written in the document>",
      "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
      "section_name": "<section name>",
      "page_number": <integer or null>,
      "line_number": <integer or null>
    }
  ]
}

CLAUSE ANCHOR LISTS — for the "clauses" array:

First, detect the document_type. Then check every clause in the anchor list for that type. Report each as FOUND (with location) or MISSING. You may add additional clauses beyond this list if you find them relevant to this specific document — but you must check every anchor clause first.

employment: Compensation, Probation Period, Working Hours, Leave Policy, Termination Clause, Notice Period, Severance Terms, Non-Compete, Non-Solicitation, Confidentiality / NDA, Intellectual Property Assignment, Governing Law, Dispute Resolution, Benefits, Bonus / Variable Pay

nda: Definition of Confidential Information, Exclusions from Confidentiality, Permitted Disclosures, Obligations of Receiving Party, Term / Duration, Return or Destruction of Information, Remedies for Breach, Governing Law, Mutual vs Unilateral Scope

rental: Rent Amount and Due Date, Security Deposit, Lease Term, Renewal Terms, Maintenance Responsibilities, Pet Policy, Subletting Policy, Early Termination, Notice Period, Utilities Responsibility, Entry by Landlord, Governing Law

service: Scope of Work, Deliverables, Payment Terms, Payment Schedule, Late Payment Penalties, Intellectual Property Ownership, Confidentiality, Term and Termination, Termination for Convenience, Limitation of Liability, Indemnification, Governing Law, Dispute Resolution

platform: Acceptance of Terms, User Account Terms, Prohibited Uses, Content Ownership, Data Collection and Use, Third-Party Sharing, Cookies Policy, Termination of Account, Limitation of Liability, Dispute Resolution / Arbitration Clause, Governing Law, Changes to Terms

financial: Loan Amount, Interest Rate, Repayment Schedule, Prepayment Penalty, Late Payment Fee, Collateral / Security, Default Conditions, Acceleration Clause, Governing Law

enterprise: Scope of License / Services, Fees and Payment Terms, Term and Renewal, Termination for Cause, Termination for Convenience, Limitation of Liability, Indemnification, Intellectual Property Ownership, Confidentiality, SLA / Service Levels, Governing Law, Dispute Resolution, Assignment

RULES:
1. Return ONLY the JSON object. Nothing before or after it.
2. Never fabricate information not present in the document. If a field cannot be determined, use null.
3. page_number and line_number must only be populated when you can locate them with certainty.
4. risks: only include clauses that are clearly harmful or unfavourable to the signing party. A clause that is merely vague or unclear is NOT a risk — it belongs in ambiguous_clauses instead.
5. ambiguous_clauses: only include clauses that actually exist in the document but are written so vaguely or loosely that their meaning, scope, or enforceability is genuinely unclear. A clause can be ambiguous without being a risk. Include the verbatim clause text. Write 2-3 specific questions the user should ask the other party before signing.
6. A clause must not appear in both risks and ambiguous_clauses. Make a judgment: is the problem that this clause is clearly bad (risk), or that this clause is unclear (ambiguous)?
7. risks must be [] if no clear risks exist.
8. ambiguous_clauses must be [] if no ambiguous clauses exist.
9. financials must be [] if no financial terms exist in the document.
10. timeline must be [] if no dates or deadlines exist in the document.
11. overall_risk must reflect the aggregate severity of all risks found — not ambiguous clauses.
12. For clauses: check every anchor clause for ALL types in document_types. If document_types is ["employment", "nda"], run the full anchor list for employment AND the full anchor list for nda — combined into a single clauses array. Add extras you find relevant beyond the anchor lists. Never skip anchor clauses for any detected type.
13. file_name: populate from the nearest preceding [FILE: filename] marker. If no markers exist (single paste), set file_name to null for all findings.
```

### 12.2 Q&A Prompt

```
You are a legal document assistant. Answer the user's question based ONLY on the provided agreement text. Do not use any external legal knowledge.

Agreement text:
{document_text_or_retrieved_chunks}

User question: {question}

Return ONLY valid JSON. No preamble, no markdown, no code fences.

{
  "answer": "<plain English answer to the question>",
  "citations": [
    {
      "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
      "section_name": "<section name>",
      "page_number": <integer or null>,
      "line_number": <integer or null>
    }
  ],
  "found_in_document": <true | false>
}

Rules:
1. If the answer is in the document: provide it clearly and cite the exact file, section, page, and line.
2. If the answer is NOT in the document: set answer to "This agreement does not specify that.", citations to [], found_in_document to false.
3. Never guess or infer beyond what the document explicitly states.
4. Return ONLY the JSON object. Nothing else.
5. file_name: populate from the nearest preceding [FILE: filename] marker. If no markers exist (single paste), set file_name to null.
```

### 12.3 Error Handling for Nova Responses

The AI Worker must handle malformed Nova output:

- Attempt `json.loads()` on the response
- If parsing fails: retry the prompt once with an explicit instruction to fix JSON syntax
- If second attempt fails: set agreement status to `FAILED`, log the raw response to CloudWatch
- Never write partial/unparsed data to DynamoDB

---

## 13. AWS Services

| Service                        | Role                                             | Why This Service                                                                                                                                                                                                                                                                                               |
| ------------------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **S3** (files)                 | Store raw uploaded documents                     | Optimized for large binary objects. Databases aren't.                                                                                                                                                                                                                                                          |
| **S3** (frontend)              | Host React build                                 | Standard static hosting — zero server management                                                                                                                                                                                                                                                               |
| **CloudFront**                 | Serve React frontend globally                    | CDN for fast delivery. Pairs naturally with S3 hosting.                                                                                                                                                                                                                                                        |
| **API Gateway**                | HTTP entry point                                 | Managed routing, rate limiting, Cognito auth integration out of the box                                                                                                                                                                                                                                        |
| **Lambda** (API)               | FastAPI request handlers                         | Serverless — scales to zero, no idle cost                                                                                                                                                                                                                                                                      |
| **Lambda** (dispatcher)        | S3 event → SQS                                   | Lightweight — just pushes job to queue                                                                                                                                                                                                                                                                         |
| **Lambda** (AI worker)         | Runs analysis pipeline                           | Handles Bedrock calls within 10-min timeout (600s) for all target document sizes                                                                                                                                                                                                                               |
| **SQS + DLQ**                  | Decouple upload from analysis                    | Upload acknowledges instantly. Failed jobs retry automatically. Dead letter queue captures persistent failures.                                                                                                                                                                                                |
| **DynamoDB**                   | All structured data                              | Access patterns are entirely key-based. No joins needed. Single-digit ms reads. Serverless pricing. No VPC.                                                                                                                                                                                                    |
| **Bedrock (Amazon Nova Lite)** | AI analysis + Q&A                                | Managed LLM inference. Extremely cost-effective — ~$0.001 per analysis. No model hosting overhead.                                                                                                                                                                                                             |
| **Bedrock Knowledge Bases**    | RAG for large documents (> 100k tokens)          | Managed embeddings + vector retrieval. One KB per agreement. Bedrock handles chunking and embedding generation — no custom vector infrastructure.                                                                                                                                                              |
| **Pinecone (serverless)**      | Vector store backend for Bedrock Knowledge Bases | Stores embeddings generated by Bedrock. Serverless pay-per-use with generous free tier — zero fixed hourly cost during development. One shared index, namespace-isolated per `agreementId`. Industry-standard dedicated vector DB — first-class Bedrock KB integration. Credentials stored in Secrets Manager. |
| **Cognito**                    | Authentication                                   | Production-ready JWT auth out of the box. Password reset, email verification, refresh tokens — all handled.                                                                                                                                                                                                    |
| **Secrets Manager**            | Store credentials                                | Never hardcode secrets. IAM-integrated. Rotates automatically.                                                                                                                                                                                                                                                 |

### Lambda Configuration

| Lambda        | Memory  | Timeout       | Reason                                                                 |
| ------------- | ------- | ------------- | ---------------------------------------------------------------------- |
| API (FastAPI) | 256 MB  | 30s           | Handles upload I/O, DynamoDB reads, Cognito JWT verification           |
| Dispatcher    | 128 MB  | 10s           | Reads S3 event, pushes one message to SQS — minimal work               |
| AI Worker     | 1024 MB | 600s (10 min) | Calls Nova for large documents; needs headroom for Bedrock KB indexing |

---

## 14. Environment Variables

Each Lambda reads its configuration from environment variables. These names are the **canonical reference** — the SAM template (Section 21) sets them, and the Lambda code reads them. Any mismatch between template and code causes a runtime KeyError.

| Variable                | Used By               | Value / Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AWS_REGION`            | All                   | AWS region (e.g. `ap-south-1`). Already set by Lambda runtime — do not override.                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `DYNAMODB_TABLE_NAME`   | All                   | Single DynamoDB table name (e.g. `clauseiq-prod`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `S3_BUCKET_NAME`        | API Lambda, AI Worker | S3 bucket for raw documents (e.g. `clauseiq-documents-prod`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `SQS_QUEUE_URL`         | Dispatcher            | Full SQS queue URL                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `COGNITO_USER_POOL_ID`  | API Lambda            | Cognito User Pool ID (e.g. `ap-south-1_XXXXXXXXX`) — used to construct JWKS URL                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `COGNITO_APP_CLIENT_ID` | API Lambda            | Cognito App Client ID — validated as `aud` claim in JWT                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `BEDROCK_REGION`        | AI Worker             | Region where Bedrock Nova Lite is available. **This is NOT the same as the primary stack region.** Nova Lite is only available in `us-east-1`, `us-west-2`, and `eu-west-1`. **Always set this to `us-east-1`** regardless of where the rest of the stack is deployed (e.g. `ap-south-1`). Cross-region Bedrock calls add ~50ms latency and are fully supported. Do **not** use `!Ref AWS::Region` here — hardcode `us-east-1` in the SAM template.                                                                            |
| `PINECONE_SECRET_ARN`   | AI Worker             | ARN of the Secrets Manager secret containing the Pinecone API key and index host URL. The AI Worker fetches this secret at runtime via `secretsmanager:GetSecretValue` and passes the values to the Bedrock KB `storageConfiguration`. Secret JSON format: `{"api_key": "pc-xxxx", "index_host": "https://clauseiq-xxxxx.svc.pinecone.io"}`. Create your Pinecone account at pinecone.io, create one serverless index (dimension: 1536, metric: cosine, cloud: AWS, region: us-east-1), then store both values in this secret. |
| `ENVIRONMENT`           | All                   | `dev` or `prod` — controls CORS origin and log verbosity                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |

**Secrets (not env vars):** Database passwords, API keys, and other credentials are stored in AWS Secrets Manager — never as environment variables. The Lambda IAM role grants `secretsmanager:GetSecretValue` access.

---

## 15. Architectural Decisions (ADRs)

### ADR-1: DynamoDB over PostgreSQL

**Decision:** DynamoDB

**Reason:** ClauseIQ's access patterns are entirely key-based — get all agreements for a user, get analysis for an agreement ID, get chat history for an agreement. There are no complex joins, no cross-table analytics, no relational queries in the core user flow. DynamoDB's single-digit millisecond lookups and serverless pricing model fit perfectly. PostgreSQL would introduce a VPC, subnet configuration, connection pooling, and operational overhead that adds zero value for these access patterns. Keeping the stack truly serverless also means no idle database cost.

**Trade-off accepted:** Cross-agreement analytics (average risk score by document type) would be cleaner in SQL. That's a Phase 2 consideration if needed.

---

### ADR-2: FastAPI over Flask / Django / Spring Boot

**Decision:** FastAPI

**Reason:** ClauseIQ is AI-first. The backend spends most of its time calling AWS services, processing files, managing async jobs, and returning JSON. FastAPI's native async support, automatic Swagger UI, Pydantic validation, and Python's AI/AWS ecosystem (boto3, PyMuPDF, python-docx) make it the natural fit. Django brings an ORM and admin panel we don't need. Flask requires rebuilding validation, async support, and docs from scratch — essentially reimplementing FastAPI. Spring Boot would require mixing Java and Python services to access the richest AI libraries.

---

### ADR-3: Async Processing via SQS + Lambda

**Decision:** Lambda → SQS → Lambda (AI Worker)

**Reason:** Nova inference for full document analysis takes 15-45 seconds. Keeping the API waiting would destroy UX and make the system fragile under load. Instead, upload is acknowledged in under 2 seconds, the job is queued in SQS, and a dedicated Lambda worker processes it independently. Failed jobs automatically return to the queue for retry. A dead letter queue captures persistent failures for debugging. API layer and AI worker scale completely independently.

**Why not Docker worker:** Lambda natively polls SQS. Analysis completes well within Lambda's 15-minute timeout even for large documents. A persistent Docker worker requires managing a long-running process and separate deployment infrastructure — operational complexity with no benefit for this use case.

---

### ADR-4: Hybrid AI Strategy (Full Context + RAG via Bedrock KB + Pinecone)

**Decision:** Automatic token-based switching — invisible to user

**Reason:** For documents under 100k tokens (~150 pages), the full document text is included in every Bedrock call. This gives superior answer quality compared to RAG for typical agreements — the model sees everything, no risk of retrieving the wrong chunk or missing critical context. For documents exceeding 100k tokens (large enterprise licenses, franchise agreements, mortgage documents), Bedrock Knowledge Bases handles chunking, embedding generation, and semantic retrieval automatically. Pinecone serverless stores the resulting vectors — chosen over OpenSearch Serverless because it has zero fixed hourly cost and is the most recognisable dedicated vector DB in the industry. The user experiences no difference — switching is entirely invisible.

**Why not RAG always:** RAG adds retrieval complexity and can miss context for small documents where the entire agreement fits in the window. Full context is strictly better quality when it fits.

**Interview answer:** "The system automatically detects document size and switches between full-context inference for standard agreements and a RAG pipeline for larger documents. RAG uses Bedrock Knowledge Bases for chunking and embedding generation, backed by Pinecone serverless as the vector store. For most everyday agreements, full context gives better quality. RAG activates for large enterprise contracts where documents exceed the model's context window."

---

### ADR-5: Analyze Once, Cache in DynamoDB

**Decision:** Run full analysis once at upload, persist all results permanently

**Reason:** Verdict, risks, clause completeness, financial terms, timeline, summary — these are deterministic. The same document always produces the same output. Calling Nova on every page load would be expensive, slow, and completely unnecessary. We pay for inference once and serve from DynamoDB forever. Only Q&A hits Nova at runtime since user questions are unpredictable and dynamic.

**Result:** A user can visit their agreement dashboard 1000 times — zero additional Nova calls. The entire cost of analysis is paid once at upload.

---

### ADR-6: Cognito over Custom Auth

**Decision:** Amazon Cognito

**Reason:** Authentication is solved infrastructure, not a product differentiator. Building JWT issuance, bcrypt hashing, refresh token rotation, password reset flows, and email verification from scratch wastes 2-3 weeks on something that isn't ClauseIQ's core value. Cognito provides all of this production-ready, makes FastAPI completely stateless (JWT verification only — no session storage), and supports MFA and social login in future with zero additional backend work.

---

### ADR-7: No Redis

**Decision:** Rejected

**Reason:** Analysis results are already persisted in DynamoDB — no repeated computation to cache. Cognito manages authentication state. There is no remaining caching problem for Redis to solve. Adding it would increase architecture complexity and cost with zero tangible benefit.

---

### ADR-8: Amazon Nova Lite over Claude Haiku

**Decision:** Amazon Nova Lite

**Reason:** Nova Lite is significantly cheaper than Claude Haiku ($0.06/million input tokens vs $0.80/million) while delivering sufficient capability for legal document analysis tasks. Estimated cost per agreement analysis: ~$0.001. Entire build and testing phase estimated under $5. Nova Lite supports Bedrock Knowledge Bases for the RAG pipeline.

---

### ADR-9: Document Deduplication via SHA-256 Hashing

**Decision:** Hash every uploaded document, reuse existing analysis if hash matches

**Reason:** If a user uploads the same document twice (or two users upload the same public T&Cs), there is no reason to run analysis again. SHA-256 hash is computed on upload, checked against a global DynamoDB Hash Index. On match, a new Agreement record is created for the uploading user (they get their own agreementId and sidebar entry), but the analysis pipeline is skipped entirely — existing analysis results are copied to the new agreementId. Nova is never called again for that document, ever. This is especially valuable for common documents like Spotify T&Cs or standard employment templates.

**Hash lookup is global across users:** Two different users uploading the same document share one analysis run. Each user still gets independent ownership (their own agreementId, title, and sidebar entry). Only Nova inference is shared.

---

### ADR-10: Exact Citations (Page + Section + Line)

**Decision:** Every AI finding must include exact document location

**Reason:** Vague references like "somewhere in the document" destroy trust. Every risk, missing element, ambiguous clause, and Q&A answer includes the exact section name, page number, and line number where extractable. Users can verify every finding directly in their original document. This makes ClauseIQ's output traceable and trustworthy rather than opaque.

---

### ADR-11: Multi-File Bundle via Concatenation, Not Separate Pipelines

**Decision:** Merge all uploaded files into one text blob with `[FILE: filename]` separators before analysis

**Alternatives considered:**

- **Separate pipeline per file** — Each file gets its own agreementId, its own analysis run, its own sidebar entry. Simple to implement but misses the entire point: a non-compete in the NDA and an IP clause in the offer letter may conflict. Separate analyses never see each other. User gets 3 sidebar entries when they wanted one view.
- **New multi-doc entity type** — New DynamoDB entities, new API endpoints, new Worker logic, new prompt design. High complexity, duplicates everything that already works.
- **Concatenation (chosen)** — FastAPI extracts and concatenates all files at upload time, separated by `[FILE: filename]` markers. S3 receives one `original.txt`. SQS gets one message. The AI Worker runs one analysis. Nova reads the markers as structural context, the same way it reads `[PAGE N]` markers. Every citation includes `file_name` so the user knows which document a finding came from. Zero changes to the dispatcher, AI Worker, SQS message format, or core Nova prompt logic.

**Trade-off accepted:** If a bundle exceeds 100k tokens combined, it routes to RAG. The Bedrock KB indexes the full concatenated text — RAG retrieval still works because the markers survive chunking and Nova's retrieved chunks include the `[FILE:]` context. For very large bundles this is the correct path anyway.

**Why 5-file limit:** Practical ceiling for real employment/rental/service packages. Beyond 5 files the combined token count reliably exceeds 100k and hits RAG. The limit also keeps the upload UI simple and validation logic trivial.

---

## 16. DynamoDB Schema (Single Table Design)

**8 entity types. Nothing more.**

| Entity           | PK                        | SK                        | Attributes                                                                                                                                     |
| ---------------- | ------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| User             | `USER#<userId>`           | `#METADATA`               | name, email, cognito_id, created_at                                                                                                            |
| Agreement        | `USER#<userId>`           | `AGREEMENT#<agreementId>` | title, document_types (JSON array), s3_key, status, document_hash, token_count, bedrock_kb_id, file_count, source_filenames (JSON), created_at |
| Analysis         | `AGREEMENT#<agreementId>` | `#ANALYSIS`               | verdict (JSON), overall_risk, summary, financials (JSON), timeline (JSON), completed_at                                                        |
| Risk             | `AGREEMENT#<agreementId>` | `RISK#<uuid>`             | title, severity, explanation, file_name, section_name, page_number, line_number                                                                |
| Ambiguous Clause | `AGREEMENT#<agreementId>` | `AMBIGUOUS#<uuid>`        | title, clause_text, explanation, file_name, section_name, page_number, line_number, suggested_questions (JSON)                                 |
| Clause Check     | `AGREEMENT#<agreementId>` | `CLAUSE#<uuid>`           | clause_name, status (FOUND / MISSING), file_name, section_name, page_number, line_number                                                       |
| Chat Message     | `AGREEMENT#<agreementId>` | `CHAT#<epoch_ms>`         | question, answer, citations (JSON), found_in_document, created_at                                                                              |
| Hash Index       | `HASH#<sha256>`           | `#METADATA`               | agreementId (of the original analysis), completed_at                                                                                           |

**`file_count`** — Number of files in the upload. 1 for single-file uploads, 2–5 for bundles, null for pasted text.

**`source_filenames`** — JSON list of original filenames in upload order (e.g. `["offer_letter.pdf", "nda.pdf"]`). null for pasted text. Used by the UI to show which files were part of the bundle.

**`file_name`** on Risk, Ambiguous Clause, Clause Check — which file the finding came from. null for pasted text or when the finding spans the whole bundle (e.g. a MISSING clause).

**Agreement `status` enum:** `UPLOADED` → `PROCESSING` → `COMPLETED` / `FAILED`

- `UPLOADED` — record created, S3 upload done, waiting for dispatcher
- `PROCESSING` — AI Worker has picked up the job and is calling Nova
- `COMPLETED` — all analysis results written to DynamoDB, ready to serve
- `FAILED` — Nova call or JSON parsing failed after retries; logged to CloudWatch

**`bedrock_kb_id`** — Bedrock Knowledge Base ARN. Null for documents under 100k tokens (full-context mode). Set by AI Worker for large documents.

**GSIs:**

- GSI-1: PK = `AGREEMENT#<agreementId>` → returns `userId` for ownership verification on every API call
- Hash Index is its own top-level entity (not a GSI) — queried directly by PK `HASH#<sha256>`

---

### Why this schema is clean

- **User** — who owns what
- **Agreement** — document metadata, processing status, S3 location, dedup hash
- **Analysis** — one-time computed summary, verdict, financials, timeline. Fetched once, served forever
- **Risk** — one item per clear-cut risk found. A risk is a clause that is demonstrably unfavourable or dangerous. Lean attributes: title, severity, explanation, citation. Nothing else.
- **Ambiguous Clause** — one item per vague or loosely written clause. Separate from Risk because these require different analytical thinking (is this unclear? vs is this harmful?) and different UI treatment. Carries the exact clause text and suggested questions for the user to ask before signing.
- **Clause Check** — one item per standard clause expected for this document type. Found (with location) or missing. Simple.
- **Chat Message** — one item per Q&A pair. SK is `CHAT#<epoch_ms>` where `epoch_ms` is the current time as integer milliseconds since Unix epoch (e.g. `CHAT#1710498234567`). DynamoDB sorts items by SK lexicographically — this works correctly only because epoch milliseconds are zero-padded to a fixed width by nature and always increase monotonically. Do **not** use ISO 8601 strings (`CHAT#2025-03-15T11:05:34Z` would sort correctly by coincidence but is fragile) and do **not** use human-readable formats (`CHAT#March 15 2025 11:05` will not sort correctly). In Python: `int(datetime.now(timezone.utc).timestamp() * 1000)`. Full history per agreement, oldest-first.
- **Hash Index** — enables O(1) deduplication lookup globally. One item per unique document ever analyzed.

### What is NOT stored in DynamoDB

- Raw document files → S3
- Passwords → Cognito
- Secrets / API keys → Secrets Manager
- Embeddings (for RAG) → Bedrock Knowledge Bases manages this internally

---

## 17. Security

| Concern         | Solution                                                                                                                                       |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Authentication  | Amazon Cognito — JWT issued, verified by FastAPI on every request                                                                              |
| Authorization   | Every API call verifies `agreement.userId == loggedInUserId` via GSI before returning any data — backend enforced, never trust frontend        |
| S3 access       | Bucket fully private — only backend IAM role accesses files, S3 URLs never exposed to frontend                                                 |
| Secrets         | AWS Secrets Manager — no hardcoded credentials anywhere in codebase                                                                            |
| File validation | MIME type + extension + file size checked before accepting upload — reject anything not PDF/DOCX                                               |
| Rate limiting   | API Gateway enforces per-user rate limits — protects against Nova abuse and runaway costs                                                      |
| CORS            | API Gateway configured to allow only `https://clauseiq.com` (and localhost for dev)                                                            |
| SQL injection   | Not applicable (DynamoDB) — parameterized queries used for all data access                                                                     |
| Logging         | Log operational events only (uploaded, processing, completed, failed, question asked) — never log agreement content, JWTs, or user credentials |

### 17.1 Cognito JWT Validation — Exact Implementation

**Library:** `python-jose[cryptography]`

**How it works — every step:**

1. **Fetch Cognito's public keys (JWKS)** — on Lambda cold start, fetch and cache:
   ```
   https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json
   ```
2. **Extract the token** from `Authorization: Bearer <token>` header
3. **Decode the JWT header** (unverified) to get the `kid` (key ID)
4. **Match `kid`** to the correct public key in the JWKS response
5. **Verify the signature** using `jose.jwt.decode()` with the matched public key
6. **Verify claims:**
   - `iss` must equal `https://cognito-idp.{region}.amazonaws.com/{userPoolId}`
   - `token_use` must equal `id`
   - `exp` must be in the future
   - `aud` must equal the Cognito App Client ID
7. **Extract `sub` claim** — this is the `userId` used for all DynamoDB lookups (`USER#<sub>`)

**Return 401** if any step fails. Never let an unverified token reach business logic.

**JWKS caching:** Fetch once at Lambda cold start and reuse for the lifetime of the container. Do not re-fetch on every request — Cognito rate-limits JWKS endpoints.

---

## 18. What We Deliberately Did Not Build

| Rejected Feature                                     | Reason                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| URL import                                           | Bot detection, dynamic JS rendering, inconsistent HTML parsing — high engineering cost for a rare use case. PDF + DOCX + paste covers 95% of real scenarios.                                                                                                                                                   |
| Redis                                                | No remaining caching problem after DynamoDB analysis storage. Adds complexity with zero benefit.                                                                                                                                                                                                               |
| Custom vector infra (FAISS / self-hosted OpenSearch) | Bedrock Knowledge Bases manages chunking, embeddings, and retrieval. Pinecone serverless provides the vector store with zero operational overhead. No benefit to owning any of this layer.                                                                                                                     |
| Separate analysis per file in a bundle               | Users uploading related files want one unified view, not 3 separate sidebar entries. Concatenation with [FILE:] markers gives Nova full context across all files and produces one coherent analysis. Splitting into separate analyses would miss cross-document conflicts — the entire point of bundle upload. |
| Confidence scores                                    | Arbitrary percentages give false precision. Exact citations are more trustworthy and actionable.                                                                                                                                                                                                               |
| Custom auth (JWT / bcrypt)                           | Not the product. Cognito solves it completely and better.                                                                                                                                                                                                                                                      |
| Docker AI worker                                     | Lambda + SQS is the standard serverless pattern. Docker adds operational overhead with no benefit at this scale.                                                                                                                                                                                               |
| PostgreSQL / RDS                                     | Access patterns are key-based — DynamoDB is the correct choice. RDS adds VPC, connection pooling, and idle cost for no gain.                                                                                                                                                                                   |
| WebSockets / SSE for status updates                  | Analysis runs in a background Lambda — no persistent process to push from. Polling a single DynamoDB key every 3s is stateless, cheap, and sufficient.                                                                                                                                                         |

---

## 19. Phase 2 Roadmap

| Feature                   | Why Deferred                                                             | What Unlocks It                                     |
| ------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------- |
| Agreement comparison      | Compare two versions of the same document — what changed, what got worse | Single-doc foundation must be solid first           |
| Renewal reminders         | Calendar integration for key dates                                       | Structured timeline data already stored in DynamoDB |
| Shareable analysis report | PDF export of full analysis                                              | Core analysis quality must be proven first          |
| Mobile app                | Core web experience first                                                | Same API, different frontend                        |
| Cross-agreement analytics | Average risk score by type, most common missing clauses                  | Needs sufficient user data first                    |

---

## 20. Non-Functional Requirements

| Requirement                                         | Target                                                |
| --------------------------------------------------- | ----------------------------------------------------- |
| Upload acknowledgement                              | < 2 seconds (async — just saves to S3 and returns)    |
| Analysis completion — typical (< 30 pages)          | < 30 seconds                                          |
| Analysis completion — large (30-150 pages)          | < 90 seconds                                          |
| Analysis completion — very large (> 150 pages, RAG) | < 3 minutes                                           |
| Dashboard load time                                 | < 500ms (served from DynamoDB — zero Nova calls)      |
| Q&A response time                                   | < 10 seconds                                          |
| Polling interval                                    | 3 seconds                                             |
| Polling timeout                                     | 5 minutes                                             |
| Availability                                        | 99.9% (fully serverless — no single point of failure) |
| Document upload size limit                          | 50MB per file                                         |
| Maximum files per upload                            | 5                                                     |
| Token threshold for RAG                             | 100,000 tokens (tiktoken cl100k_base)                 |
| Estimated cost per analysis (Nova Lite)             | ~$0.001                                               |
| Estimated total build + test cost                   | < $10                                                 |

---

## 21. IaC — AWS SAM Template Structure

**Tool: AWS SAM (Serverless Application Model)**

SAM is the correct IaC choice for this stack — it natively handles Lambda, API Gateway, SQS, S3 event notifications, and Cognito in a single `template.yaml`. The SAM CLI provides local dev (`sam local start-api`) and one-command deployment (`sam deploy --guided`).

Do not use CDK or Terraform for this project. CDK adds language complexity with no benefit at this scale. Terraform requires separate provider configuration and cannot use SAM's Lambda-specific abstractions (event sources, function URLs, layers).

### template.yaml — Top-Level Resource Inventory

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31

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
  # --- Lambda: FastAPI API handler ---
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler # Mangum-wrapped FastAPI app
      CodeUri: ./api/
      MemorySize: 256
      Timeout: 30
      Events:
        Api:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi

  # --- Lambda: S3 event → SQS dispatcher ---
  DispatcherFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: dispatcher.handler
      CodeUri: ./dispatcher/
      MemorySize: 128
      Timeout: 10
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

  # --- Lambda: AI Worker ---
  AiWorkerFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: worker.handler
      CodeUri: ./worker/
      MemorySize: 1024
      Timeout: 600
      Events:
        SQSTrigger:
          Type: SQS
          Properties:
            Queue: !GetAtt AnalysisQueue.Arn
            BatchSize: 1

  # --- Lambda: Cognito Post-Confirmation trigger ---
  UserInitializerFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: user_initializer.handler
      CodeUri: ./user_initializer/
      MemorySize: 128
      Timeout: 10

  # --- Supporting resources ---
  DocumentsBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub clauseiq-documents-${Environment}-${AWS::AccountId}
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  # S3 bucket for React frontend static files
  FrontendBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub clauseiq-frontend-${Environment}-${AWS::AccountId}
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  # CloudFront Origin Access Control — lets CloudFront read from private S3 bucket
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

  # CloudFront distribution — serves frontend from S3, handles HTTPS, global CDN
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
          CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6 # CachingOptimized managed policy
          AllowedMethods: [GET, HEAD]
        # SPA routing — return index.html for all 403/404 so React Router handles the path
        CustomErrorResponses:
          - ErrorCode: 403
            ResponseCode: 200
            ResponsePagePath: /index.html
          - ErrorCode: 404
            ResponseCode: 200
            ResponsePagePath: /index.html
        HttpVersion: http2
        PriceClass: PriceClass_100 # US/Europe/Asia — cheapest tier that covers main markets

  # Pinecone API key stored in Secrets Manager
  # Store your Pinecone credentials here after creating your index on pinecone.io
  # Format: {"api_key": "pc-xxxx", "index_host": "https://clauseiq-xxxxx.svc.pinecone.io"}
  PineconeSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub clauseiq-pinecone-${Environment}
      Description: Pinecone API key and index host for Bedrock KB vector storage

  DynamoDBTable:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      # (GSI and attribute definitions per Section 16 schema)

  AnalysisQueue:
    Type: AWS::SQS::Queue
    Properties:
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt AnalysisDLQ.Arn
        maxReceiveCount: 3

  AnalysisDLQ:
    Type: AWS::SQS::Queue

  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      LambdaConfig:
        PostConfirmation: !GetAtt UserInitializerFunction.Arn

  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      UserPoolId: !Ref UserPool

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

### Lambda Entry Points

Each Lambda function file must expose a `handler` variable that SAM invokes:

| Lambda           | File                                   | Entry Point                                                                |
| ---------------- | -------------------------------------- | -------------------------------------------------------------------------- |
| API (FastAPI)    | `api/main.py`                          | `handler = Mangum(app)` where `app` is the FastAPI instance                |
| Dispatcher       | `dispatcher/dispatcher.py`             | `def handler(event, context):` — reads S3 event, pushes to SQS             |
| AI Worker        | `worker/worker.py`                     | `def handler(event, context):` — SQS Lambda trigger, processes one message |
| User Initializer | `user_initializer/user_initializer.py` | `def handler(event, context):` — Cognito Post-Confirmation trigger         |

### Repository Layout

SAM expects each Lambda to be a self-contained folder with its own `requirements.txt`. `sam build` walks each `CodeUri`, installs dependencies into a `.aws-sam/build/` staging directory, and zips it for upload. Dependencies are **not shared** between Lambdas at build time — each gets its own package.

```
clauseiq/
├── template.yaml
├── samconfig.toml
├── api/
│   ├── main.py               # FastAPI app + Mangum handler
│   ├── routers/
│   ├── auth.py               # Cognito JWT validation (python-jose)
│   └── requirements.txt      # fastapi, mangum, python-jose[cryptography],
│                             # boto3, PyMuPDF, python-docx, tiktoken, requests
├── dispatcher/
│   ├── dispatcher.py
│   └── requirements.txt      # boto3 only
├── worker/
│   ├── worker.py
│   └── requirements.txt      # boto3, PyMuPDF, tiktoken
├── user_initializer/
│   ├── user_initializer.py
│   └── requirements.txt      # boto3 only
└── frontend/                 # React app (separate build + S3 deploy)
    ├── src/
    └── package.json
```

**Why no shared Lambda layer:** A shared layer saves build time but adds a deployment dependency — if the layer update fails, all four Lambdas break together. At this scale (four small functions, infrequent deploys) the simplicity of per-function `requirements.txt` is worth the redundancy. Revisit if cold start times become a problem.

**PyMuPDF note:** PyMuPDF (`fitz`) includes compiled C extensions. `sam build` must run on a Linux host (or in a container) to produce Lambda-compatible binaries. Use `sam build --use-container` locally on Mac/Windows. In GitHub Actions, the Ubuntu runner handles this natively — no container flag needed.

### samconfig.toml

`samconfig.toml` locks in all `sam deploy` parameters so the command is non-interactive. Without this file, `sam deploy` prompts for stack name, region, S3 bucket, and capabilities on every run — which breaks CI. Commit this file to the repo.

```toml
version = 0.1

[default.global.parameters]
stack_name = "clauseiq"
region = "ap-south-1"
confirm_changeset = false
capabilities = "CAPABILITY_NAMED_IAM"   # required — BedrockKBServiceRole has an explicit RoleName

[default.build.parameters]
cached = true
parallel = true

[default.deploy.parameters]
s3_bucket = "clauseiq-sam-artifacts"   # S3 bucket SAM uses to upload Lambda zips
s3_prefix = "clauseiq"
resolve_s3 = false

[prod.deploy.parameters]
stack_name = "clauseiq-prod"
s3_prefix = "clauseiq-prod"
parameter_overrides = "Environment=prod"

[dev.deploy.parameters]
stack_name = "clauseiq-dev"
s3_prefix = "clauseiq-dev"
parameter_overrides = "Environment=dev"
```

Deploy to prod: `sam deploy --config-env prod`
Deploy to dev: `sam deploy --config-env dev`

The `clauseiq-sam-artifacts` S3 bucket must exist before the first deploy. Create it once manually or add it as a CloudFormation resource in a bootstrap stack. It is separate from the `DocumentsBucket` that stores uploaded agreements.

### Local Development with SAM

`sam local start-api` starts a local HTTP server that invokes the API Lambda on each request. It requires Docker running locally to emulate the Lambda environment.

**Local env var overrides** — create `env.json` (never commit this file):

```json
{
  "ApiFunction": {
    "DYNAMODB_TABLE_NAME": "clauseiq-dev",
    "S3_BUCKET_NAME": "clauseiq-documents-dev",
    "COGNITO_USER_POOL_ID": "ap-south-1_XXXXXXXX",
    "COGNITO_APP_CLIENT_ID": "xxxxxxxxxxxxxxxxxxxxxxxxxx",
    "SQS_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/123456789/clauseiq-dev",
    "ENVIRONMENT": "dev"
  }
}
```

Start local API:

```bash
sam build --use-container          # required on Mac/Windows for PyMuPDF binary compat
sam local start-api --env-vars env.json --port 8000
```

Local limitations to be aware of:

- S3 events do not fire locally — test the dispatcher Lambda directly with `sam local invoke DispatcherFunction -e events/s3_event.json`
- SQS trigger does not poll locally — invoke the AI Worker directly: `sam local invoke AiWorkerFunction -e events/sqs_event.json`
- Cognito JWT validation will reject tokens unless the local env points to the real Cognito User Pool

---

## 22. CI/CD — GitHub Actions

### Strategy

Two environments, two workflows:

| Push to `dev` branch  | Deploy to `clauseiq-dev` stack  |
| --------------------- | ------------------------------- |
| Push to `main` branch | Deploy to `clauseiq-prod` stack |

No manual deploy steps. Every merge to `main` is a production deploy. There is no approval gate at MVP — add one (GitHub environment protection rules) if the team grows.

Frontend and backend deploy in the same workflow but as independent jobs. Either can fail independently without blocking the other.

### Required GitHub Secrets

Set these in GitHub → Settings → Secrets and variables → Actions. These are the **exact secret names** the workflow files reference — if the names don't match, the deploy silently uses empty strings and fails with a cryptic AWS auth error.

**Core secrets (both workflows):**

| Secret Name             | Value                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------ |
| `AWS_ACCESS_KEY_ID`     | Access key for the `clauseiq-deployer` IAM user                                      |
| `AWS_SECRET_ACCESS_KEY` | Secret key for the `clauseiq-deployer` IAM user                                      |
| `AWS_REGION`            | `ap-south-1` (primary stack region — Lambda, DynamoDB, S3, Cognito)                  |
| `SAM_ARTIFACTS_BUCKET`  | Name of the S3 bucket SAM uses to upload Lambda zips (e.g. `clauseiq-sam-artifacts`) |

**Frontend secrets — populated from SAM Outputs after first deploy:**

After running `sam deploy --config-env prod` for the first time, retrieve all values with:

```bash
aws cloudformation describe-stacks --stack-name clauseiq-prod --query "Stacks[0].Outputs"
```

| Secret Name                       | SAM Output Key                                       | Example Value                                         |
| --------------------------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| `VITE_API_BASE_URL_PROD`          | `ApiUrl`                                             | `https://abc123.execute-api.ap-south-1.amazonaws.com` |
| `VITE_COGNITO_USER_POOL_ID_PROD`  | `UserPoolId`                                         | `ap-south-1_XXXXXXXXX`                                |
| `VITE_COGNITO_APP_CLIENT_ID_PROD` | `UserPoolClientId`                                   | `1a2b3c4d5e6f7g8h9i0j`                                |
| `FRONTEND_BUCKET_PROD`            | `FrontendBucketName`                                 | `clauseiq-frontend-prod-123456789`                    |
| `CLOUDFRONT_DISTRIBUTION_ID_PROD` | `CloudFrontDistributionId`                           | `E1ABCDEFGHIJKL`                                      |
| `VITE_API_BASE_URL_DEV`           | `ApiUrl` (from clauseiq-dev stack)                   | `https://xyz789.execute-api.ap-south-1.amazonaws.com` |
| `VITE_COGNITO_USER_POOL_ID_DEV`   | `UserPoolId` (from clauseiq-dev stack)               | `ap-south-1_YYYYYYYYY`                                |
| `VITE_COGNITO_APP_CLIENT_ID_DEV`  | `UserPoolClientId` (from clauseiq-dev stack)         | `9i8h7g6f5e4d3c2b1a0`                                 |
| `FRONTEND_BUCKET_DEV`             | `FrontendBucketName` (from clauseiq-dev stack)       | `clauseiq-frontend-dev-123456789`                     |
| `CLOUDFRONT_DISTRIBUTION_ID_DEV`  | `CloudFrontDistributionId` (from clauseiq-dev stack) | `E2MNOPQRSTUVWX`                                      |

**IAM permissions for `clauseiq-deployer`:** CloudFormation full, Lambda full, S3 full, IAM role pass, API Gateway full, SQS full, DynamoDB full, Cognito full, CloudFront full, Secrets Manager read, Bedrock read. Scope these down after MVP. Never use root credentials.

### Backend Deploy Workflow

```yaml
# .github/workflows/deploy-backend.yml
name: Deploy Backend

on:
  push:
    branches: [main, dev]
    paths:
      - "api/**"
      - "dispatcher/**"
      - "worker/**"
      - "user_initializer/**"
      - "template.yaml"
      - "samconfig.toml"

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Set up SAM CLI
        uses: aws-actions/setup-sam@v2

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: SAM Build
        run: sam build --parallel

      - name: SAM Deploy (prod)
        if: github.ref == 'refs/heads/main'
        run: |
          sam deploy \
            --config-env prod \
            --s3-bucket ${{ secrets.SAM_ARTIFACTS_BUCKET }} \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset

      - name: SAM Deploy (dev)
        if: github.ref == 'refs/heads/dev'
        run: |
          sam deploy \
            --config-env dev \
            --s3-bucket ${{ secrets.SAM_ARTIFACTS_BUCKET }} \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset
```

**Why `--no-fail-on-empty-changeset`:** If you push a docs-only change that touches `template.yaml` but doesn't actually change any resource, CloudFormation throws an error without this flag. With it, the workflow succeeds cleanly.

**Why `sam build --parallel`:** Builds all four Lambda functions concurrently. No `--use-container` needed on `ubuntu-latest` — the runner is already Linux, so PyMuPDF compiles to the correct architecture natively.

### Frontend Deploy Workflow

The React frontend builds with Vite, syncs to S3, and invalidates CloudFront. Bucket name and distribution ID come from GitHub Secrets (populated from SAM Outputs after first deploy — see secrets table above). There is no hardcoded bucket name anywhere in the workflow.

```yaml
# .github/workflows/deploy-frontend.yml
name: Deploy Frontend

on:
  push:
    branches: [main, dev]
    paths:
      - "frontend/**"

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Build (prod)
        if: github.ref == 'refs/heads/main'
        working-directory: frontend
        run: npm run build
        env:
          VITE_API_BASE_URL: ${{ secrets.VITE_API_BASE_URL_PROD }}
          VITE_COGNITO_USER_POOL_ID: ${{ secrets.VITE_COGNITO_USER_POOL_ID_PROD }}
          VITE_COGNITO_APP_CLIENT_ID: ${{ secrets.VITE_COGNITO_APP_CLIENT_ID_PROD }}

      - name: Build (dev)
        if: github.ref == 'refs/heads/dev'
        working-directory: frontend
        run: npm run build
        env:
          VITE_API_BASE_URL: ${{ secrets.VITE_API_BASE_URL_DEV }}
          VITE_COGNITO_USER_POOL_ID: ${{ secrets.VITE_COGNITO_USER_POOL_ID_DEV }}
          VITE_COGNITO_APP_CLIENT_ID: ${{ secrets.VITE_COGNITO_APP_CLIENT_ID_DEV }}

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Sync to S3 and invalidate CloudFront (prod)
        if: github.ref == 'refs/heads/main'
        run: |
          # Hashed asset files (JS/CSS) — cache forever, Vite ensures unique filenames per build
          aws s3 sync frontend/dist s3://${{ secrets.FRONTEND_BUCKET_PROD }} \
            --delete \
            --exclude "index.html" \
            --cache-control "public, max-age=31536000, immutable"
          # index.html — never cache; browser must always fetch latest to get new asset filenames
          aws s3 cp frontend/dist/index.html s3://${{ secrets.FRONTEND_BUCKET_PROD }}/index.html \
            --cache-control "no-cache, no-store, must-revalidate"
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID_PROD }} \
            --paths "/*"

      - name: Sync to S3 and invalidate CloudFront (dev)
        if: github.ref == 'refs/heads/dev'
        run: |
          aws s3 sync frontend/dist s3://${{ secrets.FRONTEND_BUCKET_DEV }} \
            --delete \
            --exclude "index.html" \
            --cache-control "public, max-age=31536000, immutable"
          aws s3 cp frontend/dist/index.html s3://${{ secrets.FRONTEND_BUCKET_DEV }}/index.html \
            --cache-control "no-cache, no-store, must-revalidate"
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID_DEV }} \
            --paths "/*"
```

**Why two cache-control values:** Vite hashes asset filenames on every build (`main.a3f9bc.js`). These hashed files can be cached forever — they never change. `index.html` is not hashed and must never be cached, otherwise users get an old `index.html` pointing to deleted asset filenames, breaking the app silently until their cache expires. The `--exclude "index.html"` on the first sync and explicit `cp` on the second ensures the correct header is set per file type.

### Path Filters — Why They Matter

Both workflows use `paths:` filters. A backend-only change does not trigger a frontend rebuild, and vice versa. Without path filters, every commit redeploys everything — wasting 3-5 minutes of runner time on a no-op.

If you change both frontend and backend in one commit, both workflows trigger in parallel. This is fine — they touch completely independent AWS resources.

### Branch Protection Rules (Recommended)

Set on `main` in GitHub → Settings → Branches:

- Require pull request before merging (minimum 1 approval)
- Require status checks to pass (both deploy workflows)
- Do not allow bypassing the above settings

This means nothing reaches production without a passing deploy on `dev` first.
