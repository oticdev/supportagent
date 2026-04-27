import { useState, useRef, useCallback, useEffect } from "react"
import { Phone, PhoneOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { UserInfo } from "@/components/UserInfoGate"

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

type CallState = "idle" | "connecting" | "connected" | "ended"
type AgentState = "listening" | "thinking" | "speaking"

type Message = {
  id: string
  role: "user" | "assistant"
  text: string
  done: boolean
}

// ── Tool definitions sent via the data channel session.update ─────────────────
// These are plain JSON schema objects — no SDK dependency.

const TOOLS = [
  {
    type: "function",
    name: "search_knowledge_base",
    description:
      "Search the RelayPay knowledge base for product information, pricing, policies, compliance rules, and FAQs. Always call this before answering any product question.",
    parameters: {
      type: "object",
      properties: { query: { type: "string", description: "Specific search query" } },
      required: ["query"],
    },
  },
  {
    type: "function",
    name: "check_calendar_availability",
    description:
      "Check available time slots for a support call. Pass the customer's preferred date as a starting point.",
    parameters: {
      type: "object",
      properties: {
        preferred_date: {
          type: "string",
          description: "ISO 8601 date/datetime to start searching from, e.g. 2025-01-20",
        },
      },
      required: ["preferred_date"],
    },
  },
  {
    type: "function",
    name: "create_calendar_event",
    description: "Book a 30-minute support call on the calendar and send an invite to the customer.",
    parameters: {
      type: "object",
      properties: {
        attendee_email: { type: "string", description: "Customer email address" },
        start_time: { type: "string", description: "ISO 8601 datetime for the meeting start" },
        summary: {
          type: "string",
          description: "Meeting title, defaults to RelayPay Support Call",
        },
      },
      required: ["attendee_email", "start_time"],
    },
  },
  {
    type: "function",
    name: "escalate_to_human",
    description:
      "Record the escalation in the database and notify the support team via Slack. Call this AFTER the calendar event is created.",
    parameters: {
      type: "object",
      properties: {
        user_name: { type: "string", description: "Customer full name" },
        user_email: { type: "string", description: "Customer email" },
        category: {
          type: "string",
          enum: ["compliance", "account", "dispute", "other"],
          description: "Escalation category",
        },
        reason: { type: "string", description: "Brief summary of why escalation is needed" },
        appointment_time: { type: "string", description: "ISO 8601 datetime of booked meeting" },
        calendar_event_id: { type: "string", description: "Google Calendar event ID" },
      },
      required: ["user_name", "user_email", "category", "reason"],
    },
  },
]

// ── Backend tool dispatch ─────────────────────────────────────────────────────

async function callTool(toolName: string, args: Record<string, unknown>): Promise<string> {
  const res = await fetch(`${BASE}/api/voice/tool`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: toolName, args }),
  })
  if (!res.ok) throw new Error(`Tool ${toolName} failed: ${await res.text()}`)
  const data = await res.json()
  return data.result ?? JSON.stringify(data)
}

// ── Component ─────────────────────────────────────────────────────────────────

export function VoiceAgent({ userInfo }: { userInfo: UserInfo }) {
  const [callState, setCallState] = useState<CallState>("idle")
  const [agentState, setAgentState] = useState<AgentState>("listening")
  const [messages, setMessages] = useState<Message[]>([])
  const [activeTool, setActiveTool] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const pcRef = useRef<RTCPeerConnection | null>(null)
  const dcRef = useRef<RTCDataChannel | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // ── Message state helpers ──────────────────────────────────────────────────

  const upsertMessage = useCallback((id: string, role: "user" | "assistant", text: string, done: boolean) => {
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === id)
      if (idx === -1) return [...prev, { id, role, text, done }]
      const next = [...prev]
      next[idx] = { ...next[idx], text, done }
      return next
    })
  }, [])

  // ── Data channel event handler ─────────────────────────────────────────────

  const handleServerEvent = useCallback(
    async (event: Record<string, unknown>) => {
      const type = event.type as string
      console.log("[voice]", type, event)

      switch (type) {
        case "session.updated":
          setCallState("connected")
          break

        // Agent transcript (streaming)
        case "response.audio_transcript.delta": {
          const itemId = event.item_id as string
          const delta = event.delta as string
          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === itemId)
            if (idx === -1) return [...prev, { id: itemId, role: "assistant", text: delta, done: false }]
            const next = [...prev]
            next[idx] = { ...next[idx], text: next[idx].text + delta }
            return next
          })
          break
        }

        case "response.audio_transcript.done": {
          const itemId = event.item_id as string
          setMessages((prev) =>
            prev.map((m) => (m.id === itemId ? { ...m, done: true } : m))
          )
          break
        }

        // User speech transcript (from Whisper)
        case "conversation.item.input_audio_transcription.completed": {
          const itemId = event.item_id as string
          const transcript = event.transcript as string
          if (transcript?.trim()) {
            upsertMessage(itemId, "user", transcript.trim(), true)
          }
          break
        }

        // VAD state
        case "input_audio_buffer.speech_started":
          setAgentState("listening")
          break
        case "input_audio_buffer.speech_stopped":
          setAgentState("thinking")
          break

        // Response lifecycle
        case "response.created":
          setAgentState("thinking")
          break
        case "response.audio.delta":
          setAgentState("speaking")
          break
        case "response.audio.done":
        case "response.done":
          setAgentState("listening")
          break

        // Tool calls
        case "response.output_item.added": {
          const item = event.item as Record<string, unknown> | undefined
          if (item?.type === "function_call") {
            setActiveTool(item.name as string)
          }
          break
        }
        case "response.function_call_arguments.done": {
          const name = event.name as string
          const callId = event.call_id as string
          let args: Record<string, unknown> = {}
          try {
            args = JSON.parse((event.arguments as string) ?? "{}")
          } catch {
            /* ignore parse errors */
          }
          setActiveTool(name)
          let result = "Error executing tool"
          try {
            result = await callTool(name, args)
          } catch (err) {
            result = err instanceof Error ? err.message : "Tool execution failed"
          }
          setActiveTool(null)
          if (dcRef.current?.readyState === "open") {
            dcRef.current.send(
              JSON.stringify({
                type: "conversation.item.create",
                item: { type: "function_call_output", call_id: callId, output: result },
              })
            )
            dcRef.current.send(JSON.stringify({ type: "response.create" }))
          }
          break
        }

        case "error": {
          const err = event.error as Record<string, unknown> | undefined
          const msg = String(err?.message ?? err?.code ?? JSON.stringify(event.error))
          console.error("[voice] error:", msg, event)
          setError(msg)
          break
        }

        default:
          break
      }
    },
    [upsertMessage]
  )

  // ── Start / end call ───────────────────────────────────────────────────────

  const startCall = useCallback(async () => {
    setCallState("connecting")
    setError(null)
    setMessages([])

    try {
      // 1. Get ephemeral key + instructions from backend (pass user info for personalised prompt)
      const resp = await fetch(`${BASE}/api/voice/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: userInfo.name, user_email: userInfo.email }),
      })
      if (!resp.ok) throw new Error(`Session creation failed: ${await resp.text()}`)
      const { client_secret, instructions } = await resp.json()

      // 2. Set up RTCPeerConnection
      const pc = new RTCPeerConnection()
      pcRef.current = pc

      // 3. Wire up remote audio (agent speech) — browser handles decode + playback
      pc.ontrack = (e) => {
        const audio = document.createElement("audio")
        audio.autoplay = true
        audio.srcObject = e.streams[0]
        // Keep a reference so it doesn't get GC'd
        ;(window as unknown as Record<string, unknown>).__voiceAudio = audio
      }

      // 4. Create the OAI data channel for events
      const dc = pc.createDataChannel("oai-events")
      dcRef.current = dc

      dc.addEventListener("open", () => {
        // Send session config — no SDK, no spurious session.type field
        dc.send(
          JSON.stringify({
            type: "session.update",
            session: {
              instructions,
              voice: "alloy",
              turn_detection: {
                type: "server_vad",
                threshold: 0.5,
                prefix_padding_ms: 300,
                silence_duration_ms: 500,
              },
              input_audio_transcription: { model: "gpt-4o-transcribe" },
              tools: TOOLS,
              tool_choice: "auto",
            },
          })
        )
      })

      dc.addEventListener("message", (e) => {
        try {
          handleServerEvent(JSON.parse(e.data))
        } catch {
          /* ignore parse errors */
        }
      })

      dc.addEventListener("error", (e) => {
        console.error("[voice] data channel error", e)
        setError("Data channel error — see console")
      })

      // 5. Capture microphone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      pc.addTrack(stream.getAudioTracks()[0])

      // 6. SDP offer → OpenAI → set answer
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      const sdpResp = await fetch(
        `https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${client_secret}`,
            "Content-Type": "application/sdp",
          },
          body: offer.sdp,
        }
      )
      if (!sdpResp.ok) {
        const txt = await sdpResp.text()
        throw new Error(`OpenAI WebRTC handshake failed: ${txt}`)
      }

      const answerSdp = await sdpResp.text()
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp })

      // setCallState("connected") happens when session.updated arrives via data channel

    } catch (err) {
      console.error("[voice] startCall error:", err)
      setError(err instanceof Error ? err.message : "Failed to connect")
      setCallState("idle")
    }
  }, [handleServerEvent])

  const endCall = useCallback(() => {
    dcRef.current?.close()
    dcRef.current = null
    pcRef.current?.close()
    pcRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setCallState("ended")
    setAgentState("listening")
    setActiveTool(null)
  }, [])

  // Cleanup on unmount
  useEffect(
    () => () => {
      dcRef.current?.close()
      pcRef.current?.close()
      streamRef.current?.getTracks().forEach((t) => t.stop())
    },
    []
  )

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Transcript */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {callState === "idle" && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center text-muted-foreground">
            <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
              <Phone size={28} className="opacity-40" />
            </div>
            <p className="text-sm">Tap the button below to start a voice conversation.</p>
            <p className="text-xs">No button-holding — just speak naturally.</p>
          </div>
        )}

        {callState === "ended" && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm">
            Call ended.
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn("flex", msg.role === "user" ? "flex-row-reverse" : "flex-row")}
          >
            <div
              className={cn(
                "max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                msg.role === "user"
                  ? "bg-primary text-primary-foreground rounded-tr-sm"
                  : "bg-muted text-foreground rounded-tl-sm",
                !msg.done ? "opacity-60" : ""
              )}
            >
              {msg.text}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mb-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="border-t bg-background p-6 flex flex-col items-center gap-4">
        {callState === "connected" && (
          <div className="flex flex-col items-center gap-1">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  agentState === "speaking"
                    ? "bg-emerald-500 animate-pulse"
                    : agentState === "thinking"
                      ? "bg-yellow-500 animate-pulse"
                      : "bg-blue-400"
                )}
              />
              {agentState === "speaking"
                ? "Agent is speaking…"
                : agentState === "thinking"
                  ? activeTool
                    ? `Using ${activeTool.replace(/_/g, " ")}…`
                    : "Thinking…"
                  : "Listening…"}
            </div>
          </div>
        )}

        {callState === "idle" || callState === "ended" ? (
          <button
            onClick={startCall}
            className="w-16 h-16 rounded-full bg-emerald-500 hover:bg-emerald-600 text-white flex items-center justify-center shadow-lg transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2"
            aria-label="Start call"
          >
            <Phone size={24} />
          </button>
        ) : callState === "connecting" ? (
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
            <Loader2 size={24} className="animate-spin text-muted-foreground" />
          </div>
        ) : (
          <button
            onClick={endCall}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center shadow-lg transition-colors focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2"
            aria-label="End call"
          >
            <PhoneOff size={24} />
          </button>
        )}

        <p className="text-xs text-muted-foreground">
          {callState === "idle" || callState === "ended"
            ? "Tap to start a call"
            : callState === "connecting"
              ? "Connecting…"
              : "Tap to end the call"}
        </p>
      </div>
    </div>
  )
}
