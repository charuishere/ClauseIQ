import { useState } from 'react'
import { FileText, Loader2, FileX } from 'lucide-react'
import { useDocumentViewerData } from '../../hooks/useDocumentViewerData'
import { Document, Page, pdfjs } from 'react-pdf'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface DocumentViewerProps {
  agreementId: string
}

export default function DocumentViewer({ agreementId }: DocumentViewerProps) {
  const { data: viewerData, isLoading, isError } = useDocumentViewerData(agreementId)
  const [numPages, setNumPages] = useState<number>()

  function onDocumentLoadSuccess({ numPages }: { numPages: number }): void {
    setNumPages(numPages)
  }

  if (isLoading) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-[var(--color-bg-base)]">
        <Loader2 className="animate-spin text-[var(--color-accent)] mb-4" size={32} />
        <p className="text-[var(--color-text-muted)]">Loading document...</p>
      </div>
    )
  }

  if (isError || !viewerData) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-[var(--color-bg-base)] p-8 text-center">
        <FileX className="text-[var(--color-text-muted)] mb-4" size={48} />
        <h3 className="text-xl font-medium text-[var(--color-text-primary)] mb-2">Failed to load document</h3>
        <p className="text-[var(--color-text-muted)] max-w-md">There was a problem loading the document content. Please try again later.</p>
      </div>
    )
  }

  if (viewerData.type === 'pdf') {
    return (
      <div className="h-full w-full bg-[var(--color-bg-base)] overflow-y-auto p-4 md:p-8 flex justify-center custom-pdf-scrollbar">
        <div className="w-full max-w-4xl flex flex-col gap-6 items-center">
          <Document
            file={viewerData.url}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={
              <div className="flex flex-col items-center justify-center p-12 mt-12 bg-white/5 rounded-lg border border-[var(--color-border-subtle)]">
                <Loader2 className="animate-spin text-[var(--color-accent)] mb-4" size={32} />
                <p className="text-[var(--color-text-muted)]">Rendering high-quality PDF...</p>
              </div>
            }
            error={
              <div className="p-8 text-center text-[var(--color-error)] bg-[var(--color-bg-base)] border border-[var(--color-error)] rounded-lg mt-12">
                <FileX className="mx-auto mb-2" size={32} />
                <p>Failed to load PDF</p>
              </div>
            }
          >
            {Array.from(new Array(numPages), (el, index) => (
              <div key={`page_${index + 1}`} className="mb-6 shadow-2xl bg-white rounded-sm overflow-hidden">
                <Page
                  pageNumber={index + 1}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  width={800}
                  className="max-w-full"
                />
              </div>
            ))}
          </Document>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full bg-[var(--color-bg-base)] overflow-y-auto p-4 md:p-8 flex justify-center pb-32">
      <div className="w-full max-w-4xl bg-[var(--color-bg-elevated)] border border-[var(--color-border-subtle)] rounded-xl shadow-sm h-fit overflow-hidden">
        
        {/* File Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg-base)]">
          <FileText className="text-[var(--color-text-muted)]" size={20} />
          <span className="text-sm font-medium text-[var(--color-text-primary)] font-mono">
            document_content.txt
          </span>
        </div>

        {/* File Content */}
        <div className="p-8 md:p-10">
          <pre className="whitespace-pre-wrap font-sans text-[var(--color-text-primary)] text-[15px] leading-relaxed">
            {viewerData.content}
          </pre>
        </div>
      </div>
    </div>
  )
}
