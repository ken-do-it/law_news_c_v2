"""Runserver-only scheduler for crawling and analysis pipeline."""

from __future__ import annotations

import atexit
import logging
import os
import sys
from datetime import datetime, timedelta
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_started = False
_lock = Lock()


def _run_pipeline_job() -> None:
    """Execute one pipeline cycle: crawl -> analyze."""
    try:
        logger.info("[PIPELINE] run started")

        from articles.tasks import crawl_news

        # Synchronous execution (crawl -> analyze)
        new_count = crawl_news()
        logger.info("[PIPELINE] sync completed: new_count=%s", new_count)
    except Exception:
        logger.exception("[PIPELINE] run failed")


def start_runserver_scheduler() -> None:
    """
    Start APScheduler only for Django runserver.

    Guards:
    - Enabled flag in settings
    - runserver command only
    - RUN_MAIN=true to avoid autoreload double-start
    """
    global _scheduler, _started

    if not getattr(settings, "ENABLE_PIPELINE_ON_RUNSERVER", False):
        return

    if "runserver" not in sys.argv:
        return

    if os.environ.get("RUN_MAIN") != "true":
        return

    with _lock:
        if _started:
            return
        _started = True

    interval = int(getattr(settings, "PIPELINE_INTERVAL_MINUTES", 60))
    interval = max(1, interval)

    _scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)

    # 서버 완전 기동 후 30초 뒤 첫 실행 (AppConfig.ready() 블로킹 방지)
    _scheduler.add_job(
        _run_pipeline_job,
        trigger="date",
        run_date=datetime.now() + timedelta(seconds=30),
        id="news_pipeline_initial_job",
        replace_existing=True,
        max_instances=1,
    )

    # 이후 interval 분 간격으로 반복 실행
    _scheduler.add_job(
        _run_pipeline_job,
        trigger="interval",
        minutes=interval,
        id="news_pipeline_interval_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(minutes=interval),
    )
    _scheduler.start()
    logger.info(
        "[PIPELINE] scheduler started — 첫 실행: 30초 후 / 이후: %s분 간격", interval
    )

    def _shutdown() -> None:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)

    atexit.register(_shutdown)

