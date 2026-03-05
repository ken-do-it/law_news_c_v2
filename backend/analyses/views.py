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

from django.db.models import Case, Count, IntegerField, Q, Subquery, OuterRef, Sum, Value, When
from django.http import HttpResponse
from django_filters import rest_framework as filters  # django-filter 라이브러리의 DRF 통합
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter as DRFOrderingFilter, SearchFilter
from rest_framework.response import Response

from .export import export_analyses_to_excel, export_analyses_to_pdf, export_case_groups_to_excel
from .models import Analysis, CaseGroup
from .serializers import (
    AnalysisDetailSerializer,
    AnalysisListSerializer,
    AnalysisReviewSerializer,
    CaseGroupDetailSerializer,
    CaseGroupReviewSerializer,
    CaseGroupSerializer,
)


# ──────────────────────────────────────────────
# 커스텀 정렬 필터 — published_at alias 처리
# ──────────────────────────────────────────────
class AnalysisOrderingFilter(DRFOrderingFilter):
    """프론트에서 보내는 published_at을 article__published_at으로 매핑"""

    _ALIAS = {
        "published_at": "article__published_at",
        "-published_at": "-article__published_at",
    }

    def remove_invalid_fields(self, queryset, fields, view, request):
        resolved, remaining = [], []
        for f in fields:
            if f in self._ALIAS:
                resolved.append(self._ALIAS[f])
            else:
                remaining.append(f)
        if remaining:
            resolved.extend(super().remove_invalid_fields(queryset, remaining, view, request))
        return resolved


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

    # 단독 기사만 (case_group이 없는 기사)
    standalone = filters.BooleanFilter(field_name="case_group", lookup_expr="isnull")

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
            "suitability", "case_category", "stage", "case_group", "standalone",
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
    filter_backends = [filters.DjangoFilterBackend, SearchFilter, AnalysisOrderingFilter]

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
        # suitability_rank 어노테이션 (High=3, Medium=2, Low=1 — 숫자 정렬용)
        # case_group_high/medium/low — 케이스 그룹 내 적합도별 기사 수 (N+1 방지 annotate)
        qs = qs.annotate(
            related_count=Count(
                "case_group__analyses",
                filter=Q(case_group__analyses__is_relevant=True),
            ),
            suitability_rank=Case(
                When(suitability="High", then=Value(3)),
                When(suitability="Medium", then=Value(2)),
                When(suitability="Low", then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            case_group_high=Count(
                "case_group__analyses",
                filter=Q(
                    case_group__analyses__suitability="High",
                    case_group__analyses__is_relevant=True,
                ),
            ),
            case_group_medium=Count(
                "case_group__analyses",
                filter=Q(
                    case_group__analyses__suitability="Medium",
                    case_group__analyses__is_relevant=True,
                ),
            ),
            case_group_low=Count(
                "case_group__analyses",
                filter=Q(
                    case_group__analyses__suitability="Low",
                    case_group__analyses__is_relevant=True,
                ),
            ),
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
    ordering_fields = [
        "analyzed_at",
        "article__published_at",
        "suitability",
        "suitability_rank",    # High=3, Medium=2, Low=1 순서 정렬 (어노테이션 필드)
        "damage_amount_num",   # 피해 규모 큰 순 정렬
        "victim_count_num",    # 피해자 많은 순 정렬
        "review_completed",    # 미심사 먼저 정렬용
    ]

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
        """심사 필드(review_completed, client_suitability, accepted) PATCH 처리.
        같은 케이스 그룹의 모든 기사에 동일 심사 결과를 일괄 적용합니다.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 같은 케이스 그룹의 나머지 기사에도 동일 심사 결과 일괄 적용
        if instance.case_group_id and serializer.validated_data:
            Analysis.objects.filter(
                case_group_id=instance.case_group_id
            ).exclude(id=instance.id).update(**serializer.validated_data)

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

        # ── 2-2. 분석 대기 건수 (pending + analyzing) ──
        pending_count = Article.objects.filter(
            status__in=["pending", "analyzing"]
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

        # ── 7. 주간 추이 (최근 7일 라인차트 데이터) — 단일 aggregate 쿼리 ──
        days = [today - timedelta(days=6 - i) for i in range(7)]
        agg_kwargs = {}
        for d in days:
            k = d.isoformat().replace("-", "_")
            agg_kwargs[f"total_{k}"] = Count("id", filter=Q(analyzed_at__date=d))
            agg_kwargs[f"high_{k}"] = Count("id", filter=Q(analyzed_at__date=d, suitability="High"))
            agg_kwargs[f"medium_{k}"] = Count("id", filter=Q(analyzed_at__date=d, suitability="Medium"))
        agg = Analysis.objects.aggregate(**agg_kwargs)
        weekly_trend = []
        for d in days:
            k = d.isoformat().replace("-", "_")
            weekly_trend.append({
                "date": d.isoformat(),
                "total": agg[f"total_{k}"],
                "high": agg[f"high_{k}"],
                "medium": agg[f"medium_{k}"],
            })

        # ── 8. 심사 현황 통계 (기사 단위 — 하위 호환) ──
        total_reviewed = Analysis.objects.filter(review_completed=True).count()
        total_accepted = Analysis.objects.filter(accepted=True).count()
        acceptance_rate = round(total_accepted / total_reviewed * 100) if total_reviewed > 0 else 0

        # ── 8-1. 사건(CaseGroup) 단위 심사 통계 ──
        total_cases = CaseGroup.objects.count()
        total_reviewed_cases = CaseGroup.objects.filter(review_completed=True).count()
        total_accepted_cases = CaseGroup.objects.filter(accepted=True).count()
        acceptance_rate_cases = (
            round(total_accepted_cases / total_reviewed_cases * 100)
            if total_reviewed_cases > 0
            else 0
        )

        # ── 9. 스케줄러 상태 (다음 수집 시간 등) ──
        try:
            from scheduler.scheduler import get_scheduler_state
            scheduler_state = get_scheduler_state()
        except Exception:
            scheduler_state = None

        # 모든 통계 데이터를 JSON으로 반환
        return Response({
            "today_collected": today_collected,
            "pending_count": pending_count,
            "today_high": today_high,
            "today_medium": today_medium,
            "total_analyzed": total_analyzed,
            "monthly_cost": monthly_cost,
            "suitability_distribution": suitability_distribution,
            "category_distribution": category_distribution,
            "weekly_trend": weekly_trend,
            "total_cases": total_cases,
            "total_reviewed_cases": total_reviewed_cases,
            "total_accepted_cases": total_accepted_cases,
            "acceptance_rate_cases": acceptance_rate_cases,
            "total_reviewed": total_reviewed,
            "total_accepted": total_accepted,
            "acceptance_rate": acceptance_rate,
            "scheduler_state": scheduler_state,
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

    # ── PDF 리포트 API ──
    @action(detail=False, methods=["get"])
    def report(self, request):
        """
        주간/월간 PDF 리포트 다운로드.

        URL: GET /api/analyses/report/?period=weekly
             GET /api/analyses/report/?period=monthly

        필터 조건:
          - suitability: High 또는 Medium 등급
          - review_completed: True (심사 완료 건만)

        쿼리 파라미터:
          - period: 'weekly'(기본) 또는 'monthly'
        """
        from datetime import date, timedelta

        period = request.query_params.get("period", "weekly")

        today = date.today()
        if period == "monthly":
            date_from = today.replace(day=1)
            filename = today.strftime("report_%Y%m.pdf")
        else:
            date_from = today - timedelta(days=6)
            filename = today.strftime("report_weekly_%Y%m%d.pdf")

        queryset = (
            Analysis.objects.select_related("article", "article__source", "case_group")
            .filter(
                suitability__in=["High", "Medium"],
                article__published_at__date__gte=date_from,
            )
            .order_by("-analyzed_at")
        )

        buf = export_analyses_to_pdf(queryset, period=period)

        response = HttpResponse(buf.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ──────────────────────────────────────────────
# 사건 그룹 필터
# ──────────────────────────────────────────────
class CaseGroupFilter(filters.FilterSet):
    review_completed = filters.BooleanFilter(field_name="review_completed")
    accepted = filters.BooleanFilter(field_name="accepted")

    class Meta:
        model = CaseGroup
        fields = ["review_completed", "accepted"]


# ──────────────────────────────────────────────
# 사건 그룹 ViewSet
# ──────────────────────────────────────────────
class CaseGroupViewSet(viewsets.ModelViewSet):
    """
    사건 그룹(CaseGroup) API 엔드포인트.

    엔드포인트:
      GET    /api/case-groups/                    → 목록 (검색, 정렬)
      GET    /api/case-groups/{id}/              → 상세 (analyses 포함)
      GET    /api/case-groups/by_case_id/{case_id}/ → case_id로 상세 조회
      PATCH  /api/case-groups/{id}/              → 심사 필드 업데이트
    """

    queryset = CaseGroup.objects.annotate(
        article_count=Count("analyses", filter=Q(analyses__is_relevant=True)),
        high_count=Count("analyses", filter=Q(analyses__suitability="High")),
        medium_count=Count("analyses", filter=Q(analyses__suitability="Medium")),
        low_count=Count("analyses", filter=Q(analyses__suitability="Low")),
    )
    filterset_class = CaseGroupFilter
    search_fields = ["case_id", "name"]
    ordering = ["-article_count"]
    ordering_fields = ["created_at", "case_id", "review_completed", "article_count"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "retrieve" or self.action == "by_case_id":
            return CaseGroupDetailSerializer
        if self.action == "partial_update":
            return CaseGroupReviewSerializer
        return CaseGroupSerializer

    def get_queryset(self):
        return super().get_queryset()

    @action(detail=False, url_path="by_case_id/(?P<case_id>[^/.]+)")
    def by_case_id(self, request, case_id=None):
        """case_id로 사건 그룹 상세 조회 (GET /api/case-groups/by_case_id/2026-02-001/)"""
        obj = CaseGroup.objects.filter(case_id=case_id).prefetch_related(
            "analyses", "analyses__article", "analyses__article__source"
        ).first()
        if not obj:
            from rest_framework.exceptions import NotFound
            raise NotFound("해당 case_id를 찾을 수 없습니다.")
        serializer = CaseGroupDetailSerializer(obj)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """심사 필드 PATCH — CaseGroup 업데이트 후 동일 case_group의 Analysis에도 동기화"""
        instance = self.get_object()
        serializer = CaseGroupReviewSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 동일 case_group의 모든 Analysis에 심사 값 동기화 (하위 호환)
        Analysis.objects.filter(case_group=instance).update(
            review_completed=instance.review_completed,
            client_suitability=instance.client_suitability,
            accepted=instance.accepted,
        )

        return Response(CaseGroupDetailSerializer(instance).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """
        사건 그룹을 엑셀(.xlsx) 파일로 다운로드.
        GET /api/case-groups/export/
        필터: search, review_completed, accepted, ordering
        """
        queryset = self.filter_queryset(self.get_queryset())
        buf = export_case_groups_to_excel(queryset)
        response = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="case_groups_export.xlsx"'
        return response
