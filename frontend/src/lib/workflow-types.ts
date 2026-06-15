export interface WorkflowTemplateSummary {
  key: string;
  name: string;
  description: string | null;
  input_schema: Record<string, WorkflowInputDef>;
}

export interface WorkflowInputDef {
  type: string;
  default?: string;
  label?: string;
}

export interface WorkflowTemplate extends WorkflowTemplateSummary {
  id: string;
  steps: WorkflowStepDef[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowStepDef {
  seq: number;
  action: string;
  name: string;
  params?: Record<string, string>;
  optional?: boolean;
}

export interface WorkflowPreviewRequest {
  inputs: Record<string, string>;
  business_actions: Array<{ action: string; value?: string; field?: string; description?: string }>;
  expected_results: string[];
}

export interface WorkflowPreviewResponse {
  template_key: string;
  planned_steps: Array<{ seq: number; name: string; action: string; params: Record<string, string> }>;
  expected_results: string[];
}
