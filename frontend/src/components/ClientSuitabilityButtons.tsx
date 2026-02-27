const SUITABILITY_OPTIONS = ['High', 'Medium', 'Low'] as const;

export const SUIT_CONFIG = {
  High:   { solid: '#E11D48', light: 'rgba(225,29,72,0.10)',   text: '#E11D48' },
  Medium: { solid: '#D97706', light: 'rgba(217,119,6,0.10)',   text: '#C05621' },
  Low:    { solid: '#6B7280', light: 'rgba(107,114,128,0.10)', text: '#4B5563' },
} as const;

interface Props {
  value: 'High' | 'Medium' | 'Low' | null;
  onChange: (v: 'High' | 'Medium' | 'Low' | null) => void;
  disabled?: boolean;
}

export default function ClientSuitabilityButtons({ value, onChange, disabled }: Props) {
  return (
    <div className={`flex gap-1 ${disabled ? 'opacity-40 pointer-events-none' : ''}`}>
      {SUITABILITY_OPTIONS.map((opt) => {
        const isSelected = value === opt;
        const c = SUIT_CONFIG[opt];
        return (
          <button
            key={opt}
            onClick={() => onChange(isSelected ? null : opt)}
            title={isSelected ? '클릭하여 해제' : opt}
            className="text-xs px-2.5 py-1 rounded font-semibold transition-all whitespace-nowrap"
            style={
              isSelected
                ? { backgroundColor: c.solid, color: '#fff' }
                : { backgroundColor: c.light, color: c.text }
            }
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}
