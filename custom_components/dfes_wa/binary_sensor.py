"""Binary sensors for DFES Emergency WA."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DfesConfigEntry
from .const import CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS, FIREFIGHTING_ROLES
from .coordinator import DfesCoordinator, DfesData, entry_option
from .entity import DfesAircraftEntity, DfesEntity
from .feed import FeedEntry


@dataclass(frozen=True, kw_only=True)
class DfesBinaryDescription(BinarySensorEntityDescription):
    """Describes a DFES binary sensor."""

    matches_fn: Callable[[DfesData, float], list[FeedEntry]]


def _fires_within(data: DfesData, alert_radius: float) -> list[FeedEntry]:
    return [
        e
        for e in data.incidents
        if e.is_fire and not e.is_burn_off and (e.distance or 0) <= alert_radius
    ]


def _serious_warnings(data: DfesData, _alert_radius: float) -> list[FeedEntry]:
    return [e for e in data.warnings if e.is_serious]


def _home_in_warning(data: DfesData, _alert_radius: float) -> list[FeedEntry]:
    # distance_to() returns 0 when home is inside the warning polygon
    return [e for e in data.warnings if e.polygon and e.distance == 0]


BINARY_SENSORS: tuple[DfesBinaryDescription, ...] = (
    DfesBinaryDescription(
        key="fire_nearby",
        translation_key="fire_nearby",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:fire-alert",
        matches_fn=_fires_within,
    ),
    DfesBinaryDescription(
        key="serious_warning",
        translation_key="serious_warning",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:alert-octagon",
        matches_fn=_serious_warnings,
    ),
    DfesBinaryDescription(
        key="home_in_warning_area",
        translation_key="home_in_warning_area",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:home-alert",
        matches_fn=_home_in_warning,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DfesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        DfesBinarySensor(coordinator, d) for d in BINARY_SENSORS
    ]
    if coordinator.aircraft is not None:
        entities.append(DfesFirefightingAircraftSensor(coordinator.aircraft))
    async_add_entities(entities)


class DfesBinarySensor(DfesEntity, BinarySensorEntity):
    """On when matching incidents/warnings exist."""

    entity_description: DfesBinaryDescription

    def __init__(self, coordinator: DfesCoordinator, description: DfesBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def _alert_radius(self) -> float:
        return float(
            entry_option(self.coordinator.config_entry, CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS)
        )

    def _matches(self) -> list[FeedEntry]:
        data = self.coordinator.data
        if data is None:
            return []
        return self.entity_description.matches_fn(data, self._alert_radius)

    @property
    def is_on(self) -> bool:
        return bool(self._matches())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {"matches": [e.as_dict() for e in self._matches()[:10]]}
        if self.entity_description.key == "fire_nearby":
            attrs["alert_radius_km"] = self._alert_radius
        return attrs


class DfesFirefightingAircraftSensor(DfesAircraftEntity, BinarySensorEntity):
    """On while water bombers, helitacks or air attack aircraft are close.

    Uses the "fire nearby" alert radius, so it means firefighting aircraft
    are working within that distance of the location.
    """

    _attr_translation_key = "firefighting_aircraft_nearby"
    _attr_icon = "mdi:airplane-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "firefighting_aircraft_nearby")

    @property
    def _alert_radius(self) -> float:
        return float(
            entry_option(self.coordinator.config_entry, CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS)
        )

    def _matches(self):
        data = self.coordinator.data
        if data is None:
            return []
        radius = self._alert_radius
        return [
            a for a in data.aircraft
            if a.role in FIREFIGHTING_ROLES and (a.distance or 0) <= radius
        ]

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return bool(self._matches())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "alert_radius_km": self._alert_radius,
            "matches": [
                {k: v for k, v in a.as_dict().items() if v is not None}
                for a in self._matches()[:10]
            ],
        }
