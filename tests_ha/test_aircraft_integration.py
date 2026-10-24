"""End-to-end tests for emergency aircraft tracking (ADS-B)."""

from datetime import timedelta
import json
import pathlib
from urllib.parse import unquote

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.dfes_wa.const import (
    DEFAULT_INCIDENTS_URL,
    DEFAULT_WARNINGS_URL,
    DOMAIN,
    EVENT_AIRCRAFT_SPOTTED,
)

FIX = pathlib.Path(__file__).parent.parent / "tests"
INC = (FIX / "fixtures_incidents.xml").read_text()
WARN = (FIX / "fixtures_warnings.xml").read_text()
ADSB = json.loads((FIX / "fixtures_adsb.json").read_text())

# Home is -31.65, 115.95; a 60 km radius is 33 nm.
ADSB_LOL = "https://api.adsb.lol/v2/point/-31.6500/115.9500/33"
AIRPLANES_LIVE = "https://api.airplanes.live/v2/point/-31.6500/115.9500/33"

AIRCRAFT_OPTIONS = {
    "radius": 50,
    "alert_radius": 10,
    "track_aircraft": True,
    "aircraft_radius": 60,
    "aircraft_extra": "VH-ABC",
}


def _feeds(aioclient_mock, adsb=ADSB, lol_status=200, live_status=200, live=ADSB):
    aioclient_mock.clear_requests()
    aioclient_mock.get(DEFAULT_INCIDENTS_URL, text=INC)
    aioclient_mock.get(DEFAULT_WARNINGS_URL, text=WARN)
    aioclient_mock.get(ADSB_LOL, status=lol_status, json=adsb)
    aioclient_mock.get(AIRPLANES_LIVE, status=live_status, json=live)


async def _setup(hass: HomeAssistant, options: dict) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="DFES Home",
        data={CONF_NAME: "DFES Home", CONF_LATITUDE: -31.65, CONF_LONGITUDE: 115.95},
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _aircraft_pins(hass: HomeAssistant) -> dict[str, dict]:
    return {
        s.entity_id: s.attributes
        for s in hass.states.async_all("geo_location")
        if s.attributes.get("kind") == "aircraft"
    }


async def test_off_by_default(hass: HomeAssistant, aioclient_mock) -> None:
    _feeds(aioclient_mock)
    await _setup(hass, {"radius": 50})
    assert _aircraft_pins(hass) == {}
    assert hass.states.get("sensor.dfes_home_emergency_aircraft_nearby") is None
    assert not any("adsb" in str(call[1]) for call in aioclient_mock.mock_calls)


async def test_aircraft_pins_sensors_and_events(hass: HomeAssistant, aioclient_mock) -> None:
    _feeds(aioclient_mock)
    entry = await _setup(hass, AIRCRAFT_OPTIONS)

    pins = _aircraft_pins(hass)
    # bomber, helitack, RAC Rescue, RFDS, police, plus VH-ABC from the extra list.
    # Not the airliner, and not the stale or positionless entries.
    assert set(pins) == {
        "geo_location.bmbr611",
        "geo_location.hltk671",
        "geo_location.rscu651",
        "geo_location.fd624j",
        "geo_location.pol61",
        "geo_location.vh_abc",
    }
    bomber = hass.states.get("geo_location.bmbr611")
    assert bomber.attributes["source"] == "dfes_wa"
    assert bomber.attributes["role"] == "bomber"
    assert bomber.attributes["registration"] == "VH-RIM"
    assert bomber.attributes["altitude_ft"] == 1200
    assert bomber.attributes["external_id"] == "aircraft:7c6d2a"
    assert bomber.attributes["icon"] == "mdi:airplane"
    # Top-down picture rotated to the heading (271.6 -> 270)
    assert bomber.attributes["entity_picture"].startswith("data:image/svg+xml")
    assert "rotate(270 12 12)" in unquote(bomber.attributes["entity_picture"])
    assert 5 < float(bomber.state) < 8  # km from home
    assert pins["geo_location.rscu651"]["on_ground"] is True
    assert pins["geo_location.vh_abc"]["role"] == "other"
    # Incident and warning pins are untouched
    assert hass.states.get("geo_location.burn_off_muchea") is not None

    count = hass.states.get("sensor.dfes_home_emergency_aircraft_nearby")
    assert count.state == "6"
    assert count.attributes["aircraft"][0]["callsign"] == "BMBR611"  # nearest first
    assert count.attributes["all_aircraft_in_area"] == 7
    assert count.attributes["feed"] == "api.adsb.lol"
    assert count.attributes["radius_km"] == 60

    nearby = hass.states.get("binary_sensor.dfes_home_firefighting_aircraft_nearby")
    assert nearby.state == "on"  # the bomber is ~7 km away, inside the 10 km alert radius
    assert [m["callsign"] for m in nearby.attributes["matches"]] == ["BMBR611"]

    # Aircraft present at startup don't fire events. The bomber moves; a new
    # firebird arrives (event); the helitack leaves (pin removed).
    events = []
    hass.bus.async_listen(EVENT_AIRCRAFT_SPOTTED, callback(lambda e: events.append(e)))
    moved = json.loads(json.dumps(ADSB))
    moved["ac"] = [a for a in moved["ac"] if a.get("flight") != "HLTK671"]
    moved["ac"][0]["lat"], moved["ac"][0]["lon"] = -31.64, 115.96
    moved["ac"].append(
        {"hex": "7c3334", "flight": "FBIR661", "r": "N365JA", "t": "S65C",
         "alt_baro": 3000, "lat": -31.66, "lon": 115.97, "seen_pos": 1}
    )
    _feeds(aioclient_mock, adsb=moved)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    pins = _aircraft_pins(hass)
    assert "geo_location.hltk671" not in pins
    assert "geo_location.fbir661" in pins
    assert abs(hass.states.get("geo_location.bmbr611").attributes["latitude"] - -31.64) < 1e-6
    assert len(events) == 1
    assert events[0].data["callsign"] == "FBIR661"
    assert events[0].data["role"] == "air_attack"
    assert events[0].data["is_firefighting"] is True
    assert events[0].data["in_alert_radius"] is True
    assert events[0].data["config_entry_id"] == entry.entry_id

    # Unload removes every pin
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("geo_location") == []


async def test_falls_back_to_second_feed(hass: HomeAssistant, aioclient_mock) -> None:
    _feeds(aioclient_mock, lol_status=503)
    await _setup(hass, AIRCRAFT_OPTIONS)
    count = hass.states.get("sensor.dfes_home_emergency_aircraft_nearby")
    assert count.state == "6"
    assert count.attributes["feed"] == "api.airplanes.live"


async def test_adsb_outage_does_not_break_incidents(hass: HomeAssistant, aioclient_mock) -> None:
    _feeds(aioclient_mock, lol_status=503, live_status=500)
    await _setup(hass, AIRCRAFT_OPTIONS)
    # Incidents and warnings still load
    assert hass.states.get("sensor.dfes_home_incidents_nearby").state == "2"
    assert _aircraft_pins(hass) == {}
    assert hass.states.get("sensor.dfes_home_emergency_aircraft_nearby").state == STATE_UNAVAILABLE

    # Feed comes back -> pins appear
    _feeds(aioclient_mock)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_aircraft_pins(hass)) == 6
    assert hass.states.get("sensor.dfes_home_emergency_aircraft_nearby").state == "6"


async def test_turn_on_in_options(hass: HomeAssistant, aioclient_mock) -> None:
    _feeds(aioclient_mock)
    entry = await _setup(hass, {"radius": 50, "alert_radius": 10})
    assert _aircraft_pins(hass) == {}

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "radius": 50, "alert_radius": 10, "exclude_burn_offs": False,
            "show_incidents_on_map": True, "show_warnings_on_map": True,
            "scan_interval": 120,
            "track_aircraft": True, "aircraft_radius": 60, "aircraft_scan_interval": 30,
            "aircraft_extra": "  ",
            "incidents_url": DEFAULT_INCIDENTS_URL, "warnings_url": DEFAULT_WARNINGS_URL,
            "fdr_url": "https://api.emergency.wa.gov.au/v1/rss/fire-danger-ratings",
        },
    )
    assert flow["type"] is FlowResultType.CREATE_ENTRY
    assert "aircraft_extra" not in entry.options  # blank list isn't stored
    await hass.async_block_till_done()
    assert len(_aircraft_pins(hass)) == 5  # no extra list this time


async def test_show_all_aircraft(hass: HomeAssistant, aioclient_mock) -> None:
    _feeds(aioclient_mock)
    await _setup(hass, {**AIRCRAFT_OPTIONS, "show_all_aircraft": True})

    pins = _aircraft_pins(hass)
    # All 7 in range get a pin: the 6 emergency/extra ones plus the airliner
    assert len(pins) == 7
    assert pins["geo_location.qfa781"]["role"] == "general"
    assert hass.states.get("geo_location.qfa781").attributes["icon"] == "mdi:airplane"
    # Sensors still count emergency aircraft only
    count = hass.states.get("sensor.dfes_home_emergency_aircraft_nearby")
    assert count.state == "6"
    assert count.attributes["showing_all_aircraft"] is True
    assert "QFA781" not in [a.get("callsign") for a in count.attributes["aircraft"]]

    # A new airliner arriving doesn't fire the emergency event
    events = []
    hass.bus.async_listen(EVENT_AIRCRAFT_SPOTTED, callback(lambda e: events.append(e)))
    more = json.loads(json.dumps(ADSB))
    more["ac"].append(
        {"hex": "7c5555", "flight": "VOZ1234", "r": "VH-YIA", "t": "B738",
         "alt_baro": 9000, "lat": -31.70, "lon": 115.99, "seen_pos": 1}
    )
    _feeds(aioclient_mock, adsb=more)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "geo_location.voz1234" in _aircraft_pins(hass)
    assert events == []
