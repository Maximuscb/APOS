/* Shared TypeScript types for all report API responses */

export interface ReportFiltersState {
  storeId: string;
  includeChildren: boolean;
  startDate: string;
  endDate: string;
}

/* ── Sales & Revenue ─────────────────────────────────── */

export interface SalesSummary {
  store_ids: number[];
  start: string | null;
  end: string | null;
  gross_sales_cents: number;
  net_sales_cents: number;
  return_total_cents: number;
  tax_collected_cents: number;
  discount_total_cents: number;
  transaction_count: number;
  items_sold: number;
  avg_ticket_cents: number;
  payment_breakdown: { tender_type: string; total_cents: number; count: number }[];
}

export interface SalesByTimeRow {
  period: string;
  sales_count: number;
  gross_sales_cents: number;
  items_sold: number;
}

export interface SalesByTimeReport {
  store_ids: number[];
  mode: string;
  rows: SalesByTimeRow[];
}

export interface SalesByProductRow {
  product_id: number;
  sku: string;
  name: string;
  revenue_cents: number;
  units_sold: number;
  share_pct: number;
  cumulative_pct: number;
  category: string;
}

export interface SalesByEmployeeRow {
  user_id: number;
  username: string;
  sales_count: number;
  gross_sales_cents: number;
  avg_ticket_cents: number;
  refund_count: number;
  discount_total_cents: number;
}

export interface SalesByStoreRow {
  store_id: number;
  store_name: string;
  gross_sales_cents: number;
  cogs_cents: number;
  margin_cents: number;
  margin_pct: number | null;
  transaction_count: number;
}

/* ── Profitability ───────────────────────────────────── */

export interface MarginReport {
  store_ids: number[];
  revenue_cents: number;
  cogs_cents: number;
  margin_cents: number;
  margin_pct: number | null;
}

export interface MarginOutlierRow {
  product_id: number;
  sku: string;
  name: string;
  store_id: number;
  price_cents: number;
  cost_cents: number | null;
  margin_pct: number | null;
  issue: string;
}

export interface DiscountImpactReport {
  store_ids: number[];
  total_discount_cents: number;
  total_lines_discounted: number;
  margin_erosion_cents: number;
  by_employee: { user_id: number; username: string; discount_count: number; discount_total_cents: number }[];
}

/* ── Inventory ───────────────────────────────────────── */

export interface InventoryValuationRow {
  store_id: number;
  product_id: number;
  sku: string;
  name: string;
  quantity_on_hand: number;
  weighted_average_cost_cents: number | null;
  inventory_value_cents: number | null;
}

export interface LowStockRow {
  store_id: number;
  product_id: number;
  sku: string;
  name: string;
  quantity_on_hand: number;
}

export interface ShrinkageReport {
  store_ids: number[];
  total_counts: number;
  total_variance_units: number;
  total_variance_cost_cents: number;
  counts: {
    count_id: number;
    document_number: string;
    store_id: number;
    posted_at: string | null;
    variance_units: number;
    variance_cost_cents: number;
  }[];
}

export interface InventoryMovementRow {
  type: string;
  total_units: number;
  total_cost_cents: number;
}

/* ── Vendor & Purchasing ─────────────────────────────── */

export interface VendorSpendRow {
  vendor_id: number;
  vendor_name: string;
  total_documents: number;
  total_line_items: number;
  total_spend_cents: number;
}

export interface CostChangeRow {
  product_id: number;
  sku: string;
  name: string;
  occurred_at: string;
  unit_cost_cents: number;
  vendor_name: string;
}

/* ── Cash & Register ─────────────────────────────────── */

export interface RegisterReconRow {
  session_id: number;
  register_name: string;
  username: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash_cents: number;
  closing_cash_cents: number | null;
  expected_cash_cents: number | null;
  variance_cents: number | null;
}

export interface PaymentBreakdownRow {
  tender_type: string;
  count: number;
  total_cents: number;
  pct_of_total: number;
}

export interface OverShortReport {
  store_ids: number[];
  total_sessions: number;
  total_variance_cents: number;
  avg_variance_cents: number;
  sessions_over: number;
  sessions_short: number;
  sessions_exact: number;
  rows: RegisterReconRow[];
}

/* ── Workforce ───────────────────────────────────────── */

export interface LaborHoursRow {
  user_id: number;
  username: string;
  total_entries: number;
  total_worked_minutes: number;
  total_break_minutes: number;
  net_worked_minutes: number;
  overtime_flag: boolean;
  missed_punches: number;
}

export interface LaborVsSalesReport {
  store_ids: number[];
  total_labor_minutes: number;
  total_revenue_cents: number;
  revenue_per_labor_hour_cents: number;
}

export interface EmployeePerformanceRow {
  user_id: number;
  username: string;
  sales_count: number;
  gross_sales_cents: number;
  avg_ticket_cents: number;
  discount_count: number;
  discount_total_cents: number;
  refund_count: number;
  refund_total_cents: number;
}

/* ── Customer & Rewards ──────────────────────────────── */

export interface CustomerCLVRow {
  customer_id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  total_spent_cents: number;
  total_visits: number;
  avg_basket_cents: number;
  last_visit_at: string | null;
}

export interface RetentionReport {
  store_ids: number[];
  total_customers: number;
  repeat_customers: number;
  repeat_pct: number;
}

export interface RewardsLiabilityReport {
  store_ids: number[];
  total_accounts: number;
  outstanding_points: number;
  lifetime_earned: number;
  lifetime_redeemed: number;
  redemption_rate_pct: number;
}

/* ── Risk / Compliance ───────────────────────────────── */

export interface RefundAuditRow {
  id: number;
  document_number: string | null;
  store_id: number;
  refund_amount_cents: number;
  created_by_user_id: number;
  username: string;
  created_at: string;
  reason: string | null;
}

export interface PriceOverrideRow {
  sale_line_id: number;
  sale_document_number: string;
  store_id: number;
  product_name: string;
  original_price_cents: number;
  unit_price_cents: number;
  discount_cents: number;
  discount_reason: string | null;
  username: string;
  approved_by_username: string | null;
  created_at: string;
}

export interface VoidAuditRow {
  id: number;
  document_number: string;
  store_id: number;
  original_amount_cents: number;
  voided_by_username: string;
  voided_at: string;
  void_reason: string | null;
}

export interface SuspiciousActivityItem {
  category: string;
  description: string;
  count: number;
  user_id: number | null;
  username: string | null;
  details: string;
}
