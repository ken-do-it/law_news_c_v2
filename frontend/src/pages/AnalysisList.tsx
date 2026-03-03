import { useEffect, useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getAnalyses, downloadExcel, type AnalysisFilters } from '../lib/api';
import { useState } from 'react';
import type { ReactNode } from 'react';
import type { Analysis, PaginatedResponse } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';
import TableSkeleton from '../components/TableSkeleton';

const PAGE_SIZE = 20;

function formatDate(iso: string): string {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

// 정렬 가능한 컬럼 헤더
function SortTh({
  field,
  ordering,
  onSort,
  children,
  className,
}: {
  field: string;
  ordering: string;
  onSort: (field: string) => void;
  children: ReactNode;
  className?: string;
}) {
  const isDesc = ordering === `-${field}`;
  const isAsc = ordering === field;
  const active = isDesc || isAsc;

  return (
    <th
      className={`px-3 py-3 text-xs font-semibold tracking-wide cursor-pointer select-none whitespace-nowrap group ${
        active ? 'text-navy' : 'text-gray-400 hover:text-gray-600'
      } ${className ?? ''}`}
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center gap-0.5">
        {children}
        <span
          className={`text-[10px] transition-opacity ${
            active ? 'opacity-100 text-navy' : 'opacity-20 group-hover:opacity-60'
          }`}
        >
          {isDesc ? '↓' : isAsc ? '↑' : '↕'}
        </span>
      </span>
    </th>
  );
}

export default function AnalysisList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<PaginatedResponse<Analysis> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { document.title = '분석 목록 | LawNGood'; }, []);

  const filters = useMemo<AnalysisFilters>(() => ({
    search: searchParams.get('search') || undefined,
    suitability: searchParams.get('suitability') || undefined,
    ordering: searchParams.get('ordering') || '-analyzed_at',
    page: Number(searchParams.get('page')) || 1,
    include_irrelevant: searchParams.get('include_irrelevant') || undefined,
    group_by_case: 'true',
  }), [searchParams]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getAnalyses(filters);
      setData(result);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const setFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) { params.set(key, value); } else { params.delete(key); }
    params.delete('page');
    setSearchParams(params);
  };

  const setPage = (page: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(page));
    setSearchParams(params);
  };

  // 컬럼 헤더 클릭: 현재 내림차순이면 → 오름차순, 그 외 → 내림차순(기본)
  const toggleSort = (field: string) => {
    const current = filters.ordering ?? '-analyzed_at';
    const next = current === `-${field}` ? field : `-${field}`;
    setFilter('ordering', next);
  };

  const currentPage = Number(searchParams.get('page')) || 1;
  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;
  const activeSuitability = searchParams.get('suitability') || 'all';
  const ordering = filters.ordering ?? '-analyzed_at';

  // 기사 발행일 기준 정렬 활성 여부
  const pubSortActive = ordering === '-published_at' || ordering === 'published_at';

  return (
    <div className="p-6 max-w-[1800px] mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold">분석 목록</h1>
        <p className="text-gray-500 text-sm mt-1">
          AI가 분석한 개별 기사를 탐색합니다 · 기사 클릭 시 상세 분석 결과 표시 · 컬럼 헤더 클릭으로 정렬
        </p>
      </div>

      {/* 필터 바 */}
      <div className="bg-white rounded-xl border border-border p-4 flex flex-wrap gap-3 items-end">
        {/* 검색 */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            검색
            <span className="ml-1 text-gray-400 font-normal">기사 제목 · 케이스 ID</span>
          </label>
          <input
            key={filters.search ?? 'empty'}
            type="text"
            placeholder="예: 쿠팡, 손해배상, 2026-02-001..."
            className="border rounded px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-1 focus:ring-gold"
            defaultValue={filters.search}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setFilter('search', (e.target as HTMLInputElement).value.trim());
            }}
          />
        </div>

        {/* AI 적합도 필터 */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">AI 적합도</label>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden">
            {(['all', 'High', 'Medium', 'Low'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setFilter('suitability', v === 'all' ? '' : v)}
                className={`px-3 py-1.5 text-xs transition-colors ${
                  activeSuitability === v
                    ? 'bg-navy text-white font-semibold'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {v === 'all' ? '전체' : v}
              </button>
            ))}
          </div>
        </div>

        {/* 기사 발행일 기준 정렬 — 컬럼이 없는 발행일은 별도 버튼으로 제공 */}
        <div className="flex items-end">
          <button
            onClick={() =>
              setFilter(
                'ordering',
                ordering === '-published_at'
                  ? 'published_at'   // 내림차순 → 오름차순
                  : ordering === 'published_at'
                  ? '-analyzed_at'   // 오름차순 → 초기화
                  : '-published_at', // 그 외 → 발행일 내림차순 활성화
              )
            }
            className={`px-3 py-1.5 text-xs rounded border transition-colors whitespace-nowrap ${
              pubSortActive
                ? 'bg-navy text-white border-navy font-semibold'
                : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-50'
            }`}
          >
            기사 발행일 기준
            {ordering === '-published_at' ? ' ↓' : ordering === 'published_at' ? ' ↑' : ''}
          </button>
        </div>

        {/* 비관련 기사 포함 */}
        <div className="flex items-end">
          <button
            onClick={() =>
              setFilter(
                'include_irrelevant',
                filters.include_irrelevant === 'true' ? '' : 'true',
              )
            }
            className={`px-3 py-1.5 text-xs rounded border transition-colors ${
              filters.include_irrelevant === 'true'
                ? 'bg-navy text-white border-navy font-semibold'
                : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-50'
            }`}
          >
            비관련 포함
          </button>
        </div>

        <button
          onClick={() => downloadExcel(filters)}
          className="ml-auto bg-navy text-white text-sm px-4 py-1.5 rounded hover:opacity-90"
        >
          📥 엑셀 다운로드
        </button>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-2 text-xs text-gray-400 border-b">
          총 {data?.count ?? '—'}건
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left bg-gray-50">
                <th className="px-3 py-3 text-xs font-semibold text-gray-400 tracking-wide w-[28%]">기사 제목</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap w-[11%]">케이스</th>
                <SortTh field="suitability_rank" ordering={ordering} onSort={toggleSort} className="w-[8%]">
                  AI 적합도
                </SortTh>
                <th className="px-3 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap w-[11%]">사건 유형</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap w-[10%]">진행단계</th>
                <SortTh field="damage_amount_num" ordering={ordering} onSort={toggleSort} className="w-[13%]">
                  피해규모
                </SortTh>
                <th className="px-3 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap w-[11%]">상대방</th>
                <SortTh field="analyzed_at" ordering={ordering} onSort={toggleSort} className="w-[8%]">
                  분석일
                </SortTh>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableSkeleton cols={8} rows={12} />
              ) : (
                <>
                  {(data?.results ?? []).map((a) => (
                    <tr key={a.id} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
                      <td className="px-3 py-2.5">
                        <Link
                          to={`/analyses/${a.id}`}
                          className="hover:text-blue-600 line-clamp-2 leading-snug block"
                          title={a.article_title}
                        >
                          {a.article_title}
                        </Link>
                      </td>
                      <td className="px-3 py-2.5">
                        {a.case_id ? (
                          <div className="flex items-center gap-1">
                            <Link
                              to={`/analyses/case/${a.case_id}`}
                              className="font-mono text-xs text-blue-600 hover:underline"
                            >
                              {a.case_id}
                            </Link>
                            {a.related_count > 1 && (
                              <span className="text-[10px] text-gray-400 bg-gray-100 rounded px-1 leading-4">
                                {a.related_count}건
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-300 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <SuitabilityBadge value={a.suitability} />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-600 max-w-[100px] truncate" title={a.case_category}>
                        {a.case_category || '—'}
                      </td>
                      <td className="px-3 py-2.5">
                        {a.stage ? <StageBadge value={a.stage} /> : <span className="text-gray-400 text-xs">—</span>}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-600 max-w-[120px] truncate" title={a.damage_amount ?? ''}>
                        {a.damage_amount || '—'}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-600 max-w-[100px] truncate" title={a.defendant ?? ''}>
                        {a.defendant || '—'}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap tabular-nums">
                        {formatDate(a.analyzed_at)}
                      </td>
                    </tr>
                  ))}
                  {!loading && (data?.results ?? []).length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-gray-400">
                        분석 결과가 없습니다
                      </td>
                    </tr>
                  )}
                </>
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="flex justify-center gap-1 py-3 border-t">
            {currentPage > 1 && (
              <button onClick={() => setPage(currentPage - 1)} className="px-3 py-1 text-sm rounded hover:bg-gray-100">
                ‹
              </button>
            )}
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`px-3 py-1 text-sm rounded ${p === currentPage ? 'bg-navy text-white' : 'hover:bg-gray-100'}`}
              >
                {p}
              </button>
            ))}
            {currentPage < totalPages && (
              <button onClick={() => setPage(currentPage + 1)} className="px-3 py-1 text-sm rounded hover:bg-gray-100">
                ›
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
