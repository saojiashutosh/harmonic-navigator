from harmonic_navigator.filters import HarmonicDateFilter
from .models import Users, UsersDevices


class UsersFilter(HarmonicDateFilter):
    class Meta:
        model = Users
        fields = (
            'createdAt',
            'updatedAt',
            'is_active',
            'is_superuser',
            'is_staff',
            'level'
        )


class UsersDevicesFilter(HarmonicDateFilter):
    class Meta:
        model = UsersDevices
        fields = (
            'createdAt',
            'updatedAt',
            'userId',
        )
