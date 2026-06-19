def build_analysis_prompt(document_text: str) -> str:
    return f"""You are a legal document analyst. Analyze the following legal agreement and return ONLY a valid JSON object. No preamble, no explanation, no markdown formatting, no code fences. Just the raw JSON.

The document text may contain [FILE: filename] markers indicating multiple related files that form one agreement package. Treat the entire text as one cohesive agreement. For every finding, record which file it came from using the file_name field.

Document text:
{document_text}

Return this exact JSON structure:

{{
  "is_legal_document": <boolean, true ONLY if the document is actually a legal contract, agreement, NDA, etc. If it is a college proposal, a recipe, a novel, or other non-contract, set this to false>,
  "document_title": "<short, clean, human-readable title for this document, 3-6 words>",
  "document_types": ["<employment | nda | rental | service | platform | financial | enterprise | general>"],
  "verdict": {{
    "decision": "<Sign | Proceed with Caution | High Risk>",
    "reason": "<one sentence explaining the verdict>"
  }},
  "overall_risk": "<low | medium | high>",
  "summary": "<3-5 sentence plain English overview of the entire agreement package>",
  "risks": [
    {{
      "title": "<short descriptive title>",
      "severity": "<High | Medium | Low>",
      "explanation": "<plain English explanation of why this clause is harmful or unfavourable to the signing party, 1-2 sentences>",
      "related_discovered_clause": "<name of the clause from discovered_clauses, or null>",
      "citation": {{
        "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
        "section_name": "<exact section number and name, e.g. '12.1 Non-Compete'>",
        "page_number": <integer, or null if not determinable>,
        "line_number": <integer, or null if not determinable>
      }}
    }}
  ],
  "ambiguous_clauses": [
    {{
      "title": "<short descriptive title of the clause>",
      "clause_text": "<exact verbatim text of the clause as written in the document>",
      "explanation": "<why this clause is vague, one-sided, or unclear — 1-2 sentences>",
      "suggested_questions": ["<question 1>", "<question 2>", "<question 3>"],
      "citation": {{
        "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
        "section_name": "<exact section number and name>",
        "page_number": <integer, or null if not determinable>,
        "line_number": <integer, or null if not determinable>
      }}
    }}
  ],
  "discovered_clauses": [
    {{
      "clause_name": "<name derived from the document's own terminology>",
      "summary": "<1 sentence summary of the obligation or right>",
      "citation": {{
        "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
        "section_name": "<exact section number and name>",
        "page_number": <integer, or null if not determinable>,
        "line_number": <integer, or null if not determinable>
      }}
    }}
  ],
  "normalized_checklist": [
    {{
      "anchor_name": "<name from the anchor list below>",
      "status": "<FOUND | MISSING>",
      "mapped_from": "<name of the clause from discovered_clauses if FOUND, else null>",
      "citation": {{
        "file_name": "<filename if FOUND, else null>",
        "section_name": "<exact section if FOUND, else null>",
        "page_number": <integer if FOUND, else null>,
        "line_number": <integer if FOUND, else null>
      }}
    }}
  ],
  "financial_terms": [
    {{
      "item": "<what this financial term represents>",
      "value": "<exact value or amount as written in the document>",
      "citation": {{
        "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
        "section_name": "<section name>",
        "page_number": <integer or null>,
        "line_number": <integer or null>
      }}
    }}
  ],
  "timeline": [
    {{
      "event": "<name of the date or deadline>",
      "date": "<date exactly as written in the document>",
      "citation": {{
        "file_name": "<filename from [FILE: ...] marker, or null for pasted text>",
        "section_name": "<section name>",
        "page_number": <integer or null>,
        "line_number": <integer or null>
      }}
    }}
  ]
}}

CRITICAL: If "is_legal_document" is false, you MUST set the verdict decision to "Not a Legal Document", set overall_risk to "low", write a simple 1-2 sentence summary, and leave ALL other arrays (risks, ambiguous_clauses, discovered_clauses, normalized_checklist, financial_terms, timeline) COMPLETELY EMPTY like this: []. Do not hallucinate clauses from non-legal documents.

CLAUSE ANCHOR LISTS - for the "normalized_checklist" array:

First, identify the minimum set of applicable document_types required to accurately classify the agreement (e.g., a SaaS contract might be both 'service' and 'enterprise').
Step 1 (Discovery): Extract every legally significant clause that creates, limits, transfers, or modifies the rights, obligations, liabilities, payments, ownership, restrictions, remedies, or procedures of either party into "discovered_clauses". Ensure the discovery is highly comprehensive and captures the entirety of the agreement. Do not limit yourself to any predefined checklist. Use the document's own terminology where appropriate. Present discovered clauses in the same order they first appear in the document.
Step 2 (Normalization): After discovery, normalize the discovered clauses into canonical legal concepts where possible using ALL relevant anchor lists for the identified document_types. Report each applicable anchor clause as FOUND or MISSING in "normalized_checklist". Only include anchor clauses from the identified document_types. Do not evaluate or output anchor clauses belonging to unrelated document types.

employment: Compensation, Bonus, Benefits, Termination, Severance, Confidentiality, IP Assignment, Non-Solicitation, Non-Compete, Arbitration, Governing Law

nda: Definition of Confidential Information, Exclusions from Confidentiality, Permitted Disclosures, Obligations of Receiving Party, Term / Duration, Return or Destruction of Information, Remedies for Breach, Governing Law, Mutual vs Unilateral Scope

rental: Rent Amount and Due Date, Security Deposit, Lease Term, Renewal Terms, Maintenance Responsibilities, Pet Policy, Subletting Policy, Early Termination, Notice Period, Utilities Responsibility, Entry by Landlord, Governing Law

service: Scope of Work, Deliverables, Payment Terms, Payment Schedule, Late Payment Penalties, Intellectual Property Ownership, Confidentiality, Term and Termination, Termination for Convenience, Limitation of Liability, Indemnification, Governing Law, Dispute Resolution, Benefits, Bonus / Variable Pay

platform: Acceptance of Terms, User Account Terms, Prohibited Uses, Content Ownership, Data Collection and Use, Third-Party Sharing, Cookies Policy, Termination of Account, Limitation of Liability, Dispute Resolution / Arbitration Clause, Governing Law, Changes to Terms

financial: Loan Amount, Interest Rate, Repayment Schedule, Prepayment Penalty, Late Payment Fee, Collateral / Security, Default Conditions, Acceleration Clause, Governing Law

enterprise: Scope of License / Services, Fees and Payment Terms, Term and Renewal, Termination for Cause, Termination for Convenience, Limitation of Liability, Indemnification, Intellectual Property Ownership, Confidentiality, SLA / Service Levels, Governing Law, Dispute Resolution, Assignment

CLAUSE SYNONYM GUIDE - The synonym guide below is illustrative, not exhaustive. If the document creates the same legal obligation under different wording, treat it as the same clause even if the exact phrase does not appear:
- "Non-Compete" = any section titled "Restrictive Covenants", "Non-Competition", "Competition Restriction", or any sub-clause that prohibits the employee from working for competitors
- "Non-Solicitation" = any sub-clause in a Restrictive Covenants section that prohibits soliciting employees or customers
- "Intellectual Property Assignment" = any section titled "IP Assignment", "Work Product", "Inventions", or any sub-clause assigning intellectual property to the company
- "Governing Law" = any section titled "Choice of Law", "Applicable Law", "Jurisdiction", "Governing Law and Jurisdiction", or any sentence that specifies which state or country law governs the agreement
- "Dispute Resolution" = any section titled "Arbitration", "Mediation", "Dispute Resolution", or any clause requiring disputes to be resolved outside of court

RULES:
1. Return ONLY the JSON object. Nothing before or after it.
2. Never fabricate information not present in the document. If a field cannot be determined, use null.
3. page_number and line_number must only be populated when you can locate them with certainty.
4. risks: only include clauses that are clearly harmful or unfavourable to the signing party. A clause that is merely vague or unclear is NOT a risk - it belongs in ambiguous_clauses instead.
5. ambiguous_clauses: only include clauses that actually exist in the document but are written so vaguely or loosely that their meaning, scope, or enforceability is genuinely unclear. A clause can be ambiguous without being a risk. Include the verbatim clause text. Write 2-3 specific questions the user should ask the other party before signing.
6. A clause must not appear in both risks and ambiguous_clauses. Make a judgment: is the problem that this clause is clearly bad (risk), or that this clause is unclear (ambiguous)?
7. risks must be [] if no clear risks exist.
8. ambiguous_clauses must be [] if no ambiguous clauses exist.
9. financial_terms must be [] if no financial terms exist. If they do exist, you MUST populate section_name (e.g. "Section 5(a)") or page_number.
10. timeline: Extract all operational dates, durations, deadlines, notice periods, renewal dates, payment due dates, expiry dates, compliance deadlines, and any other legally significant temporal obligations. timeline must be [] if no dates exist.
11. overall_risk must reflect the aggregate severity of all risks found - not ambiguous clauses.
12. For "discovered_clauses": First discover every legally significant clause in the agreement. Do not limit yourself to any predefined checklist. Use the document's own terminology where appropriate.
13. For "normalized_checklist": After discovery, normalize the discovered clauses into canonical legal concepts where possible using the anchor list for comparison. If a clause in the anchor list means the same thing as a discovered clause (even if worded differently), map it and mark it FOUND. Only mark MISSING if the legal obligation truly does not exist.
14. SELF-CONSISTENCY CHECK: Before finalising your output, verify that your "normalized_checklist" array is consistent with your "summary" and "discovered_clauses".
15. file_name: populate from the nearest preceding [FILE: filename] marker. If no markers exist (single paste), set file_name to null for all findings.
16. If the document is clearly not a legal agreement or contract (e.g., a recipe, casual conversation, or random text), set document_types to ["unknown"], set verdict.decision to "Invalid Document", and return empty arrays for risks, discovered_clauses, normalized_checklist, timeline, and financial_terms.
"""
