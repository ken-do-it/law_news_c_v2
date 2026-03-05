# ============================================================
#  법률 분쟁 사건 자동 발굴 시스템 — Justfile
#  버전: 1.1.0  (PostgreSQL + APScheduler 기반)
# ============================================================

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

export PYTHONIOENCODING := "utf-8"

manage := "uv run python backend/manage.py"

# ── 기본: 사용 가능한 명령어 목록 ─────────────────────────
[doc("사용 가능한 명령어 목록")]
default:
    @just --list --unsorted

# ============================================================
#  서버
# ============================================================

[doc("백엔드 + 프론트엔드 동시 실행")]
dev:
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '{{justfile_directory()}}'; uv run python backend/manage.py runserver"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '{{justfile_directory()}}\frontend'; bun run dev"
    Write-Host "`n  Backend  → http://localhost:8000" -ForegroundColor Cyan
    Write-Host "  Frontend → http://localhost:5173`n" -ForegroundColor Cyan

[doc("Django 백엔드 서버 실행")]
backend:
    {{manage}} runserver

[doc("프론트엔드 개발 서버 실행")]
frontend:
    cd frontend; bun run dev

# ============================================================
#  PostgreSQL (Docker)
# ============================================================

[doc("PostgreSQL Docker 컨테이너 시작")]
pg-start:
    docker start law-news-postgres 2>$null; if ($LASTEXITCODE -ne 0) { docker run -d --name law-news-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=law_news -p 5432:5432 postgres:16-alpine }
    Write-Host "  PostgreSQL 실행 중 → localhost:5432 / law_news" -ForegroundColor Green

[doc("PostgreSQL Docker 컨테이너 중지")]
pg-stop:
    docker stop law-news-postgres
    Write-Host "  PostgreSQL 중지됨" -ForegroundColor Yellow

[doc("PostgreSQL 상태 확인")]
pg-status:
    docker ps --filter name=law-news-postgres

[doc("psql 접속 (docker exec)")]
pg-shell:
    docker exec -it law-news-postgres psql -U postgres -d law_news

# ============================================================
#  데이터베이스
# ============================================================

[doc("마이그레이션 생성 + 적용")]
migrate:
    {{manage}} makemigrations
    {{manage}} migrate

[doc("초기 데이터 시드 (키워드 + 언론사)")]
seed:
    {{manage}} seed_initial_data

[doc("DB 전체 초기화: 테이블 삭제 → 마이그레이션 → 시드")]
db-reset:
    {{manage}} flush --no-input
    {{manage}} migrate
    {{manage}} seed_initial_data
    Write-Host "`n  DB 초기화 완료" -ForegroundColor Green

[doc("분석 결과만 초기화 (기사는 유지, Analysis + CaseGroup 삭제 후 pending 리셋)")]
db-reset-analyses:
    {{manage}} shell -c "from analyses.models import Analysis, CaseGroup; Analysis.objects.all().delete(); CaseGroup.objects.all().delete(); from articles.models import Article; Article.objects.update(status='pending'); print('완료: Analysis/CaseGroup 삭제, 기사 pending 리셋')"
    Write-Host "  분석 초기화 완료. 'just analyze'로 재분석 시작하세요." -ForegroundColor Green

[doc("Django 관리자 계정 생성")]
superuser:
    {{manage}} createsuperuser

[doc("Django DB 셸")]
dbshell:
    {{manage}} dbshell

# ============================================================
#  뉴스 수집 & AI 분석
# ============================================================

[doc("뉴스 수집 (동기 실행)")]
crawl:
    {{manage}} crawl_news

[doc("대기 중인 기사 전체 AI 분석 (크롤링 없이, --limit N 으로 건수 제한)")]
analyze *args:
    {{manage}} run_analysis {{args}}

[doc("수집 → 분석 전체 파이프라인 (단발 실행)")]
pipeline:
    {{manage}} crawl_news
    {{manage}} run_analysis

[doc("기존 분석의 케이스 그룹 재매칭 (just regroup / just regroup --all / just regroup --dry-run)")]
regroup *args:
    {{manage}} regroup_analyses {{args}}

# ============================================================
#  모니터링 & 유틸리티
# ============================================================

[doc("현재 DB 통계 출력 (기사 / 분석 / 케이스그룹)")]
stats:
    {{manage}} shell -c "from articles.models import Article; from analyses.models import Analysis, CaseGroup; print(f'Articles: {Article.objects.count()} (pending={Article.objects.filter(status=\"pending\").count()}, analyzed={Article.objects.filter(status=\"analyzed\").count()})'); print(f'Analyses: {Analysis.objects.count()}'); print(f'CaseGroups: {CaseGroup.objects.count()}')"

[doc("Django 셸")]
shell:
    {{manage}} shell

[doc("프론트엔드 빌드 (프로덕션)")]
build:
    cd frontend; bun run build

[doc("프론트엔드 린트")]
lint:
    cd frontend; bun run lint

[doc("프론트엔드 의존성 설치")]
install-frontend:
    cd frontend; bun install

[doc("백엔드 의존성 설치 (uv.lock 기반)")]
install-backend:
    uv sync

[doc("전체 의존성 설치")]
install: install-backend install-frontend

[doc("전체 초기 셋업 (PostgreSQL 시작 → 의존성 → DB → 시드)")]
setup: pg-start install migrate seed
    Write-Host "`n  셋업 완료! 'just dev'로 서버를 시작하세요." -ForegroundColor Green

[doc("의존성 추가 (just add django-extensions)")]
add *packages:
    uv add {{packages}}

[doc("의존성 제거 (just remove django-extensions)")]
remove *packages:
    uv remove {{packages}}

[doc("uv.lock 갱신")]
lock:
    uv lock

[doc("API 문서 열기 (Swagger)")]
docs:
    Start-Process "http://localhost:8000/api/docs/"

[doc("Django Admin 열기")]
admin:
    Start-Process "http://localhost:8000/admin/"
