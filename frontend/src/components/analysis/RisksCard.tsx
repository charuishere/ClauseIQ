import { ShieldAlert, AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react'
import { type RiskItem } from '../../types'

interface RisksCardProps {
  risks: RiskItem[]
}

export default function RisksCard({ risks }: RisksCardProps) {
  if (!risks || risks.length === 0) {
    return (
      <div className="mb-6">
        <h3 className="font-serif text-lg text-[var(--color-text-primary)] mb-4">Identified Risks</h3>
        <div className="p-4 bg-[var(--color-bg-panel)] border border-[var(--color-border-subtle)] rounded-xl text-[var(--color-text-muted)] text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-600/70" />
          No significant risks identified
        </div>
      </div>
    )
  }

  // Sort risks: High -> Medium -> Low
  const sortedRisks = [...risks].sort((a, b) => {
    const order = { High: 0, Medium: 1, Low: 2 }
    return order[a.severity] - order[b.severity]
  })

  return (
    <div className="mb-8">
      <h3 className="font-serif text-lg text-[var(--color-text-primary)] mb-4">Identified Risks ({risks.length})</h3>
      
      <div className="space-y-4">
        {sortedRisks.map((risk) => {
          let badgeColor = ''
          let Icon = AlertCircle
          
          if (risk.severity === 'High') {
            badgeColor = 'bg-red-500/10 text-red-600/80'
            Icon = ShieldAlert
          } else if (risk.severity === 'Medium') {
            badgeColor = 'bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
            Icon = AlertTriangle
          } else {
            badgeColor = 'bg-blue-500/10 text-blue-600/80'
            Icon = AlertCircle
          }

          return (
            <div key={risk.riskId} className="p-5 bg-[var(--color-bg-panel)] border border-[var(--color-border-subtle)] rounded-xl">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Icon className={`w-4 h-4 ${badgeColor.split(' ')[1]}`} />
                  <h4 className="font-semibold text-[var(--color-text-primary)] text-sm">{risk.title}</h4>
                </div>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-md ${badgeColor}`}>
                  {risk.severity}
                </span>
              </div>
              <p className="text-sm text-[var(--color-text-muted)] mb-3 leading-relaxed">
                {risk.explanation}
              </p>
              
              {/* Citation */}
              {(risk.related_discovered_clause || risk.citation?.section_name || risk.citation?.text_snippet) && (
                <div className="mt-2 pt-2 border-t border-[var(--color-border-subtle)] text-xs text-[var(--color-text-muted)] opacity-80 flex flex-col gap-1">
                  {risk.related_discovered_clause && <span><span className="font-semibold">Related Clause:</span> {risk.related_discovered_clause}</span>}
                  {!risk.related_discovered_clause && risk.citation?.section_name && <span><span className="font-semibold">Section:</span> {risk.citation.section_name}</span>}
                  {risk.citation?.text_snippet && <span className="italic line-clamp-2">"{risk.citation.text_snippet}"</span>}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
