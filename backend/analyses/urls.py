from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AnalysisViewSet, CaseGroupViewSet

router = DefaultRouter()
router.register("analyses", AnalysisViewSet)
router.register("case-groups", CaseGroupViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
