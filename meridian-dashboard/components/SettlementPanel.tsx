import { SettlementsResponse } from "@/lib/api";

export function SettlementPanel({ data }: { data: SettlementsResponse }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-neutral-400">Cross-Border Settlements</p>
        <span className="text-xs text-neutral-500">
          {data.reconciliation_mismatches === 0 ? "✓ all reconciled" : `${data.reconciliation_mismatches} mismatches`}
        </span>
      </div>

      <p className="text-2xl font-semibold text-white mb-4">
        ₹{data.total_net_settled_inr.toLocaleString()}
        <span className="text-xs text-neutral-500 font-normal ml-2">total net settled</span>
      </p>

      <div className="grid grid-cols-2 gap-3">
        {data.by_currency.map((c) => (
          <div key={c.currency} className="bg-neutral-800 rounded-lg px-3 py-2">
            <p className="text-xs text-neutral-500">{c.currency} · {c.count} txns</p>
            <p className="text-sm font-medium text-white">₹{c.net_settlement_inr.toLocaleString()}</p>
            <p className="text-[10px] text-neutral-600">fee: ₹{c.total_fee_inr.toLocaleString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
