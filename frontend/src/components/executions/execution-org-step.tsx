"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import type { SalesforceOrg } from "@/lib/types";

interface ExecutionOrgStepProps {
  orgs: SalesforceOrg[];
  selectedOrgId: string;
  onSelectOrg: (id: string) => void;
  onNext: () => void;
}

export function ExecutionOrgStep({
  orgs,
  selectedOrgId,
  onSelectOrg,
  onNext,
}: ExecutionOrgStepProps) {
  const selected = orgs.find((o) => o.id === selectedOrgId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Salesforce Org</CardTitle>
        <p className="text-sm text-muted-foreground">
          Select an authorized org for this test run. SOQL and Login As use this connection.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="org-select">Connected org</Label>
          <select
            id="org-select"
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={selectedOrgId}
            onChange={(e) => onSelectOrg(e.target.value)}
          >
            <option value="">Select an org…</option>
            {orgs.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name} ({org.status})
                {org.is_default ? " — default" : ""}
              </option>
            ))}
          </select>
        </div>

        {selected && (
          <div className="rounded-md border bg-muted/20 p-3 text-sm space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{selected.name}</span>
              <Badge variant={selected.status === "connected" ? "success" : "secondary"}>
                {selected.status}
              </Badge>
            </div>
            <p className="text-muted-foreground capitalize">
              {selected.org_type} · {selected.auth_method}
            </p>
            {selected.instance_url && (
              <p className="truncate text-xs text-muted-foreground">{selected.instance_url}</p>
            )}
          </div>
        )}

        {orgs.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No orgs connected.{" "}
            <Link href="/salesforce-orgs" className="font-medium underline">
              Authorize a Salesforce org
            </Link>{" "}
            first.
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Link href="/salesforce-orgs">
            <Button type="button" variant="outline">
              Manage orgs
            </Button>
          </Link>
          <Button type="button" onClick={onNext} disabled={!selectedOrgId}>
            Continue
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
