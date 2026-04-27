import { useState, useEffect, useCallback } from "react"
import { Play, CheckCircle, XCircle, RefreshCw, AlertTriangle } from "lucide-react"
import {
  triggerEval,
  getLatestEvalRun,
  type AdminCredentials,
  type EvalRun,
  type EvalCaseResult,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

function ScoreDot({ value }: { value: number }) {
  const color =
    value >= 4 ? "bg-emerald-500" :
    value >= 3 ? "bg-yellow-400" :
    "bg-red-500"
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn("inline-block w-2 h-2 rounded-full", color)} />
      <span className="tabular-nums">{value.toFixed(1)}</span>
    </span>
  )
}

function PassRate({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 80 ? "text-emerald-600" : pct >= 60 ? "text-yellow-600" : "text-red-600"
  return <span className={cn("text-3xl font-bold tabular-nums", color)}>{pct}%</span>
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
}

export function EvalPanel({ credentials }: { credentials: AdminCredentials }) {
  const [run, setRun] = useState<EvalRun | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const fetchLatest = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getLatestEvalRun(credentials)
      setRun(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [credentials])

  useEffect(() => { fetchLatest() }, [fetchLatest])

  const handleRunEval = async () => {
    setRunning(true)
    setMessage(null)
    try {
      const res = await triggerEval(credentials)
      setMessage(`Eval started (${res.scope}). Results will appear once complete — refresh in ~60s.`)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to start eval")
    } finally {
      setRunning(false)
    }
  }

  const results: EvalCaseResult[] = run?.results ?? []

  return (
    <div className="space-y-6">
      {/* Header + controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-semibold">Agent Evaluation</h2>
          <p className="text-sm text-muted-foreground">
            LLM-as-judge scores across {run?.total ?? "—"} golden test cases
            {run?.created_at && ` · Last run: ${formatDate(run.created_at)}`}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchLatest} disabled={loading} className="gap-1.5">
            <RefreshCw size={12} className={cn(loading && "animate-spin")} />
            Refresh
          </Button>
          <Button size="sm" onClick={handleRunEval} disabled={running} className="gap-1.5">
            <Play size={12} className={cn(running && "animate-pulse")} />
            {running ? "Starting…" : "Run eval"}
          </Button>
        </div>
      </div>

      {message && (
        <p className="text-sm text-muted-foreground bg-muted px-3 py-2 rounded">{message}</p>
      )}

      {/* Summary cards */}
      {run ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Pass rate</CardDescription>
              </CardHeader>
              <CardContent>
                <PassRate rate={run.pass_rate} />
                <p className="text-xs text-muted-foreground mt-1">{run.passed}/{run.total} cases</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Route accuracy</CardDescription>
              </CardHeader>
              <CardContent>
                <PassRate rate={run.route_accuracy} />
                <p className="text-xs text-muted-foreground mt-1">correct ANSWER/ESCALATE</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Avg overall score</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-3xl font-bold tabular-nums">
                  {run.avg_scores.overall.toFixed(1)}
                  <span className="text-base font-normal text-muted-foreground">/5</span>
                </span>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Failed cases</CardDescription>
              </CardHeader>
              <CardContent>
                <span className={cn(
                  "text-3xl font-bold tabular-nums",
                  run.failed > 0 ? "text-red-600" : "text-emerald-600"
                )}>
                  {run.failed}
                </span>
              </CardContent>
            </Card>
          </div>

          {/* Score breakdown */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Average scores by dimension</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                {(["accuracy", "helpfulness", "tone", "safety"] as const).map((dim) => (
                  <div key={dim}>
                    <p className="text-xs text-muted-foreground capitalize mb-1">{dim}</p>
                    <ScoreDot value={run.avg_scores[dim]} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Per-case results */}
          {results.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Case results</CardTitle>
                <CardDescription>Click a row to see the judge's reasoning</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-24">Case</TableHead>
                      <TableHead>Query</TableHead>
                      <TableHead className="w-24">Expected</TableHead>
                      <TableHead className="w-24">Actual</TableHead>
                      <TableHead className="w-16">Overall</TableHead>
                      <TableHead className="w-20">Result</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.map((r) => (
                      <>
                        <TableRow
                          key={r.case_id}
                          className={cn("cursor-pointer hover:bg-muted/50", !r.passed && "bg-red-50/50")}
                          onClick={() => setExpanded(expanded === r.case_id ? null : r.case_id)}
                        >
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {r.case_id}
                          </TableCell>
                          <TableCell className="text-sm max-w-[240px]">
                            <span className="line-clamp-1">{r.query}</span>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">{r.expected_route}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={cn(
                                "text-xs",
                                r.route_correct
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : "bg-red-50 text-red-700 border-red-200"
                              )}
                            >
                              {r.actual_route}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <ScoreDot value={r.scores.overall} />
                          </TableCell>
                          <TableCell>
                            {r.passed
                              ? <CheckCircle size={16} className="text-emerald-500" />
                              : <XCircle size={16} className="text-red-500" />
                            }
                          </TableCell>
                        </TableRow>

                        {expanded === r.case_id && (
                          <TableRow key={`${r.case_id}-detail`} className="bg-muted/30">
                            <TableCell colSpan={6} className="text-sm py-3 px-4 space-y-2">
                              <div className="flex gap-4 flex-wrap">
                                {(["accuracy", "helpfulness", "tone", "safety"] as const).map((d) => (
                                  <span key={d} className="flex items-center gap-1 text-xs">
                                    <span className="text-muted-foreground capitalize">{d}:</span>
                                    <ScoreDot value={r.scores[d]} />
                                  </span>
                                ))}
                              </div>
                              <p className="text-muted-foreground italic text-xs">
                                "{r.reasoning}"
                              </p>
                              {r.constraint_failures.length > 0 && (
                                <div className="flex items-start gap-1.5 text-xs text-red-700">
                                  <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                                  <span>{r.constraint_failures.join(" · ")}</span>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground text-sm">
            No eval runs yet. Click <strong>Run eval</strong> to evaluate the agent against the golden dataset.
          </CardContent>
        </Card>
      )}
    </div>
  )
}
