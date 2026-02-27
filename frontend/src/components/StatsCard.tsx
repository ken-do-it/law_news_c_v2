interface Props {
  icon: string;
  label: string;
  value: string | number;
  sub?: string;
  compact?: boolean;
}

export default function StatsCard({ icon, label, value, sub, compact }: Props) {
  if (compact) {
    return (
      <div className="bg-white rounded-md border border-border px-2 py-1.5 flex items-center gap-1.5 min-w-0">
        <span className="text-sm shrink-0">{icon}</span>
        <div className="min-w-0">
          <div className="text-[10px] text-gray-500 truncate">{label}</div>
          <div className="text-sm font-bold leading-tight truncate">{value}{sub && <span className="text-[10px] font-normal text-gray-400 ml-0.5">{sub}</span>}</div>
        </div>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-xl border border-border p-5 flex items-start gap-4">
      <div className="text-2xl">{icon}</div>
      <div>
        <div className="text-sm text-gray-500">{label}</div>
        <div className="text-2xl font-bold mt-1">{value}</div>
        {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}
