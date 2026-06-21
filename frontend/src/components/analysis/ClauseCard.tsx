import { CheckCircle2, XCircle, ChevronRight } from 'lucide-react'
import type { DiscoveredClauseItem, NormalizedClauseItem } from '../../types'

interface ClausesCardProps {
  discovered_clauses: DiscoveredClauseItem[]
  normalized_checklist: NormalizedClauseItem[]
}

export default function ClausesCard({ discovered_clauses, normalized_checklist }: ClausesCardProps) {
  if (!discovered_clauses?.length && !normalized_checklist?.length) return null

  // Group normalized checklist into Found and Missing
  const foundClauses = normalized_checklist?.filter(c => c.status === 'FOUND') || []
  const missingClauses = normalized_checklist?.filter(c => c.status === 'MISSING') || []

  return (
    <div className="space-y-6 mb-6">
      {discovered_clauses?.length > 0 && (
        <div>
          <h3 className="font-serif text-lg text-[var(--color-text-primary)] mb-4">Discovered Clauses</h3>
          <div className="p-5 bg-[var(--color-bg-panel)] border border-[var(--color-border-subtle)] rounded-xl space-y-4">
            {discovered_clauses.map((clause, idx) => (
              <div key={idx} className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <ChevronRight className="w-4 h-4 text-[var(--color-accent)] shrink-0" />
                  <span className="font-medium text-sm">{clause.clause_name}</span>
                </div>
                <p className="text-sm text-[var(--color-text)] ml-6">{clause.summary}</p>
                {clause.citation?.section_name && (
                  <span className="text-xs text-[var(--color-text-muted)] ml-6">
                    Found in: {clause.citation.section_name}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {normalized_checklist?.length > 0 && (
        <div>
          <h3 className="font-serif text-lg text-[var(--color-text-primary)] mb-4">Standard Checklist</h3>
          <div className="p-5 bg-[var(--color-bg-panel)] border border-[var(--color-border-subtle)] rounded-xl">
            
            {/* Found Clauses Section */}
            {foundClauses.length > 0 && (
              <div className="space-y-3">
                {foundClauses.map((clause, idx) => (
                  <div key={idx} className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                      <span className="font-medium text-sm">{clause.anchor_name}</span>
                    </div>
                    {clause.mapped_from && clause.mapped_from !== clause.anchor_name && (
                      <span className="text-xs text-[var(--color-text-muted)] ml-6">
                        Mapped from: {clause.mapped_from}{clause.citation?.section_name ? ` (${clause.citation.section_name})` : ''}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Divider if both exist */}
            {foundClauses.length > 0 && missingClauses.length > 0 && (
              <hr className="my-4 border-[var(--color-border-subtle)]" />
            )}

            {/* Missing Clauses Section */}
            {missingClauses.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-[var(--color-text-muted)] mb-2 uppercase">Missing from document</h4>
                {missingClauses.map((clause, idx) => (
                  <div key={idx} className="flex items-center gap-2 opacity-70">
                    <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                    <span className="font-medium text-sm line-through decoration-red-500/30">{clause.anchor_name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
