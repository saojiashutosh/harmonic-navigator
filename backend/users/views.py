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
