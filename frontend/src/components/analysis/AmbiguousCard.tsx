import { useState } from 'react'
import { HelpCircle, ChevronDown, ChevronUp } from 'lucide-react'
import {type AmbiguousClauseItem } from '../../types'

interface AmbiguousCardProps {
  clauses: AmbiguousClauseItem[]
}

export default function AmbiguousCard({ clauses }: AmbiguousCardProps) {
  if (!clauses || clauses.length === 0) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Ambiguous Clauses</h3>
        <div className="p-4 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg text-[var(--color-text-muted)] text-sm">
          No ambiguous clauses detected.
        </div>
      </div>
    )
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Ambiguous Clauses ({clauses.length})</h3>
      
      <div className="space-y-4">
        {clauses.map((clause) => (
          <AmbiguousItem key={clause.ambiguousId} clause={clause} />
        ))}
      </div>
    </div>
  )
}

function AmbiguousItem({ clause }: { clause: AmbiguousClauseItem }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="p-4 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg">
      <div className="flex items-start gap-2 mb-3">
        <HelpCircle className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
        <div>
          <blockquote className="border-l-2 border-purple-500/50 pl-3 py-1 text-sm italic text-[var(--color-text-muted)] bg-purple-500/5 rounded-r-md">
            "{clause.clause_text}"
          </blockquote>
        </div>
      </div>
      
      <p className="text-sm text-[var(--color-text-base)] mb-3 leading-relaxed">
        <span className="font-semibold mr-1">Issue:</span>
        {clause.explanation}
      </p>

      {clause.suggested_questions && clause.suggested_questions.length > 0 && (
        <div className="mt-2">
          <button 
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-1 text-xs font-semibold text-[var(--color-accent)] hover:text-white transition-colors"
          >
            {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            Questions to Ask ({clause.suggested_questions.length})
          </button>
          
          {isOpen && (
            <ul className="mt-2 pl-4 list-decimal text-xs space-y-1.5 text-[var(--color-text-muted)]">
              {clause.suggested_questions.map((q, idx) => (
                <li key={idx} className="leading-relaxed">{q}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
