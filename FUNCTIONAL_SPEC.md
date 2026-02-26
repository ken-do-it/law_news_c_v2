# LawNGood — 기능 명세서 (Functional Specification)

> 버전: v2.1 | 작성일: 2026-02-24 | 기반 코드: law_news_c_v2

---

## FS-001. 뉴스 수집 파이프라인

**모듈**: `backend/articles/tasks.py`, `backend/articles/crawlers.py`

### 입력
```
- 활성화된 Keyword 목록 (DB: articles_keyword.is_active=True)
- 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
```

### 처리 흐름

```
crawl_news()
  ├── Keyword.objects.filter(is_active=True) 조회
  ├── 각 키워드 → search_naver_news(keyword) 호출
  │     └── GET https://openapi.naver.com/v1/search/news.json
  │           params: query={keyword}, display=100, sort=date
  ├── 각 결과 기사 → process_article(item)
  │     ├── URL 정규화 (naver.com link → originallink 우선)
  │     ├── Article.objects.get_or_create(url=url) → 중복 스킵
  │     ├── fetch_article_content(url) → BeautifulSoup 본문 추출
  │     ├── extract_source_from_url(url) → MediaSource 매핑 (80개+ 도메인)
  │     └── Article 저장 (status='pending')
  └── 수집 완료 → analyze_pending_articles() 자동 호출
```

### 출력
- 신규 `Article` 레코드 (status='pending')
- 중복 URL → 스킵 (기존 레코드 유지)

### 예외 처리

| 예외 | 처리 방식 |
|------|-----------|
| 네이버 API 오류 (4xx/5xx) | 로그 기록, 해당 키워드 스킵, 다음 키워드 계속 진행 |
| 본문 추출 실패 | title만 저장, content="" |
| 중복 URL | `get_or_create`로 자동 스킵 |
| 언론사 도메인 매핑 실패 | source=null로 저장 |

---

## FS-002. 자동 스케줄러

**모듈**: `backend/articles/services/scheduler.py`

### 동작 조건 (모두 충족 시 활성화)

```python
1. ENABLE_PIPELINE_ON_RUNSERVER=True  (환경변수)
2. os.environ.get('RUN_MAIN') == 'true'  (runserver 메인 프로세스)
3. Django AppConfig.ready() 완료 이후
```

### 스케줄 설정

```python
scheduler.add_job(
    _run_pipeline_job,
    trigger='interval',
    minutes=PIPELINE_INTERVAL_MINUTES,    # 기본: 60분
    next_run_time=now() + timedelta(seconds=30),  # 최초 30초 후
    max_instances=1,   # 동시 실행 방지
    coalesce=True,     # 밀린 실행은 1회로 합산
    id='pipeline_job',
    replace_existing=True
)
```

### 파이프라인 작업 순서

```
_run_pipeline_job()
  1. crawl_news()            → 뉴스 수집
  2. (crawl_news 내부에서) analyze_pending_articles()  → AI 분석
```

---

## FS-003. LLM 분석 엔진

**모듈**: `backend/analyses/tasks.py`, `backend/analyses/prompts.py`

### API 설정

| 항목 | 값 |
|------|-----|
| 모델 | gemini-2.5-flash (환경변수 LLM_MODEL) |
| Temperature | 0.1 (환경변수 LLM_TEMPERATURE) |
| 응답 형식 | JSON (response_mime_type='application/json') |
| 본문 최대 길이 | 3,000자 (초과 시 truncation) |

### 프롬프트 구조

```
[시스템 프롬프트]
당신은 소송금융 전문 애널리스트입니다.
다음 6가지 기준으로 뉴스 기사를 평가하세요.

C1: 상대방의 명확한 책임 존재
C2: 상대방의 충분한 자력 (대기업/공기관 등)
C3: 집단적 피해 (50명 이상)
C4: 대규모 피해 (10억 원↑ 또는 피해자 1만명↑)
C5: 증거 존재 또는 확보 가능
C6: 공개 절차 진행 중 (수사/감사 등)
X1: 결격 사유 — 사건 종결 (확정판결/합의 완료)

High: 4개↑ 충족 + X1 없음
Medium: 2~3개 충족 + X1 없음
Low: 1개↓ 또는 X1 해당

[Few-shot 예시 3개]
예시 1: High (개인정보 유출 집단소송)
예시 2: Medium (의료사고 단일 피해)
예시 3: Low (합의 완료 사건)

[기사 내용]
제목: {article.title}
내용: {article.content[:3000]}

[기존 케이스 목록] (중복 그룹핑 방지)
CASE-2026-001: 쿠팡 개인정보 유출 집단소송
...

[응답 형식]
반드시 아래 JSON 형식으로만 응답하세요.
```

### 분석 처리 흐름

```
analyze_single_article(article_id)
  ├── Article.objects.get(id=article_id)
  ├── article.status = 'analyzing' → 저장
  ├── 기존 CaseGroup 이름 목록 조회
  ├── build_prompt(article, case_names)
  ├── call_gemini(prompt)  [최대 3회 재시도]
  │     └── google.generativeai.GenerativeModel.generate_content()
  ├── validate_and_parse(raw_response)
  │     ├── JSON 코드블록 추출 (```json...```)
  │     ├── json.loads() 파싱
  │     ├── 필수 필드 검증: suitability, suitability_reason, case_category, summary
  │     ├── enum 유효성 검증 및 클램핑
  │     └── 선택 필드 기본값 설정 ("미상" 등)
  ├── match_or_create_case_group(case_name)
  │     ├── 유사도 >= 0.6 → 기존 그룹 반환
  │     └── 유사도 < 0.6 → 신규 CaseGroup 생성 (CASE-YYYY-NNN)
  ├── Analysis.objects.create(...)
  └── article.status = 'analyzed' → 저장
      [오류 시] article.status = 'failed', retry_count++ → 저장
```

### 재시도 로직

```python
for attempt in range(3):           # 최대 3회 시도 (재시도 2회)
    try:
        result = call_gemini(prompt)
        parsed = validate_and_parse(result)
        break
    except (JSONDecodeError, ValidationError):
        if attempt == 2:
            raise                  # 3회 모두 실패 → 예외 전파
        continue

# 최종 실패 시
article.status = 'failed'
article.retry_count += 1
```

---

## FS-004. 케이스 자동 그룹핑

**모듈**: `backend/analyses/tasks.py`

### 유사도 계산 알고리즘

```python
STOPWORDS = {'소송', '사건', '피해', '집단', '공동', '관련', '문제', ...}

def _case_similarity(a: str, b: str) -> float:
    tokens_a = set(a.split()) - STOPWORDS
    tokens_b = set(b.split()) - STOPWORDS

    base_sim = SequenceMatcher(None, a, b).ratio()   # 문자열 기본 유사도
    common = tokens_a & tokens_b
    bonus = len(common) * 0.1                        # 공통 핵심 토큰 보너스

    return min(base_sim + bonus, 1.0)
```

### 그룹 매칭 로직

```python
def match_or_create_case_group(case_name, existing_groups):
    best_score = max((_case_similarity(case_name, g.name), g) for g in existing_groups)

    if best_score >= 0.6:
        return existing_group      # 기존 그룹 재사용
    else:
        case_id = CaseGroup.generate_next_case_id()   # CASE-2026-NNN
        return CaseGroup.objects.create(case_id=case_id, name=case_name)
```

### 케이스 ID 생성 규칙

```
형식: CASE-{연도}-{3자리 순번}
예시: CASE-2026-001, CASE-2026-042

- 연도가 바뀌면 순번 1부터 재시작
- 동시 생성 시 DB 단위에서 unique constraint로 보호
```

---

## FS-005. REST API 명세

### 5-1. 분석 목록

```
GET /api/analyses/

Query Parameters:
  search            string   기사 제목, 피고, 요약, 케이스명 부분 검색
  suitability       string   High,Medium,Low (쉼표로 복수 선택 가능)
  case_category     string   사건유형 부분 검색
  stage             string   소송 단계 정확 매칭
  date_from         date     게재일 시작 (YYYY-MM-DD)
  date_to           date     게재일 종료 (YYYY-MM-DD)
  case_group        integer  케이스 그룹 ID
  is_relevant       boolean  법적 관련성 필터
  include_irrelevant boolean  true이면 관련없는 기사 포함 (기본: false)
  group_by_case     boolean  true이면 케이스별 최신 1건만 표시 (기본: true)
  page              integer  페이지 번호 (기본: 1, 페이지당 20건)
  ordering          string   정렬 기준 (기본: -analyzed_at)

Response 200:
{
  "count": 248,
  "next": "/api/analyses/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "article_title": "쿠팡 개인정보 유출 피해자 100명 집단소송",
      "article_url": "https://n.news.naver.com/...",
      "source_name": "조선일보",
      "published_at": "2026-02-24T10:30:00+09:00",
      "suitability": "High",
      "case_category": "개인정보",
      "defendant": "쿠팡",
      "damage_amount": "50억원",
      "victim_count": "100명",
      "stage": "소송중",
      "case_id": "CASE-2026-001",
      "case_name": "쿠팡 개인정보 유출 집단소송",
      "is_relevant": true,
      "analyzed_at": "2026-02-24T10:35:00+09:00",
      "related_count": 3
    }
  ]
}
```

### 5-2. 분석 상세

```
GET /api/analyses/{id}/

Response 200:
{
  "id": 1,
  ...기본 필드 (목록과 동일)...,
  "suitability_reason": "C1(쿠팡 보안 과실 명확), C2(대기업), C3(100명↑), C4(50억원) 충족",
  "stage_detail": "서울중앙지법 2026가합12345",
  "summary": "쿠팡에서 고객 100명의 개인정보가 유출되어...",
  "llm_model": "gemini-2.5-flash",
  "article": {
    "id": 1,
    "title": "...",
    "content": "...",
    "url": "...",
    "source": {"id": 1, "name": "조선일보", "url": "https://chosun.com"},
    "author": "김기자",
    "published_at": "2026-02-24T10:30:00+09:00",
    "status": "analyzed"
  },
  "case_group": {
    "id": 1,
    "case_id": "CASE-2026-001",
    "name": "쿠팡 개인정보 유출 집단소송",
    "description": "",
    "article_count": 4
  },
  "related_articles": [
    {
      "id": 2,
      "article_title": "쿠팡 집단소송 원고 200명 돌파",
      "suitability": "High",
      "published_at": "2026-02-20T09:00:00+09:00"
    }
  ]
}
```

### 5-3. 대시보드 통계

```
GET /api/analyses/stats/

Response 200:
{
  "today_collected": 15,
  "pending_count": 3,
  "today_analyzed": 12,
  "total_analyzed": 248,
  "today_high": 5,
  "today_medium": 7,
  "monthly_cost": 45600,
  "suitability_distribution": [
    {"name": "High", "value": 85},
    {"name": "Medium", "value": 120},
    {"name": "Low", "value": 43}
  ],
  "category_distribution": [
    {"name": "개인정보", "count": 48},
    {"name": "제조물책임", "count": 35},
    {"name": "의료사고", "count": 22}
  ],
  "weekly_trend": [
    {"date": "2026-02-18", "total": 12, "high": 5, "medium": 7},
    {"date": "2026-02-19", "total": 8,  "high": 3, "medium": 4},
    {"date": "2026-02-24", "total": 15, "high": 8, "medium": 6}
  ]
}
```

### 5-4. 재분석 트리거

```
POST /api/articles/{id}/reanalyze/

동작 순서:
  1. 해당 Article의 기존 Analysis 삭제
  2. article.status = 'pending', retry_count = 0 으로 초기화
  3. analyze_single_article(article_id) 즉시 동기 실행

Response 200: {"message": "재분석이 시작되었습니다."}
Response 400: {"error": "이미 분석 중입니다."}
Response 404: {"error": "Article not found"}
```

### 5-5. 엑셀 내보내기

```
GET /api/analyses/export/

Query Parameters: (목록 API와 동일한 필터 파라미터 지원)

Response 200:
  Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  Content-Disposition: attachment; filename="lawngood_analyses_20260224.xlsx"
  Body: <binary xlsx 데이터>
```

### 5-6. 키워드 CRUD

```
GET    /api/keywords/
  Response: [{"id": 1, "word": "소송", "is_active": true, "created_at": "..."}]

POST   /api/keywords/
  Body: {"word": "집단소송"}
  Response 201: {"id": 8, "word": "집단소송", "is_active": true, "created_at": "..."}

DELETE /api/keywords/{id}/
  Response 204: (no content)
```

### 5-7. 기타 API

```
GET /api/articles/          → 기사 목록 (status, source, 날짜 필터 지원)
GET /api/articles/{id}/     → 기사 상세
GET /api/sources/           → 언론사 목록
GET /api/case-groups/       → 케이스 그룹 목록
GET /api/case-groups/{id}/  → 케이스 그룹 상세
GET /api/docs/              → Swagger UI (drf-spectacular)
```

---

## FS-006. 데이터베이스 스키마

### Articles 앱

```sql
-- 언론사
CREATE TABLE articles_mediasource (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) UNIQUE NOT NULL,  -- "조선일보"
    url         VARCHAR(200),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  DATETIME NOT NULL
);

-- 검색 키워드
CREATE TABLE articles_keyword (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        VARCHAR(50) UNIQUE NOT NULL,   -- "소송"
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  DATETIME NOT NULL
);

-- 뉴스 기사
CREATE TABLE articles_article (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER REFERENCES articles_mediasource(id) ON DELETE SET NULL,
    title         VARCHAR(500) NOT NULL,
    content       TEXT NOT NULL,
    url           VARCHAR(1000) UNIQUE NOT NULL,
    author        VARCHAR(100),
    published_at  DATETIME NOT NULL,
    collected_at  DATETIME NOT NULL,
    status        VARCHAR(20) CHECK(status IN ('pending','analyzing','analyzed','failed')),
    retry_count   INTEGER DEFAULT 0
);

-- 기사-키워드 연결 (M:M)
CREATE TABLE articles_articlekeyword (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL REFERENCES articles_article(id) ON DELETE CASCADE,
    keyword_id  INTEGER NOT NULL REFERENCES articles_keyword(id) ON DELETE CASCADE,
    created_at  DATETIME NOT NULL,
    UNIQUE(article_id, keyword_id)
);
```

### Analyses 앱

```sql
-- 케이스 그룹 (자동 그룹핑)
CREATE TABLE analyses_casegroup (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     VARCHAR(30) UNIQUE NOT NULL,  -- "CASE-2026-001"
    name        VARCHAR(200) NOT NULL,         -- "쿠팡 개인정보 유출"
    description TEXT,
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);

-- AI 분석 결과
CREATE TABLE analyses_analysis (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id          INTEGER UNIQUE NOT NULL REFERENCES articles_article(id) ON DELETE CASCADE,
    case_group_id       INTEGER REFERENCES analyses_casegroup(id) ON DELETE SET NULL,

    -- AI 판단 결과
    suitability         VARCHAR(10) NOT NULL CHECK(suitability IN ('High','Medium','Low')),
    suitability_reason  TEXT NOT NULL,
    case_category       VARCHAR(100) NOT NULL,
    defendant           VARCHAR(200),
    damage_amount       VARCHAR(200),
    victim_count        VARCHAR(200),
    stage               VARCHAR(20) CHECK(stage IN (
                            '피해 발생','관련 절차 진행','소송중','판결 선고','종결'
                        )),
    stage_detail        VARCHAR(200),
    summary             TEXT NOT NULL,

    -- 필터링
    is_relevant         BOOLEAN DEFAULT TRUE,

    -- LLM 메타데이터
    llm_model           VARCHAR(50) DEFAULT 'gemini-2.5-flash',
    prompt_tokens       INTEGER DEFAULT 0,
    completion_tokens   INTEGER DEFAULT 0,
    analyzed_at         DATETIME NOT NULL
);

-- 성능 인덱스
CREATE INDEX idx_analysis_suitability ON analyses_analysis(suitability);
CREATE INDEX idx_analysis_category    ON analyses_analysis(case_category);
CREATE INDEX idx_analysis_stage       ON analyses_analysis(stage);
CREATE INDEX idx_analysis_analyzed_at ON analyses_analysis(analyzed_at);
```

### 모델 관계도

```
MediaSource (1) ──── (N) Article (1) ──── (1) Analysis
                          │                      │
                    ArticleKeyword          CaseGroup (1) ──── (N) Analysis
                          │
                       Keyword
```

---

## FS-007. 프론트엔드 페이지 명세

### 7-1. 대시보드 (`/`)

```
┌─────────────────────────────────────────────────────┐
│ [TopNav: Dashboard | 분석 목록 | 설정]               │
├──────────┬──────────┬──────────┬──────────┬──────────┤
│ 오늘수집 │ 분석대기 │ 오늘분석 │ 전체분석 │ 오늘High │
│   15건   │   3건    │  12건    │  248건   │   5건    │
├──────────┴──────────┴──────────┼──────────┴──────────┤
│ [파이차트: 적합도 분포]          │ [막대차트: 유형별]  │
│  High 35% / Medium 49% / Low 16%│  개인정보  48       │
│                                 │  제조물책임 35      │
│                                 │  의료사고  22       │
├─────────────────────────────────┴────────────────────┤
│ [라인차트: 최근 7일 트렌드 — 전체/High/Medium]        │
├──────────────────────────────────────────────────────┤
│ 최신 분석 5건                                        │
│ [High] 쿠팡 개인정보... | 개인정보 | 소송중 | 오늘   │
└──────────────────────────────────────────────────────┘

데이터: GET /api/analyses/stats/ + GET /api/analyses/?page=1
```

### 7-2. 분석 목록 (`/analyses`)

```
┌───────────────────────────────────────────────────────┐
│ [🔍 검색 input] [적합도▼] [단계▼] [케이스그룹 □]      │
│ [관련없음포함 □]                         [엑셀 다운↓]  │
├──────────┬─────────────────┬────────┬──────────┬──────┤
│ 적합도   │ 제목 (+연관N건) │ 유형   │ 피해자수 │ 피고 │
├──────────┼─────────────────┼────────┼──────────┼──────┤
│ [High]   │ 쿠팡 개인정보.. │ 개인정 │ 100명    │ 쿠팡 │
│          │ [+3]            │ 보     │          │      │
│ [Medium] │ OO병원 의료..   │ 의료   │ 1명      │ OO병 │
├──────────┴─────────────────┴────────┴──────────┴──────┤
│ ◀  1  2  3  ...  13  ▶     (총 248건)                 │
└───────────────────────────────────────────────────────┘

- 필터 상태는 URL query string에 동기화 (북마크/공유 가능)
- is_relevant=false 행은 opacity 낮게 표시
```

### 7-3. 분석 상세 (`/analyses/:id`)

```
┌──────────────────────────────────┬──────────────────────┐
│ ← 목록으로                        │ [케이스 정보 카드]    │
│                                  │ 적합도:  [High]      │
│ ## 쿠팡 개인정보 유출 집단소송     │ 유형:    개인정보    │
│ 조선일보 | 2026-02-24 | [원문↗]  │ 피고:    쿠팡        │
│                                  │ 피해금액: 50억원      │
│ ### AI 요약                       │ 피해자수: 100명       │
│ 쿠팡에서 고객 100명의 개인정보가  │ 단계:    소송중      │
│ 유출되어 집단소송이 제기되었다... │ 케이스: CASE-2026-001│
│                                  │                      │
│ ### 투자 적합도 판단              │ [재분석]  [엑셀 ↓]  │
│ ╔══════════════════════════════╗ │                      │
│ ║ [High] C1, C2, C3, C4 충족  ║ │ 모델: gemini-2.5     │
│ ║ C1: 쿠팡 보안 과실 명확      ║ │ 분석: 2026-02-24     │
│ ╚══════════════════════════════╝ │       14:30          │
│                                  └──────────────────────┘
│ ### 연관 기사 (3건)
│ [High] 쿠팡 집단소송 원고 200명... 2026-02-20
│ [High] 개인정보위, 쿠팡 과징금...  2026-02-15
└────────────────────────────────────────────────────────
```

### 7-4. 설정 (`/settings`)

```
┌────────────────────────────────────────────────────────┐
│ 검색 키워드 관리                                        │
│                                                        │
│ [소송 ✕] [손해배상 ✕] [집단소송 ✕] [공동소송 ✕]      │
│ [피해자 ✕] [피해보상 ✕] [피해구제 ✕]                  │
│                                                        │
│ [새 키워드 입력________________] [추가]                │
│                                                        │
│ * 추가/삭제는 즉시 반영되며, 다음 수집 주기부터 적용   │
└────────────────────────────────────────────────────────┘
```

### 7-5. 컴포넌트 계층

```
App (React Router)
├── TopNav
│   └── Link ×3 (Dashboard, 분석 목록, 설정)
├── Dashboard
│   ├── StatsCard ×6
│   ├── PieChart (Recharts)
│   ├── BarChart (Recharts)
│   ├── LineChart (Recharts)
│   └── 최신 분석 테이블
├── AnalysisList
│   ├── 필터 컨트롤 (search, select, checkbox)
│   ├── 분석 테이블 (rows with Link)
│   ├── Pagination
│   └── SuitabilityBadge, StageBadge
├── AnalysisDetail
│   ├── 기사 헤더 + Badges
│   ├── AI 요약 섹션
│   ├── 판단 근거 (색상 강조)
│   ├── 연관 기사 목록
│   └── 우측 고정 패널 (Detail Card + 버튼)
└── Settings
    └── 키워드 태그 CRUD
```

### 7-6. 색상 시스템

| CSS 변수 | 값 | 용도 |
|----------|----|------|
| `--color-navy` | `#0F172A` | Primary 색상 |
| `--color-gold` | `#D4AF37` | Accent 색상 |
| `--color-high` | `#E11D48` | High 적합도 (빨강) |
| `--color-medium` | `#D97706` | Medium 적합도 (주황) |
| `--color-low` | `#6B7280` | Low 적합도 (회색) |
| `--color-bg` | `#F9FAFB` | 페이지 배경 |
| `--color-border` | `#E5E7EB` | 테두리 |

---

## FS-008. 엑셀 내보내기 명세

**파일명**: `lawngood_analyses_{YYYYMMDD}.xlsx`

### 컬럼 상세

| 열 | 컬럼명 | 데이터 소스 | 권장 너비 |
|----|--------|-----------|-----------|
| A | No | 순번 (1부터) | 6 |
| B | 케이스 ID | analysis.case_id | 18 |
| C | 기사 제목 | article.title | 40 |
| D | 언론사 | article.source.name | 16 |
| E | 게재일 | article.published_at | 18 |
| F | 투자 적합도 | analysis.suitability | 14 |
| G | 판단 근거 | analysis.suitability_reason | 50 |
| H | 사건 유형 | analysis.case_category | 18 |
| I | 피고 | analysis.defendant | 20 |
| J | 피해 금액 | analysis.damage_amount | 16 |
| K | 피해자 수 | analysis.victim_count | 14 |
| L | 소송 단계 | analysis.stage | 16 |
| M | 단계 상세 | analysis.stage_detail | 25 |
| N | AI 요약 | analysis.summary | 50 |
| O | 원문 링크 | article.url (하이퍼링크) | 30 |

### 스타일 규칙

| 대상 | 스타일 |
|------|--------|
| 헤더 행 | 배경 `#0F172A`, 폰트 흰색, Bold |
| F열 (High) | 배경 `#FECDD3` (연빨강) |
| F열 (Medium) | 배경 `#FEF3C7` (연노랑) |
| F열 (Low) | 배경 `#F3F4F6` (연회색) |
| 전체 셀 | `wrap_text=True` |
| 헤더 행 고정 | `freeze_panes='A2'` |

---

## FS-009. Article 상태 전이도

```
                    crawl_news()
                         │
                         ▼
                    [ pending ]
                         │
                         ▼
         analyze_single_article() 호출
                         │
                         ▼
                   [ analyzing ]
                    ┌────┴────┐
                 성공         실패 (JSON 오류 등)
                    │              │
                    ▼         재시도 (최대 2회)
               [ analyzed ]        │
                              최종 실패
                                   │
                                   ▼
                              [ failed ]
                          retry_count++

     POST /reanalyze/ → failed/analyzed → pending (retry_count=0)
```

---

## FS-010. 환경 변수 명세

| 변수명 | 필수 | 기본값 | 설명 |
|--------|:----:|--------|------|
| `DJANGO_SECRET_KEY` | ✅ | - | Django 암호화 키 (50자↑ 랜덤) |
| `DEBUG` | | `True` | 개발 모드 여부 |
| `ALLOWED_HOSTS` | | `localhost,127.0.0.1` | 허용 호스트 (쉼표 구분) |
| `NAVER_CLIENT_ID` | ✅ | - | 네이버 검색 API Client ID |
| `NAVER_CLIENT_SECRET` | ✅ | - | 네이버 검색 API Secret |
| `GEMINI_API_KEY` | ✅ | - | Google AI Studio API 키 |
| `LLM_MODEL` | | `gemini-2.5-flash` | 사용할 Gemini 모델명 |
| `LLM_TEMPERATURE` | | `0.1` | LLM 온도 파라미터 (0~1) |
| `NEWS_KEYWORDS` | | `소송,손해배상,...` | 초기 검색 키워드 (쉼표 구분) |
| `ENABLE_PIPELINE_ON_RUNSERVER` | | `True` | 자동 파이프라인 활성화 여부 |
| `PIPELINE_INTERVAL_MINUTES` | | `60` | 파이프라인 실행 주기 (분) |

---

## FS-011. 초기 데이터 시드

**명령어**: `python manage.py seed_initial_data`

**생성 내용**:
- MediaSource: 80개 이상 주요 언론사 (조선일보, 중앙일보, KBS, MBC, SBS, 한겨레 등)
- Keyword: `NEWS_KEYWORDS` 환경변수에 정의된 키워드 목록

---

## FS-012. Admin 인터페이스

**접근 URL**: `/admin/`

### articles 앱

| 모델 | 목록 컬럼 | 필터 | 검색 |
|------|-----------|------|------|
| MediaSource | name, is_active, created_at | - | name |
| Keyword | word, is_active, created_at | - | word |
| Article | title, source, status, published_at | status, source | title, content |
| ArticleKeyword | article, keyword, created_at | - | - |

### analyses 앱

| 모델 | 목록 컬럼 | 필터 | 검색 |
|------|-----------|------|------|
| CaseGroup | case_id, name, article_count, created_at | - | case_id, name |
| Analysis | article, suitability, case_category, defendant, stage, case_group, analyzed_at | suitability, case_category, stage, case_group | 기사 제목, 피고, 요약 |

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v2.1 | 2026-02-24 | 초안 작성 (현재 코드베이스 기반) |
| v2.0 | - | Gemini로 LLM 교체, 동기 파이프라인 도입, is_relevant 필드 추가 |
| v1.0 | - | OpenAI GPT-4o, Celery 기반 초기 버전 |
