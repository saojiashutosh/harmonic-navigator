from harmonic_navigator.filters import HarmonicBaseFilterSet
from .models import GroupParticipant, GroupSession


class GroupSessionFilter(HarmonicBaseFilterSet):
    class Meta:
        model = GroupSession
        fields = (
            'id',
            'code',
            'status',
            'hostId',
            'createdAt',
            'updatedAt',
        )


class GroupParticipantFilter(HarmonicBaseFilterSet):
    class Meta:
        model = GroupParticipant
        fields = (
            'id',
            'groupSessionId',
            'userId',
            'moodSessionId',
            'isHost',
            'isReady',
            'createdAt',
            'updatedAt',
        )
