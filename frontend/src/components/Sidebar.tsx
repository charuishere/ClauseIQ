import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, FileText, LogOut, Trash2 } from 'lucide-react'
import { useAgreements, useDeleteAgreement } from '../hooks/useAgreements'
import { useAuth } from '../context/AuthContext'

interface SidebarProps {
  currentAgreementId?: string
  onNewAgreement: () => void
}

export default function Sidebar({ currentAgreementId, onNewAgreement }: SidebarProps) {
  const { signOut, user } = useAuth()
  const navigate = useNavigate()
  
  // Here we use the hook we just built! TanStack Query will fetch the data for us.
  const { data: agreements, isLoading } = useAgreements()
  
  // Hook to delete an agreement
  const deleteMutation = useDeleteAgreement()

  const [agreementToDelete, setAgreementToDelete] = useState<string | null>(null)

  const confirmDelete = () => {
    if (!agreementToDelete) return
    deleteMutation.mutate(agreementToDelete, {
      onSuccess: () => {
        if (currentAgreementId === agreementToDelete) {
          navigate('/') // redirect if they are currently viewing it
        }
        setAgreementToDelete(null)
      }
    })
  }

  const handleDeleteClick = (e: React.MouseEvent, agreementId: string) => {
    e.preventDefault() // prevent navigating to the link
    setAgreementToDelete(agreementId)
  }

  return (
    <div className="w-64 h-screen bg-[var(--color-bg-panel)] border-r border-[var(--color-border-subtle)] flex flex-col">
      {/* Top Section: Logo & New Agreement Button */}
      <div className="p-4 flex flex-col gap-4">
        <h1 className="text-xl font-bold text-[var(--color-text-primary)] font-serif pl-2">ClauseIQ</h1>
        <button 
          onClick={onNewAgreement}
          className="w-full flex items-center gap-3 px-3 py-2 text-[var(--color-text-primary)] rounded-md hover:bg-[var(--color-bg-base)] transition-colors text-sm"
        >
          <Plus size={16} className="text-[var(--color-text-muted)]" />
          <span>New chat</span>
        </button>
      </div>

      {/* Middle Section: List of Agreements */}
      <div className="flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="text-sm text-[var(--color-text-muted)] p-2">Loading agreements...</div>
        ) : agreements?.length === 0 ? (
          <div className="text-sm text-[var(--color-text-muted)] p-2">No agreements yet.</div>
        ) : (
          <div className="flex flex-col gap-1">
            {agreements?.map((doc: any) => {
              // Handle DynamoDB ghost items (which occur if an item was deleted while its SQS job was still processing/retrying)
              const actualId = doc.agreementId || (doc.SK && doc.SK.replace('AGREEMENT#', ''))
              if (!actualId) return null
              
              return (
              <Link
                key={actualId}
                to={`/agreements/${actualId}`}
                className={`flex items-center gap-2 p-2 rounded-md text-sm transition-colors ${
                  currentAgreementId === actualId
                    ? 'bg-[var(--color-bg-base)] text-[var(--color-text-base)] border border-[var(--color-border-subtle)] shadow-sm'
                    : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-base)] hover:text-[var(--color-text-base)]'
                }`}
              >
                <FileText size={16} />
                <span className="truncate flex-1">{doc.title || 'Unknown Document'}</span>
                
                {/* Status Badges */}
                {doc.status === 'PROCESSING' && <span className="text-xs bg-yellow-500/20 text-yellow-500 px-2 py-0.5 rounded-full">⏳</span>}
                
                {/* Delete / Confirm Actions */}
                {agreementToDelete === actualId ? (
                  <div className="flex items-center gap-1 ml-1">
                    <button
                      onClick={(e) => { e.preventDefault(); confirmDelete(); }}
                      className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white bg-red-500 hover:bg-red-600 rounded transition-colors"
                      disabled={deleteMutation.isPending}
                    >
                      {deleteMutation.isPending ? '...' : 'Yes'}
                    </button>
                    <button
                      onClick={(e) => { e.preventDefault(); setAgreementToDelete(null); }}
                      className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--color-text-base)] bg-[var(--color-bg-panel)] border border-[var(--color-border-subtle)] hover:bg-[var(--color-border-subtle)] rounded transition-colors"
                      disabled={deleteMutation.isPending}
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button 
                    onClick={(e) => handleDeleteClick(e, actualId)}
                    className="p-1 hover:bg-red-500/20 text-red-400 hover:text-red-500 rounded transition-colors ml-1"
                    title="Delete Agreement"
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </Link>
            )})}
          </div>
        )}
      </div>

      {/* Bottom Section: User Profile & Logout */}
      <div className="p-4 border-t border-[var(--color-border-subtle)]">
        <div className="flex items-center justify-between text-sm text-[var(--color-text-muted)]">
          <span className="truncate pr-2">{user?.email}</span>
          <button 
            onClick={signOut}
            className="p-1.5 hover:bg-red-500/10 hover:text-red-500 rounded-md transition-colors"
            title="Logout"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
