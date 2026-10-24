"""DFES Emergency WA integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SHOW_ALL_AIRCRAFT, CONF_TRACK_AIRCRAFT, DOMAIN
from .coordinator import AircraftCoordinator, DfesCoordinator, entry_option
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.GEO_LOCATION,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

# Options that can change without reloading the entry (the dashboard switch
# for "show all aircraft" flips this one).
LIVE_OPTIONS = frozenset({CONF_SHOW_ALL_AIRCRAFT})

type DfesConfigEntry = ConfigEntry[DfesCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions (once, for all entries)."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DfesConfigEntry) -> bool:
    """Set up DFES Emergency WA from a config entry."""
    coordinator = DfesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    if entry_option(entry, CONF_TRACK_AIRCRAFT, False):
        coordinator.aircraft = AircraftCoordinator(hass, entry, coordinator)
        # Not async_config_entry_first_refresh: an ADS-B outage must never stop
        # incidents and warnings loading. Entities just start out unavailable.
        await coordinator.aircraft.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.options_snapshot = dict(entry.options)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DfesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: DfesConfigEntry) -> None:
    """Reload when options change, unless only a live option changed."""
    coordinator = entry.runtime_data
    new = dict(entry.options)
    old = coordinator.options_snapshot
    changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    coordinator.options_snapshot = new
    if changed and changed <= LIVE_OPTIONS and coordinator.aircraft is not None:
        coordinator.aircraft.set_show_all(bool(new.get(CONF_SHOW_ALL_AIRCRAFT, False)))
        return
    await hass.config_entries.async_reload(entry.entry_id)
