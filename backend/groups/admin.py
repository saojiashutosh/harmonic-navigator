from django.contrib import admin

from .models import GroupParticipant, GroupSession


@admin.register(GroupSession)
class GroupSessionAdmin(admin.ModelAdmin):
    list_display = ("code", "status", "hostId", "blendedMoodLabel", "createdAt")
    list_filter = ("status",)
    search_fields = ("code",)


@admin.register(GroupParticipant)
class GroupParticipantAdmin(admin.ModelAdmin):
    list_display = ("displayName", "groupSessionId", "isHost", "isReady", "createdAt")
    list_filter = ("isHost", "isReady")
