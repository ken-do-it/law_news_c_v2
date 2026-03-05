"""
management command: crawl_news

활성 키워드로 네이버 뉴스를 수집하고 DB에 저장합니다.
스케줄러 없이 단독 실행 가능 (just crawl).

사용법:
  uv run python manage.py crawl_news
"""

import sys

from django.core.management.base import BaseCommand

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class Command(BaseCommand):
    help = "활성 키워드로 네이버 뉴스 수집 (스케줄러 없이 단독 실행)"

    def handle(self, *args, **options):
        from articles.tasks import crawl_news

        self.stdout.write("뉴스 수집 시작...")
        n = crawl_news()
        self.stdout.write(self.style.SUCCESS(f"수집 완료: {n}건"))
