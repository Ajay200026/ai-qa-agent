"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { ExecutionWizard, type WizardStepId } from "@/components/executions/execution-wizard";
import { ExecutionOrgStep } from "@/components/executions/execution-org-step";
import { ExecutionScenarioStep } from "@/components/executions/execution-scenario-step";
import { ExecutionLibrariesStep } from "@/components/executions/execution-libraries-step";
import { ExecutionReviewStep } from "@/components/executions/execution-review-step";
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
  const [step, setStep] = useState<WizardStepId>("org");
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
  const [testPackContent, setTestPackContent] = useState("");
  const [testCaseFile, setTestCaseFile] = useState<File | null>(null);
  const [regressionFile, setRegressionFile] = useState<File | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [accountQueryId, setAccountQueryId] = useState("");
  const [loginAsProfileId, setLoginAsProfileId] = useState("");
  const [recommendedQueryId, setRecommendedQueryId] = useState<string | null>(null);
  const [recommendedProfileId, setRecommendedProfileId] = useState<string | null>(null);

  const { data: llmConfig } = useQuery({
    queryKey: ["llm-config"],
    queryFn: () => api.getLlmConfig(),
    staleTime: 5 * 60_000,
  });

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

  const { data: orgs = [] } = useQuery({
    queryKey: ["orgs", projectId],
    queryFn: () => api.getOrgs(projectId!),
    enabled: !!projectId,
  });

  useEffect(() => {
    if (!selectedOrgId && orgs.length > 0) {
      const defaultOrg = orgs.find((o) => o.is_default) || orgs[0];
      setSelectedOrgId(defaultOrg.id);
    }
  }, [orgs, selectedOrgId]);

  const { data: workflows = [] } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.getWorkflows(),
  });

  const { data: accountQueries = [] } = useQuery({
    queryKey: ["account-queries", projectId],
    queryFn: () => api.listAccountQueries(projectId!),
    enabled: !!projectId,
    staleTime: 2 * 60_000,
  });

  const { data: loginAsProfiles = [] } = useQuery({
    queryKey: ["login-as-profiles", projectId],
    queryFn: () => api.listLoginAsProfiles(projectId!),
    enabled: !!projectId,
    staleTime: 2 * 60_000,
  });

  useEffect(() => {
    if (!projectId || !testPackContent.trim() || testPackContent.trim().length < 40) {
      setRecommendedQueryId(null);
      setRecommendedProfileId(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const [qRec, pRec] = await Promise.all([
          api.recommendAccountQuery(projectId, testPackContent),
          api.recommendLoginAsProfile(projectId, testPackContent),
        ]);
        if (qRec.recommended) {
          setRecommendedQueryId(qRec.recommended.id);
          if (!accountQueryId) setAccountQueryId(qRec.recommended.id);
        }
        if (pRec.recommended) {
          setRecommendedProfileId(pRec.recommended.id);
          if (!loginAsProfileId) setLoginAsProfileId(pRec.recommended.id);
        }
      } catch {
        /* ignore */
      }
    }, 600);
    return () => clearTimeout(timer);
  }, [testPackContent, projectId, accountQueryId, loginAsProfileId]);

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

  const handleRunTesting = async () => {
    if (!projectId || !selectedOrgId) {
      setError("Please select a Salesforce org");
      setStep("org");
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
      if (testPackContent.trim()) formData.append("test_pack_content", testPackContent.trim());
      if (accountQueryId) formData.append("account_query_id", accountQueryId);
      if (loginAsProfileId) formData.append("login_as_profile_id", loginAsProfileId);
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

  const selectedOrg = orgs.find((o) => o.id === selectedOrgId);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <PageHeader
        title="New Execution"
        description="Step through org selection, scenario setup, libraries, and run."
      />

      <ExecutionWizard currentStep={step} onStepClick={setStep}>
        {step === "org" && (
          <ExecutionOrgStep
            orgs={orgs}
            selectedOrgId={selectedOrgId}
            onSelectOrg={setSelectedOrgId}
            onNext={() => setStep("scenario")}
          />
        )}
        {step === "scenario" && (
          <ExecutionScenarioStep
            name={name}
            description={description}
            templateKey={templateKey}
            templateInputs={templateInputs}
            businessActionsText={businessActionsText}
            expectedText={expectedText}
            testPackContent={testPackContent}
            acceptanceCriteria={acceptanceCriteria}
            workflows={workflows}
            selectedTemplate={selectedTemplate}
            preview={preview}
            onNameChange={setName}
            onDescriptionChange={setDescription}
            onTemplateChange={(key) => {
              setTemplateKey(key);
              setTemplateInputs({});
              setPreview(null);
            }}
            onTemplateInputChange={(key, value) =>
              setTemplateInputs((prev) => ({ ...prev, [key]: value }))
            }
            onBusinessActionsChange={setBusinessActionsText}
            onExpectedChange={setExpectedText}
            onTestPackChange={setTestPackContent}
            onCriteriaChange={setAcceptanceCriteria}
            onTestCaseFile={setTestCaseFile}
            onRegressionFile={setRegressionFile}
            onPreview={handlePreview}
            onBack={() => setStep("org")}
            onNext={() => setStep("libraries")}
          />
        )}
        {step === "libraries" && (
          <ExecutionLibrariesStep
            accountQueries={accountQueries}
            loginAsProfiles={loginAsProfiles}
            accountQueryId={accountQueryId}
            loginAsProfileId={loginAsProfileId}
            recommendedQueryId={recommendedQueryId}
            recommendedProfileId={recommendedProfileId}
            llmConfig={llmConfig}
            onAccountQueryChange={setAccountQueryId}
            onLoginAsProfileChange={setLoginAsProfileId}
            onBack={() => setStep("scenario")}
            onNext={() => setStep("review")}
          />
        )}
        {step === "review" && (
          <ExecutionReviewStep
            org={selectedOrg}
            name={name}
            templateKey={templateKey}
            accountQueryName={accountQueries.find((q) => q.id === accountQueryId)?.name}
            loginAsProfileName={loginAsProfiles.find((p) => p.id === loginAsProfileId)?.name}
            loading={loading}
            onBack={() => setStep("libraries")}
            onRun={handleRunTesting}
          />
        )}
      </ExecutionWizard>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
