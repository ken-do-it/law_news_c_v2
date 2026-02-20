export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Keyword {
  id: number;
  word: string;
  is_active: boolean;
}

export interface MediaSource {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
}

export interface Article {
  id: number;
  title: string;
  url: string;
  source_name: string;
  author: string;
  published_at: string;
  collected_at: string;
  status: 'pending' | 'analyzing' | 'analyzed' | 'failed';
}

export interface Analysis {
  id: number;
  article_title: string;
  article_url: string;
  source_name: string;
  published_at: string;
  suitability: 'High' | 'Medium' | 'Low';
  case_category: string;
  defendant: string | null;
  damage_amount: string | null;
  victim_count: string | null;
  stage: string;
  case_id: string | null;
  case_name: string | null;
  is_relevant: boolean;
  analyzed_at: string;
  related_count: number;

  article: Article;
  case_group: CaseGroup | null;
  suitability_reason: string;
  stage_detail: string | null;
  summary: string;
  llm_model: string;
  prompt_tokens: number;
  completion_tokens: number;
  related_articles: RelatedArticle[];
}

export interface RelatedArticle {
  id: number;
  article_title: string;
  article_url: string;
  published_at: string;
  source_name: string;
  summary: string;
  suitability: 'High' | 'Medium' | 'Low';
}

export interface CaseGroup {
  id: number;
  case_id: string;
  name: string;
  description: string;
  article_count: number;
  created_at: string;
}

export interface DashboardStats {
  today_collected: number;
  today_high: number;
  today_medium: number;
  total_analyzed: number;
  monthly_cost: number;
  suitability_distribution: { name: string; value: number }[];
  category_distribution: { name: string; count: number }[];
  weekly_trend: { date: string; total: number; high: number; medium: number }[];
}
