import { useState, useEffect, useCallback } from "react"
import { RefreshCw, AlertTriangle, CheckCircle, Database, Mail, PhoneCall, FlaskConical } from "lucide-react"
import {
  getAdminLogs,
  getIngestStatus,
  triggerReingest,
  type AdminCredentials,
  type AdminLog,
  type IngestStatus,
} from "@/lib/api"
import { EvalPanel } from "./EvalPanel"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  })
}

function formatAppointment(iso: string | null) {
  if (!iso) return null
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function AdminPanel({ credentials }: { credentials: AdminCredentials }) {
  const [activeTab, setActiveTab] = useState<"conversations" | "eval">("conversations")
  const [logs, setLogs] = useState<AdminLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [escalatedOnly, setEscalatedOnly] = useState(false)
  const [loadingLogs, setLoadingLogs] = useState(false)

  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null)
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestMessage, setIngestMessage] = useState<string | null>(null)

  const PAGE_SIZE = 20

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true)
    try {
      const res = await getAdminLogs(credentials, page, PAGE_SIZE, escalatedOnly)
      setLogs(res.results)
      setTotal(res.total)
    } catch (err) {
      console.error("Failed to fetch logs:", err)
    } finally {
      setLoadingLogs(false)
    }
  }, [credentials, page, escalatedOnly])

  const fetchIngestStatus = useCallback(async () => {
    try {
      const status = await getIngestStatus(credentials)
      setIngestStatus(status)
    } catch (err) {
      console.error("Failed to fetch ingest status:", err)
    }
  }, [credentials])

  useEffect(() => { fetchLogs() }, [fetchLogs])
  useEffect(() => { fetchIngestStatus() }, [fetchIngestStatus])

  const handleReingest = useCallback(async (force: boolean) => {
    setIngestLoading(true)
    setIngestMessage(null)
    try {
      const res = await triggerReingest(credentials, force)
      setIngestMessage(`${res.status} — ${res.mode}`)
      setTimeout(fetchIngestStatus, 2000)
    } catch (err) {
      setIngestMessage(err instanceof Error ? err.message : "Reingest failed")
    } finally {
      setIngestLoading(false)
    }
  }, [fetchIngestStatus])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const escalationCount = logs.filter((l) => l.escalated).length

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Admin Panel</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Conversation summaries and knowledge base management
          </p>
        </div>
        <div className="flex rounded-lg border overflow-hidden text-sm">
          <button
            onClick={() => setActiveTab("conversations")}
            className={cn("px-4 py-2 flex items-center gap-1.5 transition-colors",
              activeTab === "conversations" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
            )}
          >
            <Database size={13} /> Conversations
          </button>
          <button
            onClick={() => setActiveTab("eval")}
            className={cn("px-4 py-2 flex items-center gap-1.5 transition-colors",
              activeTab === "eval" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
            )}
          >
            <FlaskConical size={13} /> Evaluation
          </button>
        </div>
      </div>

      {activeTab === "eval" && <EvalPanel credentials={credentials} />}

      {activeTab === "conversations" && <>
      {/* Stats + Ingest */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle size={16} className="text-orange-500" />
              Escalations
            </CardTitle>
            <CardDescription>Sessions routed to a human agent</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{escalationCount}</p>
            <p className="text-xs text-muted-foreground mt-1">on this page ({total} total sessions)</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Database size={16} className="text-blue-500" />
              Knowledge Base
            </CardTitle>
            <CardDescription>
              {ingestStatus?.created_at
                ? `Last synced: ${formatDate(ingestStatus.created_at)}`
                : "Never synced"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {ingestStatus && (
              <div className="flex gap-4 text-sm">
                <span className="flex items-center gap-1">
                  <CheckCircle size={12} className="text-emerald-500" />
                  {ingestStatus.pages_synced} pages
                </span>
                <Badge variant="outline" className="text-xs">
                  {ingestStatus.status ?? "idle"}
                </Badge>
              </div>
            )}
            {ingestMessage && (
              <p className="text-xs text-muted-foreground">{ingestMessage}</p>
            )}
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleReingest(false)}
                disabled={ingestLoading}
                className="gap-1.5"
              >
                <RefreshCw size={12} className={cn(ingestLoading && "animate-spin")} />
                Sync (delta)
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => handleReingest(true)}
                disabled={ingestLoading}
              >
                Force re-ingest
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Conversation summaries table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <CardTitle className="text-base">Conversations</CardTitle>
              <CardDescription>{total} total sessions</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={escalatedOnly}
                  onChange={(e) => { setEscalatedOnly(e.target.checked); setPage(1) }}
                  className="rounded"
                />
                Escalated only
              </label>
              <Button
                size="icon-sm"
                variant="outline"
                onClick={fetchLogs}
                disabled={loadingLogs}
                title="Refresh"
              >
                <RefreshCw size={12} className={cn(loadingLogs && "animate-spin")} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-32">Started</TableHead>
                <TableHead className="w-20">Channel</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Opening message</TableHead>
                <TableHead className="w-24">Turns</TableHead>
                <TableHead className="w-28">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loadingLogs ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Loading…
                  </TableCell>
                </TableRow>
              ) : logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No sessions found
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow key={log.session_id} className={log.escalated ? "bg-orange-50/50" : ""}>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(log.started_at)}
                    </TableCell>

                    <TableCell>
                      <Badge variant="secondary" className="text-xs capitalize">
                        {log.mode ?? "chat"}
                      </Badge>
                    </TableCell>

                    <TableCell className="text-sm">
                      {log.user_name && (
                        <p className="font-medium leading-tight">{log.user_name}</p>
                      )}
                      {log.user_email ? (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Mail size={10} />
                          {log.user_email}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">anonymous</span>
                      )}
                    </TableCell>

                    <TableCell className="text-sm max-w-[260px]">
                      <span className="line-clamp-2 text-muted-foreground">{log.first_message}</span>
                      {log.escalated && log.escalation_reason && (
                        <p className="text-xs text-orange-700 mt-0.5 line-clamp-1">
                          ↳ {log.escalation_reason}
                        </p>
                      )}
                    </TableCell>

                    <TableCell className="text-xs text-muted-foreground text-center">
                      {log.turns}
                    </TableCell>

                    <TableCell>
                      {log.escalated ? (
                        <div className="space-y-1">
                          <Badge variant="outline" className="text-xs bg-orange-100 text-orange-800 border-orange-200 flex items-center gap-1 w-fit">
                            <AlertTriangle size={10} />
                            Escalated
                          </Badge>
                          {log.appointment_time && (
                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                              <PhoneCall size={10} />
                              {formatAppointment(log.appointment_time)}
                            </span>
                          )}
                        </div>
                      ) : (
                        <Badge variant="outline" className="text-xs bg-emerald-100 text-emerald-800 border-emerald-200">
                          Resolved
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t text-sm">
              <span className="text-muted-foreground text-xs">
                Page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      </>}
    </div>
  )
}
