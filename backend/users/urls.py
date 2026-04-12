from rest_framework.routers import DefaultRouter

from .views import UsersDevicesViewSet, UsersViewSet

router = DefaultRouter()
router.register(r"users", UsersViewSet, basename="user")
router.register(r"devices", UsersDevicesViewSet, basename="user-device")

urlpatterns = []
urlpatterns = urlpatterns + router.urls
