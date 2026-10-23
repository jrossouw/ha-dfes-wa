"""DFES Emergency WA integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import DfesCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.GEO_LOCATION,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DfesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: DfesConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
