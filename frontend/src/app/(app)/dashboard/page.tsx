"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { OrgCard } from "@/components/dashboard/org-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, formatDuration } from "@/lib/utils";

export default function DashboardPage() {
  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.getDashboardStats(),
    refetchInterval: 10000,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.getProjects(),
  });

  const projectId = projects[0]?.id;

  const { data: orgs = [] } = useQuery({
    queryKey: ["orgs", projectId],
    queryFn: () => api.getOrgs(projectId!),
    enabled: !!projectId,
  });

  const { data: executions = [] } = useQuery({
    queryKey: ["executions"],
    queryFn: () => api.getExecutions(),
    refetchInterval: 10000,
  });

  const { data: failedExecutions = [] } = useQuery({
    queryKey: ["failed-executions"],
    queryFn: () => api.getFailedExecutions(),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">Salesforce QA testing overview</p>
        </div>
        <Link href="/executions/new">
          <Button>Run Testing</Button>
        </Link>
      </div>

      {stats && <StatsCards stats={stats} />}

      <section>
        <h2 className="mb-4 text-xl font-semibold">Connected Salesforce Orgs</h2>
        {orgs.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No orgs connected. Connect a Salesforce org from New Execution.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {orgs.map((org) => (
              <OrgCard key={org.id} org={org} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold">Recent Executions</h2>
        <Card>
          <CardContent className="p-0">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="p-4">ID</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Duration</th>
                  <th className="p-4">Started</th>
                  <th className="p-4"></th>
                </tr>
              </thead>
              <tbody>
                {executions.slice(0, 10).map((exec) => (
                  <tr key={exec.id} className="border-b">
                    <td className="p-4 font-mono text-xs">{exec.id.slice(0, 8)}...</td>
                    <td className="p-4">
                      <Badge
                        variant={
                          exec.status === "passed"
                            ? "success"
                            : exec.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {exec.status}
                      </Badge>
                    </td>
                    <td className="p-4">{formatDuration(exec.duration_ms)}</td>
                    <td className="p-4">{formatDate(exec.started_at)}</td>
                    <td className="p-4">
                      <Link href={`/executions/${exec.id}`}>
                        <Button variant="ghost" size="sm">View</Button>
                      </Link>
                    </td>
                  </tr>
                ))}
                {executions.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-muted-foreground">
                      No executions yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </section>

      {failedExecutions.length > 0 && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">Failed Executions</h2>
          <div className="space-y-2">
            {failedExecutions.map((exec) => (
              <Card key={exec.id}>
                <CardHeader className="flex flex-row items-center justify-between py-3">
                  <CardTitle className="text-sm font-mono">{exec.id.slice(0, 8)}...</CardTitle>
                  <Link href={`/executions/${exec.id}`}>
                    <Button variant="outline" size="sm">Investigate</Button>
                  </Link>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
