from datetime import date, timedelta

from django.db.models import Count, Sum
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .export import export_analyses_to_excel
from .models import Analysis, CaseGroup
from .serializers import (
    AnalysisDetailSerializer,
    AnalysisListSerializer,
    CaseGroupSerializer,
)


class AnalysisFilter(filters.FilterSet):
    suitability = filters.ChoiceFilter(choices=Analysis.SUITABILITY_CHOICES)
    case_category = filters.CharFilter(lookup_expr="icontains")
    stage = filters.ChoiceFilter(choices=Analysis.STAGE_CHOICES)
    date_from = filters.DateFilter(field_name="article__published_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="article__published_at", lookup_expr="lte")
    case_group = filters.NumberFilter(field_name="case_group__id")

    class Meta:
        model = Analysis
        fields = ["suitability", "case_category", "stage", "case_group"]


class AnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Analysis.objects.select_related("article", "article__source", "case_group").all()
    )
    filterset_class = AnalysisFilter
    search_fields = ["article__title", "defendant", "summary", "case_category"]
    ordering_fields = ["analyzed_at", "article__published_at", "suitability"]
    ordering = ["-analyzed_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AnalysisDetailSerializer
        return AnalysisListSerializer

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """대시보드 통계 데이터"""
        today = date.today()
        week_ago = today - timedelta(days=7)

        # 오늘 수집된 기사 수
        from articles.models import Article

        today_collected = Article.objects.filter(
            collected_at__date=today
        ).count()

        # 오늘 High 적합 건수
        today_high = Analysis.objects.filter(
            analyzed_at__date=today,
            suitability="High",
        ).count()

        # 전체 분석 완료 건수
        total_analyzed = Analysis.objects.count()

        # 이번 달 LLM 비용 추정 (GPT-4o 기준)
        monthly_tokens = Analysis.objects.filter(
            analyzed_at__month=today.month,
            analyzed_at__year=today.year,
        ).aggregate(
            total_prompt=Sum("prompt_tokens"),
            total_completion=Sum("completion_tokens"),
        )
        prompt_t = monthly_tokens["total_prompt"] or 0
        completion_t = monthly_tokens["total_completion"] or 0
        # GPT-4o 가격: $2.50/1M input, $10.00/1M output → KRW 환산 (1400원/달러)
        monthly_cost = round(
            (prompt_t * 2.5 / 1_000_000 + completion_t * 10.0 / 1_000_000) * 1400
        )

        # 적합도 분포
        suit_dist = (
            Analysis.objects.values("suitability")
            .annotate(value=Count("id"))
            .order_by("suitability")
        )
        suitability_distribution = [
            {"name": s["suitability"], "value": s["value"]} for s in suit_dist
        ]

        # 사건 분야별 분포 (상위 10개)
        cat_dist = (
            Analysis.objects.values("case_category")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        category_distribution = [
            {"name": c["case_category"], "count": c["count"]} for c in cat_dist
        ]

        # 주간 추이
        weekly_trend = []
        for i in range(7):
            d = today - timedelta(days=6 - i)
            total = Analysis.objects.filter(analyzed_at__date=d).count()
            high = Analysis.objects.filter(analyzed_at__date=d, suitability="High").count()
            medium = Analysis.objects.filter(analyzed_at__date=d, suitability="Medium").count()
            weekly_trend.append({
                "date": d.isoformat(),
                "total": total,
                "high": high,
                "medium": medium,
            })

        return Response({
            "today_collected": today_collected,
            "today_high": today_high,
            "total_analyzed": total_analyzed,
            "monthly_cost": monthly_cost,
            "suitability_distribution": suitability_distribution,
            "category_distribution": category_distribution,
            "weekly_trend": weekly_trend,
        })

    @action(detail=False, methods=["get"])
    def export(self, request):
        """엑셀 파일 다운로드"""
        queryset = self.filter_queryset(self.get_queryset())
        buf = export_analyses_to_excel(queryset)

        response = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="analyses_export.xlsx"'
        return response


class CaseGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CaseGroup.objects.prefetch_related("analyses").all()
    serializer_class = CaseGroupSerializer
    search_fields = ["case_id", "name"]
    ordering = ["-created_at"]
