"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SalesforceOrg } from "@/lib/types";

interface ExecutionReviewStepProps {
  org?: SalesforceOrg;
  name: string;
  templateKey: string;
  accountQueryName?: string;
  loginAsProfileName?: string;
  loading: boolean;
  onBack: () => void;
  onRun: () => void;
}

export function ExecutionReviewStep({
  org,
  name,
  templateKey,
  accountQueryName,
  loginAsProfileName,
  loading,
  onBack,
  onRun,
}: ExecutionReviewStepProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Review & Run</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Org</dt>
            <dd className="font-medium">{org?.name || "—"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Scenario</dt>
            <dd className="font-medium">{name}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Template</dt>
            <dd className="font-medium">{templateKey}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Account query</dt>
            <dd className="font-medium">{accountQueryName || "None"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Login As</dt>
            <dd className="font-medium">{loginAsProfileName || "Admin only"}</dd>
          </div>
        </dl>
        <div className="flex justify-between pt-2">
          <Button type="button" variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button size="lg" onClick={onRun} disabled={loading || !org}>
            {loading ? "Starting…" : "Run execution"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
