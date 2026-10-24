"""Config flow for DFES Emergency WA."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME, CONF_RADIUS as HA_CONF_RADIUS
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AIRCRAFT_EXTRA,
    CONF_AIRCRAFT_RADIUS,
    CONF_AIRCRAFT_SCAN_INTERVAL,
    CONF_SHOW_ALL_AIRCRAFT,
    CONF_TRACK_AIRCRAFT,
    DEFAULT_AIRCRAFT_RADIUS,
    DEFAULT_AIRCRAFT_SCAN_INTERVAL,
    MIN_AIRCRAFT_SCAN_INTERVAL,
    CONF_ALERT_RADIUS,
    CONF_EXCLUDE_BURN_OFFS,
    CONF_FDR_URL,
    CONF_FIRE_DISTRICT,
    DEFAULT_FDR_URL,
    FIRE_DISTRICTS,
    CONF_INCIDENTS_URL,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_INCIDENTS_ON_MAP,
    CONF_SHOW_WARNINGS_ON_MAP,
    CONF_WARNINGS_URL,
    DEFAULT_ALERT_RADIUS,
    DEFAULT_INCIDENTS_URL,
    DEFAULT_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WARNINGS_URL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

# Rough bounding box for WA (plus a margin) to catch swapped lat/long.
WA_LAT = (-36.5, -13.0)
WA_LON = (112.0, 130.0)


def _km(min_: float, max_: float, step: float = 1) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_, max=max_, step=step, unit_of_measurement="km",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _district_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(FIRE_DISTRICTS),
            mode=selector.SelectSelectorMode.DROPDOWN,
            sort=True,
        )
    )


def _district_field(defaults: dict[str, Any]):
    if current := defaults.get(CONF_FIRE_DISTRICT):
        return vol.Optional(CONF_FIRE_DISTRICT, description={"suggested_value": current})
    return vol.Optional(CONF_FIRE_DISTRICT)


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _district_field(defaults): _district_selector(),
            vol.Required(CONF_RADIUS, default=defaults.get(CONF_RADIUS, DEFAULT_RADIUS)): _km(1, 2500),
            vol.Required(
                CONF_ALERT_RADIUS, default=defaults.get(CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS)
            ): _km(0.5, 500, 0.5),
            vol.Required(
                CONF_EXCLUDE_BURN_OFFS, default=defaults.get(CONF_EXCLUDE_BURN_OFFS, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SHOW_INCIDENTS_ON_MAP, default=defaults.get(CONF_SHOW_INCIDENTS_ON_MAP, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SHOW_WARNINGS_ON_MAP, default=defaults.get(CONF_SHOW_WARNINGS_ON_MAP, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL, max=3600, step=30, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_TRACK_AIRCRAFT, default=defaults.get(CONF_TRACK_AIRCRAFT, False)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_AIRCRAFT_RADIUS,
                default=defaults.get(CONF_AIRCRAFT_RADIUS, DEFAULT_AIRCRAFT_RADIUS),
            ): _km(1, 460),
            vol.Required(
                CONF_AIRCRAFT_SCAN_INTERVAL,
                default=defaults.get(CONF_AIRCRAFT_SCAN_INTERVAL, DEFAULT_AIRCRAFT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_AIRCRAFT_SCAN_INTERVAL, max=600, step=5, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SHOW_ALL_AIRCRAFT, default=defaults.get(CONF_SHOW_ALL_AIRCRAFT, False)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_AIRCRAFT_EXTRA,
                description={"suggested_value": defaults.get(CONF_AIRCRAFT_EXTRA, "")},
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_INCIDENTS_URL, default=defaults.get(CONF_INCIDENTS_URL, DEFAULT_INCIDENTS_URL)
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.URL)),
            vol.Required(
                CONF_WARNINGS_URL, default=defaults.get(CONF_WARNINGS_URL, DEFAULT_WARNINGS_URL)
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.URL)),
            vol.Required(
                CONF_FDR_URL, default=defaults.get(CONF_FDR_URL, DEFAULT_FDR_URL)
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.URL)),
        }
    )


def _in_wa(lat: float, lon: float) -> bool:
    return WA_LAT[0] <= lat <= WA_LAT[1] and WA_LON[0] <= lon <= WA_LON[1]


class DfesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick a name and a location to watch."""
        errors: dict[str, str] = {}
        if user_input is not None:
            loc = user_input[CONF_LOCATION]
            lat, lon = float(loc[CONF_LATITUDE]), float(loc[CONF_LONGITUDE])
            if not _in_wa(lat, lon):
                errors[CONF_LOCATION] = "outside_wa"
            else:
                await self.async_set_unique_id(f"{lat:.4f},{lon:.4f}")
                self._abort_if_unique_id_configured()
                data = {CONF_NAME: user_input[CONF_NAME], CONF_LATITUDE: lat, CONF_LONGITUDE: lon}
                options = {
                    CONF_RADIUS: user_input[CONF_RADIUS],
                    CONF_ALERT_RADIUS: user_input[CONF_ALERT_RADIUS],
                    CONF_EXCLUDE_BURN_OFFS: user_input[CONF_EXCLUDE_BURN_OFFS],
                }
                if user_input.get(CONF_FIRE_DISTRICT):
                    options[CONF_FIRE_DISTRICT] = user_input[CONF_FIRE_DISTRICT]
                return self.async_create_entry(title=user_input[CONF_NAME], data=data, options=options)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="DFES Home"): selector.TextSelector(),
                vol.Required(
                    CONF_LOCATION,
                    default={
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                        HA_CONF_RADIUS: DEFAULT_RADIUS * 1000,
                    },
                ): selector.LocationSelector(selector.LocationSelectorConfig(radius=False)),
                vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): _km(1, 2500),
                vol.Required(CONF_ALERT_RADIUS, default=DEFAULT_ALERT_RADIUS): _km(0.5, 500, 0.5),
                vol.Required(CONF_EXCLUDE_BURN_OFFS, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_FIRE_DISTRICT): _district_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return DfesOptionsFlow()


class DfesOptionsFlow(OptionsFlow):
    """Change radius, filters, polling and feed URLs."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            if CONF_AIRCRAFT_SCAN_INTERVAL in user_input:
                user_input[CONF_AIRCRAFT_SCAN_INTERVAL] = int(user_input[CONF_AIRCRAFT_SCAN_INTERVAL])
            if not (user_input.get(CONF_AIRCRAFT_EXTRA) or "").strip():
                user_input.pop(CONF_AIRCRAFT_EXTRA, None)
            if not user_input.get(CONF_FIRE_DISTRICT):
                user_input.pop(CONF_FIRE_DISTRICT, None)
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(dict(self.config_entry.options))
        )
