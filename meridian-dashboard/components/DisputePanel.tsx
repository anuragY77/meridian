import { DisputesResponse } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  open: "text-amber-400",
  resolved: "text-emerald-400",
  breached: "text-red-400",
};

export function DisputePanel({ data }: { data: DisputesResponse }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-neutral-400">Disputes & SLA Tracking</p>
        {data.false_positive_rate !== null && (
          <span className="text-xs text-amber-400">
            {(data.false_positive_rate * 100).toFixed(0)}% false-positive rate
          </span>
        )}
      </div>

      <div className="flex gap-3 mb-4">
        {Object.entries(data.by_status).map(([status, count]) => (
          <div key={status} className="bg-neutral-800 rounded-lg px-3 py-2">
            <p className={`text-xs ${STATUS_COLOR[status] ?? "text-neutral-400"}`}>{status}</p>
            <p className="text-lg font-semibold text-white">{count}</p>
          </div>
        ))}
      </div>

      <p className="text-[11px] text-neutral-600 mb-3 leading-snug">
        {data.false_positive_count} of {data.fraud_flag_disputes_total} fraud-flagged transactions
        that were later disputed turned out to be legitimate — the measurable version of the
        merchant "false-positive account freeze" pain point.
      </p>

      <div className="max-h-48 overflow-y-auto space-y-1">
        {data.recent.map((d, idx) => (
          <div key={idx} className="text-xs flex items-center justify-between border-b border-neutral-900 py-1">
            <span className="text-neutral-500">{d.transaction_id}... · {d.dispute_type}</span>
            <span className={STATUS_COLOR[d.status] ?? "text-neutral-400"}>{d.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
