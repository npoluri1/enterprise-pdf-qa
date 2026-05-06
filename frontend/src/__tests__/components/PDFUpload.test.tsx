import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { PDFUpload } from '../../components/PDFUpload'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  docsApi: {
    upload: vi.fn(),
  },
}))

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('PDFUpload', () => {
  const onUploaded = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders upload zone', () => {
    render(<PDFUpload onUploaded={onUploaded} />)
    expect(screen.getByText(/Drag & drop PDFs/)).toBeInTheDocument()
  })

  it('shows max file size hint', () => {
    render(<PDFUpload onUploaded={onUploaded} />)
    expect(screen.getByText(/Max 50 MB/)).toBeInTheDocument()
  })

  it('calls onUploaded after successful upload', async () => {
    vi.mocked(client.docsApi.upload).mockResolvedValueOnce({
      data: { id: 'doc-1', status: 'pending', original_name: 'test.pdf' },
    } as never)

    render(<PDFUpload onUploaded={onUploaded} />)

    const file = new File(['%PDF content'], 'test.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    fireEvent.change(input)

    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledTimes(1)
    })
  })

  it('shows error toast on upload failure', async () => {
    const toast = await import('react-hot-toast')
    vi.mocked(client.docsApi.upload).mockRejectedValueOnce({
      response: { data: { detail: 'Upload failed' } },
    } as never)

    render(<PDFUpload onUploaded={onUploaded} />)

    const file = new File(['%PDF content'], 'test.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    fireEvent.change(input)

    await waitFor(() => {
      expect(toast.default.error).toHaveBeenCalled()
    })
  })
})
