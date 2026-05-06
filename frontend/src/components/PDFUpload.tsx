import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import { docsApi } from '../api/client'
import toast from 'react-hot-toast'

interface Props {
  onUploaded: () => void
}

export function PDFUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback(async (accepted: File[]) => {
    for (const file of accepted) {
      setUploading(true)
      try {
        await docsApi.upload(file)
        toast.success(`"${file.name}" uploaded – processing…`)
        onUploaded()
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || 'Upload failed')
      } finally {
        setUploading(false)
      }
    }
  }, [onUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  })

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
        ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'}`}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <Loader className="mx-auto h-10 w-10 text-blue-500 animate-spin" />
      ) : (
        <Upload className="mx-auto h-10 w-10 text-gray-400" />
      )}
      <p className="mt-3 text-sm font-medium text-gray-700">
        {isDragActive ? 'Drop your PDFs here' : 'Drag & drop PDFs, or click to select'}
      </p>
      <p className="text-xs text-gray-400 mt-1">Max 50 MB per file</p>
    </div>
  )
}
