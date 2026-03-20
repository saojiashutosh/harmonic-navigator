from rest_framework.viewsets import ModelViewSet
from rest_framework.views import Response
from rest_framework import status
import django


class HarmonicBaseViewSet(ModelViewSet):
    # renderer_classes = AtomicJsonRenderer

    # # TODO  write queryset
    # def get_queryset(self):
    #     """
    #     1. filter inactive user
    #     2. filter level zero user
    #     3. Comments
    #     """
    #     if self.request.user_level == 0:
    #         return self.serializer_class.Meta.model.objects.all()
    #     if self.request.user_level == 5:
    #         return self.serializer_class.Meta.model.objects.exclude(userId__user_level=0)
    #     return self.serializer_class.Meta.model.objects.exclude(userId__is_active=False).exclude(userId__user_level=0)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except django.db.models.deletion.ProtectedError as e:
            return Response(status=status.HTTP_423_LOCKED, data={'detail': str(e)})
        except django.db.models.deletion.RestrictedError as e:
            return Response(status=status.HTTP_423_LOCKED, data={'detail': str(e)})
        # self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()
