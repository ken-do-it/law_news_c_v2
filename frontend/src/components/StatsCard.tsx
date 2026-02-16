interface Props {
  icon: string;
  label: string;
  value: string | number;
  sub?: string;
}

export default function StatsCard({ icon, label, value, sub }: Props) {
  return (
    <div className="bg-white rounded-xl border border-[var(--color-border)] p-5 flex items-start gap-4">
      <div className="text-2xl">{icon}</div>
      <div>
        <div className="text-sm text-gray-500">{label}</div>
        <div className="text-2xl font-bold mt-1">{value}</div>
        {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}
