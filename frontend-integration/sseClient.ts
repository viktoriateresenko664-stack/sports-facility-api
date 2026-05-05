export type MobileSseEvent = {
  type:
    | "STREAM_READY"
    | "TASK_CREATED"
    | "TASK_ASSIGNED"
    | "TASK_STARTED"
    | "TASK_COMPLETED"
    | "TASK_CANCELLED"
    | "TASK_UPDATED"
    | "REPORT_READY";
  timestamp: string;
  task_id?: number;
  request_id?: number | null;
  facility_id?: number;
  assigned_engineer_id?: number;
  report_id?: number;
  engineer_id?: number;
  status?: string;
  previous_status?: string | null;
  source?: string;
};

type SseCallbacks = {
  onOpen?: () => void;
  onMessage?: (event: MobileSseEvent | Record<string, unknown>) => void;
  onError?: (event: Event) => void;
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

export function createMobileEventsSseClient(token: string, options: SseCallbacks = {}) {
  const apiBase = resolveApiBaseUrl();
  const url = `${apiBase}/bff/mobile/events/stream?token=${encodeURIComponent(token)}`;
  const source = new EventSource(url);

  source.onopen = () => {
    options.onOpen?.();
  };

  source.onerror = (event) => {
    options.onError?.(event);
  };

  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as MobileSseEvent | Record<string, unknown>;
      options.onMessage?.(payload);
    } catch {
      options.onMessage?.({ type: "unknown", raw: event.data });
    }
  };

  return {
    close() {
      source.close();
    },
  };
}

