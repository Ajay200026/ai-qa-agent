import type {
  DashboardStats,
  Execution,
  Project,
  Report,
  SalesforceOrg,
  Scenario,
  User,
} from "./types";
import type {
  WorkflowPreviewRequest,
  WorkflowPreviewResponse,
  WorkflowTemplate,
  WorkflowTemplateSummary,
} from "./workflow-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
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
      throw new Error(message || `HTTP ${response.status}`);
    }

    if (response.status === 204) return {} as T;
    return response.json();
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
    access_token?: string;
    instance_url?: string;
  }): Promise<SalesforceOrg> {
    return this.request("/salesforce/orgs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async validateOrg(orgId: string): Promise<{ valid: boolean; message: string }> {
    return this.request(`/salesforce/orgs/${orgId}/validate`, { method: "POST" });
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

  async rerunExecution(id: string): Promise<Execution> {
    return this.request(`/executions/${id}/rerun`, { method: "POST" });
  }

  async stopExecution(id: string): Promise<Execution> {
    return this.request(`/executions/${id}/stop`, { method: "POST" });
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
    return `${API_URL}/reports/artifacts/${executionId}/${filename}`;
  }
}

export const api = new ApiClient();
