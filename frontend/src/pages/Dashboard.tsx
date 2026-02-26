import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, CartesianGrid, Legend, LabelList,
} from 'recharts';
import { getStats, getAnalyses } from '../lib/api';
import type { DashboardStats, Analysis, SchedulerState } from '../lib/types';
import SuitabilityBadge from '../components/SuitabilityBadge';
import StageBadge from '../components/StageBadge';

function SchedulerBanner({ state }: { state: SchedulerState | null }) {
  if (!state) return null;
  const fmtTime = (iso: string) =>
    new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
  if (state.is_running) {
    return (
      <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5 text-sm text-blue-700">
        <span className="animate-spin">⟳</span>
        <span className="font-medium">뉴스 수집 및 AI 분석이 진행 중입니다...</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-600">
      <span>🕐</span>
      <span>
        다음 수집 예정:&nbsp;
        <span className="font-semibold text-gray-800">
          {state.next_run_at ? fmtTime(state.next_run_at) : '—'}
        </span>
      </span>
      {state.last_run_at && (
        <span className="text-gray-400 text-xs ml-auto">
          마지막 수집: {fmtTime(state.last_run_at)}
        </span>
      )}
    </div>
  );
}

const SUIT_COLORS: Record<string, string> = {
  High: '#E11D48',
  Medium: '#D97706',
  Low: '#6B7280',
};

const POLL_INTERVAL_MS = 30_000; // 30초

const RADIAN = Math.PI / 180;

function PieLabel({
  cx, cy, midAngle, outerRadius, name, value, percent,
}: {
  cx: number; cy: number; midAngle: number; outerRadius: number;
  name: string; value: number; percent: number;
}) {
  const radius = outerRadius + 28;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  if (value === 0) return null;
  return (
    <text
      x={x} y={y}
      fill={SUIT_COLORS[name] ?? '#6B7280'}
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      fontSize={11}
      fontWeight={700}
    >
      {`${value.toLocaleString()}건 (${Math.round(percent * 100)}%)`}
    </text>
  );
}

function formatDateShort(d: string) {
  const [, m, day] = d.split('-');
  return `${parseInt(m)}/${parseInt(day)}`;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color?: string; fill?: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-100 rounded-lg shadow-lg px-3 py-2 text-xs">
      {label && <div className="text-gray-400 mb-1.5 font-medium">{label}</div>}
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 py-0.5">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: p.color ?? p.fill }}
          />
          <span className="text-gray-600">{p.name}</span>
          <span className="font-semibold ml-3">{p.value}건</span>
        </div>
      ))}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-border px-5 py-4 flex items-stretch gap-4 overflow-hidden">
      <div
        className="w-1 rounded-full shrink-0 self-stretch"
        style={{ backgroundColor: accent }}
      />
      <div className="min-w-0">
        <div className="text-xs text-gray-400 font-medium">{label}</div>
        <div className="text-2xl font-bold mt-1.5 leading-none text-gray-900">{value}</div>
        {sub && <div className="text-xs text-gray-400 mt-1.5">{sub}</div>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recent, setRecent] = useState<Analysis[]>([]);

  const refresh = () => {
    getStats().then(setStats);
    getAnalyses({ ordering: '-analyzed_at' }).then((r) => setRecent(r.results.slice(0, 8)));
  };

  useEffect(() => {
    refresh();

    // 30초마다 자동 갱신 — 탭이 숨겨지면 폴링 중단
    const tick = () => {
      if (!document.hidden) refresh();
    };
    const id = setInterval(tick, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  if (!stats) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="text-gray-200 text-5xl mb-3 animate-pulse">◌</div>
          <div className="text-gray-400 text-sm">데이터를 불러오는 중...</div>
        </div>
      </div>
    );
  }

  const total = stats.total_analyzed;
  const highCount = stats.suitability_distribution.find((d) => d.name === 'High')?.value ?? 0;
  const mediumCount = stats.suitability_distribution.find((d) => d.name === 'Medium')?.value ?? 0;
  const highPct = total ? Math.round((highCount / total) * 100) : 0;
  const mediumPct = total ? Math.round((mediumCount / total) * 100) : 0;
  const reviewedPct = total ? Math.round((stats.total_reviewed / total) * 100) : 0;

  const weeklyData = stats.weekly_trend.map((d) => ({ ...d, date: formatDateShort(d.date) }));

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-7">
      {/* 페이지 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI 분석 대시보드</h1>
          <p className="text-gray-400 text-sm mt-1">법률 뉴스 분석 및 소송적합도 현황</p>
        </div>
        <Link
          to="/"
          className="text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg px-3 py-2 bg-white transition-colors"
        >
          심사 현황으로 →
        </Link>
      </div>

      {/* AI 분석 KPI */}
      <div>
        <p className="text-xs font-semibold text-gray-300 uppercase tracking-widest mb-3">
          AI 분석 현황
        </p>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <KpiCard
            label="오늘 수집"
            value={stats.today_collected.toLocaleString()}
            sub="건 신규 기사"
            accent="#3B82F6"
          />
          <KpiCard
            label="분석 대기"
            value={stats.pending_count.toLocaleString()}
            sub="건"
            accent="#F59E0B"
          />
          <KpiCard
            label="분석 완료"
            value={total.toLocaleString()}
            sub="전체 누적"
            accent="#0F172A"
          />
          <KpiCard
            label="High 적합"
            value={highCount.toLocaleString()}
            sub={`전체의 ${highPct}%`}
            accent="#E11D48"
          />
          <KpiCard
            label="Medium 적합"
            value={mediumCount.toLocaleString()}
            sub={`전체의 ${mediumPct}%`}
            accent="#D97706"
          />
        </div>
      </div>

      {/* 수집 스케줄 상태 배너 */}
      <SchedulerBanner state={stats.scheduler_state} />

      {/* 심사 KPI */}
      <div>
        <p className="text-xs font-semibold text-gray-300 uppercase tracking-widest mb-3">
          심사 현황
        </p>
        <div className="grid grid-cols-3 gap-4">
          <KpiCard
            label="심사 완료"
            value={stats.total_reviewed.toLocaleString()}
            sub={`전체의 ${reviewedPct}%`}
            accent="#8B5CF6"
          />
          <KpiCard
            label="수임 통과"
            value={stats.total_accepted.toLocaleString()}
            sub="건 채택"
            accent="#10B981"
          />
          <KpiCard
            label="통과율"
            value={`${stats.acceptance_rate}%`}
            sub="심사 완료 대비"
            accent="#F59E0B"
          />
        </div>
      </div>

      {/* 차트 2열 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 소송적합도 도넛 차트 */}
        <div className="bg-white rounded-xl border border-border p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-1">소송적합도 분포</h3>
          <p className="text-xs text-gray-400 mb-3">
            AI 판단 기준 전체 누적
            <span className="ml-2 text-gold">클릭하면 심사현황으로 이동</span>
          </p>
          <div className="relative">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={stats.suitability_distribution}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="46%"
                  innerRadius={50}
                  outerRadius={72}
                  paddingAngle={3}
                  startAngle={90}
                  endAngle={-270}
                  label={PieLabel as never}
                  labelLine={{ stroke: '#D1D5DB', strokeWidth: 1 }}
                  onClick={(data: { name?: string }) => {
                    if (data?.name) navigate(`/?suitability=${data.name}`);
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  {stats.suitability_distribution.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={SUIT_COLORS[entry.name] ?? '#ccc'}
                    />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  formatter={(value) => (
                    <span className="text-xs text-gray-600 cursor-pointer hover:underline"
                      onClick={() => navigate(`/?suitability=${value}`)}>
                      {value}
                    </span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* 도넛 중앙 총 건수 */}
            <div
              className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
              style={{ paddingBottom: '48px' }}
            >
              <span className="text-2xl font-bold text-gray-900 leading-none">
                {total.toLocaleString()}
              </span>
              <span className="text-xs text-gray-400 mt-1">전체</span>
            </div>
          </div>
        </div>

        {/* 사건 분야별 누적 스택 바 */}
        <div className="bg-white rounded-xl border border-border p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-1">사건 분야별 분포</h3>
          <p className="text-xs text-gray-400 mb-3">
            상위 10개 분야
            <span className="ml-2 text-gold">클릭하면 분석 목록으로 이동</span>
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={stats.category_distribution}
              layout="vertical"
              margin={{ top: 0, right: 52, bottom: 0, left: 0 }}
              onClick={(data) => {
                if (data?.activeLabel) {
                  navigate(`/analyses?case_category=${encodeURIComponent(data.activeLabel)}`);
                }
              }}
              style={{ cursor: 'pointer' }}
            >
              <XAxis
                type="number"
                tick={{ fontSize: 10, fill: '#9CA3AF' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={70}
                tick={{ fontSize: 11, fill: '#6B7280' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                formatter={(value) => (
                  <span className="text-xs text-gray-600">{value}</span>
                )}
              />
              <Bar dataKey="high" name="High" fill="#E11D48" stackId="stack" maxBarSize={13} />
              <Bar dataKey="medium" name="Medium" fill="#D97706" stackId="stack" maxBarSize={13} />
              <Bar dataKey="low" name="Low" fill="#6B7280" stackId="stack" maxBarSize={13} radius={[0, 4, 4, 0]}>
                <LabelList
                  dataKey="count"
                  position="right"
                  style={{ fontSize: 11, fill: '#9CA3AF', fontWeight: 600 }}
                  formatter={(v) => `${v}건`}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 주간 추이 Area 차트 */}
      <div className="bg-white rounded-xl border border-border p-5">
        <h3 className="text-sm font-semibold text-gray-800 mb-1">주간 수집·분석 추이</h3>
        <p className="text-xs text-gray-400 mb-4">최근 7일</p>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={weeklyData}>
            <defs>
              <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0F172A" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#0F172A" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradHigh" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#E11D48" stopOpacity={0.18} />
                <stop offset="95%" stopColor="#E11D48" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradMedium" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#D97706" stopOpacity={0.14} />
                <stop offset="95%" stopColor="#D97706" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: '#9CA3AF' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9CA3AF' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(value) => (
                <span className="text-xs text-gray-600">{value}</span>
              )}
            />
            <Area
              type="monotone"
              dataKey="total"
              stroke="#0F172A"
              strokeWidth={2}
              fill="url(#gradTotal)"
              name="전체"
              dot={{ r: 3, fill: '#0F172A', strokeWidth: 0 }}
            >
              <LabelList
                dataKey="total"
                position="top"
                style={{ fontSize: 10, fill: '#0F172A', fontWeight: 700 }}
                formatter={(v) => (Number(v) > 0 ? v : '')}
              />
            </Area>
            <Area
              type="monotone"
              dataKey="high"
              stroke="#E11D48"
              strokeWidth={2}
              fill="url(#gradHigh)"
              name="High"
              dot={{ r: 3, fill: '#E11D48', strokeWidth: 0 }}
            >
              <LabelList
                dataKey="high"
                position="top"
                style={{ fontSize: 10, fill: '#E11D48', fontWeight: 600 }}
                formatter={(v) => (Number(v) > 0 ? v : '')}
              />
            </Area>
            <Area
              type="monotone"
              dataKey="medium"
              stroke="#D97706"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              fill="url(#gradMedium)"
              name="Medium"
              dot={{ r: 3, fill: '#D97706', strokeWidth: 0 }}
            >
              <LabelList
                dataKey="medium"
                position="top"
                style={{ fontSize: 10, fill: '#D97706', fontWeight: 600 }}
                formatter={(v) => (Number(v) > 0 ? v : '')}
              />
            </Area>
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* 최근 분석 결과 테이블 */}
      <div className="bg-white rounded-xl border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="text-sm font-semibold text-gray-800">최근 분석 결과</h3>
          <Link
            to="/analyses"
            className="text-xs text-gold hover:underline font-medium"
          >
            전체 보기 →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-gray-400 bg-gray-50">
                <th className="px-4 py-3 font-medium">적합도</th>
                <th className="px-4 py-3 font-medium">기사 제목</th>
                <th className="px-4 py-3 font-medium">분야</th>
                <th className="px-4 py-3 font-medium">상대방</th>
                <th className="px-4 py-3 font-medium">단계</th>
                <th className="px-4 py-3 font-medium">날짜</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((a) => (
                <tr
                  key={a.id}
                  className="border-b last:border-0 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <SuitabilityBadge value={a.suitability} />
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <Link
                      to={`/analyses/${a.id}`}
                      className="hover:text-blue-600 line-clamp-1 leading-snug"
                    >
                      {a.article_title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{a.case_category}</td>
                  <td className="px-4 py-3 text-gray-500">{a.defendant ?? '—'}</td>
                  <td className="px-4 py-3">
                    <StageBadge value={a.stage} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                    {a.published_at?.slice(0, 10)}
                  </td>
                </tr>
              ))}
              {recent.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-gray-400">
                    분석 데이터가 없습니다
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
