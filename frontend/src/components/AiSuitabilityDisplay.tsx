const SUIT_CONFIG = {
  High:   { light: 'rgba(225,29,72,0.10)', text: '#E11D48' },
  Medium: { light: 'rgba(217,119,6,0.10)', text: '#C05621' },
  Low:    { light: 'rgba(107,114,128,0.10)', text: '#4B5563' },
} as const;

/** 사건 내 기사별 AI 적합도 분포 (High/Medium/Low 개수) 표시 */
export default function AiSuitabilityDisplay({ dist }: { dist?: Record<string, number> }) {
  if (!dist || Object.keys(dist).length === 0) return <span className="text-gray-400">—</span>;
  const parts = (['High', 'Medium', 'Low'] as const)
    .filter((k) => (dist[k] ?? 0) > 0)
    .map((k) => {
      const c = SUIT_CONFIG[k];
      return (
        <span
          key={k}
          className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold mr-1 last:mr-0"
          style={{ backgroundColor: c.light, color: c.text }}
        >
          {k} {dist[k]}
        </span>
      );
    });
  return <div className="flex flex-wrap gap-0.5">{parts.length ? parts : <span className="text-gray-400">—</span>}</div>;
}
