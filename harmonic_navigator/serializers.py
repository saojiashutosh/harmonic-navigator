from rest_framework import serializers
from utils.time import convert_time


class HarmonicBaseSerializer(serializers.ModelSerializer):

    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    def get_createdAt(self, instance):
        timezone = self.context['request'].META.get(
            'HTTP_X_TIMEZONE_REGION', None)
        return convert_time(instance.createdAt, timezone)

    def get_updatedAt(self, instance):
        timezone = self.context['request'].META.get(
            'HTTP_X_TIMEZONE_REGION', None)
        return convert_time(instance.updatedAt, timezone)
