interface SummaryCardProps {
  summary: string
}

export default function SummaryCard({ summary }: SummaryCardProps) {
  if (!summary) return null

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Executive Summary</h3>
      <div className="p-4 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg">
        <p className="text-sm text-[var(--color-text-base)] leading-relaxed">
          {summary}
        </p>
      </div>
    </div>
  )
}
