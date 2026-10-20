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
  confirmed_structure: boolean;
  order_date_format: string | null;
  bank_date_format: string | null;
  order_transformations: Record<string, Record<string, unknown>>;
  bank_transformations: Record<string, Record<string, unknown>>;
  transformation_version: string;
  confirmed_ambiguities: string[];
  import_profile_id: string | null;
  import_profile_schema_version: string | null;
};

export type MappingSuggestion = {
  canonical_target: string;
  source_column: string | null;
  transformation: Record<string, unknown> | null;
  heuristic_score: number;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  reasons: string[];
  competitors: { source_column: string; heuristic_score: number; reasons: string[] }[];
  sample_before: string[];
  sample_after: string[];
  status: "auto-selected" | "needs-review" | "unsupported";
};

export type MappingAnalysis = {
  suggestions: MappingSuggestion[];
  selected_mapping: Record<string, string>;
  selected_transformations: Record<string, Record<string, unknown>>;
  required_total: number;
  required_auto_selected: number;
  required_needs_review: number;
  required_unsupported: number;
};

export type DetectedStructure = {
  status: "AUTO_SELECTED" | "NEEDS_REVIEW";
  reasons: string[];
  selected: {
    sheet_name: string | null;
    delimiter: string | null;
    header_row_number: number;
    header_depth: number;
    columns: string[];
  };
};

export type Inspection = {
  session_id: string;
  status: string;
  dataset_profile: string;
  raw_eda: { orders: RawEda; bank_transactions: RawEda };
  suggested_mapping: Pick<MappingState, "order_columns" | "bank_columns">;
  mapping_suggestions: { orders: MappingAnalysis; bank_transactions: MappingAnalysis };
  detected_structure: { orders: DetectedStructure; bank_transactions: DetectedStructure };
  import_profile: {
    schema_fingerprint: string;
    schema_version: string;
    recognized: Record<string, { key: string; name: string; status: string; reasons: string[] }>;
    saved_profile: { id: string; name: string; schema_version: string; mapping_snapshot: MappingState } | null;
    applied: boolean;
  };
  automatic_mapping?: MappingState | null;
  automation_reasons?: string[];
};

export type NormalizedPreview = {
  session_id: string;
  status: "READY" | "BLOCKED";
  orders: Record<string, unknown>[];
  bank_transactions: Record<string, unknown>[];
  issues: HealthIssue[];
  blocking_count: number;
  warning_count: number;
  standardized_eda: Record<string, number | string | null>;
  preview_limit: number;
};

export type ImportProfile = {
  id: string;
  name: string;
  schema_fingerprint: string;
  schema_version: string;
  schema_snapshot: Record<string, unknown>;
  mapping_snapshot: MappingState;
  created_at: string | null;
  updated_at: string | null;
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

export type HealthIssueDetail = {
  issue_index: number;
  code: string;
  severity: HealthIssue["severity"];
  feed: string;
  message_vi: string;
  sample_values: string[];
  suggested_action_vi: string;
  row_count: number;
  is_truncated: boolean;
  rows: {
    source_row_number: number;
    source_filename: string | null;
    sheet_name: string | null;
    source_row_hash: string | null;
    raw_values: Record<string, unknown>;
    normalized_values: Record<string, unknown> | null;
  }[];
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
  created_at: string;
  completed_at: string | null;
};

export type DashboardData = {
  run_id: string;
  effective_revision: number;
  kpis: Record<string, number | string | null | Record<string, number>>;
  layer_counts: Record<string, { confirmed_groups: number; proposed_groups: number }>;
  payment_status_counts: Record<string, number>;
  analytics: {
    review_status_counts: Record<string, number>;
    review_decision_counts: Record<string, number>;
    method_summary: {
      confirmed_groups: number;
      proposed_groups: number;
      total_relation_groups: number;
      confirmation_rate_percent: number;
      confirmation_rate_denominator: string;
    };
    confirmed_group_type_counts: Record<string, number>;
    exception_reason_counts: Record<string, number>;
    residual_distribution: {
      denominator_minor: number;
      order_outstanding: { bucket: string; count: number; amount_minor: number }[];
      bank_unapplied: { bucket: string; count: number; amount_minor: number }[];
    };
    confirmed_lag: {
      observation_unit: string;
      observations: number;
      median_days: number | null;
      buckets: { bucket: string; count: number }[];
    };
  };
  conservation: { is_valid: boolean; violations: string[] };
};

export type Paged<T> = {
  run_id: string;
  effective_revision: number;
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type GroupRow = {
  group_id: string;
  group_type: string;
  order_ids: string[];
  bank_txn_ids: string[];
  link_status: string;
  review_status?: string;
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
  posted_amount_minor: number;
  allocated_cash_minor: number;
  unapplied_minor: number;
  direction: string;
};

export type SourceTrace = {
  filename: string | null;
  sheet_name: string | null;
  row_number: number | null;
  row_hash: string | null;
  file_id: string | null;
  raw_values: Record<string, unknown>;
};

export type DetailOrder = Record<string, unknown> & {
  order_id: string;
  expected_amount_minor: number;
  source: SourceTrace;
};

export type DetailBankTransaction = Record<string, unknown> & {
  bank_txn_id: string;
  posted_amount_minor: number;
  source: SourceTrace;
};

export type AllocationRow = {
  edge_id: string;
  group_id: string;
  order_id: string;
  bank_txn_id: string;
  allocated_cash_minor: number;
  currency: string;
};

export type TransactionDetail = {
  entity_type: "order" | "bank" | "group" | "exception";
  entity_id: string;
  overview: {
    link_status: string;
    payment_statuses: Record<string, string>;
    relationship_types: string[];
    expected_amount_minor: number;
    posted_amount_minor: number;
    allocated_cash_minor: number;
    verified_adjustment_minor: number;
    outstanding_minor: number;
    unapplied_minor: number;
  };
  orders: DetailOrder[];
  bank_transactions: DetailBankTransaction[];
  groups: GroupRow[];
  allocations: AllocationRow[];
  adjustments: Record<string, unknown>[];
  candidates: Record<string, unknown>[];
  exceptions: ExceptionRow[];
  selected_exception: ExceptionRow | null;
  guidance_vi: string;
};

export type GroupDetail = GroupRow & {
  allocations: AllocationRow[];
  order_records: DetailOrder[];
  bank_transaction_records: DetailBankTransaction[];
  adjustments: Record<string, unknown>[];
  exceptions: ExceptionRow[];
  candidates: Record<string, unknown>[];
  totals: TransactionDetail["overview"];
};

export type ExplorerTotals = Record<"orders" | "bank" | "groups" | "exceptions", number>;

export type ReviewQueueItem = GroupRow & {
  review_status: string;
  order_records: {
    order_id: string;
    ordered_at: string;
    expected_amount_minor: number;
    external_ref: string | null;
  }[];
  bank_records: {
    bank_txn_id: string;
    txn_date: string;
    posted_amount_minor: number;
    direction: string;
    amount_basis: string;
    txn_ref: string | null;
  }[];
  proposed_allocations: AllocationRow[];
  proposed_cash_minor: number;
  competing_candidate_ids: string[];
  can_approve: boolean;
  conflict_code: string | null;
  conflict_message: string | null;
};

export type ReviewHistoryItem = {
  action_id: string;
  action_type: "APPROVE_GROUP" | "REJECT_GROUP" | "UNDO_ACTION";
  revision_before: number;
  revision_after: number;
  target_group_id: string | null;
  actor_label: string | null;
  actor_is_authenticated: false;
  note: string | null;
  undo_of_action_id: string | null;
  allocation_delta_minor: number;
  evidence: Record<string, unknown>;
  created_at: string;
};

export type ReviewPage<T> = Paged<T> & {
  run_id: string;
  effective_revision: number;
};

export type ReviewActionResult = {
  run_id: string;
  action_id: string;
  action_type: string;
  revision_before: number;
  effective_revision: number;
  effective_checksum: string;
  changed_group_ids: string[];
  allocation_delta_minor: number;
  kpis: Record<string, unknown>;
  conservation: { is_valid: boolean; violations: string[] };
  idempotent_replay: boolean;
};
