import { useParams } from 'react-router-dom'
import { Loader2, Info } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useSharedChat } from '../hooks/useShare'

export default function SharedChatPage() {
  const { shareId } = useParams<{ shareId: string }>()
  const { data, isLoading, error } = useSharedChat(shareId)

  if (isLoading) {
    return (
      <div className="h-screen w-full bg-[var(--color-bg-base)] flex items-center justify-center">
        <Loader2 className="animate-spin text-[var(--color-accent)]" size={32} />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="h-screen w-full bg-[var(--color-bg-base)] flex items-center justify-center text-[var(--color-text-primary)]">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-serif">Chat not found</h1>
          <p className="text-[var(--color-text-muted)]">This shared link is invalid or has expired.</p>
        </div>
      </div>
    )
  }

  const messages = data.messages || []

  return (
    <div className="h-screen w-full bg-[var(--color-bg-base)] flex flex-col overflow-hidden text-[var(--color-text-primary)]">
      
      {/* Header */}
      <div className="h-14 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-panel)] flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="font-sans text-sm font-medium truncate max-w-xl">
            {data.title}
          </h1>
          <span className="text-xs bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-[var(--color-text-muted)] px-2 py-0.5 rounded-full">
            Shared Conversation
          </span>
        </div>
        <div className="text-xs text-[var(--color-text-muted)]">
          ClauseIQ
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 pt-10 pb-20 relative bg-transparent">
        <div className="absolute top-0 left-0 right-0 h-12 bg-gradient-to-b from-[var(--color-bg-panel)] to-transparent pointer-events-none z-10" />
        
        <div className="max-w-2xl mx-auto w-full space-y-8">
          {messages.length === 0 ? (
            <div className="text-center text-[var(--color-text-muted)] mt-10">
              <p>This conversation is empty.</p>
            </div>
          ) : (
            messages.map((msg: any) => (
              <div key={msg.messageId} className="flex flex-col gap-4">
                {/* User Question */}
                <div className="flex justify-end">
                  <div className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] px-4 py-3 rounded-2xl rounded-tr-sm max-w-[85%] text-[15px]">
                    {msg.question}
                  </div>
                </div>
                
                {/* AI Answer */}
                <div className="flex justify-start px-2 mt-2">
                  <div className="max-w-[95%] space-y-3 prose prose-invert prose-p:leading-relaxed max-w-none prose-pre:bg-[var(--color-bg-elevated)] prose-pre:border prose-pre:border-[var(--color-border-subtle)] prose-td:border-0 prose-td:border-b prose-td:border-[var(--color-border-subtle)] prose-th:border-0 prose-th:border-b prose-th:border-[var(--color-border-subtle)] prose-table:border-collapse prose-code:before:content-none prose-code:after:content-none prose-code:text-[#ff8a8a] prose-code:bg-[#3d2a2a] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono prose-code:font-medium">
                    <div className="font-serif text-[15px] text-[var(--color-text-primary)] leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.answer}
                      </ReactMarkdown>
                    </div>
                    
                    {/* Render Citations if the AI used the document to answer */}
                    {msg.found_in_document && msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-[var(--color-border-subtle)]">
                        <div className="flex items-center gap-1.5 text-xs text-[var(--color-accent)] mb-2 font-medium">
                          <Info size={14} />
                          <span>Sources</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.citations.map((cite: any, idx: number) => (
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
            ))
          )}
        </div>
      </div>
    </div>
  )
}
