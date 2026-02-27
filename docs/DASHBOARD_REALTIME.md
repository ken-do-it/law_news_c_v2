# 대시보드 실시간 갱신 + 자동 스케줄링 — 구현 문서

> 대시보드 통계 카드 개선, 30초 자동 새로고침, 서버 자동 수집·분석 스케줄링 기능 추가
> 최종 수정: 2026-02-27

---

## 왜 이 기능이 필요한가?

| 기존 문제 | 개선 내용 |
|----------|----------|
| 통계 카드에 "분석 대기" 건수가 없어 현재 처리 현황 파악 불가 | 5번째 카드로 "분석 대기" 추가 |
| 대시보드를 수동으로 새로고침해야 최신 데이터 확인 가능 | 30초마다 자동 갱신 |
| 수집·분석은 `just pipeline`을 직접 실행해야만 동작 | 서버 시작 시 자동 실행, 이후 1시간 간격 반복 |
| 다음 수집 시간을 알 수 없음 | 대시보드에 "다음 수집 예정: 오후 3:45" 표시 |

---

## 전체 흐름

```
┌──────────────────────────────────────────────────────────┐
│                  Django 서버 시작                          │
│                 (just dev / gunicorn)                     │
└────────────────────────┬─────────────────────────────────┘
                         │ 10초 후
                         ▼
┌──────────────────────────────────────────────────────────┐
│           APScheduler (백그라운드 스레드)                  │
│                                                          │
│  1회 실행 후 → 완료 시점 기준 +1시간 뒤 다음 실행 예약     │
│                                                          │
│  pipeline()                                              │
│   ├─ STEP 1: 뉴스 수집 (Naver API)                       │
│   └─ STEP 2: 대기 기사 AI 분석 (Gemini)                  │
└────────────────────────┬─────────────────────────────────┘
                         │ 완료 후 +60분
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   다음 실행 자동 예약                       │
│   next_run_at = 완료 시각 + CRAWL_INTERVAL_MINUTES        │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                  프론트엔드 (Dashboard.tsx)                │
│                                                          │
│  GET /api/analyses/stats/ ───────────────────────────    │
│  30초마다 자동 호출 (탭 숨김 시 중단)                      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 🕐 다음 수집 예정: 오후 3:45   마지막 수집: 오후 2:45 │  │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│  │오늘  │ │분석  │ │분석  │ │High  │ │Medium│          │
│  │수집  │ │대기  │ │완료  │ │적합  │ │적합  │          │
│  │395건 │ │12건  │ │2364  │ │54건  │ │20건  │          │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘          │
└──────────────────────────────────────────────────────────┘
```

---

## 변경된 파일 목록

```
law_news_c_v2/
├── backend/
│   ├── scheduler/                    ★ 신규 앱
│   │   ├── __init__.py
│   │   ├── apps.py                   ★ AppConfig — ready()에서 스케줄러 시작
│   │   └── scheduler.py              ★ APScheduler 로직 + 상태 관리
│   ├── analyses/
│   │   └── views.py                  ★ stats API에 pending_count + scheduler_state 추가
│   └── config/
│       └── settings.py               ★ INSTALLED_APPS에 "scheduler" 추가
├── frontend/src/
│   ├── lib/
│   │   └── types.ts                  ★ SchedulerState 인터페이스 + DashboardStats 필드 추가
│   └── pages/
│       └── Dashboard.tsx             ★ 자동 갱신 + 분석대기 카드 + SchedulerBanner
└── pyproject.toml                    ★ apscheduler 의존성 추가
```

---

## 상세 변경 내용

### 1. 통계 카드 변경 (`frontend/src/pages/Dashboard.tsx`)

카드 4개 → 5개로 확장, 그리드 `lg:grid-cols-4` → `lg:grid-cols-5`

```
변경 전                          변경 후
────────────────────────         ──────────────────────────────────
[오늘 수집] [분석 완료]           [오늘 수집] [분석 대기 ★] [분석 완료]
[High 적합] [Medium 적합]         [High 적합] [Medium 적합]
```

**"분석 대기" 카드 데이터:**
```python
# backend/analyses/views.py
pending_count = Article.objects.filter(
    status__in=["pending", "analyzing"]
).count()
```
- `pending` (수집됐지만 분석 전) + `analyzing` (분석 시작됐지만 미완료) 합산
- 파이프라인이 실행 중이면 건수가 줄어드는 것을 실시간으로 확인 가능

---

### 2. 자동 갱신 (30초 폴링)

```typescript
// frontend/src/pages/Dashboard.tsx
const POLL_INTERVAL_MS = 30_000; // 30초

const refresh = () => {
  getStats().then(setStats);
  getAnalyses({ ordering: '-analyzed_at' }).then(...);
};

useEffect(() => {
  refresh();

  const tick = () => {
    if (!document.hidden) refresh();  // 탭 숨김 시 건너뜀
  };
  const id = setInterval(tick, POLL_INTERVAL_MS);
  return () => clearInterval(id);
}, []);
```

**Page Visibility API 적용:**
- 다른 탭으로 이동하거나 창을 최소화하면 `document.hidden === true`
- 이 경우 폴링을 건너뜀 → 불필요한 서버 요청 방지
- 탭으로 돌아오면 다음 30초 주기에 자동 재개

---

### 3. APScheduler 자동 스케줄링

#### 신규 파일: `backend/scheduler/scheduler.py`

```
스케줄링 동작 순서
──────────────────────────────────────────────────────────
1. 서버 시작
       │
       ▼ 10초 대기 (Django 완전 초기화 후 실행)
2. 첫 파이프라인 실행
   └─ STEP 1: crawl_news_sync()
   └─ STEP 2: 대기 기사 순환 analyze_single_article()
       │
       ▼ 파이프라인 완료
3. 완료 시각 + 60분 → 다음 실행 예약 (DateTrigger)
       │
       ▼ 60분 후
4. 다음 파이프라인 실행 → 3번 반복
```

**핵심 설계 결정:**

| 항목 | 선택 | 이유 |
|------|------|------|
| 스케줄러 | APScheduler | Redis 불필요, 코드 내 완결 |
| 실행 방식 | BackgroundScheduler (스레드) | Django WSGI 스레드 블로킹 없음 |
| 간격 기준 | **파이프라인 완료 시점** + 60분 | 사용자 요구사항 ("이전 분석 완료 후 1시간") |
| 중복 실행 방지 | `_lock` + `is_running` 플래그 | 이전 실행 중이면 새 실행 건너뜀 |
| 첫 실행 지연 | 10초 | Django 앱/DB 초기화 완료 보장 |

#### Dev 서버 이중 실행 방지 (`backend/scheduler/apps.py`)

```python
def ready(self):
    # Django dev 서버는 auto-reloader 때문에 프로세스 2개 생성
    # 부모 프로세스(파일 감시): RUN_MAIN 미설정 → 스케줄러 시작 안 함
    # 자식 프로세스(요청 처리): RUN_MAIN='true' → 스케줄러 시작
    # 프로덕션(gunicorn): RUN_MAIN 미설정이지만 runserver 없음 → 시작
    is_dev_parent = (
        os.environ.get("RUN_MAIN") is None
        and any("runserver" in a for a in sys.argv)
    )
    if is_dev_parent:
        return
    from .scheduler import start_scheduler
    start_scheduler()
```

---

### 4. 다음 수집 시간 배너 (`SchedulerBanner` 컴포넌트)

```
수집 진행 중일 때:
┌────────────────────────────────────────────────────────┐
│  ⟳  뉴스 수집 및 AI 분석이 진행 중입니다...              │
└────────────────────────────────────────────────────────┘

대기 중일 때:
┌────────────────────────────────────────────────────────┐
│  🕐  다음 수집 예정: 오후 3:45        마지막 수집: 오후 2:45│
└────────────────────────────────────────────────────────┘
```

**API 응답 구조 (`GET /api/analyses/stats/`):**
```json
{
  "today_collected": 395,
  "pending_count": 12,
  "total_analyzed": 2364,
  "today_high": 54,
  "today_medium": 20,
  "scheduler_state": {
    "is_running": false,
    "last_run_at": "2026-02-26T06:45:00+00:00",
    "next_run_at": "2026-02-26T07:45:00+00:00"
  },
  ...
}
```

---

## 환경변수 설정

`CRAWL_INTERVAL_MINUTES`로 수집 간격 조정 가능:

```bash
# .env
CRAWL_INTERVAL_MINUTES=60   # 기본값: 60분
```

```
30분 간격 원하면 → CRAWL_INTERVAL_MINUTES=30
2시간 간격 원하면 → CRAWL_INTERVAL_MINUTES=120
```

---

## 의존성

```toml
# pyproject.toml에 추가됨
"apscheduler>=3.11.2"
```

설치 명령:
```bash
uv sync  # 또는
uv add apscheduler
```

---

## 주의사항

### 서버 재시작 시 상태 초기화
- 스케줄러 상태(`last_run_at`, `next_run_at`)는 in-memory 저장
- 서버 재시작 시 초기화됨 → 재시작 후 10초 뒤 다시 첫 실행

### Celery와의 관계
- `just pipeline` 또는 APScheduler 스케줄러 중 하나만 실행되어도 무방
- 동시에 실행되면 중복 분석 가능성 있음 (같은 기사에 `update_or_create` 사용하므로 데이터 손상은 없음)
- Redis가 있다면 Celery Beat가 더 강건한 선택

### 자동 실행 비활성화 방법
`.env` 또는 서버 환경에서:
```bash
CRAWL_INTERVAL_MINUTES=99999  # 사실상 비활성화
```
또는 `scheduler/apps.py`의 `ready()`에서 `start_scheduler()` 호출 주석 처리.
