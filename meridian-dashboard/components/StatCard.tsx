// components/StatCard.tsx
interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
}

export function StatCard({ label, value, subtext }: StatCardProps) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
      <p className="text-sm text-neutral-400">{label}</p>
      <p className="text-3xl font-semibold text-white mt-1">{value}</p>
      {subtext && <p className="text-xs text-neutral-500 mt-1">{subtext}</p>}
    </div>
  );
}
