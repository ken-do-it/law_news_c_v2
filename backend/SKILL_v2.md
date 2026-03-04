---
name: law-news-analyzer
description: AI 기반 법률 뉴스 분석 시스템 개발을 위한 단계별 프로세스 가이드. 뉴스 크롤링, LLM 기반 소송금융 적합도 분석, 웹 대시보드, 엑셀 내보내기를 포함한 PoC/MVP 개발.
updated: 2026-03-04
---

# Law News Analyzer - 개발 프로세스 가이드

AI 기반 법률 분쟁 사건 자동 발굴 시스템의 PoC/MVP 개발을 단계별로 진행하기 위한 종합 가이드입니다.

> **⚠️ 주의**: 하단 초기 계획의 일부 기술 스택은 실제 구현과 다를 수 있습니다. 현재 구현 상태는 아래 섹션을 참조하세요.

---

## 현재 구현 상태 (2026-03-04 기준)

### 실제 기술 스택

| 항목 | 초기 계획 | 현재 구현 |
|------|----------|----------|
| **데이터베이스** | SQLite → PostgreSQL (배포 시) | PostgreSQL 16 (Docker, 개발부터) |
| **비동기/스케줄링** | Celery + Redis | APScheduler (인프라 단순화) |
| **프론트엔드** | Next.js | Vite + React + TypeScript |
| **LLM** | OpenAI GPT-4o | Google Gemini 2.5 Flash (기본) |
| **패키지 관리** | pip / requirements.txt | uv (pyproject.toml) |
| **크롤링** | Celery 태스크 | APScheduler 파이프라인 (`_run_pipeline`) |
| **수집 주기** | 60분 | 60분 (`CRAWL_INTERVAL_MINUTES=60`) |
| **분석 주기** | 60분 (수집과 묶음) | 5분 (`ANALYSIS_INTERVAL_MINUTES=5`) |

### 현재 아키텍처

```
[APScheduler] ──5분마다──▶ crawl_news_sync() ──▶ analyze_single_article()
                                 │                        │
                          Naver News API          Gemini 2.5 Flash API
                                 │                        │
                          articles (PostgreSQL)   analyses + case_groups
```

### 주요 환경 변수 (.env)

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/law_news
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
CRAWL_INTERVAL_MINUTES=60
ANALYSIS_INTERVAL_MINUTES=5
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```

### 자주 쓰는 명령어 (Justfile)

```bash
just pg-start          # PostgreSQL Docker 컨테이너 시작
just dev               # 백엔드 + 프론트엔드 동시 실행
just analyze           # 전체 pending 기사 재분석
just analyze --limit 100  # 100건만 분석
just db-reset-analyses # Analysis+CaseGroup만 초기화 (기사 유지)
just stats             # DB 통계 확인
```

### Case Group 분류 로직 (현재 임계값)

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `CASE_SIMILARITY_THRESHOLD` | 0.85 | 사건명 유사도 기준 |
| `TITLE_KEYWORD_MATCH_COUNT` | 4 | 제목 키워드 일치 최소 수 |
| `get_existing_case_names()` | 최근 90일 + 최대 150그룹 | LLM 컨텍스트에 넘기는 기존 사건 목록 |

---

아래는 초기 계획 원문 (참조용) ↓

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | AI 기반 법률 분쟁 사건 자동 발굴 시스템 |
| 클라이언트 | 로앤굿 (소송금융 전문 법률회사) |
| 기간 | 1개월 (PoC/MVP) |
| 팀 구성 | 2~3명 |
| 결과물 | 웹 대시보드 + 엑셀 다운로드 |

## 핵심 원칙

### 개발 철학
- **가이드라인 충실도**: 로앤굿 가이드라인의 판단 기준을 코드와 프롬프트에 정확히 반영
- **단계별 승인 프로세스**: 각 단계 완료 시 사용자 테스트 및 승인 필수
- **AI 정확도 우선**: 프롬프트 엔지니어링과 테스트를 통해 분석 정확도 극대화
- **비용 최적화**: LLM API 호출 최소화 전략 (키워드 필터링 → LLM 분석)
- **MVP 집중**: 핵심 기능에 집중하고, 부가 기능은 시간 여유 시 추가

### 기술 스택 (현재 구현 기준)
- **백엔드**: Django 5.x + Django REST Framework + drf-spectacular
- **프론트엔드**: Vite + React + TypeScript + Tailwind CSS
- **데이터베이스**: PostgreSQL 16 (Docker, psycopg[binary])
- **스케줄링**: APScheduler (Celery 불필요, Redis 불필요)
- **크롤링**: 네이버 뉴스 API + requests
- **LLM**: Google Gemini 2.5 Flash (기본), OpenAI GPT-4o (선택)
- **엑셀**: openpyxl
- **패키지 관리**: uv (Python), bun (JS)
- **태스크 러너**: Justfile

### 팀 역할 분담 (2~3명)
| 역할 | 담당 업무 |
|------|----------|
| 백엔드 (1명) | Django API, 크롤링, Celery, 엑셀 다운로드 |
| AI (1명) | LLM 프롬프트 엔지니어링, 분석 정확도 테스트, 파이프라인 |
| 프론트 (1명) | react 대시보드, 필터링/정렬 UI, API 연동 |

> 2명 팀일 경우: 백엔드+AI를 한 사람이 맡고, 프론트를 다른 사람이 맡는 구조

---

## 개발 흐름 (Development Flow)

```
Phase 1: 프로젝트 초기화 & 환경 설정
  1.1 Django 프로젝트 생성 → 1.2 Docker Compose 설정 → 1.3 DB 마이그레이션
  ↓ [사용자 승인: 서버 실행, Admin 접근 확인]

Phase 2: 데이터베이스 & 모델
  2.1 모델 구현 (5개 테이블) → 2.2 Admin 커스터마이징 → 2.3 초기 데이터 입력
  ↓ [사용자 테스트: Admin에서 데이터 CRUD]

Phase 3: 뉴스 크롤링 시스템
  3.1 크롤링 로직 구현 → 3.2 Celery 태스크 설정 → 3.3 스케줄러 설정
  ↓ [사용자 테스트: 크롤링 실행, DB에 기사 저장 확인]

Phase 4: LLM 분석 파이프라인
  4.1 프롬프트 설계 → 4.2 API 호출 로직 → 4.3 응답 검증 → 4.4 정확도 테스트
  ↓ [사용자 테스트: 6개 샘플 기사로 정확도 검증 (목표: 100%)]

Phase 5: REST API 개발
  5.1 Serializer → 5.2 ViewSet → 5.3 필터링/정렬 → 5.4 엑셀 다운로드
  ↓ [사용자 테스트: Swagger UI에서 API 동작 확인]

Phase 6: 프론트엔드 대시보드
  6.1 레이아웃 → 6.2 메인 대시보드 → 6.3 분석 목록/상세 → 6.4 차트
  ↓ [사용자 테스트: 대시보드 UI/UX 확인]

Phase 7: 통합 테스트 & 최적화
  7.1 전체 파이프라인 테스트 → 7.2 성능 최적화 → 7.3 에러 핸들링
  ↓ [사용자 테스트: 전체 흐름 동작 확인]

Phase 8: 배포
  8.1 배포 환경 설정 → 8.2 배포 → 8.3 최종 검증
  ↓ [프로덕션 준비 완료]
```

---

## Phase 1: 프로젝트 초기화 & 환경 설정

### 1.1 Django 프로젝트 생성

**목표**: 프로젝트 기본 구조 생성 및 패키지 설치

**프로젝트 폴더 구조**:
```
law-news-analyzer/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── celery.py
│   ├── articles/          # 뉴스 기사 앱
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py       # 크롤링 Celery 태스크
│   │   └── admin.py
│   ├── analyses/          # AI 분석 앱
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py       # LLM 분석 Celery 태스크
│   │   ├── prompts.py     # 프롬프트 관리
│   │   ├── validators.py  # 응답 검증
│   │   └── export.py      # 엑셀 내보내기
│   └── manage.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx       # 메인 대시보드
│   │   ├── analyses/
│   │   └── settings/
│   └── components/
└── README.md
```

**필수 패키지** (requirements.txt):
```
Django>=5.0
djangorestframework>=3.14
django-cors-headers>=4.3
django-filter>=23.5
celery>=5.3
redis>=5.0
requests>=2.31
beautifulsoup4>=4.12
openai>=1.0
openpyxl>=3.1
psycopg2-binary>=2.9
python-dotenv>=1.0
gunicorn>=21.2
```

**환경 변수** (.env):
```env
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=law_news_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# LLM API
OPENAI_API_KEY=your-openai-api-key
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1000

# 크롤링 설정
CRAWL_INTERVAL_MINUTES=60
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret

# 프론트엔드
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

**완료 기준**:
- [ ] Django 프로젝트 생성 완료
- [ ] articles, analyses 앱 생성 완료
- [ ] 패키지 설치 완료
- [ ] .env 파일 설정 완료

**사용자 승인 요청**:
```
📋 검토 요청:

1. 프로젝트 구조가 적절한가요?
2. 패키지 목록에 빠진 것이 있나요?
3. 환경 변수 설정이 맞나요?

승인 시 Docker Compose 설정으로 진행합니다.
```

---

### 1.2 Docker Compose 설정

**목표**: 모든 서비스를 Docker로 통합 실행

**docker-compose.yml 구조**:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: law_news_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery:
    build: ./backend
    command: celery -A config worker -l info
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery-beat:
    build: ./backend
    command: celery -A config beat -l info
    depends_on:
      - db
      - redis
    env_file:
      - .env

  frontend:
    build: ./frontend
    command: npm run dev
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

**Bash 명령어**:
```bash
# 전체 서비스 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f backend

# 마이그레이션 실행
docker-compose exec backend python manage.py migrate

# 슈퍼유저 생성
docker-compose exec backend python manage.py createsuperuser
```

**사용자 테스트**:
```
🧪 환경 설정 테스트:

터미널에서: docker-compose up -d

접속 확인:
✅ http://localhost:8000/admin/ - Django Admin 로그인
✅ http://localhost:8000/api/ - DRF API 루트
✅ http://localhost:3000/ - React  프론트엔드

모두 정상이면 승인해주세요.
```

---

## Phase 2: 데이터베이스 & 모델

### 2.1 모델 구현 (5개 테이블)

**목표**: 가이드라인 분석 항목을 정확히 반영한 DB 모델 구현

**테이블 관계**:
```
MediaSource (1) ──< (N) Article (1) ── (1) Analysis
                          |
                     (N) ArticleKeyword (M)
                          |
                     Keyword (1)
```

**핵심 모델: Article (뉴스 기사)**

```python
class Article(models.Model):
    STATUS_CHOICES = [
        ('pending', '분석 대기'),
        ('analyzing', '분석 중'),
        ('analyzed', '분석 완료'),
        ('failed', '분석 실패'),
    ]

    source = models.ForeignKey(MediaSource, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=500)
    content = models.TextField()
    url = models.URLField(max_length=1000, unique=True)  # 중복 방지 핵심!
    author = models.CharField(max_length=100, blank=True, default='')
    published_at = models.DateTimeField()
    collected_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    keywords = models.ManyToManyField(Keyword, through='ArticleKeyword')

    class Meta:
        db_table = 'articles'
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['status']),
        ]
```

**핵심 모델: Analysis (AI 분석 결과)**

가이드라인의 6개 분석 항목이 그대로 컬럼이 됩니다:

| # | 가이드라인 항목 | DB 컬럼 |
|---|----------------|---------|
| 1 | 소송금융 적합도 | `suitability` + `suitability_reason` |
| 2 | 사건 분야 | `case_category` |
| 3 | 상대방 | `defendant` |
| 4 | 피해 규모 | `damage_amount` + `victim_count` |
| 5-1 | 진행 단계 | `stage` |
| 5-2 | 진행 단계 상세 | `stage_detail` |
| 6 | 요약 | `summary` |

```python
class Analysis(models.Model):
    SUITABILITY_CHOICES = [('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')]
    STAGE_CHOICES = [
        ('피해 발생', '피해 발생'),
        ('관련 절차 진행', '관련 절차 진행'),
        ('소송중', '소송중'),
        ('판결 선고', '판결 선고'),
        ('종결', '종결'),
    ]

    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name='analysis')
    suitability = models.CharField(max_length=10, choices=SUITABILITY_CHOICES, db_index=True)
    suitability_reason = models.TextField()
    case_category = models.CharField(max_length=100)
    defendant = models.CharField(max_length=200, blank=True, default='')
    damage_amount = models.CharField(max_length=200, blank=True, default='')
    victim_count = models.CharField(max_length=200, blank=True, default='')
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES, blank=True, default='')
    stage_detail = models.CharField(max_length=200, blank=True, default='')
    summary = models.TextField()
    llm_model = models.CharField(max_length=50, default='gpt-4o')
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analyses'
        ordering = ['-analyzed_at']
```

**status 필드 흐름 (중요!)**:
```
수집됨 → status="pending"
  → LLM 전송 → status="analyzing"
    → 성공 → status="analyzed" ✅
    → 실패 → status="failed" ❌ (60초 후 재시도, 최대 3번)
```

**설계 포인트**:
- `damage_amount`가 VARCHAR인 이유: "500억원 추정", "미상" 등 텍스트가 섞임
- `url`에 `unique=True`: 같은 기사 중복 저장 방지
- `db_index=True`: 필터링 성능 향상 (suitability, status, case_category 등)
- LLM 토큰 정보 저장: API 비용 추적용

**완료 기준**:
- [ ] 5개 모델 구현 완료
- [ ] 마이그레이션 성공
- [ ] Admin에서 모든 모델 확인 가능

**사용자 테스트**:
```
🧪 모델 테스트:

Admin 패널 접속: http://localhost:8000/admin/

확인 사항:
✅ MediaSource 목록이 보이나요?
✅ Keyword 추가가 가능한가요?
✅ Article 생성이 가능한가요?
✅ Analysis 생성이 가능한가요?
✅ URL 중복 시 에러가 나나요?

승인 시 크롤링 시스템으로 진행합니다.
```

---

## Phase 3: 뉴스 크롤링 시스템

### 3.1 크롤링 전략

**우선순위**:
1. **네이버 뉴스 검색 API** (추천 ⭐): 키워드 검색 한 번으로 60개 언론사 기사 수집 가능
2. **각 언론사 RSS 피드**: 네이버 API에 없는 언론사 보완
3. **직접 크롤링**: 최후의 수단 (robots.txt 확인 필수)

**수집 키워드** (가이드라인 기준):
- 소송, 손해배상, 집단소송, 공동소송, 피해자, 피해보상, 피해구제

**크롤링 로직 핵심**:
```python
@shared_task
def crawl_news():
    keywords = Keyword.objects.filter(is_active=True)
    
    for keyword in keywords:
        # 1. 네이버 뉴스 API 검색
        articles = search_naver_news(keyword.word)
        
        for article_data in articles:
            # 2. 중복 체크 (URL 기준)
            if Article.objects.filter(url=article_data['url']).exists():
                continue
            
            # 3. 기사 본문 크롤링
            content = fetch_article_content(article_data['url'])
            
            # 4. DB 저장 (status='pending')
            article = Article.objects.create(
                title=article_data['title'],
                content=content,
                url=article_data['url'],
                published_at=article_data['pub_date'],
                status='pending',
            )
            
            # 5. 키워드 연결
            ArticleKeyword.objects.create(article=article, keyword=keyword)
    
    # 6. 분석 태스크 자동 트리거
    analyze_pending_articles.delay()
```

**Celery Beat 스케줄** (config/celery.py):
```python
app.conf.beat_schedule = {
    'crawl-news-every-hour': {
        'task': 'articles.tasks.crawl_news',
        'schedule': crontab(minute=0),  # 매 정각 실행
    },
}
```

**완료 기준**:
- [ ] 네이버 뉴스 API 연동 완료
- [ ] 키워드 기반 기사 수집 동작
- [ ] URL 중복 방지 동작
- [ ] Celery 스케줄러 동작

**사용자 테스트**:
```
🧪 크롤링 테스트:

수동 실행:
docker-compose exec backend python manage.py shell
>>> from articles.tasks import crawl_news
>>> crawl_news()

확인 사항:
✅ Admin에서 수집된 기사가 보이나요?
✅ status가 "pending"인가요?
✅ 키워드가 올바르게 연결되었나요?
✅ 같은 기사가 중복 저장되지 않나요?

승인 시 LLM 분석 파이프라인으로 진행합니다.
```

---

## Phase 4: LLM 분석 파이프라인 ⭐ (핵심!)

### 4.1 프롬프트 설계

**이 Phase가 프로젝트의 성패를 결정합니다!**

**프롬프트 구성 (3단계)**:
```
[System Prompt] → AI의 역할 + 판단 기준 (가이드라인 반영)
[Few-shot Examples] → High/Medium/Low 정답 예시 3건
[User Prompt] → 실제 뉴스 기사 전달
```

**System Prompt 핵심 요소**:

1. **페르소나**: 소송금융 투자를 검토하는 전문 심사역
   - 원칙적인 법률 전문가
   - 공격적인 비즈니스 전략가

2. **적합도 판단 기준** (가이드라인 그대로):
   - 적합 조건 6가지 (C1~C6):
     - C1: 상대방 책임 명확
     - C2: 상대방 자력(배상능력) 충분
     - C3: 집단적 피해 (수십 명 이상)
     - C4: 피해 규모 큼 (수억 원 이상 또는 수만 명 이상)
     - C5: 증거 있음/확보 가능
     - C6: 공적 절차(소송 제외) 진행 중
   - 부적합 조건 1가지 (X1):
     - X1: 이미 종결된 사건
   - 등급: High(4개+), Medium(2~3개), Low(1개 이하 또는 부적합)

3. **응답 형식**: 반드시 JSON

**Few-shot Examples** (가이드라인 예시에서 3건 선별):
- High: 쿠팡 개인정보 유출 (C1, C2, C3, C6 → 4개 적합)
- Medium: 압타밀 분유 리콜 (C2, C3 → 2개 적합)
- Low: 5·18 유족 판결 (이미 판결 확정, 신규성 없음)

**LLM API 호출 설정**:
| 파라미터 | 값 | 이유 |
|---------|-----|------|
| model | gpt-4o | 한국어 이해도 높고 복잡한 법률 판단 가능 |
| temperature | 0.1 | **핵심!** 일관된 판단을 위해 낮게 설정 |
| max_tokens | 1000 | JSON 응답에 충분 |
| response_format | json_object | JSON 형식 강제 |
| content[:3000] | 본문 3000자 제한 | 토큰 절약 |

### 4.2 응답 검증 (Validation)

AI가 항상 완벽한 JSON을 주지 않으므로 검증 필수:
- suitability 값 검증 (High/Medium/Low만 허용)
- stage 값 검증 (5단계만 허용)
- 필수 필드 누락 시 기본값 처리
- summary 길이 초과 시 자르기

### 4.3 정확도 테스트

**테스트 데이터**: 로앤굿 제공 6개 샘플

| # | 사건 | 기대 적합도 | 기대 분야 |
|---|------|------------|----------|
| 1 | 넥슨 메이플키우기 | High | 확률형 아이템 |
| 2 | 5·18 유족 판결 | Low | 행정 |
| 3 | 압타밀 분유 리콜 | Medium | 제조물책임 |
| 4 | 애경산업 상표권 | Low | 지식재산권 |
| 5 | 구글 어시스턴트 | Low | 개인정보 |
| 6 | 쿠팡 개인정보 유출 | High | 개인정보 |

**정확도 목표**: 적합도 일치율 100% (6/6)

**완료 기준**:
- [ ] System Prompt 작성 완료
- [ ] Few-shot 예시 3건 준비 완료
- [ ] API 호출 로직 구현 완료
- [ ] 응답 검증 로직 구현 완료
- [ ] 6개 샘플 정확도 테스트 통과

**사용자 테스트**:
```
🧪 LLM 분석 테스트:

수동 실행:
docker-compose exec backend python manage.py shell
>>> from analyses.tasks import analyze_pending_articles
>>> analyze_pending_articles()

확인 사항:
✅ pending 기사가 analyzed로 바뀌었나요?
✅ Analysis 결과가 Admin에서 보이나요?
✅ 6개 샘플 적합도가 기대 결과와 일치하나요?
   - 넥슨: High? ✅/❌
   - 5·18: Low? ✅/❌
   - 압타밀: Medium? ✅/❌
   - 애경: Low? ✅/❌
   - 구글: Low? ✅/❌
   - 쿠팡: High? ✅/❌
✅ 판단 근거에 조건 번호(C1~C6)가 명시되어 있나요?

승인 시 REST API 개발로 진행합니다.
```

---

## Phase 5: REST API 개발

### 5.1 API 엔드포인트

| 메서드 | URL | 설명 |
|--------|-----|------|
| GET | `/api/articles/` | 수집된 기사 목록 (페이지네이션) |
| GET | `/api/articles/{id}/` | 기사 상세 + 분석 결과 |
| GET | `/api/analyses/` | 분석 결과 목록 (필터링/정렬) |
| GET | `/api/analyses/stats/` | 통계 데이터 (차트용) |
| GET | `/api/analyses/export/` | 엑셀 파일 다운로드 |
| GET | `/api/keywords/` | 수집 키워드 목록 |
| POST | `/api/articles/{id}/reanalyze/` | 기사 재분석 요청 |

### 5.2 필터링/정렬

```
GET /api/analyses/?suitability=High
GET /api/analyses/?case_category=개인정보
GET /api/analyses/?stage=피해발생
GET /api/analyses/?date_from=2026-01-01&date_to=2026-02-15
GET /api/analyses/?ordering=-analyzed_at (최신순)
GET /api/analyses/?search=쿠팡 (키워드 검색)
```

### 5.3 엑셀 다운로드

분석 결과를 가이드라인 예시와 동일한 형태의 .xlsx 파일로 내보내기:
- 시트 1: 분석 결과 전체 목록
- 컬럼: 기사 제목, 언론사, 게재일, 적합도, 판단 근거, 사건 분야, 상대방, 피해 규모, 진행 단계, 요약, 원문 링크

**완료 기준**:
- [ ] 모든 API 엔드포인트 동작 확인
- [ ] 필터링/정렬 동작 확인
- [ ] 엑셀 다운로드 동작 확인
- [ ] 페이지네이션 동작 확인

**사용자 테스트**:
```
🧪 API 테스트:

Swagger UI 접속: http://localhost:8000/api/docs/

확인 사항:
✅ GET /api/analyses/ - 목록 조회 정상
✅ GET /api/analyses/?suitability=High - 필터링 정상
✅ GET /api/analyses/export/ - 엑셀 다운로드 정상
✅ 엑셀 파일 내용이 가이드라인 예시와 유사한가?

승인 시 프론트엔드 대시보드로 진행합니다.
```

---

## Phase 6: 프론트엔드 대시보드

### 6.0 디자인 시스템

**디자인 컨셉**: 법률/금융 전문 서비스에 어울리는 Professional & Data-Driven 테마

| 항목 | 선택 | 이유 |
|------|------|------|
| 컬러 테마 | Deep Navy (#0F172A) + Gold (#F59E0B) | 법률/금융 전문성, 신뢰감 |
| 폰트 (제목) | DM Serif Display | 에디토리얼/권위감 |
| 폰트 (본문) | DM Sans | 가독성 높은 산세리프 |
| 배경 | #F1F5F9 (연한 슬레이트) | 눈의 피로 최소화 |
| 카드 | #FFFFFF + 1px border #E8ECF0 | 깔끔한 카드 UI |

**적합도 배지 (Suitability Badge)** — 가장 중요한 UI 요소:

| 등급 | 배경색 | 텍스트 | 아이콘 | 의미 |
|------|--------|--------|--------|------|
| **High** | rgba(225,29,72,0.12) | #E11D48 (레드) | ▲ | 즉시 검토 필요! |
| **Medium** | rgba(245,158,11,0.12) | #D97706 (앰버) | ● | 추가 확인 필요 |
| **Low** | rgba(107,114,128,0.1) | #6B7280 (그레이) | ▽ | 참고용 |

> High일수록 빨간색으로 눈에 띄게 → 로앤굿 심사역이 빠르게 중요 건을 찾을 수 있도록

**진행 단계 배지 (Stage Badge)**:

| 단계 | 배경 | 텍스트 |
|------|------|--------|
| 피해 발생 | #FEF3C7 | #92400E |
| 관련 절차 진행 | #DBEAFE | #1E40AF |
| 소송중 | #FCE7F3 | #9D174D |
| 판결 선고 | #E0E7FF | #3730A3 |
| 종결 | #F3F4F6 | #374151 |

### 6.1 페이지 구성 (4개 페이지)

| 페이지 | URL | 내용 |
|--------|-----|------|
| 메인 대시보드 | `/` | 통계 카드, 차트 3종, 최근 분석 테이블 |
| 분석 목록 | `/analyses` | 필터바 + 정렬 테이블 + 페이지네이션 + 엑셀 다운로드 |
| 분석 상세 | `/analyses/[id]` | 기사 정보 + AI 분석 6개 항목 + 판단 근거 |
| 설정 | `/settings` | 수집 키워드 관리 (태그 UI) |

### 6.2 페이지별 상세 레이아웃

#### 📊 메인 대시보드 (`/`)

```
┌─────────────────────────────────────────────────────────┐
│  [Top Navigation Bar - Deep Navy]                       │
│  Logo: LawNGood News Analyzer    [크롤링 활성 🟢] [👤]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📊 대시보드                                             │
│  AI 기반 법률 뉴스 분석 현황을 한눈에 확인하세요            │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 📰 오늘  │ │ 🔴 High  │ │ ✅ 분석  │ │ 💰 이번달│   │
│  │ 수집 23건│ │ 적합 4건 │ │ 완료 187│ │ ₩42만원  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                                                         │
│  ┌────────────────────┐ ┌────────────────────┐         │
│  │ 🥧 적합도 분포      │ │ 📊 사건 분야별 분포  │         │
│  │ [파이차트]          │ │ [가로 바차트]       │         │
│  │ High: 4  Med: 3    │ │ 개인정보 ████ 3    │         │
│  │ Low: 3             │ │ 제조물   ████ 3    │         │
│  └────────────────────┘ └────────────────────┘         │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │ 📈 주간 수집 추이 [라인차트]               │          │
│  │ ── 전체  ── High  -- Medium              │          │
│  └──────────────────────────────────────────┘          │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │ 최근 분석 결과              [전체 보기 →]  │          │
│  │ ┌────┬───────────┬────┬────┬────┬────┐  │          │
│  │ │적합│ 기사 제목   │분야│상대│단계│날짜│  │          │
│  │ ├────┼───────────┼────┼────┼────┼────┤  │          │
│  │ │High│ 쿠팡 여파..│개인│쿠팡│피해│1/27│  │          │
│  │ │High│ 넥슨 메이..│확률│넥슨│절차│1/25│  │          │
│  │ │Med │ 압타밀 英..│제조│다논│피해│1/28│  │          │
│  │ └────┴───────────┴────┴────┴────┴────┘  │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

**통계 카드 (4개)**:
- 오늘 수집: `GET /api/articles/?date=today` → count
- High 적합: `GET /api/analyses/?suitability=High&date=today` → count
- 분석 완료: `GET /api/analyses/stats/` → total_analyzed
- 이번 달 비용: `GET /api/analyses/stats/` → monthly_cost (토큰 기반 계산)

**차트 (3종)**:
- 적합도 분포: Recharts PieChart (도넛형, innerRadius=45)
- 사건 분야별: Recharts BarChart (가로 바, layout="vertical")
- 주간 추이: Recharts LineChart (전체/High/Medium 3개 라인)

#### 🔍 분석 목록 (`/analyses`)

```
┌──────────────────────────────────────────────────────┐
│  [필터 바 - 흰색 카드]                                 │
│  🔎 검색: [____________]                              │
│  적합도: [전체 ▼]  분야: [전체 ▼]  단계: [전체 ▼]      │
│  [📥 엑셀 다운로드]                                    │
├──────────────────────────────────────────────────────┤
│  총 187건                               최신순 정렬   │
│  ┌────┬──────────┬────┬─────┬─────┬────┬────┐       │
│  │적합│ 기사 제목 │분야│상대방│피해액│단계│날짜│ ↕정렬  │
│  ├────┼──────────┼────┼─────┼─────┼────┼────┤       │
│  │High│ 쿠팡...  │개인│쿠팡 │미상 │피해│1/27│       │
│  │High│ 넥슨...  │확률│넥슨 │500억│절차│1/25│       │
│  │High│ 테슬라...│제조│테슬라│수십억│절차│2/01│       │
│  │Med │ 압타밀...│제조│다논 │미상 │피해│1/28│       │
│  │Med │ 대형마트.│개인│미확정│미상 │절차│2/05│       │
│  │Low │ 5·18...  │행정│대한민│미상 │판결│1/22│       │
│  └────┴──────────┴────┴─────┴─────┴────┴────┘       │
│                                                      │
│            [1] [2] [3] [4] [5]  (페이지네이션)         │
└──────────────────────────────────────────────────────┘
```

**필터링 API 호출 패턴**:
```
GET /api/analyses/?suitability=High&case_category=개인정보&stage=피해발생
GET /api/analyses/?search=쿠팡&ordering=-analyzed_at
GET /api/analyses/?date_from=2026-01-01&date_to=2026-02-15
GET /api/analyses/?page=2&page_size=20
```

**테이블 기능**:
- 행 hover 시 배경색 변경 (#F8FAFC)
- 행 클릭 → `/analyses/[id]` 상세 페이지 이동
- 컬럼 헤더 클릭 → 정렬 토글 (ASC/DESC)
- 적합도, 진행 단계 → 배지 컴포넌트로 표시

#### 📄 분석 상세 (`/analyses/[id]`)

```
┌──────────────────────────────────────────────────────┐
│  ← 목록으로 돌아가기                                   │
│                                                      │
│  ┌──────────────────────────┐ ┌──────────────────┐   │
│  │ [왼쪽: 기사 + AI 분석]    │ │ [오른쪽: 상세카드]│   │
│  │                          │ │                  │   │
│  │ [High] [피해 발생]        │ │ 분석 상세 정보    │   │
│  │                          │ │ ──────────────── │   │
│  │ 📰 '쿠팡 여파' 입점       │ │ 🎯 적합도: High  │   │
│  │ 소상공인 신뢰도 하락…     │ │ 📁 분야: 개인정보│   │
│  │ 소공연, 집단소송 예고     │ │ 🏢 상대: 쿠팡    │   │
│  │                          │ │ 💰 피해액: 미상  │   │
│  │ 📰 신아일보 | 2026-01-27 │ │ 👥 피해자: 다수  │   │
│  │ 🔗 원문 보기              │ │ 📊 단계: 피해발생│   │
│  │                          │ │ 📝 상세: 집단소송│   │
│  │ ─────────────────────── │ │     예정         │   │
│  │                          │ │                  │   │
│  │ 🤖 AI 분석 요약           │ │ ──────────────── │   │
│  │ ┌────────────────────┐  │ │ [🔄 재분석 요청]  │   │
│  │ │ 쿠팡 대규모 개인정보│  │ │ [📥 엑셀 내보내기]│   │
│  │ │ 유출 사태로 입점    │  │ │                  │   │
│  │ │ 소상공인들이 매출   │  │ └──────────────────┘   │
│  │ │ 감소 피해 호소...   │  │                        │
│  │ └────────────────────┘  │                        │
│  │                          │                        │
│  │ 📋 판단 근거              │                        │
│  │ ┌────────────────────┐  │                        │
│  │ │ C1(상대방 책임 명확)│  │                        │
│  │ │ C2(자력 충분: 뉴욕 │  │                        │
│  │ │   증시 상장 대기업) │  │                        │
│  │ │ C3(집단적 피해)     │  │                        │
│  │ │ C6(공적 절차: 집단  │  │                        │
│  │ │   소송 예고)        │  │                        │
│  │ └────────────────────┘  │                        │
│  └──────────────────────────┘                        │
└──────────────────────────────────────────────────────┘
```

**레이아웃**: 2컬럼 (좌 기사+분석 / 우 상세카드 sticky)
- 왼쪽 (flex: 1): 기사 헤더 카드 + AI 분석 요약 카드
- 오른쪽 (380px): 가이드라인 6개 항목 카드 (sticky, 스크롤 따라감)

**판단 근거 배경색**:
- High: 연한 레드 배경 (rgba(225,29,72,0.04))
- Medium: 연한 앰버 배경 (rgba(245,158,11,0.04))
- Low: 연한 그레이 배경 (rgba(107,114,128,0.04))

#### ⚙️ 설정 (`/settings`)

```
┌──────────────────────────────────────────────────────┐
│  수집 키워드 관리                                      │
│                                                      │
│  [소송] [손해배상] [집단소송] [공동소송]                 │
│  [피해자] [피해보상] [피해구제]                          │
│  [+ 키워드 추가]                                      │
└──────────────────────────────────────────────────────┘
```

### 6.3 주요 컴포넌트 목록

| 컴포넌트 | 파일 | 사용 라이브러리 | 역할 |
|----------|------|----------------|------|
| `StatsCard` | components/StatsCard.tsx | - | 통계 숫자 표시 (아이콘 + 라벨 + 값) |
| `SuitabilityBadge` | components/SuitabilityBadge.tsx | - | High/Medium/Low 배지 |
| `StageBadge` | components/StageBadge.tsx | - | 진행 단계 배지 |
| `SuitabilityChart` | components/SuitabilityChart.tsx | Recharts | 적합도 분포 도넛 차트 |
| `CategoryChart` | components/CategoryChart.tsx | Recharts | 사건 분야별 가로 바차트 |
| `WeeklyTrendChart` | components/WeeklyTrendChart.tsx | Recharts | 주간 수집 추이 라인차트 |
| `AnalysisTable` | components/AnalysisTable.tsx | TanStack Table | 필터/정렬 가능한 테이블 |
| `FilterBar` | components/FilterBar.tsx | - | 필터 드롭다운 + 검색 입력 |
| `ExportButton` | components/ExportButton.tsx | - | 엑셀 다운로드 버튼 |
| `Pagination` | components/Pagination.tsx | - | 페이지네이션 |
| `TopNav` | components/TopNav.tsx | - | 상단 네비게이션 바 |
| `KeywordTag` | components/KeywordTag.tsx | - | 키워드 태그 (삭제 가능) |

### 6.4 프론트엔드 폴더 구조

```
frontend/
├── app/
│   ├── layout.tsx              # 공통 레이아웃 (TopNav 포함)
│   ├── page.tsx                # 메인 대시보드
│   ├── analyses/
│   │   ├── page.tsx            # 분석 목록
│   │   └── [id]/
│   │       └── page.tsx        # 분석 상세
│   └── settings/
│       └── page.tsx            # 키워드 설정
├── components/
│   ├── TopNav.tsx
│   ├── StatsCard.tsx
│   ├── SuitabilityBadge.tsx
│   ├── StageBadge.tsx
│   ├── SuitabilityChart.tsx
│   ├── CategoryChart.tsx
│   ├── WeeklyTrendChart.tsx
│   ├── AnalysisTable.tsx
│   ├── FilterBar.tsx
│   ├── ExportButton.tsx
│   ├── Pagination.tsx
│   └── KeywordTag.tsx
├── lib/
│   ├── api.ts                  # API 호출 함수 모음
│   └── types.ts                # TypeScript 타입 정의
├── styles/
│   └── globals.css             # Tailwind + 커스텀 스타일
├── package.json
├── tailwind.config.js
└── next.config.js
```

### 6.5 API 연동 패턴 (lib/api.ts)

```typescript
// 분석 목록 조회
async function getAnalyses(params: {
  suitability?: 'High' | 'Medium' | 'Low';
  case_category?: string;
  stage?: string;
  search?: string;
  ordering?: string;
  page?: number;
}) → Promise<PaginatedResponse<Analysis>>

// 분석 상세 조회
async function getAnalysis(id: number) → Promise<Analysis>

// 통계 데이터
async function getStats() → Promise<DashboardStats>

// 엑셀 다운로드
async function downloadExcel(params: FilterParams) → Blob

// 재분석 요청
async function reanalyze(articleId: number) → Promise<void>

// 키워드 목록
async function getKeywords() → Promise<Keyword[]>
```

### 6.6 TypeScript 타입 정의 (lib/types.ts)

```typescript
interface Analysis {
  id: number;
  article: {
    id: number;
    title: string;
    source: string;
    url: string;
    published_at: string;
  };
  suitability: 'High' | 'Medium' | 'Low';
  suitability_reason: string;
  case_category: string;
  defendant: string;
  damage_amount: string;
  victim_count: string;
  stage: string;
  stage_detail: string;
  summary: string;
  analyzed_at: string;
}

interface DashboardStats {
  today_collected: number;
  today_high: number;
  total_analyzed: number;
  monthly_cost: number;
  suitability_distribution: { name: string; value: number }[];
  category_distribution: { name: string; count: number }[];
  weekly_trend: { week: string; total: number; high: number; medium: number }[];
}
```

**완료 기준**:
- [ ] 메인 대시보드 4개 통계 카드 정상 표시
- [ ] 차트 3종 (파이, 바, 라인) 정상 렌더링
- [ ] 분석 목록 필터/정렬/검색 동작
- [ ] 분석 상세 가이드라인 6개 항목 + 판단 근거 표시
- [ ] 엑셀 다운로드 동작
- [ ] 행 클릭 → 상세 페이지 이동
- [ ] 재분석 요청 동작
- [ ] 키워드 설정 CRUD
- [ ] 반응형 디자인 (모바일 대응)

**사용자 테스트**:
```
🧪 프론트엔드 테스트:

http://localhost:3000/ 접속

1. 메인 대시보드
   ✅ 통계 카드 4개가 실제 데이터와 일치하나요?
   ✅ 적합도 파이차트가 정확한가요?
   ✅ 사건 분야 바차트가 정확한가요?
   ✅ 주간 추이 라인차트가 표시되나요?
   ✅ 최근 분석 테이블에서 행 클릭 시 상세로 이동하나요?

2. 분석 목록
   ✅ 적합도 필터 (High만 선택) 동작하나요?
   ✅ 분야 필터 동작하나요?
   ✅ 검색 (기사 제목, 상대방) 동작하나요?
   ✅ 엑셀 다운로드 버튼이 .xlsx 파일을 생성하나요?
   ✅ 페이지네이션 동작하나요?

3. 분석 상세
   ✅ 기사 정보 (제목, 언론사, 날짜) 표시되나요?
   ✅ AI 분석 요약이 보이나요?
   ✅ 판단 근거에 조건 번호(C1~C6)가 표시되나요?
   ✅ 오른쪽 상세 카드에 6개 항목이 모두 있나요?
   ✅ 재분석 요청 버튼이 동작하나요?

4. 설정
   ✅ 현재 키워드 목록이 표시되나요?
   ✅ 키워드 삭제가 되나요?
   ✅ 새 키워드 추가가 되나요?

승인 시 통합 테스트로 진행합니다.
```

---

## Phase 7: 통합 테스트 & 최적화

### 7.1 전체 파이프라인 테스트

**전체 흐름 확인**:
```
① 매 1시간 Celery Beat 트리거
② 크롤링 → 키워드 검색 → 새 기사 DB 저장
③ LLM 분석 자동 실행 → 결과 DB 저장
④ 대시보드에서 결과 확인
⑤ 엑셀로 다운로드
```

### 7.2 에러 핸들링

- 크롤링 실패 시: 로깅 + 다음 실행에서 재시도
- LLM API 실패 시: status='failed' + 60초 후 재시도 (최대 3번)
- JSON 파싱 실패 시: 기본값 보정 + 에러 로깅

### 7.3 성능 최적화

- select_related / prefetch_related로 N+1 문제 해결
- 페이지네이션 적용 (기본 20건)
- LLM 호출 전 키워드 필터링으로 불필요한 분석 방지

---

## Phase 8: 배포

### 8.1 배포 환경

- **추천**: AWS EC2 또는 Railway
- Docker Compose 기반 배포
- 환경 변수 프로덕션용으로 변경
- DEBUG=False, ALLOWED_HOSTS 설정

### 8.2 최종 체크리스트

- [ ] 전체 파이프라인 정상 동작
- [ ] 크롤링 스케줄러 정상 동작
- [ ] LLM 분석 정확도 검증 완료
- [ ] 대시보드 UI/UX 확인
- [ ] 엑셀 다운로드 확인
- [ ] 에러 핸들링 확인
- [ ] 배포 완료

---

## 진행 프로토콜

### 단계 시작 시
```
📍 현재 단계: [Phase X - 단계명]

목표: [목표 설명]

작업 내용:
1. [작업 1]
2. [작업 2]

시작하겠습니다.
```

### 단계 완료 시
```
✅ 완료: [Phase X - 단계명]

구현된 기능:
- [기능 1]
- [기능 2]

🧪 테스트 방법:
[구체적인 테스트 시나리오]

다음 단계로 진행할까요? (승인/수정/보류)
```

---

## 비용 예상 (LLM API)

| 항목 | 수치 |
|------|------|
| 하루 예상 수집 기사 수 | ~200건 (키워드 필터링 후) |
| 기사당 비용 (GPT-4o 기준) | ~₩100~300 |
| 하루 비용 | ~₩20,000~60,000 |
| PoC 기간 (1개월) 총 비용 | ~₩60만~180만원 |

> 절약 팁: 먼저 키워드 필터링으로 관련 없는 기사를 걸러내고, 남은 기사만 LLM에 보내면 비용을 크게 줄일 수 있습니다.

---

## 트러블슈팅

### 일반적인 문제

**1. Docker Compose 서비스 연결 실패**
- db 서비스가 먼저 시작되어야 함 → depends_on 확인
- PostgreSQL이 준비될 때까지 대기 로직 추가

**2. Celery 태스크 실행 안됨**
- Redis 연결 확인
- celery.py에서 app.autodiscover_tasks() 확인
- Celery Worker 로그 확인: docker-compose logs celery

**3. LLM API 호출 실패**
- API 키 확인 (.env)
- 요청 제한(Rate Limit) 확인 → 재시도 로직으로 해결
- 응답 형식 오류 → response_format=json_object 설정 확인

**4. 크롤링 기사 중복**
- Article.url에 unique=True 설정 확인
- IntegrityError 예외 처리 추가

**5. 프론트엔드 CORS 에러**
- django-cors-headers 설치 확인
- CORS_ALLOWED_ORIGINS 설정 확인

---

## 리소스

### 공식 문서
- Django: https://docs.djangoproject.com/
- DRF: https://www.django-rest-framework.org/
- Celery: https://docs.celeryq.dev/
- Next.js: https://nextjs.org/docs
- OpenAI API: https://platform.openai.com/docs/
- 네이버 검색 API: https://developers.naver.com/docs/serviceapi/search/news/news.md

### Notion 설계 문서
- 기술 스택 선정
- 시스템 아키텍처 상세 설계
- DB 모델 설계 (테이블 구조)
- 프롬프트 엔지니어링 상세 설계

---

이 Skill은 AI 기반 법률 뉴스 분석 시스템의 전 과정을 단계별로 안내합니다.
각 단계를 완료하고 사용자의 테스트와 승인을 받아 진행하면,
로앤굿의 요구사항을 충족하는 PoC/MVP를 1개월 안에 완성할 수 있습니다.
