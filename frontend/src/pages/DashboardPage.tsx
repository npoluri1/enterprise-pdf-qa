import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { LogOut, FileText, Zap, Bot, Building2, ChevronDown } from 'lucide-react'
import { docsApi, orgsApi } from '../api/client'
import { useAuthStore, type OrgInfo } from '../store/authStore'
import { useNavigate } from 'react-router-dom'
import { PDFUpload } from '../components/PDFUpload'
import { DocumentList } from '../components/DocumentList'
import { ChatInterface } from '../components/ChatInterface'

type Mode = 'langgraph' | 'mcp'

interface DocItem {
  id: string
  original_name: string
  file_size: number
  status: 'pending' | 'processing' | 'ready' | 'failed'
  page_count: number | null
  chunk_count: number | null
  created_at: string
}

export function DashboardPage() {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [mode, setMode] = useState<Mode>('langgraph')
  const [orgMenuOpen, setOrgMenuOpen] = useState(false)
  const { user, logout, organizations, currentOrgId, setOrganizations, setCurrentOrgId } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const currentOrg: OrgInfo | null = organizations.length > 0
    ? (organizations.find((o) => o.id === currentOrgId) ?? organizations[0])
    : null

  // Fetch orgs on mount
  useEffect(() => {
    orgsApi.list().then((resp) => {
      const orgs = (resp.data as { items: OrgInfo[] }).items
      setOrganizations(orgs)
      if (!currentOrgId && orgs.length > 0) {
        setCurrentOrgId(orgs[0].id)
      }
    }).catch(() => {
      // silently fail — user may have no orgs yet
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: docsData, isLoading } = useQuery<{
    data: { items: DocItem[] }
  }>({
    queryKey: ['documents', currentOrgId],
    queryFn: () => docsApi.list(0, 20, currentOrgId ?? undefined),
    refetchInterval: 5000,
    enabled: !!currentOrg,
  })

  const documents = docsData?.data.items ?? []

  const toggleDoc = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const switchOrg = (org: OrgInfo) => {
    setCurrentOrgId(org.id)
    setOrgMenuOpen(false)
    setSelectedIds([])
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="h-6 w-6 text-blue-600" />
          <span className="font-bold text-gray-900">Enterprise PDF Q&A</span>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full ml-2">
            RAG + Agents + MCP
          </span>
        </div>
        <div className="flex items-center gap-4">
          {/* Org selector */}
          {organizations.length > 0 && (
            <div className="relative">
              <button
                onClick={() => { setOrgMenuOpen(!orgMenuOpen) }}
                className="flex items-center gap-1.5 text-sm text-gray-600 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg px-3 py-1.5 transition"
              >
                <Building2 className="h-4 w-4" />
                <span className="max-w-[120px] truncate">{currentOrg?.name ?? 'Select org'}</span>
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
              {orgMenuOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => { setOrgMenuOpen(false) }} />
                  <div className="absolute right-0 mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1">
                    {organizations.map((org) => (
                      <button
                        key={org.id}
                        onClick={() => { switchOrg(org) }}
                        className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2
                          ${org.id === currentOrgId ? 'text-blue-600 font-medium' : 'text-gray-700'}`}
                      >
                        <Building2 className="h-4 w-4 shrink-0" />
                        <span className="truncate">{org.name}</span>
                        {org.id === currentOrgId && (
                          <span className="ml-auto text-xs text-blue-500">Active</span>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          <span className="text-sm text-gray-500">{user?.email}</span>
          <button onClick={handleLogout} className="text-gray-400 hover:text-red-500 transition">
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar – documents */}
        <aside className="w-80 bg-white border-r border-gray-200 flex flex-col shrink-0">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
              <FileText className="h-4 w-4" /> Documents
            </h2>
            <PDFUpload
              orgId={currentOrgId ?? undefined}
              onUploaded={() => { void queryClient.invalidateQueries({ queryKey: ['documents', currentOrgId] }) }}
            />
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {isLoading ? (
              <p className="text-sm text-gray-400 text-center py-4">Loading…</p>
            ) : (
              <DocumentList
                documents={documents}
                selectedIds={selectedIds}
                onToggle={toggleDoc}
                onDeleted={() => {
                  void queryClient.invalidateQueries({ queryKey: ['documents', currentOrgId] })
                  setSelectedIds([])
                }}
              />
            )}
          </div>
          {selectedIds.length > 0 && (
            <div className="p-3 border-t border-gray-100">
              <button
                onClick={() => { setSelectedIds([]) }}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Clear selection ({selectedIds.length})
              </button>
            </div>
          )}
        </aside>

        {/* Main chat area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Mode selector */}
          <div className="bg-white border-b border-gray-200 px-6 py-2 flex items-center gap-4">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Mode:</span>
            <button
              onClick={() => { setMode('langgraph') }}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition
                ${mode === 'langgraph' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              <Bot className="h-3.5 w-3.5" />
              LangGraph Multi-Agent
            </button>
            <button
              onClick={() => { setMode('mcp') }}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition
                ${mode === 'mcp' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              <Zap className="h-3.5 w-3.5" />
              Claude + MCP
            </button>
          </div>
          <div className="flex-1 overflow-hidden">
            <ChatInterface selectedDocumentIds={selectedIds} mode={mode} organizationId={currentOrgId ?? undefined} />
          </div>
        </main>
      </div>
    </div>
  )
}
