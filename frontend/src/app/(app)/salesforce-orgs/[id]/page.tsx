"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, RefreshCw, Star, Trash2 } from "lucide-react";
import { OrgMetadataSkeleton } from "@/components/loading/org-metadata-skeleton";

export default function SalesforceOrgDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: org, isLoading, refetch } = useQuery({
    queryKey: ["org", id],
    queryFn: () => api.getOrg(id),
  });

  if (isLoading || !org) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Salesforce Org"
          description="Connected Salesforce org details"
        />
        <OrgMetadataSkeleton />
      </div>
    );
  }

  const statusVariant =
    org.status === "connected" ? "success" : org.status === "error" ? "destructive" : "secondary";

  const handleValidate = async () => {
    setBusy(true);
    try {
      const result = await api.validateOrg(id);
      setMessage(result.message);
      await refetch();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSetDefault = async () => {
    setBusy(true);
    try {
      await api.updateOrg(id, { is_default: true });
      await refetch();
      setMessage("Set as default org.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${org.name}"?`)) return;
    setBusy(true);
    try {
      await api.deleteOrg(id);
      window.location.href = "/salesforce-orgs";
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Delete failed");
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={org.name}
        description="Connected Salesforce org details"
        actions={
          <Link href="/salesforce-orgs">
            <Button variant="outline" size="sm" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
          </Link>
        }
      />

      {message && (
        <div className="rounded-lg border bg-muted/30 px-4 py-3 text-sm">{message}</div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Org metadata</CardTitle>
          <Badge variant={statusVariant}>{org.status}</Badge>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <p className="text-muted-foreground">Type</p>
            <p className="font-medium capitalize">{org.org_type}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Auth method</p>
            <p className="font-medium capitalize">{org.auth_method}</p>
            {org.auth_method === "oauth" && (
              <p className="mt-1 text-xs text-muted-foreground">
                One-time browser sign-in — test runs reuse your stored OAuth session (no password
                needed).
              </p>
            )}
          </div>
          {org.salesforce_username && (
            <div className="sm:col-span-2">
              <p className="text-muted-foreground">Salesforce user</p>
              <p className="font-medium">{org.salesforce_username}</p>
            </div>
          )}
          <div className="sm:col-span-2">
            <p className="text-muted-foreground">Login URL</p>
            <p className="break-all font-medium">{org.login_url}</p>
          </div>
          <div className="sm:col-span-2">
            <p className="text-muted-foreground">Instance URL</p>
            <p className="break-all font-medium">{org.instance_url || "—"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Role</p>
            <p className="font-medium">{org.role || "—"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Bottler</p>
            <p className="font-medium">{org.bottler || "—"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Default org</p>
            <p className="font-medium">{org.is_default ? "Yes" : "No"}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Last validated</p>
            <p className="font-medium">{formatDate(org.last_validated_at)}</p>
          </div>
          <div className="sm:col-span-2">
            <p className="text-muted-foreground">Org ID</p>
            <p className="break-all font-mono text-xs">{org.id}</p>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" loading={busy} onClick={handleValidate} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Re-validate
        </Button>
        {!org.is_default && (
          <Button variant="outline" loading={busy} onClick={handleSetDefault} className="gap-2">
            <Star className="h-4 w-4" />
            Set as default
          </Button>
        )}
        <Button variant="destructive" loading={busy} onClick={handleDelete} className="gap-2">
          <Trash2 className="h-4 w-4" />
          Delete org
        </Button>
      </div>
    </div>
  );
}
