import { useState, useEffect, useRef, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Document } from '@/types'
import { listDocuments, uploadDocument, deleteDocument, searchKnowledgeBase, type SearchResultItem } from '@/services/ragService'
import { IconFile, IconUpload, IconTrash, IconSearch, IconRefresh, IconX } from '@/components/ui/Icons'
import { statusLabels, statusColors } from '@/components/knowledge/constants'

// 文档解析/向量化是异步任务：上传后状态会先 queued 再 processing。
// 不轮询的话列表会一直停在"排队中"，必须手动刷新才能看到 ready。
const POLL_INTERVAL_MS = 3000

const ACCEPTED_EXTENSIONS = '.txt,.md,.pdf,.docx,.pptx'

// 后端对 .doc/.ppt 和超限文件会返回可操作的中文提示，别再吞成"上传失败，请重试"
function apiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { detail?: unknown; msg?: unknown } } })?.response?.data
  const message = data?.detail ?? data?.msg
  return typeof message === 'string' && message ? message : fallback
}

export default function KnowledgePanel() {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [queryResult, setQueryResult] = useState<SearchResultItem[] | null>(null)
  const [querying, setQuerying] = useState(false)
  const [queryError, setQueryError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const pollInFlight = useRef(false)

  const hasPendingDocuments = documents.some(
    (doc) => doc.status === 'queued' || doc.status === 'processing'
  )

  async function loadDocs() {
    setError('')
    try {
      const data = await listDocuments()
      setDocuments(data)
    } catch (err) {
      setError(apiErrorMessage(err, '加载文档失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDocs()
  }, [])

  // 只要还有文档在处理，就自动轮询；全部结束（ready/failed）后自动停
  useEffect(() => {
    if (!hasPendingDocuments) return

    const timer = window.setInterval(async () => {
      if (pollInFlight.current) return
      pollInFlight.current = true
      try {
        await loadDocs()
      } finally {
        pollInFlight.current = false
      }
    }, POLL_INTERVAL_MS)

    return () => window.clearInterval(timer)
  }, [documents])

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    setUploading(true)
    try {
      await uploadDocument(file)
      await loadDocs()
    } catch (err) {
      setError(apiErrorMessage(err, '上传失败，请重试'))
    }
    if (fileRef.current) fileRef.current.value = ''
    setUploading(false)
  }

  async function handleDelete(id: number) {
    setError('')
    try {
      await deleteDocument(id)
      await loadDocs()
    } catch (err) {
      setError(apiErrorMessage(err, '删除失败，请重试'))
    }
  }

  async function handleQuery() {
    if (!query.trim() || querying) return
    setQuerying(true)
    setQueryResult(null)
    setQueryError('')
    try {
      const result = await searchKnowledgeBase(query.trim())
      setQueryResult(result.results)
      if (result.results.length === 0) setQueryError('没有找到相关片段，试试换个说法')
    } catch (err) {
      setQueryError(apiErrorMessage(err, '搜索失败，请重试'))
    } finally {
      setQuerying(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={handleUpload}
          className="hidden"
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="w-full border-2 border-dashed border-[var(--border-primary)] rounded-xl p-6 text-center hover:border-brand-500/50 transition-colors cursor-pointer disabled:opacity-50"
        >
          <IconUpload className="mx-auto mb-2 text-[var(--text-tertiary)]" />
          <p className="text-sm text-[var(--text-tertiary)]">
            {uploading ? '上传中...' : '点击上传文档'}
          </p>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">支持 .txt .md .pdf .docx .pptx（.doc/.ppt 请另存为新格式）</p>
        </button>
      </div>

      {error && <p className="text-sm text-[var(--color-error)] bg-[var(--color-error)]/10 rounded-lg px-3 py-2">{error}</p>}

      <button
        type="button"
        onClick={() => navigate('/knowledge')}
        className="w-full text-left text-xs text-brand-500 hover:text-brand-400 transition-colors"
      >
        打开完整知识库 / 问答 →
      </button>

      <div>
        <div className="relative">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
            placeholder="搜索知识库..."
            className="w-full h-9 pl-9 pr-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
          />
        </div>

        {querying && (
          <div className="mt-2 text-xs text-[var(--text-tertiary)] flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            正在查询...
          </div>
        )}

        {queryError && (
          <div className="mt-2 text-xs text-[var(--color-error)]">{queryError}</div>
        )}

        {queryResult && (
          <div className="mt-2 p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase">搜索结果 ({queryResult.length})</span>
              <button onClick={() => setQueryResult(null)} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
                <IconX />
              </button>
            </div>
            {queryResult.map((item, i) => (
              <div key={i} className="mt-1 pt-1 border-t border-[var(--border-primary)] first:border-t-0 first:mt-0 first:pt-0">
                <p className="text-xs text-[var(--text-tertiary)] mb-0.5">[{i + 1}] 文档 #{item.document_id}</p>
                <p className="text-sm text-[var(--text-primary)] leading-relaxed line-clamp-4">{item.content}</p>
              </div>
            ))}
            <p className="mt-2 text-xs text-[var(--text-tertiary)]">想基于结果深入问答？去对话框直接提问</p>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
            文档列表
          </span>
          <div className="flex items-center gap-2">
            {hasPendingDocuments && (
              <span className="text-xs text-[var(--text-tertiary)] flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
                处理中，自动刷新
              </span>
            )}
            <button
              onClick={loadDocs}
              className="p-1 rounded text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
            >
              <IconRefresh />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 rounded-lg bg-[var(--bg-tertiary)] animate-pulse" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--text-tertiary)]">暂无文档</p>
            <p className="text-xs text-[var(--text-tertiary)] mt-1">上传文档以开始构建知识库</p>
          </div>
        ) : (
          <div className="space-y-1">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors group">
                <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center shrink-0">
                  <IconFile className="text-[var(--text-tertiary)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[var(--text-primary)] truncate">{doc.filename}</p>
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {statusLabels[doc.status] || doc.status}
                    {doc.status === 'ready' && ` · ${doc.chunks_count} chunks`}
                  </p>
                </div>
                <span className={`w-2 h-2 rounded-full shrink-0 ${statusColors[doc.status] || statusColors.queued}`} />
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="shrink-0 p-1 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all"
                >
                  <IconTrash />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
