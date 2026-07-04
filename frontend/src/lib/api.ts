import type {
  AccountQuery,
  AzureConnection,
  AzureProject,
  AzureRepo,
  BrainConfig,
  BrainNodeDetail,
  AskCitation,
  AskResponse,
  CustomerSearchOptions,
  CustomerTarget,
  DashboardStats,
  DiscoveredModule,
  ValidateScopeResponse,
  RepoFolderEntry,
  RepoFileEntry,
  FileContentResponse,
  EntityDetail,
  Execution,
  ExecutionStep,
  IdentityMap,
  IdentityPreviewResponse,
  KnowledgeGraph,
  KnowledgeModule,
  KnowledgeRepo,
  KnowledgeRepoCreate,
  FolderUploadResult,
  LoginAsProfile,
  LoginAsTarget,
  LlmConfig,
  MatchHints,
  ModuleStatus,
  Project,
  RecommendResponse,
  Report,
  SalesforceOrg,
  Scenario,
  SoqlQueryResponse,
  User,
} from "./types";
import type {
  WorkflowPreviewRequest,
  WorkflowPreviewResponse,
  WorkflowTemplate,
  WorkflowTemplateSummary,
} from "./workflow-types";
import { getFirebaseIdToken } from "./firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export { API_URL };

class ApiClient {
  /** Fresh Firebase ID token (auto-refreshes when expired); falls back to stored legacy JWT. */
  private async resolveToken(forceRefresh = false): Promise<string | null> {
    if (typeof window !== "undefined") {
      try {
        const fresh = await getFirebaseIdToken(forceRefresh);
        if (fresh) {
          localStorage.setItem("token", fresh);
          return fresh;
        }
      } catch {
        // Firebase unavailable — use stored token if any
      }
    }
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    retried = false
  ): Promise<T> {
    const token = await this.resolveToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      const detail = error.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg).join(", ")
            : `HTTP ${response.status}`;

      if (
        response.status === 401 &&
        !retried &&
        typeof message === "string" &&
        /expired|invalid firebase token/i.test(message)
      ) {
        const refreshed = await this.resolveToken(true);
        if (refreshed) {
          return this.request<T>(path, options, true);
        }
      }

      throw new Error(message || `HTTP ${response.status}`);
    }

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  }

  async register(email: string, password: string): Promise<User> {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async login(email: string, password: string): Promise<{ access_token: string }> {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async getMe(): Promise<User> {
    return this.request("/auth/me");
  }

  async getProjects(): Promise<Project[]> {
    return this.request("/projects");
  }

  async createProject(name: string, description?: string): Promise<Project> {
    return this.request("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  }

  async getOrgs(projectId: string): Promise<SalesforceOrg[]> {
    return this.request(`/salesforce/orgs?project_id=${projectId}`);
  }

  async createOrg(data: {
    project_id: string;
    name: string;
    org_type: string;
    login_url: string;
    auth_method: string;
    username?: string;
    password?: string;
    security_token?: string;
    access_token?: string;
    instance_url?: string;
    role?: string;
    bottler?: string;
    is_default?: boolean;
  }): Promise<SalesforceOrg> {
    return this.request("/salesforce/orgs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async validateOrg(orgId: string): Promise<{ valid: boolean; message: string }> {
    return this.request(`/salesforce/orgs/${orgId}/validate`, { method: "POST" });
  }

  async getOrg(orgId: string): Promise<SalesforceOrg> {
    return this.request(`/salesforce/orgs/${orgId}`);
  }

  async updateOrg(
    orgId: string,
    data: Partial<{
      name: string;
      org_type: string;
      login_url: string;
      instance_url: string;
      role: string;
      bottler: string;
      is_default: boolean;
      username: string;
      password: string;
      security_token: string;
    }>
  ): Promise<SalesforceOrg> {
    return this.request(`/salesforce/orgs/${orgId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteOrg(orgId: string): Promise<void> {
    return this.request(`/salesforce/orgs/${orgId}`, { method: "DELETE" });
  }

  async startSalesforceOAuth(data: {
    project_id: string;
    name: string;
    org_type: string;
    login_url?: string;
    role?: string;
    bottler?: string;
    is_default?: boolean;
  }): Promise<{ authorization_url: string; state: string; redirect_session: string }> {
    return this.request("/salesforce/orgs/oauth/start", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async completeSalesforceOAuth(data: {
    state: string;
    code: string;
  }): Promise<{ org: SalesforceOrg }> {
    return this.request("/salesforce/orgs/oauth/callback", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async createScenario(formData: FormData): Promise<Scenario> {
    return this.request("/scenarios", {
      method: "POST",
      body: formData,
      headers: {},
    });
  }

  async getWorkflows(): Promise<WorkflowTemplateSummary[]> {
    return this.request("/workflows");
  }

  async getWorkflow(key: string): Promise<WorkflowTemplate> {
    return this.request(`/workflows/${key}`);
  }

  async previewWorkflow(
    key: string,
    body: WorkflowPreviewRequest
  ): Promise<WorkflowPreviewResponse> {
    return this.request(`/workflows/${key}/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async getScenarios(projectId: string): Promise<Scenario[]> {
    return this.request(`/scenarios?project_id=${projectId}`);
  }

  async createExecution(scenarioId: string, orgId: string): Promise<Execution> {
    return this.request("/executions", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId, org_id: orgId }),
    });
  }

  async getExecutions(): Promise<Execution[]> {
    return this.request("/executions");
  }

  async getFailedExecutions(): Promise<Execution[]> {
    return this.request("/executions/failed");
  }

  async getExecution(id: string): Promise<Execution> {
    return this.request(`/executions/${id}`);
  }

  async rerunExecution(
    id: string,
    body?: { from_step_seq?: number }
  ): Promise<Execution> {
    return this.request(`/executions/${id}/rerun`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    });
  }

  async patchExecutionStep(
    executionId: string,
    seq: number,
    params: Record<string, unknown>
  ): Promise<ExecutionStep> {
    return this.request(`/executions/${executionId}/steps/${seq}`, {
      method: "PATCH",
      body: JSON.stringify({ params }),
    });
  }

  async putExecutionStepNotes(
    executionId: string,
    seq: number,
    notes: string | null
  ): Promise<ExecutionStep> {
    return this.request(`/executions/${executionId}/steps/${seq}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes }),
    });
  }

  async updateScenario(
    id: string,
    payload: Partial<Scenario> & {
      account_query_id?: string | null;
      login_as_profile_id?: string | null;
      customer_target?: Scenario["customer_target"];
      login_as_target?: Scenario["login_as_target"];
      identity_map?: Scenario["identity_map"];
    }
  ): Promise<Scenario> {
    return this.request(`/scenarios/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async getScenario(id: string): Promise<Scenario> {
    return this.request(`/scenarios/${id}`);
  }

  async querySalesforce(
    orgId: string,
    soql: string,
    limit = 5
  ): Promise<SoqlQueryResponse> {
    return this.request(`/salesforce/orgs/${orgId}/query`, {
      method: "POST",
      body: JSON.stringify({ soql, limit }),
    });
  }

  async getCustomerSearchOptions(
    orgId: string,
    salesOffice?: string
  ): Promise<CustomerSearchOptions> {
    const qs = salesOffice
      ? `?sales_office=${encodeURIComponent(salesOffice)}`
      : "";
    return this.request(`/salesforce/orgs/${orgId}/customer-search-options${qs}`);
  }

  async getLlmConfig(): Promise<LlmConfig> {
    return this.request("/config/llm");
  }

  async previewIdentities(testPackContent: string): Promise<IdentityPreviewResponse> {
    return this.request("/scenarios/preview-identities", {
      method: "POST",
      body: JSON.stringify({ test_pack_content: testPackContent }),
    });
  }

  async listAccountQueries(projectId: string): Promise<AccountQuery[]> {
    return this.request(`/account-queries?project_id=${projectId}`);
  }

  async createAccountQuery(data: {
    project_id: string;
    name: string;
    soql_text: string;
    match_hints?: MatchHints | null;
    sort_order?: number;
  }): Promise<AccountQuery> {
    return this.request("/account-queries", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateAccountQuery(
    id: string,
    data: Partial<{
      name: string;
      soql_text: string;
      match_hints: MatchHints | null;
      sort_order: number;
    }>
  ): Promise<AccountQuery> {
    return this.request(`/account-queries/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteAccountQuery(id: string): Promise<void> {
    return this.request(`/account-queries/${id}`, { method: "DELETE" });
  }

  async recommendAccountQuery(
    projectId: string,
    testPackContent: string
  ): Promise<RecommendResponse> {
    return this.request("/account-queries/recommend", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, test_pack_content: testPackContent }),
    });
  }

  async listLoginAsProfiles(projectId: string): Promise<LoginAsProfile[]> {
    return this.request(`/login-as-profiles?project_id=${projectId}`);
  }

  async createLoginAsProfile(data: {
    project_id: string;
    name: string;
    bottler_id: string;
    onboarding_role: string;
    match_hints?: MatchHints | null;
    enabled?: boolean;
    sort_order?: number;
  }): Promise<LoginAsProfile> {
    return this.request("/login-as-profiles", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateLoginAsProfile(
    id: string,
    data: Partial<{
      name: string;
      bottler_id: string;
      onboarding_role: string;
      match_hints: MatchHints | null;
      enabled: boolean;
      sort_order: number;
    }>
  ): Promise<LoginAsProfile> {
    return this.request(`/login-as-profiles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteLoginAsProfile(id: string): Promise<void> {
    return this.request(`/login-as-profiles/${id}`, { method: "DELETE" });
  }

  async recommendLoginAsProfile(
    projectId: string,
    testPackContent: string
  ): Promise<RecommendResponse> {
    return this.request("/login-as-profiles/recommend", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, test_pack_content: testPackContent }),
    });
  }

  async stopExecution(id: string): Promise<Execution> {
    return this.request(`/executions/${id}/stop`, { method: "POST" });
  }

  async deleteExecution(id: string): Promise<void> {
    return this.request(`/executions/${id}`, { method: "DELETE" });
  }

  async clearFailedExecutions(): Promise<{ deleted: number }> {
    return this.request("/executions/failed", { method: "DELETE" });
  }

  async clearExecutionHistory(): Promise<{ deleted: number }> {
    return this.request("/executions/history", { method: "DELETE" });
  }

  async getReports(): Promise<Report[]> {
    return this.request("/reports");
  }

  async getReport(id: string): Promise<Report> {
    return this.request(`/reports/${id}`);
  }

  async getReportByExecution(executionId: string): Promise<Report> {
    return this.request(`/reports/execution/${executionId}`);
  }

  async getDashboardStats(): Promise<DashboardStats> {
    return this.request("/reports/dashboard");
  }

  getArtifactUrl(executionId: string, filename: string): string {
    return `${API_URL}/reports/artifacts/${executionId}/${encodeURIComponent(filename)}`;
  }

  async listArtifacts(executionId: string): Promise<{ files: string[] }> {
    return this.request(`/reports/artifacts/${executionId}`);
  }

  async downloadReport(reportId: string, format: "zip" | "pdf"): Promise<Blob> {
    const token = await this.resolveToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(
      `${API_URL}/reports/${reportId}/download?format=${format}`,
      { headers }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Download failed" }));
      throw new Error(
        typeof error.detail === "string" ? error.detail : `HTTP ${response.status}`
      );
    }
    return response.blob();
  }

  // --- Knowledge Engine ---

  async listKnowledgeRepos(): Promise<KnowledgeRepo[]> {
    return this.request("/knowledge/repos");
  }

  async createKnowledgeRepo(body: KnowledgeRepoCreate): Promise<KnowledgeRepo> {
    return this.request("/knowledge/repos", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async connectAzure(body: {
    name: string;
    organization_url: string;
    pat: string;
  }): Promise<AzureConnection> {
    return this.request("/knowledge/azure/connect", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  async listAzureConnections(): Promise<AzureConnection[]> {
    return this.request("/knowledge/azure/connections");
  }

  async deleteAzureConnection(connectionId: string): Promise<void> {
    return this.request(`/knowledge/azure/connections/${connectionId}`, { method: "DELETE" });
  }

  async validateAzureConnection(connectionId: string): Promise<AzureConnection> {
    return this.request(`/knowledge/azure/connections/${connectionId}/validate`, { method: "POST" });
  }

  async listAzureProjects(connectionId: string): Promise<AzureProject[]> {
    return this.request(`/knowledge/azure/connections/${connectionId}/projects`);
  }

  async listAzureRepos(connectionId: string, project: string): Promise<AzureRepo[]> {
    return this.request(
      `/knowledge/azure/connections/${connectionId}/projects/${encodeURIComponent(project)}/repos`
    );
  }

  async listAzureBranches(
    connectionId: string,
    repoId: string,
    project: string
  ): Promise<{ branches: string[] }> {
    return this.request(
      `/knowledge/azure/connections/${connectionId}/repos/${repoId}/branches?project=${encodeURIComponent(project)}`
    );
  }

  async listRepoTree(repoId: string, path = ""): Promise<RepoFolderEntry[]> {
    const query = path ? `?path=${encodeURIComponent(path)}` : "";
    return this.request(`/knowledge/repos/${repoId}/tree${query}`);
  }

  async listRepoFiles(
    repoId: string,
    path = "",
    scopePath?: string
  ): Promise<RepoFileEntry[]> {
    const params = new URLSearchParams();
    if (path) params.set("path", path);
    if (scopePath) params.set("scope_path", scopePath);
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.request(`/knowledge/repos/${repoId}/files${query}`);
  }

  async getRepoFileContent(repoId: string, path: string): Promise<FileContentResponse> {
    return this.request(
      `/knowledge/repos/${repoId}/file-content?path=${encodeURIComponent(path)}`
    );
  }

  async discoverModules(repoId: string): Promise<DiscoveredModule[]> {
    return this.request(`/knowledge/repos/${repoId}/discover`);
  }

  async validateScope(repoId: string, path: string): Promise<ValidateScopeResponse> {
    return this.request(
      `/knowledge/repos/${repoId}/validate-scope?path=${encodeURIComponent(path)}`
    );
  }

  async deleteKnowledgeRepo(repoId: string): Promise<void> {
    return this.request(`/knowledge/repos/${repoId}`, { method: "DELETE" });
  }

  async deleteKnowledgeModule(moduleId: string): Promise<void> {
    return this.request(`/knowledge/modules/${moduleId}`, { method: "DELETE" });
  }

  async resetKnowledge(): Promise<{ repos_deleted: number; connections_deleted: number }> {
    return this.request("/knowledge/reset", { method: "POST" });
  }

  async uploadRepoZip(name: string, file: File): Promise<KnowledgeRepo> {
    const token = await this.resolveToken();
    const form = new FormData();
    form.append("name", name);
    form.append("file", file);
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(`${API_URL}/knowledge/repos/upload`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(typeof error.detail === "string" ? error.detail : "Upload failed");
    }
    return response.json();
  }

  async uploadRepoFolder(
    name: string,
    files: FileList,
    onProgress?: (percent: number) => void
  ): Promise<FolderUploadResult> {
    const { chunkFiles, prepareFolderUpload } = await import("./upload-folder");
    const { files: fileArr, paths } = prepareFolderUpload(files);
    if (fileArr.length === 0) {
      throw new Error("No files in folder. Select a folder with Salesforce code (LWC, Apex, etc.).");
    }

    const token = await this.resolveToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;

    const batches = chunkFiles(
      fileArr.map((file, i) => ({ file, path: paths[i] })),
      150
    );
    let sessionId: string | undefined;
    let result: FolderUploadResult | null = null;

    for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
      const batch = batches[batchIndex];
      const form = new FormData();
      if (!sessionId) {
        form.append("name", name);
      } else {
        form.append("session_id", sessionId);
      }
      const isLast = batchIndex === batches.length - 1;
      if (isLast) {
        form.append("finalize", "true");
      }
      form.append("relative_paths", JSON.stringify(batch.map((b) => b.path)));
      batch.forEach((b) => form.append("files", b.file, b.path));

      const response = await fetch(`${API_URL}/knowledge/repos/upload-folder`, {
        method: "POST",
        headers,
        body: form,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Upload failed" }));
        const detail = error.detail;
        const message = Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ")
          : typeof detail === "string"
            ? detail
            : "Upload failed";
        throw new Error(message || `Upload failed (${response.status})`);
      }

      const data = await response.json();
      if (isLast) {
        result = data as FolderUploadResult;
      } else {
        sessionId = data.session_id;
      }
      onProgress?.(Math.round(((batchIndex + 1) / batches.length) * 100));
    }

    if (!result) {
      throw new Error("Upload did not finalize");
    }
    return result;
  }

  async listKnowledgeModules(repoId: string): Promise<KnowledgeModule[]> {
    return this.request(`/knowledge/repos/${repoId}/modules`);
  }

  async createKnowledgeModule(
    repoId: string,
    name: string,
    scopePath?: string
  ): Promise<KnowledgeModule> {
    return this.request(`/knowledge/repos/${repoId}/modules`, {
      method: "POST",
      body: JSON.stringify({ name, scope_path: scopePath ?? null }),
    });
  }

  async startModuleScan(moduleId: string): Promise<{ status: string; module_id: string }> {
    return this.request(`/knowledge/modules/${moduleId}/scan`, { method: "POST" });
  }

  async *streamModuleScan(
    moduleId: string
  ): AsyncGenerator<{ event_type: string; message?: string; count?: number; stats?: Record<string, unknown> }> {
    const token = await this.resolveToken();
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(`${API_URL}/knowledge/modules/${moduleId}/scan/stream`, {
      headers,
    });
    if (!response.ok || !response.body) {
      throw new Error(`Scan stream failed: HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            yield JSON.parse(line.slice(6));
          } catch {
            // skip malformed
          }
        }
      }
    }
  }

  async getModuleStatus(moduleId: string): Promise<ModuleStatus> {
    return this.request(`/knowledge/modules/${moduleId}/status`);
  }

  async getModuleGraph(moduleId: string): Promise<KnowledgeGraph> {
    return this.request(`/knowledge/modules/${moduleId}/graph`);
  }

  async getRepoBrain(repoId: string): Promise<KnowledgeGraph> {
    return this.request(`/knowledge/repos/${repoId}/brain`);
  }

  async getBrainNode(nodeId: string): Promise<BrainNodeDetail> {
    return this.request(`/knowledge/nodes/${encodeURIComponent(nodeId)}`);
  }

  async getBrainConfig(): Promise<BrainConfig> {
    return this.request("/config/brain");
  }

  async patchBrainConfig(agent_mode: "single" | "multi"): Promise<BrainConfig> {
    return this.request("/config/brain", {
      method: "PATCH",
      body: JSON.stringify({ agent_mode }),
    });
  }

  async getExecutionRca(executionId: string) {
    return this.request(`/executions/${executionId}/rca`);
  }

  async getKnowledgeEntity(entityId: string): Promise<EntityDetail> {
    return this.request(`/knowledge/entities/${entityId}`);
  }

  async askKnowledge(moduleId: string, question: string): Promise<AskResponse> {
    return this.request("/knowledge/ask", {
      method: "POST",
      body: JSON.stringify({ module_id: moduleId, question }),
    });
  }

  async *askKnowledgeStream(
    moduleId: string,
    question: string
  ): AsyncGenerator<{ type: string; content?: string; citations?: AskCitation[]; message?: string }> {
    const token = await this.resolveToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(`${API_URL}/knowledge/ask/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ module_id: moduleId, question }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`Ask stream failed: HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            yield JSON.parse(line.slice(6));
          } catch {
            // skip malformed
          }
        }
      }
    }
  }
}

export const api = new ApiClient();
