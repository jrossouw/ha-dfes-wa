"""Emergency aircraft from community ADS-B feeds (adsb.lol / airplanes.live).

Parses readsb-style JSON and picks out WA emergency aircraft by flight ID
(callsign) or by a user-supplied list of callsigns, registrations and ICAO
hex codes. Kept free of Home Assistant imports so it can be unit tested on
its own.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.parse import quote

from .const import (
    AIRCRAFT_STALE_SECONDS,
    CALLSIGN_PATTERNS,
    ROLE_COLOURS,
    ROLE_HELITACK,
    ROLE_OTHER,
    ROLE_RESCUE,
)

KNOTS_TO_KMH = 1.852

_PATTERNS = tuple((role, re.compile(rx)) for role, rx in CALLSIGN_PATTERNS)


# Top-down silhouettes in a 24x24 box, nose pointing north (up).
_PLANE = (
    '<path d="M12 1.8c.8 0 1.3 1 1.3 2.2v5l8 4.6v2.1l-8-2.5v5.4l2.4 1.8v1.6'
    'l-3.7-1-3.7 1v-1.6l2.4-1.8v-5.4l-8 2.5v-2.1l8-4.6v-5c0-1.2.5-2.2 1.3-2.2z"/>'
)
_HELICOPTER = (
    '<rect x="11.3" y="12.5" width="1.4" height="8.5" rx=".7"/>'
    '<rect x="9.2" y="19.4" width="5.6" height="1.5" rx=".75"/>'
    '<rect x="11.25" y="0.6" width="1.5" height="16.8" rx=".75" transform="rotate(45 12 9)"/>'
    '<rect x="11.25" y="0.6" width="1.5" height="16.8" rx=".75" transform="rotate(-45 12 9)"/>'
    '<ellipse cx="12" cy="9" rx="3.2" ry="4.4"/>'
)
HELICOPTER_ROLES = (ROLE_HELITACK, ROLE_RESCUE)


def marker_svg(role: str | None, heading: float | None) -> str:
    """A data: URI of the aircraft drawn top-down, pointing along its heading.

    Map-card shows an entity's picture with ``display: marker``, so this is
    how the map gets direction-of-flight icons. The heading is rounded to
    10 degrees so the picture only changes when the turn is visible.
    """
    colour = ROLE_COLOURS.get(role or "", ROLE_COLOURS[ROLE_OTHER])
    shape = _HELICOPTER if role in HELICOPTER_ROLES else _PLANE
    angle = 0 if heading is None else (round(heading / 10) * 10) % 360
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<g transform="rotate({angle} 12 12)" fill="{colour}" stroke="#ffffff" '
        f'stroke-width=".8" stroke-linejoin="round">{shape}</g></svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")


class AircraftParseError(Exception):
    """Raised when an ADS-B response cannot be parsed."""


@dataclass(slots=True)
class Aircraft:
    """One aircraft position."""

    hex: str
    latitude: float
    longitude: float
    callsign: str | None = None
    registration: str | None = None
    type_code: str | None = None
    description: str | None = None
    altitude_ft: int | None = None
    on_ground: bool = False
    ground_speed_kt: float | None = None
    track: float | None = None
    vertical_rate_fpm: int | None = None
    squawk: str | None = None
    seen_pos: float | None = None
    role: str | None = None
    distance: float | None = None

    @property
    def external_id(self) -> str:
        return f"aircraft:{self.hex}"

    @property
    def display_name(self) -> str:
        return self.callsign or self.registration or self.hex.upper()

    @property
    def ground_speed_kmh(self) -> int | None:
        if self.ground_speed_kt is None:
            return None
        return round(self.ground_speed_kt * KNOTS_TO_KMH)

    @property
    def picture(self) -> str:
        return marker_svg(self.role, self.track)

    @property
    def link(self) -> str:
        return f"https://globe.adsb.lol/?icao={self.hex}"

    def as_dict(self) -> dict:
        """Plain dict for state attributes and events."""
        return {
            "id": self.external_id,
            "kind": "aircraft",
            "role": self.role,
            "callsign": self.callsign,
            "registration": self.registration,
            "aircraft_type": self.type_code,
            "description": self.description,
            "hex": self.hex,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_ft": self.altitude_ft,
            "on_ground": self.on_ground,
            "ground_speed_kmh": self.ground_speed_kmh,
            "heading": None if self.track is None else round(self.track),
            "vertical_rate_fpm": self.vertical_rate_fpm,
            "squawk": self.squawk,
            "distance_km": None if self.distance is None else round(self.distance, 1),
            "link": self.link,
        }


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _num(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    number = _num(value)
    return None if number is None else int(round(number))


def normalise_ident(value: str) -> str:
    """Upper-case, without spaces or dashes ("VH-RIM" -> "VHRIM")."""
    return re.sub(r"[\s\-]", "", value).upper()


def parse_extra(text: str | None) -> frozenset[str]:
    """Split the user's extra watch-list (commas, semicolons or new lines)."""
    if not text:
        return frozenset()
    parts = re.split(r"[,;\n]+", text)
    return frozenset(normalise_ident(p) for p in parts if p.strip())


def classify(aircraft: Aircraft, extra: frozenset[str] = frozenset()) -> str | None:
    """Return the aircraft's emergency role, or None if it isn't one."""
    callsign = normalise_ident(aircraft.callsign) if aircraft.callsign else None
    if callsign:
        for role, pattern in _PATTERNS:
            if pattern.match(callsign):
                return role
    if extra:
        idents = {aircraft.hex.upper()}
        if callsign:
            idents.add(callsign)
        if aircraft.registration:
            idents.add(normalise_ident(aircraft.registration))
        if idents & extra:
            return ROLE_OTHER
    return None


def _build(item: dict) -> Aircraft | None:
    hex_code = _clean(item.get("hex"))
    lat = _num(item.get("lat"))
    lon = _num(item.get("lon"))
    if hex_code is None or lat is None or lon is None:
        return None
    # "~" marks a non-ICAO (TIS-B) address; keep it, it's still unique.
    hex_code = hex_code.lower()
    seen_pos = _num(item.get("seen_pos"))
    if seen_pos is not None and seen_pos > AIRCRAFT_STALE_SECONDS:
        return None
    alt = item.get("alt_baro")
    on_ground = isinstance(alt, str) and alt.lower() == "ground"
    altitude = 0 if on_ground else _int(alt)
    if altitude is None:
        altitude = _int(item.get("alt_geom"))
    vertical = item.get("baro_rate", item.get("geom_rate"))
    return Aircraft(
        hex=hex_code,
        latitude=lat,
        longitude=lon,
        callsign=_clean(item.get("flight")),
        registration=_clean(item.get("r")),
        type_code=_clean(item.get("t")),
        description=_clean(item.get("desc")),
        altitude_ft=altitude,
        on_ground=on_ground,
        ground_speed_kt=_num(item.get("gs")),
        track=_num(item.get("track", item.get("true_heading"))),
        vertical_rate_fpm=_int(vertical),
        squawk=_clean(item.get("squawk")),
        seen_pos=seen_pos,
    )


def parse_aircraft(raw: str | bytes) -> list[Aircraft]:
    """Parse a readsb/ADSBx v2 response (``{"ac": [...]}``)."""
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as err:
        raise AircraftParseError(f"Not JSON: {err}") from err
    if not isinstance(doc, dict):
        raise AircraftParseError("Unexpected response")
    items = doc.get("ac", doc.get("aircraft"))
    if items is None:
        if "msg" in doc and "No error" not in str(doc.get("msg")):
            raise AircraftParseError(str(doc["msg"]))
        return []
    if not isinstance(items, list):
        raise AircraftParseError("Unexpected 'ac' value")
    result: list[Aircraft] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        aircraft = _build(item)
        if aircraft is None or aircraft.hex in seen:
            continue
        seen.add(aircraft.hex)
        result.append(aircraft)
    return result
