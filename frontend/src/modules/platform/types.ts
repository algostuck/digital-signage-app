/** Contracts for the Platform Console (Super Admin). Mirrors
 * `app/api/v1/platform.py` and `app/schemas/saas.py`. */

export interface TenantRow {
  id: string;
  name: string;
  code: string;
  status: string;
  plan_code: string | null;
  plan_name: string | null;
  subscription_status: string | null;
  devices: number;
  users: number;
  created_at: string | null;
}

export interface TenantDetail extends TenantRow {
  timezone: string;
  locale: string;
  region: string;
  quotas: Record<string, number>;
}

export interface EntitlementRow {
  key: string;
  int_value: number | null;
  bool_value: boolean | null;
}

export interface PlanRow {
  id?: string;
  code: string;
  name: string;
  description: string | null;
  prices: Record<string, { amount: number; currency: string }>;
  is_active: boolean;
  sort_order: number;
  entitlements: EntitlementRow[];
}

export interface SubscriptionOut {
  id: string;
  plan: { code: string; name: string };
  status: string;
  billing_cycle: string;
  start_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end_at: string | null;
  cancel_at: string | null;
  cancelled_at: string | null;
  provider: string;
  items: EntitlementRow[];
}

export interface TenantSubscription {
  subscription: SubscriptionOut | null;
  entitlements: Record<string, number | boolean | null>;
}

export interface InvoiceRow {
  id: string;
  number: string;
  period_start: string | null;
  period_end: string | null;
  amount: string;
  currency: string;
  status: string;
  issued_at: string | null;
  due_at: string | null;
  paid_at: string | null;
}

export interface PlatformInvoiceRow extends InvoiceRow {
  organization_id: string;
  organization_name: string;
  organization_code: string;
  plan_code: string;
  plan_name: string;
}

export interface PlanRequestRow {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_code: string;
  from_plan: string;
  to_plan: string;
  to_plan_name: string;
  status: string;
  note: string | null;
  decision_note: string | null;
  created_at: string | null;
}

export interface UsageMetric {
  used: number;
  limit: number | null;
}

export interface TenantQuotas {
  usage: {
    devices: UsageMetric;
    users: UsageMetric;
    storage_mb: UsageMetric;
  };
  quotas: Record<string, number>;
}

export const ORG_STATUSES = ["active", "suspended", "archived"] as const;

export const SUB_STATUSES = [
  "trialing",
  "active",
  "past_due",
  "grace_period",
  "suspended",
  "cancelled",
  "expired",
] as const;

export const INVOICE_STATUSES = ["issued", "paid", "void"] as const;
export const PROVIDERS = ["manual", "stripe", "razorpay"] as const;
export const BILLING_CYCLES = ["monthly", "yearly"] as const;

/** Human labels for the entitlement catalogue keys. Anything not listed
 * falls back to the key with underscores replaced. */
export const ENTITLEMENT_LABELS: Record<string, string> = {
  max_devices: "Devices",
  max_users: "Users",
  max_storage_mb: "Storage (MB)",
  max_locations: "Locations",
  max_api_calls_month: "API calls / month",
  ai_credits_month: "AI credits / month",
  proof_of_play: "Proof of play",
  advanced_analytics: "Advanced analytics",
  api_access: "API access",
  sso: "Single sign-on",
  white_label: "White label",
  video_wall: "Video walls",
  ai_features: "AI features",
  dynamic_data: "Dynamic data",
  experiments: "Experiments",
  advertising: "Advertising",
  fleet_ai: "Fleet intelligence",
  developer_portal: "Developer portal",
  edge_bundles: "Edge bundles",
};

export function entitlementLabel(key: string): string {
  return ENTITLEMENT_LABELS[key] ?? key.replace(/_/g, " ");
}
