import {
  cancelEngineerTask,
  createEngineerTask,
  createUserRequest,
  finishEngineerTask,
  generateReport,
  getMobileTasks,
  getMe,
  loginEmployee,
  loginUser,
  startEngineerTask,
} from "./apiClient";
import { pollJob } from "./polling";
import { createSensorsWsClient, handleSensorEventExample } from "./wsClient";

export async function exampleLoginUser() {
  const tokenResponse = await loginUser("user1@test.com", "UserPass123!");
  localStorage.setItem("access_token", tokenResponse.access_token);
  return tokenResponse;
}

export async function exampleLoginEmployee() {
  const tokenResponse = await loginEmployee("ENG001", "EmpPass123!");
  localStorage.setItem("access_token", tokenResponse.access_token);
  return tokenResponse;
}

export async function exampleGetAuthMe() {
  return getMe();
}

export async function exampleCreateRequest() {
  return createUserRequest({
    facility_id: 1,
    title: "Need maintenance",
    description: "Temperature jumps above normal range.",
  });
}

export async function exampleCreateEngineerTask() {
  return createEngineerTask({
    facility_id: 1,
    description: "Inspect temperature sensor and wiring",
    operator_comment: "Created from desktop dashboard",
  });
}

export async function exampleTaskLifecycle(taskId: number) {
  const started = await startEngineerTask(taskId);
  const finished = await finishEngineerTask(taskId);
  const canceled = await cancelEngineerTask(taskId);
  return { started, finished, canceled };
}

export async function exampleGenerateReportWithPolling(taskId: number) {
  const job = await generateReport({ task_id: taskId, notes: "Auto-generated from frontend example" });
  return pollJob(job.job_id);
}

export async function exampleMobileTasksListWithFallback() {
  const response = await getMobileTasks();
  const tasks = Array.isArray(response.tasks) ? response.tasks : [];

  // Backward-compatible fallback when backend returns only legacy counters.
  if (!response.tasks) {
    return {
      total: response.total ?? response.summary?.total ?? 0,
      active: response.active ?? response.summary?.active ?? 0,
      completed: response.completed ?? response.summary?.completed ?? 0,
      created: response.created ?? response.summary?.created ?? 0,
      cancelled: response.cancelled ?? response.summary?.cancelled ?? 0,
      tasks: [],
    };
  }

  return {
    total: response.total ?? response.summary?.total ?? tasks.length,
    active: response.active ?? response.summary?.active ?? 0,
    completed: response.completed ?? response.summary?.completed ?? 0,
    created: response.created ?? response.summary?.created ?? 0,
    cancelled: response.cancelled ?? response.summary?.cancelled ?? 0,
    tasks,
  };
}

export function exampleConnectSensorsWs() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw new Error("No token in localStorage");
  }

  const ws = createSensorsWsClient(token, {
    onOpen: () => console.log("WS connected: /ws/sensors"),
    onMessage: (event) => handleSensorEventExample(event),
    onError: (error) => console.error("WS error", error),
    onClose: (event) => console.log("WS closed", event.code, event.reason),
  });

  return ws;
}
