from django.db import models
import uuid
from django.utils.translation import gettext_lazy as _


class HarmonicBaseModel(models.Model):
    id = models.UUIDField(
        verbose_name=_('Id'),
        primary_key=True,
        db_column="id",
        default=uuid.uuid4
    )
    createdAt = models.DateTimeField(
        verbose_name=_('Create Date'),
        auto_now_add=True,
        db_column='created_at'
    )
    updatedAt = models.DateTimeField(
        verbose_name=_('Update Date'),
        auto_now=True,
        db_column='updated_at'
    )

    class Meta:
        abstract = True


class HN_TIMESTAMP(models.Model):
    createdAt = models.DateTimeField(
        verbose_name=_('Create Date'),
        auto_now_add=True,
        db_column='created_at'
    )
    updatedAt = models.DateTimeField(
        verbose_name=_('Update Date'),
        auto_now=True,
        db_column='updated_at'
    )

    class Meta:
        abstract = True
