import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

interface Citation {
  chunk_id: string
  document_id: string
  document_name: string
  page_number: number | null
  content: string
  relevance_score: number
}

interface Props {
  citations: Citation[]
}

/**
 * Normalize scores relative to the best result so the top citation always
 * reads close to 100%. Cross-encoder logit scores are unbounded and can all
 * be very negative for domain-specific queries — showing 3% or 0% would be
 * confusing even when the passage IS the best available match.
 */
function getRelativeScores(citations: Citation[]): number[] {
  const raw = citations.map(c => Math.max(0, c.relevance_score))
  const max = Math.max(...raw, 0.001)
  return raw.map(s => s / max)
}

function matchLabel(relative: number): { text: string; colour: string } {
  const pct = Math.round(relative * 100)
  if (pct >= 70) return { text: `${String(pct)}% match`, colour: 'text-green-600' }
  if (pct >= 40) return { text: `${String(pct)}% match`, colour: 'text-yellow-600' }
  return { text: `${String(pct)}% match`, colour: 'text-gray-400' }
}

export function CitationPanel({ citations }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (!citations.length) return null

  const relativeScores = getRelativeScores(citations)

  return (
    <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 flex items-center gap-2 border-b border-gray-200">
        <BookOpen className="h-4 w-4 text-blue-500" />
        <span className="text-sm font-semibold text-gray-700">
          Sources ({citations.length})
        </span>
      </div>
      <ul className="divide-y divide-gray-100">
        {citations.map((c, i) => {
          const { text, colour } = matchLabel(relativeScores[i])
          return (
            <li key={c.chunk_id} className="px-4 py-3">
              <button
                onClick={() => { setExpanded(expanded === c.chunk_id ? null : c.chunk_id) }}
                className="flex w-full items-start justify-between gap-2 text-left"
              >
                <div>
                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold mr-2">
                    {i + 1}
                  </span>
                  <span className="text-sm font-medium text-gray-800">{c.document_name}</span>
                  {c.page_number != null && (
                    <span className="ml-2 text-xs text-gray-400">p.{c.page_number}</span>
                  )}
                  <span className={`ml-2 text-xs ${colour}`}>{text}</span>
                </div>
                {expanded === c.chunk_id
                  ? <ChevronUp className="h-4 w-4 text-gray-400 shrink-0 mt-0.5" />
                  : <ChevronDown className="h-4 w-4 text-gray-400 shrink-0 mt-0.5" />}
              </button>
              {expanded === c.chunk_id && (
                <p className="mt-2 text-xs text-gray-600 bg-gray-50 p-3 rounded leading-relaxed">
                  {c.content}
                </p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
