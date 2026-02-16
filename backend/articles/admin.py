from django.contrib import admin

from .models import Article, ArticleKeyword, Keyword, MediaSource


@admin.register(MediaSource)
class MediaSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("word", "is_active", "created_at")
    list_filter = ("is_active",)


class ArticleKeywordInline(admin.TabularInline):
    model = ArticleKeyword
    extra = 0


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "status", "published_at", "collected_at")
    list_filter = ("status", "source")
    search_fields = ("title", "content")
    date_hierarchy = "published_at"
    readonly_fields = ("collected_at",)
    inlines = [ArticleKeywordInline]
