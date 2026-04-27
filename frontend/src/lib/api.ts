const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

function adminHeaders(credentials: AdminCredentials): HeadersInit {
  return {
    Authorization: `Basic ${btoa(`${credentials.username}:${credentials.password}`)}`,
  }
}

export type AdminCredentials = { username: string; password: string }

export type ChatResponse = {
  session_id: string
  response: string
  route: "ANSWER" | "ESCALATE" | "CLARIFY" | "DECLINE"
}

export type AdminLog = {
  id: number
  session_id: string
  mode: string
  transcript: string
  response: string
  route: string | null
  escalated: boolean
  created_at: string
}

export type AdminLogsResponse = {
  results: AdminLog[]
  total: number
  page: number
  page_size: number
}

export type IngestStatus = {
  status: string | null
  pages_synced: number
  created_at: string | null
}

export type UserInfo = { name: string; email: string }

export async function sendChat(
  message: string,
  sessionId: string | null,
  userInfo?: UserInfo
): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_name: userInfo?.name,
      user_email: userInfo?.email,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/api/chat/${sessionId}`, { method: "DELETE" })
}

export async function sendVoice(
  audioBlob: Blob,
  sessionId: string | null
): Promise<{ audio: Blob; transcript: string; route: string; sessionId: string }> {
  const form = new FormData()
  form.append("audio", audioBlob, "recording.webm")
  if (sessionId) form.append("session_id", sessionId)

  const res = await fetch(`${BASE}/api/voice`, { method: "POST", body: form })
  if (!res.ok) throw new Error(await res.text())

  const transcript = res.headers.get("X-Transcript") ?? ""
  const route = res.headers.get("X-Route") ?? "ANSWER"
  const newSessionId = res.headers.get("X-Session-Id") ?? sessionId ?? ""
  const audio = await res.blob()

  return { audio, transcript, route, sessionId: newSessionId }
}

export async function verifyAdminCredentials(creds: AdminCredentials): Promise<void> {
  const res = await fetch(`${BASE}/api/admin/ingest-status`, { headers: adminHeaders(creds) })
  if (res.status === 401) throw new Error("Invalid username or password")
  if (!res.ok) throw new Error("Server error — try again")
}

export async function getAdminLogs(
  creds: AdminCredentials,
  page = 1,
  pageSize = 20,
  route?: string
): Promise<AdminLogsResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (route) params.set("route", route)
  const res = await fetch(`${BASE}/api/admin/logs?${params}`, { headers: adminHeaders(creds) })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getIngestStatus(creds: AdminCredentials): Promise<IngestStatus> {
  const res = await fetch(`${BASE}/api/admin/ingest-status`, { headers: adminHeaders(creds) })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function triggerReingest(
  creds: AdminCredentials,
  force = false
): Promise<{ status: string; mode: string }> {
  const res = await fetch(`${BASE}/api/admin/reingest?force=${force}`, {
    method: "POST",
    headers: adminHeaders(creds),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
