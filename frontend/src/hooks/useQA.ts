import { useState } from 'react'
import toast from 'react-hot-toast'
import { qaApi, type QuestionRequest } from '../api/client'

export interface Citation {
  chunk_id: string
  document_id: string
  document_name: string
  page_number: number | null
  content: string
  relevance_score: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  model?: string
  confidence?: number | null
}

export type QAMode = 'langgraph' | 'mcp'

export function useQA(mode: QAMode) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  const ask = async (question: string, selectedDocumentIds: string[]) => {
    if (!question.trim() || loading) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const req: QuestionRequest = {
        question,
        document_ids: selectedDocumentIds.length ? selectedDocumentIds : undefined,
        top_k: 5,
        use_reranker: true,
      }

      const resp = mode === 'mcp' ? await qaApi.askMcp(req) : await qaApi.ask(req)
      const data = resp.data as {
        answer: string
        citations: Citation[]
        model_used: string
        confidence: number | null
      }

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.answer,
          citations: data.citations,
          model: data.model_used,
          confidence: data.confidence,
        },
      ])
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const clearMessages = () => setMessages([])

  return { messages, loading, ask, clearMessages }
}
