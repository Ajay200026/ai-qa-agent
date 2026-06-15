export interface User {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
}

export interface SalesforceOrg {
  id: string;
  project_id: string;
  name: string;
  org_type: string;
  login_url: string;
  auth_method: string;
  instance_url: string | null;
  status: string;
  last_validated_at: string | null;
  created_at: string;
}

export interface Scenario {
  id: string;
  project_id: string;
  name: string;
  description: string;
  acceptance_criteria: string;
  template_key: string | null;
  inputs: Record<string, string>;
  business_actions: Array<Record<string, string>>;
  expected_results: string[];
  test_case_file: string | null;
  regression_file: string | null;
  created_at: string;
}

export interface ExecutionStep {
  id: string;
  seq: number;
  name: string;
  action: string;
  status: string;
  screenshot_path: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Execution {
  id: string;
  scenario_id: string;
  org_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  plan_json: Record<string, unknown> | null;
  created_at: string;
  steps: ExecutionStep[];
}

export interface Report {
  id: string;
  execution_id: string;
  summary: string;
  passed_count: number;
  failed_count: number;
  llm_analysis: string | null;
  artifacts_path: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_executions: number;
  success_rate: number;
  failed_executions: number;
  connected_orgs: number;
}

export interface ExecutionEvent {
  execution_id: string;
  event_type: string;
  step_seq: number | null;
  step_name: string | null;
  status: string | null;
  message: string | null;
  screenshot_path: string | null;
  timestamp: string;
}
