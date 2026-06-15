import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ExecutionEvent, ExecutionStep } from "@/lib/types";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

interface ExecutionTimelineProps {
  steps: ExecutionStep[];
  events: ExecutionEvent[];
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "passed":
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case "failed":
    case "error":
      return <XCircle className="h-5 w-5 text-red-500" />;
    case "cancelled":
    case "skipped":
      return <XCircle className="h-5 w-5 text-muted-foreground" />;
    case "running":
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    default:
      return <Circle className="h-5 w-5 text-muted-foreground" />;
  }
}

function statusBadgeVariant(status: string) {
  if (status === "passed") return "success" as const;
  if (status === "failed" || status === "error") return "destructive" as const;
  if (status === "cancelled" || status === "skipped") return "outline" as const;
  return "secondary" as const;
}

export function ExecutionTimeline({ steps, events }: ExecutionTimelineProps) {
  const latestEventByStep = new Map<number, ExecutionEvent>();
  events.forEach((e) => {
    if (e.step_seq) latestEventByStep.set(e.step_seq, e);
  });

  const phases = [
    { name: "Parse Scenario", key: "parse" },
    { name: "Plan Steps", key: "plan" },
    { name: "Launch Salesforce", key: "launch" },
    { name: "Login", key: "login" },
    { name: "Navigation", key: "open" },
    { name: "Search Customer", key: "search" },
    { name: "Execute Scenario", key: "save" },
    { name: "Validation", key: "valid" },
    { name: "Report Generation", key: "report" },
  ];

  const phaseEvents = events.filter(
    (e) =>
      e.event_type === "phase_completed" ||
      e.event_type === "execution_completed" ||
      e.event_type === "execution_cancelled"
  );

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h3 className="font-semibold">Execution Phases</h3>
        {phases.map((phase) => {
          const event = phaseEvents.find((e) =>
            e.step_name?.toLowerCase().includes(phase.key) ||
            (phase.key === "report" && e.event_type === "execution_completed")
          );
          const status = event?.status || "pending";
          return (
            <div key={phase.name} className="flex items-center gap-3 rounded-lg border p-3">
              <StatusIcon status={status} />
              <div className="flex-1">
                <p className="font-medium">{phase.name}</p>
                {event?.message && (
                  <p className="text-sm text-muted-foreground">{event.message}</p>
                )}
              </div>
              <Badge variant={statusBadgeVariant(status)} className="capitalize">
                {status}
              </Badge>
            </div>
          );
        })}
      </div>

      <div className="space-y-3">
        <h3 className="font-semibold">Step Details</h3>
        {steps.map((step) => {
          const event = latestEventByStep.get(step.seq);
          const status = event?.status || step.status;
          return (
            <div
              key={step.id}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3",
                status === "running" && "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20"
              )}
            >
              <StatusIcon status={status} />
              <div className="flex-1">
                <p className="font-medium">
                  {step.seq}. {step.name}
                </p>
                <p className="text-xs text-muted-foreground">Action: {step.action}</p>
                {(step.error || event?.message) && (
                  <p className="mt-1 text-sm text-destructive">{step.error || event?.message}</p>
                )}
              </div>
              <Badge variant={statusBadgeVariant(status)} className="capitalize">
                {status}
              </Badge>
            </div>
          );
        })}
      </div>
    </div>
  );
}
