import axios from 'axios';
import type { Analysis, DashboardStats, Keyword, PaginatedResponse } from './types';

const api = axios.create({ baseURL: '/api' });

export interface AnalysisFilters {
  suitability?: string;
  case_category?: string;
  stage?: string;
  search?: string;
  ordering?: string;
  page?: number;
  include_irrelevant?: string;
  group_by_case?: string;
  review_completed?: boolean;
  accepted?: boolean;
  client_suitability?: string;
}

export async function getStats(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>('/analyses/stats/');
  return data;
}

export async function getAnalyses(
  filters?: AnalysisFilters,
): Promise<PaginatedResponse<Analysis>> {
  const params = filters ? Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== ''),
  ) : {};
  const { data } = await api.get<PaginatedResponse<Analysis>>('/analyses/', { params });
  return data;
}

export async function getAnalysis(id: number): Promise<Analysis> {
  const { data } = await api.get<Analysis>(`/analyses/${id}/`);
  return data;
}

export async function reanalyze(articleId: number): Promise<void> {
  await api.post(`/articles/${articleId}/reanalyze/`);
}

export async function downloadExcel(filters?: AnalysisFilters): Promise<void> {
  const params = filters ? Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== ''),
  ) : {};
  const { data } = await api.get('/analyses/export/', {
    params,
    responseType: 'blob',
  });

  const url = window.URL.createObjectURL(data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'analyses_export.xlsx';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export interface ReviewPayload {
  review_completed?: boolean;
  client_suitability?: 'High' | 'Medium' | 'Low' | null;
  accepted?: boolean;
}

export async function updateReview(id: number, payload: ReviewPayload): Promise<Analysis> {
  const { data } = await api.patch<Analysis>(`/analyses/${id}/`, payload);
  return data;
}

export async function getKeywords(): Promise<Keyword[]> {
  const { data } = await api.get<{ results: Keyword[] }>('/keywords/');
  return data.results;
}

export async function createKeyword(word: string): Promise<void> {
  await api.post('/keywords/', { word, is_active: true });
}

export async function deleteKeyword(id: number): Promise<void> {
  await api.delete(`/keywords/${id}/`);
}

export async function downloadReport(period: 'weekly' | 'monthly'): Promise<void> {
  const { data } = await api.get('/analyses/report/', {
    params: { period },
    responseType: 'blob',
  });

  const today = new Date();
  const dateStr = today.toISOString().slice(0, 10).replace(/-/g, '');
  const filename = period === 'monthly'
    ? `report_${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}.pdf`
    : `report_weekly_${dateStr}.pdf`;

  const url = window.URL.createObjectURL(data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
