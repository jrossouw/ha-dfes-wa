"""Tests for the ADS-B emergency aircraft parser and classifier."""

import pathlib

import pytest

from dfes_wa.aircraft import (
    Aircraft,
    AircraftParseError,
    classify,
    parse_aircraft,
    parse_extra,
)
from dfes_wa.const import (
    ROLE_AIR_ATTACK,
    ROLE_BOMBER,
    ROLE_HELITACK,
    ROLE_MEDICAL,
    ROLE_OTHER,
    ROLE_POLICE,
    ROLE_RESCUE,
)

HERE = pathlib.Path(__file__).parent


def _all():
    return parse_aircraft((HERE / "fixtures_adsb.json").read_bytes())


def test_parse_skips_stale_positionless_and_duplicates():
    planes = _all()
    hexes = [a.hex for a in planes]
    assert "7c3333" not in hexes  # position 95 s old
    assert "7c4444" not in hexes  # no position
    assert hexes.count("7c6d2a") == 1  # duplicate hex keeps the first
    assert len(planes) == 7


def test_parse_fields():
    bomber = _all()[0]
    assert bomber.callsign == "BMBR611"  # padding stripped
    assert bomber.registration == "VH-RIM"
    assert bomber.type_code == "AT8T"
    assert bomber.altitude_ft == 1200
    assert bomber.ground_speed_kmh == 264
    assert bomber.vertical_rate_fpm == -320
    assert bomber.external_id == "aircraft:7c6d2a"
    assert bomber.link.endswith("icao=7c6d2a")

    rescue = next(a for a in _all() if a.callsign == "RSCU651")
    assert rescue.on_ground and rescue.altitude_ft == 0


@pytest.mark.parametrize(
    ("callsign", "role"),
    [
        ("BMBR611", ROLE_BOMBER),
        ("BMBR138", ROLE_BOMBER),
        ("HLTK671", ROLE_HELITACK),
        ("FBIR623", ROLE_AIR_ATTACK),
        ("PKAR643", ROLE_AIR_ATTACK),
        ("SPTR643", ROLE_AIR_ATTACK),
        ("BDOG682", ROLE_AIR_ATTACK),
        ("RSCU652", ROLE_RESCUE),
        ("RESU651", ROLE_RESCUE),
        ("FD601", ROLE_MEDICAL),
        ("FD624J", ROLE_MEDICAL),
        ("POL61", ROLE_POLICE),
        ("POLAIR", ROLE_POLICE),
        ("QFA781", None),
        ("VOZ1234", None),
        ("FD1", None),
        ("POLLY1", None),
        ("BOMBAY", None),
    ],
)
def test_callsign_roles(callsign, role):
    plane = Aircraft(hex="abc123", latitude=-31.6, longitude=116.0, callsign=callsign)
    assert classify(plane) == role


def test_extra_watch_list():
    extra = parse_extra("vh-abc; 7C1111\n  , QFA9 ")
    assert extra == frozenset({"VHABC", "7C1111", "QFA9"})
    by_rego = Aircraft(hex="7c2222", latitude=0, longitude=0, registration="VH-ABC")
    by_hex = Aircraft(hex="7c1111", latitude=0, longitude=0, callsign="QFA781")
    neither = Aircraft(hex="7c9999", latitude=0, longitude=0, callsign="VOZ1")
    assert classify(by_rego, extra) == ROLE_OTHER
    assert classify(by_hex, extra) == ROLE_OTHER
    assert classify(neither, extra) is None
    assert parse_extra("") == frozenset()
    assert parse_extra(None) == frozenset()


def test_built_in_roles_win_over_extra_list():
    plane = Aircraft(hex="7c6d2a", latitude=0, longitude=0, callsign="BMBR611")
    assert classify(plane, frozenset({"7C6D2A"})) == ROLE_BOMBER


@pytest.mark.parametrize("raw", [b"not json", b"[1, 2]", b'{"ac": "x"}', b'{"msg": "rate limited"}'])
def test_bad_responses(raw):
    with pytest.raises(AircraftParseError):
        parse_aircraft(raw)


def test_empty_sky():
    assert parse_aircraft(b'{"ac": [], "msg": "No error"}') == []
    assert parse_aircraft(b'{"msg": "No error", "now": 1}') == []
