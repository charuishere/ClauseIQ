import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'

interface ChatMessage {
  messageId: string;
  question: string;
  answer: string;
  answer_type?: 'document' | 'general' | 'mixed';
  citations: any[];
  found_in_document: boolean;
  created_at: string;
}

// 1. Fetch the chat history for a specific agreement
export function useChatHistory(agreementId: string | undefined) {
  return useQuery({
    queryKey: ['chat', agreementId],
    queryFn: () => api.get(`/agreements/${agreementId}/chat`).then(r => r.data.messages as ChatMessage[]),
    enabled: !!agreementId // Only fetch if we have a valid ID
  })
}

// 2. Send a new message
export function useSendMessage(agreementId: string | undefined) {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (question: string) => 
      api.post(`/agreements/${agreementId}/chat`, { question }).then(r => r.data as ChatMessage),
    onSuccess: () => {
      // Refresh the chat history immediately after the AI responds
      queryClient.invalidateQueries({ queryKey: ['chat', agreementId] })
    }
  })
}
