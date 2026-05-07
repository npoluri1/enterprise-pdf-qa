import { FileText, Trash2, Loader, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { docsApi } from '../api/client'
import toast from 'react-hot-toast'

interface Document {
  id: string
  original_name: string
  file_size: number
  status: 'pending' | 'processing' | 'ready' | 'failed'
  page_count: number | null
  chunk_count: number | null
  created_at: string
}

interface Props {
  documents: Document[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onDeleted: () => void
}

const statusIcon = {
  pending: <Clock className="h-4 w-4 text-yellow-500" />,
  processing: <Loader className="h-4 w-4 text-blue-500 animate-spin" />,
  ready: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <AlertCircle className="h-4 w-4 text-red-500" />,
}

export function DocumentList({ documents, selectedIds, onToggle, onDeleted }: Props) {
  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`Delete "${name}"?`)) return
    try {
      await docsApi.delete(id)
      toast.success('Document deleted')
      onDeleted()
    } catch {
      toast.error('Delete failed')
    }
  }

  if (!documents.length) {
    return <p className="text-center text-gray-500 py-8">No documents yet. Upload a PDF to get started.</p>
  }

  return (
    <ul className="divide-y divide-gray-100">
      {documents.map((doc) => {
        const isSelected = selectedIds.includes(doc.id)
        return (
          <li
            key={doc.id}
            onClick={() => { if (doc.status === 'ready') onToggle(doc.id) }}
            className={`flex items-center gap-3 p-3 rounded-lg transition cursor-pointer
              ${doc.status === 'ready' ? 'hover:bg-gray-50' : 'opacity-60 cursor-default'}
              ${isSelected ? 'bg-blue-50 ring-1 ring-blue-300' : ''}`}
          >
            <FileText className="h-5 w-5 text-red-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{doc.original_name}</p>
              <p className="text-xs text-gray-400">
                {String((doc.file_size / 1024).toFixed(0))} KB
                {doc.page_count ? ` · ${String(doc.page_count)} pages` : ''}
                {doc.chunk_count ? ` · ${String(doc.chunk_count)} chunks` : ''}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {statusIcon[doc.status]}
              <button
                onClick={(e) => { void handleDelete(doc.id, doc.original_name, e) }}
                className="p-1 text-gray-300 hover:text-red-500 transition"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
