import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'

type ViewerData = 
  | { type: 'pdf'; url: string }
  | { type: 'text'; content: string }

export function useDocumentViewerData(agreementId: string | undefined) {
  return useQuery({
    queryKey: ['viewerData', agreementId],
    queryFn: async () => {
      const { data } = await api.get(`/agreements/${agreementId}/viewer_data`)
      return data as ViewerData
    },
    enabled: !!agreementId,
    // Cache the viewer data in memory for an hour
    staleTime: 1000 * 60 * 60,
  })
}
