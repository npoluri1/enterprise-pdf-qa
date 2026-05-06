import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { docsApi } from '../api/client'

export interface Document {
  id: string
  filename: string
  original_name: string
  file_size: number
  status: 'pending' | 'processing' | 'ready' | 'failed'
  page_count: number | null
  chunk_count: number | null
  created_at: string
}

interface DocumentList {
  items: Document[]
  total: number
}

export function useDocuments() {
  return useQuery<DocumentList>({
    queryKey: ['documents'],
    queryFn: async () => {
      const resp = await docsApi.list()
      return resp.data as DocumentList
    },
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      const hasProcessing = items.some(
        (d) => d.status === 'pending' || d.status === 'processing'
      )
      return hasProcessing ? 3000 : false
    },
    staleTime: 5_000,
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => docsApi.upload(file),
    onSuccess: (_, file) => {
      toast.success(`"${file.name}" uploaded — processing…`)
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast.error(err?.response?.data?.detail ?? 'Upload failed')
    },
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => docsApi.delete(id),
    onSuccess: () => {
      toast.success('Document deleted')
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: () => {
      toast.error('Delete failed')
    },
  })
}
