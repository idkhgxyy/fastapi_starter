interface Props {
  status: 'todo' | 'in_progress' | 'done'
}

const styles: Record<string, string> = {
  todo: 'bg-[var(--text-tertiary)]/10 text-[var(--text-tertiary)]',
  in_progress: 'bg-brand-500/10 text-brand-500',
  done: 'bg-[var(--color-success)]/10 text-[var(--color-success)]',
}

const labels: Record<string, string> = {
  todo: '待办',
  in_progress: '进行中',
  done: '已完成',
}

export default function TaskStatusBadge({ status }: Props) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}
