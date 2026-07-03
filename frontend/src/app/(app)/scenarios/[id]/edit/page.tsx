"use client";

import { use, useCallback, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ScenarioForm, type ScenarioFormValues } from "@/components/scenarios/scenario-form";
import {
  ScenarioOrgCard,
  type ScenarioOrgFormValues,
} from "@/components/scenarios/scenario-org-card";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { ScenarioEditSkeleton } from "@/components/loading/scenario-edit-skeleton";
import { OrgCardSkeleton } from "@/components/loading/org-card-skeleton";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function EditScenarioPage({ params }: PageProps) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const returnTo = searchParams.get("return");
  const orgId = searchParams.get("org_id");
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [orgValues, setOrgValues] = useState<ScenarioOrgFormValues | null>(null);

  const { data: scenario, isLoading: scenarioLoading } = useQuery({
    queryKey: ["scenario", id],
    queryFn: () => api.getScenario(id),
  });

  const { data: org, isLoading: orgLoading } = useQuery({
    queryKey: ["org", orgId],
    queryFn: () => api.getOrg(orgId!),
    enabled: !!orgId,
  });

  const handleOrgChange = useCallback((values: ScenarioOrgFormValues) => {
    setOrgValues(values);
  }, []);

  const handleSubmit = async (values: ScenarioFormValues) => {
    setError("");
    setSaved(false);
    setSaving(true);
    try {
      await api.updateScenario(id, values);
      if (orgId && org && orgValues) {
        const orgChanged =
          orgValues.org_type !== org.org_type || orgValues.login_url !== org.login_url;
        if (orgChanged) {
          await api.updateOrg(orgId, {
            org_type: orgValues.org_type,
            login_url: orgValues.login_url,
          });
          await queryClient.invalidateQueries({ queryKey: ["org", orgId] });
        }
      }
      await queryClient.invalidateQueries({ queryKey: ["scenario", id] });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save scenario");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4">
      <PageHeader
        title="Edit Scenario"
        description={scenario?.name || "Loading scenario…"}
      />
      {saved && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-900 dark:bg-green-950/40 dark:text-green-200">
          Scenario saved successfully.
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {orgId && orgLoading && <OrgCardSkeleton />}
      {org && <ScenarioOrgCard org={org} onChange={handleOrgChange} />}

      {scenarioLoading && <ScenarioEditSkeleton />}
      {scenario && !scenarioLoading && (
        <ScenarioForm
          initial={scenario}
          projectId={scenario.project_id}
          orgId={orgId}
          orgBottler={org?.bottler || null}
          onSubmit={handleSubmit}
          submitting={saving}
          submitLabel="Save Scenario"
        />
      )}

      <div className="flex flex-wrap gap-2">
        {returnTo ? (
          <Link href={returnTo}>
            <Button variant="outline">Back</Button>
          </Link>
        ) : (
          <Link href="/dashboard">
            <Button variant="outline">Back to Dashboard</Button>
          </Link>
        )}
      </div>
    </div>
  );
}
