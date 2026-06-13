export const statusLabels: Record<string, string> = {
  queued: '排队中',
  processing: '处理中',
  ready: '就绪',
  failed: '失败',
}

export const statusColors: Record<string, string> = {
  queued: 'bg-[var(--text-tertiary)]',
  processing: 'bg-brand-500',
  ready: 'bg-[var(--color-success)]',
  failed: 'bg-[var(--color-error)]',
}
