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
  session_id: string
  mode: string
  user_email: string | null
  user_name: string | null
  turns: number
  first_message: string
  escalated: boolean
  escalation_category: string | null
  escalation_reason: string | null
  appointment_time: string | null
  started_at: string
  last_activity: string
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
  escalatedOnly = false
): Promise<AdminLogsResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (escalatedOnly) params.set("escalated_only", "true")
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

// ── Evaluation ────────────────────────────────────────────────────────────────

export type EvalCaseResult = {
  case_id: string
  query: string
  actual_route: string
  expected_route: string
  route_correct: boolean
  constraints_passed: boolean
  constraint_failures: string[]
  scores: {
    accuracy: number
    helpfulness: number
    tone: number
    safety: number
    overall: number
  }
  reasoning: string
  passed: boolean
}

export type EvalRun = {
  id: string
  total: number
  passed: number
  failed: number
  pass_rate: number
  route_accuracy: number
  avg_scores: {
    accuracy: number
    helpfulness: number
    tone: number
    safety: number
    overall: number
  }
  tags: string[] | null
  created_at: string
  results?: EvalCaseResult[]
}

export async function triggerEval(creds: AdminCredentials): Promise<{ status: string; scope: string }> {
  const res = await fetch(`${BASE}/api/admin/eval/run`, {
    method: "POST",
    headers: adminHeaders(creds),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getLatestEvalRun(creds: AdminCredentials): Promise<EvalRun | null> {
  const res = await fetch(`${BASE}/api/admin/eval/runs/latest`, { headers: adminHeaders(creds) })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  if (data.status === "never_run") return null
  return {
    ...data,
    avg_scores: {
      accuracy: data.avg_accuracy,
      helpfulness: data.avg_helpfulness,
      tone: data.avg_tone,
      safety: data.avg_safety,
      overall: data.avg_overall,
    },
  }
}

export async function getEvalRuns(creds: AdminCredentials): Promise<EvalRun[]> {
  const res = await fetch(`${BASE}/api/admin/eval/runs`, { headers: adminHeaders(creds) })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return (data.runs ?? []).map((r: any) => ({
    ...r,
    avg_scores: {
      accuracy: r.avg_accuracy,
      helpfulness: r.avg_helpfulness,
      tone: r.avg_tone,
      safety: r.avg_safety,
      overall: r.avg_overall,
    },
  }))
}
