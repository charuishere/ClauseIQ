import axios from 'axios'

/**
 * Pulls a user-facing message out of an API error (FastAPI's
 * {"detail": "..."} shape), falling back to a generic message otherwise.
 * Was previously copy-pasted with an `any`-typed catch in both
 * UploadModal.tsx and ChatPanel.tsx.
 */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || fallback
  }
  return fallback
}
