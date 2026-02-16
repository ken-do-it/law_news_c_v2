from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ArticleViewSet, KeywordViewSet, MediaSourceViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet)
router.register("keywords", KeywordViewSet)
router.register("sources", MediaSourceViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
