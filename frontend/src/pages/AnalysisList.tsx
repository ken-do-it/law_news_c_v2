import { useEffect, useCallback, useMemo, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getAnalyses, getCaseGroups, downloadExcel, downloadExcelCase, type AnalysisFilters, type CaseGroupFilters } from '../lib/api';
import { useState } from 'react';
import type { Analysis, CaseGroup, PaginatedResponse } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';
import TableSkeleton from '../components/TableSkeleton';

// 목록용 피해액 요약 — 괄호 내용 제거 후 앞부분만 표시
function shortenDamageAmount(s: string | null | undefined): string {
  if (!s) return '—';
  const withoutParen = s.replace(/\s*\([^)]*\)\s*$/, '').trim();
  if (withoutParen.length <= 14) return withoutParen;
  return withoutParen.slice(0, 12) + '…';
}

// 정렬 헤더 컴포넌트
function SortTh({
  label,
  field,
  currentOrdering,
  onSort,
  className,
}: {
  label: string;
  field: string;
  currentOrdering: string;
  onSort: (field: string) => void;
  className?: string;
}) {
  const isDesc = currentOrdering === `-${field}`;
  const isAsc = currentOrdering === field;
  const isActive = isAsc || isDesc;
  return (
    <th
      className={`px-3 py-3 text-xs font-semibold tracking-wide whitespace-nowrap cursor-pointer select-none transition-colors ${
        isActive ? 'text-navy' : 'text-gray-400 hover:text-gray-600'
      } ${className ?? ''}`}
      onClick={() => onSort(field)}
    >
      {label}
      <span className="ml-1 inline-block w-3 text-center">
        {isDesc ? '↓' : isAsc ? '↑' : <span className="text-gray-200">↕</span>}
      </span>
    </th>
  );
}

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

function matchesExclude(item: Analysis, exclude: string): boolean {
  const lower = exclude.trim().toLowerCase();
  if (!lower) return false;
  const isCaseId = /^case-\d{4}-\d{3}$/i.test(lower);
  if (isCaseId && item.case_id) {
    return item.case_id.toLowerCase() === lower;
  }
  return (item.article_title?.toLowerCase().includes(lower) ?? false) || (item.defendant?.toLowerCase().includes(lower) ?? false) || (item.case_id?.toLowerCase().includes(lower) ?? false);
}

type ViewMode = 'case' | 'standalone';

export default function AnalysisList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const viewMode: ViewMode = (searchParams.get('view') as ViewMode) || 'case';
  const [data, setData] = useState<PaginatedResponse<Analysis> | null>(null);
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

  const filters = useMemo<AnalysisFilters>(() => {
    const search = searchParams.get('search') || undefined;
    const groupByCaseParam = searchParams.get('group_by_case');
    // case_id로 검색 시(CASE-YYYY-NNN) 같은 사건의 모든 기사 표시를 위해 묶기 해제
    const isCaseIdSearch = search && /^CASE-\d{4}-\d{3}$/i.test(search.trim());
    const group_by_case = isCaseIdSearch
      ? 'false'
      : groupByCaseParam !== 'false'
        ? 'true'
        : undefined;
    return {
      suitability: searchParams.get('suitability') || undefined,
      case_category: searchParams.get('case_category') || undefined,
      stage: searchParams.get('stage') || undefined,
      search,
      ordering: searchParams.get('ordering') || '-analyzed_at',
      page: Number(searchParams.get('page')) || 1,
      include_irrelevant: searchParams.get('include_irrelevant') || undefined,
      group_by_case,
    };
  }, [searchParams]);

  const caseFilters = useMemo<CaseGroupFilters>(() => ({
    search: searchParams.get('search') || undefined,
    ordering: searchParams.get('ordering') || '-created_at',
    page: Number(searchParams.get('page')) || 1,
  }), [searchParams]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      if (viewMode === 'case') {
        const result = await getCaseGroups(caseFilters);
        setCaseData(result);
        setData(null);
      } else {
        const result = await getAnalyses({ ...filters, standalone: true });
        setData(result);
        setCaseData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [viewMode, filters, caseFilters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const setFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) { params.set(key, value); } else { params.delete(key); }
    params.delete('page');
    setSearchParams(params);
  };

  const setViewMode = (v: ViewMode) => {
    const params = new URLSearchParams(searchParams);
    params.set('view', v);
    params.delete('page');
    setSearchParams(params);
  };

  const handleSort = (field: string) => {
    const current = filters.ordering || '-analyzed_at';
    const next = current === `-${field}` ? field : `-${field}`;
    setFilter('ordering', next);
  };

  const setPage = (page: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(page));
    setSearchParams(params);
  };

  const currentPage = Number(searchParams.get('page')) || 1;
  const totalPages = viewMode === 'case'
    ? (caseData ? Math.ceil(caseData.count / 20) : 0)
    : (data ? Math.ceil(data.count / 20) : 0);
  const currentOrdering = filters.ordering || '-analyzed_at';

  const filteredCaseResults = useMemo(() => {
    if (!caseData?.results) return [];
    if (excludeList.length === 0) return caseData.results;
    return caseData.results.filter((c) => !excludeList.some((ex) =>
      c.case_id.toLowerCase().includes(ex.trim().toLowerCase()) || c.name.toLowerCase().includes(ex.trim().toLowerCase())
    ));
  }, [caseData?.results, excludeList]);

  const filteredResults = useMemo(() => {
    if (!data?.results) return [];
    if (excludeList.length === 0) return data.results;
    return data.results.filter((a) => !excludeList.some((ex) => matchesExclude(a, ex)));
  }, [data?.results, excludeList]);

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

  // 활성 필터 칩 정의
  const activeChips = [
    filters.search && { key: 'search', label: `"${filters.search}"` },
    filters.suitability && { key: 'suitability', label: `적합도: ${filters.suitability}` },
    filters.stage && { key: 'stage', label: `단계: ${filters.stage}` },
    filters.case_category && { key: 'case_category', label: `분야: ${filters.case_category}` },
  ].filter(Boolean) as { key: string; label: string }[];

  const clearAllFilters = () => {
    const params = new URLSearchParams();
    if (searchParams.get('group_by_case')) params.set('group_by_case', searchParams.get('group_by_case')!);
    setSearchParams(params);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">분석 목록</h1>
        <div className="flex rounded-lg border border-gray-200 overflow-hidden">
          <button
            type="button"
            onClick={() => setViewMode('case')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              viewMode === 'case' ? 'bg-navy text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            사건별
          </button>
          <button
            type="button"
            onClick={() => setViewMode('standalone')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              viewMode === 'standalone' ? 'bg-navy text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            단독 기사
          </button>
        </div>
      </div>

      {/* 필터 바 */}
      <div className="bg-white rounded-xl border border-border p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            검색
            <span className="ml-1 text-gray-400 font-normal">기사 제목 · 상대방 · 케이스 ID</span>
          </label>
          <input
            key={filters.search ?? 'empty'}
            type="text"
            placeholder="예: 쿠팡, CASE-2026-001..."
            className="border rounded px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-1 focus:ring-gold"
            defaultValue={filters.search}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setFilter('search', (e.target as HTMLInputElement).value.trim());
            }}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">적합도</label>
          <select
            className="border rounded px-3 py-1.5 text-sm"
            value={filters.suitability || ''}
            onChange={(e) => setFilter('suitability', e.target.value)}
          >
            <option value="">전체</option>
            <option value="High,Medium">High + Medium</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">단계</label>
          <select
            className="border rounded px-3 py-1.5 text-sm"
            value={filters.stage || ''}
            onChange={(e) => setFilter('stage', e.target.value)}
          >
            <option value="">전체</option>
            <option value="피해 발생">피해 발생</option>
            <option value="관련 절차 진행">관련 절차 진행</option>
            <option value="소송중">소송중</option>
            <option value="판결 선고">판결 선고</option>
            <option value="종결">종결</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">정렬</label>
          <select
            className="border rounded px-3 py-1.5 text-sm"
            value={currentOrdering}
            onChange={(e) => setFilter('ordering', e.target.value)}
          >
            <option value="-analyzed_at">최신 분석순</option>
            <option value="-article__published_at">최신 기사순</option>
            <option value="-damage_amount_num">피해 규모 큰 순</option>
            <option value="-victim_count_num">피해자 많은 순</option>
          </select>
        </div>
        {viewMode === 'standalone' && (
          <label className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={searchParams.get('group_by_case') !== 'false'}
              onChange={(e) => setFilter('group_by_case', e.target.checked ? '' : 'false')}
              className="w-6 h-6 accent-navy rounded cursor-pointer"
            />
            사건별 묶기
          </label>
        )}
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={filters.include_irrelevant === 'true'}
            onChange={(e) => setFilter('include_irrelevant', e.target.checked ? 'true' : '')}
            className="w-6 h-6 accent-navy rounded cursor-pointer"
          />
          무관 기사 포함
        </label>
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
          onClick={() => viewMode === 'case' ? downloadExcelCase(caseFilters) : downloadExcel(filters)}
          className="ml-auto bg-navy text-white text-sm px-4 py-1.5 rounded hover:opacity-90"
        >
          📥 엑셀 다운로드 {viewMode === 'case' ? '(사건)' : '(기사)'}
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
          <span>총 {viewMode === 'case' ? (caseData?.count ?? '—') : (data?.count ?? '—')}건</span>
          {excludeList.length > 0 && (
            <span className="text-amber-600">
              제외 적용: {viewMode === 'case' ? filteredCaseResults.length : filteredResults.length}건 표시
            </span>
          )}
        </div>
        <div className="overflow-hidden">
          {viewMode === 'case' ? (
            <table className="w-full text-sm table-fixed">
              <thead>
                <tr className="border-b text-left bg-gray-50">
                  <th className="w-[12%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">케이스 ID</th>
                  <th className="w-[35%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide">사건명</th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">기사 수</th>
                  <th className="w-[15%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">심사 결과</th>
                  <th className="w-[14%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">심사 완료</th>
                  <th className="w-[14%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">통과</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <TableSkeleton cols={6} rows={10} />
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
                          <SuitabilityBadge value={c.client_suitability ?? 'Low'} />
                        </td>
                        <td className="px-2 py-2.5 text-sm">{c.review_completed ? '✓' : '—'}</td>
                        <td className="px-2 py-2.5 text-sm">{c.accepted ? '✓' : '—'}</td>
                      </tr>
                    ))}
                    {filteredCaseResults.length === 0 && !loading && (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-gray-400">
                          결과가 없습니다
                        </td>
                      </tr>
                    )}
                  </>
                )}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-sm table-fixed">
              <thead>
                <tr className="border-b text-left bg-gray-50">
                  <th className="w-16 px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">적합도</th>
                  <th className="w-[28%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide">기사 제목</th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">분야</th>
                  <th className="w-[8%] px-2 py-3"><SortTh label="피해자" field="victim_count_num" currentOrdering={currentOrdering} onSort={handleSort} /></th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">상대방</th>
                  <th className="w-[9%] px-2 py-3"><SortTh label="피해액" field="damage_amount_num" currentOrdering={currentOrdering} onSort={handleSort} /></th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">단계</th>
                  <th className="w-[10%] px-2 py-3 text-xs font-semibold text-gray-400 tracking-wide whitespace-nowrap">케이스</th>
                  <th className="w-[9%] px-2 py-3"><SortTh label="날짜" field="article__published_at" currentOrdering={currentOrdering} onSort={handleSort} /></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <TableSkeleton cols={9} rows={10} />
                ) : (
                  <>
                    {filteredResults.map((a) => (
                      <tr
                        key={a.id}
                      className={`border-b last:border-0 hover:bg-gray-50 transition-colors ${!a.is_relevant ? 'opacity-50 bg-gray-50' : ''}`}
                    >
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        <SuitabilityBadge value={a.suitability ?? 'Low'} />
                      </td>
                      <td className="px-2 py-2.5 overflow-hidden">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <Link to={`/analyses/${a.id}`} className="hover:text-blue-600 truncate block min-w-0" title={a.article_title}>
                            {a.article_title}
                          </Link>
                          {(a.related_count ?? 0) > 1 && (
                            <span className="shrink-0 text-[11px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-medium whitespace-nowrap">
                              +{(a.related_count ?? 0) - 1}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-gray-600 truncate" title={a.case_category}>{a.case_category}</td>
                      <td className="px-2 py-2.5 text-gray-600 truncate" title={a.victim_count || undefined}>{a.victim_count || '—'}</td>
                      <td className="px-2 py-2.5 text-gray-600 truncate" title={a.defendant || undefined}>{a.defendant || '—'}</td>
                      <td
                        className="px-2 py-2.5 text-gray-600 truncate"
                        title={a.damage_amount || undefined}
                      >
                        {shortenDamageAmount(a.damage_amount)}
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap"><StageBadge value={a.stage} /></td>
                      {/* 케이스 ID — 클릭하면 해당 케이스 검색 */}
                      <td className="px-2 py-2.5 text-xs truncate">
                        {a.case_id ? (
                          <button
                            onClick={() => setFilter('search', a.case_id!)}
                            className="text-blue-600 hover:underline font-mono"
                            title="이 케이스 전체 보기"
                          >
                            {a.case_id}
                          </button>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                        {a.published_at?.slice(0, 10)}
                      </td>
                    </tr>
                    ))}
                    {filteredResults.length === 0 && (
                    <tr>
                      <td colSpan={9} className="py-12 text-center text-gray-400">
                        결과가 없습니다
                        {activeChips.length > 0 && (
                          <button
                            onClick={clearAllFilters}
                            className="ml-2 text-blue-600 hover:underline text-sm"
                          >
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
          )}
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
