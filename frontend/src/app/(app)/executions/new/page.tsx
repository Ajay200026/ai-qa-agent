"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkflowPreviewResponse } from "@/lib/workflow-types";

const DEFAULT_ACTIONS = `Actions:
- Open Customer Details
- Update Primary Group = TEST_GROUP
- Submit`;

const DEFAULT_EXPECTED = `Expected:
- Request Created
- Status Submitted
- Primary Group Saved`;

export default function NewExecutionPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("Update Primary Group");
  const [templateKey, setTemplateKey] = useState("DATA_CHANGE_REQUEST");
  const [templateInputs, setTemplateInputs] = useState<Record<string, string>>({});
  const [businessActionsText, setBusinessActionsText] = useState(DEFAULT_ACTIONS);
  const [expectedText, setExpectedText] = useState(DEFAULT_EXPECTED);
  const [preview, setPreview] = useState<WorkflowPreviewResponse | null>(null);
  const [acceptanceCriteria, setAcceptanceCriteria] = useState(
    "Primary group updated and request submitted successfully"
  );
  const [testCaseFile, setTestCaseFile] = useState<File | null>(null);
  const [regressionFile, setRegressionFile] = useState<File | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [showConnect, setShowConnect] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [loginUrl, setLoginUrl] = useState("https://test.salesforce.com");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authMethod, setAuthMethod] = useState("credentials");
  const [accessToken, setAccessToken] = useState("");
  const [instanceUrl, setInstanceUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

  const { data: orgs = [], refetch: refetchOrgs } = useQuery({
    queryKey: ["orgs", projectId],
    queryFn: () => api.getOrgs(projectId!),
    enabled: !!projectId,
  });

  const { data: workflows = [] } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.getWorkflows(),
  });

  const { data: selectedTemplate } = useQuery({
    queryKey: ["workflow", templateKey],
    queryFn: () => api.getWorkflow(templateKey),
    enabled: !!templateKey,
  });

  const parseActions = (text: string) => {
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l && !l.toLowerCase().startsWith("actions"));
    return lines.map((line) => {
      const cleaned = line.replace(/^[-*]\s*/, "");
      if (cleaned.includes("=")) {
        const [action, value] = cleaned.split("=").map((s) => s.trim());
        return { action, value, description: cleaned };
      }
      return { action: cleaned, description: cleaned };
    });
  };

  const parseExpected = (text: string) =>
    text
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l && !l.toLowerCase().startsWith("expected"))
      .map((l) => l.replace(/^[-*]\s*/, ""));

  const handlePreview = async () => {
    setError("");
    try {
      const result = await api.previewWorkflow(templateKey, {
        inputs: templateInputs,
        business_actions: parseActions(businessActionsText),
        expected_results: parseExpected(expectedText),
      });
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    }
  };

  const handleConnectOrg = async () => {
    if (!projectId) return;
    setLoading(true);
    setError("");
    try {
      const org = await api.createOrg({
        project_id: projectId,
        name: orgName,
        org_type: "sandbox",
        login_url: loginUrl,
        auth_method: authMethod,
        username: authMethod === "credentials" ? username : undefined,
        password: authMethod === "credentials" ? password : undefined,
        access_token: authMethod === "oauth" ? accessToken : undefined,
        instance_url: authMethod === "oauth" ? instanceUrl : undefined,
      });
      await api.validateOrg(org.id);
      setSelectedOrgId(org.id);
      setShowConnect(false);
      refetchOrgs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect org");
    } finally {
      setLoading(false);
    }
  };

  const handleRunTesting = async () => {
    if (!projectId || !selectedOrgId) {
      setError("Please connect a Salesforce org first");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("project_id", projectId);
      formData.append("name", name);
      const fullDescription = [
        `Template: ${templateKey}`,
        description.trim(),
        businessActionsText,
        expectedText,
      ].join("\n");
      formData.append("description", fullDescription);
      formData.append("acceptance_criteria", acceptanceCriteria);
      formData.append("template_key", templateKey);
      formData.append("inputs", JSON.stringify(templateInputs));
      formData.append("business_actions", JSON.stringify(parseActions(businessActionsText)));
      formData.append("expected_results", JSON.stringify(parseExpected(expectedText)));
      if (testCaseFile) formData.append("test_case_file", testCaseFile);
      if (regressionFile) formData.append("regression_file", regressionFile);

      const scenario = await api.createScenario(formData);
      const execution = await api.createExecution(scenario.id, selectedOrgId);
      router.push(`/executions/${execution.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start execution");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">New Execution</h1>
        <p className="text-muted-foreground">
          Pick a workflow template, set inputs, and define business actions only
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Workflow & Scenario</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Scenario Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Update Primary Group - TC_DC_001"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="template">Workflow Template</Label>
            <select
              id="template"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={templateKey}
              onChange={(e) => {
                setTemplateKey(e.target.value);
                setTemplateInputs({});
                setPreview(null);
              }}
            >
              {workflows.map((wf) => (
                <option key={wf.key} value={wf.key}>
                  {wf.name}
                </option>
              ))}
              {workflows.length === 0 && (
                <option value="DATA_CHANGE_REQUEST">Data Change Request</option>
              )}
            </select>
          </div>

          {selectedTemplate &&
            Object.entries(selectedTemplate.input_schema).map(([key, spec]) => (
              <div key={key} className="space-y-2">
                <Label htmlFor={`input-${key}`}>
                  {spec.label || key}
                  <span className="ml-1 text-xs text-muted-foreground">
                    (default: {spec.default || "auto"})
                  </span>
                </Label>
                <Input
                  id={`input-${key}`}
                  placeholder={spec.default || ""}
                  value={templateInputs[key] || ""}
                  onChange={(e) =>
                    setTemplateInputs((prev) => ({ ...prev, [key]: e.target.value }))
                  }
                />
              </div>
            ))}

          <div className="space-y-2">
            <Label htmlFor="description">Business Objective</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="actions">Business Actions</Label>
            <Textarea
              id="actions"
              value={businessActionsText}
              onChange={(e) => setBusinessActionsText(e.target.value)}
              rows={5}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="expected">Expected Results</Label>
            <Textarea
              id="expected"
              value={expectedText}
              onChange={(e) => setExpectedText(e.target.value)}
              rows={4}
            />
          </div>

          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={handlePreview}>
              Preview Plan
            </Button>
          </div>

          {preview && (
            <div className="rounded-md border p-3 text-sm">
              <p className="font-medium mb-2">
                Merged plan ({preview.planned_steps.length} steps)
              </p>
              <ol className="list-decimal list-inside space-y-1 max-h-48 overflow-y-auto">
                {preview.planned_steps.map((step) => (
                  <li key={step.seq}>
                    {step.name} <span className="text-muted-foreground">({step.action})</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="criteria">Acceptance Criteria</Label>
            <Textarea
              id="criteria"
              value={acceptanceCriteria}
              onChange={(e) => setAcceptanceCriteria(e.target.value)}
              rows={2}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Salesforce Org</CardTitle>
          <Button variant="outline" onClick={() => setShowConnect(!showConnect)}>
            Connect Salesforce
          </Button>
        </CardHeader>
        <CardContent>
          {showConnect ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Org Name</Label>
                <Input value={orgName} onChange={(e) => setOrgName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Login URL</Label>
                <Input value={loginUrl} onChange={(e) => setLoginUrl(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Auth Method</Label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={authMethod}
                  onChange={(e) => setAuthMethod(e.target.value)}
                >
                  <option value="credentials">Username / Password</option>
                  <option value="oauth">OAuth / SFDX</option>
                </select>
              </div>
              {authMethod === "credentials" ? (
                <>
                  <div className="space-y-2">
                    <Label>Username</Label>
                    <Input value={username} onChange={(e) => setUsername(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label>Access Token</Label>
                    <Input value={accessToken} onChange={(e) => setAccessToken(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label>Instance URL</Label>
                    <Input value={instanceUrl} onChange={(e) => setInstanceUrl(e.target.value)} />
                  </div>
                </>
              )}
              <Button onClick={handleConnectOrg} disabled={loading}>
                Save & Validate
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <Label>Select Org</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedOrgId}
                onChange={(e) => setSelectedOrgId(e.target.value)}
              >
                <option value="">Select a connected org</option>
                {orgs.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name} ({org.status})
                  </option>
                ))}
              </select>
            </div>
          )}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button
        size="lg"
        className="w-full"
        onClick={handleRunTesting}
        disabled={loading || !name || !description}
      >
        {loading ? "Starting..." : "Run Testing"}
      </Button>
    </div>
  );
}
