"""APScheduler 기반 수집/분석 자동 실행 (Redis 불필요)

- crawl  잡: CRAWL_INTERVAL_MINUTES 마다 뉴스 수집
- analyze 잡: ANALYSIS_INTERVAL_MINUTES 마다 pending 기사 분석
두 잡은 독립 실행 (서로 블로킹 없음).
"""

import logging
import threading
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_crawl_lock = threading.Lock()
_analyze_lock = threading.Lock()

_state: dict = {
    "is_running": False,       # 분석 잡 실행 중 여부 (대시보드 표시용)
    "last_run_at": None,       # 마지막 분석 완료 시각
    "quota_error": None,       # 일일 한도 초과 안내 메시지 (None이면 정상)
}

_scheduler = None
_crawl_interval_minutes: int = 60
_analysis_interval_minutes: int = 5


# ──────────────────────────────────────────────────────────
# 수집 잡
# ──────────────────────────────────────────────────────────

def _run_crawl() -> None:
    """뉴스 수집 — 60분마다 실행"""
    if not _crawl_lock.acquire(blocking=False):
        logger.warning("수집이 이미 실행 중 — 건너뜀")
        return
    try:
        logger.info("=== 뉴스 수집 시작 ===")
        from articles.tasks import crawl_news
        new_count = crawl_news()
        logger.info("수집 완료: %d건", new_count)
    except Exception as e:
        logger.error("수집 오류: %s", e, exc_info=True)
    finally:
        _crawl_lock.release()
        _reschedule("crawl", _crawl_interval_minutes)


# ──────────────────────────────────────────────────────────
# 분석 잡
# ──────────────────────────────────────────────────────────

def _run_analyze() -> None:
    """pending 기사 분석 — 5분마다 실행"""
    if not _analyze_lock.acquire(blocking=False):
        logger.warning("분석이 이미 실행 중 — 건너뜀")
        return

    _state["is_running"] = True
    try:
        from analyses.tasks import analyze_single_article
        from articles.models import Article

        pending = Article.objects.filter(
            status__in=["pending", "analyzing"]
        ).order_by("collected_at")

        total = pending.count()
        if total == 0:
            logger.info("분석 대상 없음 — 건너뜀")
            return

        logger.info("=== 분석 시작: %d건 ===", total)
        success = failed = 0
        for article in pending.iterator():
            try:
                ok = analyze_single_article(article)
                if ok:
                    success += 1
                    _state["quota_error"] = None  # 성공하면 에러 상태 해제
                else:
                    failed += 1
            except Exception as e:
                from analyses.tasks import DailyQuotaExceededError, _is_daily_quota_error
                if isinstance(e, DailyQuotaExceededError):
                    if _is_daily_quota_error(e):
                        _state["quota_error"] = "Gemini 일일 요청 한도 초과 — 내일 오전 9시(KST) 이후 자동 재개됩니다."
                    else:
                        _state["quota_error"] = "Gemini API 분당 요청 한도 초과 — 5분 후 자동 재개됩니다."
                    logger.warning("API 한도 초과 — 분석 중단: %s", _state["quota_error"])
                    break
                article.status = "failed"
                article.retry_count += 1
                article.save(update_fields=["status", "retry_count"])
                logger.error("분석 실패 [%s]: %s", article.title[:50], e)
                failed += 1

        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("분석 완료 — 성공 %d, 실패 %d", success, failed)

    except Exception as e:
        logger.error("분석 오류: %s", e, exc_info=True)
    finally:
        _state["is_running"] = False
        _analyze_lock.release()
        _reschedule("analyze", _analysis_interval_minutes)


# ──────────────────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────────────────

def _reschedule(job_id: str, minutes: int) -> None:
    """잡 완료 후 다음 실행 예약.

    DateTrigger 잡은 실행 후 스케줄러에서 자동 제거되므로
    reschedule_job 대신 add_job(replace_existing=True)으로 재등록한다.
    """
    if not (_scheduler and _scheduler.running):
        return
    next_run = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    job_func = _run_crawl if job_id == "crawl" else _run_analyze
    try:
        from apscheduler.triggers.date import DateTrigger
        _scheduler.add_job(
            job_func,
            trigger=DateTrigger(run_date=next_run),
            id=job_id,
            replace_existing=True,
            max_instances=1,
        )
        logger.info("다음 %s 예약: %s", job_id, next_run.isoformat())
    except Exception as e:
        logger.error("%s 재예약 실패: %s", job_id, e)


# ──────────────────────────────────────────────────────────
# 스케줄러 시작
# ──────────────────────────────────────────────────────────

def start_scheduler() -> None:
    global _scheduler, _crawl_interval_minutes, _analysis_interval_minutes

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.date import DateTrigger
    except ImportError:
        logger.warning("apscheduler 미설치 — 자동 스케줄링 비활성화")
        return

    from django.conf import settings
    _crawl_interval_minutes = int(getattr(settings, "CRAWL_INTERVAL_MINUTES", 60))
    _analysis_interval_minutes = int(getattr(settings, "ANALYSIS_INTERVAL_MINUTES", 5))

    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    now = datetime.now(timezone.utc)

    # 수집: 10초 후 첫 실행
    _scheduler.add_job(
        _run_crawl,
        trigger=DateTrigger(run_date=now + timedelta(seconds=10)),
        id="crawl",
        replace_existing=True,
        max_instances=1,
    )

    # 분석: 15초 후 첫 실행 (수집 직후 바로 처리 시작)
    _scheduler.add_job(
        _run_analyze,
        trigger=DateTrigger(run_date=now + timedelta(seconds=15)),
        id="analyze",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        "스케줄러 시작 — 수집 %d분, 분석 %d분 주기",
        _crawl_interval_minutes,
        _analysis_interval_minutes,
    )


# ──────────────────────────────────────────────────────────
# 상태 조회 (대시보드 API)
# ──────────────────────────────────────────────────────────

def get_scheduler_state() -> dict:
    next_run_at = None
    if _scheduler and _scheduler.running:
        # 분석 잡의 다음 실행 시각을 대표값으로 표시
        job = _scheduler.get_job("analyze")
        if job and job.next_run_time:
            next_run_at = job.next_run_time.isoformat()

    return {
        "is_running": _state["is_running"],
        "last_run_at": _state["last_run_at"],
        "next_run_at": next_run_at,
        "quota_error": _state.get("quota_error"),
    }
