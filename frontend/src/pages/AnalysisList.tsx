import { useEffect, useState, useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getAnalyses, downloadExcel, type AnalysisFilters } from '../lib/api';
import type { Analysis, PaginatedResponse } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';

export default function AnalysisList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<PaginatedResponse<Analysis> | null>(null);
  const [loading, setLoading] = useState(true);

  const filters = useMemo<AnalysisFilters>(() => ({
    suitability: searchParams.get('suitability') || undefined,
    case_category: searchParams.get('case_category') || undefined,
    stage: searchParams.get('stage') || undefined,
    search: searchParams.get('search') || undefined,
    ordering: searchParams.get('ordering') || '-analyzed_at',
    page: Number(searchParams.get('page')) || 1,
    include_irrelevant: searchParams.get('include_irrelevant') || undefined,
    group_by_case: searchParams.get('group_by_case') !== 'false' ? 'true' : undefined,
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
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.delete('page');
    setSearchParams(params);
  };

  const setPage = (page: number) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', String(page));
    setSearchParams(params);
  };

  const currentPage = Number(searchParams.get('page')) || 1;
  const totalPages = data ? Math.ceil(data.count / 20) : 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold">분석 목록</h1>

      {/* 필터 바 */}
      <div className="bg-white rounded-xl border border-border p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">검색</label>
          <input
            type="text"
            placeholder="기사 제목, 상대방..."
            className="border rounded px-3 py-1.5 text-sm w-52"
            defaultValue={filters.search}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setFilter('search', (e.target as HTMLInputElement).value);
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
            value={filters.ordering || '-analyzed_at'}
            onChange={(e) => setFilter('ordering', e.target.value)}
          >
            <option value="-analyzed_at">최신 분석순</option>
            <option value="-article__published_at">최신 기사순</option>
            <option value="-damage_amount_num">피해 규모 큰 순</option>
            <option value="-victim_count_num">피해자 많은 순</option>
          </select>
        </div>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={searchParams.get('group_by_case') !== 'false'}
            onChange={(e) => setFilter('group_by_case', e.target.checked ? '' : 'false')}
            className="rounded"
          />
          사건별 묶기
        </label>
        <label className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={filters.include_irrelevant === 'true'}
            onChange={(e) => setFilter('include_irrelevant', e.target.checked ? 'true' : '')}
            className="rounded"
          />
          무관 기사 포함
        </label>
        <button
          onClick={() => downloadExcel(filters)}
          className="ml-auto bg-navy text-white text-sm px-4 py-1.5 rounded hover:opacity-90"
        >
          📥 엑셀 다운로드
        </button>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl border border-border overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400">로딩 중...</div>
        ) : (
          <>
            <div className="px-4 py-2 text-xs text-gray-500 border-b">
              총 {data?.count || 0}건
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500 bg-gray-50">
                    <th className="px-4 py-2">적합도</th>
                    <th className="px-4 py-2">기사 제목</th>
                    <th className="px-4 py-2">분야</th>
                    <th className="px-4 py-2">피해자</th>
                    <th className="px-4 py-2">상대방</th>
                    <th className="px-4 py-2">피해액</th>
                    <th className="px-4 py-2">단계</th>
                    <th className="px-4 py-2">케이스</th>
                    <th className="px-4 py-2">날짜</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.results.map((a) => (
                    <tr key={a.id} className={`border-b last:border-0 hover:bg-[#F8FAFC] cursor-pointer ${!a.is_relevant ? 'opacity-50 bg-gray-50' : ''}`}>
                      <td className="px-4 py-2.5"><SuitabilityBadge value={a.suitability} /></td>
                      <td className="px-4 py-2.5 max-w-xs">
                        <div className="flex items-center gap-1.5">
                          <Link to={`/analyses/${a.id}`} className="hover:text-blue-600 line-clamp-1">
                            {a.article_title}
                          </Link>
                          {(a.related_count ?? 0) > 1 && (
                            <span className="shrink-0 text-[11px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">
                              +{(a.related_count ?? 0) - 1}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-gray-600">{a.case_category}</td>
                      <td className="px-4 py-2.5 text-gray-600">{a.victim_count || '-'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{a.defendant || '-'}</td>
                      <td className="px-4 py-2.5 text-gray-600">{a.damage_amount || '-'}</td>
                      <td className="px-4 py-2.5"><StageBadge value={a.stage} /></td>
                      <td className="px-4 py-2.5 text-xs text-gray-500">{a.case_id || '-'}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-400">{a.published_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                  {data?.results.length === 0 && (
                    <tr><td colSpan={9} className="py-8 text-center text-gray-400">결과가 없습니다</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* 페이지네이션 */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-1 py-3 border-t">
                {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`px-3 py-1 text-sm rounded ${
                      p === currentPage
                        ? 'bg-navy text-white'
                        : 'hover:bg-gray-100'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
