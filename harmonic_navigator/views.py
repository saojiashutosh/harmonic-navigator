from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.response import Response
from django.db.models.deletion import ProtectedError, RestrictedError

from harmonic_navigator.pagination import HarmonicPagination


class HarmonicBaseViewSet(ModelViewSet):
    # renderer_classes = AtomicJsonRenderer
    pagination_class = HarmonicPagination

    def get_queryset(self):
        """
        Fall back to the serializer model when a concrete queryset is not set.
        This keeps derived viewsets lightweight while still behaving like a
        normal DRF ModelViewSet.
        """
        queryset = getattr(self, "queryset", None)
        if queryset is not None:
            if hasattr(queryset, "all"):
                return queryset.all()
            return queryset

        serializer_class = self.get_serializer_class()
        model = getattr(getattr(serializer_class, "Meta", None), "model", None)
        if model is None:
            raise AttributeError(
                f"{self.__class__.__name__} must define `queryset` or a serializer with `Meta.model`."
            )
        return model.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError as e:
            return Response(status=status.HTTP_423_LOCKED, data={'detail': str(e)})
        except RestrictedError as e:
            return Response(status=status.HTTP_423_LOCKED, data={'detail': str(e)})
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()
