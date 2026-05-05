export type SensorEvent = {
  type: "sensor_data";
  sensor_id: number;
  sensor_name: string;
  sensor_type: string;
  facility_id: number;
  equipment_id: number;
  value: number;
  measurement_unit: string;
  status: "NORMAL" | "WARNING" | "CRITICAL";
  alert_level: 0 | 1 | 2;
  timestamp: string;
};

export type TaskEvent = {
  type:
    | "TASK_CREATED"
    | "TASK_ASSIGNED"
    | "TASK_STARTED"
    | "TASK_COMPLETED"
    | "TASK_CANCELLED"
    | "TASK_UPDATED"
    | "REPORT_READY"
    | "STREAM_READY";
  task_id?: number;
  request_id?: number | null;
  facility_id?: number;
  assigned_engineer_id?: number;
  report_id?: number;
  engineer_id?: number;
  status?: string;
  source?: string;
  timestamp: string;
};

type WsCallbacks = {
  onOpen?: () => void;
  onMessage?: (event: SensorEvent | Record<string, unknown>) => void;
  onError?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
};

type WsOptions = WsCallbacks & {
  reconnectDelayMs?: number;
  maxReconnectAttempts?: number;
};

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

function resolveWsUrl(token: string): string {
  const apiBase = resolveApiBaseUrl();
  const wsBase = apiBase.replace(/^http:\/\//i, "ws://").replace(/^https:\/\//i, "wss://");
  const encodedToken = encodeURIComponent(token);
  return `${wsBase}/ws/sensors?token=${encodedToken}`;
}

function resolveTasksWsUrl(token: string): string {
  const apiBase = resolveApiBaseUrl();
  const wsBase = apiBase.replace(/^http:\/\//i, "ws://").replace(/^https:\/\//i, "wss://");
  const encodedToken = encodeURIComponent(token);
  return `${wsBase}/ws/tasks?token=${encodedToken}`;
}

export function createSensorsWsClient(token: string, options: WsOptions = {}) {
  const reconnectDelayMs = options.reconnectDelayMs ?? 2_000;
  const maxReconnectAttempts = options.maxReconnectAttempts ?? Infinity;

  let socket: WebSocket | null = null;
  let reconnectAttempts = 0;
  let closedManually = false;

  const connect = () => {
    socket = new WebSocket(resolveWsUrl(token));

    socket.onopen = () => {
      reconnectAttempts = 0;
      options.onOpen?.();
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as SensorEvent | Record<string, unknown>;
        options.onMessage?.(payload);
      } catch {
        options.onMessage?.({ type: "unknown", raw: event.data });
      }
    };

    socket.onerror = (event) => {
      options.onError?.(event);
    };

    socket.onclose = (event) => {
      options.onClose?.(event);
      if (closedManually) {
        return;
      }
      if (reconnectAttempts >= maxReconnectAttempts) {
        return;
      }
      reconnectAttempts += 1;
      window.setTimeout(connect, reconnectDelayMs);
    };
  };

  connect();

  return {
    send(payload: unknown) {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(payload));
      }
    },
    close() {
      closedManually = true;
      socket?.close();
    },
  };
}

export function createTasksWsClient(token: string, options: WsOptions = {}) {
  const reconnectDelayMs = options.reconnectDelayMs ?? 2_000;
  const maxReconnectAttempts = options.maxReconnectAttempts ?? Infinity;

  let socket: WebSocket | null = null;
  let reconnectAttempts = 0;
  let closedManually = false;

  const connect = () => {
    socket = new WebSocket(resolveTasksWsUrl(token));

    socket.onopen = () => {
      reconnectAttempts = 0;
      options.onOpen?.();
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as TaskEvent | Record<string, unknown>;
        options.onMessage?.(payload);
      } catch {
        options.onMessage?.({ type: "unknown", raw: event.data });
      }
    };

    socket.onerror = (event) => {
      options.onError?.(event);
    };

    socket.onclose = (event) => {
      options.onClose?.(event);
      if (closedManually) {
        return;
      }
      if (reconnectAttempts >= maxReconnectAttempts) {
        return;
      }
      reconnectAttempts += 1;
      window.setTimeout(connect, reconnectDelayMs);
    };
  };

  connect();

  return {
    send(payload: unknown) {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(payload));
      }
    },
    close() {
      closedManually = true;
      socket?.close();
    },
  };
}

export function handleSensorEventExample(event: SensorEvent | Record<string, unknown>) {
  if (event.type !== "sensor_data") {
    return;
  }
  const typed = event as SensorEvent;
  if (typed.alert_level >= 2) {
    console.warn(`[CRITICAL] ${typed.sensor_name}: ${typed.value}${typed.measurement_unit}`);
    return;
  }
  if (typed.alert_level === 1) {
    console.info(`[WARNING] ${typed.sensor_name}: ${typed.value}${typed.measurement_unit}`);
    return;
  }
  console.log(`[NORMAL] ${typed.sensor_name}: ${typed.value}${typed.measurement_unit}`);
}
