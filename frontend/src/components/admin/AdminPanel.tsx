import { useState, useEffect, useCallback } from "react"
import { RefreshCw, AlertTriangle, CheckCircle, Database } from "lucide-react"
import {
  getAdminLogs,
  getIngestStatus,
  triggerReingest,
  type AdminCredentials,
  type AdminLog,
  type IngestStatus,
} from "@/lib/api"
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
import { Select } from "@/components/ui/select"
import { cn } from "@/lib/utils"

const ROUTE_COLORS: Record<string, string> = {
  ANSWER: "bg-emerald-100 text-emerald-800 border-emerald-200",
  ESCALATE: "bg-orange-100 text-orange-800 border-orange-200",
  CLARIFY: "bg-blue-100 text-blue-800 border-blue-200",
  DECLINE: "bg-red-100 text-red-800 border-red-200",
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  })
}

export function AdminPanel({ credentials }: { credentials: AdminCredentials }) {
  const [logs, setLogs] = useState<AdminLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [routeFilter, setRouteFilter] = useState("")
  const [loadingLogs, setLoadingLogs] = useState(false)

  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null)
  const [ingestLoading, setIngestLoading] = useState(false)
  const [ingestMessage, setIngestMessage] = useState<string | null>(null)

  const PAGE_SIZE = 20

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true)
    try {
      const res = await getAdminLogs(credentials, page, PAGE_SIZE, routeFilter || undefined)
      setLogs(res.results)
      setTotal(res.total)
    } catch (err) {
      console.error("Failed to fetch logs:", err)
    } finally {
      setLoadingLogs(false)
    }
  }, [credentials, page, routeFilter])

  const fetchIngestStatus = useCallback(async () => {
    try {
      const status = await getIngestStatus(credentials)
      setIngestStatus(status)
    } catch (err) {
      console.error("Failed to fetch ingest status:", err)
    }
  }, [credentials])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  useEffect(() => {
    fetchIngestStatus()
  }, [fetchIngestStatus])

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
  const escalations = logs.filter((l) => l.escalated).length

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Conversation logs and knowledge base management
        </p>
      </div>

      {/* Stats + Ingest */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle size={16} className="text-orange-500" />
              Escalations
            </CardTitle>
            <CardDescription>Conversations routed to human agents</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{escalations}</p>
            <p className="text-xs text-muted-foreground mt-1">on this page ({total} total records)</p>
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

      {/* Logs table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <CardTitle className="text-base">Conversation Logs</CardTitle>
              <CardDescription>{total} total records</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={routeFilter}
                onChange={(e) => {
                  setRouteFilter(e.target.value)
                  setPage(1)
                }}
                className="w-36 h-8 text-xs"
              >
                <option value="">All routes</option>
                <option value="ANSWER">ANSWER</option>
                <option value="ESCALATE">ESCALATE</option>
                <option value="CLARIFY">CLARIFY</option>
                <option value="DECLINE">DECLINE</option>
              </Select>
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
                <TableHead className="w-32">Time</TableHead>
                <TableHead className="w-28">Session</TableHead>
                <TableHead className="w-16">Mode</TableHead>
                <TableHead>User said</TableHead>
                <TableHead>Agent replied</TableHead>
                <TableHead className="w-28">Route</TableHead>
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
                    No records found
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow key={log.id} className={log.escalated ? "bg-orange-50/50" : ""}>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(log.created_at)}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground truncate max-w-[100px]">
                      {log.session_id.slice(0, 8)}…
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">
                        {log.mode}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm max-w-[180px]">
                      <span className="line-clamp-2">{log.transcript}</span>
                    </TableCell>
                    <TableCell className="text-sm max-w-[180px]">
                      <span className="line-clamp-2">{log.response}</span>
                    </TableCell>
                    <TableCell>
                      {log.route ? (
                        <Badge
                          variant="outline"
                          className={cn("text-xs", ROUTE_COLORS[log.route] ?? "bg-gray-100")}
                        >
                          {log.route}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
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
    </div>
  )
}
