from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Article, Keyword, MediaSource
from .serializers import (
    ArticleDetailSerializer,
    ArticleListSerializer,
    KeywordSerializer,
    MediaSourceSerializer,
)


class ArticleFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="published_at", lookup_expr="gte")
    date_to = filters.DateFilter(field_name="published_at", lookup_expr="lte")

    class Meta:
        model = Article
        fields = ["status", "source"]


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Article.objects.select_related("source").all()
    filterset_class = ArticleFilter
    search_fields = ["title", "content"]
    ordering_fields = ["published_at", "collected_at"]
    ordering = ["-published_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ArticleDetailSerializer
        return ArticleListSerializer

    @action(detail=True, methods=["post"])
    def reanalyze(self, request, pk=None):
        article = self.get_object()
        from analyses.tasks import reanalyze_article

        reanalyze_article.delay(article.pk)
        return Response({"detail": "재분석 요청이 접수되었습니다."}, status=status.HTTP_202_ACCEPTED)


class KeywordViewSet(viewsets.ModelViewSet):
    queryset = Keyword.objects.all()
    serializer_class = KeywordSerializer
    search_fields = ["word"]


class MediaSourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MediaSource.objects.all()
    serializer_class = MediaSourceSerializer
