# LawNGood — 기능 명세서 (Functional Specification)

> 버전: v2.3 | 최종 수정: 2026-03-05 | 기반 코드: law_news_c_v2
>
> 이 문서는 `backend/` 디렉토리 내 Django 앱별 모델, API, 비즈니스 로직과 프론트엔드 명세를 통합 기술합니다.

---

## 목차

1. [FS-001. 뉴스 수집 파이프라인](#fs-001-뉴스-수집-파이프라인)
2. [FS-002. 자동 스케줄러](#fs-002-자동-스케줄러)
3. [FS-003. LLM 분석 엔진](#fs-003-llm-분석-엔진)
4. [FS-004. 케이스 자동 그룹핑](#fs-004-케이스-자동-그룹핑)
5. [FS-005. REST API 명세](#fs-005-rest-api-명세)
6. [FS-006. 데이터베이스 스키마](#fs-006-데이터베이스-스키마)
7. [FS-007. 프론트엔드 페이지 명세](#fs-007-프론트엔드-페이지-명세)
8. [FS-008. 엑셀 내보내기 명세](#fs-008-엑셀-내보내기-명세)
9. [FS-009. Article 상태 전이도](#fs-009-article-상태-전이도)
10. [FS-010. 환경 변수 명세](#fs-010-환경-변수-명세)
11. [FS-011. 초기 데이터 시드](#fs-011-초기-데이터-시드)
12. [FS-012. Admin 인터페이스](#fs-012-admin-인터페이스)
13. [FS-013. config — Django 프로젝트 설정](#fs-013-config--django-프로젝트-설정)
14. [FS-014. 크롤러 상세](#fs-014-크롤러-상세)
15. [FS-015. 모델 상세 (articles)](#fs-015-모델-상세-articles)
16. [FS-016. 모델 상세 (analyses)](#fs-016-모델-상세-analyses)

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

### 실행 방법

| 방법 | 설명 |
|------|------|
| `just crawl` | `manage.py crawl_news` 호출 — 스케줄러 미시작, 단독 수집 |
| APScheduler (자동) | 서버 실행 시 60분마다 `crawl_news()` 자동 호출 |

### 예외 처리

| 예외 | 처리 방식 |
|------|-----------|
| 네이버 API 오류 (4xx/5xx) | 로그 기록, 해당 키워드 스킵, 다음 키워드 계속 진행 |
| 본문 추출 실패 | title만 저장, content="" |
| 중복 URL | `get_or_create`로 자동 스킵 |
| 언론사 도메인 매핑 실패 | source=null로 저장 |

---

## FS-002. 자동 스케줄러

**모듈**: `backend/scheduler/scheduler.py`, `backend/scheduler/apps.py`

### 동작 조건

- `manage.py runserver` 실행 시 `SchedulerConfig.ready()`에서 자동 시작
- 관리 명령어(`shell`, `crawl_news`, `run_analysis` 등) 실행 시 **미시작** (충돌 방지)
- WSGI/ASGI 서버 사용 시 `DJANGO_SCHEDULER_ENABLED=1` 환경변수로 명시 활성화

### 잡 구성 (두 잡 독립 실행)

| 잡 ID | 함수 | 최초 실행 | 재실행 주기 |
|-------|------|---------|-----------|
| `crawl` | `_run_crawl()` | 서버 시작 10초 후 | 60분 (`CRAWL_INTERVAL_MINUTES`) |
| `analyze` | `_run_analyze()` | 서버 시작 15초 후 | 5분 (`ANALYSIS_INTERVAL_MINUTES`) |

- 잡 완료 후 `add_job(replace_existing=True)`으로 다음 실행 재등록 (DateTrigger one-shot 방식)
- 각 잡은 threading.Lock으로 동시 실행 방지

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

### validate_and_parse 처리 흐름 (validators.py)

1. JSON 파싱 (`json.loads`)
2. 필수 필드 검증: `suitability`, `suitability_reason`, `case_category`, `summary`
3. `suitability` 값 검증 (High/Medium/Low 아니면 Low로 보정)
4. `stage` 값 검증 (유효하지 않으면 빈값으로 보정)
5. 기본값 설정: defendant, damage_amount, victim_count, stage, stage_detail, case_name, is_relevant
6. `is_relevant` 타입 검증 (boolean 아니면 True로 보정)
7. `summary` 길이 제한 (1000자)

### build_messages (prompts.py)

- 본문 3000자 제한 (토큰 절약)
- 기존 사건 그룹 목록을 시스템 프롬프트 말미에 추가
- system → few-shot (user/assistant 3쌍) → user(실제 기사) 순서로 메시지 구성

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

#### ArticleViewSet

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/articles/` | 기사 목록 (필터, 검색, 페이지네이션) |
| GET | `/api/articles/{id}/` | 기사 상세 |
| POST | `/api/articles/{id}/reanalyze/` | 기사 재분석 요청 |

#### KeywordViewSet

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/keywords/` | 키워드 목록 |
| POST | `/api/keywords/` | 키워드 추가 |
| DELETE | `/api/keywords/{id}/` | 키워드 삭제 |

#### MediaSourceViewSet

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/sources/` | 언론사 목록 |

#### CaseGroupViewSet

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/case-groups/` | 케이스 그룹 목록 |
| GET | `/api/case-groups/{id}/` | 케이스 그룹 상세 |

- 검색: case_id, name
- 정렬: -created_at
- CaseGroupSerializer: article_count 어노테이션 포함

#### Swagger

```
GET /api/docs/              → Swagger UI (drf-spectacular)
GET /api/schema/            → OpenAPI 스키마
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

### ERD (엔티티 관계도)

```
┌─────────────────┐       ┌────────────────────────────────────────────┐
│   MediaSource   │       │                 Article                    │
│─────────────────│       │────────────────────────────────────────────│
│ PK id           │       │ PK id                                     │
│    name (uniq)  │◄──1:N─│ FK source_id → MediaSource (nullable)     │
│    url          │       │    title                                  │
│    is_active    │       │    content                                │
│    created_at   │       │    url (unique)                           │
└─────────────────┘       │    author                                 │
                          │    published_at                           │
┌─────────────────┐       │    collected_at                           │
│    Keyword      │       │    status (pending/analyzing/analyzed/failed)│
│─────────────────│       │    retry_count                            │
│ PK id           │       └────────────┬───────────────────────────────┘
│    word (uniq)  │                    │
│    is_active    │                    │ 1:1
│    created_at   │                    │
└────────┬────────┘                    │
         │                             ▼
         │ M:N              ┌────────────────────────────────────────────┐
         │ (ArticleKeyword) │                Analysis                    │
         └─────────────────▶│────────────────────────────────────────────│
                            │ PK id                                     │
┌─────────────────┐         │ FK article_id → Article (OneToOne)        │
│   CaseGroup     │         │ FK case_group_id → CaseGroup (nullable)  │
│─────────────────│         │    suitability (High/Medium/Low)          │
│ PK id           │◄───N:1──│    suitability_reason                     │
│    case_id (uniq│         │    case_category                          │
│    name         │         │    defendant                              │
│    description  │         │    damage_amount                          │
│    created_at   │         │    victim_count                            │
│    updated_at   │         │    stage                                  │
└─────────────────┘         │    stage_detail                           │
                            │    summary                                │
                            │    is_relevant                            │
                            │    llm_model                              │
                            │    prompt_tokens / completion_tokens       │
                            │    analyzed_at                            │
                            └────────────────────────────────────────────┘
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

**명령어**: `python manage.py seed_initial_data` (또는 `just seed`)

**생성 내용**:
- MediaSource: 80개 이상 주요 언론사 (종합일간지, 방송/통신, 경제, 인터넷, IT 전문, 매거진, 전문지, 지역)
- Keyword: 7개 기본 키워드 (`get_or_create`): 소송, 손해배상, 집단소송, 공동소송, 피해자, 피해보상, 피해구제

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

## FS-013. config — Django 프로젝트 설정

**경로**: `backend/config/`

### settings.py

| 설정 그룹 | 주요 설정 |
|----------|----------|
| INSTALLED_APPS | django 기본 + rest_framework, django_filters, corsheaders, drf_spectacular, articles, analyses |
| DATABASE | SQLite (backend/db.sqlite3) |
| REST_FRAMEWORK | PageNumberPagination(20), DjangoFilterBackend, SearchFilter, OrderingFilter |
| CORS | localhost:5173, localhost:3000 허용 |
| Celery | Redis broker/backend, JSON 직렬화, Asia/Seoul |
| LLM | OPENAI_API_KEY, GEMINI_API_KEY, LLM_MODEL, GEMINI_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS |
| Naver | NAVER_CLIENT_ID, NAVER_CLIENT_SECRET |
| i18n | ko-kr, Asia/Seoul |

### urls.py

| URL 패턴 | 대상 |
|----------|------|
| `/admin/` | Django 관리자 페이지 |
| `/api/` | articles.urls + analyses.urls |
| `/api/schema/` | drf-spectacular OpenAPI 스키마 |
| `/api/docs/` | Swagger UI |

### celery.py

- Django 설정 기반 Celery 앱 구성
- `autodiscover_tasks()`: articles, analyses 앱의 tasks.py 자동 등록

---

## FS-014. 크롤러 상세

**모듈**: `backend/articles/crawlers.py`

| 함수 | 설명 |
|------|------|
| `search_naver_news(keyword, display=100)` | 네이버 뉴스 검색 API 호출. 키워드별 최대 100건 반환 |
| `fetch_article_content(naver_url)` | 네이버 뉴스 페이지에서 `#dic_area` 영역의 본문 텍스트 추출 |
| `clean_html(text)` | HTML 태그 및 엔티티 제거 |
| `parse_naver_date(date_str)` | 네이버 API 날짜 형식 → datetime 변환 |
| `extract_source_from_url(url)` | URL 도메인을 언론사명으로 매핑 (60개+ 도메인) |
| `extract_source_from_naver_page(url)` | 네이버 뉴스 페이지에서 언론사 로고 alt 텍스트 추출 |

**언론사 식별 2단계 프로세스:**
1. `extract_source_from_url`: originallink 도메인으로 매핑 (빠르고 정확)
2. `extract_source_from_naver_page`: 1단계 실패 시 네이버 페이지 스크래핑 (느리지만 범용)

---

## FS-015. 모델 상세 (articles)

### MediaSource (언론사)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | BigAutoField (PK) | 자동 증가 기본키 |
| `name` | CharField(100), unique | 언론사명 (예: "조선일보") |
| `url` | URLField(500), blank | 언론사 홈페이지 URL |
| `is_active` | BooleanField, default=True | 활성화 여부 |
| `created_at` | DateTimeField, auto_now_add | 등록일시 |

- 초기 데이터: 80개 언론사 (종합일간지, 방송/통신, 경제, 인터넷, IT 전문, 매거진, 지역)

### Keyword (검색 키워드)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | BigAutoField (PK) | 자동 증가 기본키 |
| `word` | CharField(50), unique | 검색 키워드 (예: "집단소송") |
| `is_active` | BooleanField, default=True | 활성화 여부 |
| `created_at` | DateTimeField, auto_now_add | 등록일시 |

- 초기 데이터: 소송, 손해배상, 집단소송, 공동소송, 피해자, 피해보상, 피해구제 (7개)

### Article (기사)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | BigAutoField (PK) | 자동 증가 기본키 |
| `source` | FK → MediaSource, nullable | 언론사 |
| `title` | CharField(500) | 기사 제목 (HTML 태그 제거됨) |
| `content` | TextField | 기사 본문 (네이버 뉴스 페이지에서 추출) |
| `url` | URLField(1000), unique | 기사 URL (중복 크롤링 방지 키) |
| `author` | CharField(100), blank | 기자명 |
| `published_at` | DateTimeField | 기사 발행일시 |
| `collected_at` | DateTimeField, auto_now_add | 수집일시 |
| `status` | CharField(20), indexed | 상태: `pending` / `analyzing` / `analyzed` / `failed` |
| `retry_count` | IntegerField, default=0 | 분석 재시도 횟수 |
| `keywords` | M2M → Keyword (through ArticleKeyword) | 수집에 사용된 키워드 |

- 인덱스: `status`, `-published_at`

### ArticleKeyword (기사-키워드 중간 테이블)

| 필드 | 타입 | 설명 |
|------|------|------|
| `article` | FK → Article | 기사 |
| `keyword` | FK → Keyword | 키워드 |
| `created_at` | DateTimeField, auto_now_add | 연결일시 |

- unique_together: (article, keyword)

### Article API 필터 파라미터

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `status` | 상태 필터 | `pending`, `analyzed` |
| `source` | 언론사 ID | `1` |
| `date_from` | 발행일 시작 | `2026-02-01` |
| `date_to` | 발행일 끝 | `2026-02-20` |
| `search` | 제목/본문 검색 | `쿠팡` |
| `ordering` | 정렬 | `-published_at`, `collected_at` |

---

## FS-016. 모델 상세 (analyses)

### CaseGroup (사건 그룹)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | BigAutoField (PK) | 자동 증가 기본키 |
| `case_id` | CharField(30), unique | 사건 ID (예: "CASE-2026-001") |
| `name` | CharField(200) | 사건명 (예: "쿠팡 개인정보 유출") |
| `description` | TextField, blank | 사건 설명 |
| `created_at` | DateTimeField, auto_now_add | 생성일시 |
| `updated_at` | DateTimeField, auto_now | 수정일시 |

**클래스 메서드:** `generate_next_case_id()` — 현재 연도 기반으로 `CASE-YYYY-NNN` 형식의 다음 ID 생성

### Analysis (분석 결과)

| 필드 | 타입 | 설명 |
|------|------|------|
| `article` | OneToOneField → Article | 분석 대상 기사 (1:1) |
| `case_group` | FK → CaseGroup, nullable | 소속 사건 그룹 |
| `suitability` | CharField(10), indexed | 적합도: `High` / `Medium` / `Low` |
| `suitability_reason` | TextField | 판단 근거 (C1~C6, X1 참조) |
| `case_category` | CharField(100), indexed | 사건 분야 |
| `defendant` | CharField(200), blank | 상대방 (기업명/기관명) |
| `damage_amount` | CharField(200), blank | 피해 규모 |
| `victim_count` | CharField(200), blank | 피해자 수 |
| `stage` | CharField(50), indexed | 소송 단계 |
| `stage_detail` | CharField(200), blank | 단계 상세 설명 |
| `summary` | TextField | AI 생성 3~5문장 요약 |
| `is_relevant` | BooleanField, default=True, indexed | 법적 분쟁 관련 여부 |
| `llm_model` | CharField(50) | 사용된 LLM 모델명 |
| `prompt_tokens` / `completion_tokens` | IntegerField | 토큰 수 |
| `analyzed_at` | DateTimeField, auto_now_add | 분석 완료일시 |

**stage 선택지:** 피해 발생 / 관련 절차 진행 / 소송중 / 판결 선고 / 종결

### 시리얼라이저

- **AnalysisListSerializer**: 기본 필드 + `article_title`, `article_url`, `source_name`, `published_at` (Article 플래튼), `case_id`, `case_name` (CaseGroup 플래튼), `related_count`
- **AnalysisDetailSerializer**: 위 + `article` 객체, `case_group` 객체, `related_articles` (같은 사건 그룹 최근 10건)
- **ArticleListSerializer**: id, title, url, source_name, author, published_at, collected_at, status
- **ArticleDetailSerializer**: 위 + source 객체, keywords 배열, content 본문

### 유사도 매칭 세부 (find_or_create_case_group)

- 기본: `SequenceMatcher` 문자열 유사도
- 법률 일반 용어 28개 stopword 제외 (소송, 분쟁, 사건, 피해 등)
- 핵심 엔티티(2자 이상) 공유 시 보너스 +0.25
- 3자 이상 엔티티의 부분 문자열 매칭 시 보너스 +0.25
- 임계값: 0.6 이상이면 기존 그룹에 매칭

### 사건 그룹 매칭 흐름

```
 LLM 응답의 case_name
         │
         ▼
 1) 정확 일치하는 CaseGroup 존재?
         │
    ┌────┴────┐
   YES       NO
    │         │
    ▼         ▼
 기존 그룹   2) 유사도 ≥ 0.6인 CaseGroup 존재?
 반환            │
            ┌───┴───┐
           YES     NO
            │       │
            ▼       ▼
         기존 그룹  3) 새 CaseGroup 생성
         반환       CASE-YYYY-NNN
```

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v2.3 | 2026-03-05 | 스케줄러-관리명령어 충돌 수정, `crawl_news` management command 신규, CLI 출력 개선 |
| v2.2 | 2026-02-27 | 기능명세서.md 내용 통합 (모델 상세, config, 크롤러, ERD, 시리얼라이저 등) |
| v2.1 | 2026-02-24 | 초안 작성 (현재 코드베이스 기반) |
| v2.0 | - | Gemini로 LLM 교체, 동기 파이프라인 도입, is_relevant 필드 추가 |
| v1.0 | - | OpenAI GPT-4o, Celery 기반 초기 버전 |

---

## 개발 트러블슈팅 이력

> 구현 과정에서 발생한 실제 버그와 설계 변경 이력입니다.
> "원래 이렇게 만들었는데, 이런 문제가 생겨서, 이렇게 바꿨다"를 코드 레벨로 기록합니다.

---

### TS-001. SQLite 동시 쓰기 잠금 → PostgreSQL 전환

**발생 시점**: v2.0 APScheduler 도입 직후

**원래 구현**

```python
# settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

**증상**

APScheduler가 백그라운드 스레드에서 `analyze_single_article()`을 실행하는 동안,
Django dev 서버가 `/api/analyses/` 요청을 처리하면 아래 에러가 반복 발생:

```
django.db.utils.OperationalError: database is locked
```

**원인 분석**

SQLite는 동시 쓰기(Concurrent Write)를 지원하지 않는다.
파일 레벨 락(WAL 모드에서도 단일 writer)이기 때문에, 분석 스레드가
`Article.status = "analyzing"`으로 쓰는 순간 웹 요청 스레드의 쓰기가 차단된다.

**해결**

```python
# settings.py — DATABASE_URL 파싱 직접 구현 (dj-database-url 라이브러리 없이)
import os, urllib.parse

_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("postgresql"):
    _r = urllib.parse.urlparse(_db_url)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _r.path.lstrip("/"),
        "USER": _r.username, "PASSWORD": _r.password,
        "HOST": _r.hostname, "PORT": _r.port or 5432,
    }}
```

Docker Compose로 PostgreSQL 16-alpine 컨테이너 구성:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: law_news
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
```

기존 SQLite 데이터 이전:
```python
# 데이터 덤프 (SQLite에서)
uv run python manage.py dumpdata --natural-foreign > backup.json
# PostgreSQL로 로드
uv run python manage.py loaddata backup.json
```

**교훈**

멀티스레드 환경(APScheduler + Django dev server)에서는 처음부터 PostgreSQL을 사용해야 한다.
"개발은 SQLite, 운영은 PostgreSQL"은 동시 I/O가 있는 순간 유지 불가능한 전략이다.

---

### TS-002. APScheduler 단일 파이프라인 잡 → 수집/분석 독립 분리

**발생 시점**: v2.0 초기 스케줄러 구현 후

**원래 구현**

```python
# 수집 + 분석을 하나의 잡으로 묶음
def _run_pipeline_job():
    crawl_news()          # 수집 (수 분 소요)
    analyze_pending()     # 분석 (수십 분 소요)

scheduler.add_job(
    _run_pipeline_job,
    trigger="interval",
    minutes=60,
)
```

**증상 / 문제**

1. 분석이 오래 걸릴수록 다음 수집 시작이 지연됨 (블로킹 구조)
2. 수집 직후 새 기사가 쌓이는데 분석은 60분 후에야 다시 시작 → 대기 기사 누적
3. 분석 잡 실행 중 수집 잡이 또 시작되면 동일 기사를 두 스레드가 `analyzing`으로 변경 시도

**해결**

```python
# scheduler.py — 두 잡 독립 분리
_crawl_lock = threading.Lock()
_analyze_lock = threading.Lock()

def _run_crawl():
    if not _crawl_lock.acquire(blocking=False):
        return  # 이미 실행 중이면 스킵
    try:
        crawl_news()
    finally:
        _crawl_lock.release()
        _reschedule("crawl", 60)  # 완료 후 다음 실행 재등록

def _run_analyze():
    if not _analyze_lock.acquire(blocking=False):
        return
    try:
        for article in Article.objects.filter(status="pending"):
            analyze_single_article(article)
    finally:
        _analyze_lock.release()
        _reschedule("analyze", 5)

# 각각 독립 잡으로 등록
scheduler.add_job(_run_crawl,   trigger=DateTrigger(...+10s), id="crawl")
scheduler.add_job(_run_analyze, trigger=DateTrigger(...+15s), id="analyze")
```

**교훈**

수집 주기(60분)와 분석 주기(5분)는 본질적으로 다르다. 처음부터 분리하는 것이 맞다.
Lock을 잡이 아닌 함수 레벨에 두면 스케줄러가 중복 실행을 트리거해도 안전하다.

---

### TS-003. APScheduler DateTrigger 잡 재예약 버그

**발생 시점**: TS-002 독립 잡 분리 직후

**원래 구현**

```python
def _reschedule(job_id: str, minutes: int):
    next_run = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    _scheduler.reschedule_job(job_id, trigger=DateTrigger(run_date=next_run))
```

**증상**

서버 로그에 매 잡 완료마다 아래 에러 출력:

```
analyze 재예약 실패: 'No job by the id of analyze was found'
```

**원인 분석**

`DateTrigger`는 **one-shot trigger**다. 지정 시각에 한 번 실행되면 APScheduler가
해당 잡을 스케줄러 내부 목록에서 **자동 삭제**한다.
`reschedule_job()`은 기존 잡의 트리거를 교체하는 함수인데,
잡이 이미 삭제된 상태에서 호출하면 `JobLookupError`가 발생한다.

**해결**

```python
def _reschedule(job_id: str, minutes: int):
    """DateTrigger 잡은 실행 후 자동 삭제되므로 add_job으로 재등록"""
    next_run = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    job_func = _run_crawl if job_id == "crawl" else _run_analyze
    _scheduler.add_job(
        job_func,
        trigger=DateTrigger(run_date=next_run),
        id=job_id,
        replace_existing=True,  # 혹시 남아있는 잡도 교체
        max_instances=1,
    )
```

**교훈**

`IntervalTrigger`와 `DateTrigger`의 동작이 다르다.
`IntervalTrigger`는 잡을 유지하며 반복 실행하지만,
`DateTrigger`는 one-shot이라 실행 후 잡이 사라진다.
"완료 후 N분 뒤 재실행" 패턴에서는 `IntervalTrigger` 대신 이 방식이 더 명시적이다.

---

### TS-004. `just crawl` 스케줄러 충돌 → management command 분리

**발생 시점**: v2.3 운영 중

**원래 구현**

```python
# justfile
crawl:
    {{manage}} shell -c "from articles.tasks import crawl_news_sync; n = crawl_news_sync(); print(f'수집 완료: {n}건')"
```

```python
# articles/tasks.py
@shared_task
def crawl_news_sync():
    """동기식 크롤링 (테스트/수동 실행용) — Celery 없이 직접 호출"""
    return crawl_news()
```

**증상**

`just crawl` 실행 시 아래 두 가지 문제 동시 발생:

```
analyze 재예약 실패: 'No job by the id of analyze was found'

object type name: KeyboardInterrupt
lost sys.stderr
```

**원인 분석**

`manage.py shell -c "..."` 실행 시 Django가 로드되면서 `AppConfig.ready()` → `start_scheduler()` 호출.
스케줄러가 백그라운드에서 10초 후 `crawl` 잡, 15초 후 `analyze` 잡을 실행 예약.
동시에 shell 커맨드도 `crawl_news_sync()`를 직접 호출 → **이중 수집 실행**.

크롤링 중 `extract_source_from_naver_page()`가 HTTP 요청을 보내는 C 레이어에서
인터럽트가 발생하면 Python이 정상적으로 예외를 처리하지 못하고 `lost sys.stderr` 발생.

`analyze 재예약 실패`는 TS-003의 DateTrigger 버그가 이 상황에서 추가로 노출된 것.

**해결**

1. `crawl_news` management command 신규 생성

```python
# articles/management/commands/crawl_news.py
class Command(BaseCommand):
    help = "활성 키워드로 네이버 뉴스 수집 (스케줄러 없이 단독 실행)"

    def handle(self, *args, **options):
        from articles.tasks import crawl_news
        n = crawl_news()
        self.stdout.write(self.style.SUCCESS(f"수집 완료: {n}건"))
```

2. `SchedulerConfig.ready()`에 관리 명령어 감지 로직 추가

```python
# scheduler/apps.py
_NO_SCHEDULER_CMDS = {
    "shell", "migrate", "crawl_news", "run_analysis", ...
}

def ready(self):
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    is_manage_py = "manage.py" in (sys.argv[0] if sys.argv else "")

    if is_manage_py and cmd in _NO_SCHEDULER_CMDS:
        return  # 관리 명령어에서는 스케줄러 미시작
    ...
```

3. `crawl_news_sync` 제거 (`shell -c` 패턴과 함께 폐기)

**교훈**

`manage.py shell -c`는 Django 전체를 로드하므로 `AppConfig.ready()`도 실행된다.
"스크립트처럼 쓰는 shell 커맨드"와 "서버 환경"은 분리되어야 한다.
수동 실행이 필요한 기능은 반드시 전용 management command로 만들어야 한다.

---

### TS-005. `just analyze` 진행 상황 불투명 → 건별 실시간 출력

**발생 시점**: v2.2 운영 중 (사용성 문제)

**원래 구현**

```python
# run_analysis.py
for i, article in enumerate(qs.iterator(), 1):
    ok = analyze_single_article(article)
    if i % 50 == 0:  # 50건마다 한 번 출력
        self.stdout.write(f"  {i}/{total} 완료...")
```

**증상**

기사 1건 분석에 평균 1~2초 소요. 50건이 쌓일 때까지 CLI에 아무 출력이 없어
"멈춘 건지, 실행 중인 건지" 알 수 없었다. 특히 첫 50건이 완료되기까지 최대 1~2분간
완전한 침묵.

**해결**

```python
# 건별 즉시 출력 + 10건마다 ETA 요약
for i, article in enumerate(qs.iterator(), 1):
    t0 = time.time()
    ok = analyze_single_article(article)
    elapsed_item = time.time() - t0

    tag = self.style.SUCCESS("✓") if ok else self.style.ERROR("✗")
    self.stdout.write(f"[{i:{pad}d}/{total}] {tag} {elapsed_item:5.1f}s │ {article.title[:60]}")

    if i % 10 == 0:
        avg = (time.time() - start) / i
        eta = _eta(time.time() - start, i, total)
        self.stdout.write(f"  진행 {i/total*100:5.1f}% │ 평균 {avg:.1f}s/건 │ 남은시간 약 {eta}")
```

출력 예시:
```
분석 시작: 307건
────────────────────────────────────────────────────────────────────────
[  1/307] ✓  1.2s │ 법무법인 '허위 소송비' 수임료 반환 소송...
[  2/307] ✓  0.9s │ 재건축 조합장 업무상 배임 혐의로...
...
[  10/307]          진행  3.2% │ 평균 1.1s/건 │ 남은시간 약 5분
────────────────────────────────────────────────────────────────────────
완료: 307건 처리 — 성공 300  실패 7  (소요 5.6분, 평균 1.1s/건)
```

**교훈**

배치 처리 CLI는 처음부터 건별 실시간 출력을 해야 한다.
"50건마다 출력"은 개발자 입장에서 로그 비용을 줄이는 것처럼 보이지만,
실제로는 프로세스 상태를 알 수 없어서 불안감만 키운다.
