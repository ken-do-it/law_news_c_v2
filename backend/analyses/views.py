"""
analyses/views.py — 분석 결과 API 뷰 모듈

이 모듈은 LLM 분석 결과(Analysis)와 사건 그룹(CaseGroup)에 대한
REST API 엔드포인트를 제공합니다.

주요 기능:
  - 분석 결과 목록 조회 / 상세 조회 (필터·검색·정렬 지원)
  - 대시보드 통계 API (적합도 분포, 사건 유형 분포, 주간 추이 등)
  - 분석 결과 엑셀 다운로드
  - 사건 그룹 목록 조회 / 상세 조회
"""

from datetime import date, timedelta

from django.db.models import Count, Q, Subquery, OuterRef, Sum
from django.http import HttpResponse
from django_filters import rest_framework as filters  # django-filter 라이브러리의 DRF 통합
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .export import export_analyses_to_excel  # 엑셀 내보내기 유틸리티
from .models import Analysis, CaseGroup
from .serializers import (
    AnalysisDetailSerializer,   # 분석 상세 조회용 시리얼라이저
    AnalysisListSerializer,     # 분석 목록 조회용 시리얼라이저
    AnalysisReviewSerializer,   # 심사 필드 PATCH용 시리얼라이저
    CaseGroupSerializer,        # 사건 그룹 시리얼라이저
)


# ──────────────────────────────────────────────
# 분석 결과 필터셋 (django-filter)
# ──────────────────────────────────────────────
class AnalysisFilter(filters.FilterSet):
    """
    분석 결과 필터링을 위한 FilterSet 클래스.

    프론트엔드에서 쿼리 파라미터로 필터링 조건을 전달하면
    자동으로 QuerySet에 반영됩니다.

    지원하는 필터:
      - suitability: 적합도 (High / Medium / Low) — 정확히 일치
      - case_category: 사건 유형 — 부분 문자열 포함 검색 (icontains)
      - stage: 소송 단계 — 정확히 일치
      - date_from: 기사 발행일 시작 범위 (이상, >=)
      - date_to: 기사 발행일 끝 범위 (이하, <=)
      - case_group: 사건 그룹 ID — 정확히 일치

    사용 예시:
      GET /api/analyses/?suitability=High&date_from=2026-02-01
      GET /api/analyses/?case_category=개인정보&stage=소송중
    """

    # 적합도 필터 — 쉼표 구분으로 복수 선택 가능 (예: ?suitability=High,Medium)
    suitability = filters.BaseInFilter(field_name="suitability")

    # 사건 유형 필터 — 부분 문자열 검색 (예: "개인" → "개인정보" 매칭)
    case_category = filters.CharFilter(lookup_expr="icontains")

    # 소송 단계 필터 — Analysis 모델에 정의된 선택지만 허용
    stage = filters.ChoiceFilter(choices=Analysis.STAGE_CHOICES)

    # 기사 발행일 범위 필터 — 연관된 Article 모델의 published_at 필드를 참조
    date_from = filters.DateFilter(field_name="article__published_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="article__published_at", lookup_expr="lte")

    # 사건 그룹 ID 필터 — 특정 사건 그룹에 속한 분석 결과만 조회
    case_group = filters.NumberFilter(field_name="case_group__id")

    # 법적 분쟁 관련 여부 필터 — 기본값 True (무관 기사 숨김)
    is_relevant = filters.BooleanFilter(field_name="is_relevant")

    # 심사 완료 여부 필터 — ?review_completed=true / false
    review_completed = filters.BooleanFilter(field_name="review_completed")

    # 통과 여부 필터 — ?accepted=true / false
    accepted = filters.BooleanFilter(field_name="accepted")

    # 로앤굿 심사결과 필터 — 쉼표 구분 복수 선택 가능 (예: ?client_suitability=High,Medium)
    client_suitability = filters.BaseInFilter(field_name="client_suitability")

    class Meta:
        model = Analysis
        fields = [
            "suitability", "case_category", "stage", "case_group",
            "is_relevant", "review_completed", "accepted", "client_suitability",
        ]


# ──────────────────────────────────────────────
# 분석 결과 ViewSet (읽기 전용)
# ──────────────────────────────────────────────
class AnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    분석 결과(Analysis) API 엔드포인트.

    ReadOnlyModelViewSet을 상속하되 심사 필드에 한해 PATCH를 허용합니다.
    (생성/전체수정/삭제는 LLM 분석 태스크에서 자동으로 처리)

    엔드포인트:
      GET   /api/analyses/          → 분석 결과 목록 (페이지네이션, 필터, 검색, 정렬)
      GET   /api/analyses/{id}/     → 분석 결과 상세
      PATCH /api/analyses/{id}/     → 심사 필드 업데이트 (review_completed, client_suitability, accepted)
      GET   /api/analyses/stats/    → 대시보드 통계 데이터
      GET   /api/analyses/export/   → 엑셀 파일 다운로드
    """

    http_method_names = ["get", "patch", "head", "options"]

    # QuerySet 정의 — select_related로 관련 모델을 JOIN하여 N+1 쿼리 방지
    # article: 기사 정보, article__source: 매체 정보, case_group: 사건 그룹
    queryset = (
        Analysis.objects.select_related("article", "article__source", "case_group").all()
    )

    def get_queryset(self):
        """
        is_relevant 파라미터가 없으면 기본적으로 관련 기사만 표시.
        ?include_irrelevant=true 를 전달하면 무관 기사도 포함.
        ?group_by_case=true 를 전달하면 같은 사건 그룹의 기사를 하나로 묶어 표시.
        """
        qs = super().get_queryset()
        # 프론트에서 include_irrelevant=true 보내면 전체 표시
        if self.request.query_params.get("include_irrelevant") == "true":
            pass
        elif "is_relevant" not in self.request.query_params:
            qs = qs.filter(is_relevant=True)

        # 사건 그룹별 대표 기사만 표시 (목록 액션에서만)
        if (
            self.request.query_params.get("group_by_case") == "true"
            and self.action == "list"
        ):
            # 각 case_group 내에서 가장 최근 기사의 ID
            latest_per_group = (
                Analysis.objects.filter(
                    case_group=OuterRef("case_group"),
                    is_relevant=True,
                )
                .order_by("-article__published_at")
                .values("id")[:1]
            )
            # case_group이 있는 분석 중 대표만 + case_group이 없는 분석 전부
            qs = qs.filter(
                Q(case_group__isnull=True)
                | Q(id=Subquery(latest_per_group))
            )

        # related_count 어노테이션 (같은 사건 그룹의 다른 기사 수)
        qs = qs.annotate(
            related_count=Count(
                "case_group__analyses",
                filter=Q(case_group__analyses__is_relevant=True),
            )
        )

        return qs

    # 필터셋 클래스 연결 — 위에서 정의한 AnalysisFilter 사용
    filterset_class = AnalysisFilter

    # 검색 필드 — ?search= 파라미터로 텍스트 검색 시 대상 필드들
    # 기사 제목, 피고(피청구인), AI 요약, 사건 유형에서 검색
    search_fields = [
        "article__title", "defendant", "summary", "case_category",
        "case_group__case_id", "case_group__name",
    ]

    # 정렬 가능 필드 — ?ordering= 파라미터로 정렬 기준 변경 가능
    ordering_fields = ["analyzed_at", "article__published_at", "suitability"]

    # 기본 정렬 — 분석 완료일 기준 최신순
    ordering = ["-analyzed_at"]

    def get_serializer_class(self):
        """
        요청 액션에 따라 시리얼라이저를 동적으로 선택합니다.

        - retrieve (상세 조회): AnalysisDetailSerializer
        - partial_update (PATCH): AnalysisReviewSerializer
        - list (목록 조회): AnalysisListSerializer
        """
        if self.action == "retrieve":
            return AnalysisDetailSerializer
        if self.action == "partial_update":
            return AnalysisReviewSerializer
        return AnalysisListSerializer

    def partial_update(self, request, *args, **kwargs):
        """심사 필드(review_completed, client_suitability, accepted) PATCH 처리"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # 저장 후 목록 시리얼라이저 형식으로 응답 반환
        return Response(AnalysisListSerializer(instance, context=self.get_serializer_context()).data)

    # ── 대시보드 통계 API ──
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        대시보드 통계 데이터를 반환하는 커스텀 액션.

        URL: GET /api/analyses/stats/
        detail=False → 개별 객체가 아닌 컬렉션 레벨의 액션

        반환 데이터:
          - today_collected: 오늘 수집된 기사 수
          - today_high: 오늘 High 적합 판정 건수
          - total_analyzed: 전체 분석 완료 건수
          - monthly_cost: 이번 달 LLM 비용 추정 (원화)
          - suitability_distribution: 적합도별 분포 (파이차트용)
          - category_distribution: 사건 유형별 분포 상위 10개 (바차트용)
          - weekly_trend: 최근 7일간 일별 분석 추이 (라인차트용)
        """
        today = date.today()
        week_ago = today - timedelta(days=7)

        # ── 1. 오늘 수집된 기사 수 ──
        from articles.models import Article  # 순환 import 방지를 위해 함수 내부에서 import

        today_collected = Article.objects.filter(
            collected_at__date=today  # collected_at(DateTime)의 날짜 부분만 비교
        ).count()

        # ── 2. 오늘 High 적합 판정 건수 ──
        today_high = Analysis.objects.filter(
            analyzed_at__date=today,
            suitability="High",
        ).count()

        # ── 2-1. 오늘 Medium 적합 판정 건수 ──
        today_medium = Analysis.objects.filter(
            analyzed_at__date=today,
            suitability="Medium",
        ).count()

        # ── 3. 전체 분석 완료 건수 ──
        total_analyzed = Analysis.objects.count()

        # ── 4. 이번 달 LLM 비용 추정 (GPT-4o 기준) ──
        # 이번 달에 분석된 모든 건의 토큰 합계를 집계
        monthly_tokens = Analysis.objects.filter(
            analyzed_at__month=today.month,
            analyzed_at__year=today.year,
        ).aggregate(
            total_prompt=Sum("prompt_tokens"),       # 입력 토큰 합계
            total_completion=Sum("completion_tokens"),  # 출력 토큰 합계
        )
        prompt_t = monthly_tokens["total_prompt"] or 0       # None 방지
        completion_t = monthly_tokens["total_completion"] or 0
        # GPT-4o 가격: 입력 $2.50/1M tokens, 출력 $10.00/1M tokens
        # 달러→원화 환산 (1달러 = 1,400원 기준)
        monthly_cost = round(
            (prompt_t * 2.5 / 1_000_000 + completion_t * 10.0 / 1_000_000) * 1400
        )

        # ── 5. 적합도 분포 (파이차트 데이터) ── High → Medium → Low 순서 고정
        suit_dist = (
            Analysis.objects.values("suitability")
            .annotate(value=Count("id"))
        )
        _suit_order = {"High": 0, "Medium": 1, "Low": 2}
        suitability_distribution = sorted(
            [{"name": s["suitability"], "value": s["value"]} for s in suit_dist],
            key=lambda x: _suit_order.get(x["name"], 99),
        )

        # ── 6. 사건 유형별 분포 상위 10개 (누적 스택 바 데이터) ──
        cat_dist = (
            Analysis.objects.values("case_category")
            .annotate(
                count=Count("id"),
                high=Count("id", filter=Q(suitability="High")),
                medium=Count("id", filter=Q(suitability="Medium")),
                low=Count("id", filter=Q(suitability="Low")),
            )
            .order_by("-count")[:10]
        )
        category_distribution = [
            {
                "name": c["case_category"],
                "count": c["count"],
                "high": c["high"],
                "medium": c["medium"],
                "low": c["low"],
            }
            for c in cat_dist
        ]

        # ── 7. 주간 추이 (최근 7일 라인차트 데이터) ──
        weekly_trend = []
        for i in range(7):
            # 6일 전부터 오늘까지 순서대로 반복
            d = today - timedelta(days=6 - i)
            total = Analysis.objects.filter(analyzed_at__date=d).count()
            high = Analysis.objects.filter(analyzed_at__date=d, suitability="High").count()
            medium = Analysis.objects.filter(analyzed_at__date=d, suitability="Medium").count()
            weekly_trend.append({
                "date": d.isoformat(),  # "2026-02-16" 형식
                "total": total,
                "high": high,
                "medium": medium,
            })

        # ── 8. 심사 현황 통계 ──
        total_reviewed = Analysis.objects.filter(review_completed=True).count()
        total_accepted = Analysis.objects.filter(accepted=True).count()
        acceptance_rate = round(total_accepted / total_reviewed * 100) if total_reviewed > 0 else 0

        # 모든 통계 데이터를 JSON으로 반환
        return Response({
            "today_collected": today_collected,
            "today_high": today_high,
            "today_medium": today_medium,
            "total_analyzed": total_analyzed,
            "monthly_cost": monthly_cost,
            "suitability_distribution": suitability_distribution,
            "category_distribution": category_distribution,
            "weekly_trend": weekly_trend,
            "total_reviewed": total_reviewed,
            "total_accepted": total_accepted,
            "acceptance_rate": acceptance_rate,
        })

    # ── 엑셀 내보내기 API ──
    @action(detail=False, methods=["get"])
    def export(self, request):
        """
        분석 결과를 엑셀(.xlsx) 파일로 다운로드하는 커스텀 액션.

        URL: GET /api/analyses/export/
        필터 파라미터를 함께 전달하면 필터링된 결과만 내보냅니다.
        예: GET /api/analyses/export/?suitability=High

        동작 흐름:
          1. filter_queryset()으로 현재 필터 조건이 적용된 QuerySet 획득
          2. export_analyses_to_excel()로 엑셀 파일 생성 (BytesIO 버퍼)
          3. HttpResponse에 엑셀 MIME 타입과 다운로드 헤더를 설정하여 반환
        """
        # 현재 적용된 필터(suitability, stage 등)를 QuerySet에 반영
        queryset = self.filter_queryset(self.get_queryset())

        # 엑셀 파일을 메모리 버퍼(BytesIO)로 생성
        buf = export_analyses_to_excel(queryset)

        # HTTP 응답 생성 — 엑셀 파일 다운로드 형태
        response = HttpResponse(
            buf.getvalue(),  # BytesIO 버퍼의 바이너리 데이터
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        # Content-Disposition 헤더 — 브라우저가 파일 다운로드로 처리하도록 설정
        response["Content-Disposition"] = 'attachment; filename="analyses_export.xlsx"'
        return response


# ──────────────────────────────────────────────
# 사건 그룹 ViewSet (읽기 전용)
# ──────────────────────────────────────────────
class CaseGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    사건 그룹(CaseGroup) API 엔드포인트.

    동일한 사건에 대한 여러 기사를 하나의 그룹으로 묶어 관리합니다.
    예: "쿠팡 개인정보 유출" 관련 기사 34건 → CASE-2026-001

    엔드포인트:
      GET /api/case-groups/       → 사건 그룹 목록 (검색, 정렬)
      GET /api/case-groups/{id}/  → 사건 그룹 상세

    QuerySet:
      prefetch_related("analyses")로 관련 분석 결과를 미리 로드하여
      N+1 쿼리 문제를 방지합니다.
    """

    # prefetch_related: 역참조 관계(1:N)에서 추가 쿼리를 최소화
    queryset = CaseGroup.objects.prefetch_related("analyses").all()

    serializer_class = CaseGroupSerializer

    # 검색 필드 — ?search= 파라미터로 사건 ID 또는 사건명 검색
    # 예: ?search=쿠팡  또는  ?search=CASE-2026-001
    search_fields = ["case_id", "name"]

    # 기본 정렬 — 생성일 기준 최신순
    ordering = ["-created_at"]
