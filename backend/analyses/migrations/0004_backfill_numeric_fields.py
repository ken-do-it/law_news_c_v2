"""
Data Migration: 기존 Analysis 레코드의 damage_amount / victim_count 텍스트를
숫자 컬럼(damage_amount_num / victim_count_num)으로 소급 파싱.
"""

import re

from django.db import migrations


# ── 파싱 함수 (tasks.py 복사본 — Migration은 앱 코드 import 불가) ──

def _parse_damage_amount(text):
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if re.search(r"미상|불명|알\s*수\s*없|불확실|확인\s*안\s*됨|확인\s*불가", text):
        return None
    if not re.search(r"\d", text):
        return None
    try:
        t = re.sub(r",", "", text)
        total = 0
        m = re.search(r"([\d.]+)\s*조", t)
        if m:
            total += int(float(m.group(1)) * 1_000_000_000_000)
        m = re.search(r"([\d.]+)\s*억", t)
        if m:
            total += int(float(m.group(1)) * 100_000_000)
        m = re.search(r"([\d.]+)\s*천\s*(?:만|원)", t)
        if m:
            unit = 10_000 if "만" in t[m.end() - 1:m.end() + 1] else 1_000
            total += int(float(m.group(1)) * unit)
        m = re.search(r"([\d.]+)\s*만", t)
        if m:
            total += int(float(m.group(1)) * 10_000)
        if total == 0:
            m = re.search(r"([\d.]+)\s*원", t)
            if m:
                total += int(float(m.group(1)))
        return total if total > 0 else None
    except (ValueError, OverflowError):
        return None


def _parse_victim_count(text):
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if re.search(r"미상|불명|알\s*수\s*없|불확실|확인\s*안\s*됨|확인\s*불가", text):
        return None
    if not re.search(r"\d", text):
        return None
    try:
        t = re.sub(r",", "", text)
        total = 0
        m = re.search(r"([\d.]+)\s*만", t)
        if m:
            total += int(float(m.group(1)) * 10_000)
        m = re.search(r"([\d.]+)\s*천", t)
        if m:
            total += int(float(m.group(1)) * 1_000)
        m = re.search(r"([\d.]+)\s*백", t)
        if m:
            total += int(float(m.group(1)) * 100)
        if total == 0:
            m = re.search(r"(\d+)", t)
            if m:
                total += int(m.group(1))
        return total if total > 0 else None
    except (ValueError, OverflowError):
        return None


# ── 마이그레이션 함수 ──

def backfill_numeric_fields(apps, schema_editor):
    Analysis = apps.get_model("analyses", "Analysis")
    to_update = []
    for a in Analysis.objects.all():
        a.damage_amount_num = _parse_damage_amount(a.damage_amount)
        a.victim_count_num = _parse_victim_count(a.victim_count)
        to_update.append(a)
    if to_update:
        Analysis.objects.bulk_update(to_update, ["damage_amount_num", "victim_count_num"])


class Migration(migrations.Migration):

    dependencies = [
        ("analyses", "0003_analysis_numeric_sort_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_numeric_fields, migrations.RunPython.noop),
    ]
