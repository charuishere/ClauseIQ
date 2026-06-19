import { Calendar } from 'lucide-react'
import type { TimelineItem } from '../../types'

interface TimelineCardProps {
  timeline: TimelineItem[]
}

export default function TimelineCard({ timeline }: TimelineCardProps) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">Key Dates</h3>
        <div className="p-4 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg text-[var(--color-text-muted)] text-sm">
          No key dates identified.
        </div>
      </div>
    )
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4 flex items-center gap-2">
        <Calendar className="w-4 h-4" />
        Key Dates ({timeline.length})
      </h3>
      
      <div className="bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg p-4">
        <div className="relative border-l-2 border-[var(--color-border-subtle)] ml-3 space-y-6">
          {timeline.map((item, idx) => (
            <div key={idx} className="relative pl-6">
              {/* Timeline Dot */}
              <div className="absolute w-3 h-3 bg-[var(--color-accent)] rounded-full -left-[7px] top-1.5 shadow-[0_0_0_4px_var(--color-bg-base)]"></div>
              
              <div className="flex flex-col gap-1">
                <span className="text-sm font-bold text-[var(--color-accent)]">{item.date}</span>
                <span className="text-sm font-medium text-[var(--color-text-base)]">{item.event}</span>
                
                {item.citation?.section_name && (
                  <span className="text-xs text-[var(--color-text-muted)] mt-1 opacity-80">
                    Source: {item.citation.section_name}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
