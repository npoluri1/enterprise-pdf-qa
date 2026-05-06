import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CitationPanel } from '../../components/CitationPanel'

const mockCitations = [
  {
    chunk_id: 'chunk-1',
    document_id: 'doc-1',
    document_name: 'annual_report.pdf',
    page_number: 4,
    content: 'The total revenue for the year was $10M.',
    relevance_score: 0.92,
  },
  {
    chunk_id: 'chunk-2',
    document_id: 'doc-1',
    document_name: 'annual_report.pdf',
    page_number: 8,
    content: 'Operating expenses increased by 15%.',
    relevance_score: 0.78,
  },
]

describe('CitationPanel', () => {
  it('renders nothing when citations are empty', () => {
    const { container } = render(<CitationPanel citations={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows citation count in header', () => {
    render(<CitationPanel citations={mockCitations} />)
    expect(screen.getByText(/Sources \(2\)/)).toBeInTheDocument()
  })

  it('renders document names', () => {
    render(<CitationPanel citations={mockCitations} />)
    const names = screen.getAllByText('annual_report.pdf')
    expect(names.length).toBeGreaterThan(0)
  })

  it('shows page numbers', () => {
    render(<CitationPanel citations={mockCitations} />)
    expect(screen.getByText('p.4')).toBeInTheDocument()
    expect(screen.getByText('p.8')).toBeInTheDocument()
  })

  it('expands content on click', () => {
    render(<CitationPanel citations={mockCitations} />)
    // Content should not be visible initially
    expect(screen.queryByText('The total revenue for the year was $10M.')).not.toBeInTheDocument()

    // Click to expand first citation
    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[0])

    expect(screen.getByText('The total revenue for the year was $10M.')).toBeInTheDocument()
  })

  it('collapses content on second click', () => {
    render(<CitationPanel citations={mockCitations} />)
    const buttons = screen.getAllByRole('button')

    fireEvent.click(buttons[0]) // expand
    expect(screen.getByText('The total revenue for the year was $10M.')).toBeInTheDocument()

    fireEvent.click(buttons[0]) // collapse
    expect(screen.queryByText('The total revenue for the year was $10M.')).not.toBeInTheDocument()
  })

  it('shows relevance score percentage', () => {
    render(<CitationPanel citations={mockCitations} />)
    expect(screen.getByText('92% match')).toBeInTheDocument()
    expect(screen.getByText('78% match')).toBeInTheDocument()
  })
})
