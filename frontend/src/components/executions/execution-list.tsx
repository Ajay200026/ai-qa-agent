"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, formatDuration } from "@/lib/utils";
import type { Execution } from "@/lib/types";

function statusVariant(status: string) {
  if (status === "passed") return "success" as const;
  if (status === "failed" || status === "error") return "destructive" as const;
  return "secondary" as const;
}

export function ExecutionList({
  executions,
  emptyMessage = "No executions yet",
}: {
  executions: Execution[];
  emptyMessage?: string;
}) {
  if (executions.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <>
      <div className="space-y-3 md:hidden">
        {executions.map((exec) => (
          <div key={exec.id} className="rounded-lg border p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-mono text-xs">{exec.id}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {formatDate(exec.started_at)} · {formatDuration(exec.duration_ms)}
                </p>
              </div>
              <Badge variant={statusVariant(exec.status)} className="capitalize">
                {exec.status}
              </Badge>
            </div>
            <div className="mt-3">
              <Link href={`/executions/${exec.id}`}>
                <Button variant="outline" size="sm" className="w-full sm:w-auto">
                  View
                </Button>
              </Link>
            </div>
          </div>
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr className="border-b text-left text-sm text-muted-foreground">
              <th className="p-4">ID</th>
              <th className="p-4">Status</th>
              <th className="p-4">Duration</th>
              <th className="p-4">Started</th>
              <th className="p-4" />
            </tr>
          </thead>
          <tbody>
            {executions.map((exec) => (
              <tr key={exec.id} className="border-b">
                <td className="p-4 font-mono text-xs">{exec.id.slice(0, 8)}...</td>
                <td className="p-4">
                  <Badge variant={statusVariant(exec.status)} className="capitalize">
                    {exec.status}
                  </Badge>
                </td>
                <td className="p-4">{formatDuration(exec.duration_ms)}</td>
                <td className="p-4">{formatDate(exec.started_at)}</td>
                <td className="p-4">
                  <Link href={`/executions/${exec.id}`}>
                    <Button variant="ghost" size="sm">
                      View
                    </Button>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
