import MessageList from './MessageList'
import ChatInput from './ChatInput'
import { useChat } from '@/hooks/useChat'

export default function ChatArea() {
  const { messages, isStreaming, sendMessage } = useChat()

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[var(--bg-primary)]">
      <MessageList messages={messages} isStreaming={isStreaming} />
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}
