"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ExecutionEvent } from "@/lib/types";
import { Trash2 } from "lucide-react";
import { ScreenshotThumbnail } from "@/components/artifacts/screenshot-lightbox";

type LogFilter = "all" | "steps" | "phases" | "errors";

function eventTone(event: ExecutionEvent): string {
  if (event.event_type === "execution_error" || event.status === "failed" || event.status === "error") {
    return "text-red-600 dark:text-red-400";
  }
  if (event.status === "passed" || event.event_type === "execution_completed") {
    return "text-green-700 dark:text-green-400";
  }
  if (event.status === "running" || event.event_type === "step_started") {
    return "text-blue-600 dark:text-blue-400";
  }
  return "text-muted-foreground";
}

function matchesFilter(event: ExecutionEvent, filter: LogFilter): boolean {
  if (filter === "all") return true;
  if (filter === "errors") {
    return (
      event.event_type === "execution_error" ||
      event.status === "failed" ||
      event.status === "error"
    );
  }
  if (filter === "steps") {
    return event.event_type.startsWith("step_") || event.event_type.startsWith("test_case_");
  }
  if (filter === "phases") {
    return event.event_type === "phase_completed" || event.event_type.startsWith("execution_");
  }
  return true;
}

interface ExecutionEventLogProps {
  executionId: string;
  events: ExecutionEvent[];
  connected: boolean;
  isRunning: boolean;
  onClear: () => void;
}

export function ExecutionEventLog({
  executionId,
  events,
  connected,
  isRunning,
  onClear,
}: ExecutionEventLogProps) {
  const [filter, setFilter] = useState<LogFilter>("all");
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = events.filter((e) => matchesFilter(e, filter));

  useEffect(() => {
    if (!isRunning || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length, isRunning]);

  const filters: { id: LogFilter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "steps", label: "Steps" },
    { id: "phases", label: "Phases" },
    { id: "errors", label: "Errors" },
  ];

  return (
    <div className="flex h-full min-h-[320px] flex-col rounded-lg border bg-card lg:min-h-0 lg:max-h-[calc(100vh-3rem)]">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">Live Log</span>
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              connected ? "bg-green-500 animate-pulse" : "bg-muted-foreground"
            )}
          />
        </div>
        <Button variant="ghost" size="sm" className="h-8 gap-1 px-2" onClick={onClear}>
          <Trash2 className="h-3.5 w-3.5" />
          Clear
        </Button>
      </div>
      <div className="flex gap-1 border-b px-2 py-1.5">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded px-2 py-0.5 text-xs",
              filter === f.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-auto bg-muted/20 p-3 font-mono text-xs"
      >
        {filtered.length === 0 ? (
          <p className="text-muted-foreground">Waiting for events…</p>
        ) : (
          filtered.map((event, i) => (
            <div key={`${event.timestamp}-${i}`} className={cn("mb-1 break-words", eventTone(event))}>
              <span className="text-muted-foreground">
                [{new Date(event.timestamp).toLocaleTimeString()}]
              </span>{" "}
              <span className="font-medium">{event.event_type}</span>
              {event.step_seq != null && (
                <span className="text-muted-foreground"> #{event.step_seq}</span>
              )}
              {event.step_name && <span> — {event.step_name}</span>}
              {event.message && <span>: {event.message}</span>}
              {event.screenshot_path && (
                <div className="mt-1 pl-4">
                  <ScreenshotThumbnail
                    executionId={executionId}
                    screenshotPath={event.screenshot_path}
                    alt={event.step_name ? `Step ${event.step_seq} screenshot` : "Screenshot"}
                    className="max-h-16"
                  />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
