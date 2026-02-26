import { Link, useLocation } from 'react-router-dom';

const navItems = [
  { path: '/', label: '심사 현황' },
  { path: '/analyses', label: '분석 목록' },
  { path: '/settings', label: '키워드 관리' },
  { path: '/dashboard', label: 'AI 대시보드' },
];

export default function TopNav() {
  const location = useLocation();

  return (
    <nav className="bg-[var(--color-navy)] text-white px-6 py-3 flex items-center justify-between">
      <Link to="/" className="text-lg font-bold tracking-wide">
        <span className="text-[var(--color-gold)]">LawNGood</span> News Analyzer
      </Link>

      <div className="flex items-center gap-6">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`text-sm transition-colors ${
              location.pathname === item.path
                ? 'text-[var(--color-gold)] font-semibold'
                : 'text-gray-300 hover:text-white'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
