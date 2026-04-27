import { useState, useRef, useEffect, useCallback } from "react"
import { Send, Trash2, Bot, User } from "lucide-react"
import { sendChat, clearSession, type ChatResponse } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { UserInfo } from "@/components/UserInfoGate"

type Message = {
  id: string
  role: "user" | "assistant"
  content: string
  route?: ChatResponse["route"]
}

const ROUTE_COLORS: Record<string, string> = {
  ANSWER: "bg-emerald-100 text-emerald-800",
  ESCALATE: "bg-orange-100 text-orange-800",
  CLARIFY: "bg-blue-100 text-blue-800",
  DECLINE: "bg-red-100 text-red-800",
}

export function ChatAgent({ userInfo }: { userInfo: UserInfo }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const submit = useCallback(async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setLoading(true)

    try {
      const res = await sendChat(text, sessionId, userInfo)
      if (!sessionId) setSessionId(res.session_id)
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.response,
        route: res.route,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Sorry, something went wrong. Please try again.",
        route: "DECLINE",
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const handleKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        submit()
      }
    },
    [submit]
  )

  const handleClear = useCallback(async () => {
    if (sessionId) await clearSession(sessionId)
    setMessages([])
    setSessionId(null)
  }, [sessionId])

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-3">
            <Bot size={48} className="opacity-30" />
            <p className="text-sm">
              Hi! I'm the RelayPay support agent. How can I help you today?
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn("flex gap-3", msg.role === "user" ? "flex-row-reverse" : "flex-row")}
          >
            <div
              className={cn(
                "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
              )}
            >
              {msg.role === "user" ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className={cn("max-w-[75%] space-y-1", msg.role === "user" ? "items-end" : "items-start")}>
              <div
                className={cn(
                  "rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground rounded-tr-sm"
                    : "bg-muted text-foreground rounded-tl-sm"
                )}
              >
                {msg.content}
              </div>
              {msg.route && msg.role === "assistant" && (
                <Badge
                  className={cn(
                    "text-xs font-medium ml-1",
                    ROUTE_COLORS[msg.route] ?? "bg-gray-100 text-gray-800"
                  )}
                  variant="outline"
                >
                  {msg.route}
                </Badge>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
              <Bot size={14} />
            </div>
            <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4 flex gap-2 items-end bg-background">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Type your message… (Enter to send)"
          className="resize-none min-h-[44px] max-h-32 flex-1"
          rows={1}
          disabled={loading}
        />
        <Button onClick={submit} disabled={loading || !input.trim()} size="icon">
          <Send size={16} />
        </Button>
        {messages.length > 0 && (
          <Button
            onClick={handleClear}
            variant="ghost"
            size="icon"
            title="Clear conversation"
          >
            <Trash2 size={16} />
          </Button>
        )}
      </div>
    </div>
  )
}
