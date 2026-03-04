import type { ReactNode } from 'react';
import { useEffect, useState, useRef } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { getCaseGroupByCaseId, getAnalysis, updateCaseGroupReview, downloadExcel } from '../lib/api';
import type { CaseGroupDetail, ReviewPayload } from '../lib/api';
import type { Analysis } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';
import ClientSuitabilityButtons from '../components/ClientSuitabilityButtons';
import { useToast } from '../components/Toast';

const reasonBg: Record<string, string> = {
  High: 'rgba(225,29,72,0.04)',
  Medium: 'rgba(245,158,11,0.04)',
  Low: 'rgba(107,114,128,0.04)',
};

export default function CaseDetail() {
  const { case_id } = useParams<{ case_id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const articleId = searchParams.get('article');
  const articleRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const userCollapsedRef = useRef(false);
  const { toast } = useToast();
  const [caseGroup, setCaseGroup] = useState<CaseGroupDetail | null>(null);
  const [selectedAnalysis, setSelectedAnalysis] = useState<Analysis | null>(null);
  const [reviewSaving, setReviewSaving] = useState(false);

  useEffect(() => {
    if (articleId) getAnalysis(Number(articleId)).then(setSelectedAnalysis);
    else setSelectedAnalysis(null);
  }, [articleId]);

  useEffect(() => {
    if (case_id) getCaseGroupByCaseId(case_id).then(setCaseGroup);
  }, [case_id]);

  // article 미선택 시 첫 기사 자동 선택 → 상세(상대방, 피해액 등) 바로 표시 (접기 후에는 재선택 안 함)
  useEffect(() => {
    if (!caseGroup || articleId || userCollapsedRef.current) return;
    const first = caseGroup.analyses[0];
    if (first) {
      setSearchParams((p) => {
        const next = new URLSearchParams(p);
        next.set('article', String(first.id));
        return next;
      }, { replace: true });
    }
  }, [caseGroup, articleId, setSearchParams]);

  useEffect(() => {
    userCollapsedRef.current = false;
  }, [case_id]);

  useEffect(() => {
    if (caseGroup && articleId) {
      const id = Number(articleId);
      const el = articleRefs.current[id];
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [caseGroup, articleId]);

  useEffect(() => {
    if (caseGroup) {
      document.title = `${caseGroup.case_id} — ${caseGroup.name} | LawNGood`;
    }
  }, [caseGroup]);

  const handleReviewChange = async (
    field: 'review_completed' | 'client_suitability' | 'accepted',
    value: boolean | 'High' | 'Medium' | 'Low' | null,
  ) => {
    if (!caseGroup) return;
    const extraPayload: Partial<ReviewPayload> = {};
    if (field === 'review_completed' && value === true && !caseGroup.client_suitability) {
      const dist = caseGroup.suitability_distribution;
      const suit = dist?.High ? 'High' : dist?.Medium ? 'Medium' : 'Low';
      extraPayload.client_suitability = suit;
    }
    setCaseGroup((prev) => prev ? { ...prev, [field]: value, ...extraPayload } : prev);
    setReviewSaving(true);
    try {
      const updated = await updateCaseGroupReview(caseGroup.id, { [field]: value, ...extraPayload });
      setCaseGroup(updated);
      toast(field === 'accepted' && value ? '수임 통과로 설정되었습니다.' : '심사 상태가 저장되었습니다.');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { accepted?: string[] } } })
        ?.response?.data?.accepted?.[0];
      toast(msg ?? '저장에 실패했습니다.', 'error');
      getCaseGroupByCaseId(case_id!).then(setCaseGroup);
    } finally {
      setReviewSaving(false);
    }
  };

  if (!caseGroup) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="text-gray-200 text-5xl mb-3 animate-pulse">◌</div>
          <div className="text-gray-400 text-sm">로딩 중...</div>
        </div>
      </div>
    );
  }

  const dist = caseGroup.suitability_distribution || {};

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <Link to="/analyses" className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        ← 목록으로 돌아가기
      </Link>

      <div className="flex flex-col lg:flex-row gap-6">
        <div className="flex-1 space-y-4">
          {/* 사건 헤더 */}
          <div className="bg-white rounded-xl border border-border p-6">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-mono text-navy font-semibold">{caseGroup.case_id}</span>
              <span className="text-xs text-gray-500">· 기사 {caseGroup.article_count}건</span>
            </div>
            <h1 className="text-xl font-bold mb-2">{caseGroup.name}</h1>
            {caseGroup.description && (
              <p className="text-sm text-gray-600">{caseGroup.description}</p>
            )}
            <div className="flex flex-wrap gap-2 mt-3">
              {dist.High != null && (
                <span className="text-xs bg-red-50 text-red-700 px-2 py-0.5 rounded">
                  High {dist.High}
                </span>
              )}
              {dist.Medium != null && (
                <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded">
                  Medium {dist.Medium}
                </span>
              )}
              {dist.Low != null && (
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  Low {dist.Low}
                </span>
              )}
            </div>
          </div>

          {/* 기사 목록 */}
          <div className="bg-white rounded-xl border border-border p-6">
            <h2 className="text-sm font-semibold mb-4">
              📰 소속 기사 ({caseGroup.analyses.length}건)
            </h2>
            <div className="space-y-3">
              {caseGroup.analyses.map((a) => (
                <div
                  key={a.id}
                  ref={(r) => { articleRefs.current[a.id] = r; }}
                  className={`border-b border-gray-100 pb-3 last:border-0 last:pb-0 ${articleId === String(a.id) ? 'ring-2 ring-navy ring-inset rounded-lg p-2 -m-2' : ''}`}
                >
                  <div className="flex items-start gap-2">
                    <SuitabilityBadge value={a.suitability} />
                    <div className="flex-1 min-w-0">
                      <Link
                        to={`/analyses/case/${case_id}?article=${a.id}`}
                        onClick={() => { userCollapsedRef.current = false; }}
                        className="text-sm font-medium text-gray-800 hover:text-blue-600 line-clamp-1"
                      >
                        {a.article_title}
                      </Link>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{a.summary}</p>
                      <div className="flex items-center gap-2 mt-1.5 text-xs">
                        <span className="text-gray-400">{a.source_name}</span>
                        <span className="text-gray-600 font-medium tabular-nums">{a.published_at?.slice(0, 10)}</span>
                        <a
                          href={a.article_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-500 hover:underline"
                        >
                          원문
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 선택된 기사 상세 (요약 + 판단 근거) */}
          {selectedAnalysis ? (
            <div className="bg-white rounded-xl border border-border p-6">
              <h2 className="text-sm font-semibold mb-3">📋 기사 상세 — {selectedAnalysis.article?.title?.slice(0, 40)}…</h2>
              <div className="flex items-center gap-2 mb-3">
                <SuitabilityBadge value={selectedAnalysis.suitability} />
                <StageBadge value={selectedAnalysis.stage} />
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line mb-4">
                {selectedAnalysis.summary}
              </p>
              <div
                className="rounded-lg p-4 border border-gray-100"
                style={{ backgroundColor: reasonBg[selectedAnalysis.suitability] || '#fff' }}
              >
                <div className="text-xs font-semibold text-gray-500 mb-1">판단 근거</div>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{selectedAnalysis.suitability_reason}</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  userCollapsedRef.current = true;
                  const p = new URLSearchParams(searchParams);
                  p.delete('article');
                  setSearchParams(p);
                }}
                className="inline-block mt-3 text-xs text-gray-400 hover:text-gray-600"
              >
                상세 접기
              </button>
            </div>
          ) : caseGroup.analyses.length > 0 && (
            <div className="bg-white rounded-xl border border-border p-4 text-center">
              <button
                type="button"
                onClick={() => {
                  userCollapsedRef.current = false;
                  const p = new URLSearchParams(searchParams);
                  p.set('article', String(caseGroup.analyses[0].id));
                  setSearchParams(p);
                }}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                상세 펴기
              </button>
            </div>
          )}
        </div>

        {/* 우측: 기사 메타 + 심사 카드 */}
        <div className="lg:w-[380px]">
          <div
            className={`bg-white rounded-xl border border-border p-6 lg:sticky lg:top-6 space-y-4 ${reviewSaving ? 'opacity-60 pointer-events-none' : ''}`}
          >
            {/* 선택된 기사 메타 정보 */}
            <h2 className="text-sm font-semibold border-b pb-2">기사 상세 정보</h2>

            {selectedAnalysis ? (
              <div className="space-y-3">
                <DetailItem icon="🎯" label="적합도" value={<SuitabilityBadge value={selectedAnalysis.suitability} />} />
                <DetailItem icon="📅" label="발행일" value={selectedAnalysis.published_at?.slice(0, 10) || '-'} />
                <DetailItem icon="📁" label="사건 분야" value={selectedAnalysis.case_category || '-'} />
                <DetailItem icon="🏢" label="상대방" value={selectedAnalysis.defendant || '-'} />
                <DetailItem icon="💰" label="피해 규모" value={selectedAnalysis.damage_amount || '미상'} />
                <DetailItem icon="👥" label="피해자 수" value={selectedAnalysis.victim_count || '미상'} />
                <DetailItem icon="📊" label="진행 단계" value={<StageBadge value={selectedAnalysis.stage} />} />
                <DetailItem icon="📝" label="단계 상세" value={selectedAnalysis.stage_detail || '-'} />
              </div>
            ) : (
              <p className="text-xs text-gray-400">
                왼쪽 기사 목록에서 하나를 선택하면 상세 정보가 여기 표시됩니다.
              </p>
            )}

            {/* 사건 단위 로앤굿 심사 */}
            <h2 className="text-sm font-semibold border-t pt-4 mt-2">로앤굿 심사 (사건 단위)</h2>

            <div className="space-y-1">
              <div className="text-xs text-gray-400">심사 결과</div>
              <ClientSuitabilityButtons
                value={caseGroup.client_suitability}
                onChange={(v) => handleReviewChange('client_suitability', v)}
                disabled={reviewSaving}
              />
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={caseGroup.review_completed}
                  onChange={(e) => handleReviewChange('review_completed', e.target.checked)}
                  className="w-6 h-6 accent-navy cursor-pointer"
                />
                <span className="text-sm">심사 완료</span>
              </label>
              <label
                className={`flex items-center gap-2 select-none ${
                  caseGroup.review_completed ? 'cursor-pointer' : 'cursor-not-allowed opacity-40'
                }`}
                title={!caseGroup.review_completed ? '심사 완료 후 체크 가능합니다' : undefined}
              >
                <input
                  type="checkbox"
                  checked={caseGroup.accepted}
                  disabled={!caseGroup.review_completed || reviewSaving}
                  onChange={(e) => handleReviewChange('accepted', e.target.checked)}
                  className="w-6 h-6 accent-gold cursor-pointer disabled:cursor-not-allowed"
                />
                <span className="text-sm">통과</span>
              </label>
            </div>

            <div className="border-t pt-4">
              <button
                onClick={() => downloadExcel({})}
                className="w-full border border-border text-sm py-2 rounded hover:bg-gray-50"
              >
                📥 엑셀 내보내기
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailItem({ icon, label, value }: { icon: string; label: string; value: ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-sm shrink-0">{icon}</span>
      <div className="min-w-0">
        <div className="text-xs text-gray-500">{label}</div>
        <div className="text-sm font-medium mt-0.5">{value}</div>
      </div>
    </div>
  );
}
