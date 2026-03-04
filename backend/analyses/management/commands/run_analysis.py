"""
management command: run_analysis

pending/failed 상태의 기사를 LLM으로 분석합니다 (크롤링 없이).
DB 초기화 후 전체 재분석 등에 사용.

사용법:
  uv run python manage.py run_analysis
  uv run python manage.py run_analysis --limit 100
"""

import sys
import time

from django.core.management.base import BaseCommand

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class Command(BaseCommand):
    help = "pending 기사 전체 LLM 분석 (크롤링 없음)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="최대 처리 건수 (0=전체)",
        )

    def handle(self, *args, **options):
        from articles.models import Article
        from analyses.tasks import analyze_single_article

        limit = options["limit"]
        qs = Article.objects.filter(
            status__in=["pending", "analyzing"]
        ).order_by("collected_at")
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"분석 대상: {total}건 시작")

        success = failed = 0
        start = time.time()

        for i, article in enumerate(qs.iterator(), 1):
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
                failed += 1
                self.stdout.write(f"  [오류] {article.title[:50]}: {e}")

            if i % 50 == 0:
                elapsed = time.time() - start
                rate = i / elapsed
                remaining = (total - i) / rate if rate > 0 else 0
                self.stdout.write(
                    f"  {i}/{total} 완료 "
                    f"(성공 {success} / 실패 {failed}) "
                    f"— 남은 시간 약 {remaining/60:.0f}분"
                )

        elapsed = time.time() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"\n완료: 전체 {total}건 — 성공 {success}, 실패 {failed} "
                f"(소요 {elapsed/60:.1f}분)"
            )
        )
