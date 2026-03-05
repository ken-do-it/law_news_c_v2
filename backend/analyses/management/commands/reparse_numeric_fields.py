"""
기존 분석 결과의 damage_amount_num / victim_count_num 을 재파싱합니다.

"수만 명 이상", "수백억" 처럼 숫자가 없는 한자어 수사 표현이
parse 함수 개선 전에는 None 으로 저장됐을 수 있으므로
이 커맨드로 전체 or 일부를 다시 계산합니다.

사용:
  uv run python manage.py reparse_numeric_fields          # 전체 재파싱
  uv run python manage.py reparse_numeric_fields --null-only  # None 인 것만
"""

from django.core.management.base import BaseCommand
from analyses.models import Analysis
from analyses.tasks import parse_damage_amount, parse_victim_count


class Command(BaseCommand):
    help = "damage_amount_num / victim_count_num 재파싱"

    def add_arguments(self, parser):
        parser.add_argument(
            "--null-only",
            action="store_true",
            help="현재 None 인 레코드만 재파싱 (기본: 전체)",
        )

    def handle(self, *args, **options):
        qs = Analysis.objects.exclude(damage_amount="", victim_count="")

        if options["null_only"]:
            qs = qs.filter(
                damage_amount_num__isnull=True,
                victim_count_num__isnull=True,
            )

        total = qs.count()
        self.stdout.write(f"Target: {total} records")

        updated = 0
        for a in qs.iterator(chunk_size=500):
            new_damage = parse_damage_amount(a.damage_amount or "")
            new_victim = parse_victim_count(a.victim_count or "")

            if new_damage != a.damage_amount_num or new_victim != a.victim_count_num:
                a.damage_amount_num = new_damage
                a.victim_count_num = new_victim
                a.save(update_fields=["damage_amount_num", "victim_count_num"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done: {updated}/{total} updated"))
