import MessageList from './MessageList'
import ChatInput from './ChatInput'
import { useChatContext } from '@/contexts/ChatContext'

export default function ChatArea() {
  const { messages, isStreaming, sendMessage } = useChatContext()

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[var(--bg-primary)]">
      <MessageList messages={messages} isStreaming={isStreaming} onQuickAsk={sendMessage} />
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}
