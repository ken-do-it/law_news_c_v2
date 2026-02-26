import os
import sys

from django.apps import AppConfig


class SchedulerConfig(AppConfig):
    name = "scheduler"
    verbose_name = "자동 스케줄러"

    def ready(self):
        # Django dev 서버는 auto-reloader 때문에 프로세스가 2개 뜸.
        # 부모 프로세스(파일 감시용)에서는 스케줄러를 시작하지 않음.
        # 자식 프로세스(실제 요청 처리)에서만 시작 → RUN_MAIN='true'
        # 프로덕션(gunicorn 등)에서는 RUN_MAIN 미설정 → 그대로 시작
        is_dev_parent = (
            os.environ.get("RUN_MAIN") is None
            and any("runserver" in a for a in sys.argv)
        )
        if is_dev_parent:
            return

        from .scheduler import start_scheduler
        start_scheduler()
