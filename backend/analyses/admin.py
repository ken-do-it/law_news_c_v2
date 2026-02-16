from django.contrib import admin

from .models import Analysis, CaseGroup


@admin.register(CaseGroup)
class CaseGroupAdmin(admin.ModelAdmin):
    list_display = ("case_id", "name", "article_count", "created_at")
    search_fields = ("case_id", "name")
    readonly_fields = ("case_id",)

    def article_count(self, obj):
        return obj.analyses.count()

    article_count.short_description = "관련 기사 수"


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "article",
        "suitability",
        "case_category",
        "defendant",
        "stage",
        "case_group",
        "analyzed_at",
    )
    list_filter = ("suitability", "case_category", "stage", "case_group")
    search_fields = ("article__title", "defendant", "summary")
    readonly_fields = ("analyzed_at", "prompt_tokens", "completion_tokens")
    raw_id_fields = ("article",)
