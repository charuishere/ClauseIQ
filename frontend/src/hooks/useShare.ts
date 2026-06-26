import { useMutation, useQuery } from '@tanstack/react-query'
import api from '../lib/api'

export function useCreateShareLink(agreementId: string) {
  return useMutation({
    mutationFn: async () => {
      const res = await api.post(`/agreements/${agreementId}/share`)
      return res.data as { share_id: string }
    }
  })
}

export function useSharedChat(shareId: string | undefined) {
  return useQuery({
    queryKey: ['sharedChat', shareId],
    queryFn: async () => {
      const res = await api.get(`/share/${shareId}`)
      return res.data
    },
    enabled: !!shareId
  })
}
