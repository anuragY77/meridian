"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { api, Overview, MethodStat, GatewayStat, DeclineCode, RoutingComparison, RecentTransaction } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { RoutingComparisonCard } from "@/components/RoutingComparisonCard";
import { FraudPanel } from "@/components/FraudPanel";
import { FraudFlagsResponse } from "@/lib/api";

const COLORS = ["#34d399", "#60a5fa", "#f472b6", "#fbbf24", "#a78bfa", "#f87171"];

export default function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [byMethod, setByMethod] = useState<MethodStat[]>([]);
  const [byGateway, setByGateway] = useState<GatewayStat[]>([]);
  const [declineCodes, setDeclineCodes] = useState<DeclineCode[]>([]);
  const [routingComparison, setRoutingComparison] = useState<RoutingComparison[]>([]);
  const [recent, setRecent] = useState<RecentTransaction[]>([]);
  const [fraudFlags, setFraudFlags] = useState<FraudFlagsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    try {
      const [ov, meth, gw, decl, routing, rec, fraud] = await Promise.all([
        api.overview(),
        api.byMethod(),
        api.byGateway(),
        api.declineCodes(),
        api.routingComparison(),
        api.recentTransactions(15),
        api.fraudFlags(30),
      ]);
      setOverview(ov);
      setByMethod(meth);
      setByGateway(gw);
      setDeclineCodes(decl);
      setRoutingComparison(routing);
      setRecent(rec);
      setFraudFlags(fraud);
      setError(null);
    } catch (e) {
      setError("Could not reach the Meridian API — is uvicorn running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 5000); // poll every 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return       <div className="min-h-screen bg-black text-white flex items-center justify-center">Loading Meridian...</div>;
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">Meridian</h1>
        <p className="text-neutral-500 text-sm">Intelligent Payment Routing & Reconciliation — live dashboard</p>
      </header>

      {/* KPI row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Transactions" value={overview!.total_transactions.toLocaleString()} />
        <StatCard label="Success Rate" value={`${(overview!.success_rate * 100).toFixed(2)}%`} />
        <StatCard label="Avg Latency" value={`${overview!.avg_latency_ms} ms`} />
        <StatCard label="Avg Attempts" value={`${overview!.avg_attempts}`} subtext="per transaction" />
      </div>

      {/* Routing comparison */}
      <div className="mb-6">
        <RoutingComparisonCard data={routingComparison} />
      </div>

      {fraudFlags && (
        <div className="mb-6">
          <FraudPanel data={fraudFlags} />
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
          <p className="text-sm text-neutral-400 mb-4">Success Rate by Method</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byMethod}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="method" stroke="#737373" fontSize={12} />
              <YAxis stroke="#737373" fontSize={12} domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
              <Tooltip
                contentStyle={{ background: "#171717", border: "1px solid #262626" }}
                formatter={(v: number) => `${(v * 100).toFixed(2)}%`}
              />
              <Bar dataKey="success_rate" fill="#34d399" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
          <p className="text-sm text-neutral-400 mb-4">Decline Code Breakdown</p>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={declineCodes}
                dataKey="count"
                nameKey="decline_code"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ decline_code, percentage }) => `${decline_code} (${percentage}%)`}
              >
                {declineCodes.map((_, idx) => (
                  <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#171717", border: "1px solid #262626" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Gateway table */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 mb-6">
        <p className="text-sm text-neutral-400 mb-4">Gateway Performance</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-neutral-500 border-b border-neutral-800">
              <th className="pb-2">Gateway</th>
              <th className="pb-2">Total</th>
              <th className="pb-2">Success Rate</th>
              <th className="pb-2">Avg Latency</th>
            </tr>
          </thead>
          <tbody>
            {byGateway.map((gw) => (
              <tr key={gw.gateway_id} className="border-b border-neutral-900">
                <td className="py-2">{gw.gateway_name}</td>
                <td className="py-2">{gw.total.toLocaleString()}</td>
                <td className="py-2">
                  <span className={gw.success_rate >= 0.9 ? "text-emerald-400" : "text-amber-400"}>
                    {(gw.success_rate * 100).toFixed(2)}%
                  </span>
                </td>
                <td className="py-2">{gw.avg_latency_ms} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Recent transactions feed */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
        <p className="text-sm text-neutral-400 mb-4">Recent Transactions (live)</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-neutral-500 border-b border-neutral-800">
              <th className="pb-2">Txn</th>
              <th className="pb-2">Merchant</th>
              <th className="pb-2">Method</th>
              <th className="pb-2">Amount</th>
              <th className="pb-2">Gateway</th>
              <th className="pb-2">Attempts</th>
              <th className="pb-2">Strategy</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((txn) => (
              <tr key={txn.transaction_id} className="border-b border-neutral-900">
                <td className="py-2 font-mono text-xs text-neutral-500">{txn.transaction_id}...</td>
                <td className="py-2">{txn.merchant_name}</td>
                <td className="py-2">{txn.method}</td>
                <td className="py-2">₹{txn.amount.toLocaleString()}</td>
                <td className="py-2">{txn.chosen_gateway_id ?? "—"}</td>
                <td className="py-2">{txn.attempt_count}</td>
                <td className="py-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-neutral-800">{txn.routing_strategy ?? "—"}</span>
                </td>
                <td className="py-2">
                  <span className={txn.status === "success" ? "text-emerald-400" : "text-red-400"}>
                    {txn.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
