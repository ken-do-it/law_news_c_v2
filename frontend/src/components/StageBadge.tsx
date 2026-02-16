interface Props {
  value: string;
}

const stageColors: Record<string, { bg: string; text: string }> = {
  '피해 발생': { bg: '#FEF3C7', text: '#92400E' },
  '관련 절차 진행': { bg: '#DBEAFE', text: '#1E40AF' },
  '소송중': { bg: '#FCE7F3', text: '#9D174D' },
  '판결 선고': { bg: '#E0E7FF', text: '#3730A3' },
  '종결': { bg: '#F3F4F6', text: '#374151' },
};

export default function StageBadge({ value }: Props) {
  if (!value) return <span className="text-gray-400 text-xs">-</span>;
  const c = stageColors[value] || { bg: '#F3F4F6', text: '#374151' };
  return (
    <span
      className="inline-block px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: c.bg, color: c.text }}
    >
      {value}
    </span>
  );
}
