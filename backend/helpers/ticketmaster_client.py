"""Ticketmaster Discovery API client — upcoming music events by city.

Free API key: create an app at https://developer.ticketmaster.com.
Set TICKETMASTER_API_KEY in the environment to enable concert discovery.
"""
from __future__ import annotations

import os

import requests
from django.core.cache import cache

TICKETMASTER_EVENTS_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

# Discovery results are stable enough for half-hour caching; this also keeps the
# free-tier rate limit comfortable when several users search the same city.
_CACHE_TTL = 60 * 30


class TicketmasterConfigurationError(RuntimeError):
    """Raised when the Ticketmaster API key is missing."""


class TicketmasterRequestError(RuntimeError):
    """Raised when a Ticketmaster request fails."""


def _api_key() -> str:
    key = (os.getenv("TICKETMASTER_API_KEY") or "").strip()
    if not key:
        raise TicketmasterConfigurationError(
            "Ticketmaster API key is missing. Set TICKETMASTER_API_KEY to enable "
            "concert discovery."
        )
    return key


def search_events(
    city: str,
    *,
    country_code: str | None = None,
    size: int = 100,
) -> list[dict]:
    """Return normalized upcoming music events for a city.

    Each event dict contains: external_id, name, venue_name, city, country,
    event_date (ISO yyyy-mm-dd string), ticket_url, image_url and a list of
    attraction (artist/act) names.
    """
    city = (city or "").strip()
    if not city:
        return []

    cache_key = f"ticketmaster:events:{city.lower()}:{(country_code or '').lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "apikey": _api_key(),
        "city": city,
        "classificationName": "music",
        "sort": "date,asc",
        "size": min(max(size, 1), 200),
    }
    if country_code:
        params["countryCode"] = country_code

    try:
        response = requests.get(TICKETMASTER_EVENTS_URL, params=params, timeout=12)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TicketmasterRequestError(
            f"Ticketmaster request failed: {exc}"
        ) from exc

    payload = response.json() or {}
    events = (payload.get("_embedded") or {}).get("events") or []
    results = [event for event in (_normalise_event(e) for e in events) if event]
    cache.set(cache_key, results, _CACHE_TTL)
    return results


def _normalise_event(event: dict) -> dict | None:
    embedded = event.get("_embedded") or {}
    venues = embedded.get("venues") or []
    attractions = embedded.get("attractions") or []
    venue = venues[0] if venues else {}
    start = (event.get("dates") or {}).get("start") or {}
    images = event.get("images") or []

    attraction_names = [a.get("name") for a in attractions if a.get("name")]
    if not attraction_names:
        return None

    return {
        "external_id": event.get("id"),
        "name": event.get("name"),
        "venue_name": venue.get("name"),
        "city": (venue.get("city") or {}).get("name"),
        "country": (venue.get("country") or {}).get("name"),
        "event_date": start.get("localDate"),
        "ticket_url": event.get("url"),
        "image_url": images[0].get("url") if images else None,
        "attractions": attraction_names,
    }
