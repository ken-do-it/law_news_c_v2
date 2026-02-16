interface Props {
  value: 'High' | 'Medium' | 'Low';
}

const config = {
  High: { bg: 'var(--color-high-bg)', text: 'var(--color-high)', icon: '▲' },
  Medium: { bg: 'var(--color-medium-bg)', text: 'var(--color-medium)', icon: '●' },
  Low: { bg: 'var(--color-low-bg)', text: 'var(--color-low)', icon: '▽' },
};

export default function SuitabilityBadge({ value }: Props) {
  const c = config[value] || config.Low;
  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold"
      style={{ backgroundColor: c.bg, color: c.text }}
    >
      {c.icon} {value}
    </span>
  );
}
