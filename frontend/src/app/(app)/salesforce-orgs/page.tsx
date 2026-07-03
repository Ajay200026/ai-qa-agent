"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { OrgConnectPanel } from "@/components/salesforce/org-connect-panel";
import { OrgList } from "@/components/salesforce/org-list";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/loading/table-skeleton";

export default function SalesforceOrgsPage() {
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

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
    setMessage("Org authorized — your Salesforce session is saved. No password needed for test runs.");
    window.history.replaceState({}, "", "/salesforce-orgs");
    if (projectId) {
      void refetch();
    }
  }, [projectId, refetch]);

  const handleValidate = async (orgId: string) => {
    setBusyId(orgId);
    setMessage("");
    try {
      const result = await api.validateOrg(orgId);
      setMessage(result.message);
      await refetch();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusyId(null);
    }
  };

  const handleSetDefault = async (orgId: string) => {
    setBusyId(orgId);
    try {
      await api.updateOrg(orgId, { is_default: true });
      await queryClient.invalidateQueries({ queryKey: ["orgs", projectId] });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to set default");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (orgId: string) => {
    const org = orgs.find((o) => o.id === orgId);
    if (!confirm(`Delete org "${org?.name}"? This cannot be undone.`)) return;
    setBusyId(orgId);
    try {
      await api.deleteOrg(orgId);
      await refetch();
      setMessage("Org deleted.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Salesforce Orgs"
        description="Authorize and manage connected orgs for SOQL user lookup and Login As test runs."
      />

      {message && (
        <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm">{message}</div>
      )}

      <Card>
        <CardContent className="p-0 pt-0">
          {orgsLoading && projectId ? (
            <TableSkeleton rows={4} columns={5} />
          ) : (
            <OrgList
              orgs={orgs}
              onValidate={handleValidate}
              onSetDefault={handleSetDefault}
              onDelete={handleDelete}
              busyId={busyId}
            />
          )}
        </CardContent>
      </Card>

      {projectId && (
        <OrgConnectPanel
          projectId={projectId}
          onConnected={() => {
            refetch();
            setMessage("Org connected.");
          }}
        />
      )}
    </div>
  );
}
