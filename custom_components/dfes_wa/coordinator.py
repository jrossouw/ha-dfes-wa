"""Data update coordinator for DFES Emergency WA."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXCLUDE_BURN_OFFS,
    CONF_FDR_URL,
    CONF_FIRE_DISTRICT,
    DEFAULT_FDR_URL,
    FDR_REFRESH,
    CONF_INCIDENTS_URL,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_WARNINGS_URL,
    DEFAULT_INCIDENTS_URL,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WARNINGS_URL,
    DOMAIN,
    EVENT_NEW_INCIDENT,
    EVENT_NEW_WARNING,
    KIND_INCIDENT,
    KIND_WARNING,
)
from .feed import FdrForecast, FeedEntry, FeedParseError, distance_to, parse_fdr, parse_feed

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


@dataclass(slots=True)
class DfesData:
    """Everything one refresh produced."""

    incidents: list[FeedEntry] = field(default_factory=list)
    warnings: list[FeedEntry] = field(default_factory=list)
    all_incident_count: int = 0
    all_warning_count: int = 0
    fdr: FdrForecast | None = None

    def get(self, external_id: str) -> FeedEntry | None:
        """Find an entry by id."""
        for entry in (*self.incidents, *self.warnings):
            if entry.external_id == external_id:
                return entry
        return None


# Placeholder feed URLs shipped in early builds. They serve the Emergency WA
# website, not a feed, so any entry that saved them falls back to the default.
LEGACY_FEED_URLS = {
    "https://www.emergency.wa.gov.au/data/incidents.rss",
    "https://www.emergency.wa.gov.au/data/warnings.rss",
}


def entry_option(entry: ConfigEntry, key: str, default):
    """Options override data, which overrides the default."""
    value = entry.options.get(key, entry.data.get(key, default))
    if isinstance(value, str) and value.strip() in LEGACY_FEED_URLS:
        return default
    return value


class DfesCoordinator(DataUpdateCoordinator[DfesData]):
    """Fetches both feeds and filters them to the configured area."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise."""
        scan = int(entry_option(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(seconds=scan),
        )
        self._session = async_get_clientsession(hass)
        self._seen: set[str] | None = None  # None until the first refresh
        # Incident/warning picked on the map (see the select_pin action).
        self.selected_id: str | None = None
        self.selected_pin: str | None = None
        self._fdr: FdrForecast | None = None
        self._fdr_fetched: datetime | None = None

    @callback
    def select(self, external_id: str | None, pin: str | None = None) -> None:
        """Remember (or clear) the map pin the user picked, and tell entities."""
        if (external_id, pin) == (self.selected_id, self.selected_pin):
            return
        self.selected_id = external_id
        self.selected_pin = pin if external_id else None
        self.async_update_listeners()

    # -- config helpers -------------------------------------------------
    @property
    def latitude(self) -> float:
        return float(entry_option(self.config_entry, CONF_LATITUDE, self.hass.config.latitude))

    @property
    def longitude(self) -> float:
        return float(entry_option(self.config_entry, CONF_LONGITUDE, self.hass.config.longitude))

    @property
    def radius(self) -> float:
        return float(entry_option(self.config_entry, CONF_RADIUS, DEFAULT_RADIUS))

    @property
    def fire_district(self) -> str | None:
        value = entry_option(self.config_entry, CONF_FIRE_DISTRICT, None)
        return value or None

    @property
    def exclude_burn_offs(self) -> bool:
        return bool(entry_option(self.config_entry, CONF_EXCLUDE_BURN_OFFS, False))

    # -- fetching -------------------------------------------------------
    async def _get(self, url: str, kind: str) -> tuple[bytes, str]:
        # Use Home Assistant's default headers - the same request the built-in
        # REST integration makes, which Emergency WA is known to answer.
        try:
            async with self._session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                return await resp.read(), resp.headers.get("Content-Type", "")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error fetching {kind} feed: {err}") from err

    async def _fetch(self, url: str, kind: str) -> list[FeedEntry]:
        body, content_type = await self._get(url, kind)
        try:
            return await self.hass.async_add_executor_job(parse_feed, body, kind)
        except FeedParseError as err:
            snippet = body[:300].decode("utf-8", "replace")
            _LOGGER.warning(
                "Could not parse the %s feed from %s (Content-Type %r, %s bytes). "
                "Start of response: %r",
                kind,
                url,
                content_type,
                len(body),
                snippet,
            )
            raise UpdateFailed(f"Could not parse {kind} feed: {err}") from err

    def _filter(self, entries: list[FeedEntry]) -> list[FeedEntry]:
        lat, lon, radius = self.latitude, self.longitude, self.radius
        kept: list[FeedEntry] = []
        for entry in entries:
            if self.exclude_burn_offs and entry.is_burn_off:
                continue
            entry.distance = distance_to(entry, lat, lon)
            if entry.distance <= radius:
                kept.append(entry)
        kept.sort(key=lambda e: e.distance or 0)
        return kept

    async def _async_update_data(self) -> DfesData:
        incidents_url = entry_option(self.config_entry, CONF_INCIDENTS_URL, DEFAULT_INCIDENTS_URL)
        warnings_url = entry_option(self.config_entry, CONF_WARNINGS_URL, DEFAULT_WARNINGS_URL)

        incidents_raw, warnings_raw = await asyncio.gather(
            self._fetch(incidents_url, KIND_INCIDENT),
            self._fetch(warnings_url, KIND_WARNING),
        )

        data = DfesData(
            incidents=self._filter(incidents_raw),
            warnings=self._filter(warnings_raw),
            all_incident_count=len(incidents_raw),
            all_warning_count=len(warnings_raw),
            fdr=await self._async_fdr(),
        )
        _LOGGER.debug(
            "Fetched %s incidents / %s warnings statewide; %s / %s within %s km",
            data.all_incident_count,
            data.all_warning_count,
            len(data.incidents),
            len(data.warnings),
            self.radius,
        )
        self._fire_new_entry_events(data, incidents_raw, warnings_raw)
        return data

    async def _async_fdr(self) -> FdrForecast | None:
        """Fire Danger Ratings, refreshed every FDR_REFRESH.

        A failure here never fails the whole update: the last good forecast
        is kept and the incident/warning entities carry on.
        """
        if self.fire_district is None:
            return None
        now = dt_util.utcnow()
        if (
            self._fdr is not None
            and self._fdr_fetched is not None
            and now - self._fdr_fetched < FDR_REFRESH
        ):
            return self._fdr
        url = entry_option(self.config_entry, CONF_FDR_URL, DEFAULT_FDR_URL)
        try:
            body, _ = await self._get(url, "fire danger rating")
            self._fdr = await self.hass.async_add_executor_job(parse_fdr, body)
            self._fdr_fetched = now
        except (UpdateFailed, FeedParseError) as err:
            _LOGGER.warning("Could not update fire danger ratings: %s", err)
        return self._fdr

    def _fire_new_entry_events(
        self, data: DfesData, incidents: list[FeedEntry], warnings: list[FeedEntry]
    ) -> None:
        """Fire an event for each incident/warning seen for the first time.

        Events cover the whole state, so automations can alert on incidents
        near a person wherever they are; ``in_radius`` says whether it is
        within the configured tracking radius of this location. Nothing is
        fired on the first refresh after startup, so a restart doesn't
        re-announce everything that's already active.
        """
        everything = [
            e for e in (*incidents, *warnings)
            if not (self.exclude_burn_offs and e.is_burn_off)
        ]
        current = {e.external_id for e in everything}
        if self._seen is None:
            self._seen = current
            return
        in_radius = {e.external_id for e in (*data.incidents, *data.warnings)}
        for entry in everything:
            if entry.external_id in self._seen:
                continue
            if entry.distance is None:
                entry.distance = distance_to(entry, self.latitude, self.longitude)
            event = EVENT_NEW_INCIDENT if entry.kind == KIND_INCIDENT else EVENT_NEW_WARNING
            payload = entry.as_dict()
            payload["config_entry_id"] = self.config_entry.entry_id
            payload["in_radius"] = entry.external_id in in_radius
            payload["is_fire"] = entry.is_fire
            payload["is_burn_off"] = entry.is_burn_off
            self.hass.bus.async_fire(event, payload)
        # Remember everything currently active; forget things that cleared so a
        # re-opened incident would alert again.
        self._seen = current
