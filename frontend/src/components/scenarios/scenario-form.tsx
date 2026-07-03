"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import type { CustomerTarget, IdentityMap, LoginAsTarget, Scenario } from "@/lib/types";
import { CustomerTargetingCard } from "@/components/scenarios/customer-targeting-card";
import { IdentityMapCard } from "@/components/scenarios/identity-map-card";
import { LoginAsCard } from "@/components/scenarios/login-as-card";

export interface ScenarioFormValues {
  name: string;
  description: string;
  acceptance_criteria: string;
  template_key: string | null;
  inputs: Record<string, string>;
  business_actions: Array<Record<string, string>>;
  expected_results: string[];
  test_pack_content: string | null;
  account_query_id: string | null;
  login_as_profile_id: string | null;
  customer_target: CustomerTarget | null;
  login_as_target: LoginAsTarget | null;
  identity_map: IdentityMap | null;
}

interface Props {
  initial: Scenario;
  projectId: string;
  orgId?: string | null;
  orgBottler?: string | null;
  onSubmit: (values: ScenarioFormValues) => Promise<void> | void;
  submitting?: boolean;
  submitLabel?: string;
}

function actionsToText(actions: Array<Record<string, string>>): string {
  if (!actions?.length) return "";
  return actions
    .map((a) =>
      a.value ? `- ${a.action} = ${a.value}` : `- ${a.action || a.description || ""}`
    )
    .join("\n");
}

function parseActions(text: string): Array<Record<string, string>> {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.toLowerCase().startsWith("actions"))
    .map((line) => {
      const cleaned = line.replace(/^[-*]\s*/, "");
      const result: Record<string, string> = { action: cleaned, description: cleaned };
      if (cleaned.includes("=")) {
        const [action, value] = cleaned.split("=").map((s) => s.trim());
        result.action = action;
        result.value = value;
      }
      return result;
    });
}

export function ScenarioForm({
  initial,
  projectId,
  orgId,
  orgBottler,
  onSubmit,
  submitting,
  submitLabel = "Save Changes",
}: Props) {
  const [name, setName] = useState(initial.name);
  const [description, setDescription] = useState(initial.description);
  const [acceptance, setAcceptance] = useState(initial.acceptance_criteria);
  const [templateKey, setTemplateKey] = useState(initial.template_key || "DATA_CHANGE_REQUEST");
  const [actionsText, setActionsText] = useState(
    actionsToText(initial.business_actions || [])
  );
  const [expectedText, setExpectedText] = useState(
    (initial.expected_results || []).map((e) => `- ${e}`).join("\n")
  );
  const [inputsJson, setInputsJson] = useState(
    JSON.stringify(initial.inputs || {}, null, 2)
  );
  const [testPack, setTestPack] = useState(initial.test_pack_content || "");
  const [accountQueryId, setAccountQueryId] = useState(
    initial.account_query_id || ""
  );
  const [loginAsProfileId, setLoginAsProfileId] = useState(
    initial.login_as_profile_id || ""
  );
  const [customerTarget, setCustomerTarget] = useState<CustomerTarget | null>(
    initial.customer_target || null
  );
  const [loginAsTarget, setLoginAsTarget] = useState<LoginAsTarget | null>(
    initial.login_as_target || null
  );
  const [identityMap, setIdentityMap] = useState<IdentityMap | null>(
    initial.identity_map || null
  );
  const [parseError, setParseError] = useState("");

  const { data: workflows = [], isLoading: workflowsLoading } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.getWorkflows(),
    staleTime: 10 * 60_000,
  });

  const { data: accountQueries = [], isLoading: accountQueriesLoading } = useQuery({
    queryKey: ["account-queries", projectId],
    queryFn: () => api.listAccountQueries(projectId),
    staleTime: 2 * 60_000,
  });

  const { data: loginAsProfiles = [], isLoading: loginAsProfilesLoading } = useQuery({
    queryKey: ["login-as-profiles", projectId],
    queryFn: () => api.listLoginAsProfiles(projectId),
    staleTime: 2 * 60_000,
  });

  const librariesLoading =
    workflowsLoading || accountQueriesLoading || loginAsProfilesLoading;

  useEffect(() => {
    setParseError("");
  }, [inputsJson]);

  const handleSubmit = async () => {
    let inputs: Record<string, string>;
    try {
      inputs = inputsJson.trim() ? JSON.parse(inputsJson) : {};
    } catch {
      setParseError("Inputs must be valid JSON");
      return;
    }
    const expectedResults = expectedText
      .split("\n")
      .map((l) => l.replace(/^[-*]\s*/, "").trim())
      .filter(Boolean);
    await onSubmit({
      name,
      description,
      acceptance_criteria: acceptance,
      template_key: templateKey,
      inputs,
      business_actions: parseActions(actionsText),
      expected_results: expectedResults,
      test_pack_content: testPack.trim() ? testPack : null,
      account_query_id: accountQueryId || null,
      login_as_profile_id: loginAsProfileId || null,
      customer_target: customerTarget,
      login_as_target: loginAsTarget,
      identity_map: identityMap,
    });
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Scenario</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Workflow template</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={templateKey}
              onChange={(e) => setTemplateKey(e.target.value)}
            >
              {workflows.map((wf) => (
                <option key={wf.key} value={wf.key}>
                  {wf.name}
                </option>
              ))}
              {workflows.length === 0 && (
                <option value={templateKey}>{templateKey}</option>
              )}
            </select>
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Acceptance Criteria</Label>
            <Textarea
              rows={2}
              value={acceptance}
              onChange={(e) => setAcceptance(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Inputs (JSON)</Label>
            <Textarea
              rows={5}
              className="font-mono text-xs"
              value={inputsJson}
              onChange={(e) => setInputsJson(e.target.value)}
            />
            {parseError && (
              <p className="text-xs text-destructive">{parseError}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>Business Actions (one per line)</Label>
            <Textarea
              rows={5}
              value={actionsText}
              onChange={(e) => setActionsText(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Expected Results (one per line)</Label>
            <Textarea
              rows={4}
              value={expectedText}
              onChange={(e) => setExpectedText(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Test Pack Content</Label>
            <Textarea
              rows={8}
              value={testPack}
              onChange={(e) => setTestPack(e.target.value)}
              placeholder="Paste the test cases or markdown table here..."
            />
          </div>
        </CardContent>
      </Card>

      <LoginAsCard
        bottler={orgBottler || loginAsTarget?.bottler_id || null}
        value={loginAsTarget}
        onChange={setLoginAsTarget}
      />

      {orgId && (
        <CustomerTargetingCard
          orgId={orgId}
          bottler={orgBottler || customerTarget?.bottler || null}
          value={customerTarget}
          onChange={setCustomerTarget}
        />
      )}

      {testPack.trim().length >= 40 && (
        <IdentityMapCard
          testPackContent={testPack}
          value={identityMap}
          onChange={setIdentityMap}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Libraries</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Manage entries in{" "}
            <Link href="/account-queries" className="underline">
              Account Queries
            </Link>{" "}
            and{" "}
            <Link href="/login-as" className="underline">
              Login As
            </Link>
            .
          </p>
          {librariesLoading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner size="sm" />
              Loading libraries…
            </div>
          ) : (
            <>
          <div className="space-y-2">
            <Label>Account Query</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={accountQueryId}
              onChange={(e) => setAccountQueryId(e.target.value)}
            >
              <option value="">None</option>
              {accountQueries.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>Login As Profile</Label>
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={loginAsProfileId}
              onChange={(e) => setLoginAsProfileId(e.target.value)}
            >
              <option value="">None</option>
              {loginAsProfiles.filter((p) => p.enabled).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
            </>
          )}
        </CardContent>
      </Card>

      <Button onClick={handleSubmit} loading={!!submitting} size="lg">
        {submitting ? "Saving…" : submitLabel}
      </Button>
    </div>
  );
}
