from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from harmonic_navigator.views import HarmonicBaseViewSet

from .filters import UsersDevicesFilter, UsersFilter
from .models import Users, UsersDevices
from .serializers import UsersDevicesSerializer, UsersSerializer


class UsersViewSet(HarmonicBaseViewSet):
    queryset = Users.objects.all()
    serializer_class = UsersSerializer
    filterset_class = UsersFilter
    search_fields = ()
    ordering_fields = (
        "createdAt",
        "updatedAt",
    )


class UsersDevicesViewSet(HarmonicBaseViewSet):
    queryset = UsersDevices.objects.all()
    serializer_class = UsersDevicesSerializer
    filterset_class = UsersDevicesFilter
    search_fields = ()
    ordering_fields = (
        "createdAt",
        "updatedAt",
    )


# ── Auth helpers ─────────────────────────────────────────────────────────────

def _user_payload(user):
    return {
        "id": str(user.id),
        "email": user.email,
        "firstName": user.firstName,
        "lastName": user.lastName,
    }


# ── Register ─────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    email = (request.data.get("email") or "").strip().lower()
    password = (request.data.get("password") or "").strip()
    first_name = (request.data.get("firstName") or "").strip()
    last_name = (request.data.get("lastName") or "").strip()

    if not email or not password or not first_name:
        return Response(
            {"detail": "Email, password, and first name are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 6:
        return Response(
            {"detail": "Password must be at least 6 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if Users.objects.filter(email=email).exists():
        return Response(
            {"detail": "An account with this email already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = Users.objects.create_user(
        email=email,
        password=password,
        firstName=first_name,
        lastName=last_name,
        level=1,
        phoneNumber="",
    )
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {"token": token.key, "user": _user_payload(user)},
        status=status.HTTP_201_CREATED,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    email = (request.data.get("email") or "").strip().lower()
    password = (request.data.get("password") or "").strip()

    if not email or not password:
        return Response(
            {"detail": "Email and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, email=email, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid email or password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": _user_payload(user)})


# ── Logout ────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    request.user.auth_token.delete()
    return Response({"detail": "Logged out."})


# ── Me ────────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(_user_payload(request.user))
