from datetime import date

from harmonic_navigator.filters import HarmonicBaseFilterSet, django_filters

from .models import ConcertEvent, ConcertPlaylist


class ConcertEventFilter(HarmonicBaseFilterSet):
    # City is matched case-insensitively so "mumbai" and "Mumbai" both work.
    city = django_filters.CharFilter(field_name="city", lookup_expr="icontains")
    upcoming = django_filters.BooleanFilter(method="filter_upcoming")

    def filter_upcoming(self, queryset, name, value):
        if value:
            return queryset.filter(eventDate__gte=date.today())
        return queryset

    class Meta:
        model = ConcertEvent
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'artistId',
            'city',
            'country',
            'source',
            'isActive',
        )


class ConcertPlaylistFilter(HarmonicBaseFilterSet):
    class Meta:
        model = ConcertPlaylist
        fields = (
            'id',
            'createdAt',
            'updatedAt',
            'concertEventId',
            'playlistId',
            'userId',
            'city',
        )
