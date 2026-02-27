# Data migration: Copy review fields from Analysis to CaseGroup

from django.db import migrations


def backfill_casegroup_review(apps, schema_editor):
    CaseGroup = apps.get_model("analyses", "CaseGroup")
    Analysis = apps.get_model("analyses", "Analysis")

    for cg in CaseGroup.objects.all():
        # Prefer analysis with review_completed=True, else most recent
        best = (
            Analysis.objects.filter(case_group=cg, review_completed=True)
            .order_by("-analyzed_at")
            .first()
        )
        if not best:
            best = Analysis.objects.filter(case_group=cg).order_by("-analyzed_at").first()
        if best:
            cg.review_completed = best.review_completed
            cg.client_suitability = best.client_suitability
            cg.accepted = best.accepted
            cg.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("analyses", "0006_add_casegroup_review_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_casegroup_review, noop),
    ]
