"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { OrgCard } from "@/components/dashboard/org-card";
import { ExecutionList } from "@/components/executions/execution-list";
import { PageHeader, SectionHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatsCardsSkeleton } from "@/components/loading/stats-cards-skeleton";
import { ListCardsSkeleton } from "@/components/loading/list-cards-skeleton";
import { TableSkeleton } from "@/components/loading/table-skeleton";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [clearingFailed, setClearingFailed] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [actionError, setActionError] = useState("");

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.getDashboardStats(),
    refetchInterval: 10000,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.getProjects(),
  });

  const projectId = projects[0]?.id;

  const { data: orgs = [], isLoading: orgsLoading } = useQuery({
    queryKey: ["orgs", projectId],
    queryFn: () => api.getOrgs(projectId!),
    enabled: !!projectId,
  });

  const { data: executions = [], isLoading: executionsLoading } = useQuery({
    queryKey: ["executions"],
    queryFn: () => api.getExecutions(),
    refetchInterval: 10000,
  });

  const { data: failedExecutions = [] } = useQuery({
    queryKey: ["failed-executions"],
    queryFn: () => api.getFailedExecutions(),
    refetchInterval: 10000,
  });

  const invalidateExecutionQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["executions"] }),
      queryClient.invalidateQueries({ queryKey: ["failed-executions"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] }),
      queryClient.invalidateQueries({ queryKey: ["reports"] }),
    ]);
  };

  const handleClearFailed = async () => {
    if (!confirm("Clear all failed executions? This cannot be undone.")) return;
    setClearingFailed(true);
    setActionError("");
    try {
      await api.clearFailedExecutions();
      await invalidateExecutionQueries();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to clear failed executions");
    } finally {
      setClearingFailed(false);
    }
  };

  const handleClearHistory = async () => {
    if (!confirm("Clear all finished execution history? Active runs will be kept.")) return;
    setClearingHistory(true);
    setActionError("");
    try {
      await api.clearExecutionHistory();
      await invalidateExecutionQueries();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to clear execution history");
    } finally {
      setClearingHistory(false);
    }
  };

  return (
    <div className="space-y-6 sm:space-y-8">
      <PageHeader
        title="Dashboard"
        description="Salesforce QA testing overview"
        actions={
          <Link href="/executions/new" className="w-full sm:w-auto">
            <Button className="w-full sm:w-auto">Run Testing</Button>
          </Link>
        }
      />

      {actionError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {statsLoading ? <StatsCardsSkeleton /> : stats && <StatsCards stats={stats} />}

      <section>
        <SectionHeader
          title="Connected Salesforce Orgs"
          actions={
            <Link href="/salesforce-orgs">
              <Button variant="outline" size="sm">
                Manage orgs
              </Button>
            </Link>
          }
        />
        {orgsLoading && projectId ? (
          <ListCardsSkeleton count={3} />
        ) : orgs.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              No orgs connected.{" "}
              <Link href="/salesforce-orgs" className="font-medium underline">
                Authorize a Salesforce org
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {orgs.map((org) => (
              <OrgCard key={org.id} org={org} />
            ))}
          </div>
        )}
      </section>

      <section>
        <SectionHeader
          title="Recent Executions"
          actions={
            executions.length > 0 ? (
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={handleClearHistory}
                disabled={clearingHistory}
              >
                <Trash2 className="h-4 w-4" />
                {clearingHistory ? "Clearing..." : "Clear History"}
              </Button>
            ) : null
          }
        />
        <Card>
          <CardContent className="p-0 sm:p-0">
            {executionsLoading ? (
              <TableSkeleton rows={5} columns={3} />
            ) : (
              <ExecutionList executions={executions.slice(0, 10)} />
            )}
          </CardContent>
        </Card>
      </section>

      {failedExecutions.length > 0 && (
        <section>
          <SectionHeader
            title="Failed Executions"
            actions={
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={handleClearFailed}
                disabled={clearingFailed}
              >
                <Trash2 className="h-4 w-4" />
                {clearingFailed ? "Clearing..." : "Clear Failed"}
              </Button>
            }
          />
          <div className="space-y-2">
            {failedExecutions.map((exec) => (
              <Card key={exec.id}>
                <CardHeader className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <CardTitle className="break-all font-mono text-sm">{exec.id}</CardTitle>
                  <Link href={`/executions/${exec.id}`} className="w-full sm:w-auto">
                    <Button variant="outline" size="sm" className="w-full sm:w-auto">
                      Investigate
                    </Button>
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
