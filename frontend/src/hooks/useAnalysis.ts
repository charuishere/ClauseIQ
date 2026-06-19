import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { type AnalysisResponse } from '../types'

export function useAnalysis(agreementId: string | undefined, enabled: boolean) {
  return useQuery<AnalysisResponse>({
    queryKey: ['analysis', agreementId],
    queryFn: async () => {
      const response = await api.get(`/agreements/${agreementId}/analysis`)
      return response.data
    },
    enabled: enabled && !!agreementId,
    staleTime: Infinity, // analysis never changes, cache forever
  })
}
