"""Actions for DFES Emergency WA: pick an incident on the map."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SOURCE
from .coordinator import DfesCoordinator

SERVICE_SELECT_PIN = "select_pin"
SERVICE_CLEAR_SELECTION = "clear_selection"
ATTR_PIN = "pin"

SELECT_PIN_SCHEMA = vol.Schema({vol.Required(ATTR_PIN): cv.entity_id})
CLEAR_SELECTION_SCHEMA = vol.Schema({})


def _coordinators(hass: HomeAssistant) -> list[DfesCoordinator]:
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register select_pin and clear_selection."""

    async def _select_pin(call: ServiceCall) -> None:
        pin: str = call.data[ATTR_PIN]
        state = hass.states.get(pin)
        if state is None or state.attributes.get("source") != SOURCE:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_a_pin",
                translation_placeholders={"pin": pin},
            )
        external_id = state.attributes.get("external_id")
        # Every location that can see this incident shows it; the rest clear.
        for coordinator in _coordinators(hass):
            data = coordinator.data
            if external_id and data is not None and data.get(external_id):
                coordinator.select(external_id, pin)
            else:
                coordinator.select(None)

    async def _clear_selection(call: ServiceCall) -> None:
        for coordinator in _coordinators(hass):
            coordinator.select(None)

    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_PIN, _select_pin, schema=SELECT_PIN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_SELECTION, _clear_selection, schema=CLEAR_SELECTION_SCHEMA
    )
