import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DocumentList } from '../../components/DocumentList'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  docsApi: { delete: vi.fn() },
}))
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

const makeDoc = (overrides = {}) => ({
  id: 'doc-1',
  original_name: 'report.pdf',
  file_size: 204800,
  status: 'ready' as const,
  page_count: 10,
  chunk_count: 40,
  created_at: '2025-01-01T00:00:00Z',
  ...overrides,
})

describe('DocumentList', () => {
  const onToggle = vi.fn()
  const onDeleted = vi.fn()

  beforeEach(() => vi.clearAllMocks())

  it('shows empty state message when no documents', () => {
    render(<DocumentList documents={[]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    expect(screen.getByText(/No documents yet/)).toBeInTheDocument()
  })

  it('renders document names', () => {
    render(<DocumentList documents={[makeDoc()]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    expect(screen.getByText('report.pdf')).toBeInTheDocument()
  })

  it('shows page count when available', () => {
    render(<DocumentList documents={[makeDoc()]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    expect(screen.getByText(/10 pages/)).toBeInTheDocument()
  })

  it('calls onToggle when ready document is clicked', () => {
    render(<DocumentList documents={[makeDoc()]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    fireEvent.click(screen.getByText('report.pdf'))
    expect(onToggle).toHaveBeenCalledWith('doc-1')
  })

  it('does not call onToggle for non-ready document', () => {
    const doc = makeDoc({ status: 'processing' })
    render(<DocumentList documents={[doc]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    fireEvent.click(screen.getByText('report.pdf'))
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('highlights selected documents', () => {
    const { container } = render(
      <DocumentList documents={[makeDoc()]} selectedIds={['doc-1']} onToggle={onToggle} onDeleted={onDeleted} />
    )
    const li = container.querySelector('li')
    expect(li?.className).toContain('bg-blue-50')
  })

  it('calls docsApi.delete on delete confirm', async () => {
    vi.mocked(client.docsApi.delete).mockResolvedValueOnce({} as never)
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(<DocumentList documents={[makeDoc()]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    const deleteBtn = screen.getByRole('button')
    fireEvent.click(deleteBtn)

    await waitFor(() => {
      expect(client.docsApi.delete).toHaveBeenCalledWith('doc-1')
      expect(onDeleted).toHaveBeenCalled()
    })
  })

  it('does not delete when confirm is cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<DocumentList documents={[makeDoc()]} selectedIds={[]} onToggle={onToggle} onDeleted={onDeleted} />)
    const deleteBtn = screen.getByRole('button')
    fireEvent.click(deleteBtn)
    expect(client.docsApi.delete).not.toHaveBeenCalled()
  })
})
