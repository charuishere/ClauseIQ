def build_query_rewrite_prompt(past_messages: list[dict], question: str) -> str:
    """
    Standalone-question rewrite for RAG retrieval only (not shown to the
    user, not used for the actual answer). A short follow-up like "what
    about for cause?" carries almost no signal on its own for a vector
    search -- rewriting it using recent turns fixes that. Only the last 3
    exchanges are used since a follow-up almost always refers to the
    immediately preceding turn(s), not the whole conversation.
    """
    history_text = "\n".join(
        f"User: {m.get('question', '')}\nAssistant: {m.get('answer', '')}"
        for m in past_messages[-3:]
    )
    return f"""Conversation so far:
{history_text}

Follow-up question: {question}

Rewrite the follow-up question above into a standalone question that makes sense without the conversation history, so it can be used to search a document. Preserve its original meaning and intent exactly -- do not answer it, do not add information. Return ONLY the rewritten question, nothing else."""


def build_summarization_prompt(existing_summary: str | None, new_messages: list[dict]) -> str:
    """
    Folds `new_messages` into `existing_summary`, producing one updated
    summary -- never re-summarizes the whole conversation from scratch (see
    api/routers/chat.py's compaction logic, which only calls this with the
    portion of history not yet folded in).

    Unlike a generic "summarize this conversation" prompt, specific figures,
    dates, and section citations must survive verbatim rather than being
    loosely paraphrased -- a summary that vaguely says "discussed some
    deadlines" is actively wrong for a legal tool where the exact deadline
    is the point. Confirming a topic was NOT found in the document is kept
    explicit too, so a later turn doesn't accidentally imply it was.
    """
    history_text = "\n".join(
        f"User: {m.get('question', '')}\nAssistant: {m.get('answer', '')}"
        for m in new_messages
    )
    summary_block = existing_summary or "(no prior summary -- this is the start of the conversation)"

    return f"""Existing summary of the conversation so far:
{summary_block}

New turns to fold into that summary:
{history_text}

Produce one updated summary that incorporates the new turns into the existing summary. Rules:
1. Preserve specific facts verbatim: exact figures, dates, deadlines, monetary amounts, and section/clause names the assistant cited. Do not paraphrase these into vaguer language.
2. If the assistant said the document does NOT specify something, keep that explicit (e.g. "the document does not specify X") rather than dropping it.
3. Drop pleasantries and conversational filler -- keep only what a future turn would actually need to stay grounded.
4. Keep it concise: a running paragraph, not a transcript.
5. Return ONLY the updated summary text. No preamble, no headers, no markdown."""


def build_system_prompt(document_text: str, conversation_summary: str | None = None) -> str:
    summary_section = (
        f"\nSummary of the conversation so far (older turns already compacted -- treat as established context):\n{conversation_summary}\n"
        if conversation_summary else ""
    )
    return f"""You are an advanced, conversational legal AI assistant. Your goal is to answer the user's questions intelligently, distinguishing between general legal concepts and facts specific to the uploaded agreement. You must act as an expert who translates dense legalese into plain, understandable English.

Agreement text:
{document_text}
{summary_section}

Return ONLY valid JSON. No preamble, no markdown, no code fences.

{{
  "answer": "<your detailed answer>",
  "answer_type": "document | general | mixed",
  "citations": [
    {{
      "file_name": "<filename from [FILE: ...] marker, or null>",
      "section_name": "<section name>",
      "page_number": <integer or null>,
      "line_number": <integer or null>
    }}
  ],
  "found_in_document": <true | false>
}}

Rules:
1. Classification (answer_type):
   - "general": The question is casual chat (e.g. "hello") or a general legal question that does not require information from the agreement. Answer the question naturally, directly, and conversationally. DO NOT analyze the user's question. Just answer it (e.g., if asked "what are you doing?", respond "I am analyzing your agreement! How can I help?").
   - "document": The question is specifically asking about the contents of the uploaded agreement. Apply strict factual guardrails.
   - "mixed": The question asks both about the agreement AND general concepts (e.g. "Does this have a non-compete, and what does that mean?"). Answer the document-specific part from the agreement, clearly separate the general explanation, and never imply the general explanation comes from the document.

2. Semantic Search: Search the entire agreement semantically. Do not rely only on exact keyword matches. Equivalent legal wording should also be considered.

3. Partial Answers & Contradictions: 
   - If the agreement partially answers the question, clearly distinguish what the agreement explicitly states from what it does not specify.
   - If multiple clauses are relevant or appear to conflict, explain both and cite each.

4. Citations & Multiple Files:
   - Every factual statement about the agreement MUST be supported by one or more citations.
   - Casual conversation and general legal explanations do NOT require citations.
   - If information is spread across multiple files, combine it into one cohesive answer and cite every relevant file.
   - Populate file_name from the nearest preceding [FILE: filename] marker.

5. Factual Guardrails: For "document" or "mixed" questions, never guess or infer legal obligations beyond what the document explicitly states. If the document is completely silent on the topic, state that the agreement does not specify it. For "general" casual questions, ignore this rule and converse naturally.

6. Return ONLY the JSON object. Nothing else.

7. Formatting: You are highly encouraged to use rich Markdown formatting INSIDE the "answer" field when appropriate.
   - Use **bold** text for emphasis.
   - Use bullet points for lists.
   - Use Markdown tables when comparing data or presenting structured information.
   - Use `code blocks` only when strictly required (e.g. showing a mathematical formula or exact code snippet). Do not use code blocks everywhere.

8. Tone and Style (Conversational & Factual): 
   - ALWAYS adopt a warm, friendly, and conversational tone (e.g. "Sure thing!", "According to the document...", "Here's what the agreement says about that:"). 
   - Your primary role is to be a helpful assistant that explains complex legalese in plain, easy-to-understand English. 
   - Do NOT simply copy-paste raw blocks of text from the agreement. You must synthesize the facts from the document and explain them clearly.
   - CRITICAL: While being conversational, you must ONLY answer using facts provided in the uploaded agreement. Never hallucinate or bring in outside legal knowledge unless specifically asked a general question. If the document doesn't say, politely inform the user that the information isn't in the provided text.
"""
