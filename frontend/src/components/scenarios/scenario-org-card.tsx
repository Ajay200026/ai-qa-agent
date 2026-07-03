"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { ORG_TYPES, loginUrlForOrgType } from "@/lib/salesforce-org";
import type { SalesforceOrg } from "@/lib/types";

export interface ScenarioOrgFormValues {
  org_type: string;
  login_url: string;
}

interface Props {
  org: SalesforceOrg;
  onChange: (values: ScenarioOrgFormValues) => void;
}

export function ScenarioOrgCard({ org, onChange }: Props) {
  const [orgType, setOrgType] = useState(org.org_type);
  const [customLoginUrl, setCustomLoginUrl] = useState(
    org.org_type === "custom" ? org.login_url : ""
  );

  useEffect(() => {
    setOrgType(org.org_type);
    setCustomLoginUrl(org.org_type === "custom" ? org.login_url : "");
  }, [org.id, org.org_type, org.login_url]);

  useEffect(() => {
    const loginUrl =
      orgType === "custom"
        ? loginUrlForOrgType(orgType, customLoginUrl)
        : loginUrlForOrgType(orgType, "");
    onChange({ org_type: orgType, login_url: loginUrl });
  }, [orgType, customLoginUrl, onChange]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Salesforce Org</CardTitle>
        <p className="text-sm text-muted-foreground">
          Org used for this test run. Change the org type if login or OAuth should target a
          different Salesforce environment.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border bg-muted/20 p-3 text-sm">
          <p className="font-medium">{org.name}</p>
          <p className="text-xs text-muted-foreground capitalize">
            {org.auth_method} · {org.status}
          </p>
          {org.instance_url && (
            <p className="mt-1 truncate text-xs text-muted-foreground">{org.instance_url}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label>Org type</Label>
          <div className="flex flex-wrap gap-2">
            {ORG_TYPES.map((t) => (
              <Button
                key={t.value}
                type="button"
                size="sm"
                variant={orgType === t.value ? "default" : "outline"}
                onClick={() => setOrgType(t.value)}
              >
                {t.label}
              </Button>
            ))}
          </div>
        </div>
        {orgType === "custom" && (
          <div className="space-y-2">
            <Label>Login URL</Label>
            <Input
              value={customLoginUrl}
              onChange={(e) => setCustomLoginUrl(e.target.value)}
              placeholder="https://test.salesforce.com"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
