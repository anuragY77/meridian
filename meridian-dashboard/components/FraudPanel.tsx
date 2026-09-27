import { FraudFlagsResponse } from "@/lib/api";

const SEVERITY_COLOR: Record<string, string> = {
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-neutral-400",
};

export function FraudPanel({ data }: { data: FraudFlagsResponse }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-neutral-400">Fraud & Risk Flags</p>
        <span className="text-xs text-neutral-500">{data.total_flags} total</span>
      </div>

      <div className="flex gap-4 mb-4">
        {Object.entries(data.by_rule).map(([rule, count]) => (
          <div key={rule} className="bg-neutral-800 rounded-lg px-3 py-2">
            <p className="text-xs text-neutral-500">{rule}</p>
            <p className="text-lg font-semibold text-white">{count}</p>
          </div>
        ))}
      </div>

      <div className="max-h-64 overflow-y-auto space-y-2">
        {data.recent.map((flag, idx) => (
          <div key={idx} className="text-xs border-l-2 border-neutral-700 pl-3 py-1">
            <div className="flex items-center gap-2">
              <span className={`font-medium ${SEVERITY_COLOR[flag.severity] ?? "text-neutral-400"}`}>
                {flag.rule_triggered}
              </span>
              <span className="text-neutral-600">txn {flag.transaction_id}...</span>
            </div>
            <p className="text-neutral-500">{flag.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
