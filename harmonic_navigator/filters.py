from django_filters import FilterSet
import django_filters
import pytz
from django.utils import timezone
from datetime import datetime, timedelta


class HarmonicDateFilter(FilterSet):
    fromDate = django_filters.DateTimeFilter(
        field_name='createdAt', method='filter_fromDate')
    toDate = django_filters.DateTimeFilter(
        field_name='createdAt', method='filter_toDate')

    def filter_fromDate(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        value = timezone.make_naive(value)
        value = tz.localize(value)
        return queryset.filter(createdAt__gte=value)

    def filter_toDate(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        value = timezone.make_naive(value)
        value = tz.localize(value)
        value = value.replace(hour=23, minute=59,
                              second=59, microsecond=999999)
        return queryset.filter(createdAt__lte=value)


class HarmonicUserFilter(FilterSet):
    firstName = django_filters.CharFilter(
        field_name='userId__firstName', lookup_expr='icontains')
    lastName = django_filters.CharFilter(
        field_name='userId__lastName', lookup_expr='icontains')
    email = django_filters.CharFilter(
        field_name='userId__email', lookup_expr='exact')
    fromDate = django_filters.DateTimeFilter(
        field_name='createdAt', method='filter_fromDate')
    toDate = django_filters.DateTimeFilter(
        field_name='createdAt', method='filter_toDate')

    def filter_fromDate(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        value = timezone.make_naive(value)
        value = tz.localize(value)
        return queryset.filter(createdAt__gte=value)

    def filter_toDate(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        value = timezone.make_naive(value)
        value = tz.localize(value)
        value = value.replace(hour=23, minute=59,
                              second=59, microsecond=999999)
        return queryset.filter(createdAt__lte=value)


class HarmonicTimeFilter(FilterSet):
    today = django_filters.BooleanFilter(
        field_name='createdAt',
        method='filter_today',
        label='Today'
    )

    this_week = django_filters.BooleanFilter(
        field_name='createdAt',
        method='filter_this_week',
        label='This Week'
    )

    this_month = django_filters.BooleanFilter(
        field_name='createdAt',
        method='filter_this_month',
        label='This Month'
    )

    this_year = django_filters.BooleanFilter(
        field_name='createdAt',
        method='filter_this_year',
        label='This Year'
    )

    def filter_today(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        today = timezone.now().astimezone(tz).date()
        start_of_day = tz.localize(
            datetime.combine(today, datetime.min.time()))
        end_of_day = tz.localize(datetime.combine(today, datetime.max.time()))
        return queryset.filter(createdAt__range=(start_of_day, end_of_day))

    def filter_this_week(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        today = timezone.now().astimezone(tz).date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        start_of_week = tz.localize(datetime.combine(
            start_of_week, datetime.min.time()))
        end_of_week = tz.localize(datetime.combine(
            end_of_week, datetime.max.time()))
        return queryset.filter(createdAt__range=(start_of_week, end_of_week))

    def filter_this_month(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        today = timezone.now().astimezone(tz).date()
        start_of_month = today.replace(day=1)
        end_of_month = (start_of_month.replace(
            month=start_of_month.month + 1) - timedelta(days=1))
        start_of_month = tz.localize(datetime.combine(
            start_of_month, datetime.min.time()))
        end_of_month = tz.localize(datetime.combine(
            end_of_month, datetime.max.time()))
        return queryset.filter(createdAt__range=(start_of_month, end_of_month))

    def filter_this_year(self, queryset, name, value):
        try:
            tz = pytz.timezone(self.request.META.get(
                'HTTP_X_TIMEZONE_REGION', 'UTC'))
        except Exception:
            tz = pytz.utc
        today = timezone.now().astimezone(tz).date()
        start_of_year = today.replace(month=1, day=1)
        end_of_year = today.replace(month=12, day=31)
        start_of_year = tz.localize(datetime.combine(
            start_of_year, datetime.min.time()))
        end_of_year = tz.localize(datetime.combine(
            end_of_year, datetime.max.time()))
        return queryset.filter(createdAt__range=(start_of_year, end_of_year))


class MultiValueCharFilter(django_filters.BaseCSVFilter, django_filters.CharFilter):
    def filter(self, qs, value):
        # value is either a list or an 'empty' value
        values = value or []
        if values == []:
            return qs
        lookup = "%s__%s" % (self.field_name, self.lookup_expr)
        return qs.filter(**{lookup: value})
