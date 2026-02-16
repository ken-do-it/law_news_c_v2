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
            "victim_count",
            "stage",
            "case_id",
            "case_name",
            "analyzed_at",
        ]

    def get_source_name(self, obj):
        return obj.article.source.name if obj.article.source else ""


class AnalysisDetailSerializer(serializers.ModelSerializer):
    article = ArticleListSerializer(read_only=True)
    case_group = CaseGroupSerializer(read_only=True)

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
            "llm_model",
            "prompt_tokens",
            "completion_tokens",
            "analyzed_at",
        ]
