import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAnalysis, reanalyze, downloadExcel } from '../lib/api';
import type { Analysis } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';

const reasonBg: Record<string, string> = {
  High: 'rgba(225,29,72,0.04)',
  Medium: 'rgba(245,158,11,0.04)',
  Low: 'rgba(107,114,128,0.04)',
};

export default function AnalysisDetail() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [reanalyzing, setReanalyzing] = useState(false);

  useEffect(() => {
    if (id) getAnalysis(Number(id)).then(setAnalysis);
  }, [id]);

  if (!analysis) return <div className="p-8 text-center text-gray-400">로딩 중...</div>;

  const article = analysis.article;

  const handleReanalyze = async () => {
    if (!article) return;
    setReanalyzing(true);
    try {
      await reanalyze(article.id);
      alert('재분석 요청이 접수되었습니다.');
    } catch {
      alert('재분석 요청 실패');
    } finally {
      setReanalyzing(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <Link to="/analyses" className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        ← 목록으로 돌아가기
      </Link>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* 왼쪽: 기사 + AI 분석 */}
        <div className="flex-1 space-y-4">
          {/* 기사 헤더 */}
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
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
              <span>{article?.source?.name || article?.source_name}</span>
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
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-6">
            <h2 className="text-sm font-semibold mb-3">🤖 AI 분석 요약</h2>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {analysis.summary}
            </p>
          </div>

          {/* 판단 근거 */}
          <div
            className="rounded-xl border border-[var(--color-border)] p-6"
            style={{ backgroundColor: reasonBg[analysis.suitability] || '#fff' }}
          >
            <h2 className="text-sm font-semibold mb-3">📋 판단 근거</h2>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
              {analysis.suitability_reason}
            </p>
          </div>
        </div>

        {/* 오른쪽: 상세 카드 (sticky) */}
        <div className="lg:w-[380px]">
          <div className="bg-white rounded-xl border border-[var(--color-border)] p-6 lg:sticky lg:top-6 space-y-4">
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

            <div className="border-t pt-4 space-y-2">
              <button
                onClick={handleReanalyze}
                disabled={reanalyzing}
                className="w-full bg-[var(--color-navy)] text-white text-sm py-2 rounded hover:opacity-90 disabled:opacity-50"
              >
                {reanalyzing ? '요청 중...' : '🔄 재분석 요청'}
              </button>
              <button
                onClick={() => downloadExcel({})}
                className="w-full border border-[var(--color-border)] text-sm py-2 rounded hover:bg-gray-50"
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
