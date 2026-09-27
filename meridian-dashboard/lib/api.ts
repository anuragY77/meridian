// lib/api.ts
const API_BASE = "http://localhost:8000";

export interface Overview {
  total_transactions: number;
  success_rate: number;
  avg_latency_ms: number;
  avg_attempts: number;
}

export interface MethodStat {
  method: string;
  total: number;
  success_rate: number;
}

export interface GatewayStat {
  gateway_id: string;
  gateway_name: string;
  total: number;
  success_rate: number;
  avg_latency_ms: number;
}

export interface DeclineCode {
  decline_code: string;
  count: number;
  percentage: number;
}

export interface RoutingComparison {
  strategy: string;
  total: number;
  success_rate: number;
  avg_attempts: number;
}

export interface RecentTransaction {
  transaction_id: string;
  merchant_name: string;
  method: string;
  amount: number;
  status: string;
  chosen_gateway_id: string | null;
  attempt_count: number;
  routing_strategy: string | null;
  created_at: string | null;
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`);
  return res.json();
}

export const api = {
  overview: () => fetchJson<Overview>("/api/overview"),
  byMethod: () => fetchJson<MethodStat[]>("/api/by-method"),
  byGateway: () => fetchJson<GatewayStat[]>("/api/by-gateway"),
  declineCodes: () => fetchJson<DeclineCode[]>("/api/decline-codes"),
  routingComparison: () => fetchJson<RoutingComparison[]>("/api/routing-comparison"),
  recentTransactions: (limit = 20) =>
    fetchJson<RecentTransaction[]>(`/api/recent-transactions?limit=${limit}`),
};
