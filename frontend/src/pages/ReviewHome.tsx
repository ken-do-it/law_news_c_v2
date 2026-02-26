import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getAnalyses, getStats, updateReview } from '../lib/api';
import type { AnalysisFilters, ReviewPayload } from '../lib/api';
import type { Analysis, DashboardStats } from '../lib/types';
import StatsCard from '../components/StatsCard';
import SuitabilityBadge from '../components/SuitabilityBadge';

const SUITABILITY_OPTIONS = ['High', 'Medium', 'Low'] as const;

const SUIT_CONFIG = {
  High:   { solid: '#E11D48', light: 'rgba(225,29,72,0.10)',   text: '#E11D48' },
  Medium: { solid: '#D97706', light: 'rgba(217,119,6,0.10)',   text: '#C05621' },
  Low:    { solid: '#6B7280', light: 'rgba(107,114,128,0.10)', text: '#4B5563' },
} as const;

// ── 로앤굿 심사결과 컬러 버튼 ──
function ClientSuitabilityButtons({
  value,
  onChange,
  disabled,
}: {
  value: 'High' | 'Medium' | 'Low' | null;
  onChange: (v: 'High' | 'Medium' | 'Low' | null) => void;
  disabled?: boolean;
}) {
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

// ── AI 적합도 다중 선택 필터 ──
function SuitabilityMultiFilter({
  value,
  onToggle,
}: {
  value: string[];
  onToggle: (opt: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 whitespace-nowrap">AI 적합도</span>
      <div className="flex gap-1">
        {SUITABILITY_OPTIONS.map((opt) => {
          const isActive = value.includes(opt);
          const c = SUIT_CONFIG[opt];
          return (
            <button
              key={opt}
              onClick={() => onToggle(opt)}
              className="px-3 py-1 text-xs font-semibold rounded transition-all"
              style={
                isActive
                  ? { backgroundColor: c.solid, color: '#fff' }
                  : { backgroundColor: 'white', color: '#9CA3AF', border: '1px solid #E5E7EB' }
              }
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── 단일 선택 토글 필터 (심사완료, 통과여부) ──
type BoolFilter = 'all' | 'true' | 'false';

function FilterToggle<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 whitespace-nowrap">{label}</span>
      <div className="flex rounded-lg border border-gray-200 overflow-hidden">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1 text-xs transition-colors ${
              value === opt.value
                ? 'bg-navy text-white font-semibold'
                : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

interface Filters {
  suitability: string[];   // 다중 선택 (빈 배열 = 전체)
  review_completed: BoolFilter;
  accepted: BoolFilter;
}

const DEFAULT_FILTERS: Filters = {
  suitability: [],
  review_completed: 'all',
  accepted: 'all',
};

export default function ReviewHome() {
  const [searchParams] = useSearchParams();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Set<number>>(new Set());

  // URL 파라미터로 초기 필터 설정 (대시보드 파이 차트 클릭 연동)
  const [filters, setFilters] = useState<Filters>(() => {
    const suitabilityParam = searchParams.get('suitability');
    return {
      suitability: suitabilityParam ? [suitabilityParam] : [],
      review_completed: 'all',
      accepted: 'all',
    };
  });

  const PAGE_SIZE = 20;

  const buildApiFilters = useCallback((f: Filters, p: number): AnalysisFilters => {
    const params: AnalysisFilters = { ordering: '-analyzed_at', page: p };
    if (f.suitability.length > 0) params.suitability = f.suitability.join(',');
    if (f.review_completed !== 'all') params.review_completed = f.review_completed === 'true';
    if (f.accepted !== 'all') params.accepted = f.accepted === 'true';
    return params;
  }, []);

  const loadData = useCallback(async (p: number, f: Filters) => {
    setLoading(true);
    try {
      const [statsData, listData] = await Promise.all([
        getStats(),
        getAnalyses(buildApiFilters(f, p)),
      ]);
      setStats(statsData);
      setAnalyses(listData.results);
      setTotal(listData.count);
    } finally {
      setLoading(false);
    }
  }, [buildApiFilters]);

  useEffect(() => {
    loadData(page, filters);
  }, [page, filters, loadData]);

  const handleSuitabilityToggle = (opt: string) => {
    setPage(1);
    setFilters((prev) => ({
      ...prev,
      suitability: prev.suitability.includes(opt)
        ? prev.suitability.filter((v) => v !== opt)
        : [...prev.suitability, opt],
    }));
  };

  const handleFilterChange = <K extends keyof Omit<Filters, 'suitability'>>(
    key: K,
    value: Filters[K],
  ) => {
    setPage(1);
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetFilters = () => {
    setPage(1);
    setFilters(DEFAULT_FILTERS);
  };

  const isFiltered =
    filters.suitability.length > 0 ||
    filters.review_completed !== 'all' ||
    filters.accepted !== 'all';

  const handleReviewChange = async (
    id: number,
    field: 'review_completed' | 'client_suitability' | 'accepted',
    value: boolean | 'High' | 'Medium' | 'Low' | null,
  ) => {
    // 심사완료 체크 시 client_suitability 자동 설정 (미선택 상태일 때만)
    const extraPayload: ReviewPayload = {};
    if (field === 'review_completed' && value === true) {
      const analysis = analyses.find((a) => a.id === id);
      if (analysis && !analysis.client_suitability) {
        extraPayload.client_suitability = analysis.suitability;
      }
    }

    // 낙관적 업데이트
    setAnalyses((prev) =>
      prev.map((a) => (a.id === id ? { ...a, [field]: value, ...extraPayload } : a)),
    );

    setSaving((prev) => new Set(prev).add(id));
    try {
      const updated = await updateReview(id, { [field]: value, ...extraPayload });
      setAnalyses((prev) => prev.map((a) => (a.id === id ? { ...a, ...updated } : a)));
      const newStats = await getStats();
      setStats(newStats);
    } catch {
      const listData = await getAnalyses(buildApiFilters(filters, page));
      setAnalyses(listData.results);
    } finally {
      setSaving((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-2xl font-bold">심사 현황</h1>
        <p className="text-gray-500 text-sm mt-1">
          AI 분석 결과를 바탕으로 로앤굿 심사 결과와 수임 여부를 관리합니다
        </p>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard icon="📋" label="전체 케이스" value={stats?.total_analyzed ?? '-'} sub="건" />
        <StatsCard icon="✅" label="심사 완료" value={stats?.total_reviewed ?? '-'} sub="건" />
        <StatsCard icon="🎯" label="수임 통과" value={stats?.total_accepted ?? '-'} sub="건" />
        <StatsCard
          icon="📊"
          label="통과율"
          value={stats ? `${stats.acceptance_rate}%` : '-'}
          sub="심사 완료 대비"
        />
      </div>

      {/* 필터 바 */}
      <div className="bg-white rounded-xl border border-border px-5 py-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* AI 적합도 — 다중 선택 */}
          <SuitabilityMultiFilter
            value={filters.suitability}
            onToggle={handleSuitabilityToggle}
          />

          <FilterToggle
            label="심사완료"
            value={filters.review_completed}
            onChange={(v) => handleFilterChange('review_completed', v)}
            options={[
              { value: 'all', label: '전체' },
              { value: 'true', label: '완료' },
              { value: 'false', label: '미완료' },
            ]}
          />
          <FilterToggle
            label="통과여부"
            value={filters.accepted}
            onChange={(v) => handleFilterChange('accepted', v)}
            options={[
              { value: 'all', label: '전체' },
              { value: 'true', label: '통과' },
              { value: 'false', label: '미통과' },
            ]}
          />
          {isFiltered && (
            <button
              onClick={resetFilters}
              className="text-xs text-gray-400 hover:text-gray-600 underline underline-offset-2 ml-auto"
            >
              필터 초기화
            </button>
          )}
        </div>
      </div>

      {/* 심사 현황 테이블 */}
      <div className="bg-white rounded-xl border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="text-sm font-semibold">
            사건 목록
            {isFiltered && (
              <span className="ml-2 text-xs font-normal text-gold">필터 적용 중</span>
            )}
          </h3>
          <span className="text-xs text-gray-400">총 {total}건</span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">로딩 중...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500 bg-gray-50">
                  <th className="px-4 py-3 font-medium">AI 적합도</th>
                  <th className="px-4 py-3 font-medium">기사 제목</th>
                  <th className="px-4 py-3 font-medium">분야</th>
                  <th className="px-4 py-3 font-medium">로앤굿 심사결과</th>
                  <th className="px-4 py-3 font-medium text-center">심사완료</th>
                  <th className="px-4 py-3 font-medium text-center">통과여부</th>
                  <th className="px-4 py-3 font-medium">날짜</th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((a) => {
                  const isSaving = saving.has(a.id);
                  return (
                    <tr
                      key={a.id}
                      className={`border-b last:border-0 transition-colors ${isSaving ? 'opacity-60' : 'hover:bg-gray-50'}`}
                    >
                      {/* AI 적합도 */}
                      <td className="px-4 py-3">
                        <SuitabilityBadge value={a.suitability} />
                      </td>

                      {/* 기사 제목 */}
                      <td className="px-4 py-3 max-w-xs">
                        <Link
                          to={`/analyses/${a.id}`}
                          className="hover:text-blue-600 line-clamp-2 leading-snug"
                        >
                          {a.article_title}
                        </Link>
                      </td>

                      {/* 분야 */}
                      <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                        {a.case_category}
                      </td>

                      {/* 로앤굿 심사결과 버튼 */}
                      <td className="px-4 py-3">
                        <ClientSuitabilityButtons
                          value={a.client_suitability}
                          onChange={(v) => handleReviewChange(a.id, 'client_suitability', v)}
                          disabled={isSaving}
                        />
                      </td>

                      {/* 심사완료 체크박스 — 2배 크기 */}
                      <td className="px-4 py-3 text-center">
                        <input
                          type="checkbox"
                          checked={a.review_completed}
                          disabled={isSaving}
                          onChange={(e) =>
                            handleReviewChange(a.id, 'review_completed', e.target.checked)
                          }
                          className="w-6 h-6 accent-navy cursor-pointer disabled:cursor-not-allowed"
                        />
                      </td>

                      {/* 통과여부 체크박스 — 2배 크기 */}
                      <td className="px-4 py-3 text-center">
                        <input
                          type="checkbox"
                          checked={a.accepted}
                          disabled={isSaving || !a.review_completed}
                          title={!a.review_completed ? '심사 완료 후 체크 가능합니다' : undefined}
                          onChange={(e) =>
                            handleReviewChange(a.id, 'accepted', e.target.checked)
                          }
                          className="w-6 h-6 accent-gold cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        />
                      </td>

                      {/* 날짜 */}
                      <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                        {a.published_at?.slice(0, 10)}
                      </td>
                    </tr>
                  );
                })}
                {analyses.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-gray-400">
                      분석 데이터가 없습니다
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-border">
            <span className="text-xs text-gray-500">
              {page} / {totalPages} 페이지
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-xs rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
              >
                이전
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 text-xs rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
              >
                다음
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
