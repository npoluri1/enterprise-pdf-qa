import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, Loader, Bot } from 'lucide-react'
import { qaApi } from '../api/client'
import { CitationPanel } from './CitationPanel'
import toast from 'react-hot-toast'

/** Colour-coded confidence badge with a tooltip explaining what it means. */
function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  const [show, setShow] = useState(false)

  let colour = 'text-green-600'
  let label = 'High'
  if (pct < 40) { colour = 'text-red-500'; label = 'Low' }
  else if (pct < 70) { colour = 'text-yellow-600'; label = 'Medium' }

  const tip =
    pct >= 70
      ? 'The answer is well-supported by your documents.'
      : pct >= 40
        ? 'The answer is partially supported — some details may be inferred.'
        : 'The documents had limited information on this question. Treat carefully.'

  return (
    <span className="relative inline-flex items-center gap-1">
      <span
        className={`cursor-help underline decoration-dotted ${colour}`}
        onMouseEnter={() => { setShow(true) }}
        onMouseLeave={() => { setShow(false) }}
      >
        {label} confidence ({pct}%)
      </span>
      {show && (
        <span className="absolute bottom-full left-0 mb-1 w-56 bg-gray-800 text-white text-xs rounded px-2 py-1.5 z-10 shadow-lg">
          {tip}
        </span>
      )}
    </span>
  )
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Array<unknown>
  model?: string
  confidence?: number | null
  streaming?: boolean
}

interface Props {
  selectedDocumentIds: string[]
  mode: 'langgraph' | 'mcp'
}

export function ChatInterface({ selectedDocumentIds, mode }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input,
    }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setLoading(true)

    try {
      const req = {
        question: input,
        document_ids: selectedDocumentIds.length ? selectedDocumentIds : undefined,
        top_k: 5,
        use_reranker: true,
      }

      const resp = mode === 'mcp'
        ? await qaApi.askMcp(req)
        : await qaApi.ask(req)

      const data = resp.data as { answer: string; citations: Array<unknown>; model_used: string; confidence: number }
      setMessages((m) => [
        ...m,
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
      const error = err as { response?: { data?: { detail?: string }; status?: number } }
      const detail = error.response?.data?.detail
      const status = error.response?.status

      // Show 503 (missing API key / service unavailable) inline in chat so the full
      // message is readable — toasts truncate long text
      if (status === 503 && detail) {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `**Configuration required**\n\n${detail}`,
            citations: [],
          },
        ])
      } else {
        toast.error(detail ?? 'Request failed')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-16">
            <Bot className="mx-auto h-12 w-12 mb-3 opacity-40" />
            <p className="text-sm">Ask anything about your documents</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm
              ${msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-sm'
                : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'}`}>
              {msg.role === 'assistant' ? (
                <>
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                  {msg.model && (
                    <p className="text-xs text-gray-400 mt-2 flex items-center gap-1.5 flex-wrap">
                      <span>{msg.model}</span>
                      {msg.confidence != null && (
                        <ConfidenceBadge confidence={msg.confidence} />
                      )}
                    </p>
                  )}
                  {msg.citations && msg.citations.length > 0 && (
                    <CitationPanel citations={msg.citations} />
                  )}
                </>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <Loader className="h-4 w-4 text-blue-500 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => { setInput(e.target.value) }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                void sendMessage()
              }
            }}
            placeholder="Ask a question about your documents…"
            className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            onClick={() => { void sendMessage() }}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition flex items-center gap-1.5"
          >
            {loading ? <Loader className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
        {selectedDocumentIds.length > 0 && (
          <p className="text-xs text-gray-400 mt-1.5">
            Scoped to {selectedDocumentIds.length} selected document{selectedDocumentIds.length > 1 ? 's' : ''}
          </p>
        )}
      </div>
    </div>
  )
}
