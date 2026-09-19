import { Info } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '../../types'

// Shared by ChatPanel (a live chat session) and SharedChatPage (a public
// read-only snapshot) -- both rendered this exact same question/answer/
// citations layout independently, which had already drifted into a subtle
// prop-typing difference before being unified here.
export default function ChatMessageBubble({ message }: { message: ChatMessage }) {
  return (
    <div className="flex flex-col gap-4">
      {/* User Question */}
      <div className="flex justify-end">
        <div className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] px-4 py-3 rounded-2xl rounded-tr-sm max-w-[85%] text-[15px]">
          {message.question}
        </div>
      </div>

      {/* AI Answer */}
      <div className="flex justify-start px-2 mt-2">
        <div className="max-w-[95%] space-y-3 prose prose-invert prose-p:leading-relaxed max-w-none prose-pre:bg-[var(--color-bg-elevated)] prose-pre:border prose-pre:border-[var(--color-border-subtle)] prose-td:border-0 prose-td:border-b prose-td:border-[var(--color-border-subtle)] prose-th:border-0 prose-th:border-b prose-th:border-[var(--color-border-subtle)] prose-table:border-collapse prose-code:before:content-none prose-code:after:content-none prose-code:text-[#ff8a8a] prose-code:bg-[#3d2a2a] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono prose-code:font-medium">
          <div className="font-serif text-[15px] text-[var(--color-text-primary)] leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.answer}
            </ReactMarkdown>
          </div>

          {/* Render Citations if the AI used the document to answer */}
          {message.found_in_document && message.citations && message.citations.length > 0 && (
            <div className="mt-3 pt-3 border-t border-[var(--color-border-subtle)]">
              <div className="flex items-center gap-1.5 text-xs text-[var(--color-accent)] mb-2 font-medium">
                <Info size={14} />
                <span>Sources</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {message.citations.map((cite, idx) => (
                  <span key={idx} className="text-[10px] bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] px-2 py-1 rounded-md text-[var(--color-text-muted)]">
                    {cite.file_name || 'Document'} {cite.page_number ? `(Page ${cite.page_number})` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
