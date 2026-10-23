"""Summary sensors for DFES Emergency WA."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DfesConfigEntry
from .const import FDR_COLOURS, FDR_LEVELS
from .coordinator import DfesData
from .entity import DfesEntity
from .feed import FeedEntry

MAX_LISTED = 25  # keep attributes well under the recorder's 16 KB limit


def _nearest(entries: list[FeedEntry]) -> FeedEntry | None:
    return entries[0] if entries else None  # already sorted by distance


def _fires(data: DfesData) -> list[FeedEntry]:
    return [e for e in data.incidents if e.is_fire and not e.is_burn_off]


def _list_attrs(entries: list[FeedEntry], key: str) -> dict[str, Any]:
    return {key: [e.as_dict() for e in entries[:MAX_LISTED]]}


def _nearest_attrs(entry: FeedEntry | None) -> dict[str, Any]:
    if entry is None:
        return {}
    return {k: v for k, v in entry.as_dict().items() if v is not None}


@dataclass(frozen=True, kw_only=True)
class DfesSensorDescription(SensorEntityDescription):
    """Describes a DFES sensor."""

    value_fn: Callable[[DfesData], Any]
    attrs_fn: Callable[[DfesData], dict[str, Any]]


SENSORS: tuple[DfesSensorDescription, ...] = (
    DfesSensorDescription(
        key="incidents",
        translation_key="incidents",
        icon="mdi:fire-alert",
        native_unit_of_measurement="incidents",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.incidents),
        attrs_fn=lambda d: _list_attrs(d.incidents, "incidents"),
    ),
    DfesSensorDescription(
        key="warnings",
        translation_key="warnings",
        icon="mdi:alert",
        native_unit_of_measurement="warnings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.warnings),
        attrs_fn=lambda d: _list_attrs(d.warnings, "warnings"),
    ),
    DfesSensorDescription(
        key="nearest_incident",
        translation_key="nearest_incident",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=lambda d: (n := _nearest(d.incidents)) and round(n.distance or 0, 1),
        attrs_fn=lambda d: _nearest_attrs(_nearest(d.incidents)),
    ),
    DfesSensorDescription(
        key="nearest_fire",
        translation_key="nearest_fire",
        icon="mdi:fire",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=lambda d: (n := _nearest(_fires(d))) and round(n.distance or 0, 1),
        attrs_fn=lambda d: _nearest_attrs(_nearest(_fires(d))),
    ),
    DfesSensorDescription(
        key="nearest_warning",
        translation_key="nearest_warning",
        icon="mdi:alert-circle",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=lambda d: (n := _nearest(d.warnings)) and round(n.distance or 0, 1),
        attrs_fn=lambda d: _nearest_attrs(_nearest(d.warnings)),
    ),
    DfesSensorDescription(
        key="statewide_incidents",
        translation_key="statewide_incidents",
        icon="mdi:map",
        native_unit_of_measurement="incidents",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.all_incident_count,
        attrs_fn=lambda d: {},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DfesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [DfesSensor(coordinator, desc) for desc in SENSORS]
    entities.append(DfesSelectedSensor(coordinator))
    if coordinator.fire_district:
        entities.append(DfesFireDangerSensor(coordinator, 0))
        entities.append(DfesFireDangerSensor(coordinator, 1))
    async_add_entities(entities)


class DfesSensor(DfesEntity, SensorEntity):
    """A DFES summary sensor."""

    entity_description: DfesSensorDescription

    def __init__(self, coordinator, description: DfesSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data
        return None if data is None else self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs = {} if data is None else self.entity_description.attrs_fn(data)
        if self.entity_description.key in ("incidents", "warnings"):
            # Lets dashboards show "within N km" from the current setting
            attrs["radius_km"] = self.coordinator.radius
        return attrs


class DfesSelectedSensor(DfesEntity, SensorEntity):
    """The incident or warning last picked on the map (dfes_wa.select_pin).

    State is the incident's name, "Cleared" once it has left the feed, or
    unknown when nothing is selected. Details are in the attributes.
    """

    _attr_translation_key = "selected"
    _attr_icon = "mdi:map-marker-check"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "selected")

    def _entry(self) -> FeedEntry | None:
        data = self.coordinator.data
        selected = self.coordinator.selected_id
        if data is None or selected is None:
            return None
        return data.get(selected)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.selected_id is None:
            return None
        entry = self._entry()
        if entry is None:
            return "Cleared"
        return entry.display_name[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.selected_id is None:
            return {}
        attrs: dict[str, Any] = {"pin": self.coordinator.selected_pin}
        entry = self._entry()
        if entry is None:
            attrs["cleared"] = True
            return attrs
        attrs.update({k: v for k, v in entry.as_dict().items() if v is not None})
        return attrs


class DfesFireDangerSensor(DfesEntity, SensorEntity):
    """Fire Danger Rating for the configured fire weather district."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(FDR_LEVELS)

    def __init__(self, coordinator, day_offset: int) -> None:
        key = "fire_danger_today" if day_offset == 0 else "fire_danger_tomorrow"
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._day_offset = day_offset

    def _day(self) -> date:
        return dt_util.now().date() + timedelta(days=self._day_offset)

    def _rating(self) -> str | None:
        data = self.coordinator.data
        district = self.coordinator.fire_district
        if data is None or data.fdr is None or not district:
            return None
        return data.fdr.rating(district, self._day())

    @property
    def native_value(self) -> str | None:
        return self._rating()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rating = self._rating()
        data = self.coordinator.data
        attrs: dict[str, Any] = {
            "district": self.coordinator.fire_district,
            "date": self._day().isoformat(),
        }
        if rating is not None:
            attrs["level"] = FDR_LEVELS.index(rating)
            attrs["colour"] = FDR_COLOURS[rating]
        if data is not None and data.fdr is not None and data.fdr.issued:
            attrs["issued"] = data.fdr.issued.isoformat()
        return attrs
