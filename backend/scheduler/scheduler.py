"""APScheduler 기반 파이프라인 자동 실행 (Redis 불필요)"""

import logging
import threading
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_state: dict = {
    "is_running": False,
    "last_run_at": None,  # ISO 8601 문자열 or None
}
_scheduler = None
_interval_minutes: int = 60


def _run_pipeline() -> None:
    """파이프라인 실행 — APScheduler 백그라운드 스레드에서 호출됨"""
    with _lock:
        if _state["is_running"]:
            logger.warning("파이프라인이 이미 실행 중 — 건너뜀")
            return
        _state["is_running"] = True

    try:
        logger.info("=== 자동 파이프라인 시작 ===")

        from articles.tasks import crawl_news_sync
        from analyses.tasks import analyze_single_article
        from articles.models import Article

        # STEP 1: 수집
        new_count = crawl_news_sync()
        logger.info("새 기사 %d건 수집됨", new_count)

        # STEP 2: 분석
        pending = Article.objects.filter(
            status__in=["pending", "analyzing"]
        ).order_by("collected_at")

        success = failed = 0
        for article in pending:
            try:
                ok = analyze_single_article(article)
                if ok:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                article.status = "failed"
                article.retry_count += 1
                article.save(update_fields=["status", "retry_count"])
                logger.error("분석 실패 [%s]: %s", article.title[:50], e)
                failed += 1

        logger.info("파이프라인 완료 — 성공 %d, 실패 %d", success, failed)
        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.error("파이프라인 오류: %s", e, exc_info=True)

    finally:
        _state["is_running"] = False

        # 완료 후 _interval_minutes 뒤 다음 실행 예약
        if _scheduler and _scheduler.running:
            next_run = datetime.now(timezone.utc) + timedelta(minutes=_interval_minutes)
            try:
                from apscheduler.triggers.date import DateTrigger
                _scheduler.reschedule_job("pipeline", trigger=DateTrigger(run_date=next_run))
                logger.info("다음 파이프라인 예약: %s", next_run.isoformat())
            except Exception as e:
                logger.error("다음 실행 예약 실패: %s", e)


def start_scheduler() -> None:
    global _scheduler, _interval_minutes

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.date import DateTrigger
    except ImportError:
        logger.warning("apscheduler 미설치 — 자동 스케줄링 비활성화")
        return

    from django.conf import settings
    _interval_minutes = int(getattr(settings, "CRAWL_INTERVAL_MINUTES", 60))

    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    # 서버 시작 10초 후 첫 실행 (Django 초기화 완료 대기)
    first_run = datetime.now(timezone.utc) + timedelta(seconds=10)
    _scheduler.add_job(
        _run_pipeline,
        trigger=DateTrigger(run_date=first_run),
        id="pipeline",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("자동 스케줄러 시작 — 수집 주기 %d분, 첫 실행 10초 후", _interval_minutes)


def get_scheduler_state() -> dict:
    """stats API에서 호출하여 스케줄러 상태 반환"""
    next_run_at = None
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("pipeline")
        if job and job.next_run_time:
            next_run_at = job.next_run_time.isoformat()

    return {
        "is_running": _state["is_running"],
        "last_run_at": _state["last_run_at"],
        "next_run_at": next_run_at,
    }
