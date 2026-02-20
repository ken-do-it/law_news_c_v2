# LawNGood AI 법률 뉴스 분석 시스템

---

## 초보자를 위한 완전 실행 가이드 (A-Z)

> 처음 실행하는 분을 위해 순서대로 따라하면 됩니다.
> 각 단계에서 오류가 나면 하단의 [트러블슈팅](#beginners-troubleshooting) 섹션을 확인하세요.

---

### 이 시스템이 하는 일 (한 줄 요약)

```
네이버 뉴스 자동 수집 → Gemini AI가 소송금융 적합도 판정 → 대시보드에서 확인
```

필요한 API 키는 딱 **2가지**입니다:
- **네이버 검색 API** — 뉴스 기사 수집
- **Google Gemini API** — AI 분석

---

### Step 1. 필수 프로그램 설치 확인

아래 명령어를 터미널(명령 프롬프트 또는 PowerShell)에서 실행해 버전을 확인합니다.

#### Python 확인 (3.12 이상 필요)

```bash
python --version
```

출력 예시: `Python 3.12.3`

> **설치가 안 되어 있다면**: https://www.python.org/downloads/ 에서 다운로드
>
> **Windows 설치 시 중요**: 설치 화면 맨 아래 `Add Python to PATH` 체크박스를 **반드시 체크**하고 설치하세요. 체크하지 않으면 `python` 명령어가 인식되지 않습니다.

#### Node.js 확인 (18 이상 필요)

```bash
node --version
npm --version
```

출력 예시: `v20.11.0` / `10.2.4`

> **설치가 안 되어 있다면**: https://nodejs.org/ 에서 LTS 버전 다운로드 후 설치

---

### Step 2. API 키 발급

#### 2-A. 네이버 검색 API

1. https://developers.naver.com/apps/ 접속 → 로그인
2. **[Application 등록]** 클릭
3. 애플리케이션 이름 입력 (예: `lawngood-test`)
4. **사용 API** 에서 **검색** 선택
5. **등록하기** → `Client ID`와 `Client Secret` 복사해 두기

#### 2-B. Google Gemini API

1. https://aistudio.google.com/apikey 접속 → Google 계정 로그인
2. **[Create API key]** 클릭
3. 생성된 API 키 복사해 두기

---

### Step 3. 프로젝트 폴더로 이동

터미널에서 프로젝트 루트 폴더로 이동합니다.

```bash
# 예시 (본인 경로에 맞게 변경)
cd C:\Users\사용자이름\Desktop\law_news_c_v2
```

이 폴더 안에 `backend/`, `frontend/`, `.env.example` 등이 있으면 정상입니다.

---

### Step 4. 환경변수 파일(.env) 설정

```bash
# 템플릿 복사 (Windows)
copy .env.example .env
```

```bash
# 템플릿 복사 (macOS/Linux)
cp .env.example .env
```

`.env` 파일을 메모장이나 VSCode로 열어서 아래 항목을 실제 값으로 교체합니다:

```env
# ---- Django ----
DJANGO_SECRET_KEY=아무-랜덤-문자열-50자-이상-입력  # 예: my-super-secret-key-abc123xyz

# ---- 네이버 API ----
NAVER_CLIENT_ID=Step2에서_복사한_Client_ID
NAVER_CLIENT_SECRET=Step2에서_복사한_Client_Secret

# ---- Gemini API ----
GEMINI_API_KEY=Step2에서_복사한_Gemini_API_키

# ---- 자동 파이프라인 설정 ----
ENABLE_PIPELINE_ON_RUNSERVER=True   # 서버 시작 시 자동으로 크롤링+분석 실행
PIPELINE_INTERVAL_MINUTES=60        # 60분마다 반복
```

> **나머지 항목은 건드리지 않아도 됩니다.** 기본값으로 동작합니다.

---

### Step 5. Python 가상환경 만들기

가상환경은 이 프로젝트의 Python 패키지를 다른 프로젝트와 분리해 관리하는 공간입니다.

```bash
# 가상환경 생성
python -m venv law_claude_venv2(가상환경 이름 변경가능)
```

```bash
# 가상환경 활성화 (Windows CMD / PowerShell)
law_claude_venv2\Scripts\activate
```

```bash
# 가상환경 활성화 (macOS / Linux)
source law_claude_venv2/bin/activate
```

활성화되면 터미널 앞에 `(law_claude_venv2)` 가 붙습니다.

```
(law_claude_venv2) C:\Users\...>
```

> **앞으로 모든 Python 명령어는 가상환경이 활성화된 상태에서 실행**해야 합니다.

---

### Step 6. Python 패키지 설치

```bash
pip install -r backend/requirements.txt
```

설치에 수 분이 걸릴 수 있습니다. 마지막에 오류 없이 완료되면 다음 단계로 이동합니다.

---

### Step 7. 데이터베이스 초기화

```bash
# 테이블 생성 (데이터베이스 구조 적용)
python backend/manage.py migrate
```

```bash
# 초기 데이터 입력 (언론사 80개 + 검색 키워드 7개)
python backend/manage.py seed_initial_data
```

---

### Step 8. (선택) 관리자 계정 생성

Django 관리자 페이지(http://localhost:8000/admin/)를 사용하려면 계정이 필요합니다.

```bash
python backend/manage.py createsuperuser
```

```
Username: admin
Email address: (비워도 됨, 엔터)
Password: 원하는비밀번호
Password (again): 동일하게입력
```

---

### Step 9. 프론트엔드 패키지 설치

**새 터미널 창**을 열거나, 기존 터미널에서 아래 명령어를 실행합니다.

```bash
cd frontend
npm install
cd ..
```

설치에 1~3분 정도 걸립니다.

---

### Step 10. 서버 실행 (터미널 2개 필요)

#### 터미널 1: 백엔드 서버

가상환경이 활성화된 터미널에서 실행합니다.

```bash
python backend/manage.py runserver
```

아래와 같이 출력되면 정상:

```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
Django version 5.x.x, using settings 'config.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

> `.env`에서 `ENABLE_PIPELINE_ON_RUNSERVER=True`로 설정했다면, 서버 시작 직후 자동으로 뉴스 크롤링과 AI 분석이 백그라운드에서 시작됩니다. 터미널에 로그가 출력됩니다.

#### 터미널 2: 프론트엔드 서버

새 터미널을 열고 실행합니다.

```bash
cd frontend
npm run dev
```

아래와 같이 출력되면 정상:

```
  VITE v7.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

---

### Step 11. 브라우저로 접속

| 서비스 | URL | 설명 |
|--------|-----|------|
| **메인 대시보드** | http://localhost:5173 | 차트·통계 메인 화면 |
| API 문서 (Swagger) | http://localhost:8000/api/docs/ | REST API 명세 |
| Django 관리자 | http://localhost:8000/admin/ | 데이터 직접 조회/수정 |

---

### Step 12. 첫 번째 뉴스 수집 및 분석 (수동 실행)옵션

자동 파이프라인이 활성화되어 있어도, 즉시 테스트하고 싶다면 수동으로 실행할 수 있습니다.

```bash
# 가상환경 활성화 상태에서 실행

# 1단계: 뉴스 크롤링 (7개 키워드로 최대 700건 수집)
python backend/manage.py shell -c "
from articles.tasks import crawl_news
crawl_news()
"
```

```bash
# 2단계: AI 분석 (수집된 기사를 Gemini가 판정)
python backend/manage.py shell -c "
from analyses.tasks import analyze_pending_articles
analyze_pending_articles()
"
```

> 기사당 약 3~5초 소요됩니다. 600건 기준 약 30~50분 걸릴 수 있습니다.

분석이 끝나면 http://localhost:5173 에서 결과를 확인할 수 있습니다.

---

### 전체 단계 요약

```
1. python --version       → Python 3.12+ 확인
2. node --version         → Node.js 18+ 확인
3. 네이버 API 키 발급
4. Gemini API 키 발급
5. copy .env.example .env → API 키 입력
6. python -m venv law_claude_venv2
7. law_claude_venv2\Scripts\activate
8. pip install -r backend/requirements.txt
9. python backend/manage.py migrate
10. python backend/manage.py seed_initial_data
11. cd frontend && npm install && cd ..
12. [터미널1] python backend/manage.py runserver
13. [터미널2] cd frontend && npm run dev
14. 브라우저에서 http://localhost:5173 열기
```

---

### 초보자 트러블슈팅 {#beginners-troubleshooting}

#### `python`을 찾을 수 없습니다

```
'python'은(는) 내부 또는 외부 명령, 실행할 수 있는 프로그램, 또는
배치 파일이 아닙니다.
```

**해결**: Python 설치 시 `Add Python to PATH`를 체크하지 않은 경우입니다.
Python을 제거한 후 재설치하면서 해당 옵션을 체크하세요.
또는 `py --version`으로 시도해보세요 (Windows Python Launcher).

---

#### 가상환경 활성화 오류 (PowerShell)

```
이 시스템에서 스크립트를 실행할 수 없으므로 ...Scripts\Activate.ps1 파일을 로드할 수 없습니다.
```

**해결**: PowerShell 실행 정책 문제입니다. PowerShell을 **관리자 권한**으로 열고:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

이후 다시 가상환경 활성화를 시도하세요.

---

#### `pip install` 중 한글 인코딩 오류

```
UnicodeDecodeError: 'cp949' codec can't decode byte ...
```

**해결**:

```bash
# Windows CMD
set PYTHONIOENCODING=utf-8
pip install -r backend/requirements.txt

# PowerShell
$env:PYTHONIOENCODING="utf-8"
pip install -r backend/requirements.txt
```

---

#### `migrate` 실행 시 오류 — `.env` 파일을 못 찾음

```
KeyError: 'SECRET_KEY'  또는  FileNotFoundError: .env
```

**해결**: `.env` 파일이 프로젝트 루트(backend/ 폴더와 같은 위치)에 있는지 확인하세요.

```
law_news_c_v2/        ← 여기에
├── .env              ← 이 파일
├── backend/
└── frontend/
```

---

#### 서버가 이미 실행 중 / 포트 충돌

```
Error: That port is already in use.
```

**해결 (백엔드 포트 8000 충돌)**:

```bash
# 다른 포트로 실행
python backend/manage.py runserver 8001
```

**해결 (프론트 포트 5173 충돌)**:
Vite는 충돌 시 자동으로 5174, 5175 등을 사용합니다. 터미널에 표시된 URL을 사용하세요.

---

#### Gemini API 오류

```
google.api_core.exceptions.InvalidArgument: 400 API key not valid.
```

**해결**: `.env`의 `GEMINI_API_KEY` 값이 올바른지 확인하세요. 키 앞뒤에 공백이나 따옴표가 없어야 합니다.

```env
# 올바른 예시
GEMINI_API_KEY=AIzaSyAbcdef123456...

# 잘못된 예시 (따옴표 금지)
GEMINI_API_KEY="AIzaSyAbcdef123456..."
```

---

#### 네이버 API 오류

```
{"errorCode": "024", "errorMessage": "Not Exist Client ID"}
```

**해결**: `.env`의 `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET`이 올바른지 확인하세요.
네이버 개발자센터에서 앱의 **사용 API**에 **검색**이 포함되어 있는지도 확인하세요.

---

#### `npm install` 후 `npm run dev` 오류

```
Error: Cannot find module ...
```

**해결**: `frontend/` 폴더 안에서 실행했는지 확인하세요.

```bash
cd frontend
npm install    # 먼저 설치
npm run dev    # 그 다음 실행
```

---

#### 브라우저에서 데이터가 안 보임 (빈 대시보드)

뉴스 수집과 AI 분석이 아직 실행되지 않았거나, 진행 중인 상태입니다.

1. 백엔드 터미널에서 로그 확인 (크롤링/분석 진행 중인지)
2. 수동 실행으로 테스트:

```bash
python backend/manage.py shell -c "
from articles.tasks import crawl_news
result = crawl_news()
print('수집 완료:', result)
"
```

---

---

## 기존 상세 문서

> 이하는 아키텍처·프롬프트·API 명세·운영 가이드 등 기술 상세 문서입니다.

---

> **소송금융(Litigation Finance) 투자 적합 사건을 자동으로 발굴하는 AI 시스템**
>
> 네이버 뉴스를 실시간 수집하고, Gemini 2.5 Flash가 소송금융 가이드라인(C1~C6)에 따라
> High / Medium / Low 적합도를 자동 판정합니다.

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [전체 아키텍처](#2-전체-아키텍처)
3. [기술 스택](#3-기술-스택)
4. [프로젝트 폴더 구조](#4-프로젝트-폴더-구조)
5. [환경 준비 (Python, Node.js 설치)](#5-환경-준비)
6. [프로젝트 설치 및 실행](#6-프로젝트-설치-및-실행)
7. [데이터 파이프라인 (크롤링 → 분석)](#7-데이터-파이프라인)
8. [AI 분석 프롬프트 상세](#8-ai-분석-프롬프트-상세)
9. [데이터베이스 모델(ERD)](#9-데이터베이스-모델)
10. [REST API 명세](#10-rest-api-명세)
11. [프론트엔드 페이지 구성](#11-프론트엔드-페이지-구성)
12. [주요 설정값](#12-주요-설정값)
13. [운영 가이드](#13-운영-가이드)
14. [트러블슈팅](#14-트러블슈팅)

---

## 1. 시스템 개요

### 이 시스템이 하는 일

```
한 줄 요약: 법률 뉴스를 자동 수집 → AI가 소송금융 적합도 판정 → 대시보드에서 확인
```

**로앤굿(LawNGood)** 은 소송금융 전문 법무법인입니다.
소송금융이란, 승소 가능성이 높은 소송에 자금을 투자하고 승소 시 수익을 얻는 비즈니스입니다.

이 시스템은 다음을 자동화합니다:

| 단계 | 사람이 하던 일 | 시스템이 대신 하는 일 |
|------|-------------|-------------------|
| 1단계 | 매일 뉴스를 검색하여 법률 관련 기사를 찾음 | 네이버 뉴스 API로 7개 키워드 자동 크롤링 |
| 2단계 | 기사를 읽고 투자 적합 여부를 판단 | Gemini 2.5 Flash가 6가지 기준(C1~C6)으로 자동 판정 |
| 3단계 | 유사한 사건끼리 분류·정리 | AI가 자동으로 사건 그룹(Case ID) 생성 |
| 4단계 | 엑셀로 보고서 작성 | 대시보드 + 엑셀 자동 내보내기 |

---

## 2. 전체 아키텍처

### 시스템 흐름도

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 (브라우저)                              │
│                     http://localhost:5173                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP 요청
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    프론트엔드 (Vite + React)                         │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌────────┐         │
│  │ 대시보드  │  │ 분석목록  │  │  분석 상세    │  │  설정   │         │
│  │ (차트)   │  │ (테이블)  │  │  (AI 요약)   │  │(키워드) │         │
│  └──────────┘  └──────────┘  └──────────────┘  └────────┘         │
│                                                                     │
│  Vite 개발서버가 /api/* 요청을 백엔드로 프록시 (proxy)                │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ /api/*
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   백엔드 (Django REST Framework)                     │
│                     http://localhost:8000                            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐                 │
│  │ articles 앱 │  │ analyses 앱  │  │ config     │                 │
│  │ (크롤링)    │  │ (AI 분석)    │  │ (설정)     │                 │
│  └──────┬──────┘  └──────┬───────┘  └────────────┘                 │
│         │                │                                          │
│         ▼                ▼                                          │
│  ┌─────────────────────────────┐                                    │
│  │       SQLite 데이터베이스    │                                    │
│  │       (backend/db.sqlite3)  │                                    │
│  └─────────────────────────────┘                                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│   네이버 뉴스 API     │  │  Google Gemini 2.5   │
│   (기사 수집)         │  │  Flash (AI 분석)      │
│                      │  │                      │
│  Client-Id/Secret    │  │  GEMINI_API_KEY       │
└──────────────────────┘  └──────────────────────┘
```

### 데이터 흐름 상세

```
 ① 크롤링                  ② AI 분석                    ③ 결과 제공
 ──────────                ──────────                   ──────────

 네이버 뉴스 API            Gemini 2.5 Flash              REST API
      │                        │                            │
      ▼                        ▼                            ▼
┌───────────┐  pending   ┌───────────┐  analyzed    ┌──────────────┐
│  키워드별   │ ────────▶ │  기사별     │ ──────────▶ │  대시보드     │
│  100건 검색 │  (저장)   │  LLM 호출   │  (저장)     │  분석 목록    │
│  중복 제거  │           │  JSON 파싱  │             │  엑셀 내보내기 │
│  본문 추출  │           │  사건 그룹핑 │             │              │
└───────────┘            └───────────┘              └──────────────┘
```

---

## 3. 기술 스택

### 백엔드

| 기술 | 버전 | 역할 |
|------|------|------|
| Python | 3.12+ | 메인 프로그래밍 언어 |
| Django | 5.x | 웹 프레임워크 |
| Django REST Framework | 3.14+ | REST API 구축 |
| django-filter | 23.5+ | API 필터링 |
| drf-spectacular | 0.27+ | Swagger API 문서 자동 생성 |
| google-generativeai | 0.8+ | Gemini 2.5 Flash LLM |
| APScheduler | 3.x | 자동 파이프라인 스케줄러 |
| requests | 2.31+ | 네이버 API HTTP 호출 |
| BeautifulSoup4 | 4.12+ | HTML 파싱 (기사 본문 추출) |
| openpyxl | 3.1+ | 엑셀 파일 생성 |
| SQLite | 내장 | 개발용 데이터베이스 |

### 프론트엔드

| 기술 | 버전 | 역할 |
|------|------|------|
| React | 19.x | UI 라이브러리 |
| TypeScript | 5.9+ | 타입 안정성 |
| Vite | 7.x | 번들러 + 개발 서버 |
| Tailwind CSS | 4.x | 유틸리티 CSS |
| Recharts | 3.x | 차트 (파이, 바, 라인) |
| Axios | 1.x | HTTP 클라이언트 |
| React Router | 7.x | 클라이언트 라우팅 |

---

## 4. 프로젝트 폴더 구조

```
law_news_c_v2/                    ← 프로젝트 루트
│
├── .env                          ← 환경변수 (API 키) — git 미추적
├── .env.example                  ← 환경변수 템플릿
├── .gitignore                    ← git 제외 파일 목록
├── README.md                     ← 이 문서
│
├── backend/                      ← Django 백엔드
│   ├── manage.py                 ← Django CLI 진입점
│   ├── requirements.txt          ← Python 패키지 목록
│   ├── db.sqlite3                ← SQLite DB — git 미추적
│   │
│   ├── config/                   ← Django 프로젝트 설정
│   │   ├── settings.py           ← 전체 설정 (DB, API키, CORS 등)
│   │   ├── urls.py               ← URL 라우팅 (api/, admin/, docs/)
│   │   └── __init__.py
│   │
│   ├── articles/                 ← 뉴스 기사 앱 (수집 담당)
│   │   ├── models.py             ← 모델: MediaSource, Keyword, Article
│   │   ├── crawlers.py           ← 네이버 뉴스 API 크롤러
│   │   ├── tasks.py              ← 크롤링 태스크
│   │   ├── serializers.py        ← DRF 시리얼라이저
│   │   ├── views.py              ← API 뷰셋
│   │   ├── urls.py               ← 라우터 등록
│   │   ├── admin.py              ← Django 관리자 페이지
│   │   └── management/commands/
│   │       └── seed_initial_data.py  ← 초기 데이터 (80개 언론사 + 7개 키워드)
│   │
│   └── analyses/                 ← AI 분석 앱
│       ├── models.py             ← 모델: CaseGroup, Analysis
│       ├── prompts.py            ← LLM 프롬프트 + Few-shot 예시
│       ├── validators.py         ← LLM 응답 JSON 검증
│       ├── tasks.py              ← 분석 태스크 (Gemini 2.5 Flash)
│       ├── export.py             ← 엑셀 내보내기
│       ├── serializers.py        ← DRF 시리얼라이저
│       ├── views.py              ← API 뷰셋 (통계, 필터, 엑셀)
│       ├── urls.py               ← 라우터 등록
│       └── admin.py              ← Django 관리자 페이지
│
├── frontend/                     ← React 프론트엔드
│   ├── package.json              ← Node.js 패키지 목록
│   ├── vite.config.ts            ← Vite 설정 (프록시 포함)
│   ├── tsconfig.json             ← TypeScript 설정
│   ├── index.html                ← HTML 진입점
│   │
│   └── src/
│       ├── main.tsx              ← React 앱 마운트
│       ├── App.tsx               ← 라우팅 (4개 페이지)
│       ├── index.css             ← Tailwind + 커스텀 테마 색상
│       │
│       ├── lib/
│       │   ├── types.ts          ← TypeScript 인터페이스 정의
│       │   └── api.ts            ← Axios API 클라이언트
│       │
│       ├── components/
│       │   ├── TopNav.tsx        ← 상단 내비게이션 바
│       │   ├── StatsCard.tsx     ← 통계 카드 컴포넌트
│       │   ├── SuitabilityBadge.tsx  ← 적합도 뱃지 (High/Medium/Low)
│       │   └── StageBadge.tsx    ← 소송 단계 뱃지
│       │
│       └── pages/
│           ├── Dashboard.tsx     ← 대시보드 (차트 + 통계)
│           ├── AnalysisList.tsx  ← 분석 목록 (필터 + 테이블)
│           ├── AnalysisDetail.tsx ← 분석 상세 (AI 요약 + 가이드라인)
│           └── Settings.tsx      ← 설정 (키워드 관리)
│
└── law_claude_venv2/             ← Python 가상환경 — git 미추적
```

---

## 5. 환경 준비

### 5-1. Python 설치

**Python 3.12 이상**이 필요합니다.

```bash
# 버전 확인
python --version
# 출력: Python 3.12.x
```

> 아직 설치하지 않았다면: https://www.python.org/downloads/
>
> **Windows 설치 시 주의**: 설치 화면에서 `Add Python to PATH` 체크박스를 반드시 체크하세요.

### 5-2. Node.js 설치

**Node.js 18 이상**이 필요합니다.

```bash
# 버전 확인
node --version
# 출력: v18.x.x 이상

npm --version
# 출력: 9.x.x 이상
```

> 아직 설치하지 않았다면: https://nodejs.org/

### 5-3. API 키 준비

시스템이 작동하려면 **2개의 API 키**가 필요합니다:

| API | 용도 | 발급처 |
|-----|------|--------|
| 네이버 검색 API | 뉴스 기사 수집 | [네이버 개발자센터](https://developers.naver.com/apps/) |
| Gemini API | AI 분석 (Gemini 2.5 Flash) | [Google AI Studio](https://aistudio.google.com/apikey) |

---

## 6. 프로젝트 설치 및 실행

### 6-1. 저장소 클론

```bash
git clone <저장소 URL>
cd law_news_c_v2
```

### 6-2. 환경변수 설정

```bash
# 템플릿 복사
cp .env.example .env

# .env 파일을 열어서 실제 API 키 입력
# 아래 항목들을 본인의 키로 변경:
#   NAVER_CLIENT_ID=발급받은_클라이언트_ID
#   NAVER_CLIENT_SECRET=발급받은_시크릿
#   GEMINI_API_KEY=발급받은_Gemini_키
```

### 6-3. 백엔드 설치

```bash
# 1) 가상환경 생성
python -m venv law_claude_venv2

# 2) 가상환경 활성화
# Windows:
law_claude_venv2\Scripts\activate
# macOS/Linux:
source law_claude_venv2/bin/activate

# 3) 패키지 설치
pip install -r backend/requirements.txt

# 4) 데이터베이스 초기화 (테이블 생성)
python backend/manage.py migrate

# 5) 초기 데이터 입력 (80개 언론사 + 7개 키워드)
python backend/manage.py seed_initial_data

# 6) 관리자 계정 생성 (선택)
python backend/manage.py createsuperuser
```

### 6-4. 프론트엔드 설치

```bash
cd frontend
npm install
cd ..
```

### 6-5. 서버 실행

**터미널 2개**가 필요합니다:

```bash
# 터미널 1: 백엔드 서버
python backend/manage.py runserver

# 터미널 2: 프론트엔드 개발 서버
cd frontend && npm run dev
```

### 6-6. 접속 확인

| 서비스 | URL | 설명 |
|--------|-----|------|
| 프론트엔드 | http://localhost:5173 | 대시보드 메인 화면 |
| 백엔드 API | http://localhost:8000/api/ | REST API 루트 |
| Swagger 문서 | http://localhost:8000/api/docs/ | API 자동 문서 |
| Django 관리자 | http://localhost:8000/admin/ | DB 관리 페이지 |

### 6-7. 크롤링 + AI 분석 실행

```bash
# 가상환경 활성화 상태에서 실행

# 1) 뉴스 크롤링 (7개 키워드 x 100건씩 = 최대 700건, 중복 제거)
python backend/manage.py shell -c "
from articles.tasks import crawl_news
crawl_news()
"

# 2) AI 분석 (수집된 모든 기사에 대해 Gemini 분석 실행)
python backend/manage.py shell -c "
from analyses.tasks import analyze_pending_articles
analyze_pending_articles()
"
```

> **참고**: AI 분석은 기사당 약 3~5초 소요됩니다.

---

## 7. 데이터 파이프라인

### 전체 파이프라인 흐름도

```
┌──────────────────────────────────────────────────────────────────┐
│                        STEP 1: 크롤링                            │
│                                                                  │
│  키워드 7개 순회:                                                 │
│  소송, 손해배상, 집단소송, 공동소송, 피해자, 피해보상, 피해구제       │
│                                                                  │
│  각 키워드마다:                                                    │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐      │
│  │ 네이버 API    │ ──▶ │ URL 중복검사  │ ──▶ │ 본문 스크래핑 │      │
│  │ 100건 검색    │     │ (DB 대조)    │     │ (HTML→텍스트) │      │
│  └──────────────┘     └──────────────┘     └──────┬───────┘      │
│                                                    │              │
│                                      ┌─────────────▼────────┐    │
│                                      │ Article 테이블 저장    │    │
│                                      │ status = "pending"   │    │
│                                      └──────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                       STEP 2: AI 분석                            │
│                                                                  │
│  pending 상태의 기사를 하나씩 처리:                                 │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐      │
│  │ 프롬프트 구성  │ ──▶ │ Gemini 호출   │ ──▶ │ JSON 응답    │      │
│  │ (시스템 프롬프 │     │ 2.5 Flash    │     │  파싱/검증   │      │
│  │  트 + Few-shot│     │              │     │              │      │
│  │  + 기사 본문) │     │              │     │              │      │
│  └──────────────┘     └──────────────┘     └──────┬───────┘      │
│                                                    │              │
│                    ┌───────────────────────────────┘              │
│                    ▼                                              │
│  ┌──────────────────────────────────────────────────────┐        │
│  │ Analysis 테이블 저장                                   │        │
│  │ - suitability: High / Medium / Low                   │        │
│  │ - case_category: 개인정보, 형사, 특허, 금융 등          │        │
│  │ - defendant: 상대방 (기업명/기관명)                     │        │
│  │ - case_name → CaseGroup 자동 생성/매칭                 │        │
│  │ - Article.status → "analyzed"                        │        │
│  └──────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     STEP 3: 결과 활용                             │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐    │
│  │ 대시보드  │  │ 분석 목록 │  │  상세 보기    │  │ 엑셀     │    │
│  │ 통계/차트 │  │ 필터/검색 │  │  AI 분석 보기 │  │ 다운로드  │    │
│  └──────────┘  └──────────┘  └──────────────┘  └──────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### 크롤링 상세 프로세스

```
네이버 뉴스 검색 API 호출
          │
          ▼
    검색 결과 (JSON)
    ├── title (HTML 태그 포함)
    ├── link (네이버 뉴스 URL)
    ├── originallink (원본 기사 URL)
    ├── description (요약)
    └── pubDate (발행일)
          │
          ▼
    ┌─────────────────────────────────┐
    │ URL 중복 체크                    │
    │ DB에 이미 같은 URL이 있으면 SKIP  │
    └──────────────┬──────────────────┘
                   │ 새 기사만 진행
                   ▼
    ┌─────────────────────────────────┐
    │ 언론사 식별                      │
    │ 1순위: URL 도메인 매핑 (60+개)    │
    │ 2순위: 네이버 페이지 스크래핑      │
    └──────────────┬──────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────┐
    │ 기사 본문 추출                   │
    │ 네이버 뉴스 페이지의 #dic_area   │
    │ 에서 HTML → 텍스트 변환          │
    └──────────────┬──────────────────┘
                   │
                   ▼
    Article 테이블에 저장 (status="pending")
```

### 언론사 매핑 방식

네이버 뉴스 API에는 언론사 정보가 포함되지 않습니다.
그래서 2단계 방식으로 언론사를 식별합니다:

```
1단계: URL 도메인 매핑 (빠르고 정확)
┌──────────────────────────────────────────┐
│ www.chosun.com    → 조선일보              │
│ www.mk.co.kr      → 매일경제              │
│ news.kbs.co.kr    → KBS                  │
│ ... (60개 이상 매핑)                      │
└──────────────────────────────────────────┘

2단계: 네이버 뉴스 페이지 스크래핑 (1단계 실패 시)
┌──────────────────────────────────────────┐
│ 네이버 뉴스 페이지에서                     │
│ 언론사 로고의 alt 텍스트 추출              │
└──────────────────────────────────────────┘
```

---

## 8. AI 분석 프롬프트 상세

### LLM 호출 구조

```
┌────────────────────────────────────────────────────────────┐
│                Gemini 2.5 Flash 메시지 구조                  │
│                                                            │
│  1. [system] 시스템 프롬프트                                │
│     - 역할: 소송금융 투자 심사역                             │
│     - 판단 기준 C1~C6, X1                                  │
│     - JSON 응답 형식 지정                                   │
│                                                            │
│  2. [user] Few-shot 예시 #1 (기사)                          │
│  3. [assistant] Few-shot 예시 #1 (분석 결과)                 │
│  4. [user] Few-shot 예시 #2 (기사)                          │
│  5. [assistant] Few-shot 예시 #2 (분석 결과)                 │
│  6. [user] Few-shot 예시 #3 (기사)                          │
│  7. [assistant] Few-shot 예시 #3 (분석 결과)                 │
│                                                            │
│  8. [user] 실제 분석 대상 기사 (본문 3000자 제한)             │
│                                                            │
│  설정: temperature=0.1, JSON 응답 강제                      │
└────────────────────────────────────────────────────────────┘
```

### 소송금융 적합도 판단 기준

```
┌─────────────────────────────────────────────────────────────┐
│                    적합 조건 (C1 ~ C6)                       │
├─────┬───────────────────────────────────────────────────────┤
│ C1  │ 상대방의 책임이 명확함 (법적 의무 위반, 과실 등)         │
│ C2  │ 상대방의 자력이 충분함 (대기업, 상장사, 정부기관 등)     │
│ C3  │ 집단적 피해가 존재함 (피해자 수십 명 이상)              │
│ C4  │ 피해 규모가 큼 (수억 원 이상 또는 피해자 수만 명 이상)   │
│ C5  │ 증거가 있거나 확보 가능함                              │
│ C6  │ 공적 절차가 진행 중 (수사, 감사, 행정조치 등)           │
├─────┼───────────────────────────────────────────────────────┤
│     │                 부적합 조건 (X1)                       │
├─────┼───────────────────────────────────────────────────────┤
│ X1  │ 이미 종결된 사건 (판결 확정, 합의 완료 등)              │
└─────┴───────────────────────────────────────────────────────┘
```

### 등급 판정 로직

```
                    C1~C6 충족 개수
                         │
              ┌──────────┼──────────┐
              │          │          │
          4개 이상    2~3개      1개 이하
              │          │          │
              ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │  High  │ │ Medium │ │  Low   │
         └────┬───┘ └────┬───┘ └────────┘
              │          │
              ▼          ▼
         단, X1(종결) 해당 시 → 무조건 Low
```

### Few-shot 예시 (3건)

| # | 기사 | 판정 | 이유 |
|---|------|------|------|
| 1 | 쿠팡 개인정보 유출, 소상공인 집단소송 예고 | **High** | C1(책임 명확), C2(상장 대기업), C3(집단 피해), C6(소송 예고) |
| 2 | 압타밀 분유 리콜, 이물질 발견 | **Medium** | C2(글로벌 기업), C3(다수 소비자) — 2개 충족 |
| 3 | 5·18 유족 국가배상 판결 확정 | **Low** | X1(대법원 판결 확정, 종결 사건) |

### LLM JSON 응답 형식

```json
{
  "suitability": "High",
  "suitability_reason": "C1(책임 명확), C2(자력 충분), C3(집단 피해), C6(공적 절차) — 4개 충족",
  "case_category": "개인정보",
  "defendant": "쿠팡",
  "damage_amount": "미상",
  "victim_count": "다수 소상공인",
  "stage": "피해 발생",
  "stage_detail": "집단소송 준비 중",
  "summary": "쿠팡에서 대규모 개인정보 유출 사태가 발생하여...",
  "case_name": "쿠팡 개인정보 유출"
}
```

---

## 9. 데이터베이스 모델

### ER 다이어그램

```
┌─────────────────────┐       ┌──────────────────────────────────────────────────┐
│    MediaSource      │       │                  Article                         │
│─────────────────────│       │──────────────────────────────────────────────────│
│ id (PK)            │       │ id (PK)                                         │
│ name (unique)      │◄──────│ source_id (FK → MediaSource, nullable)          │
│ url                │  1:N  │ title                                           │
│ is_active          │       │ content (본문 텍스트)                             │
│ created_at         │       │ url (unique — 중복 크롤링 방지)                   │
└─────────────────────┘       │ author                                          │
                              │ published_at (기사 발행일)                       │
┌─────────────────────┐       │ collected_at (수집일)                            │
│     Keyword         │       │ status: pending|analyzing|analyzed|failed        │
│─────────────────────│       │ retry_count                                     │
│ id (PK)            │       └──────────────────┬───────────────────────────────┘
│ word (unique)      │                          │
│ is_active          │                          │ 1:1
│ created_at         │                          │
└─────────┬───────────┘                          │
          │                                      │
          │ M:N (ArticleKeyword)                 │
          │                                      ▼
          │                    ┌──────────────────────────────────────────────────┐
          └───────────────────▶│                 Analysis                         │
                               │──────────────────────────────────────────────────│
                               │ id (PK)                                         │
                               │ article_id (FK → Article, OneToOne)             │
┌─────────────────────┐        │ case_group_id (FK → CaseGroup, nullable)        │
│    CaseGroup        │        │                                                 │
│─────────────────────│        │ suitability: High | Medium | Low                │
│ id (PK)            │◄───────│ suitability_reason (판단 근거, C1~C6 참조)       │
│ case_id (unique)   │  N:1   │ case_category (사건 분야)                        │
│   CASE-2026-001    │        │ defendant (상대방)                               │
│ name (사건명)       │        │ damage_amount (피해 규모)                        │
│ description        │        │ victim_count (피해자 수)                         │
│ created_at         │        │ stage: 피해발생|절차진행|소송중|판결선고|종결       │
│ updated_at         │        │ stage_detail (단계 상세)                         │
└─────────────────────┘        │ summary (AI 요약 3~5문장)                       │
                               │ llm_model (gemini-2.5-flash)                   │
                               │ prompt_tokens                                  │
                               │ completion_tokens                              │
                               │ analyzed_at                                    │
                               └──────────────────────────────────────────────────┘
```

### Article 상태 흐름도

```
  ┌─────────┐     크롤링      ┌──────────┐    LLM 호출    ┌───────────┐
  │  (없음)  │ ─────────────▶ │  pending  │ ────────────▶ │ analyzing │
  └─────────┘    저장 시       └──────────┘   분석 시작     └─────┬─────┘
                                    ▲                           │
                                    │                     ┌─────┴─────┐
                                    │                     │           │
                              재분석 요청            성공         실패
                                    │                     │           │
                                    │                     ▼           ▼
                               ┌────┴─────┐       ┌──────────┐ ┌────────┐
                               │ 기존삭제  │       │ analyzed │ │ failed │
                               └──────────┘       └──────────┘ └────────┘
```

### 사건 그룹(CaseGroup) 자동 생성 흐름

```
 LLM 응답에서 case_name 추출
 (예: "쿠팡 개인정보 유출")
          │
          ▼
 같은 이름의 CaseGroup이 이미 있는가?
          │
    ┌─────┴─────┐
    │ YES       │ NO
    ▼           ▼
  기존 그룹    새 그룹 생성
  연결        CASE-2026-XXX
              (자동 번호 증가)
```

**예시**: "쿠팡 개인정보 유출" 관련 기사 50건이 모두 CASE-2026-001로 자동 그룹핑

### 사건 그룹 자동 매칭 (중복 방지)

#### 문제

AI가 같은 사건에 대해 조금씩 다른 이름을 만들 수 있습니다:

```
기사 A → "두쫀쿠 원재료 표시 및 이물질"  → 새 그룹 생성
기사 B → "두쫀쿠 소비자 민원"            → 또 새 그룹 생성 (중복!)
기사 C → "두쫀쿠 이물질 민원"            → 또 새 그룹 생성 (중복!)
```

#### 해결: 2단계 자동 매칭

**1단계: LLM 프롬프트에 기존 사건 목록 제공**

AI에게 기사를 분석 요청할 때, 이미 존재하는 사건 그룹 이름 목록을 함께 전달합니다.

```
## 기존 사건 그룹 목록
- 쿠팡 개인정보 유출
- 빗썸 비트코인 오지급
- 두쫀쿠 피스타치오 이물질 민원
- ...
```

AI는 이 목록을 보고, 분석 중인 기사가 기존 사건과 동일하면 **기존 이름을 그대로** 사용합니다.

```
기사 D → AI가 "두쫀쿠 피스타치오 이물질 민원" 선택 → 기존 그룹에 추가!
```

관련 코드: `backend/analyses/prompts.py`의 `build_messages()` — `existing_case_names` 파라미터

**2단계: Python 유사도 매칭 (안전장치)**

AI가 기존 이름을 사용하지 않고 새 이름을 만든 경우를 대비한 2차 안전장치입니다.

```python
# 새 이름 "두쫀쿠 이물질 소비자 피해"가 들어오면:

1단계: 정확히 일치하는 그룹 있나? → 없음
2단계: 유사한 이름의 그룹 있나?
        → "두쫀쿠 피스타치오 이물질 민원"과 유사도 0.80 → 매칭!
3단계: (유사 그룹 없으면) 새 그룹 생성
```

**유사도 계산 방식** (`_case_similarity()` 함수):

1. 기본 문자열 유사도 (`SequenceMatcher`)
2. 핵심 키워드 매칭 보너스:
   - "소송", "피해", "민원" 같은 **일반 법률 용어는 제외** (stopwords)
   - "쿠팡", "빗썸", "두쫀쿠" 같은 **핵심 엔티티(회사명/제품명)**만 비교
   - 핵심 엔티티가 겹치면 유사도에 보너스 부여
3. 최종 유사도 **0.6 이상**이면 기존 그룹에 매칭

**왜 stopwords를 빼나요?**

| 비교 | stopwords 미적용 | stopwords 적용 |
|------|-----------------|---------------|
| "두쫀쿠 이물질 소비자 피해" vs "해외직구 소비자 피해" | 0.96 (잘못된 매칭!) | 0.42 (매칭 안 됨) |
| "두쫀쿠 이물질 소비자 피해" vs "두쫀쿠 피스타치오 이물질 민원" | 0.50 (매칭 실패!) | 0.80 (정확한 매칭) |

"소비자", "피해" 같은 공통 단어가 오히려 엉뚱한 그룹에 매칭시키는 것을 방지합니다.

관련 코드: `backend/analyses/tasks.py`의 `_case_similarity()`, `find_or_create_case_group()`

### 무관 기사 자동 필터링 (is_relevant)

AI가 아래에 해당하는 기사를 `is_relevant=false`로 판정하여 목록에서 자동 숨김 처리합니다:

- 한국과 무관한 해외 뉴스 (외국 내부 소송, 외국 형사사건 등)
- 단순 형사 범죄 보도 (개인 간 살인, 폭행 등)
- 드라마/영화의 법정 스토리 소개 (실제 법적 분쟁이 아닌 허구)
- 문학 작품, 서평, 전시회 등 문화/예술 기사
- 칼럼, 사설 등 구체적 사건 정보가 없는 일반론
- 게임 업데이트, 제품 발표 등 IT 업계 소식
- 예방 캠페인, 정책 홍보, 마케팅 기사
- 적합 조건(C1~C6)을 하나도 충족하지 않는 기사

프론트엔드에서 "무관 기사 포함" 체크박스로 on/off 가능합니다.

관련 코드: `backend/analyses/prompts.py` (is_relevant 판단 기준), `backend/analyses/views.py` (필터링)

### 사건별 묶기 (목록 뷰)

분석 목록에서 같은 사건 그룹의 기사를 하나로 묶어 표시합니다.

- 기본 활성화 (체크박스로 on/off 가능)
- 각 사건 그룹에서 가장 최근 기사 1건만 대표로 표시
- 제목 옆에 `+N` 배지로 유사 기사 수 표시 (예: "+33")

### 유사 기사 표시 (상세 뷰)

기사 상세 페이지에서 같은 사건 그룹의 유사 기사를 보여줍니다.

- "판단 근거" 아래에 유사 기사 섹션 표시
- 기사 제목, 요약, 출처, 날짜, 원문 링크 제공
- 최대 10건까지 표시

---

## 10. REST API 명세

### 엔드포인트 목록

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/analyses/` | 분석 결과 목록 (페이지네이션, 필터, 검색, 정렬) |
| GET | `/api/analyses/{id}/` | 분석 결과 상세 |
| GET | `/api/analyses/stats/` | 대시보드 통계 데이터 |
| GET | `/api/analyses/export/` | 엑셀 파일 다운로드 |
| GET | `/api/case-groups/` | 사건 그룹 목록 |
| GET | `/api/case-groups/{id}/` | 사건 그룹 상세 |
| GET | `/api/articles/` | 기사 목록 |
| GET | `/api/articles/{id}/` | 기사 상세 |
| POST | `/api/articles/{id}/reanalyze/` | 기사 재분석 요청 |
| GET | `/api/keywords/` | 키워드 목록 |
| POST | `/api/keywords/` | 키워드 추가 |
| DELETE | `/api/keywords/{id}/` | 키워드 삭제 |
| GET | `/api/media-sources/` | 언론사 목록 |
| GET | `/api/docs/` | Swagger API 문서 |

### 분석 목록 필터 파라미터

```
GET /api/analyses/?suitability=High&stage=소송중&search=쿠팡&ordering=-analyzed_at&page=1
```

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `suitability` | 적합도 (복수 선택 시 쉼표 구분) | `High` 또는 `High,Medium` |
| `case_category` | 사건 유형 (부분 문자열 검색) | `개인정보` |
| `stage` | 소송 단계 (정확히 일치) | `소송중` |
| `date_from` | 기사 발행일 시작 | `2026-02-01` |
| `date_to` | 기사 발행일 끝 | `2026-02-16` |
| `case_group` | 사건 그룹 ID | `1` |
| `search` | 제목/상대방/요약/유형 통합 검색 | `쿠팡` |
| `ordering` | 정렬 기준 | `-analyzed_at` |
| `page` | 페이지 번호 | `1` |

### 통계 API 응답 형식

```
GET /api/analyses/stats/
```

```json
{
  "today_collected": 654,
  "today_high": 59,
  "today_medium": 133,
  "total_analyzed": 654,
  "monthly_cost": 0,
  "suitability_distribution": [
    {"name": "High", "value": 59},
    {"name": "Medium", "value": 133},
    {"name": "Low", "value": 462}
  ],
  "category_distribution": [
    {"name": "행정", "count": 134},
    {"name": "개인정보", "count": 73}
  ],
  "weekly_trend": [
    {"date": "2026-02-10", "total": 0, "high": 0, "medium": 0},
    {"date": "2026-02-16", "total": 654, "high": 59, "medium": 133}
  ]
}
```

---

## 11. 프론트엔드 페이지 구성

### 페이지 라우팅

```
┌─────────────────────────────────────────────────────────┐
│  TopNav (상단 내비게이션 - 네이비 배경, 골드 로고)         │
│  ┌──────────┐  ┌──────────┐            ┌──────┐        │
│  │ 대시보드  │  │ 분석 목록 │            │ 설정  │        │
│  │    /     │  │ /analyses│            │/sett │        │
│  └──────────┘  └──────────┘            └──────┘        │
└─────────────────────────────────────────────────────────┘

라우트:
  /                → Dashboard     (대시보드)
  /analyses        → AnalysisList  (분석 목록)
  /analyses/:id    → AnalysisDetail (분석 상세)
  /settings        → Settings      (키워드 관리)
```

### 대시보드 (Dashboard)

```
┌──────────────────────────────────────────────────────────┐
│  대시보드                                                │
│  AI 기반 법률 뉴스 분석 현황을 한눈에 확인하세요              │
│                                                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │오늘 수집 │ │분석 완료 │ │High 적합│ │Med 적합 │       │
│  │   654   │ │   654   │ │   59    │ │   133   │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  적합도 분포      │  │  사건 분야별 분포 │               │
│  │  (도넛 차트)     │  │  (가로 바 차트)  │               │
│  │  High / Med / Low│  │  상위 10개 분야  │               │
│  └─────────────────┘  └─────────────────┘               │
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │  주간 수집 추이 (라인 차트)            │               │
│  │  전체 / High / Medium 3개 라인        │               │
│  └──────────────────────────────────────┘               │
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │  최근 분석 결과 (테이블 5건)           │               │
│  │  적합도 | 기사제목 | 분야 | 상대방 | ..│               │
│  └──────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

### 분석 목록 (AnalysisList)

```
┌──────────────────────────────────────────────────────────┐
│  분석 목록                                               │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ [검색창]  [적합도 ▼]  [단계 ▼]      [엑셀 다운로드]│   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  적합도│기사제목│분야│피해자│상대방│피해액│단계│케이스│날짜 │
│  ──────┼───────┼───┼─────┼─────┼─────┼───┼─────┼──── │
│  High  │쿠팡...│개인│다수  │쿠팡 │미상 │발생│001  │02-16│
│  Med   │압타..│제조│미상  │다논 │미상 │발생│002  │02-16│
│  Low   │5·18..│행정│미상  │대한 │미상 │종결│003  │02-16│
│                                                          │
│              [1] [2] [3] ... [33]                         │
└──────────────────────────────────────────────────────────┘
```

### 분석 상세 (AnalysisDetail)

```
┌─────────────────────────────────┬─────────────────────┐
│  [기사 제목]                     │  AI 분석 결과 (고정) │
│  출처: 조선일보 | 2026-02-16     │                     │
│                                 │  적합도: High       │
│  ─── AI 요약 ───                │  사건 분야: 개인정보  │
│  쿠팡에서 대규모 개인정보          │  상대방: 쿠팡       │
│  유출 사태가 발생하여...          │  피해자: 다수        │
│                                 │  피해액: 미상        │
│  ─── 판단 근거 ───              │  단계: 피해 발생     │
│  C1(책임 명확), C2(자력 충분)    │  케이스: CASE-2026-001│
│  C3(집단 피해), C6(공적 절차)    │                     │
│  — 4개 적합 조건 충족            │  [재분석 요청]       │
│                                 │                     │
└─────────────────────────────────┴─────────────────────┘
```

### 설정 (Settings)

```
┌──────────────────────────────────────────────────────────┐
│  설정                                                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 수집 키워드 관리                                    │   │
│  │ 뉴스 크롤링에 사용되는 검색 키워드를 관리합니다.       │   │
│  │                                                    │   │
│  │ [소송 x] [손해배상 x] [집단소송 x] [공동소송 x]     │   │
│  │ [피해자 x] [피해보상 x] [피해구제 x]                │   │
│  │                                                    │   │
│  │ [새 키워드 입력_______________] [+ 추가]            │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 12. 주요 설정값

### .env 환경변수 전체 목록

| 변수 | 설명 | 기본값/예시 |
|------|------|-----------|
| `DJANGO_SECRET_KEY` | Django 보안 키 | `your-secret-key` |
| `DEBUG` | 디버그 모드 | `True` (개발) / `False` (운영) |
| `ALLOWED_HOSTS` | 허용 호스트 | `localhost,127.0.0.1` |
| `NAVER_CLIENT_ID` | 네이버 API 클라이언트 ID | 네이버 개발자센터에서 발급 |
| `NAVER_CLIENT_SECRET` | 네이버 API 시크릿 | 네이버 개발자센터에서 발급 |
| `GEMINI_API_KEY` | Gemini API 키 | Google AI Studio에서 발급 |
| `LLM_MODEL` | 사용할 LLM 모델 | `gemini-2.5-flash` |
| `LLM_TEMPERATURE` | LLM 응답 다양성 (낮을수록 일관적) | `0.1` |
| `CRAWL_INTERVAL_MINUTES` | 크롤링 주기 (분) | `60` |
| `NEWS_KEYWORDS` | 수집 키워드 (쉼표 구분) | `소송,손해배상,집단소송,...` |
| `ENABLE_PIPELINE_ON_RUNSERVER` | runserver 시 자동 파이프라인 | `False` |
| `PIPELINE_INTERVAL_MINUTES` | 자동 파이프라인 반복 주기 (분) | `60` |

### LLM 비용 추정

| 모델 | 입력 가격 | 출력 가격 | 기사당 비용 |
|------|----------|----------|-----------|
| Gemini 2.5 Flash | 무료 티어 / 유료 구간 존재 | 무료 티어 / 유료 구간 존재 | 무료 티어 내 $0 |

> Gemini는 현재 토큰 수를 DB에 기록하지 않으므로, 대시보드의 "비용" 항목은 항상 0원으로 표시됩니다.

### 등록된 언론사 (80개)

종합일간지, 방송/통신사, 경제지, 인터넷 매체, IT 전문지, 매거진, 전문지, 지역 매체를 포함합니다.

---

## 13. 운영 가이드

### 자동 파이프라인 (권장)

`.env`에서 아래 설정을 활성화하면, `runserver` 시작과 동시에 자동으로 크롤링 + 분석이 실행됩니다.

```env
ENABLE_PIPELINE_ON_RUNSERVER=True
PIPELINE_INTERVAL_MINUTES=60
```

서버 시작 시:
1. 즉시 1회 `crawl_news()` + `analyze_pending_articles()` 실행 (백그라운드 스레드)
2. 이후 60분마다 반복

### 일일 운영 루틴 (수동)

```
┌──────────────────────────────────────────────────────────────┐
│                     일일 운영 순서                             │
│                                                              │
│  1. 크롤링 실행 ─────────────────────────────────▶ 약 5분     │
│     새로운 법률 뉴스 수집 (7개 키워드)                         │
│                                                              │
│  2. AI 분석 실행 ────────────────────────────────▶ 약 30~50분 │
│     수집된 기사에 Gemini 적합도 판정                           │
│                                                              │
│  3. 대시보드 확인 ───────────────────────────────▶ 즉시       │
│     http://localhost:5173                                    │
│                                                              │
│  4. High 사건 확인 ──────────────────────────────▶ 즉시       │
│     분석 목록 → "High + Medium" 필터 선택                     │
│                                                              │
│  5. 엑셀 다운로드 (필요 시) ─────────────────────▶ 즉시       │
│     분석 목록 → "엑셀 다운로드" 버튼                           │
└──────────────────────────────────────────────────────────────┘
```

### 크롤링 실행 명령어

```bash
# 가상환경 활성화 후 실행
python backend/manage.py shell -c "
from articles.tasks import crawl_news
crawl_news()
"
```

### AI 분석 실행 명령어

```bash
python backend/manage.py shell -c "
from analyses.tasks import analyze_pending_articles
analyze_pending_articles()
"
```

### 키워드 관리

설정 페이지(`/settings`)에서 수집 키워드를 추가/삭제할 수 있습니다.

현재 기본 키워드 (7개):
`소송`, `손해배상`, `집단소송`, `공동소송`, `피해자`, `피해보상`, `피해구제`

### 특정 기사 재분석

분석 상세 페이지에서 **"재분석 요청"** 버튼을 클릭하면:

```
1. 기존 Analysis 레코드 삭제
2. Article.status → "pending"으로 복구
3. Gemini 2.5 Flash로 재분석 실행
```

---

## 14. 트러블슈팅

### Windows에서 한글 인코딩 오류

```
UnicodeEncodeError: 'charmap' codec can't encode characters
```

**해결**: 환경변수 설정 후 재실행

```bash
# Windows CMD
set PYTHONIOENCODING=utf-8
python backend/manage.py runserver

# 또는 PowerShell
$env:PYTHONIOENCODING="utf-8"
python backend/manage.py runserver
```

### pip 패키지 설치 실패

```bash
# pip이 없는 경우
python -m ensurepip --upgrade

# 재설치
pip install -r backend/requirements.txt
```

### 포트 충돌 (5173 이미 사용 중)

Vite가 자동으로 다음 포트(5174 등)를 선택합니다. 터미널에 표시된 URL을 확인하세요.

```
  VITE v7.x.x  ready in 461 ms
  ➜  Local:   http://localhost:5174/    ← 이 URL을 사용
```

### 네이버 API 호출 제한

네이버 검색 API는 일일 25,000건 제한이 있습니다.
현재 기본 설정(7개 키워드 x 키워드당 최대 100건) 기준으로 1회 수집 시 최대 700건이므로,
일반적인 개발/운영에서는 보통 제한에 걸리지 않습니다.

### LLM 분석 실패(failed 상태) 기사 재처리

```bash
# failed 상태 기사 확인
python backend/manage.py shell -c "
from articles.models import Article
failed = Article.objects.filter(status='failed')
for a in failed:
    print(f'{a.id}: {a.title} (retry: {a.retry_count})')
"

# failed → pending으로 변경 후 재분석
python backend/manage.py shell -c "
from articles.models import Article
from analyses.tasks import analyze_pending_articles
Article.objects.filter(status='failed').update(status='pending', retry_count=0)
analyze_pending_articles()
"
```

### Django 마이그레이션 오류

```bash
# 마이그레이션 파일 새로 생성 + 적용
python backend/manage.py makemigrations
python backend/manage.py migrate
```

### 빠른 상태 점검

```bash
# Article 상태별 집계
python backend/manage.py shell -c "
from articles.models import Article
from django.db.models import Count
print(list(Article.objects.values('status').annotate(c=Count('id')).order_by('status')))
"
```

---

## 라이선스

이 프로젝트는 로앤굿(LawNGood)을 위해 개발되었습니다.
