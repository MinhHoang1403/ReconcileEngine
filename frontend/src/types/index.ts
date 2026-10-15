export type RawEda = {
  row_count: number;
  column_count: number;
  columns: string[];
  missing_by_column: Record<string, number>;
  duplicate_rows: number;
  sample_rows: Record<string, unknown>[];
  confidence: string;
};

export type MappingState = {
  order_columns: Record<string, string>;
  bank_columns: Record<string, string>;
  currency: "VND" | "BRL";
  source_profile: string;
  date_format: string;
  decimal_separator: string;
  thousand_separator: string | null;
  order_defaults: Record<string, string>;
  bank_defaults: Record<string, string>;
};

export type Inspection = {
  session_id: string;
  status: string;
  dataset_profile: string;
  raw_eda: { orders: RawEda; bank_transactions: RawEda };
  suggested_mapping: Pick<MappingState, "order_columns" | "bank_columns">;
};

export type HealthIssue = {
  code: string;
  severity: "BLOCKING" | "WARNING" | "INFO";
  feed: string;
  message_vi: string;
  source_rows: number[];
  sample_values: string[];
};

export type HealthResponse = {
  session_id: string;
  status: string;
  report: {
    status: "READY" | "BLOCKED";
    blocking_count: number;
    warning_count: number;
    info_count: number;
    issues: HealthIssue[];
  };
  standardized_eda: Record<string, number | string | null>;
  exclusions: { feed: string; source_row_number: number; reason: string }[];
  acknowledged_issue_codes: string[];
};

export type RunCreated = {
  run_id: string;
  status: string;
  effective_revision: number;
  semantic_checksum: string;
};

export type RunDetail = RunCreated & {
  upload_session_id: string;
  currency: string;
};

export type DashboardData = {
  run_id: string;
  effective_revision: number;
  kpis: Record<string, number | string | null | Record<string, number>>;
  layer_counts: Record<string, { confirmed_groups: number; proposed_groups: number }>;
  payment_status_counts: Record<string, number>;
  conservation: { is_valid: boolean; violations: string[] };
};

export type Paged<T> = { items: T[]; page: number; page_size: number; total: number };

export type GroupRow = {
  group_id: string;
  group_type: string;
  order_ids: string[];
  bank_txn_ids: string[];
  link_status: string;
  payment_statuses: Record<string, string>;
  evidence: { rule_id: string; explanation_vi: string; reason_codes: string[] };
};

export type ExceptionRow = {
  exception_id: string;
  reason_codes: string[];
  order_ids: string[];
  bank_txn_ids: string[];
  risk_amount_minor: number;
};

export type OrderRow = {
  order_id: string;
  expected_amount_minor: number;
  allocated_cash_minor: number;
  outstanding_minor: number;
  payment_status: string;
};

export type BankRow = {
  bank_txn_id: string;
  amount_minor: number;
  allocated_cash_minor: number;
  unapplied_minor: number;
  direction: string;
};
