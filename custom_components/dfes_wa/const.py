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
