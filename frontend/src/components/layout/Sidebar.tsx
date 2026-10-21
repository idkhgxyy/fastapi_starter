import { useState } from 'react'
import { IconChat, IconFile, IconPlus, IconTrash, IconWrench, IconX } from '@/components/ui/Icons'
import KnowledgePanel from '@/components/knowledge/KnowledgePanel'
import TasksPanel from '@/components/tasks/TasksPanel'
import AgentTasksPanel from '@/components/tasks/AgentTasksPanel'
import { useChatContext } from '@/contexts/ChatContext'

type Tab = 'chats' | 'knowledge' | 'tasks'

export default function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<Tab>('chats')
  const [taskTab, setTaskTab] = useState<'todo' | 'agent'>('todo')
  const {
    conversations,
    conversationId,
    loadingConversations,
    conversationsError,
    selectConversation,
    newConversation,
    removeConversation,
  } = useChatContext()

  const handleSelect = async (id: number) => {
    await selectConversation(id)
    onClose()
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`
          fixed lg:absolute inset-y-0 left-0 w-80 z-40
          border-r border-[var(--border-primary)] bg-[var(--bg-secondary)]
          flex flex-col
          transition-transform duration-200 ease-in-out
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="flex border-b border-[var(--border-primary)]">
          <button
            onClick={() => setActiveTab('chats')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-sm font-medium transition-colors ${
              activeTab === 'chats'
                ? 'text-brand-500 border-b-2 border-brand-500'
                : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
            }`}
          >
            <IconChat />
            对话
          </button>
          <button
            onClick={() => setActiveTab('knowledge')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-sm font-medium transition-colors ${
              activeTab === 'knowledge'
                ? 'text-brand-500 border-b-2 border-brand-500'
                : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
            }`}
          >
            <IconFile />
            知识库
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-sm font-medium transition-colors ${
              activeTab === 'tasks'
                ? 'text-brand-500 border-b-2 border-brand-500'
                : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
            }`}
          >
            <IconWrench />
            任务
          </button>
          <button
            onClick={onClose}
            className="px-3 py-3 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
          >
            <IconX />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {activeTab === 'knowledge' && <KnowledgePanel />}
          {activeTab === 'tasks' && (
            <div className="space-y-3">
              <div className="flex rounded-lg bg-[var(--bg-tertiary)] p-0.5 text-xs">
                <button
                  onClick={() => setTaskTab('todo')}
                  className={`flex-1 py-1.5 rounded-md transition-colors ${
                    taskTab === 'todo'
                      ? 'bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm'
                      : 'text-[var(--text-tertiary)]'
                  }`}
                >
                  待办
                </button>
                <button
                  onClick={() => setTaskTab('agent')}
                  className={`flex-1 py-1.5 rounded-md transition-colors ${
                    taskTab === 'agent'
                      ? 'bg-[var(--bg-primary)] text-[var(--text-primary)] shadow-sm'
                      : 'text-[var(--text-tertiary)]'
                  }`}
                >
                  目标成果
                </button>
              </div>
              {taskTab === 'todo' ? <TasksPanel /> : <AgentTasksPanel />}
            </div>
          )}
          {activeTab === 'chats' && (
            <div className="space-y-2">
              <button
                onClick={() => {
                  newConversation()
                  onClose()
                }}
                className="w-full flex items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-primary)] py-2 text-sm text-[var(--text-secondary)] hover:border-brand-500/50 hover:text-brand-500 transition-colors"
              >
                <IconPlus />
                新对话
              </button>

              {conversationsError && (
                <p className="text-xs text-[var(--color-error)] px-1">{conversationsError}</p>
              )}

              {loadingConversations ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-12 rounded-lg bg-[var(--bg-tertiary)] animate-pulse" />
                  ))}
                </div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-[var(--text-tertiary)]">暂无历史对话</p>
                  <p className="text-xs text-[var(--text-tertiary)] mt-1">发一条消息就会自动创建</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {conversations.map((conversation) => (
                    <div
                      key={conversation.id}
                      className={`group flex items-center rounded-lg transition-colors ${
                        conversation.id === conversationId
                          ? 'bg-brand-500/10'
                          : 'hover:bg-[var(--bg-tertiary)]'
                      }`}
                    >
                      <button
                        onClick={() => handleSelect(conversation.id)}
                        className="flex-1 min-w-0 text-left px-2.5 py-2"
                      >
                        <p
                          className={`truncate text-sm ${
                            conversation.id === conversationId
                              ? 'text-brand-500 font-medium'
                              : 'text-[var(--text-primary)]'
                          }`}
                        >
                          {conversation.title}
                        </p>
                        <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                          {conversation.message_count} 条消息
                        </p>
                      </button>
                      <button
                        onClick={() => removeConversation(conversation.id)}
                        title="删除会话"
                        className="shrink-0 p-1.5 mr-1 rounded text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-error)] transition-all"
                      >
                        <IconTrash />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
