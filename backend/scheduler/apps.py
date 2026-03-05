import os
import sys

from django.apps import AppConfig

# 스케줄러를 시작하지 않을 관리 명령어 목록.
# 일회성 작업 커맨드에서는 백그라운드 스케줄러가 불필요하고 충돌을 유발한다.
_NO_SCHEDULER_CMDS = {
    "shell", "migrate", "makemigrations", "test",
    "createsuperuser", "flush", "dbshell", "collectstatic",
    "check", "showmigrations", "dumpdata", "loaddata",
    "run_analysis", "crawl_news", "seed_initial_data", "regroup_analyses",
}


class SchedulerConfig(AppConfig):
    name = "scheduler"
    verbose_name = "자동 스케줄러"

    def ready(self):
        argv0 = sys.argv[0] if sys.argv else ""
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""

        is_manage_py = argv0.endswith("manage.py") or "manage.py" in argv0

        if is_manage_py:
            # 관리 명령어(shell, crawl_news, run_analysis 등)에서는 미시작
            if cmd in _NO_SCHEDULER_CMDS:
                return
            # runserver dev auto-reloader 부모 프로세스에서는 미시작
            if cmd == "runserver" and os.environ.get("RUN_MAIN") is None:
                return
        else:
            # 직접 스크립트(scripts/*.py) 또는 WSGI/ASGI 서버 실행
            # DJANGO_SCHEDULER_ENABLED=1 로 명시적으로 활성화한 경우에만 시작
            # (granian/gunicorn 실행 시 환경변수로 설정)
            if not os.environ.get("DJANGO_SCHEDULER_ENABLED"):
                return

        from .scheduler import start_scheduler
        start_scheduler()
