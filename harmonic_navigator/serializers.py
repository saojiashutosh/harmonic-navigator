from rest_framework import serializers
from collections import OrderedDict
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        action = self.context["view"].action
        permission = self.context["request"].user == instance.id
        if action == "list":
            return OrderedDict(
                {key: data[key]
                    for key in data if key in self.Meta.list_fields}
            )
        if action == "retrieve":
            if not permission:
                return data
            return OrderedDict(
                {key: data[key] for key in data if key in self.Meta.get_fields}
            )
        return data

    @property
    def errors(self):
        # get errors
        errors = super().errors
        verbose_errors = {}

        fields = {field.name: field.verbose_name for field in
                  self.Meta.model._meta.get_fields() if hasattr(field, 'verbose_name')}

        for field_name, error in errors.items():
            if field_name in fields:
                verbose_errors[str(fields[field_name])] = error
            else:
                verbose_errors[field_name] = error
        return verbose_errors
