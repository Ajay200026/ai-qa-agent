"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { OrgConnectPanel } from "@/components/salesforce/org-connect-panel";
import { OrgList } from "@/components/salesforce/org-list";
import { PageHeader } from "@/components/layout/page-header";
import { PremiumCard } from "@/components/ui/premium-card";
import { TableSkeleton } from "@/components/loading/table-skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function SalesforceOrgsPage() {
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const p = await api.getProjects();
      if (p.length === 0) {
        return [await api.createProject("Default Project", "Salesforce QA testing project")];
      }
      return p;
    },
  });
  const projectId = projects[0]?.id;

  const { data: orgs = [], isLoading: orgsLoading, refetch } = useQuery({
    queryKey: ["orgs", projectId],
    queryFn: () => api.getOrgs(projectId!),
    enabled: !!projectId,
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") !== "1") return;
    toast.success("Org authorized — Salesforce session saved.");
    window.history.replaceState({}, "", "/salesforce-orgs");
    if (projectId) void refetch();
  }, [projectId, refetch]);

  const handleValidate = async (orgId: string) => {
    setBusyId(orgId);
    try {
      const result = await api.validateOrg(orgId);
      toast.success(result.message);
      await refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusyId(null);
    }
  };

  const handleSetDefault = async (orgId: string) => {
    setBusyId(orgId);
    try {
      await api.updateOrg(orgId, { is_default: true });
      await queryClient.invalidateQueries({ queryKey: ["orgs", projectId] });
      toast.success("Default org updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to set default");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setBusyId(deleteId);
    try {
      await api.deleteOrg(deleteId);
      await refetch();
      toast.success("Org deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
      setDeleteId(null);
    }
  };

  const deleteOrgName = orgs.find((o) => o.id === deleteId)?.name;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Salesforce Orgs"
        description="Authorize and manage connected orgs for SOQL user lookup and Login As test runs."
      />

      <PremiumCard title="Connected Orgs" noPadding>
        {orgsLoading && projectId ? (
          <TableSkeleton rows={4} columns={5} />
        ) : (
          <OrgList
            orgs={orgs}
            onValidate={handleValidate}
            onSetDefault={handleSetDefault}
            onDelete={setDeleteId}
            busyId={busyId}
          />
        )}
      </PremiumCard>

      {projectId && (
        <PremiumCard title="Connect New Org">
          <OrgConnectPanel
            projectId={projectId}
            onConnected={() => {
              refetch();
              toast.success("Org connected");
            }}
          />
        </PremiumCard>
      )}

      <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete org?</DialogTitle>
            <DialogDescription>
              Delete &quot;{deleteOrgName}&quot;? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
