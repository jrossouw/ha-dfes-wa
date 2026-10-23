"""Map pins for DFES incidents and warnings.

Every incident/warning inside the configured radius becomes a geo_location
entity, which the built-in Map card and Map panel show automatically. Pins
are added and removed as incidents appear and clear.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DfesConfigEntry
from .const import (
    ATTRIBUTION,
    CONF_SHOW_INCIDENTS_ON_MAP,
    CONF_SHOW_WARNINGS_ON_MAP,
    KIND_INCIDENT,
    SOURCE,
)
from .coordinator import DfesCoordinator, entry_option
from .feed import FeedEntry

ICONS = {
    "bushfire": "mdi:pine-tree-fire",
    "burn off": "mdi:campfire",
    "structure fire": "mdi:home-alert",
    "vehicle fire": "mdi:car-emergency",
    "fire": "mdi:fire",
    "road crash": "mdi:car-wrench",
    "active alarm": "mdi:alarm-light",
    "hazmat": "mdi:biohazard",
    "storm": "mdi:weather-lightning-rainy",
    "flood": "mdi:home-flood",
    "cyclone": "mdi:weather-hurricane",
}


def icon_for(entry: FeedEntry) -> str:
    """Pick an icon from the incident type."""
    if entry.kind != KIND_INCIDENT:
        if entry.is_serious:
            return "mdi:alert-octagon"
        return "mdi:alert"
    category = entry.category.lower()
    for key, icon in ICONS.items():
        if key in category:
            return icon
    return "mdi:alert-circle"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DfesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up geo_location entities, adding/removing them as the feed changes."""
    coordinator = entry.runtime_data
    show_incidents = entry_option(entry, CONF_SHOW_INCIDENTS_ON_MAP, True)
    show_warnings = entry_option(entry, CONF_SHOW_WARNINGS_ON_MAP, True)
    tracked: dict[str, DfesGeolocationEvent] = {}

    @callback
    def _sync() -> None:
        data = coordinator.data
        if data is None:
            return
        wanted: list[FeedEntry] = []
        if show_incidents:
            wanted.extend(data.incidents)
        if show_warnings:
            wanted.extend(data.warnings)
        wanted_ids = {e.external_id for e in wanted}

        for external_id in list(tracked):
            if external_id not in wanted_ids:
                tracked.pop(external_id).async_remove_self()

        new_entities = []
        for feed_entry in wanted:
            if feed_entry.external_id not in tracked:
                entity = DfesGeolocationEvent(coordinator, feed_entry.external_id)
                tracked[feed_entry.external_id] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class DfesGeolocationEvent(CoordinatorEntity[DfesCoordinator], GeolocationEvent):
    """One incident or warning on the map."""

    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_attribution = ATTRIBUTION
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(self, coordinator: DfesCoordinator, external_id: str) -> None:
        super().__init__(coordinator)
        self._external_id = external_id
        # Not registered: these come and go with the feed.
        self._attr_unique_id = None
        self._removed = False

    @property
    def _entry(self) -> FeedEntry | None:
        data = self.coordinator.data
        return data.get(self._external_id) if data else None

    @callback
    def async_remove_self(self) -> None:
        """Remove this pin once its incident has cleared."""
        if self._removed or self.hass is None:
            return
        self._removed = True
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @property
    def available(self) -> bool:
        return super().available and self._entry is not None

    @property
    def name(self) -> str | None:
        entry = self._entry
        return entry.display_name if entry else None

    @property
    def icon(self) -> str | None:
        entry = self._entry
        return icon_for(entry) if entry else None

    @property
    def latitude(self) -> float | None:
        entry = self._entry
        return entry.latitude if entry else None

    @property
    def longitude(self) -> float | None:
        entry = self._entry
        return entry.longitude if entry else None

    @property
    def distance(self) -> float | None:
        entry = self._entry
        return None if entry is None or entry.distance is None else round(entry.distance, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self._entry
        if entry is None:
            return {}
        attrs = entry.as_dict()
        # latitude/longitude/distance are already standard geo_location attributes
        for key in ("latitude", "longitude", "distance_km", "title"):
            attrs.pop(key, None)
        attrs["external_id"] = attrs.pop("id")
        # Affected area, e.g. for map-card's `geojson: {attribute: geojson}`
        attrs["geojson"] = entry.geojson
        return {k: v for k, v in attrs.items() if v is not None}
