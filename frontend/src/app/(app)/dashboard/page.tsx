"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { OrgCard } from "@/components/dashboard/org-card";
import { KnowledgeQuickAccess } from "@/components/dashboard/knowledge-quick-access";
import { ExecutionList } from "@/components/executions/execution-list";
import { PageHeader, SectionHeader } from "@/components/layout/page-header";
import { PremiumCard } from "@/components/ui/premium-card";
import { Button } from "@/components/ui/button";
import { StatsCardsSkeleton } from "@/components/loading/stats-cards-skeleton";
import { ListCardsSkeleton } from "@/components/loading/list-cards-skeleton";
import { TableSkeleton } from "@/components/loading/table-skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [clearingFailed, setClearingFailed] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"failed" | "history" | null>(null);

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
    setClearingFailed(true);
    try {
      await api.clearFailedExecutions();
      await invalidateExecutionQueries();
      toast.success("Failed executions cleared");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to clear");
    } finally {
      setClearingFailed(false);
      setConfirmAction(null);
    }
  };

  const handleClearHistory = async () => {
    setClearingHistory(true);
    try {
      await api.clearExecutionHistory();
      await invalidateExecutionQueries();
      toast.success("Execution history cleared");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to clear");
    } finally {
      setClearingHistory(false);
      setConfirmAction(null);
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

      {statsLoading ? <StatsCardsSkeleton /> : stats && <StatsCards stats={stats} />}

      <KnowledgeQuickAccess />

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
          <PremiumCard>
            <p className="py-4 text-center text-sm text-muted-foreground">
              No orgs connected.{" "}
              <Link href="/salesforce-orgs" className="font-medium text-primary underline">
                Authorize a Salesforce org
              </Link>
            </p>
          </PremiumCard>
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
                onClick={() => setConfirmAction("history")}
                disabled={clearingHistory}
              >
                <Trash2 className="h-4 w-4" />
                {clearingHistory ? "Clearing..." : "Clear History"}
              </Button>
            ) : null
          }
        />
        <PremiumCard noPadding>
          {executionsLoading ? (
            <TableSkeleton rows={5} columns={3} />
          ) : (
            <ExecutionList executions={executions.slice(0, 10)} />
          )}
        </PremiumCard>
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
                onClick={() => setConfirmAction("failed")}
                disabled={clearingFailed}
              >
                <Trash2 className="h-4 w-4" />
                {clearingFailed ? "Clearing..." : "Clear Failed"}
              </Button>
            }
          />
          <div className="space-y-2">
            {failedExecutions.map((exec) => (
              <PremiumCard key={exec.id} className="py-3">
                <div className="flex flex-col gap-3 px-6 sm:flex-row sm:items-center sm:justify-between">
                  <p className="break-all font-mono text-sm">{exec.id}</p>
                  <Link href={`/executions/${exec.id}`}>
                    <Button variant="outline" size="sm">
                      Investigate
                    </Button>
                  </Link>
                </div>
              </PremiumCard>
            ))}
          </div>
        </section>
      )}

      <Dialog open={!!confirmAction} onOpenChange={() => setConfirmAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmAction === "failed" ? "Clear failed executions?" : "Clear execution history?"}
            </DialogTitle>
            <DialogDescription>
              {confirmAction === "failed"
                ? "This will permanently remove all failed execution records."
                : "This will clear finished execution history. Active runs will be kept."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmAction(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmAction === "failed" ? handleClearFailed : handleClearHistory}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
