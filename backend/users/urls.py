from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import UsersDevicesViewSet, UsersViewSet, login_view, logout_view, me_view, register_view

router = DefaultRouter()
router.register(r"users", UsersViewSet, basename="user")
router.register(r"devices", UsersDevicesViewSet, basename="user-device")

urlpatterns = router.urls + [
    path("auth/register/", register_view, name="auth-register"),
    path("auth/login/",    login_view,    name="auth-login"),
    path("auth/logout/",   logout_view,   name="auth-logout"),
    path("auth/me/",       me_view,       name="auth-me"),
]
