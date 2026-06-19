import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, Info } from 'lucide-react'
import { useChatHistory, useSendMessage } from '../../hooks/useChat'

export default function ChatPanel({ agreementId }: { agreementId: string }) {
  const [input, setInput] = useState('')
  const [optimisticQuestion, setOptimisticQuestion] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  
  // 1. Connect to the hooks we just built
  const { data: history, isLoading: isHistoryLoading } = useChatHistory(agreementId)
  const { mutate: sendMessage, isPending } = useSendMessage(agreementId)

  // 2. Auto-scroll to the bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [history, optimisticQuestion, isPending])

  // 3. Handle sending a message
  const handleSend = () => {
    if (!input.trim() || isPending) return
    setOptimisticQuestion(input)
    sendMessage(input, {
      onSettled: () => setOptimisticQuestion('')
    })
    setInput('') // clear the input box immediately
  }

  if (isHistoryLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
      </div>
    )
  }

  const messages = history || []

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg-base)]">
      {/* Message History Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="text-center text-[var(--color-text-muted)] mt-10">
            <p>Ask a question about this agreement!</p>
            <p className="text-xs mt-2">Example: "What is the penalty for early termination?"</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.messageId} className="flex flex-col gap-4">
              {/* User Question */}
              <div className="flex justify-end">
                <div className="bg-[var(--color-accent)] text-[var(--color-text-inverse)] px-4 py-2 rounded-2xl max-w-[85%] rounded-tr-sm">
                  {msg.question}
                </div>
              </div>
              
              {/* AI Answer */}
              <div className="flex justify-start">
                <div className="bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] px-4 py-3 rounded-2xl max-w-[85%] rounded-tl-sm border border-[var(--color-border-subtle)] space-y-2">
                  <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.answer}</p>
                  
                  {/* Render Citations if the AI used the document to answer */}
                  {msg.found_in_document && msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[var(--color-border-subtle)]">
                      <div className="flex items-center gap-1.5 text-xs text-[var(--color-accent)] mb-2 font-medium">
                        <Info size={14} />
                        <span>Sources</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.citations.map((cite: any, idx) => (
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
        
        {/* Optimistic User Question (shows immediately while waiting) */}
        {optimisticQuestion && (
          <div className="flex justify-end">
            <div className="bg-[var(--color-accent)] text-[var(--color-text-inverse)] px-4 py-2 rounded-2xl max-w-[85%] rounded-tr-sm opacity-70">
              {optimisticQuestion}
            </div>
          </div>
        )}

        {/* Loading indicator while waiting for the AI */}
        {isPending && (
          <div className="flex justify-start">
            <div className="bg-[var(--color-bg-elevated)] px-4 py-3 rounded-2xl rounded-tl-sm border border-[var(--color-border-subtle)]">
              <Loader2 className="animate-spin text-[var(--color-accent)]" size={16} />
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg-base)] shrink-0">
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask a question..."
            disabled={isPending}
            className="w-full bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] rounded-full pl-4 pr-12 py-3 text-sm focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)] disabled:opacity-50 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] transition-all"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isPending}
            className="absolute right-2 p-2 bg-[var(--color-accent)] text-[var(--color-text-inverse)] rounded-full hover:opacity-90 disabled:opacity-50 disabled:hover:opacity-50 transition-all flex items-center justify-center"
          >
            <Send size={16} className={isPending ? "opacity-0" : "opacity-100"} />
            {isPending && <Loader2 size={16} className="animate-spin absolute" />}
          </button>
        </div>
      </div>
    </div>
  )
}
