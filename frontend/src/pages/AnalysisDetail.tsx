import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAnalysis, reanalyze, downloadExcel, updateReview } from '../lib/api';
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

export default function AnalysisDetail() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [reviewSaving, setReviewSaving] = useState(false);

  useEffect(() => {
    if (id) getAnalysis(Number(id)).then(setAnalysis);
  }, [id]);

  useEffect(() => {
    if (analysis) {
      const title = analysis.article?.title ?? analysis.article_title ?? '';
      document.title = `${title.slice(0, 40)} | LawNGood`;
    }
  }, [analysis]);

  if (!analysis) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="text-gray-200 text-5xl mb-3 animate-pulse">◌</div>
          <div className="text-gray-400 text-sm">로딩 중...</div>
        </div>
      </div>
    );
  }

  const article = analysis.article;

  const handleReanalyze = async () => {
    if (!article) return;
    setReanalyzing(true);
    try {
      await reanalyze(article.id);
      toast('재분석 요청이 접수되었습니다.', 'info');
    } catch {
      toast('재분석 요청에 실패했습니다.', 'error');
    } finally {
      setReanalyzing(false);
    }
  };

  const handleReviewChange = async (
    field: 'review_completed' | 'client_suitability' | 'accepted',
    value: boolean | 'High' | 'Medium' | 'Low' | null,
  ) => {
    // 낙관적 업데이트
    const extraPayload: Partial<Analysis> = {};
    if (field === 'review_completed' && value === true && !analysis.client_suitability) {
      extraPayload.client_suitability = analysis.suitability;
    }
    setAnalysis((prev) => prev ? { ...prev, [field]: value, ...extraPayload } : prev);

    setReviewSaving(true);
    try {
      const updated = await updateReview(Number(id), { [field]: value, ...extraPayload });
      setAnalysis((prev) => prev ? { ...prev, ...updated } : prev);
      toast(field === 'accepted' && value ? '수임 통과로 설정되었습니다.' : '심사 상태가 저장되었습니다.');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { accepted?: string[] } } })
        ?.response?.data?.accepted?.[0];
      toast(msg ?? '저장에 실패했습니다.', 'error');
      // 실패 시 원래 값으로 되돌리기
      getAnalysis(Number(id)).then(setAnalysis);
    } finally {
      setReviewSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-4">
        <Link to="/analyses" className="text-sm text-blue-600 hover:underline">
          ← 목록으로 돌아가기
        </Link>
        {analysis.case_group && (
          <Link
            to={`/analyses/case/${analysis.case_group.case_id}`}
            className="text-sm text-blue-600 hover:underline"
          >
            이 사건 전체 보기 ({analysis.case_group.case_id})
          </Link>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* 왼쪽: 기사 + AI 분석 */}
        <div className="flex-1 space-y-4">
          {/* 기사 헤더 */}
          <div className="bg-white rounded-xl border border-border p-6">
            <div className="flex items-center gap-2 mb-3">
              <SuitabilityBadge value={analysis.suitability} />
              <StageBadge value={analysis.stage} />
              {analysis.case_group && (
                <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                  {analysis.case_group.case_id}
                </span>
              )}
            </div>
            <h1 className="text-xl font-bold mb-2">{article?.title}</h1>
            <div className="flex items-center gap-3 text-sm text-gray-500">
              <span>{article?.source_name}</span>
              <span>|</span>
              <span>{article?.published_at?.slice(0, 10)}</span>
              {article?.url && (
                <>
                  <span>|</span>
                  <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    🔗 원문 보기
                  </a>
                </>
              )}
            </div>
          </div>

          {/* AI 분석 요약 */}
          <div className="bg-white rounded-xl border border-border p-6">
            <h2 className="text-sm font-semibold mb-3">🤖 AI 분석 요약</h2>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {analysis.summary}
            </p>
          </div>

          {/* 판단 근거 */}
          <div
            className="rounded-xl border border-border p-6"
            style={{ backgroundColor: reasonBg[analysis.suitability] || '#fff' }}
          >
            <h2 className="text-sm font-semibold mb-3">📋 판단 근거</h2>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {analysis.suitability_reason}
            </p>
          </div>

          {/* 유사 기사 목록 */}
          {analysis.related_articles && analysis.related_articles.length > 0 && (
            <div className="bg-white rounded-xl border border-border p-6">
              <h2 className="text-sm font-semibold mb-4">
                📰 유사 기사 ({analysis.related_articles.length}건)
                {analysis.case_group && (
                  <span className="ml-2 text-xs font-normal text-gray-500">
                    {analysis.case_group.case_id} — {analysis.case_group.name}
                  </span>
                )}
              </h2>
              <div className="space-y-3">
                {analysis.related_articles.map((ra) => (
                  <div key={ra.id} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                    <div className="flex items-start gap-2">
                      <SuitabilityBadge value={ra.suitability} />
                      <div className="flex-1 min-w-0">
                        <Link
                          to={`/analyses/${ra.id}`}
                          className="text-sm font-medium text-gray-800 hover:text-blue-600 line-clamp-1"
                        >
                          {ra.article_title}
                        </Link>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{ra.summary}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                          <span>{ra.source_name}</span>
                          <span>{ra.published_at?.slice(0, 10)}</span>
                          <a href={ra.article_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">원문</a>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 오른쪽: 상세 카드 (sticky) */}
        <div className="lg:w-[380px]">
          <div className="bg-white rounded-xl border border-border p-6 lg:sticky lg:top-6 space-y-4">
            <h2 className="text-sm font-semibold border-b pb-2">분석 상세 정보</h2>

            <DetailRow icon="🎯" label="적합도" value={<SuitabilityBadge value={analysis.suitability} />} />
            <DetailRow icon="📁" label="사건 분야" value={analysis.case_category} />
            <DetailRow icon="🏢" label="상대방" value={analysis.defendant || '-'} />
            <DetailRow icon="💰" label="피해 규모" value={analysis.damage_amount || '미상'} />
            <DetailRow icon="👥" label="피해자 수" value={analysis.victim_count || '미상'} />
            <DetailRow icon="📊" label="진행 단계" value={<StageBadge value={analysis.stage} />} />
            <DetailRow icon="📝" label="단계 상세" value={analysis.stage_detail || '-'} />
            {analysis.case_group && (
              <DetailRow icon="🔗" label="사건 그룹" value={`${analysis.case_group.case_id} — ${analysis.case_group.name}`} />
            )}

            {/* 로앤굿 심사 섹션 */}
            <div className={`border-t pt-4 space-y-3 ${reviewSaving ? 'opacity-60 pointer-events-none' : ''}`}>
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                로앤굿 심사
                {reviewSaving && <span className="ml-2 font-normal text-gray-400">저장 중...</span>}
              </div>

              <div className="space-y-1">
                <div className="text-xs text-gray-400">심사 결과</div>
                <ClientSuitabilityButtons
                  value={analysis.client_suitability}
                  onChange={(v) => handleReviewChange('client_suitability', v)}
                  disabled={reviewSaving}
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={analysis.review_completed}
                    onChange={(e) => handleReviewChange('review_completed', e.target.checked)}
                    className="w-6 h-6 accent-navy cursor-pointer"
                  />
                  <span className="text-sm">심사 완료</span>
                </label>
                <label
                  className={`flex items-center gap-2 select-none ${
                    analysis.review_completed ? 'cursor-pointer' : 'cursor-not-allowed opacity-40'
                  }`}
                  title={!analysis.review_completed ? '심사 완료 후 체크 가능합니다' : undefined}
                >
                  <input
                    type="checkbox"
                    checked={analysis.accepted}
                    disabled={!analysis.review_completed || reviewSaving}
                    onChange={(e) => handleReviewChange('accepted', e.target.checked)}
                    className="w-6 h-6 accent-gold cursor-pointer disabled:cursor-not-allowed"
                  />
                  <span className="text-sm">통과</span>
                </label>
              </div>
            </div>

            <div className="border-t pt-4 space-y-2">
              <button
                onClick={handleReanalyze}
                disabled={reanalyzing}
                className="w-full bg-navy text-white text-sm py-2 rounded hover:opacity-90 disabled:opacity-50"
              >
                {reanalyzing ? '요청 중...' : '🔄 재분석 요청'}
              </button>
              <button
                onClick={() => downloadExcel({})}
                className="w-full border border-border text-sm py-2 rounded hover:bg-gray-50"
              >
                📥 엑셀 내보내기
              </button>
            </div>

            <div className="text-xs text-gray-400 pt-2 border-t">
              <div>모델: {analysis.llm_model}</div>
              <div>분석일: {analysis.analyzed_at?.slice(0, 16).replace('T', ' ')}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailRow({ icon, label, value }: { icon: string; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-sm">{icon}</span>
      <div>
        <div className="text-xs text-gray-500">{label}</div>
        <div className="text-sm font-medium mt-0.5">{value}</div>
      </div>
    </div>
  );
}
