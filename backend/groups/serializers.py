from rest_framework import serializers

from harmonic_navigator.serializers import HarmonicBaseSerializer
from playlists.serializers import PlaylistSerializer

from .models import GroupParticipant, GroupSession


class GroupParticipantSerializer(HarmonicBaseSerializer):
    moodLabel = serializers.SerializerMethodField()

    class Meta:
        model = GroupParticipant
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'groupSessionId',
            'userId',
            'moodSessionId',
            'displayName',
            'isHost',
            'isReady',
            'moodLabel',
        )

    def get_moodLabel(self, obj):
        if obj.moodSessionId_id is None:
            return None
        inference = getattr(obj.moodSessionId, "mood_inference", None)
        return inference.moodLabel if inference else None


class GroupSessionSerializer(HarmonicBaseSerializer):
    participants = GroupParticipantSerializer(many=True, read_only=True)
    playlist = PlaylistSerializer(source="playlistId", read_only=True)

    class Meta:
        model = GroupSession
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'code',
            'hostId',
            'status',
            'playlistId',
            'playlist',
            'blendedMoodLabel',
            'expiresAt',
            'participants',
        )


class CreateGroupSessionSerializer(serializers.Serializer):
    displayName = serializers.CharField(max_length=64)


class JoinGroupSessionSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8, min_length=4)
    displayName = serializers.CharField(max_length=64)


class AttachMoodSessionSerializer(serializers.Serializer):
    participantId = serializers.UUIDField()
    moodSessionId = serializers.UUIDField()
