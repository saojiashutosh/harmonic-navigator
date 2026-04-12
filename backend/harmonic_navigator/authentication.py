try:
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import AuthenticationFailed
except ModuleNotFoundError:
    from rest_framework.authentication import BaseAuthentication

    class JWTAuthentication(BaseAuthentication):
        """Placeholder when simplejwt is not installed."""
        def authenticate(self, request):
            return None

    class AuthenticationFailed(Exception):
        pass

from .exceptions import UserDeleted


class HarmonicJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user = super().get_user(validated_token)
        except AuthenticationFailed:
            raise UserDeleted("User no longer exists and has been deleted.")
        return user
