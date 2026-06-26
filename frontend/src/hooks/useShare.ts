import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchAuthSession } from 'aws-amplify/auth'
import { getApiUrl } from '../config'

export function useCreateShareLink(agreementId: string) {
  return useMutation({
    mutationFn: async () => {
      const { tokens } = await fetchAuthSession()
      const token = tokens?.idToken?.toString()

      const res = await fetch(`${getApiUrl()}/agreements/${agreementId}/share`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!res.ok) {
        throw new Error('Failed to create share link')
      }
      return res.json() as Promise<{ share_id: string }>
    }
  })
}

export function useSharedChat(shareId: string | undefined) {
  return useQuery({
    queryKey: ['sharedChat', shareId],
    queryFn: async () => {
      const res = await fetch(`${getApiUrl()}/share/${shareId}`)
      if (!res.ok) {
        throw new Error('Failed to load shared chat')
      }
      return res.json()
    },
    enabled: !!shareId
  })
}
