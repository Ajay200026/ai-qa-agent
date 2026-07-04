"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function avail(ok: boolean | undefined) {
  if (ok === undefined) return "secondary";
  return ok ? "secondary" : "outline";
}

export function AgentModeToggle({ className }: { className?: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["brain-config"],
    queryFn: () => api.getBrainConfig(),
  });

  const mutation = useMutation({
    mutationFn: (mode: "single" | "multi") => api.patchBrainConfig(mode),
    onMutate: async (mode) => {
      await qc.cancelQueries({ queryKey: ["brain-config"] });
      const prev = qc.getQueryData(["brain-config"]);
      qc.setQueryData(["brain-config"], (old: typeof data) =>
        old ? { ...old, agent_mode: mode } : old
      );
      return { prev };
    },
    onError: (_err, _mode, ctx) => {
      if (ctx?.prev) qc.setQueryData(["brain-config"], ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["brain-config"] }),
  });

  const isMulti = data?.agent_mode === "multi";
  const hybrid = data?.routing_mode === "hybrid";

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <button
        type="button"
        role="switch"
        aria-checked={isMulti}
        disabled={isLoading || mutation.isPending}
        onClick={() => mutation.mutate(isMulti ? "single" : "multi")}
        className={cn(
          "relative inline-flex h-7 w-14 shrink-0 cursor-pointer rounded-full border transition-colors",
          isMulti ? "bg-primary" : "bg-muted"
        )}
      >
        <span
          className={cn(
            "pointer-events-none block h-6 w-6 translate-y-0.5 rounded-full bg-white shadow transition-transform",
            isMulti ? "translate-x-7" : "translate-x-0.5"
          )}
        />
      </button>
      <span className="text-xs font-medium">
        {isMulti
          ? hybrid
            ? "Multi-agent (Gemma brain + NVIDIA chat)"
            : "3-agent mode"
          : "Single agent"}
      </span>
      {data?.degraded && (
        <Badge variant="outline" className="border-amber-500 text-amber-600">
          Agent degraded
        </Badge>
      )}
      {data?.models && (
        <div className="flex flex-wrap gap-1">
          {hybrid ? (
            <>
              <Badge variant={avail(data.scan_available)} className="text-[10px]">
                Brain: {data.models.scan || data.models.brain}
              </Badge>
              <Badge variant={avail(data.chat_available)} className="text-[10px]">
                Chat: {data.models.chat}
              </Badge>
              <Badge variant={avail(data.analysis_available)} className="text-[10px]">
                Analysis: {data.models.analysis}
              </Badge>
              <Badge variant={avail(data.automation_available)} className="text-[10px]">
                Auto: {data.models.automation}
              </Badge>
            </>
          ) : (
            <>
              <Badge variant="secondary" className="text-[10px]">
                Brain: {data.models.brain}
              </Badge>
              <Badge variant="secondary" className="text-[10px]">
                RCA: {data.models.rca}
              </Badge>
              <Badge variant="secondary" className="text-[10px]">
                Vision: {data.models.vision}
              </Badge>
            </>
          )}
        </div>
      )}
    </div>
  );
}
