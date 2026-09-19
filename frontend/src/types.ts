
export interface Verdict {
  decision: string;
  reason: string;
}

// Shared by every analysis item below (was six near-identical inline object
// types, one per item -- some included text_snippet/file_name, some didn't,
// for no clear reason). All fields are optional here so this one type still
// fits every use site without changing what's actually optional per item.
export interface Citation {
  section_name?: string;
  text_snippet?: string;
  page_number?: number;
  line_number?: number;
  file_name?: string;
}

export interface RiskItem {
  riskId: string;
  severity: 'High' | 'Medium' | 'Low';
  title: string;
  explanation: string;
  related_discovered_clause?: string;
  citation?: Citation;
}

export interface AmbiguousClauseItem {
  ambiguousId: string;
  clause_text: string;
  explanation: string;
  suggested_questions: string[];
  citation?: Citation;
}

export interface DiscoveredClauseItem {
  clause_name: string;
  summary: string;
  citation?: Citation;
}

export interface NormalizedClauseItem {
  anchor_name: string;
  status: 'FOUND' | 'MISSING';
  mapped_from: string | null;
  citation?: Citation;
}

export interface FinancialItem {
  item: string;
  value: string;
  citation?: Citation;
}

export interface TimelineItem {
  event: string;
  date: string;
  citation?: Citation;
}

export interface AnalysisResponse {
  verdict: Verdict;
  overall_risk: 'low' | 'medium' | 'high';
  summary: string;
  risks: RiskItem[];
  ambiguous_clauses: AmbiguousClauseItem[];
  discovered_clauses: DiscoveredClauseItem[];
  normalized_checklist: NormalizedClauseItem[];
  financial_terms: FinancialItem[];
  timeline: TimelineItem[];
  is_legal_document?: boolean;
}

// Shared by both a live chat session (ChatPanel) and a public shared-chat
// snapshot (SharedChatPage) -- both render the exact same message shape.
export interface ChatMessage {
  messageId: string;
  question: string;
  answer: string;
  answer_type?: 'document' | 'general' | 'mixed';
  citations: Citation[];
  found_in_document: boolean;
  created_at: string;
}

export interface SharedChatResponse {
  agreement_id: string;
  title: string;
  created_at: string;
  messages: ChatMessage[];
}

// The list item shape returned by GET /agreements, and the single-agreement
// shape from GET /agreements/{id}. agreementId/SK are both optional because
// Sidebar.tsx has to defend against "ghost" rows (a DynamoDB item that was
// deleted mid-flight while its SQS job was still retrying).
export interface AgreementSummary {
  agreementId?: string;
  SK?: string;
  title?: string;
  status: 'UPLOADED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
}
