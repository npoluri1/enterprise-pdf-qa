import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface OrgInfo {
  id: string
  name: string
  slug: string
  is_active: boolean
  member_count: number
}

interface AuthState {
  token: string | null
  user: { email: string; full_name: string | null } | null
  organizations: OrgInfo[]
  currentOrgId: string | null
  setToken: (token: string) => void
  setUser: (user: AuthState['user']) => void
  setOrganizations: (orgs: OrgInfo[]) => void
  setCurrentOrgId: (orgId: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      organizations: [],
      currentOrgId: null,
      setToken: (token) => {
        localStorage.setItem('access_token', token)
        set({ token })
      },
      setUser: (user) => set({ user }),
      setOrganizations: (organizations) => set({ organizations }),
      setCurrentOrgId: (currentOrgId) => set({ currentOrgId }),
      logout: () => {
        localStorage.removeItem('access_token')
        set({ token: null, user: null, organizations: [], currentOrgId: null })
      },
    }),
    { name: 'auth-storage' }
  )
)
