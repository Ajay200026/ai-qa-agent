"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useExecutionStream } from "@/hooks/useExecutionStream";
import { ExecutionTimeline } from "@/components/executions/execution-timeline";
import { ExecutionEventLog } from "@/components/executions/execution-event-log";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, formatDuration } from "@/lib/utils";
import { FileText, Pencil, RotateCcw, Square } from "lucide-react";
import { StepEditDialog } from "@/components/executions/step-edit-dialog";
import type { ExecutionStep } from "@/lib/types";
import { Spinner } from "@/components/ui/spinner";

function statusBadgeVariant(status: string) {
  switch (status) {
    case "passed":
      return "success" as const;
    case "failed":
    case "error":
      return "destructive" as const;
    case "running":
      return "warning" as const;
    case "cancelled":
      return "outline" as const;
    default:
      return "secondary" as const;
  }
}

export default function ExecutionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const queryClient = useQueryClient();
  const { events, connected, clearEvents } = useExecutionStream(id);
  const [rerunning, setRerunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [actionError, setActionError] = useState("");
  const [editingStep, setEditingStep] = useState<ExecutionStep | null>(null);

  const { data: execution, isLoading: executionLoading, refetch } = useQuery({
    queryKey: ["execution", id],
    queryFn: () => api.getExecution(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "queued" ? 2000 : false;
    },
  });

  const isActive = execution?.status === "running" || execution?.status === "queued";
  const streamError = [...events].reverse().find((e) => e.event_type === "execution_error");
  const isComplete =
    execution?.status === "passed" ||
    execution?.status === "failed" ||
    execution?.status === "error" ||
    execution?.status === "cancelled";

  const canRerun =
    execution &&
    !isActive &&
    (execution.status === "failed" ||
      execution.status === "error" ||
      execution.status === "passed" ||
      execution.status === "cancelled");

  const handleRerun = async () => {
    setRerunning(true);
    setActionError("");
    try {
      await api.rerunExecution(id);
      await queryClient.invalidateQueries({ queryKey: ["execution", id] });
      await refetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to re-run execution");
    } finally {
      setRerunning(false);
    }
  };

  const handleStop = async () => {
    setStopping(true);
    setActionError("");
    try {
      await api.stopExecution(id);
      await queryClient.invalidateQueries({ queryKey: ["execution", id] });
      await refetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to stop execution");
    } finally {
      setStopping(false);
    }
  };

  return (
    <div className="lg:grid lg:grid-cols-[minmax(280px,340px)_1fr] lg:items-start lg:gap-6">
      <div className="mb-6 lg:sticky lg:top-6 lg:mb-0 lg:max-h-[calc(100vh-3rem)]">
        <ExecutionEventLog
          executionId={id}
          events={events}
          connected={connected}
          isRunning={execution?.status === "running"}
          onClear={clearEvents}
        />
      </div>

      <div className="min-w-0 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Test Execution</h1>
          <p className="break-all font-mono text-xs text-muted-foreground sm:text-sm">{id}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={connected ? "success" : "secondary"}>
              {connected ? "Live" : "Disconnected"}
            </Badge>
            {execution && (
              <Badge variant={statusBadgeVariant(execution.status)} className="capitalize">
                {execution.status}
              </Badge>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {isActive && (
            <Button
              variant="destructive"
              onClick={handleStop}
              loading={stopping}
              className="gap-2"
            >
              <Square className="h-4 w-4 fill-current" />
              {stopping ? "Stopping..." : "Stop Execution"}
            </Button>
          )}
          {canRerun && (
            <Button onClick={handleRerun} loading={rerunning} variant="secondary" className="gap-2">
              <RotateCcw className="h-4 w-4" />
              {rerunning ? "Starting..." : "Re-run"}
            </Button>
          )}
          {execution?.scenario_id && !isActive && (
            <Link
              href={`/scenarios/${execution.scenario_id}/edit?return=${encodeURIComponent(`/executions/${id}`)}&org_id=${execution.org_id}`}
            >
              <Button variant="outline" className="gap-2">
                <Pencil className="h-4 w-4" />
                Edit Scenario
              </Button>
            </Link>
          )}
          {isComplete && execution?.status !== "cancelled" && (
            <Link href={`/reports?execution=${id}`}>
              <Button variant="outline" className="gap-2">
                <FileText className="h-4 w-4" />
                View Report
              </Button>
            </Link>
          )}
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {execution?.status === "queued" && (
        <Card className="border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/30">
          <CardContent className="flex items-center gap-3 py-4 text-sm">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-500" />
            </span>
            Queued — automation will start shortly. Use <strong>Stop Execution</strong> to cancel.
          </CardContent>
        </Card>
      )}

      {execution?.status === "error" && (
        <Card className="border-destructive/40 bg-destructive/10">
          <CardContent className="py-4 text-sm text-destructive">
            Execution failed
            {streamError?.message ? `: ${streamError.message}` : "."} Click <strong>Re-run</strong> to try again.
          </CardContent>
        </Card>
      )}

      {execution?.status === "running" && (
        <Card className="border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/30">
          <CardContent className="flex items-center gap-3 py-4 text-sm">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-500" />
            </span>
            Running in Salesforce — watch live progress below. Click <strong>Stop Execution</strong> to end early.
          </CardContent>
        </Card>
      )}

      {execution?.status === "cancelled" && (
        <Card className="border-muted bg-muted/30">
          <CardContent className="py-4 text-sm text-muted-foreground">
            This execution was stopped before completion. Click <strong>Re-run</strong> to try again.
          </CardContent>
        </Card>
      )}

      {execution && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Started</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">{formatDate(execution.started_at)}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Duration</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">{formatDuration(execution.duration_ms)}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Steps</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">{execution.steps.length}</CardContent>
          </Card>
        </div>
      )}

      {(execution?.plan_json as { mode?: string } | undefined)?.mode === "test_pack" && Boolean(execution?.plan_json?.test_pack_result) && (
        <Card>
          <CardHeader>
            <CardTitle>Test Case Results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {(execution?.plan_json?.test_pack_result as {
              test_case_results?: Array<{
                tc_id: string;
                title: string;
                status: string;
                is_smoke?: boolean;
                error?: string;
              }>;
            }).test_case_results?.map((tc) => (
              <div key={tc.tc_id} className="rounded-md border p-3">
                <div className="flex items-center gap-2">
                  <Badge variant={statusBadgeVariant(tc.status)} className="capitalize">
                    {tc.status}
                  </Badge>
                  <span className="font-medium">{tc.tc_id}</span>
                  {tc.is_smoke && <Badge variant="outline">Smoke</Badge>}
                </div>
                <p className="text-sm text-muted-foreground mt-1">{tc.title}</p>
                {tc.error && <p className="text-sm text-destructive mt-1">{tc.error}</p>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Live Progress</CardTitle>
        </CardHeader>
        <CardContent>
          {executionLoading ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <Spinner size="lg" />
              <p className="text-sm text-muted-foreground">Loading execution…</p>
            </div>
          ) : execution ? (
            <ExecutionTimeline
              executionId={id}
              steps={execution.steps}
              events={events}
              onEditStep={!isActive ? setEditingStep : undefined}
            />
          ) : null}
        </CardContent>
      </Card>

      {editingStep && (
        <StepEditDialog
          executionId={id}
          step={editingStep}
          open={!!editingStep}
          onClose={() => setEditingStep(null)}
          onSaved={async () => {
            await queryClient.invalidateQueries({ queryKey: ["execution", id] });
            await refetch();
          }}
        />
      )}
      </div>
    </div>
  );
}
