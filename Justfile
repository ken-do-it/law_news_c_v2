# ============================================================
#  법률 분쟁 사건 자동 발굴 시스템 — Justfile
# ============================================================

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

python     := ".\\.venv\\Scripts\\python.exe"
manage     := python + " backend/manage.py"
celery     := ".\\.venv\\Scripts\\celery.exe"
celery_abs := justfile_directory() + "\\.venv\\Scripts\\celery.exe"

# ── 기본: 사용 가능한 명령어 목록 ─────────────────────────
[doc("사용 가능한 명령어 목록")]
default:
    @just --list --unsorted

# ============================================================
#  서버
# ============================================================

[doc("백엔드 + 프론트엔드 동시 실행")]
dev:
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '{{justfile_directory()}}'; {{manage}} runserver"
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
#  데이터베이스
# ============================================================

[doc("마이그레이션 생성 + 적용")]
migrate:
    {{manage}} makemigrations
    {{manage}} migrate

[doc("초기 데이터 시드 (키워드 + 언론사)")]
seed:
    {{manage}} seed_initial_data

[doc("DB 초기화: 삭제 → 마이그레이션 → 시드")]
db-reset:
    {{python}} scripts/reset_db.py
    {{manage}} migrate
    {{manage}} seed_initial_data
    Write-Host "`n  DB 초기화 완료" -ForegroundColor Green

[doc("Django 관리자 계정 생성")]
superuser:
    {{manage}} createsuperuser

[doc("Django DB 셸")]
dbshell:
    {{manage}} dbshell

# ============================================================
#  뉴스 수집 & AI 분석
# ============================================================

[doc("뉴스 수집 (Celery 없이 동기 실행)")]
crawl:
    {{python}} scripts/crawl_now.py

[doc("대기 중인 기사 AI 분석 (Celery 없이 동기 실행)")]
analyze:
    {{python}} scripts/analyze_now.py

[doc("수집 → 분석 전체 파이프라인")]
pipeline:
    {{python}} scripts/pipeline.py

[doc("특정 기사 재분석 (just reanalyze 42)")]
reanalyze article_id:
    {{python}} scripts/reanalyze.py {{article_id}}

# ============================================================
#  Celery (Redis 필요)
# ============================================================

[doc("Celery 워커 실행")]
worker:
    cd backend; & "{{celery_abs}}" -A config worker -l info -P solo

[doc("Celery Beat 스케줄러 실행")]
beat:
    cd backend; & "{{celery_abs}}" -A config beat -l info

[doc("Celery 워커 + Beat 동시 실행")]
celery:
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '{{justfile_directory()}}\backend'; & '{{celery_abs}}' -A config worker -l info -P solo"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '{{justfile_directory()}}\backend'; & '{{celery_abs}}' -A config beat -l info"
    Write-Host "`n  Celery Worker + Beat 실행됨" -ForegroundColor Cyan

# ============================================================
#  모니터링 & 유틸리티
# ============================================================

[doc("현재 시스템 통계 출력")]
stats:
    {{python}} scripts/show_stats.py

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

[doc("백엔드 의존성 설치")]
install-backend:
    uv pip install -e . --python {{python}}

[doc("전체 의존성 설치")]
install: install-backend install-frontend

[doc("전체 초기 셋업 (의존성 → DB → 시드)")]
setup: install migrate seed
    Write-Host "`n  셋업 완료! 'just dev'로 서버를 시작하세요." -ForegroundColor Green

[doc("API 문서 열기 (Swagger)")]
docs:
    Start-Process "http://localhost:8000/api/docs/"

[doc("Django Admin 열기")]
admin:
    Start-Process "http://localhost:8000/admin/"

[doc("엑셀 내보내기")]
export:
    {{python}} scripts/export_excel.py
