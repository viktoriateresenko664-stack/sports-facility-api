type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API request failed: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

declare global {
  interface Window {
    __API_URL__?: string;
  }
}

function resolveApiBaseUrl(): string {
  const viteUrl =
    typeof import.meta !== "undefined" &&
    (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env?.VITE_API_URL;
  const windowUrl = typeof window !== "undefined" ? window.__API_URL__ : undefined;
  const baseUrl = (viteUrl ?? windowUrl ?? "").trim().replace(/\/+$/, "");
  if (!baseUrl) {
    throw new Error("API base URL is empty. Set VITE_API_URL or window.__API_URL__.");
  }
  return baseUrl;
}

function getToken(): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  return localStorage.getItem("access_token") ?? localStorage.getItem("token");
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text || null;
}

async function request<TResponse>(
  method: HttpMethod,
  path: string,
  body?: unknown
): Promise<TResponse> {
  const url = `${resolveApiBaseUrl()}${path}`;
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const parsed = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, parsed);
  }
  return parsed as TResponse;
}

async function requestBlob(path: string): Promise<Blob> {
  const url = `${resolveApiBaseUrl()}${path}`;
  const token = getToken();

  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    const parsed = await parseBody(response);
    throw new ApiError(response.status, parsed);
  }
  return response.blob();
}

export function registerUser(data: {
  username: string;
  email: string;
  password: string;
  phone?: string;
}) {
  return request("POST", "/auth/register", data);
}

export function loginUser(email: string, password: string) {
  return request<{ access_token: string; token_type: string; expires_in: number }>("POST", "/auth/login", {
    email,
    password,
  });
}

export function loginEmployee(employee_key: string, password: string) {
  return request<{ access_token: string; token_type: string; expires_in: number }>(
    "POST",
    "/auth/employee-login",
    { employee_key, password }
  );
}

export function changeCurrentPassword(data: {
  current_password: string;
  new_password: string;
  new_password_confirm: string;
}) {
  return request<{ changed: boolean; revoked_refresh_tokens: number; message: string }>(
    "POST",
    "/auth/change-password",
    data
  );
}

export function getMe() {
  return request("GET", "/auth/me");
}

export function updateMyProfile(data: { username?: string; email?: string; phone?: string | null }) {
  return request("PATCH", "/auth/me", data);
}

export function createUserRequest(data: { facility_id: number; title: string; description: string }) {
  return request("POST", "/user-requests", data);
}

export function getMyRequests() {
  return request("GET", "/user-requests/my");
}

export function getEngineerTasks(params?: {
  status?: string;
  facility_id?: number;
  assigned_engineer?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.facility_id !== undefined) query.set("facility_id", String(params.facility_id));
  if (params?.assigned_engineer !== undefined) query.set("assigned_engineer", String(params.assigned_engineer));
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.page !== undefined) query.set("page", String(params.page));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request("GET", `/engineer-tasks${suffix}`);
}

export function getEngineerTask(taskId: number) {
  return request("GET", `/engineer-tasks/${taskId}`);
}

export function createEngineerTask(data: {
  facility_id: number;
  request_id?: number | null;
  assigned_engineer_id?: number | null;
  description: string;
  operator_comment?: string | null;
}) {
  return request("POST", "/engineer-tasks", data);
}

export function startEngineerTask(taskId: number) {
  return request("POST", `/engineer-tasks/${taskId}/start`);
}

export function finishEngineerTask(taskId: number) {
  return request("POST", `/engineer-tasks/${taskId}/finish`);
}

export function cancelEngineerTask(taskId: number) {
  return request("POST", `/engineer-tasks/${taskId}/cancel`);
}

export function generateReport(data: { task_id: number; notes?: string | null }) {
  return request("POST", "/reports/generate", data);
}

export function generateReportDelayed(data: { task_id: number; delay_seconds: number; notes?: string | null }) {
  return request("POST", "/reports/generate-delayed", data);
}

export async function uploadEngineerReportFile(data: {
  task_id: number;
  file: File;
  notes?: string | null;
  idempotency_key?: string;
}) {
  const url = `${resolveApiBaseUrl()}/reports/upload`;
  const token = getToken();
  const formData = new FormData();
  formData.append("task_id", String(data.task_id));
  formData.append("report_file", data.file);
  if (data.notes) {
    formData.append("notes", data.notes);
  }

  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
  };
  const generatedKey =
    data.idempotency_key ??
    (typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`);
  headers["Idempotency-Key"] = generatedKey;
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });
  const parsed = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, parsed);
  }
  return parsed;
}

export function getMyReports(params?: {
  engineer_id?: number;
  assigned_engineer?: number;
  status?: string;
  facility_id?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.engineer_id !== undefined) query.set("engineer_id", String(params.engineer_id));
  if (params?.assigned_engineer !== undefined) query.set("assigned_engineer", String(params.assigned_engineer));
  if (params?.status) query.set("status", params.status);
  if (params?.facility_id !== undefined) query.set("facility_id", String(params.facility_id));
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.page !== undefined) query.set("page", String(params.page));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request("GET", `/reports/my${suffix}`);
}

export function seedSampleReports(data: { task_ids?: number[]; overwrite_existing?: boolean }) {
  return request("POST", "/reports/seed-samples", data);
}

export function downloadReportTemplate() {
  return requestBlob("/reports/template");
}

export function downloadEngineerReportFile(reportId: number) {
  return requestBlob(`/reports/${reportId}/download`);
}

export function getJob(jobId: string) {
  return request("GET", `/jobs/${jobId}`);
}

export function getWebDashboard() {
  return request("GET", "/bff/web/dashboard");
}

export function getWebFacilitiesMap(onlyWithCoordinates = true) {
  const suffix = `?only_with_coordinates=${onlyWithCoordinates ? "true" : "false"}`;
  return request<{
    items: Array<{
      facility_id: number;
      name: string;
      facility_type: string;
      address: string;
      status: string;
      latitude: number | null;
      longitude: number | null;
    }>;
  }>("GET", `/bff/web/facilities-map${suffix}`);
}

export function getMobileTasks() {
  return request<{
    total?: number;
    active?: number;
    completed?: number;
    created?: number;
    cancelled?: number;
    summary?: {
      total: number;
      active: number;
      completed: number;
      created: number;
      cancelled: number;
    };
    tasks?: Array<{
      task_id: number;
      request_id: number | null;
      facility_id: number;
      facility_name: string;
      facility_address: string;
      description: string;
      operator_comment: string | null;
      status: string;
      status_label: string;
      created_at: string;
      started_at: string | null;
      completed_at: string | null;
    }>;
  }>("GET", "/bff/mobile/tasks");
}

export function getDesktopMonitoring() {
  return request("GET", "/bff/desktop/monitoring");
}

export function getDesktopLogs(params?: {
  status?: "SUCCESS" | "FAILED";
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.page !== undefined) query.set("page", String(params.page));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<
    | Array<{
        id: number;
        user: string;
        role: string;
        action: string;
        object: string;
        date: string;
        status: string;
      }>
    | {
        items: Array<{
          id: number;
          user: string;
          role: string;
          action: string;
          object: string;
          date: string;
          status: string;
        }>;
        page: number;
        limit: number;
        total: number;
      }
  >("GET", `/bff/desktop/logs${suffix}`);
}

export function getDesktopRequests(params?: {
  status?: string;
  facility_id?: number;
  assigned_engineer?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.facility_id !== undefined) query.set("facility_id", String(params.facility_id));
  if (params?.assigned_engineer !== undefined) query.set("assigned_engineer", String(params.assigned_engineer));
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.page !== undefined) query.set("page", String(params.page));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<
    | Array<{
        id: number;
        facility: string;
        description: string;
        date: string;
        status: string;
        engineer: string;
      }>
    | {
        items: Array<{
          id: number;
          facility: string;
          description: string;
          date: string;
          status: string;
          engineer: string;
        }>;
        page: number;
        limit: number;
        total: number;
      }
  >("GET", `/bff/desktop/requests${suffix}`);
}

export function getDesktopReports(params?: {
  facility_id?: number;
  engineer_id?: number;
  source?: "uploaded_file" | "generated_text";
  created_from?: string;
  created_to?: string;
  page?: number;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.facility_id !== undefined) query.set("facility_id", String(params.facility_id));
  if (params?.engineer_id !== undefined) query.set("engineer_id", String(params.engineer_id));
  if (params?.source) query.set("source", params.source);
  if (params?.created_from) query.set("created_from", params.created_from);
  if (params?.created_to) query.set("created_to", params.created_to);
  if (params?.page !== undefined) query.set("page", String(params.page));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request("GET", `/bff/desktop/reports${suffix}`);
}

export function getDesktopReportDetail(reportId: number) {
  return request("GET", `/bff/desktop/reports/${reportId}`);
}

export function previewEngineerReportFile(reportId: number) {
  return requestBlob(`/reports/${reportId}/preview`);
}
