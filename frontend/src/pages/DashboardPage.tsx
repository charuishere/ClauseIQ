import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Loader2, PanelRightClose, PanelRightOpen, MessageSquare, FileText } from 'lucide-react'
import Sidebar from '../components/Sidebar'
import UploadModal from '../components/UploadModal'
import { useAgreementStatus } from '../hooks/useAgreements'
import { useAnalysis } from '../hooks/useAnalysis'
import VerdictCard from '../components/analysis/VerdictCard'
import RisksCard from '../components/analysis/RisksCard'
import AmbiguousCard from '../components/analysis/AmbiguousCard'
import ClauseCard from '../components/analysis/ClauseCard'
import FinancialCard from '../components/analysis/FinancialCard'
import TimelineCard from '../components/analysis/TimelineCard'
import SummaryCard from '../components/analysis/SummaryCard'
import ChatPanel from '../components/analysis/ChatPanel'
import DocumentViewer from '../components/analysis/DocumentViewer'
import { useCreateShareLink } from '../hooks/useShare'

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>()
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true)
  const [panelWidth, setPanelWidth] = useState(384) // 384px is w-96
  const [isDragging, setIsDragging] = useState(false)
  const [activeTab, setActiveTab] = useState<'analysis' | 'chat'>('analysis')
  const [isCopied, setIsCopied] = useState(false)
  const { mutate: createShareLink, isPending: isSharing } = useCreateShareLink(id || '')

  const handleShare = () => {
    if (!id) return
    createShareLink(undefined, {
      onSuccess: (data) => {
        const shareUrl = `${window.location.origin}/share/${data.share_id}`
        navigator.clipboard.writeText(shareUrl)
        setIsCopied(true)
        setTimeout(() => setIsCopied(false), 2000)
      }
    })
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return
      // Calculate width from the right side of the screen
      const newWidth = window.innerWidth - e.clientX
      // Clamp between 300px and 800px
      if (newWidth > 300 && newWidth < 800) {
        setPanelWidth(newWidth)
      }
    }
    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])
  
  // 1. Fetch the data for the SPECIFIC agreement we clicked on in the Sidebar!
  // "enabled: !!id" means it only runs if 'id' actually exists in the URL.
  const { data: agreement, isLoading } = useAgreementStatus(id, !!id)

  // 2. Are we currently waiting for the AI?
  const isProcessing = agreement?.status === 'UPLOADED' || agreement?.status === 'PROCESSING'
  
  // 3. Fetch the full analysis if processing is done
  const isCompleted = agreement?.status === 'COMPLETED'
  const { data: analysis, isLoading: isAnalysisLoading } = useAnalysis(id, isCompleted)

  return (
    <div className="h-screen w-full flex bg-[var(--color-bg-base)] text-[var(--color-text-primary)] relative">
      
      {/* 1. Left Sidebar */}
      <Sidebar 
        currentAgreementId={id} 
        onNewAgreement={() => setIsUploadModalOpen(true)} 
      />

      {/* If no agreement is selected in the Sidebar, show a welcome message */}
      {!id ? (
        <div className="flex-1 flex items-center justify-center bg-[var(--color-bg-panel)]">
          <p className="text-[var(--color-text-muted)] text-lg">Select an agreement from the sidebar, or upload a new one.</p>
        </div>
      ) : (
        <>
          {/* 2. Center Panel (Document / Chat) */}
          <div className="flex-1 flex flex-col bg-[var(--color-bg-panel)] overflow-hidden">
            {/* Minimalist Claude Header */}
            <div className="p-3 grid grid-cols-[1fr_auto_1fr] items-center h-14 gap-2 md:gap-4">
              
              {/* Left Side: Title */}
              <div className="flex items-center gap-2 px-2 py-1.5 min-w-0">
                <h1 className="font-sans text-[14px] font-medium text-[var(--color-text-primary)] truncate">
                  {agreement?.title || 'Stateless LLM memory architecture'}
                </h1>
                {isProcessing && <span className="text-xs bg-[var(--color-accent)]/10 text-[var(--color-accent)] px-2 py-0.5 rounded-full animate-pulse font-semibold shrink-0">Analyzing...</span>}
              </div>
              
              {/* Center: Toggle Buttons */}
              <div className="flex justify-center shrink-0">
                {isCompleted && (
                  <div className="flex bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] rounded-lg p-0.5 z-10 shadow-sm">
                    <button
                      onClick={() => setActiveTab('analysis')}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
                        activeTab === 'analysis' ? 'bg-[var(--color-border-subtle)] text-[var(--color-text-primary)] shadow-sm' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                      }`}
                    >
                      Document
                    </button>
                    <button
                      onClick={() => setActiveTab('chat')}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${
                        activeTab === 'chat' ? 'bg-[var(--color-border-subtle)] text-[var(--color-text-primary)] shadow-sm' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                      }`}
                    >
                      Chat
                    </button>
                  </div>
                )}
              </div>
              
              {/* Right Side: Tools */}
              <div className="flex items-center justify-end gap-3 pr-2 shrink-0">
                <button 
                  onClick={handleShare}
                  disabled={isSharing}
                  className="px-3 py-1.5 text-xs font-medium text-[var(--color-text-primary)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] rounded-md hover:bg-[var(--color-border-subtle)] transition-colors disabled:opacity-50 whitespace-nowrap shadow-sm"
                >
                  {isSharing ? 'Sharing...' : isCopied ? 'Copied!' : 'Share'}
                </button>
                {/* Keeping your panel toggle for functionality, but restyled */}
                {agreement && (
                  <button 
                    onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
                    className="p-1.5 rounded-md hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] transition-colors shrink-0"
                  >
                    {isRightPanelOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
                  </button>
                )}
              </div>
            </div>
            
            <div className="flex-1 overflow-hidden relative">
              {isLoading ? (
                <div className="h-full flex flex-col items-center justify-center gap-4 text-[var(--color-text-muted)]">
                  <Loader2 size={32} className="animate-spin text-[var(--color-accent)]" />
                  <p>Loading document details...</p>
                </div>
              ) : isProcessing ? (
                <div className="h-full flex flex-col items-center justify-center gap-4 text-[var(--color-text-muted)]">
                  <Loader2 size={48} className="animate-spin text-yellow-500" />
                  <p className="text-lg font-medium text-[var(--color-text-base)]">The AI is currently reading your document.</p>
                  <p className="text-sm text-center max-w-md">
                    This usually takes 15-30 seconds. We are securely processing it through AWS Bedrock.
                    This screen will automatically refresh when it finishes!
                  </p>
                </div>
              ) : agreement?.status === 'FAILED' ? (
                <div className="h-full flex items-center justify-center text-red-500 font-medium">The AI failed to process this document.</div>
              ) : activeTab === 'chat' ? (
                <ChatPanel agreementId={id!} />
              ) : (
                <DocumentViewer agreementId={id!} />
              )}
            </div>
          </div>

          {/* 3. Right Analysis Panel (Resizable & Collapsible) */}
          {isRightPanelOpen && (
            <div 
              className="relative border-l border-[var(--color-border-subtle)] flex flex-col bg-[var(--color-bg-base)] overflow-hidden shrink-0 transition-[width] duration-0"
              style={{ width: panelWidth }}
            >
              {/* Drag Handle */}
              <div 
                className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-[var(--color-accent)]/50 z-20"
                onMouseDown={() => setIsDragging(true)}
              />
              
              {/* Header */}
              <div className="p-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-base)] z-10 sticky top-0 shrink-0">
                <h2 className="font-serif text-xl text-[var(--color-text-primary)]">AI Analysis</h2>
              </div>

              <div className="flex-1 overflow-y-auto">
                <div className="p-4">
                  {isProcessing ? (
                    <div className="h-full flex items-center justify-center pt-20">
                      <p className="text-sm text-[var(--color-text-muted)] text-center animate-pulse">Waiting for AI...</p>
                    </div>
                  ) : isAnalysisLoading ? (
                    <div className="h-full flex items-center justify-center pt-20">
                      <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
                    </div>
                  ) : analysis ? (
                    <div className="flex flex-col gap-2">
                      {analysis.is_legal_document === false ? (
                        <>
                          <div className="bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg p-6 text-center shadow-sm">
                            <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">Not a Legal Document</h3>
                            <p className="text-[var(--color-text-muted)] text-sm">
                              This document does not appear to be a legal contract. Clause extraction, risk analysis, and checklist mapping have been disabled.
                            </p>
                          </div>
                          <SummaryCard summary={analysis.summary} />
                        </>
                      ) : (
                        <>
                          <VerdictCard verdict={analysis.verdict} overallRisk={analysis.overall_risk} />
                          <ClauseCard discovered_clauses={analysis.discovered_clauses} normalized_checklist={analysis.normalized_checklist} />
                          <RisksCard risks={analysis.risks} />
                          <AmbiguousCard clauses={analysis.ambiguous_clauses} />
                          <FinancialCard financials={analysis.financial_terms} />
                          <TimelineCard timeline={analysis.timeline} />
                          <SummaryCard summary={analysis.summary} />
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center pt-20">
                      <p className="text-sm text-[var(--color-text-muted)] text-center">No analysis available for this document.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* 4. The Hidden Popup Modal */}
      <UploadModal 
        isOpen={isUploadModalOpen} 
        onClose={() => setIsUploadModalOpen(false)} 
      />

    </div>
  )
}
