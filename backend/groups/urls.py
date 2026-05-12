from rest_framework.routers import DefaultRouter

from .views import GroupSessionViewSet

router = DefaultRouter()
router.register(r'group-sessions', GroupSessionViewSet, basename='group-session')

urlpatterns = router.urls
