"""
management command: regroup_analyses

DB에 이미 저장된 Analysis 레코드에 새 그룹핑 로직(기사 제목 키워드 매칭)을 소급 적용.

사용법:
  # case_group이 null인 분석만 재그룹 (기본)
  just regroup

  # 모든 분석 재그룹 (기존 그룹 포함)
  just regroup --all

  # 드라이런 (실제 저장 없이 결과 확인)
  just regroup --dry-run
"""

import sys

from django.core.management.base import BaseCommand

# Windows cp1252 터미널에서도 한글 출력 가능하도록
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from analyses.models import Analysis
from analyses.tasks import find_or_create_case_group


class Command(BaseCommand):
    help = "기존 분석 결과에 새 케이스 그룹 매칭 로직을 소급 적용"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            dest="regroup_all",
            help="case_group이 있는 분석도 포함하여 전체 재그룹 (기본: null인 것만)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 매칭 결과만 출력",
        )

    def handle(self, *args, **options):
        regroup_all = options["regroup_all"]
        dry_run = options["dry_run"]

        qs = (
            Analysis.objects.select_related("article", "case_group")
            .order_by("analyzed_at")
        )
        if not regroup_all:
            qs = qs.filter(case_group__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("재그룹 대상 없음."))
            return

        mode = "[드라이런] " if dry_run else ""
        self.stdout.write(f"{mode}재그룹 대상: {total}건 (--all={regroup_all})")

        grouped = 0
        skipped = 0

        for i, analysis in enumerate(qs.iterator(), 1):
            article = analysis.article
            old_group = analysis.case_group

            # 새 그룹 매칭 시도
            new_group = find_or_create_case_group(
                case_name="",          # 이미 분석된 기사는 case_name 재추출 없이
                article_title=article.title,   # 제목 키워드 매칭만 사용
                article_date=article.published_at.date(),
            )

            # 변경 없으면 스킵
            if new_group is None or new_group == old_group:
                skipped += 1
                if i % 100 == 0:
                    self.stdout.write(f"  {i}/{total} 처리 중... (변경 {grouped}건)")
                continue

            old_name = old_group.name if old_group else "null"
            self.stdout.write(
                f"  [{analysis.pk}] '{article.title[:50]}'\n"
                f"    {old_name} → {new_group.name}"
            )

            if not dry_run:
                analysis.case_group = new_group
                analysis.save(update_fields=["case_group"])

            grouped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n완료: 전체 {total}건 중 {grouped}건 그룹 변경"
                + (" (저장 안 함 — dry-run)" if dry_run else " 저장 완료")
            )
        )
