import { CheckCircle2, AlertTriangle, AlertOctagon } from 'lucide-react'
import {type Verdict } from '../../types'

interface VerdictCardProps {
  verdict: Verdict
  overallRisk: 'low' | 'medium' | 'high'
}

export default function VerdictCard({ verdict, overallRisk }: VerdictCardProps) {
  const getVerdictStyles = () => {
    switch (verdict.decision) {
      case 'Sign':
        return {
          bg: 'bg-[var(--color-bg-panel)] border-[var(--color-border-subtle)]',
          icon: <CheckCircle2 className="w-6 h-6 text-green-600/80" />
        }
      case 'Proceed with Caution':
        return {
          bg: 'bg-[var(--color-bg-panel)] border-[var(--color-border-subtle)]',
          icon: <AlertTriangle className="w-6 h-6 text-[var(--color-accent)]" />
        }
      case 'High Risk':
      default:
        return {
          bg: 'bg-[var(--color-bg-panel)] border-[var(--color-border-subtle)]',
          icon: <AlertOctagon className="w-6 h-6 text-red-600/80" />
        }
    }
  }

  const getRiskBadge = () => {
    switch (overallRisk) {
      case 'low':
        return <span className="text-green-600/80 bg-green-500/10 px-2 py-0.5 rounded-md text-xs font-semibold">Low Risk</span>
      case 'medium':
        return <span className="text-[var(--color-accent)] bg-[var(--color-accent)]/10 px-2 py-0.5 rounded-md text-xs font-semibold">Medium Risk</span>
      case 'high':
        return <span className="text-red-600/80 bg-red-500/10 px-2 py-0.5 rounded-md text-xs font-semibold">High Risk</span>
      default:
        return null
    }
  }

  const styles = getVerdictStyles()

  return (
    <div className={`p-4 rounded-xl border ${styles.bg} mb-6`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {styles.icon}
          <h2 className="text-2xl font-serif text-[var(--color-text-primary)]">{verdict.decision}</h2>
        </div>
        {getRiskBadge()}
      </div>
      <p className="text-sm opacity-90 leading-relaxed">
        {verdict.reason}
      </p>
    </div>
  )
}
