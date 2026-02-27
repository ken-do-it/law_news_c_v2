import { useEffect, useCallback, useMemo, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getCaseGroups, downloadExcelCase, type CaseGroupFilters } from '../lib/api';
import { useState } from 'react';
import type { CaseGroup, PaginatedResponse } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import AiSuitabilityDisplay from '../components/AiSuitabilityDisplay';
import TableSkeleton from '../components/TableSkeleton';

const EXCLUDE_STORAGE_KEY = 'lawngood-exclude-list';

function loadExcludeList(): string[] {
  try {
    const s = localStorage.getItem(EXCLUDE_STORAGE_KEY);
    return s ? JSON.parse(s) : [];
  } catch {
    return [];
  }
}

function saveExcludeList(list: string[]) {
  localStorage.setItem(EXCLUDE_STORAGE_KEY, JSON.stringify(list));
}

function matchesExcludeCase(c: CaseGroup, exclude: string): boolean {
  const lower = exclude.trim().toLowerCase();
  if (!lower) return false;
  return (c.case_id?.toLowerCase().includes(lower) ?? false) || (c.name?.toLowerCase().includes(lower) ?? false);
}

export default function AnalysisList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [caseData, setCaseData] = useState<PaginatedResponse<CaseGroup> | null>(null);
  const [loading, setLoading] = useState(true);
  const [excludeList, setExcludeList] = useState<string[]>(loadExcludeList);
  const [excludeInput, setExcludeInput] = useState('');
  const [showExcludeInput, setShowExcludeInput] = useState(false);
  const excludePanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => { document.title = '분석 목록 | LawNGood'; }, []);

  useEffect(() => {
    if (!showExcludeInput) return;
    const onOutside = (e: MouseEvent) => {
      if (excludePanelRef.current && !excludePanelRef.current.contains(e.target as Node)) {
        setShowExcludeInput(false);
      }
    };
    document.addEventListener('click', onOutside);
    return () => document.removeEventListener('click', onOutside);
  }, [showExcludeInput]);

  const caseFilters = useMemo<CaseGroupFilters>(() => ({
    search: searchParams.get('search') || undefined,
    ordering: searchParams.get('ordering') || '-article_count',
    page: Number(searchParams.get('page')) || 1,
  }), [searchParams]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getCaseGroups(caseFilters);
      setCaseData(result);
    } finally {
      setLoading(false);
    }
  }, [caseFilters]);

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

  const currentPage = Number(searchParams.get('page')) || 1;
  const totalPages = caseData ? Math.ceil(caseData.count / 20) : 0;

  const filteredCaseResults = useMemo(() => {
    if (!caseData?.results) return [];
    if (excludeList.length === 0) return caseData.results;
    return caseData.results.filter((c) => !excludeList.some((ex) => matchesExcludeCase(c, ex)));
  }, [caseData?.results, excludeList]);

  const addExclude = (value: string) => {
    const v = value.trim();
    if (!v || excludeList.includes(v)) return;
    const next = [...excludeList, v];
    setExcludeList(next);
    saveExcludeList(next);
    setExcludeInput('');
    setShowExcludeInput(false);
  };

  const removeExclude = (value: string) => {
    const next = excludeList.filter((x) => x !== value);
    setExcludeList(next);
    saveExcludeList(next);
  };

  const activeChips = [
    caseFilters.search && { key: 'search', label: `"${caseFilters.search}"` },
  ].filter(Boolean) as { key: string; label: string }[];

  const clearAllFilters = () => setSearchParams(new URLSearchParams());

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">분석 목록</h1>
        <p className="text-sm text-gray-500">case_id 기준 · 사건 클릭 시 소속 기사 전체 표시</p>
      </div>

      {/* 필터 바 */}
      <div className="bg-white rounded-xl border border-border p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            검색
            <span className="ml-1 text-gray-400 font-normal">케이스 ID · 사건명</span>
          </label>
          <input
            key={caseFilters.search ?? 'empty'}
            type="text"
            placeholder="예: 쿠팡, CASE-2026-001..."
            className="border rounded px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-1 focus:ring-gold"
            defaultValue={caseFilters.search}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setFilter('search', (e.target as HTMLInputElement).value.trim());
            }}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">정렬</label>
          <select
            className="border rounded px-3 py-1.5 text-sm"
            value={caseFilters.ordering || '-article_count'}
            onChange={(e) => setFilter('ordering', e.target.value)}
          >
            <option value="-article_count">기사 수 많은 순</option>
            <option value="-created_at">최신 등록순</option>
            <option value="case_id">케이스 ID순</option>
          </select>
        </div>
        <div className="relative" ref={excludePanelRef}>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setShowExcludeInput((v) => !v); }}
            className="text-sm text-gray-600 hover:text-navy border border-border rounded px-3 py-1.5"
          >
            {excludeList.length > 0 ? `제외: ${excludeList.length}개` : '제외 목록'}
          </button>
          {showExcludeInput && (
            <div className="absolute top-full left-0 mt-1 z-10 bg-white border border-border rounded-lg shadow-lg p-2 min-w-[200px]">
              <div className="flex gap-1 mb-2">
                <input
                  type="text"
                  value={excludeInput}
                  onChange={(e) => setExcludeInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') addExclude(excludeInput);
                  }}
                  placeholder="키워드 또는 CASE-2026-001"
                  className="border rounded px-2 py-1 text-sm flex-1"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => addExclude(excludeInput)}
                  className="bg-navy text-white text-sm px-2 py-1 rounded"
                >
                  추가
                </button>
              </div>
              {excludeList.length > 0 && (
                <div className="flex flex-wrap gap-1 text-xs">
                  {excludeList.map((ex) => (
                    <span
                      key={ex}
                      className="inline-flex items-center gap-0.5 bg-red-50 text-red-700 px-2 py-0.5 rounded"
                    >
                      {ex}
                      <button type="button" onClick={() => removeExclude(ex)} className="hover:text-red-900">✕</button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        <button
          onClick={() => downloadExcelCase(caseFilters)}
          className="ml-auto bg-navy text-white text-sm px-4 py-1.5 rounded hover:opacity-90"
        >
          📥 엑셀 다운로드
        </button>
      </div>

      {/* 활성 필터 칩 */}
      {activeChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-400">필터:</span>
          {activeChips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1 bg-navy text-white text-xs px-2.5 py-1 rounded-full"
            >
              {chip.label}
              <button
                onClick={() => setFilter(chip.key, '')}
                className="opacity-70 hover:opacity-100 ml-0.5 leading-none"
              >
                ✕
              </button>
            </span>
          ))}
          <button
            onClick={clearAllFilters}
            className="text-xs text-gray-400 hover:text-gray-600 underline underline-offset-2"
          >
            전체 초기화
          </button>
        </div>
      )}

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-2 text-xs text-gray-400 border-b flex justify-between">
          <span>총 {caseData?.count ?? '—'}건</span>
          {excludeList.length > 0 && (
            <span className="text-amber-600">
              제외 적용: {filteredCaseResults.length}건 표시
            </span>
          )}
        </div>
        <div className="overflow-hidden">
          <table className="w-full text-sm table-fixed">
              <thead>
                <tr className="border-b text-left bg-gray-50">
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">케이스 ID</th>
                  <th className="w-[28%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide">사건명</th>
                  <th className="w-[8%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">기사 수</th>
                  <th className="w-[14%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">AI 적합도</th>
                  <th className="w-[14%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">로앤굿 심사결과</th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">심사완료</th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">통과여부</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <TableSkeleton cols={7} rows={10} />
                ) : (
                  <>
                    {filteredCaseResults.map((c) => (
                      <tr key={c.id} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
                        <td className="px-2 py-2.5">
                          <Link
                            to={`/analyses/case/${c.case_id}`}
                            className="text-blue-600 hover:underline font-mono text-sm"
                          >
                            {c.case_id}
                          </Link>
                        </td>
                        <td className="px-2 py-2.5 truncate" title={c.name}>
                          <Link to={`/analyses/case/${c.case_id}`} className="hover:text-blue-600">
                            {c.name}
                          </Link>
                        </td>
                        <td className="px-2 py-2.5 text-gray-600">{c.article_count}</td>
                        <td className="px-2 py-2.5">
                          <AiSuitabilityDisplay dist={c.suitability_distribution} />
                        </td>
                        <td className="px-2 py-2.5">
                          {c.client_suitability ? <SuitabilityBadge value={c.client_suitability} /> : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-2 py-2.5 text-sm">{c.review_completed ? '✓' : '—'}</td>
                        <td className="px-2 py-2.5 text-sm">{c.accepted ? '✓' : '—'}</td>
                      </tr>
                    ))}
                    {filteredCaseResults.length === 0 && !loading && (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-gray-400">
                          결과가 없습니다
                          {activeChips.length > 0 && (
                            <button onClick={clearAllFilters} className="ml-2 text-blue-600 hover:underline text-sm">
                              필터 초기화
                            </button>
                          )}
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
