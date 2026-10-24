"""Constants for the DFES Emergency WA integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "dfes_wa"
ATTRIBUTION: Final = "Data provided by DFES / Emergency WA (emergency.wa.gov.au)"

# Default Emergency WA RSS feed URLs. Users can override these in the
# integration options if Emergency WA moves them.
DEFAULT_INCIDENTS_URL: Final = "https://api.emergency.wa.gov.au/v1/rss/incidents"
DEFAULT_WARNINGS_URL: Final = "https://api.emergency.wa.gov.au/v1/rss/warnings"
DEFAULT_FDR_URL: Final = "https://api.emergency.wa.gov.au/v1/rss/fire-danger-ratings"

CONF_INCIDENTS_URL: Final = "incidents_url"
CONF_WARNINGS_URL: Final = "warnings_url"
CONF_FDR_URL: Final = "fdr_url"
CONF_FIRE_DISTRICT: Final = "fire_district"
CONF_RADIUS: Final = "radius"
CONF_ALERT_RADIUS: Final = "alert_radius"
CONF_EXCLUDE_BURN_OFFS: Final = "exclude_burn_offs"
CONF_SHOW_INCIDENTS_ON_MAP: Final = "show_incidents_on_map"
CONF_SHOW_WARNINGS_ON_MAP: Final = "show_warnings_on_map"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_RADIUS: Final = 50.0  # km - incidents/warnings tracked and mapped
DEFAULT_ALERT_RADIUS: Final = 10.0  # km - "fire nearby" binary sensor
DEFAULT_SCAN_INTERVAL: Final = 120  # seconds
MIN_SCAN_INTERVAL: Final = 60

DEFAULT_SCAN_TIMEDELTA: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SOURCE: Final = "dfes_wa"

# Fired once per incident/warning the first time it appears inside the radius.
EVENT_NEW_INCIDENT: Final = f"{DOMAIN}_new_incident"
EVENT_NEW_WARNING: Final = f"{DOMAIN}_new_warning"

# Australian Warning System levels, most to least severe.
LEVEL_EMERGENCY: Final = "Emergency Warning"
LEVEL_WATCH_AND_ACT: Final = "Watch and Act"
LEVEL_ADVICE: Final = "Advice"
SERIOUS_LEVELS: Final = (LEVEL_EMERGENCY, LEVEL_WATCH_AND_ACT)

FIRE_KEYWORDS: Final = ("fire", "burn")

KIND_INCIDENT: Final = "incident"
KIND_WARNING: Final = "warning"

SIGNAL_NEW_ENTRIES: Final = f"{DOMAIN}_new_entries_{{}}"

# -- Emergency aircraft (ADS-B) ---------------------------------------------
# Live positions come from free, unfiltered community ADS-B feeds (readsb JSON).
# The first URL that answers wins; {lat}/{lon}/{radius} are filled in, with the
# radius in nautical miles (both feeds cap it at 250 nm).
ADSB_URLS: Final = (
    "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}",
    "https://api.airplanes.live/v2/point/{lat}/{lon}/{radius}",
)
ADSB_ATTRIBUTION: Final = "Aircraft positions © adsb.lol / airplanes.live contributors (ODbL)"
ADSB_MAX_RADIUS_NM: Final = 250

CONF_TRACK_AIRCRAFT: Final = "track_aircraft"
CONF_AIRCRAFT_RADIUS: Final = "aircraft_radius"
CONF_AIRCRAFT_SCAN_INTERVAL: Final = "aircraft_scan_interval"
CONF_AIRCRAFT_EXTRA: Final = "aircraft_extra"
CONF_SHOW_ALL_AIRCRAFT: Final = "show_all_aircraft"

DEFAULT_AIRCRAFT_RADIUS: Final = 50.0  # km
DEFAULT_AIRCRAFT_SCAN_INTERVAL: Final = 30  # seconds
MIN_AIRCRAFT_SCAN_INTERVAL: Final = 15  # be kind to the free feeds
# Positions older than this are dropped (the feed keeps aircraft for a while
# after they go out of receiver range).
AIRCRAFT_STALE_SECONDS: Final = 60

KIND_AIRCRAFT: Final = "aircraft"
EVENT_AIRCRAFT_SPOTTED: Final = f"{DOMAIN}_aircraft_spotted"

# Roles, and the ADS-B flight IDs (callsigns) WA emergency aircraft use.
# Flight IDs are at most 8 characters, so the spoken callsign is abbreviated:
# "Bomber 611" broadcasts BMBR611, "Firebird 623" FBIR623, and so on.
ROLE_BOMBER: Final = "bomber"
ROLE_HELITACK: Final = "helitack"
ROLE_AIR_ATTACK: Final = "air_attack"
ROLE_RESCUE: Final = "rescue"
ROLE_MEDICAL: Final = "medical"
ROLE_POLICE: Final = "police"
ROLE_OTHER: Final = "other"  # matched only by the user's extra list
ROLE_GENERAL: Final = "general"  # everything else, only with "show all aircraft"

AIRCRAFT_ROLES: Final = (
    ROLE_BOMBER, ROLE_HELITACK, ROLE_AIR_ATTACK, ROLE_RESCUE,
    ROLE_MEDICAL, ROLE_POLICE, ROLE_OTHER, ROLE_GENERAL,
)
# Firefighting roles feed the "Firefighting aircraft nearby" binary sensor.
FIREFIGHTING_ROLES: Final = (ROLE_BOMBER, ROLE_HELITACK, ROLE_AIR_ATTACK)

# (role, regex on the flight ID). Checked in order; first match wins.
CALLSIGN_PATTERNS: Final = (
    (ROLE_BOMBER, r"^(BMBR|BOMB|BOMBER)\d+[A-Z]?$"),
    (ROLE_HELITACK, r"^(HLTK|HTAK|HELTAK|HELITAK|HELITACK)\d+[A-Z]?$"),
    (ROLE_AIR_ATTACK, r"^(FBIR|FIREBIRD|BDOG|BIRDDOG|PKAR|SPTR|SPOTTER|AATK|AIRATK)\d+[A-Z]?$"),
    (ROLE_RESCUE, r"^(RSCU|RESU|RESCUE)\d+[A-Z]?$"),
    (ROLE_MEDICAL, r"^FD\d{3}[A-Z]?$"),  # Royal Flying Doctor Service WA
    (ROLE_POLICE, r"^(POL\d+[A-Z]?|POLAIR\d*)$"),
)

# Marker colours, matching the enhanced dashboard's trail colours.
ROLE_COLOURS: Final = {
    ROLE_BOMBER: "#e65100",
    ROLE_HELITACK: "#c62828",
    ROLE_AIR_ATTACK: "#6a1b9a",
    ROLE_RESCUE: "#1565c0",
    ROLE_MEDICAL: "#1565c0",
    ROLE_POLICE: "#1565c0",
    ROLE_OTHER: "#1565c0",
    ROLE_GENERAL: "#616161",
}

ROLE_ICONS: Final = {
    ROLE_BOMBER: "mdi:airplane",
    ROLE_HELITACK: "mdi:helicopter",
    ROLE_AIR_ATTACK: "mdi:airplane-search",
    ROLE_RESCUE: "mdi:helicopter",
    ROLE_MEDICAL: "mdi:medical-bag",
    ROLE_POLICE: "mdi:police-badge",
    ROLE_OTHER: "mdi:airplane-alert",
    ROLE_GENERAL: "mdi:airplane",
}

# Fire Danger Ratings (Australian Fire Danger Rating System), lowest to highest.
FDR_LEVELS: Final = ("no_rating", "moderate", "high", "extreme", "catastrophic")
FDR_COLOURS: Final = {
    "no_rating": "#ffffff",
    "moderate": "#64bf30",
    "high": "#ffe324",
    "extreme": "#ff6e1e",
    "catastrophic": "#a01e23",
}
# The ratings feed is issued once or twice a day; don't fetch it every poll.
FDR_REFRESH: Final = timedelta(minutes=30)

# WA fire weather districts, as named in the Emergency WA ratings feed.
FIRE_DISTRICTS: Final = (
    "Arthur", "Ashburton Coast", "Ashburton Inland", "Avon", "Blackwood",
    "Brockman", "Burrup", "Capes", "Central Interior", "Central Pilbara",
    "Dampier Derby Coast", "Esperance Coast", "Esperance Inland", "Eucla",
    "Exmouth Gulf Coast", "Fitzgerald", "Gascoyne Coast", "Gascoyne Inland",
    "Geographe", "Hedland", "Karroun", "Kimberley Inland North",
    "Kimberley Inland South", "Lakes", "Lesueur", "Lockwood", "Mid West",
    "Mortlock", "North Goldfields", "North Interior", "North Kimberley",
    "North Midlands", "Perth Inner", "Roe", "Rottnest", "South Goldfields",
    "South Interior", "South Kimberley Coast", "South Murchison",
    "Southern Forests", "Stirling Coast", "Stirling North", "Stirling West",
    "Swan Coastal North", "Swan Coastal South", "Swan Inland North",
    "Swan Inland South", "Watheroo", "West Interior",
)
