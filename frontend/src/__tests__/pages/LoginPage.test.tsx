import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginPage } from '../../pages/LoginPage'
import * as client from '../../api/client'

vi.mock('../../api/client', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
  },
}))
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
)

describe('LoginPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders login form by default', () => {
    render(<LoginPage />, { wrapper })
    expect(screen.getByText('Sign in to your account')).toBeInTheDocument()
  })

  it('switches to register mode', () => {
    render(<LoginPage />, { wrapper })
    fireEvent.click(screen.getByText('Register'))
    expect(screen.getByText('Create an account')).toBeInTheDocument()
  })

  it('submits login with email and password', async () => {
    vi.mocked(client.authApi.login).mockResolvedValueOnce({
      data: { access_token: 'test-token', token_type: 'bearer' },
    } as never)
    vi.mocked(client.authApi.me).mockResolvedValueOnce({
      data: { email: 'test@example.com', full_name: null, is_active: true },
    } as never)

    render(<LoginPage />, { wrapper })
    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'test@example.com' } })
    fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: 'Pass123!' } })
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))

    await waitFor(() => {
      expect(client.authApi.login).toHaveBeenCalledWith('test@example.com', 'Pass123!')
    })
  })

  it('shows error toast on login failure', async () => {
    const toast = await import('react-hot-toast')
    vi.mocked(client.authApi.login).mockRejectedValueOnce({
      response: { data: { detail: 'Invalid credentials' } },
    } as never)

    render(<LoginPage />, { wrapper })
    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'bad@example.com' } })
    fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))

    await waitFor(() => {
      expect(toast.default.error).toHaveBeenCalledWith('Invalid credentials')
    })
  })

  it('disables submit button while loading', async () => {
    vi.mocked(client.authApi.login).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    )

    render(<LoginPage />, { wrapper })
    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'test@example.com' } })
    fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: 'Pass123!' } })

    const btn = screen.getByRole('button', { name: /Sign in/i })
    fireEvent.click(btn)

    await waitFor(() => {
      expect(btn).toBeDisabled()
    })
  })
})
