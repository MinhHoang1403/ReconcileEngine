import type {
  DashboardData,
  BankRow,
  ExceptionRow,
  GroupRow,
  HealthResponse,
  Inspection,
  MappingState,
  OrderRow,
  Paged,
  RunCreated,
  RunDetail,
} from "../types";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `Yêu cầu thất bại (${response.status})`;
    try {
      const body = (await response.json()) as {
        detail?: string | { message?: string; error_code?: string };
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
      else if (body.detail?.error_code) message = body.detail.error_code;
    } catch {
      // Keep the status-based message for non-JSON server failures.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const jsonHeaders = { "Content-Type": "application/json" };

export const api = {
  createDemo: () => requestJson<Inspection>("/api/demo/datasets", { method: "POST" }),
  inspectFiles: (orders: File, bank: File) => {
    const body = new FormData();
    body.append("orders_file", orders);
    body.append("bank_file", bank);
    return requestJson<Inspection>("/api/uploads/inspect", { method: "POST", body });
  },
  confirmMapping: (sessionId: string, mapping: MappingState) =>
    requestJson<HealthResponse>(`/api/uploads/${sessionId}/mapping`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(mapping),
    }),
  resolveHealth: (
    sessionId: string,
    exclusions: { feed: string; source_row_number: number; reason: string }[],
    acknowledgedIssueCodes: string[],
  ) =>
    requestJson<HealthResponse>(`/api/uploads/${sessionId}/resolutions`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ exclusions, acknowledged_issue_codes: acknowledgedIssueCodes }),
    }),
  createRun: (sessionId: string, currency: "VND" | "BRL") =>
    requestJson<RunCreated>("/api/runs", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        upload_session_id: sessionId,
        policy: {
          currency,
          max_days_diff: 3,
          fuzzy_candidate_threshold: 85,
          max_candidates_per_item: 5,
          max_group_orders: 3,
          max_split_bank_rows: 3,
          max_group_block_size: 20,
          max_combinations_per_case: 2000,
          allow_verified_psp_fees: true,
        },
      }),
    }),
  dashboard: (runId: string) => requestJson<DashboardData>(`/api/runs/${runId}/dashboard`),
  run: (runId: string) => requestJson<RunDetail>(`/api/runs/${runId}`),
  groups: (runId: string) => requestJson<Paged<GroupRow>>(`/api/runs/${runId}/groups?page_size=100`),
  exceptions: (runId: string) =>
    requestJson<Paged<ExceptionRow>>(`/api/runs/${runId}/exceptions?page_size=100`),
  orders: (runId: string) => requestJson<Paged<OrderRow>>(`/api/runs/${runId}/orders?page_size=100`),
  bankTransactions: (runId: string) =>
    requestJson<Paged<BankRow>>(`/api/runs/${runId}/bank-transactions?page_size=100`),
};
