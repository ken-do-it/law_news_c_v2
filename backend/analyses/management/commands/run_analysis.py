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

_W = 60  # 제목 출력 최대 너비


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}초"
    return f"{seconds / 60:.1f}분"


def _eta(elapsed: float, done: int, total: int) -> str:
    if done == 0:
        return "?"
    remaining = (elapsed / done) * (total - done)
    return _fmt_time(remaining)


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
        from analyses.tasks import DailyQuotaExceededError, analyze_single_article

        limit = options["limit"]
        qs = Article.objects.filter(
            status__in=["pending", "analyzing"]
        ).order_by("collected_at")
        if limit:
            qs = qs[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("분석 대상 없음 (pending 기사가 없습니다)"))
            return

        pad = len(str(total))  # 숫자 자릿수 맞추기용
        self.stdout.write(f"\n분석 시작: {total}건")
        self.stdout.write("─" * 72)

        success = failed = 0
        start = time.time()

        for i, article in enumerate(qs.iterator(), 1):
            t0 = time.time()
            tag = ok = None
            try:
                ok = analyze_single_article(article)
                if ok:
                    success += 1
                    tag = self.style.SUCCESS("✓")
                else:
                    failed += 1
                    tag = self.style.ERROR("✗")
            except DailyQuotaExceededError as e:
                elapsed_item = time.time() - t0
                self.stdout.write(
                    self.style.WARNING(
                        f"\n[{i:{pad}d}/{total}] API 일일 한도 초과 — 분석 중단 ({elapsed_item:.1f}s): {e}"
                    )
                )
                self.stdout.write(
                    self.style.WARNING("기사 상태는 pending 유지. 내일 다시 실행하세요.")
                )
                break
            except Exception as e:
                article.status = "failed"
                article.retry_count += 1
                article.save(update_fields=["status", "retry_count"])
                failed += 1
                tag = self.style.ERROR("✗")
                short_title = f"[오류: {str(e)[:40]}]"
                elapsed_item = time.time() - t0
                self.stdout.write(
                    f"[{i:{pad}d}/{total}] {tag} {elapsed_item:5.1f}s │ {short_title}"
                )
                continue

            elapsed_item = time.time() - t0
            short_title = article.title[:_W].ljust(_W)
            self.stdout.write(
                f"[{i:{pad}d}/{total}] {tag} {elapsed_item:5.1f}s │ {short_title}"
            )

            # 10건마다 진행률 요약 줄 출력
            if i % 10 == 0:
                elapsed = time.time() - start
                avg = elapsed / i
                eta = _eta(elapsed, i, total)
                pct = i / total * 100
                self.stdout.write(
                    f"{'':>{pad + 10}}  "
                    f"진행 {pct:5.1f}% │ 평균 {avg:.1f}s/건 │ 남은시간 약 {eta}"
                )

        elapsed = time.time() - start
        self.stdout.write("─" * 72)
        self.stdout.write(
            self.style.SUCCESS(
                f"완료: {total}건 처리 — "
                f"성공 {success}  실패 {failed}  "
                f"(소요 {_fmt_time(elapsed)}, 평균 {elapsed/total:.1f}s/건)"
            )
        )
