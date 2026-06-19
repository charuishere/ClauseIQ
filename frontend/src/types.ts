
export interface Verdict {
  decision: string;
  reason: string;
}

export interface RiskItem {
  riskId: string;
  severity: 'High' | 'Medium' | 'Low';
  title: string;
  explanation: string;
  related_discovered_clause?: string;
  citation?: {
    section_name?: string;
    text_snippet?: string;
    page_number?: number;
    line_number?: number;
    file_name?: string;
  };
}

export interface AmbiguousClauseItem {
  ambiguousId: string;
  clause_text: string;
  explanation: string;
  suggested_questions: string[];
  citation?: {
    section_name?: string;
    page_number?: number;
    line_number?: number;
    file_name?: string;
  };
}

export interface DiscoveredClauseItem {
  clause_name: string;
  summary: string;
  citation?: {
    section_name?: string;
    page_number?: number;
    line_number?: number;
    file_name?: string;
  };
}

export interface NormalizedClauseItem {
  anchor_name: string;
  status: 'FOUND' | 'MISSING';
  mapped_from: string | null;
  citation?: {
    section_name?: string;
    page_number?: number;
    line_number?: number;
    file_name?: string;
  };
}

export interface FinancialItem {
  item: string;
  value: string;
  citation?: {
    section_name?: string;
    page_number?: number;
    line_number?: number;
  };
}

export interface TimelineItem {
  event: string;
  date: string;
  citation?: {
    section_name?: string;
    page_number?: number;
    line_number?: number;
  };
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
