# LawNGood — AI 법률 뉴스 분석 시스템

> 법률 뉴스를 자동으로 수집하고, AI(Gemini 2.5 Flash)가 소송금융 가이드라인에 따라 소송금융 투자 적합도(High/Medium/Low)를 판정하는 시스템입니다.

---

## 빠른 시작 가이드 (Quick Start)

> 아래 단계를 순서대로 따라하면 시스템이 실행됩니다.
> 예상 소요 시간: **약 10~15분**

### 사전 준비물

시작하기 전에 아래 4가지가 컴퓨터에 설치되어 있어야 합니다.

| 필요한 것 | 확인 방법 | 없다면 |
|----------|----------|--------|
| **Python 3.12+** | `python --version` | [python.org](https://www.python.org/downloads/) (설치 시 **"Add to PATH" 체크**) |
| **Node.js 18+** | `node --version` | [nodejs.org](https://nodejs.org/) LTS 버전 |
| **Docker Desktop** | `docker --version` | [docker.com](https://www.docker.com/products/docker-desktop/) (PostgreSQL 실행용) |
| **Git** | `git --version` | [git-scm.com](https://git-scm.com/) |

---

### STEP 1. 프로젝트 다운로드

```powershell
git clone https://github.com/ken-do-it/law_news_c_v2.git
cd law_news_c_v2
```

---

### STEP 2. 도구 설치

```powershell
# Python 패키지 매니저 (uv)
pip install uv

# Node.js 패키지 매니저 (bun)
npm install -g bun

# 명령어 도구 (just)
winget install Casey.Just
```

> 설치 후 터미널을 **한 번 닫았다가 다시 열어야** 명령어가 인식됩니다.

설치 확인:

```powershell
uv --version    # 예: uv 0.6.x
bun --version   # 예: 1.x.x
just --version  # 예: just 1.x.x
docker --version  # 예: Docker version 27.x.x
```

---

### STEP 3. 환경변수 설정 (API 키 입력)

프로젝트 폴더에 `.env` 파일을 열고 아래 항목을 입력하세요:

```
# 네이버 뉴스 검색 API (필수 — 뉴스 수집용)
NAVER_CLIENT_ID=발급받은_클라이언트_ID
NAVER_CLIENT_SECRET=발급받은_시크릿

# Gemini API (필수 — AI 분석용)
GEMINI_API_KEY=발급받은_키
```

**API 키 발급처:**

| API | 발급 사이트 | 비용 |
|-----|-----------|------|
| 네이버 검색 API | [developers.naver.com](https://developers.naver.com/apps/) | 무료 (일 25,000건) |
| Gemini API | [aistudio.google.com](https://aistudio.google.com/apikey) | 무료 티어 |

---

### STEP 4. 전체 설치 + 초기화 (한 번만)

```powershell
just setup
```

이 명령어 하나로 아래가 **자동으로** 실행됩니다:

```
✅ PostgreSQL Docker 컨테이너 시작 (law-news-postgres)
✅ Python 패키지 설치 (Django, AI 라이브러리 등)
✅ Node.js 패키지 설치 (React, Tailwind 등)
✅ 데이터베이스 테이블 생성
✅ 초기 데이터 입력 (95개 언론사 + 7개 검색 키워드)
```

---

### STEP 5. 관리자 계정 만들기

```powershell
just superuser
```

---

### STEP 6. 서버 실행

```powershell
just dev
```

새 창이 2개 열리며 아래 주소로 접속 가능합니다:

| 서비스 | 주소 | 설명 |
|--------|------|------|
| **대시보드** | http://localhost:5173 | 메인 화면 (차트, 분석 목록) |
| **Django 관리자** | http://localhost:8000/admin/ | DB 직접 관리 |
| **API 문서** | http://localhost:8000/api/docs/ | Swagger API 문서 |

> **자동 실행**: 서버가 시작되면 APScheduler가 **수집(60분)** 과 **분석(5분)** 을 자동으로 반복합니다.

---

### STEP 7. 수동 수집 + AI 분석 (초기 데이터 구축 시)

```powershell
# 수집과 분석을 한 번에
just pipeline

# 또는 따로 실행
just crawl      # 뉴스 수집만
just analyze    # AI 분석만 (pending 기사 전체)
just analyze --limit 100  # 100건만 분석
```

`just analyze` 실행 시 건별 실시간 진행 상황이 출력됩니다:

```
분석 시작: 307건
────────────────────────────────────────────────────────────────────────
[  1/307] ✓  1.2s │ 법무법인 '허위 소송비' 수임료 반환 소송...
[  2/307] ✓  0.9s │ 재건축 조합장 업무상 배임 혐의로...
...
[  10/307]           진행  3.2% │ 평균 1.1s/건 │ 남은시간 약 5분
────────────────────────────────────────────────────────────────────────
완료: 307건 처리 — 성공 300  실패 7  (소요 5.6분, 평균 1.1s/건)
```

---

## 주요 명령어 모음

### 서버

| 명령어 | 설명 |
|--------|------|
| `just dev` | 백엔드 + 프론트엔드 동시 실행 |
| `just backend` | 백엔드만 실행 |
| `just frontend` | 프론트엔드만 실행 |

### PostgreSQL (Docker)

| 명령어 | 설명 |
|--------|------|
| `just pg-start` | PostgreSQL 컨테이너 시작 |
| `just pg-stop` | PostgreSQL 컨테이너 중지 |
| `just pg-status` | 컨테이너 상태 확인 |
| `just pg-shell` | psql 접속 |

### 뉴스 수집 & AI 분석

| 명령어 | 설명 |
|--------|------|
| `just crawl` | 뉴스 수집 (7개 키워드 × 100건, 스케줄러 충돌 없음) |
| `just analyze` | 대기 중인 기사 전체 AI 분석 (건별 실시간 진행 출력) |
| `just analyze --limit N` | N건만 분석 |
| `just pipeline` | 수집 → 분석 한 번에 실행 |
| `just regroup` | 기존 분석 케이스 그룹 재매칭 |
| `just stats` | 현재 DB 통계 출력 |

### 데이터베이스

| 명령어 | 설명 |
|--------|------|
| `just migrate` | DB 마이그레이션 적용 |
| `just seed` | 초기 데이터 입력 |
| `just db-reset` | DB 전체 초기화 |
| `just db-reset-analyses` | 분석 결과만 초기화 (기사 유지) |
| `just superuser` | 관리자 계정 생성 |

### 설치 & 설정

| 명령어 | 설명 |
|--------|------|
| `just setup` | 전체 초기 셋업 (PG + 의존성 + DB + 시드) |
| `just install` | 의존성 설치 (백엔드 + 프론트엔드) |
| `just admin` | Django 관리자 페이지 열기 |
| `just docs` | API 문서 (Swagger) 열기 |

---

## 일일 운영 순서

```
1. just pg-start     ← PostgreSQL 시작 (Docker Desktop 실행 필요)
2. just dev          ← 서버 실행 (이미 실행 중이면 생략)
   → APScheduler가 자동으로 수집(60분) + 분석(5분) 반복
3. 브라우저에서 대시보드 확인  ← http://localhost:5173
4. "High" 사건 확인   ← 분석 목록에서 적합도 필터링
5. 엑셀 다운로드 (필요 시)  ← 분석 목록 우측 상단 버튼
```

---

## 간단 트러블슈팅

| 증상 | 해결 |
|------|------|
| `just` 명령어 인식 안 됨 | `winget install Casey.Just` 후 터미널 재시작 |
| 서버가 안 켜짐 | `just pg-start` → `just install` → `just migrate` |
| PostgreSQL 연결 실패 | Docker Desktop 실행 확인 → `just pg-start` |
| 크롤링 0건 수집 | `.env`의 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 확인 |
| AI 분석 실패 | `.env`의 `GEMINI_API_KEY` 확인 후 `just analyze` 재실행 |
| 포트 충돌 | Vite가 자동으로 다음 포트 선택 — 터미널에 표시된 URL 확인 |

---

## 기술 스택 요약

| 영역 | 기술 |
|------|------|
| 백엔드 | Python 3.12, Django 5, Django REST Framework |
| AI | Google Gemini 2.5 Flash |
| 프론트엔드 | React 19, TypeScript, Vite 7, Tailwind CSS 4 |
| 차트 | Recharts 3 |
| DB | PostgreSQL 16 (Docker) |
| 스케줄링 | APScheduler (수집 60분 / 분석 5분 주기) |
| 도구 | uv, bun, just |

---
---

# 상세 기술 문서

> 아래부터는 개발자를 위한 상세 기술 문서입니다.

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [전체 아키텍처](#2-전체-아키텍처)
3. [기술 스택](#3-기술-스택)
4. [프로젝트 폴더 구조](#4-프로젝트-폴더-구조)
5. [환경 준비](#5-환경-준비)
6. [프로젝트 설치 및 실행](#6-프로젝트-설치-및-실행)
7. [데이터 파이프라인](#7-데이터-파이프라인)
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
| 1단계 | 매일 뉴스를 검색하여 법률 관련 기사를 찾음 | 네이버 뉴스 API로 7개 키워드 자동 크롤링 (60분 주기) |
| 2단계 | 기사를 읽고 투자 적합 여부를 판단 | AI가 6가지 기준(C1~C6)으로 자동 판정 (5분 주기) |
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
│  │ 대시보드  │  │ 분석목록  │  │  케이스 상세  │  │  설정   │         │
│  │ (차트)   │  │ (테이블)  │  │  (AI 요약)   │  │(키워드) │         │
│  └──────────┘  └──────────┘  └──────────────┘  └────────┘         │
│                                                                     │
│  Vite 개발서버가 /api/* 요청을 백엔드로 프록시                         │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ /api/*
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   백엔드 (Django REST Framework)                     │
│                     http://localhost:8000                            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐    │
│  │ articles 앱 │  │ analyses 앱  │  │ scheduler 앱            │    │
│  │ (크롤링)    │  │ (AI 분석)    │  │ APScheduler             │    │
│  └──────┬──────┘  └──────┬───────┘  │ ├ crawl  (60분 주기)    │    │
│         │                │          │ └ analyze (5분 주기)    │    │
│         ▼                ▼          └─────────────────────────┘    │
│  ┌──────────────────────────────────────┐                          │
│  │  PostgreSQL 16 (Docker)              │                          │
│  │  localhost:5432 / law_news           │                          │
│  └──────────────────────────────────────┘                          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│   네이버 뉴스 API     │  │  Gemini 2.5 Flash    │
│   (기사 수집)         │  │  (AI 분석 — 기본)     │
│                      │  │                      │
│  Client-Id/Secret    │  │                      │
└──────────────────────┘  └──────────────────────┘
```

### 데이터 흐름 상세

```
 ① 크롤링 (60분)           ② AI 분석 (5분)              ③ 결과 제공
 ──────────────            ──────────────               ──────────
 네이버 뉴스 API            Gemini API                   REST API
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
| APScheduler | 3.x | 수집/분석 자동 스케줄링 (60분/5분) |
| google-genai | 1.64+ | Gemini LLM 호출 |
| requests | 2.31+ | 네이버 API HTTP 호출 |
| BeautifulSoup4 | 4.12+ | HTML 파싱 (기사 본문 추출) |
| openpyxl | 3.1+ | 엑셀 파일 생성 |
| psycopg | 3.x | PostgreSQL 드라이버 |

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

### 인프라

| 기술 | 역할 |
|------|------|
| PostgreSQL 16 (Docker) | 운영 데이터베이스 |
| Docker Desktop | PostgreSQL 컨테이너 실행 |
| uv | Python 패키지 관리 |
| bun | Node.js 패키지 관리 |
| just | 태스크 러너 (Makefile 대체) |

---

## 4. 프로젝트 폴더 구조

```
law_news_c_v2/                    ← 프로젝트 루트
│
├── .env                          ← 환경변수 (API 키) — git 미추적
├── Justfile                      ← 명령어 정의 (just xxx)
├── pyproject.toml                ← Python 패키지 목록 (uv 관리)
├── README.md                     ← 이 문서
│
├── backend/                      ← Django 백엔드
│   ├── manage.py
│   │
│   ├── config/                   ← Django 프로젝트 설정
│   │   ├── settings.py           ← 전체 설정 (DB, API키, CORS, 스케줄 주기 등)
│   │   └── urls.py               ← URL 라우팅
│   │
│   ├── articles/                 ← 뉴스 기사 앱 (수집 담당)
│   │   ├── models.py             ← 모델: MediaSource, Keyword, Article
│   │   ├── crawlers.py           ← 네이버 뉴스 API 크롤러
│   │   ├── tasks.py              ← crawl_news() 크롤링 태스크
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── management/commands/
│   │       ├── seed_initial_data.py
│   │       └── crawl_news.py     ← just crawl (스케줄러 없이 단독 실행)
│   │
│   ├── analyses/                 ← AI 분석 앱
│   │   ├── models.py             ← 모델: CaseGroup, Analysis
│   │   ├── prompts.py            ← LLM 프롬프트 + Few-shot 예시
│   │   ├── validators.py         ← LLM 응답 JSON 검증
│   │   ├── tasks.py              ← analyze_single_article() + Case 그룹핑 로직
│   │   ├── export.py             ← 엑셀 내보내기
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── management/commands/
│   │       ├── run_analysis.py   ← just analyze (bulk 재분석)
│   │       └── regroup_analyses.py
│   │
│   └── scheduler/                ← APScheduler 앱
│       ├── apps.py               ← 웹 서버 실행 시에만 스케줄러 시작 (관리 명령어에서는 미시작)
│       └── scheduler.py          ← crawl(60분) + analyze(5분) 두 개 독립 잡
│
└── frontend/                     ← React 프론트엔드
    ├── package.json
    ├── vite.config.ts            ← Vite 설정 (프록시 포함)
    └── src/
        ├── lib/
        │   ├── types.ts          ← TypeScript 인터페이스
        │   └── api.ts            ← Axios API 클라이언트
        ├── components/
        │   ├── SuitabilityBadge.tsx
        │   ├── AiSuitabilityDisplay.tsx  ← 케이스 적합도 분포 표시
        │   ├── StageBadge.tsx
        │   └── ...
        └── pages/
            ├── Dashboard.tsx
            ├── AnalysisList.tsx  ← 분석 목록 (케이스 단위 뷰)
            ├── CaseDetail.tsx    ← 케이스 상세 + 심사 기능
            ├── AnalysisDetail.tsx
            └── Settings.tsx
```

---

## 5. 환경 준비

### 5-1. Python 3.12+ 설치

```bash
python --version  # Python 3.12.x
```

> [python.org](https://www.python.org/downloads/) — 설치 시 `Add Python to PATH` 체크 필수

### 5-2. Docker Desktop 설치

PostgreSQL을 Docker로 실행합니다.

```bash
docker --version  # Docker version 27.x.x
```

> [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

### 5-3. uv 설치

```bash
pip install uv
uv --version
```

### 5-4. API 키 준비

| API | 용도 | 발급처 |
|-----|------|--------|
| 네이버 검색 API | 뉴스 기사 수집 | [developers.naver.com](https://developers.naver.com/apps/) |
| Gemini API | AI 분석 (기본 LLM) | [aistudio.google.com](https://aistudio.google.com/apikey) |


---

## 6. 프로젝트 설치 및 실행

### 6-1. 저장소 클론

```bash
git clone https://github.com/ken-do-it/law_news_c_v2.git
cd law_news_c_v2
```

### 6-2. 환경변수 설정

`.env` 파일에 API 키 입력:

```env
NAVER_CLIENT_ID=발급받은_클라이언트_ID
NAVER_CLIENT_SECRET=발급받은_시크릿
GEMINI_API_KEY=발급받은_키
```

### 6-3. 전체 설치

```powershell
just setup
```

### 6-4. 수동 설치 (just 없이)

```bash
# 1) PostgreSQL 컨테이너 시작
docker run -d --name law-news-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=law_news \
  -p 5432:5432 postgres:16-alpine

# 2) 백엔드 패키지 설치
uv sync

# 3) 프론트엔드 패키지 설치
cd frontend && bun install && cd ..

# 4) 데이터베이스 초기화
uv run python backend/manage.py migrate

# 5) 초기 데이터 입력
uv run python backend/manage.py seed_initial_data
```

### 6-5. 서버 실행

```powershell
just dev
# → 백엔드 http://localhost:8000
# → 프론트엔드 http://localhost:5173
# → APScheduler: 수집(60분) + 분석(5분) 자동 시작
```

---

## 7. 데이터 파이프라인

### 자동 스케줄링

```
Django 서버 시작
      │
      ├─ 10초 후 → crawl 잡 첫 실행 → 이후 60분마다 반복
      └─ 15초 후 → analyze 잡 첫 실행 → 이후 5분마다 반복
```

두 잡은 독립적으로 실행됩니다. 분석 잡이 실행 중이어도 수집 잡은 정상 동작합니다.

### 크롤링 프로세스

```
네이버 뉴스 API (7개 키워드 × 100건)
      │
      ▼
URL 중복 체크 → 이미 있으면 SKIP
      │
      ▼
언론사 식별 (URL 도메인 매핑 → 실패 시 페이지 스크래핑)
      │
      ▼
기사 본문 추출 (네이버 뉴스 #dic_area)
      │
      ▼
Article 저장 (status="pending")
```

### AI 분석 프로세스

```
pending/analyzing 기사 순회
      │
      ▼
프롬프트 구성 (시스템 + Few-shot 3건 + 기사 본문 3000자)
      │
      ▼
Gemini 2.5 Flash 호출
      │
      ▼
JSON 응답 파싱 + 검증
      │
      ▼
Analysis 저장 + CaseGroup 자동 매칭/생성
      │
      ▼
Article.status = "analyzed"
```

---

## 8. AI 분석 프롬프트 상세

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
  High      Medium      Low
   └──── X1 해당 시 무조건 Low ────┘
```

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
┌─────────────────────┐       ┌──────────────────────────────────────┐
│    MediaSource      │       │              Article                  │
│─────────────────────│       │──────────────────────────────────────│
│ id (PK)            │◄──────│ source_id (FK, nullable)             │
│ name (unique)      │  1:N  │ title                                │
│ url                │       │ content (본문 텍스트)                  │
│ is_active          │       │ url (unique)                         │
└─────────────────────┘       │ published_at                        │
                              │ status: pending|analyzing|analyzed|failed │
┌─────────────────────┐       └──────────────────┬───────────────────┘
│     Keyword         │                          │ 1:1
│─────────────────────│                          ▼
│ id (PK)            │       ┌──────────────────────────────────────┐
│ word (unique)      │       │             Analysis                  │
│ is_active          │       │──────────────────────────────────────│
└─────────────────────┘       │ article_id (FK, OneToOne)           │
                              │ case_group_id (FK, nullable)        │
┌─────────────────────┐       │ suitability: High|Medium|Low        │
│    CaseGroup        │       │ suitability_reason                  │
│─────────────────────│       │ case_category                       │
│ id (PK)            │◄──────│ defendant                           │
│ case_id            │  N:1  │ damage_amount                       │
│   2026-MM-XXX      │       │ victim_count                        │
│ name (사건명)       │       │ stage                               │
│ review_completed   │       │ summary                             │
│ client_suitability │       │ is_relevant                         │
│ accepted           │       │ analyzed_at                         │
└─────────────────────┘       └──────────────────────────────────────┘
```

### 사건 그룹 자동 매칭 (Case ID)

```
LLM 응답에서 case_name 추출
      │
      ▼
① 기존 그룹 이름과 정확히 일치?  → YES → 기존 그룹 연결
      │ NO
      ▼
② Python 유사도 ≥ 0.85?         → YES → 기존 그룹 연결
      │ NO
      ▼
③ 제목 키워드 4개 이상 겹침?     → YES → 기존 그룹 연결
      │ NO
      ▼
새 CaseGroup 생성 (case_id: 2026-MM-XXX)
```

> LLM 프롬프트에 기존 사건 목록(최근 90일, 최대 150건)을 함께 전달하여 1차로 일관성을 유도합니다.

---

## 10. REST API 명세

### 주요 엔드포인트

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/analyses/` | 분석 결과 목록 (케이스 단위 뷰 포함) |
| GET | `/api/analyses/{id}/` | 분석 결과 상세 |
| GET | `/api/analyses/stats/` | 대시보드 통계 |
| GET | `/api/analyses/export/` | 엑셀 다운로드 |
| PATCH | `/api/analyses/{id}/review/` | 심사 결과 저장 |
| GET | `/api/case-groups/` | 사건 그룹 목록 |
| GET | `/api/case-groups/{case_id}/` | 사건 그룹 상세 |
| GET | `/api/articles/` | 기사 목록 |
| POST | `/api/articles/{id}/reanalyze/` | 기사 재분석 요청 |
| GET | `/api/keywords/` | 키워드 목록 |
| POST | `/api/keywords/` | 키워드 추가 |
| GET | `/api/docs/` | Swagger API 문서 |

### 분석 목록 주요 파라미터

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `suitability` | 적합도 필터 | `High`, `Medium`, `Low` |
| `search` | 제목/케이스ID 통합 검색 | `쿠팡` |
| `group_by_case` | 케이스 단위 뷰 | `true` |
| `include_irrelevant` | 비관련 기사 포함 | `true` |
| `ordering` | 정렬 기준 | `-analyzed_at`, `-damage_amount_num` |
| `page` | 페이지 번호 | `1` |

---

## 11. 프론트엔드 페이지 구성

### 페이지 라우팅

```
/                      → Dashboard     (대시보드)
/analyses              → AnalysisList  (분석 목록 — 케이스 단위)
/analyses/:id          → AnalysisDetail (기사 단위 상세)
/analyses/case/:caseId → CaseDetail    (케이스 상세 + 심사)
/settings              → Settings      (키워드 관리)
```

### 케이스 상세 (CaseDetail)

- 케이스 소속 기사 목록 + 적합도 분포 표시
- 기사 클릭 시 AI 요약 + 판단 근거 펼치기/접기
- 로앤굿 심사 기능 (client_suitability, accepted)

---

## 12. 주요 설정값

### .env 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 접속 URL | `postgresql://postgres:postgres@localhost:5432/law_news` |
| `DJANGO_SECRET_KEY` | Django 보안 키 | — |
| `DEBUG` | 디버그 모드 | `True` |
| `NAVER_CLIENT_ID` | 네이버 API ID | — |
| `NAVER_CLIENT_SECRET` | 네이버 API 시크릿 | — |
| `GEMINI_API_KEY` | Gemini API 키 | — |
| `GEMINI_MODEL` | Gemini 모델명 | `gemini-2.5-flash` |
| `LLM_TEMPERATURE` | LLM 응답 다양성 | `0.1` |
| `LLM_MAX_TOKENS` | LLM 최대 응답 길이 | `8192` |
| `CRAWL_INTERVAL_MINUTES` | 수집 주기 (분) | `60` |
| `ANALYSIS_INTERVAL_MINUTES` | 분석 주기 (분) | `5` |
| `NEWS_KEYWORDS` | 수집 키워드 (쉼표 구분) | `소송,손해배상,...` |

### LLM 비용 추정

| 모델 | 비용 | 비고 |
|------|------|------|
| Gemini 2.5 Flash | 무료 티어 | AI 분석 |

---

## 13. 운영 가이드

### 일일 운영 루틴

```
1. Docker Desktop 실행 확인
2. just pg-start      ← PostgreSQL 시작
3. just dev           ← 서버 실행 (APScheduler 자동 시작)
   → 수집: 60분마다 자동
   → 분석: 5분마다 자동
4. 대시보드 확인       ← http://localhost:5173
5. High/Medium 사건 검토 + 로앤굿 심사 입력
6. 엑셀 다운로드 (필요 시)
```

### 전체 재분석 (DB 초기화 후)

```powershell
just db-reset-analyses    # Analysis + CaseGroup 삭제, 기사 pending 리셋
just analyze              # 전체 재분석 (백그라운드 권장)
```

### 케이스 그룹 재매칭

```powershell
just regroup              # 최근 분석만
just regroup --all        # 전체 재매칭
just regroup --dry-run    # 미리보기 (실제 변경 없음)
```

---

## 14. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `just` 명령어 인식 안 됨 | just 미설치 | `winget install Casey.Just` 후 터미널 재시작 |
| PostgreSQL 연결 실패 | Docker 미실행 | Docker Desktop 실행 → `just pg-start` |
| 서버 시작 오류 | 의존성/마이그레이션 문제 | `just install` → `just migrate` |
| 크롤링 0건 수집 | 네이버 API 키 오류 | `.env` `NAVER_CLIENT_ID/SECRET` 확인 |
| AI 분석 실패 | Gemini API 키 오류 | `.env` `GEMINI_API_KEY` 확인 |
| Windows 한글 인코딩 오류 | cp949 인코딩 충돌 | `$env:PYTHONIOENCODING="utf-8"` 설정 후 재실행 |
| 포트 충돌 | 5173 사용 중 | Vite가 자동으로 다음 포트 선택 — 터미널 확인 |

---

## 라이선스

이 프로젝트는 로앤굿(LawNGood)을 위해 개발되었습니다.
