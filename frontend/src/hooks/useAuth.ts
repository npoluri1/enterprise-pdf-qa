import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { authApi } from '../api/client'
import { useAuthStore } from '../store/authStore'

export function useLogin() {
  const [loading, setLoading] = useState(false)
  const { setToken, setUser } = useAuthStore()
  const navigate = useNavigate()

  const login = async (email: string, password: string) => {
    setLoading(true)
    try {
      const resp = await authApi.login(email, password)
      setToken(resp.data.access_token)
      const meResp = await authApi.me()
      setUser(meResp.data as { email: string; full_name: string | null })
      navigate('/dashboard')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return { login, loading }
}

export function useRegister() {
  const [loading, setLoading] = useState(false)

  const register = async (
    email: string,
    password: string,
    fullName?: string,
    onSuccess?: () => void
  ) => {
    setLoading(true)
    try {
      await authApi.register(email, password, fullName)
      toast.success('Account created! Please log in.')
      onSuccess?.()
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return { register, loading }
}

export function useLogout() {
  const { logout } = useAuthStore()
  const navigate = useNavigate()

  return () => {
    logout()
    navigate('/login')
  }
}
