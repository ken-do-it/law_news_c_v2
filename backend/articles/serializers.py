from rest_framework import serializers

from .models import Article, Keyword, MediaSource


class MediaSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaSource
        fields = ["id", "name", "url", "is_active"]


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = ["id", "word", "is_active"]


class ArticleListSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", default="")

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "url",
            "source_name",
            "author",
            "published_at",
            "collected_at",
            "status",
        ]


class ArticleDetailSerializer(serializers.ModelSerializer):
    source = MediaSourceSerializer(read_only=True)
    keywords = KeywordSerializer(many=True, read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "content",
            "url",
            "source",
            "author",
            "published_at",
            "collected_at",
            "status",
            "keywords",
        ]
