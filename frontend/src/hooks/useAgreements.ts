import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

// 1. Hook to fetch the list of all agreements for the sidebar
export function useAgreements() {
  return useQuery({
    queryKey: ['agreements'],
    queryFn: () => api.get('/agreements').then(r => r.data)
  })
}

// 2. Hook to fetch a single agreement AND automatically poll it if it is processing
export function useAgreementStatus(agreementId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['agreement', agreementId],
    // Guard: never fire if agreementId is undefined/empty (prevents GET /agreements/undefined)
    queryFn: () => api.get(`/agreements/${agreementId}`).then(r => r.data),
    
    // Polling logic: If the document is UPLOADED or PROCESSING, ask the server for an update every 3 seconds.
    // If it is COMPLETED or FAILED, stop asking.
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data || data.status === 'UPLOADED' || data.status === 'PROCESSING') {
        return 3000 // poll every 3000ms (3 seconds)
      }
      return false // stop polling
    },
    // Only run if explicitly enabled AND we actually have a valid ID
    enabled: enabled && !!agreementId
  })
}

// 3. Hook to delete an agreement
export function useDeleteAgreement() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (agreementId: string) => api.delete(`/agreements/${agreementId}`),
    
    // OPTIMISTIC UPDATE: Instantly remove it from the UI cache before the server responds
    onMutate: async (deletedId) => {
      // Cancel any outgoing refetches so they don't overwrite our optimistic update
      await queryClient.cancelQueries({ queryKey: ['agreements'] })

      // Snapshot the previous value
      const previousAgreements = queryClient.getQueryData(['agreements'])

      // Optimistically update to the new value by filtering out the deleted agreement
      queryClient.setQueryData(['agreements'], (old: any) => 
        old ? old.filter((doc: any) => doc.SK !== `AGREEMENT#${deletedId}`) : []
      )

      // Return a context object with the snapshotted value so we can rollback if it fails
      return { previousAgreements }
    },
    
    // If the API call fails, roll back to the previous state
    onError: (err, newTodo, context) => {
      if (context?.previousAgreements) {
        queryClient.setQueryData(['agreements'], context.previousAgreements)
      }
    },
    
    // Always fetch the real data in the background after success or failure
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['agreements'] })
    }
  })
}
