import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getCaseGroups, getStats, updateCaseGroupReview, downloadExcelCase } from '../lib/api';
import type { CaseGroupFilters, ReviewPayload } from '../lib/api';
import type { CaseGroup, DashboardStats } from '../lib/types';
import StatsCard from '../components/StatsCard';
import AiSuitabilityDisplay from '../components/AiSuitabilityDisplay';
import TableSkeleton from '../components/TableSkeleton';

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
  review_completed: BoolFilter;
  accepted: BoolFilter;
  unreviewed_first: boolean;
}

const DEFAULT_FILTERS: Filters = {
  review_completed: 'all',
  accepted: 'all',
  unreviewed_first: false,
};

export default function ReviewHome() {
  const [searchParams] = useSearchParams();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cases, setCases] = useState<CaseGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Set<number>>(new Set());

  const [filters, setFilters] = useState<Filters>(() => ({
    review_completed: 'all',
    accepted: 'all',
    unreviewed_first: false,
  }));

  const PAGE_SIZE = 20;

  const buildApiFilters = useCallback((f: Filters, p: number): CaseGroupFilters => {
    const params: CaseGroupFilters = {
      ordering: f.unreviewed_first ? 'review_completed,-article_count' : '-article_count',
      page: p,
      group_by_case: 'true',  // 같은 케이스 ID 중복 제거 (최신 기사 1건만 표시)
    };
    if (f.review_completed !== 'all') params.review_completed = f.review_completed === 'true';
    if (f.accepted !== 'all') params.accepted = f.accepted === 'true';
    return params;
  }, []);

  const loadData = useCallback(async (p: number, f: Filters) => {
    setLoading(true);
    try {
      const [statsData, listData] = await Promise.all([
        getStats(),
        getCaseGroups(buildApiFilters(f, p)),
      ]);
      setStats(statsData);
      setCases(listData.results);
      setTotal(listData.count);
    } finally {
      setLoading(false);
    }
  }, [buildApiFilters]);

  useEffect(() => {
    loadData(page, filters);
  }, [page, filters, loadData]);

  const handleFilterChange = <K extends keyof Filters>(
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

  useEffect(() => { document.title = '심사 현황 | LawNGood'; }, []);

  const isFiltered =
    filters.review_completed !== 'all' ||
    filters.accepted !== 'all';

  const toggleUnreviewedFirst = () => {
    setPage(1);
    setFilters((prev) => ({ ...prev, unreviewed_first: !prev.unreviewed_first }));
  };

  const handleReviewChange = async (
    id: number,
    field: 'review_completed' | 'client_suitability' | 'accepted',
    value: boolean | 'High' | 'Medium' | 'Low' | null,
  ) => {
    const extraPayload: ReviewPayload = {};
    if (field === 'review_completed' && value === true) {
      const c = cases.find((x) => x.id === id);
      if (c && !c.client_suitability) {
        extraPayload.client_suitability = 'Medium';
      }
    }

    setCases((prev) =>
      prev.map((c) => (c.id === id ? { ...c, [field]: value, ...extraPayload } : c)),
    );
    setSaving((prev) => new Set(prev).add(id));
    try {
      const updated = await updateCaseGroupReview(id, { [field]: value, ...extraPayload });
      setCases((prev) => prev.map((c) => (c.id === id ? { ...c, ...updated } : c)));
      const newStats = await getStats();
      setStats(newStats);
    } catch {
      const listData = await getCaseGroups(buildApiFilters(filters, page));
      setCases(listData.results);
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
    <div className="p-6 w-full max-w-[1600px] mx-auto space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-2xl font-bold">심사 현황</h1>
        <p className="text-gray-500 text-sm mt-1">
          AI 분석 결과를 바탕으로 로앤굿 심사 결과와 수임 여부를 관리합니다
        </p>
      </div>

      {/* 요약 카드 — 가로형 "라벨 : 값건", 1.5배 확대 */}
      <div className="-mx-6 px-6 py-5 bg-gray-50/60 border-y border-border">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-[1600px] mx-auto">
          <StatsCard horizontal large icon="📋" label="전체케이스" value={stats?.total_cases ?? '-'} sub="건" />
          <StatsCard horizontal large icon="✅" label="심사완료" value={stats?.total_reviewed_cases ?? '-'} sub="건" />
          <StatsCard horizontal large icon="🎯" label="수임 통과" value={stats?.total_accepted_cases ?? '-'} sub="건" />
          <StatsCard
            horizontal
            large
            icon="📊"
            label="통과율"
            value={stats != null ? `${stats.acceptance_rate_cases}%` : '-'}
          />
        </div>
      </div>

      {/* 필터 바 */}
      <div className="bg-white rounded-xl border border-border px-5 py-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* AI 적합도 — 다중 선택 */}
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
          {/* 미심사 먼저 토글 */}
          <button
            onClick={toggleUnreviewedFirst}
            className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
              filters.unreviewed_first
                ? 'bg-navy text-white border-navy font-semibold'
                : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-50'
            }`}
          >
            미심사 먼저
          </button>

          {(isFiltered || filters.unreviewed_first) && (
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
          <div className="flex items-center gap-3">
            <button
              onClick={() => downloadExcelCase(buildApiFilters(filters, 1))}
              className="text-xs text-navy hover:underline font-medium"
            >
              📥 엑셀 다운로드
            </button>
            <span className="text-xs text-gray-400">총 {total}건</span>
          </div>
        </div>

        {loading ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody><TableSkeleton cols={7} rows={10} /></tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500 bg-gray-50">
                  <th className="px-4 py-3 font-medium whitespace-nowrap">케이스 ID</th>
                  <th className="px-4 py-3 font-medium">사건명</th>
                  <th className="px-4 py-3 font-medium whitespace-nowrap">기사 수</th>
                  <th className="px-4 py-3 font-medium whitespace-nowrap">AI 적합도</th>
                  <th className="px-4 py-3 font-medium whitespace-nowrap">로앤굿 심사결과</th>
                  <th className="px-4 py-3 font-medium text-center whitespace-nowrap">심사완료</th>
                  <th className="px-4 py-3 font-medium text-center whitespace-nowrap">통과여부</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => {
                  const isSaving = saving.has(c.id);
                  return (
                    <tr
                      key={c.id}
                      className={`border-b last:border-0 transition-colors ${isSaving ? 'opacity-60' : 'hover:bg-gray-50'}`}
                    >
                      <td className="px-4 py-3">
                        <Link
                          to={`/analyses/case/${c.case_id}`}
                          className="text-blue-600 hover:underline font-mono"
                        >
                          {c.case_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        <Link
                          to={`/analyses/case/${c.case_id}`}
                          className="hover:text-blue-600 line-clamp-2 leading-snug"
                        >
                          {c.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{c.article_count}</td>
                      <td className="px-4 py-3">
                        <AiSuitabilityDisplay dist={c.suitability_distribution} />
                      </td>
                      <td className="px-4 py-3">
                        <ClientSuitabilityButtons
                          value={c.client_suitability}
                          onChange={(v) => handleReviewChange(c.id, 'client_suitability', v)}
                          disabled={isSaving}
                        />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <input
                          type="checkbox"
                          checked={c.review_completed}
                          disabled={isSaving}
                          onChange={(e) =>
                            handleReviewChange(c.id, 'review_completed', e.target.checked)
                          }
                          className="w-6 h-6 accent-navy cursor-pointer disabled:cursor-not-allowed"
                        />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <input
                          type="checkbox"
                          checked={c.accepted}
                          disabled={isSaving || !c.review_completed}
                          title={!c.review_completed ? '심사 완료 후 체크 가능합니다' : undefined}
                          onChange={(e) =>
                            handleReviewChange(c.id, 'accepted', e.target.checked)
                          }
                          className="w-6 h-6 accent-gold cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        />
                      </td>
                    </tr>
                  );
                })}
                {cases.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-gray-400">
                      사건 데이터가 없습니다
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* 페이지네이션 — 숫자로 바로 이동 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-1 px-5 py-3 border-t border-border">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-sm rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-100"
            >
              ‹
            </button>
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`px-3 py-1 text-sm rounded border border-gray-200 ${
                  p === page ? 'bg-navy text-white border-navy' : 'hover:bg-gray-100'
                }`}
              >
                {p}
              </button>
            ))}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-sm rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-100"
            >
              ›
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
