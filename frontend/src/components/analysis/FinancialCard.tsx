import type { FinancialItem } from '../../types'

interface FinancialsCardProps {
  financials: FinancialItem[]
}

export default function FinancialsCard({ financials }: FinancialsCardProps) {
  if (!financials || financials.length === 0) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Financial Terms</h3>
        <div className="p-4 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg text-[var(--color-text-muted)] text-sm">
          No financial terms identified.
        </div>
      </div>
    )
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Financial Terms</h3>
      
      <div className="bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-[var(--color-bg-panel)] text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-border-subtle)]">
            <tr>
              <th className="px-4 py-3 font-semibold">Item</th>
              <th className="px-4 py-3 font-semibold">Value</th>
              <th className="px-4 py-3 font-semibold">Location</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border-subtle)]">
            {financials.map((fin, idx) => (
              <tr key={idx} className="hover:bg-[var(--color-bg-panel)]/50 transition-colors">
                <td className="px-4 py-3 font-medium">{fin.item}</td>
                <td className="px-4 py-3 text-[var(--color-accent)] font-semibold">{fin.value}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)] text-xs">
                  {fin.citation?.section_name || 'Unknown'}
                  {fin.citation?.page_number && ` (Pg ${fin.citation.page_number})`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
