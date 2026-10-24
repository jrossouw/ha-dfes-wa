"""Switch for DFES Emergency WA: show all aircraft, or emergency aircraft only."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DfesConfigEntry
from .const import CONF_SHOW_ALL_AIRCRAFT
from .coordinator import AircraftCoordinator
from .entity import DfesAircraftEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DfesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the switch when emergency aircraft tracking is on."""
    aircraft = entry.runtime_data.aircraft
    if aircraft is not None:
        async_add_entities([DfesShowAllAircraftSwitch(aircraft)])


class DfesShowAllAircraftSwitch(DfesAircraftEntity, SwitchEntity):
    """Map every aircraft in range, or only emergency aircraft.

    The same setting as "Show all aircraft" in the integration options; this
    switch saves it there, and the change applies without reloading.
    """

    _attr_translation_key = "show_all_aircraft"
    _attr_icon = "mdi:airplane-search"

    def __init__(self, coordinator: AircraftCoordinator) -> None:
        super().__init__(coordinator, "show_all_aircraft")

    @property
    def available(self) -> bool:
        # Usable even while the ADS-B feed is down.
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.show_all

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._save(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._save(False)

    def _save(self, value: bool) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_SHOW_ALL_AIRCRAFT: value}
        )
        # The update listener applies it to the coordinator straight away.
        self.coordinator.set_show_all(value)
        self.async_write_ha_state()
