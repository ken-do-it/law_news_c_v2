import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from 'recharts';
import { getStats, getAnalyses } from '../lib/api';
import type { DashboardStats, Analysis } from '../lib/types';
import StatsCard from '../components/StatsCard';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';

const PIE_COLORS: Record<string, string> = {
  High: '#E11D48',
  Medium: '#D97706',
  Low: '#6B7280',
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recent, setRecent] = useState<Analysis[]>([]);

  useEffect(() => {
    getStats().then(setStats);
    getAnalyses({ ordering: '-analyzed_at' }).then((r) => setRecent(r.results.slice(0, 5)));
  }, []);

  if (!stats) return <div className="p-8 text-center text-gray-400">로딩 중...</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">대시보드</h1>
        <p className="text-gray-500 text-sm mt-1">AI 기반 법률 뉴스 분석 현황을 한눈에 확인하세요</p>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard icon="📰" label="오늘 수집" value={stats.today_collected} sub="건" />
        <StatsCard icon="🔴" label="High 적합" value={stats.today_high} sub="건" />
        <StatsCard icon="✅" label="분석 완료" value={stats.total_analyzed} sub="전체" />
        <StatsCard icon="💰" label="이번 달 비용" value={`₩${stats.monthly_cost.toLocaleString()}`} />
      </div>

      {/* 차트 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 적합도 분포 파이차트 */}
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
          <h3 className="text-sm font-semibold mb-4">적합도 분포</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={stats.suitability_distribution} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={2}>
                {stats.suitability_distribution.map((entry) => (
                  <Cell key={entry.name} fill={PIE_COLORS[entry.name] || '#ccc'} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* 사건 분야별 바차트 */}
        <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
          <h3 className="text-sm font-semibold mb-4">사건 분야별 분포</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.category_distribution} layout="vertical" margin={{ left: 60 }}>
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--color-gold)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 주간 추이 */}
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
        <h3 className="text-sm font-semibold mb-4">주간 수집 추이</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={stats.weekly_trend}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="total" stroke="var(--color-navy)" name="전체" />
            <Line type="monotone" dataKey="high" stroke="var(--color-high)" name="High" />
            <Line type="monotone" dataKey="medium" stroke="var(--color-medium)" name="Medium" strokeDasharray="5 5" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 최근 분석 결과 */}
      <div className="bg-white rounded-xl border border-[var(--color-border)] p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">최근 분석 결과</h3>
          <Link to="/analyses" className="text-xs text-blue-600 hover:underline">전체 보기 →</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2 pr-3">적합도</th>
                <th className="pb-2 pr-3">기사 제목</th>
                <th className="pb-2 pr-3">분야</th>
                <th className="pb-2 pr-3">상대방</th>
                <th className="pb-2 pr-3">단계</th>
                <th className="pb-2">날짜</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((a) => (
                <tr key={a.id} className="border-b last:border-0 hover:bg-gray-50 cursor-pointer">
                  <td className="py-2.5 pr-3"><SuitabilityBadge value={a.suitability} /></td>
                  <td className="py-2.5 pr-3">
                    <Link to={`/analyses/${a.id}`} className="hover:text-blue-600 line-clamp-1">
                      {a.article_title}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-3 text-gray-600">{a.case_category}</td>
                  <td className="py-2.5 pr-3 text-gray-600">{a.defendant || '-'}</td>
                  <td className="py-2.5 pr-3"><StageBadge value={a.stage} /></td>
                  <td className="py-2.5 text-gray-400 text-xs">{a.published_at?.slice(0, 10)}</td>
                </tr>
              ))}
              {recent.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-gray-400">분석 데이터가 없습니다</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
