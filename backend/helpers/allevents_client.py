"""Real-time concert scraper for AllEvents (allevents.in).

AllEvents.in is a broad India-focused events aggregator. Unlike District /
BookMyShow (client-rendered SPAs behind bot protection), AllEvents
server-renders its city listings and — crucially — embeds a clean
schema.org JSON-LD array of `Event` objects in the page HTML. That makes it
reliably scrapable with a plain HTTP request, no API key, no headless browser.

Strategy:
  1. Fetch the public music listing for the city: allevents.in/{slug}/music.
  2. Parse `<script type="application/ld+json">` blocks and collect every
     schema.org Event (name, startDate, location, url, image).
  3. Fall back to the Next.js `__NEXT_DATA__` blob if no JSON-LD is present.

The page URL template is overridable via the CONCERT_EVENTS_URL env var
(use `{slug}` for the hyphenated city), in case the site's scheme changes.
"""
from __future__ import annotations

import json
import os
import re

import requests
from django.core.cache import cache

# Public music-events listing. `{slug}` = lowercase hyphenated city.
_DEFAULT_URL_TEMPLATE = "https://allevents.in/{slug}/music"

# Scraped listings are cached so repeated city searches don't re-hit the site.
_CACHE_TTL = 60 * 30

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class AllEventsScrapeError(RuntimeError):
    """Raised when the AllEvents page cannot be fetched."""


def _city_slug(city: str) -> str:
    return "-".join((city or "").strip().lower().split())


def _events_urls(city: str) -> list[str]:
    template = os.getenv("CONCERT_EVENTS_URL") or _DEFAULT_URL_TEMPLATE
    slug = _city_slug(city)
    if template == _DEFAULT_URL_TEMPLATE:
        return [
            f"https://allevents.in/{slug}/music",
            f"https://allevents.in/{slug}/concerts",
            f"https://allevents.in/{slug}/festivals",
        ]
    return [template.format(slug=slug, city=slug)]


def search_events(city: str, *, size: int = 100) -> list[dict]:
    """Scrape normalized upcoming music events for a city in real time.

    Each event dict contains: external_id, name, venue_name, city, country,
    event_date (ISO yyyy-mm-dd string), ticket_url, image_url, attractions
    (performer names, when the page exposes them) and tags.
    """
    city = (city or "").strip()
    if not city:
        return []

    cache_key = f"allevents:events:{_city_slug(city)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    results: list[dict] = []
    seen: set = set()
    urls = _events_urls(city)
    scrape_errors: list[str] = []

    for url in urls:
        try:
            response = requests.get(
                url, headers=_BROWSER_HEADERS, timeout=15,
            )
            response.raise_for_status()
            html = response.text
            raw_events = _events_from_jsonld(html) or _events_from_next_data(html)
            for raw in raw_events:
                normalised = _normalise_event(raw, city)
                if not normalised:
                    continue
                key = normalised["external_id"] or normalised["name"]
                if key in seen:
                    continue
                seen.add(key)
                results.append(normalised)
        except requests.RequestException as exc:
            scrape_errors.append(f"Error scraping {url}: {exc}")

    # If ALL requests failed and we have no results, raise the scrape error.
    if len(scrape_errors) == len(urls) and len(urls) > 0:
        raise AllEventsScrapeError(
            f"Could not reach AllEvents for '{city}': {'; '.join(scrape_errors)}"
        )

    results = results[:size]

    # Only cache a productive scrape — an empty result may be a transient
    # block, and shouldn't be frozen in for the full TTL.
    if results:
        cache.set(cache_key, results, _CACHE_TTL)
    return results



# ── JSON-LD (schema.org) ────────────────────────────────────────────────────

def _events_from_jsonld(html: str) -> list[dict]:
    events: list[dict] = []
    for block in _JSONLD_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        events.extend(_collect_event_nodes(data))
    return events


def _collect_event_nodes(node) -> list[dict]:
    """Recursively gather schema.org objects whose @type mentions 'Event'."""
    found: list[dict] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_collect_event_nodes(item))
    elif isinstance(node, dict):
        if "@graph" in node:
            found.extend(_collect_event_nodes(node["@graph"]))
        node_type = node.get("@type", "")
        types = node_type if isinstance(node_type, list) else [node_type]
        if any("event" in str(t).lower() for t in types):
            found.append(node)
    return found


def _normalise_event(event: dict, fallback_city: str) -> dict | None:
    name = _clean_str(event.get("name"))
    if not name:
        return None

    location = event.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    if not isinstance(location, dict):
        location = {}

    address = location.get("address")
    city = fallback_city
    if isinstance(address, dict):
        city = (
            _clean_str(address.get("addressLocality"))
            or _clean_str(address.get("addressRegion"))
            or fallback_city
        )

    return {
        "external_id": _clean_str(event.get("url")) or _clean_str(event.get("@id")),
        "name": name,
        "venue_name": _clean_str(location.get("name")),
        "city": city,
        "country": "India",
        "event_date": _iso_date(event.get("startDate")),
        "ticket_url": _clean_str(event.get("url")),
        "image_url": _first_image(event.get("image")),
        "attractions": _performer_names(event.get("performer")),
        "tags": _event_tags(event),
    }


def _performer_names(performer) -> list[str]:
    names: list[str] = []
    if isinstance(performer, dict):
        performer = [performer]
    if isinstance(performer, list):
        for entry in performer:
            if isinstance(entry, dict):
                name = _clean_str(entry.get("name"))
                if name:
                    names.append(name)
            elif isinstance(entry, str):
                names.append(entry.strip())
    elif isinstance(performer, str):
        names.append(performer.strip())
    return names


def _event_tags(event: dict) -> list[str]:
    tags: list[str] = []
    for key in ("genre", "keywords"):
        value = event.get(key)
        if isinstance(value, str):
            tags.extend(part.strip() for part in value.split(",") if part.strip())
        elif isinstance(value, list):
            tags.extend(str(v).strip() for v in value if v)
    return tags


# ── __NEXT_DATA__ fallback ──────────────────────────────────────────────────

def _events_from_next_data(html: str) -> list[dict]:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return []
    try:
        data = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return []

    found: list[dict] = []
    _walk_next_data(data, found)
    return found


def _walk_next_data(node, found: list[dict]) -> None:
    """Recursively pull out event-shaped dicts from the Next.js data blob."""
    if isinstance(node, list):
        for item in node:
            _walk_next_data(item, found)
    elif isinstance(node, dict):
        if _looks_like_event(node):
            found.append({
                "name": node.get("name") or node.get("title"),
                "startDate": (
                    node.get("startDate")
                    or node.get("start_date")
                    or node.get("date")
                ),
                "url": node.get("url") or node.get("slug"),
                "image": (
                    node.get("image")
                    or node.get("horizontal_cover_image")
                    or node.get("cover_image")
                ),
                "location": {
                    "name": node.get("venue") or node.get("venue_name"),
                },
            })
        for value in node.values():
            _walk_next_data(value, found)


def _looks_like_event(node: dict) -> bool:
    has_name = bool(node.get("name") or node.get("title"))
    has_date = bool(
        node.get("startDate") or node.get("start_date") or node.get("date")
    )
    has_link = bool(node.get("url") or node.get("slug"))
    return has_name and has_date and has_link


# ── small helpers ───────────────────────────────────────────────────────────

def _clean_str(value) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    return text or None


def _iso_date(value) -> str | None:
    text = _clean_str(value)
    if not text:
        return None
    # schema.org startDate is ISO-8601 — keep just the calendar date.
    match = re.match(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None


def _first_image(image) -> str | None:
    if isinstance(image, str):
        return image.strip() or None
    if isinstance(image, dict):
        return _clean_str(image.get("url"))
    if isinstance(image, list):
        for item in image:
            url = _first_image(item)
            if url:
                return url
    return None
