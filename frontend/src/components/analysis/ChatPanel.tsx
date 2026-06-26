import { useState, useRef, useEffect } from 'react'
import { Loader2, Info, ArrowUp } from 'lucide-react'
import { useChatHistory, useSendMessage } from '../../hooks/useChat'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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
    <div className="relative h-full bg-transparent overflow-hidden">
      {/* Top Fade Gradient to mask text scrolling under header */}
      <div className="absolute top-0 left-0 right-0 h-12 bg-gradient-to-b from-[var(--color-bg-panel)] to-transparent pointer-events-none z-10" />
      
      {/* Message History Area */}
      <div className="absolute inset-0 overflow-y-auto p-4 pt-6 pb-40" ref={scrollRef}>
        <div className="max-w-3xl mx-auto w-full space-y-4">
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
            <div className="bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] px-4 py-3 rounded-2xl rounded-tr-sm max-w-[85%] text-[15px] opacity-70">
              {optimisticQuestion}
            </div>
          </div>
        )}
        
        {/* Loading indicator while waiting for the AI */}
        {isPending && (
          <div className="flex justify-start px-2 mt-2">
            <div className="flex items-center gap-2">
              <Loader2 className="animate-spin text-[var(--color-accent)]" size={20} />
              <span className="font-serif text-[var(--color-text-muted)] text-sm italic">Claude is thinking...</span>
            </div>
          </div>
        )}
        </div>
      </div>

      {/* Floating Input Area */}
      <div className="absolute bottom-0 left-0 right-0 p-4 pt-12 bg-gradient-to-t from-[var(--color-bg-base)] via-[var(--color-bg-base)] to-transparent pointer-events-none">
        <div className="pointer-events-auto relative flex flex-col max-w-3xl mx-auto bg-[#2c2b2a] rounded-2xl shadow-lg border border-[var(--color-border-subtle)] focus-within:border-[var(--color-text-muted)] transition-colors">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Write a message..."
            disabled={isPending}
            className="w-full bg-transparent px-4 pt-4 pb-4 text-[15px] focus:outline-none disabled:opacity-50 text-white placeholder-[var(--color-text-muted)] transition-all"
          />
          
          {/* Bottom Tool Row */}
          <div className="flex items-center justify-between px-3 pb-3">
            <div className="flex items-center">
              {/* Optional left tools */}
            </div>
            
            <div className="flex items-center gap-3">
              <div className="text-[13px] font-medium text-[var(--color-text-muted)] hover:text-white transition-colors cursor-pointer mr-2">
                Nova Lite
              </div>
              
              <button
                onClick={handleSend}
                disabled={!input.trim() || isPending}
                className="bg-[var(--color-accent)] hover:opacity-90 text-white p-1.5 rounded-lg disabled:opacity-30 transition-all flex items-center justify-center relative ml-1"
              >
                <ArrowUp size={18} className={isPending ? "opacity-0" : "opacity-100"} />
                {isPending && <Loader2 size={18} className="animate-spin absolute text-white" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
