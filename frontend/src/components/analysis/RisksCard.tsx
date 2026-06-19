import { ShieldAlert, AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react'
import { type RiskItem } from '../../types'

interface RisksCardProps {
  risks: RiskItem[]
}

export default function RisksCard({ risks }: RisksCardProps) {
  if (!risks || risks.length === 0) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Identified Risks</h3>
        <div className="p-4 bg-[var(--color-bg-base)] border border-green-500/20 rounded-lg text-green-400 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
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
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Identified Risks ({risks.length})</h3>
      
      <div className="space-y-3">
        {sortedRisks.map((risk) => {
          let badgeColor = ''
          let Icon = AlertCircle
          
          if (risk.severity === 'High') {
            badgeColor = 'bg-red-500/20 text-red-400'
            Icon = ShieldAlert
          } else if (risk.severity === 'Medium') {
            badgeColor = 'bg-yellow-500/20 text-yellow-400'
            Icon = AlertTriangle
          } else {
            badgeColor = 'bg-blue-500/20 text-blue-400'
            Icon = AlertCircle
          }

          return (
            <div key={risk.riskId} className="p-4 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Icon className={`w-4 h-4 ${badgeColor.replace('bg-', 'text-').split(' ')[1]}`} />
                  <h4 className="font-semibold text-sm">{risk.title}</h4>
                </div>
                <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${badgeColor}`}>
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
