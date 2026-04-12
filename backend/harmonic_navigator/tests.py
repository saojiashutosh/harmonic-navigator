from rest_framework.test import APIRequestFactory, APITestCase

from harmonic_navigator.serializers import HarmonicBaseSerializer
from users.models import Users


class HarmonicBaseSerializerTests(APITestCase):
    def test_retrieve_uses_get_fields_for_authenticated_owner(self):
        user = Users.objects.create_user(
            email="owner@example.com",
            password="secret123",
            firstName="Owner",
            lastName="User",
            level=1,
            phoneNumber="1234567890",
        )

        class OwnerAwareUserSerializer(HarmonicBaseSerializer):
            class Meta:
                model = Users
                fields = ("id", "email", "firstName", "lastName")
                get_fields = ("id", "email")

        request = APIRequestFactory().get(f"/users/users/{user.id}/")
        request.user = user
        view = type("View", (), {"action": "retrieve"})()

        serializer = OwnerAwareUserSerializer(
            user,
            context={"request": request, "view": view},
        )

        self.assertEqual(
            serializer.data,
            {
                "id": str(user.id),
                "email": user.email,
            },
        )
