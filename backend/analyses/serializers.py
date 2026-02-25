from rest_framework import serializers

from articles.serializers import ArticleListSerializer

from .models import Analysis, CaseGroup


class CaseGroupSerializer(serializers.ModelSerializer):
    article_count = serializers.IntegerField(source="analyses.count", read_only=True)

    class Meta:
        model = CaseGroup
        fields = ["id", "case_id", "name", "description", "article_count", "created_at"]


class AnalysisListSerializer(serializers.ModelSerializer):
    article_title = serializers.CharField(source="article.title")
    article_url = serializers.URLField(source="article.url")
    source_name = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField(source="article.published_at")
    case_id = serializers.CharField(source="case_group.case_id", default="")
    case_name = serializers.CharField(source="case_group.name", default="")
    related_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Analysis
        fields = [
            "id",
            "article_title",
            "article_url",
            "source_name",
            "published_at",
            "suitability",
            "case_category",
            "defendant",
            "damage_amount",
            "damage_amount_num",
            "victim_count",
            "victim_count_num",
            "stage",
            "case_id",
            "case_name",
            "is_relevant",
            "analyzed_at",
            "related_count",
        ]

    def get_source_name(self, obj):
        return obj.article.source.name if obj.article.source else ""


class RelatedArticleSerializer(serializers.ModelSerializer):
    """같은 케이스 그룹의 유사 기사 요약"""
    article_title = serializers.CharField(source="article.title")
    article_url = serializers.URLField(source="article.url")
    published_at = serializers.DateTimeField(source="article.published_at")
    source_name = serializers.SerializerMethodField()

    class Meta:
        model = Analysis
        fields = ["id", "article_title", "article_url", "published_at", "source_name", "summary", "suitability"]

    def get_source_name(self, obj):
        return obj.article.source.name if obj.article.source else ""


class AnalysisDetailSerializer(serializers.ModelSerializer):
    article = ArticleListSerializer(read_only=True)
    case_group = CaseGroupSerializer(read_only=True)
    related_articles = serializers.SerializerMethodField()

    class Meta:
        model = Analysis
        fields = [
            "id",
            "article",
            "case_group",
            "suitability",
            "suitability_reason",
            "case_category",
            "defendant",
            "damage_amount",
            "victim_count",
            "stage",
            "stage_detail",
            "summary",
            "is_relevant",
            "llm_model",
            "prompt_tokens",
            "completion_tokens",
            "analyzed_at",
            "related_articles",
        ]

    def get_related_articles(self, obj):
        if not obj.case_group:
            return []
        related = (
            Analysis.objects.filter(case_group=obj.case_group, is_relevant=True)
            .exclude(id=obj.id)
            .select_related("article", "article__source")
            .order_by("-article__published_at")[:10]
        )
        return RelatedArticleSerializer(related, many=True).data
