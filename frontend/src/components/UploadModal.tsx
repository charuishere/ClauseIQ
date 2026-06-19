import { useState, useRef } from 'react'
import { X, Upload, FileText, Loader2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function UploadModal({ isOpen, onClose }: UploadModalProps) {
  const [files, setFiles] = useState<File[]>([])
  const [text, setText] = useState('')
  const [mode, setMode] = useState<'file' | 'text'>('file')
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // This hooks into TanStack Query's manager
  const queryClient = useQueryClient()

  if (!isOpen) return null

  async function handleUpload() {
    if (mode === 'file' && files.length === 0) return
    if (mode === 'text' && !text.trim()) return

    setIsUploading(true)
    const formData = new FormData()
    
    if (mode === 'file' && files.length > 0) {
      files.forEach(f => formData.append('files', f))
    } else if (mode === 'text') {
      formData.append('text', text)
    }

    try {
      // 1. Send the file to our Python backend!
      await api.post('/agreements', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      // 2. Tell TanStack Query that we just added a new agreement, 
      // so it should instantly refresh the Sidebar list!
      queryClient.invalidateQueries({ queryKey: ['agreements'] })
      
      setFiles([])
      onClose()
    } catch (error) {
      console.error('Failed to upload', error)
      alert('Failed to upload file.')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--color-bg-panel)] w-full max-w-md rounded-lg shadow-xl border border-[var(--color-border-subtle)] overflow-hidden">
        
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-[var(--color-border-subtle)]">
          <h2 className="text-lg font-semibold">Analyze New Agreement</h2>
          <button onClick={onClose} className="p-1 hover:bg-[var(--color-bg-base)] rounded-md transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 flex flex-col items-center justify-center gap-4">
          
          {/* Mode Toggle */}
          <div className="flex bg-[var(--color-bg-base)] rounded-lg p-1 w-full border border-[var(--color-border-subtle)]">
            <button
              onClick={() => setMode('file')}
              className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${mode === 'file' ? 'bg-[var(--color-bg-panel)] shadow-sm' : 'text-[var(--color-text-muted)] hover:text-white'}`}
            >
              Upload File
            </button>
            <button
              onClick={() => setMode('text')}
              className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${mode === 'text' ? 'bg-[var(--color-bg-panel)] shadow-sm' : 'text-[var(--color-text-muted)] hover:text-white'}`}
            >
              Paste Text
            </button>
          </div>

          {mode === 'file' ? (
            <>
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                multiple
                accept=".pdf,.docx"
                onChange={(e) => {
                  if (e.target.files) {
                    setFiles((prev) => [...prev, ...Array.from(e.target.files!)])
                  }
                }}
              />
              
              {files.length > 0 ? (
                <div className="flex flex-col gap-2 w-full max-h-48 overflow-y-auto">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 bg-[var(--color-bg-base)] w-full rounded-md border border-[var(--color-border-subtle)]">
                      <FileText className="text-[var(--color-accent)] shrink-0" size={20} />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{f.name}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">{(f.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                      <button 
                        onClick={() => setFiles(files.filter((_, index) => index !== i))}
                        className="p-1 hover:bg-red-500/10 hover:text-red-500 rounded-md transition-colors text-[var(--color-text-muted)] shrink-0"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ))}
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="mt-2 text-sm text-[var(--color-accent)] hover:underline text-center font-medium"
                  >
                    + Add more files
                  </button>
                </div>
              ) : (
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full h-32 border-2 border-dashed border-[var(--color-border-subtle)] rounded-lg flex flex-col items-center justify-center gap-2 hover:border-[var(--color-accent)] hover:bg-[var(--color-bg-base)] transition-all group"
                >
                  <div className="p-3 bg-[var(--color-bg-base)] rounded-full group-hover:bg-[var(--color-accent)] group-hover:text-white transition-colors">
                    <Upload size={24} />
                  </div>
                  <span className="text-sm font-medium">Click to select files</span>
                </button>
              )}
            </>
          ) : (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste contract text here..."
              className="w-full h-32 bg-[var(--color-bg-base)] border border-[var(--color-border-subtle)] rounded-lg p-3 text-sm focus:outline-none focus:border-[var(--color-accent)] resize-none"
            />
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--color-border-subtle)] flex justify-end gap-2 bg-[var(--color-bg-base)]">
          <button 
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium hover:bg-[var(--color-bg-panel)] rounded-md transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleUpload}
            disabled={(mode === 'file' && files.length === 0) || (mode === 'text' && !text.trim()) || isUploading}
            className="px-4 py-2 text-sm font-medium bg-[var(--color-accent)] text-white rounded-md hover:bg-opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {isUploading && <Loader2 size={16} className="animate-spin" />}
            {isUploading ? 'Uploading...' : 'Analyze'}
          </button>
        </div>

      </div>
    </div>
  )
}



