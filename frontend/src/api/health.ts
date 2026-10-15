export type HealthStatus = {
  status: string;
  database: string;
};

export async function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  const response = await fetch("/healthz", { signal });
  if (!response.ok) {
    throw new Error("Backend chưa sẵn sàng");
  }
  return response.json() as Promise<HealthStatus>;
}

