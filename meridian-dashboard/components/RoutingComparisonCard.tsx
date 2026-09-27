// components/RoutingComparisonCard.tsx
import { RoutingComparison } from "@/lib/api";

export function RoutingComparisonCard({ data }: { data: RoutingComparison[] }) {
  const ml = data.find((d) => d.strategy === "ml");
  const rule = data.find((d) => d.strategy === "rule");

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
      <p className="text-sm text-neutral-400 mb-3">ML vs Rule-Based Routing</p>
      <div className="grid grid-cols-2 gap-4">
        {[
          { label: "ML Router", stat: ml, color: "text-emerald-400" },
          { label: "Rule-Based", stat: rule, color: "text-blue-400" },
        ].map(({ label, stat, color }) => (
          <div key={label}>
            <p className={`text-xs font-medium ${color}`}>{label}</p>
            {stat ? (
              <>
                <p className="text-xl font-semibold text-white">
                  {(stat.success_rate * 100).toFixed(2)}%
                </p>
                <p className="text-xs text-neutral-500">
                  {stat.total.toLocaleString()} txns · {stat.avg_attempts} avg attempts
                </p>
              </>
            ) : (
              <p className="text-xs text-neutral-600">No data yet</p>
            )}
          </div>
        ))}
      </div>
      <p className="text-[11px] text-neutral-600 mt-3 leading-snug">
        Live samples are small — offline time-based backtest (84.9% true-best-gateway
        pick rate) is the primary evidence for routing quality, not this live comparison.
      </p>
    </div>
  );
}
