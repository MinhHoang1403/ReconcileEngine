import type {
  DashboardData,
  BankRow,
  ExceptionRow,
  GroupRow,
  HealthResponse,
  HealthIssueDetail,
  GroupDetail,
  Inspection,
  MappingState,
  OrderRow,
  Paged,
  RunCreated,
  RunDetail,
  ReviewActionResult,
  ReviewHistoryItem,
  ReviewPage,
  ReviewQueueItem,
  TransactionDetail,
} from "../types";

export class ApiError extends Error {
  status: number;
  code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `Yêu cầu thất bại (${response.status})`;
    let code: string | null = null;
    try {
      const body = (await response.json()) as {
        detail?: string | { message?: string; error_code?: string };
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
      else if (body.detail?.error_code) message = body.detail.error_code;
      if (typeof body.detail === "object" && body.detail?.error_code) code = body.detail.error_code;
    } catch {
      // Keep the status-based message for non-JSON server failures.
    }
    throw new ApiError(message, response.status, code);
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
  healthIssueDetail: (sessionId: string, issueIndex: number) =>
    requestJson<HealthIssueDetail>(`/api/uploads/${sessionId}/health/issues/${issueIndex}`),
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
  dashboard: (runId: string, revision?: number) => requestJson<DashboardData>(`/api/runs/${runId}/dashboard${revision === undefined ? "" : `?revision=${revision}`}`),
  run: (runId: string) => requestJson<RunDetail>(`/api/runs/${runId}`),
  groups: (runId: string, page = 1, pageSize = 50, revision?: number) =>
    requestJson<Paged<GroupRow>>(`/api/runs/${runId}/groups?page=${page}&page_size=${pageSize}${revision === undefined ? "" : `&revision=${revision}`}`),
  exceptions: (runId: string, page = 1, pageSize = 50, revision?: number) =>
    requestJson<Paged<ExceptionRow>>(`/api/runs/${runId}/exceptions?page=${page}&page_size=${pageSize}${revision === undefined ? "" : `&revision=${revision}`}`),
  orders: (runId: string, page = 1, pageSize = 50, revision?: number) =>
    requestJson<Paged<OrderRow>>(`/api/runs/${runId}/orders?page=${page}&page_size=${pageSize}${revision === undefined ? "" : `&revision=${revision}`}`),
  bankTransactions: (runId: string, page = 1, pageSize = 50, revision?: number) =>
    requestJson<Paged<BankRow>>(`/api/runs/${runId}/bank-transactions?page=${page}&page_size=${pageSize}${revision === undefined ? "" : `&revision=${revision}`}`),
  orderDetail: (runId: string, orderId: string, revision?: number) =>
    requestJson<TransactionDetail>(`/api/runs/${runId}/orders/${encodeURIComponent(orderId)}${revision === undefined ? "" : `?revision=${revision}`}`),
  bankTransactionDetail: (runId: string, bankTxnId: string, revision?: number) =>
    requestJson<TransactionDetail>(`/api/runs/${runId}/bank-transactions/${encodeURIComponent(bankTxnId)}${revision === undefined ? "" : `?revision=${revision}`}`),
  exceptionDetail: (runId: string, exceptionId: string, revision?: number) =>
    requestJson<TransactionDetail>(`/api/runs/${runId}/exceptions/${encodeURIComponent(exceptionId)}${revision === undefined ? "" : `?revision=${revision}`}`),
  groupDetail: (runId: string, groupId: string, revision?: number) =>
    requestJson<GroupDetail>(`/api/runs/${runId}/groups/${encodeURIComponent(groupId)}${revision === undefined ? "" : `?revision=${revision}`}`),
  reviews: (runId: string, page = 1, pageSize = 20, query = "", groupType = "") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (query) params.set("query", query);
    if (groupType) params.set("group_type", groupType);
    return requestJson<ReviewPage<ReviewQueueItem>>(`/api/runs/${runId}/reviews?${params}`);
  },
  reviewHistory: (runId: string, page = 1, pageSize = 20) =>
    requestJson<ReviewPage<ReviewHistoryItem>>(
      `/api/runs/${runId}/reviews/history?page=${page}&page_size=${pageSize}`,
    ),
  approveReview: (
    runId: string,
    command: { group_id: string; expected_revision: number; idempotency_key: string; actor_label?: string; note: string },
  ) => requestJson<ReviewActionResult>(`/api/runs/${runId}/reviews/approve`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(command),
  }),
  rejectReview: (
    runId: string,
    command: { group_id: string; expected_revision: number; idempotency_key: string; actor_label?: string; note: string },
  ) => requestJson<ReviewActionResult>(`/api/runs/${runId}/reviews/reject`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(command),
  }),
  undoReview: (
    runId: string,
    command: { action_id: string; expected_revision: number; idempotency_key: string; actor_label?: string; note?: string },
  ) => requestJson<ReviewActionResult>(`/api/runs/${runId}/reviews/undo`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(command),
  }),
};
