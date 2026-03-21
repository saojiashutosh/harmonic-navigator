from rest_framework import serializers
from collections import OrderedDict
from utils.time import convert_time


class HarmonicBaseSerializer(serializers.ModelSerializer):

    createdAt = serializers.SerializerMethodField(method_name="get_created_at")
    updatedAt = serializers.SerializerMethodField(method_name="get_updated_at")

    def get_created_at(self, instance):
        request = self.context.get('request')
        timezone = request.META.get('HTTP_X_TIMEZONE_REGION', None) if request else None
        return convert_time(instance.createdAt, timezone)

    def get_updated_at(self, instance):
        request = self.context.get('request')
        timezone = request.META.get('HTTP_X_TIMEZONE_REGION', None) if request else None
        return convert_time(instance.updatedAt, timezone)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context.get("view")
        request = self.context.get("request")
        action = getattr(view, "action", None)
        permission = bool(
            request and getattr(request, "user", None) == getattr(instance, "id", None)
        )
        if action == "list":
            list_fields = getattr(self.Meta, "list_fields", self.Meta.fields)
            return OrderedDict(
                {key: data[key]
                    for key in data if key in list_fields}
            )
        if action == "retrieve":
            get_fields = getattr(self.Meta, "get_fields", self.Meta.fields)
            if not permission:
                return data
            return OrderedDict(
                {key: data[key] for key in data if key in get_fields}
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
