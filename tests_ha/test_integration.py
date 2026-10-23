"""End-to-end test: config flow, entities, map pins and events."""

import pathlib

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from homeassistant.util import dt as dt_util
from datetime import timedelta

from custom_components.dfes_wa.const import (
    DEFAULT_INCIDENTS_URL,
    DEFAULT_WARNINGS_URL,
    DOMAIN,
    EVENT_NEW_INCIDENT,
)

FIX = pathlib.Path(__file__).parent.parent / "tests"
INC = (FIX / "fixtures_incidents.xml").read_text()
WARN = (FIX / "fixtures_warnings.xml").read_text()

NEW_INC = INC.replace(
    "  </channel>",
    """    <item>
      <title>Bushfire (BULLSBROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 999999)</title>
      <link>https://emergency.wa.gov.au/incidents/new</link>
      <guid isPermaLink="false">new-fire</guid>
      <geo:long>115.99</geo:long>
      <geo:lat>-31.66</geo:lat>
    </item>
  </channel>""",
)


async def test_full_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # outside WA is rejected
    bad = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "x", CONF_LOCATION: {CONF_LATITUDE: -33.86, CONF_LONGITUDE: 151.2},
         "radius": 50, "alert_radius": 10, "exclude_burn_offs": False},
    )
    assert bad["errors"] == {CONF_LOCATION: "outside_wa"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "DFES Home", CONF_LOCATION: {CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
         "radius": 50, "alert_radius": 10, "exclude_burn_offs": False},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Sensors
    assert hass.states.get("sensor.dfes_home_incidents_nearby").state == "2"
    assert hass.states.get("sensor.dfes_home_incidents_nearby").attributes["radius_km"] == 50
    assert hass.states.get("sensor.dfes_home_warnings_nearby").state == "1"
    assert float(hass.states.get("sensor.dfes_home_nearest_incident").state) < 10
    # nearest real fire is the structure fire at Bambun (~22 km)
    assert 15 < float(hass.states.get("sensor.dfes_home_nearest_fire").state) < 30
    assert hass.states.get("binary_sensor.dfes_home_fire_nearby").state == "off"
    assert hass.states.get("binary_sensor.dfes_home_watch_and_act_or_emergency_warning").state == "on"
    assert hass.states.get("binary_sensor.dfes_home_home_in_warning_area").state == "on"

    # Map pins
    pins = hass.states.async_entity_ids("geo_location")
    assert len(pins) == 3, pins
    burn = hass.states.get("geo_location.burn_off_muchea")
    assert burn is not None
    assert burn.attributes["source"] == "dfes_wa"
    assert "geojson" not in burn.attributes  # incidents have no area
    warn_pin = hass.states.get("geo_location.bushfire_watch_and_act_test_town")
    assert warn_pin.attributes["geojson"]["geometry"]["type"] == "Polygon"
    assert abs(burn.attributes["latitude"] - -31.58184933) < 1e-4

    # A new fire appears -> event fired, pin added, fire_nearby turns on
    events = []
    hass.bus.async_listen(EVENT_NEW_INCIDENT, callback(lambda e: events.append(e)))
    aioclient_mock.clear_requests()
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=NEW_INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(events) == 1
    assert events[0].data["suburb"] == "Bullsbrook"
    assert events[0].data["is_fire"] is True
    assert events[0].data["in_radius"] is True
    assert hass.states.get("binary_sensor.dfes_home_fire_nearby").state == "on"
    assert len(hass.states.async_entity_ids("geo_location")) == 4

    # Incident clears -> pin removed
    aioclient_mock.clear_requests()
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(hass.states.async_entity_ids("geo_location")) == 3

    # Unload cleanly
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("geo_location")) == 0


async def test_options_flow(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    aioclient_mock.get(
        "https://api.emergency.wa.gov.au/v1/rss/fire-danger-ratings",
        text=(FIX / "fixtures_fdr.xml").read_text(),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "DFES Home", CONF_LOCATION: {CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
         "radius": 50, "alert_radius": 10, "exclude_burn_offs": False},
    )
    await hass.async_block_till_done()
    entry = result["result"]

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] is FlowResultType.FORM
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "radius": 50, "alert_radius": 10, "exclude_burn_offs": True,
            "show_incidents_on_map": True, "show_warnings_on_map": False,
            "scan_interval": 300,
            "incidents_url": DEFAULT_INCIDENTS_URL, "warnings_url": DEFAULT_WARNINGS_URL,
            "fdr_url": "https://api.emergency.wa.gov.au/v1/rss/fire-danger-ratings",
            "fire_district": "Swan Inland North",
        },
    )
    assert flow["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Burn off hidden, warnings not mapped -> only the structure fire pin remains
    assert hass.states.async_entity_ids("geo_location") == ["geo_location.structure_fire_bambun"]
    assert hass.states.get("sensor.dfes_home_incidents_nearby").state == "1"
    # Choosing a district adds the rating sensors
    assert hass.states.get("sensor.dfes_home_fire_danger_rating_today") is not None


async def test_legacy_urls_in_options_are_ignored(hass: HomeAssistant, aioclient_mock) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DFES Home",
        data={CONF_NAME: "DFES Home", CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
        options={
            "radius": 50,
            "incidents_url": "https://www.emergency.wa.gov.au/data/incidents.rss",
            "warnings_url": "https://www.emergency.wa.gov.au/data/warnings.rss",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.dfes_home_incidents_nearby").state == "2"


async def test_select_pin_and_clear(hass: HomeAssistant, aioclient_mock) -> None:
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "DFES Home", CONF_LOCATION: {CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
         "radius": 50, "alert_radius": 10, "exclude_burn_offs": False},
    )
    await hass.async_block_till_done()

    selected = "sensor.dfes_home_selected_on_map"
    assert hass.states.get(selected).state == "unknown"

    await hass.services.async_call(
        DOMAIN, "select_pin", {"pin": "geo_location.burn_off_muchea"}, blocking=True
    )
    state = hass.states.get(selected)
    assert state.state == "Burn Off - Muchea"
    assert state.attributes["suburb"] == "Muchea"
    assert state.attributes["lga"] == "Shire Of Chittering"
    assert state.attributes["pin"] == "geo_location.burn_off_muchea"
    assert state.attributes["link"].endswith("6adad8f25a47352fe58b7297")

    # Warnings work too
    await hass.services.async_call(
        DOMAIN, "select_pin", {"pin": "geo_location.bushfire_watch_and_act_test_town"}, blocking=True
    )
    state = hass.states.get(selected)
    assert state.attributes["alert_level"] == "Watch and Act"

    # Not a DFES pin -> clear error
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "select_pin", {"pin": "zone.home"}, blocking=True
        )

    await hass.services.async_call(DOMAIN, "clear_selection", {}, blocking=True)
    assert hass.states.get(selected).state == "unknown"

    # Selected incident disappears from the feed -> "Cleared"
    await hass.services.async_call(
        DOMAIN, "select_pin", {"pin": "geo_location.burn_off_muchea"}, blocking=True
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC.replace("6adad8f25a47352fe58b7297", "gone"))
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(selected).state == "Cleared"


FDR = (FIX / "fixtures_fdr.xml").read_text()


async def test_fire_danger_rating_sensors(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.dfes_wa.const import DEFAULT_FDR_URL

    freezer.move_to("2026-10-23T09:00:00+08:00")
    await hass.config.async_set_time_zone("Australia/Perth")
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    aioclient_mock.get(DEFAULT_FDR_URL, text=FDR)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DFES Home",
        data={CONF_NAME: "DFES Home", CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
        options={"radius": 50, "fire_district": "Swan Inland North"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    today = hass.states.get("sensor.dfes_home_fire_danger_rating_today")
    tomorrow = hass.states.get("sensor.dfes_home_fire_danger_rating_tomorrow")
    assert today.state == "moderate"
    assert today.attributes["district"] == "Swan Inland North"
    assert today.attributes["level"] == 1
    assert today.attributes["date"] == "2026-10-23"
    assert tomorrow.state == "high"
    assert tomorrow.attributes["colour"] == "#ffe324"


async def test_fdr_failure_does_not_break_setup(hass: HomeAssistant, aioclient_mock) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.dfes_wa.const import DEFAULT_FDR_URL

    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    aioclient_mock.get(DEFAULT_FDR_URL, text="<!doctype html><html></html>")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DFES Home",
        data={CONF_NAME: "DFES Home", CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
        options={"radius": 50, "fire_district": "Swan Inland North"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.dfes_home_incidents_nearby").state == "2"
    assert hass.states.get("sensor.dfes_home_fire_danger_rating_today").state == "unknown"


async def test_no_district_no_fdr_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DFES Home",
        data={CONF_NAME: "DFES Home", CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
        options={"radius": 50},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.dfes_home_fire_danger_rating_today") is None
    assert aioclient_mock.call_count == 2  # ratings feed never fetched



async def test_statewide_event_outside_radius(hass: HomeAssistant, aioclient_mock) -> None:
    """New incidents beyond the radius still fire an event, flagged in_radius False."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DFES Home",
        data={CONF_NAME: "DFES Home", CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
        options={"radius": 50},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    events = []
    hass.bus.async_listen(EVENT_NEW_INCIDENT, callback(lambda e: events.append(e)))
    far = INC.replace(
        "  </channel>",
        """    <item>
      <title>Bushfire (ALBANY, CITY OF ALBANY, GREAT SOUTHERN, CAD-ID: 777)</title>
      <link>https://emergency.wa.gov.au/incidents/far</link>
      <guid isPermaLink="false">far-fire</guid>
      <geo:long>117.88</geo:long>
      <geo:lat>-35.02</geo:lat>
    </item>
  </channel>""",
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=far)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["suburb"] == "Albany"
    assert events[0].data["in_radius"] is False
    assert events[0].data["distance_km"] > 300
    # ...but it is not mapped or counted
    assert hass.states.get("sensor.dfes_home_incidents_nearby").state == "2"
