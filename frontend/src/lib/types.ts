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
  role?: string | null;
  bottler?: string | null;
  is_default?: boolean;
  salesforce_username?: string | null;
  last_validated_at: string | null;
  created_at: string;
}

export interface CustomerTarget {
  account_number?: string | null;
  account_name?: string | null;
  sales_office?: string | null;
  account_group?: string | null;
  distribution_channel?: string | null;
  search_strategy?: "by_number" | "by_name" | "by_soql";
  soql_query?: string | null;
  soql_resolved_at?: string | null;
  bottler?: string | null;
}

export interface LoginAsTarget {
  bottler_id: string;
  onboarding_role: string;
  enabled?: boolean;
}

export interface IdentityMapEntry {
  bottler: string;
  role: string;
  override_bottler?: string | null;
  override_role?: string | null;
  enabled?: boolean;
}

export interface IdentityMap {
  entries: IdentityMapEntry[];
}

export interface IdentityPreviewItem {
  bottler: string | null;
  role: string | null;
  tc_ids: string[];
}

export interface IdentityPreviewResponse {
  identities: IdentityPreviewItem[];
  pack_bottler: string | null;
}

export interface MatchHints {
  bottler?: string | null;
  account_group?: string | null;
  distribution_channel?: string | null;
  role?: string | null;
  tags?: string[];
}

export interface AccountQuery {
  id: string;
  project_id: string;
  name: string;
  soql_text: string;
  match_hints?: MatchHints | null;
  sort_order: number;
  created_at: string;
}

export interface LoginAsProfile {
  id: string;
  project_id: string;
  name: string;
  bottler_id: string;
  onboarding_role: string;
  match_hints?: MatchHints | null;
  enabled: boolean;
  sort_order: number;
  created_at: string;
}

export interface RecommendationItem {
  id: string;
  name: string;
  score: number;
  reason?: string | null;
}

export interface RecommendResponse {
  recommended: RecommendationItem | null;
  alternatives: RecommendationItem[];
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
  test_pack_content?: string | null;
  customer_target?: CustomerTarget | null;
  login_as_target?: LoginAsTarget | null;
  identity_map?: IdentityMap | null;
  account_query_id?: string | null;
  login_as_profile_id?: string | null;
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
  action_params?: Record<string, unknown> | null;
  notes?: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface SoqlAccountRow {
  account_number: string | null;
  account_name: string | null;
  sales_office: string | null;
  account_group: string | null;
  distribution_channel: string | null;
  bottler: string | null;
  raw: Record<string, unknown>;
}

export interface SoqlQueryResponse {
  total_size: number;
  records: SoqlAccountRow[];
  done: boolean;
}

export interface CustomerSearchOption {
  account_group: string;
  distribution_channel: string | null;
}

export interface CustomerSearchOptions {
  bottler: string | null;
  sales_office: string | null;
  combinations: CustomerSearchOption[];
  default_soql: string;
}

export interface LlmConfig {
  provider: string;
  is_local: boolean;
  enabled: boolean;
  llm_field_fallback: boolean;
  model?: string | null;
  embedding_model?: string | null;
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

export interface KnowledgeRepo {
  id: string;
  name: string;
  path: string;
  owner_id: string;
  created_at: string;
}

export interface KnowledgeModule {
  id: string;
  repo_id: string;
  name: string;
  scan_status: string;
  scan_error: string | null;
  stats: Record<string, number | string> | null;
  scanned_at: string | null;
  created_at: string;
}

export interface DiscoveredModule {
  name: string;
  file_count: number;
}

export interface ModuleStatus {
  module_id: string;
  scan_status: string;
  scan_error: string | null;
  stats: Record<string, number | string> | null;
  graph_status: string;
  vector_status: string;
  ai_status: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  name: string;
  summary?: string | null;
  file_path?: string | null;
  entity_id?: string | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface EntityDetail {
  id: string;
  entity_type: string;
  name: string;
  file_path: string | null;
  summary: string | null;
  extracted: Record<string, unknown> | null;
  business_rules: string[] | null;
  dependencies: GraphNode[];
  related_files: string[];
  navigation_path: string[];
}

export interface AskCitation {
  entity_id: string | null;
  name: string;
  entity_type: string;
  file_path: string | null;
}

export interface AskResponse {
  answer: string;
  citations: AskCitation[];
}
