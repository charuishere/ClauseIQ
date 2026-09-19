import { useState, useRef, useEffect } from 'react'
import { Loader2, ArrowUp } from 'lucide-react'
import { useChatHistory, useSendMessage } from '../../hooks/useChat'
import ChatMessageBubble from './ChatMessageBubble'
import { getErrorMessage } from '../../lib/errors'

export default function ChatPanel({ agreementId }: { agreementId: string }) {
  const [input, setInput] = useState('')
  const [optimisticQuestion, setOptimisticQuestion] = useState('')
  const [sendError, setSendError] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // 1. Connect to the hooks we just built
  const { data: history, isLoading: isHistoryLoading } = useChatHistory(agreementId)
  const { mutate: sendMessage, isPending } = useSendMessage(agreementId)

  // 2. Auto-scroll to the bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [history, optimisticQuestion, isPending, sendError])

  // 3. Handle sending a message
  const handleSend = () => {
    if (!input.trim() || isPending) return
    setSendError('')
    setOptimisticQuestion(input)
    const question = input
    setInput('') // clear the input box immediately
    sendMessage(question, {
      onSettled: () => setOptimisticQuestion(''),
      onError: (err) => {
        setSendError(getErrorMessage(err, 'Failed to send message. Please try again.'))
        setInput(question) // give the user their question back so they don't retype it
      }
    })
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
        <div className="max-w-2xl mx-auto w-full space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-[var(--color-text-muted)] mt-10">
            <p>Ask a question about this agreement!</p>
            <p className="text-xs mt-2">Example: "What is the penalty for early termination?"</p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessageBubble key={msg.messageId} message={msg} />
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
              <span className="font-serif text-[var(--color-text-muted)] text-sm italic">Thinking...</span>
            </div>
          </div>
        )}

        {/* Error message if the last send failed */}
        {sendError && (
          <div className="flex justify-start px-2 mt-2">
            <div className="text-sm text-[var(--color-error,#e05c5c)] bg-[var(--color-error,#e05c5c)]/10 border border-[var(--color-error,#e05c5c)]/30 rounded-lg px-3 py-2">
              {sendError}
            </div>
          </div>
        )}
        </div>
      </div>

      {/* Floating Input Area */}
      <div className="absolute bottom-0 left-0 right-0 p-4 pt-12 bg-gradient-to-t from-[var(--color-bg-base)] via-[var(--color-bg-base)] to-transparent pointer-events-none">
        <div className="pointer-events-auto relative flex flex-col max-w-2xl mx-auto bg-[#2c2b2a]/60 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/10 ring-1 ring-white/5 focus-within:border-white/30 focus-within:ring-white/10 transition-all duration-300">
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
