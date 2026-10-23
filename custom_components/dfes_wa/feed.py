"""Parser for the Emergency WA (DFES) GeoRSS feeds.

Kept free of Home Assistant imports so it can be unit tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from datetime import date, datetime
import json
import math
import re
import xml.etree.ElementTree as ET

from .const import (
    FIRE_KEYWORDS,
    KIND_INCIDENT,
    KIND_WARNING,
    LEVEL_ADVICE,
    LEVEL_EMERGENCY,
    LEVEL_WATCH_AND_ACT,
    SERIOUS_LEVELS,
)

_TITLE_RE = re.compile(r"^(?P<type>.+?)\s*\((?P<inner>.+)\)\s*$")
_CAD_RE = re.compile(r"CAD-ID:\s*(\d+)", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


class FeedParseError(Exception):
    """Raised when a feed cannot be parsed."""


@dataclass(slots=True)
class FeedEntry:
    """A single incident or warning."""

    kind: str
    external_id: str
    title: str
    category: str
    latitude: float
    longitude: float
    link: str | None = None
    published: datetime | None = None
    suburb: str | None = None
    lga: str | None = None
    region: str | None = None
    incident_number: str | None = None
    alert_level: str | None = None
    polygon: list[tuple[float, float]] = field(default_factory=list)
    distance: float | None = None

    @property
    def is_fire(self) -> bool:
        """Return True if this looks like a fire (incl. burn offs)."""
        text = f"{self.category} {self.title}".lower()
        return any(word in text for word in FIRE_KEYWORDS)

    @property
    def is_burn_off(self) -> bool:
        """Return True for planned burn offs / prescribed burns."""
        text = self.category.lower()
        return "burn off" in text or "prescribed burn" in text

    @property
    def is_serious(self) -> bool:
        """Return True for Watch and Act or Emergency Warning."""
        return self.alert_level in SERIOUS_LEVELS

    @property
    def display_name(self) -> str:
        """Short human friendly name, e.g. 'Bushfire - Muchea'."""
        if self.kind == KIND_INCIDENT and self.suburb:
            return f"{self.category} - {self.suburb}"
        return self.title

    @property
    def geojson(self) -> dict | None:
        """The affected area as a GeoJSON Feature (for map cards), if any."""
        if len(self.polygon) < 3:
            return None
        ring = [[round(lon, 6), round(lat, 6)] for lat, lon in self.polygon]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "name": self.display_name,
                "alert_level": self.alert_level,
            },
        }

    def as_dict(self) -> dict:
        """Serialisable summary used in sensor attributes and events."""
        return {
            "id": self.external_id,
            "kind": self.kind,
            "type": self.category,
            "title": self.title,
            "suburb": self.suburb,
            "lga": self.lga,
            "region": self.region,
            "incident_number": self.incident_number,
            "alert_level": self.alert_level,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_km": None if self.distance is None else round(self.distance, 1),
            "link": self.link,
            "published": self.published.isoformat() if self.published else None,
        }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _local(tag: str) -> str:
    """Strip an XML namespace: '{uri}lat' -> 'lat'."""
    return tag.rsplit("}", 1)[-1]


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    value = el.text.strip()
    return value or None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _title_case(value: str | None) -> str | None:
    if not value:
        return value
    # "SHIRE OF DERBY/WEST KIMBERLEY" -> "Shire Of Derby/West Kimberley"
    return value.strip().title()


def _parse_polygon(value: str | None) -> list[tuple[float, float]]:
    """GeoRSS polygon: space separated 'lat,lon' pairs (or flat lat lon list)."""
    if not value:
        return []
    points: list[tuple[float, float]] = []
    tokens = value.replace("\n", " ").split()
    if tokens and "," in tokens[0]:
        for token in tokens:
            lat, _, lon = token.partition(",")
            flat, flon = _float(lat), _float(lon)
            if flat is not None and flon is not None:
                points.append((flat, flon))
    else:
        nums = [_float(t) for t in tokens]
        for i in range(0, len(nums) - 1, 2):
            if nums[i] is not None and nums[i + 1] is not None:
                points.append((nums[i], nums[i + 1]))
    return points


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def _alert_level(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    if "emergency warning" in blob:
        return LEVEL_EMERGENCY
    if "watch and act" in blob or "watch & act" in blob:
        return LEVEL_WATCH_AND_ACT
    if "advice" in blob:
        return LEVEL_ADVICE
    return None


def _parse_incident_title(title: str) -> dict[str, str | None]:
    """'Bushfire (MUCHEA, SHIRE OF CHITTERING, METRO NORTH EAST, CAD-ID: 825904)'."""
    result: dict[str, str | None] = {
        "category": title,
        "suburb": None,
        "lga": None,
        "region": None,
        "cad": None,
    }
    match = _TITLE_RE.match(title)
    if not match:
        return result
    result["category"] = match.group("type").strip()
    inner = match.group("inner")
    if cad := _CAD_RE.search(inner):
        result["cad"] = cad.group(1)
        inner = inner[: cad.start()]
    parts = [p.strip() for p in inner.split(",") if p.strip()]
    if parts:
        result["suburb"] = _title_case(parts[0])
    if len(parts) > 1:
        lga = parts[1]
        result["lga"] = None if lga.lower() == "unknown lga" else _title_case(lga)
    if len(parts) > 2:
        result["region"] = _title_case(parts[2])
    return result


def _description_tag(description: str | None, tag: str) -> str | None:
    """Pull '<region>X</region>' style values out of an escaped description."""
    if not description:
        return None
    match = re.search(rf"<{tag}>(.*?)</{tag}>", description, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _TAG_RE.sub("", match.group(1)).strip() or None


def _clean_body(raw: str | bytes) -> bytes:
    """Strip BOMs, NULs and whitespace that would trip the XML parser."""
    data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
    data = data.replace(b"\x00", b"")
    for bom in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):
        if data.startswith(bom):
            data = data[len(bom):]
    return data.strip()


def _xml_items(data: bytes) -> list[dict[str, str | None]]:
    """Flatten each <item>/<entry> into {local tag name: text}."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as err:
        raise FeedParseError(f"Invalid XML: {err}") from err
    items: list[dict[str, str | None]] = []
    for item in root.iter():
        if _local(item.tag) not in ("item", "entry"):
            continue
        fields: dict[str, str | None] = {}
        for child in item:
            name = _local(child.tag)
            if name in fields:
                continue
            value = _text(child)
            if value is None and name == "link":
                value = child.get("href")
            fields[name] = value
        items.append(fields)
    return items


def _json_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("#text", value.get("href"))
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip() or None
    return None


def _find_json_items(node) -> list | None:
    """Locate the item list in an RSS-as-JSON document (xmltodict style)."""
    if isinstance(node, dict):
        for key in ("item", "items", "entry", "entries", "features"):
            if key in node:
                found = node[key]
                return found if isinstance(found, list) else [found]
        for value in node.values():
            if (found := _find_json_items(value)) is not None:
                return found
    elif isinstance(node, list) and node and all(isinstance(i, dict) for i in node):
        return node
    return None


def _json_items(data: bytes) -> list[dict[str, str | None]]:
    try:
        doc = json.loads(data)
    except ValueError as err:
        raise FeedParseError(f"Invalid JSON: {err}") from err
    raw_items = _find_json_items(doc)
    if raw_items is None:
        raise FeedParseError("JSON response has no items")
    items: list[dict[str, str | None]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        fields: dict[str, str | None] = {}
        for key, value in raw.items():
            name = key.lstrip("@").rsplit(":", 1)[-1]
            fields.setdefault(name, _json_text(value))
        items.append(fields)
    return items


def parse_feed(raw: str | bytes, kind: str) -> list[FeedEntry]:
    """Parse an Emergency WA feed (RSS/Atom XML, or the same as JSON).

    Entries without any usable location are skipped.
    """
    data = _clean_body(raw)
    if not data:
        raise FeedParseError("Empty response")
    if data[:1] in (b"{", b"["):
        items = _json_items(data)
    else:
        # Skip anything before the first tag (e.g. stray text or a script prefix)
        lt = data.find(b"<")
        if lt == -1:
            raise FeedParseError("Response is neither XML nor JSON")
        items = _xml_items(data[lt:])
    return [e for e in (_build_entry(f, kind) for f in items) if e is not None]


def _build_entry(c: dict[str, str | None], kind: str) -> FeedEntry | None:
    title = c.get("title") or ""
    link = c.get("link")
    guid = c.get("guid") or c.get("id") or link or title
    description = c.get("description") or c.get("summary")

    polygon = _parse_polygon(c.get("polygon"))
    lat = _float(c.get("lat"))
    lon = _float(c.get("long") or c.get("lon"))
    if (lat is None or lon is None) and (point := c.get("point")):
        bits = point.split()
        if len(bits) == 2:
            lat, lon = _float(bits[0]), _float(bits[1])
    if (lat is None or lon is None) and (centre := _centroid(polygon)):
        lat, lon = centre
    if lat is None or lon is None:
        return None

    published = _date(c.get("publicationTime") or c.get("pubDate")) or _date(
        _description_tag(description, "publicationTime")
    )

    if kind == KIND_INCIDENT:
        info = _parse_incident_title(title)
        region = info["region"] or _title_case(
            c.get("region") or _description_tag(description, "region")
        )
        return FeedEntry(
            kind=kind,
            external_id=guid,
            title=title,
            category=info["category"] or title,
            latitude=lat,
            longitude=lon,
            link=link,
            published=published,
            suburb=info["suburb"],
            lga=info["lga"],
            region=region,
            incident_number=info["cad"]
            or c.get("incidentNumber")
            or _description_tag(description, "incidentNumber"),
            polygon=polygon,
        )

    level = c.get("alertLevel") or _alert_level(title)
    # Title looks like "Bushfire Advice MONITOR CONDITIONS - ORD RIVER"
    category = title.split(" - ")[0].strip() if title else "Warning"
    return FeedEntry(
        kind=KIND_WARNING,
        external_id=guid,
        title=title,
        category=category,
        latitude=lat,
        longitude=lon,
        link=link,
        published=published,
        region=_title_case(c.get("region")),
        incident_number=c.get("incidentNumber"),
        alert_level=level,
        polygon=polygon,
    )


def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test (polygon as (lat, lon) pairs)."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def distance_to(entry: FeedEntry, lat: float, lon: float) -> float:
    """Distance from home to an entry; 0 if home is inside its polygon."""
    if entry.polygon and point_in_polygon(lat, lon, entry.polygon):
        return 0.0
    distances = [haversine_km(lat, lon, entry.latitude, entry.longitude)]
    distances.extend(haversine_km(lat, lon, p[0], p[1]) for p in entry.polygon)
    return min(distances)


# ---------------------------------------------------------------------------
# Fire Danger Ratings
# ---------------------------------------------------------------------------

_FDR_HEADING_RE = re.compile(
    r"\b(no|moderate|high|extreme|catastrophic)\s+fire\s+danger\s+ratings?\b",
    re.IGNORECASE,
)
_FDR_TOKEN_RE = re.compile(
    r"<(?:strong|b|h[1-6])[^>]*>(?P<head>.*?)</(?:strong|b|h[1-6])>|<li[^>]*>(?P<li>.*?)</li>",
    re.IGNORECASE | re.DOTALL,
)
_FDR_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2},? \d{4})")
_FDR_DATE_DMY_RE = re.compile(r"(\d{1,2} [A-Z][a-z]+ \d{4})")


@dataclass(slots=True)
class FdrForecast:
    """Fire Danger Ratings by day and district (district names lower-cased)."""

    days: dict[date, dict[str, str]] = field(default_factory=dict)
    issued: datetime | None = None

    def rating(self, district: str, day: date) -> str | None:
        """Rating key (e.g. 'high') for a district on a day, if forecast."""
        return self.days.get(day, {}).get(district.strip().lower())


def _strip_html(value: str) -> str:
    text = _TAG_RE.sub(" ", value)
    text = (
        text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'")
    )
    return " ".join(text.split())


def _fdr_day(title: str, description: str) -> date | None:
    for regex, formats in (
        (_FDR_DATE_RE, ("%B %d, %Y", "%B %d %Y")),
        (_FDR_DATE_DMY_RE, ("%d %B %Y",)),
    ):
        for source in (title, _strip_html(description)):
            if match := regex.search(source):
                for fmt in formats:
                    try:
                        return datetime.strptime(match.group(1), fmt).date()
                    except ValueError:
                        continue
    return None


def parse_fdr(raw: str | bytes) -> FdrForecast:
    """Parse the Emergency WA Fire Danger Ratings feed.

    Each item is one day. Its description lists districts under headings such
    as "High Fire Danger Ratings have been forecast for ...".
    """
    data = _clean_body(raw)
    if not data:
        raise FeedParseError("Empty response")
    lt = data.find(b"<")
    if lt == -1:
        raise FeedParseError("Response is not XML")
    forecast = FdrForecast()
    for item in _xml_items(data[lt:]):
        title = item.get("title") or ""
        description = item.get("description") or ""
        day = _fdr_day(title, description)
        if day is None:
            continue
        issued = _date(item.get("publicationTime") or item.get("pubDate"))
        if issued and (forecast.issued is None or issued > forecast.issued):
            forecast.issued = issued
        ratings: dict[str, str] = {}
        current: str | None = None
        for token in _FDR_TOKEN_RE.finditer(description):
            if token.group("head") is not None:
                match = _FDR_HEADING_RE.search(_strip_html(token.group("head")))
                if match:
                    level = match.group(1).lower()
                    current = "no_rating" if level == "no" else level
                continue
            if current and (name := _strip_html(token.group("li") or "")):
                ratings[name.lower()] = current
        if ratings:
            forecast.days[day] = ratings
    if not forecast.days:
        raise FeedParseError("No fire danger ratings found")
    return forecast
