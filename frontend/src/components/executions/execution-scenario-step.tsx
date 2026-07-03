"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { WorkflowPreviewResponse, WorkflowTemplate } from "@/lib/workflow-types";

interface ExecutionScenarioStepProps {
  name: string;
  description: string;
  templateKey: string;
  templateInputs: Record<string, string>;
  businessActionsText: string;
  expectedText: string;
  testPackContent: string;
  acceptanceCriteria: string;
  workflows: { key: string; name: string }[];
  selectedTemplate?: WorkflowTemplate;
  preview: WorkflowPreviewResponse | null;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onTemplateChange: (key: string) => void;
  onTemplateInputChange: (key: string, value: string) => void;
  onBusinessActionsChange: (v: string) => void;
  onExpectedChange: (v: string) => void;
  onTestPackChange: (v: string) => void;
  onCriteriaChange: (v: string) => void;
  onTestCaseFile: (file: File | null) => void;
  onRegressionFile: (file: File | null) => void;
  onPreview: () => void;
  onBack: () => void;
  onNext: () => void;
}

export function ExecutionScenarioStep(props: ExecutionScenarioStepProps) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Scenario</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label>Scenario name</Label>
              <Input
                value={props.name}
                onChange={(e) => props.onNameChange(e.target.value)}
                placeholder="Update Primary Group - TC_DC_001"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Workflow template</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={props.templateKey}
                onChange={(e) => props.onTemplateChange(e.target.value)}
              >
                {props.workflows.map((wf) => (
                  <option key={wf.key} value={wf.key}>
                    {wf.name}
                  </option>
                ))}
                {props.workflows.length === 0 && (
                  <option value="DATA_CHANGE_REQUEST">Data Change Request</option>
                )}
              </select>
            </div>
          </div>

          {props.selectedTemplate &&
            Object.entries(props.selectedTemplate.input_schema).map(([key, spec]) => (
              <div key={key} className="space-y-2">
                <Label>
                  {spec.label || key}
                  <span className="ml-1 text-xs text-muted-foreground">
                    (default: {spec.default || "auto"})
                  </span>
                </Label>
                <Input
                  placeholder={spec.default || ""}
                  value={props.templateInputs[key] || ""}
                  onChange={(e) => props.onTemplateInputChange(key, e.target.value)}
                />
              </div>
            ))}

          <div className="space-y-2">
            <Label>Business objective</Label>
            <Textarea
              value={props.description}
              onChange={(e) => props.onDescriptionChange(e.target.value)}
              rows={2}
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2">
              <Label>Business actions</Label>
              <Textarea
                value={props.businessActionsText}
                onChange={(e) => props.onBusinessActionsChange(e.target.value)}
                rows={6}
              />
            </div>
            <div className="space-y-2">
              <Label>Expected results</Label>
              <Textarea
                value={props.expectedText}
                onChange={(e) => props.onExpectedChange(e.target.value)}
                rows={6}
              />
            </div>
          </div>
          <Button type="button" variant="outline" onClick={props.onPreview}>
            Preview plan
          </Button>
          {props.preview && (
            <div className="rounded-md border p-3 text-sm">
              <p className="mb-2 font-medium">
                Merged plan ({props.preview.planned_steps.length} steps)
              </p>
              <ol className="max-h-40 list-inside list-decimal space-y-1 overflow-y-auto">
                {props.preview.planned_steps.map((step) => (
                  <li key={step.seq}>
                    {step.name}{" "}
                    <span className="text-muted-foreground">({step.action})</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Test pack</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Paste test cases (markdown / tables)</Label>
            <Textarea
              value={props.testPackContent}
              onChange={(e) => props.onTestPackChange(e.target.value)}
              rows={10}
              placeholder="Paste US-21153 test cases or TC tables…"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Upload test pack</Label>
              <Input
                type="file"
                accept=".txt,.md,.csv,.xlsx,.xls"
                onChange={(e) => props.onTestCaseFile(e.target.files?.[0] || null)}
              />
            </div>
            <div className="space-y-2">
              <Label>Regression file (optional)</Label>
              <Input
                type="file"
                onChange={(e) => props.onRegressionFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Acceptance criteria</Label>
            <Textarea
              value={props.acceptanceCriteria}
              onChange={(e) => props.onCriteriaChange(e.target.value)}
              rows={2}
            />
          </div>
          <div className="flex justify-between">
            <Button type="button" variant="outline" onClick={props.onBack}>
              Back
            </Button>
            <Button type="button" onClick={props.onNext} disabled={!props.name.trim()}>
              Continue
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
