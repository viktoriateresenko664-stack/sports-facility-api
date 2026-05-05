import { getJob } from "./apiClient";

type PollEndpointOptions<T> = {
  intervalMs?: number;
  timeoutMs?: number;
  stopCondition: (result: T) => boolean;
};

export async function pollEndpoint<T>(
  fn: () => Promise<T>,
  options: PollEndpointOptions<T>
): Promise<T> {
  const intervalMs = options.intervalMs ?? 2_000;
  const timeoutMs = options.timeoutMs ?? 60_000;
  const startedAt = Date.now();

  while (true) {
    const result = await fn();
    if (options.stopCondition(result)) {
      return result;
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error("Polling timeout reached");
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export async function pollJob(
  jobId: string,
  options: { intervalMs?: number; timeoutMs?: number } = {}
) {
  return pollEndpoint(
    () => getJob(jobId),
    {
      intervalMs: options.intervalMs ?? 2_000,
      timeoutMs: options.timeoutMs ?? 120_000,
      stopCondition: (job: any) => {
        const status = String(job?.status ?? "");
        return status === "SUCCESS" || status === "FAILED";
      },
    }
  );
}

