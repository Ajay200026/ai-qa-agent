"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import type { AccountQuery, LoginAsProfile, LlmConfig } from "@/lib/types";

interface ExecutionLibrariesStepProps {
  accountQueries: AccountQuery[];
  loginAsProfiles: LoginAsProfile[];
  accountQueryId: string;
  loginAsProfileId: string;
  recommendedQueryId: string | null;
  recommendedProfileId: string | null;
  llmConfig?: LlmConfig;
  onAccountQueryChange: (id: string) => void;
  onLoginAsProfileChange: (id: string) => void;
  onBack: () => void;
  onNext: () => void;
}

export function ExecutionLibrariesStep({
  accountQueries,
  loginAsProfiles,
  accountQueryId,
  loginAsProfileId,
  recommendedQueryId,
  recommendedProfileId,
  llmConfig,
  onAccountQueryChange,
  onLoginAsProfileChange,
  onBack,
  onNext,
}: ExecutionLibrariesStepProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Libraries</CardTitle>
        <p className="text-sm text-muted-foreground">
          Optional saved queries and Login As profiles. Manage in{" "}
          <Link href="/account-queries" className="underline">
            Account Queries
          </Link>{" "}
          and{" "}
          <Link href="/login-as" className="underline">
            Login As
          </Link>
          .
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Account query</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={accountQueryId}
            onChange={(e) => onAccountQueryChange(e.target.value)}
          >
            <option value="">None</option>
            {accountQueries.map((q) => (
              <option key={q.id} value={q.id}>
                {q.name}
              </option>
            ))}
          </select>
          {recommendedQueryId && accountQueryId === recommendedQueryId && (
            <Badge variant="secondary">Recommended from test pack</Badge>
          )}
        </div>
        <div className="space-y-2">
          <Label>Login As profile</Label>
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={loginAsProfileId}
            onChange={(e) => onLoginAsProfileChange(e.target.value)}
          >
            <option value="">None (stay as admin)</option>
            {loginAsProfiles.filter((p) => p.enabled).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.onboarding_role} @ {p.bottler_id})
              </option>
            ))}
          </select>
          {recommendedProfileId && loginAsProfileId === recommendedProfileId && (
            <Badge variant="secondary">Recommended from test pack</Badge>
          )}
        </div>
        {(accountQueryId || loginAsProfileId) &&
          llmConfig &&
          !llmConfig.is_local &&
          llmConfig.enabled && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
              Account queries and Login As data stay local and are never sent to the LLM.
            </div>
          )}
        <div className="flex justify-between">
          <Button type="button" variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button type="button" onClick={onNext}>
            Continue
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
