"""Tests for the Emergency WA feed parser."""

import pathlib

import pytest

from dfes_wa.const import KIND_INCIDENT, KIND_WARNING, LEVEL_ADVICE, LEVEL_WATCH_AND_ACT
from dfes_wa.feed import FeedParseError, distance_to, haversine_km, parse_feed

HERE = pathlib.Path(__file__).parent
HOME = (-31.65, 115.95)  # near Muchea


def _load(name):
    return (HERE / name).read_bytes()


def test_incidents_parsed():
    entries = parse_feed(_load("fixtures_incidents.xml"), KIND_INCIDENT)
    assert len(entries) == 3  # item without coordinates is skipped
    burn = entries[0]
    assert burn.category == "Burn Off"
    assert burn.suburb == "Muchea"
    assert burn.lga == "Shire Of Chittering"
    assert burn.region == "Metro North East"
    assert burn.incident_number == "825904"
    assert burn.external_id == "6adad8f25a47352fe58b7297"
    assert burn.is_burn_off and burn.is_fire
    assert burn.display_name == "Burn Off - Muchea"
    assert burn.published.utcoffset().total_seconds() == 8 * 3600

    structure = entries[1]
    assert structure.is_fire and not structure.is_burn_off

    kimberley = entries[2]
    assert kimberley.lga is None  # "unknown LGA"


def test_warnings_parsed():
    entries = parse_feed(_load("fixtures_warnings.xml"), KIND_WARNING)
    assert len(entries) == 2
    advice, watch = entries
    assert advice.alert_level == LEVEL_ADVICE
    assert advice.region == "Goldfields Midlands"
    assert advice.incident_number == "825781"
    assert len(advice.polygon) == 5
    assert not advice.is_serious

    assert watch.alert_level == LEVEL_WATCH_AND_ACT
    assert watch.is_serious
    # No geo:lat/long -> falls back to the polygon centroid
    assert watch.latitude == pytest.approx(-31.66, abs=0.01)


def test_distance_inside_polygon_is_zero():
    watch = parse_feed(_load("fixtures_warnings.xml"), KIND_WARNING)[1]
    assert distance_to(watch, *HOME) == 0.0


def test_distance_point():
    burn = parse_feed(_load("fixtures_incidents.xml"), KIND_INCIDENT)[0]
    assert distance_to(burn, *HOME) == pytest.approx(7.6, abs=0.3)


def test_haversine_known():
    # Perth CBD to Fremantle ~ 15.5 km
    assert haversine_km(-31.9523, 115.8613, -32.0569, 115.7439) == pytest.approx(16.0, abs=1.0)


def test_bad_xml():
    with pytest.raises(FeedParseError):
        parse_feed(b"<rss><channel>", KIND_INCIDENT)


def test_leading_bom_and_whitespace():
    data = b"\xef\xbb\xbf\r\n  " + _load("fixtures_warnings.xml")
    assert len(parse_feed(data, KIND_WARNING)) == 2


def test_text_before_first_tag():
    data = b"\n\n" + _load("fixtures_incidents.xml").replace(b'<?xml version="1.0" encoding="UTF-8"?>', b"")
    assert len(parse_feed(b"junk " + data, KIND_INCIDENT)) == 3


def test_json_xmltodict_shape():
    """Same structure Home Assistant's REST sensor produces from this feed."""
    import json

    doc = {
        "rss": {
            "channel": {
                "lastBuildDate": "Fri, 23 Oct 2026 15:05:50 +0800",
                "item": [
                    {
                        "title": "Bushfire Advice MONITOR CONDITIONS - ORD RIVER",
                        "link": "https://emergency.wa.gov.au/warnings/6adb030775081574b38c3ae4",
                        "pubDate": "Fri, 23 Oct 2026 14:52:30 +0800",
                        "dfes:region": "KIMBERLEY",
                        "dfes:incidentNumber": "825411",
                        "guid": {"@isPermaLink": "false", "#text": "6adb030775081574b38c3ae4"},
                        "geo:long": "127.81646443741508",
                        "geo:lat": "-17.839107355711846",
                        "georss:alertLevel": None,
                        "georss:polygon": "-17.79,127.77 -17.79,127.80 -17.87,127.85 -17.79,127.77",
                    }
                ],
            }
        }
    }
    entries = parse_feed(json.dumps(doc).encode(), KIND_WARNING)
    assert len(entries) == 1
    w = entries[0]
    assert w.external_id == "6adb030775081574b38c3ae4"
    assert w.region == "Kimberley"
    assert w.incident_number == "825411"
    assert w.alert_level == LEVEL_ADVICE
    assert len(w.polygon) == 4


def test_empty_and_garbage():
    with pytest.raises(FeedParseError):
        parse_feed(b"   ", KIND_WARNING)
    with pytest.raises(FeedParseError):
        parse_feed(b"Service unavailable", KIND_WARNING)


def test_fire_danger_ratings():
    from datetime import date

    from dfes_wa.feed import parse_fdr

    fdr = parse_fdr(_load("fixtures_fdr.xml"))
    today, tomorrow = date(2026, 10, 23), date(2026, 10, 24)
    assert set(fdr.days) == {today, tomorrow}
    assert fdr.rating("Swan Inland North", today) == "moderate"
    assert fdr.rating("swan inland north", tomorrow) == "high"
    assert fdr.rating("Hedland", tomorrow) == "extreme"
    assert fdr.rating("Perth Inner", today) == "no_rating"
    assert fdr.rating("Nowhere", today) is None
    assert fdr.issued.utcoffset().total_seconds() == 8 * 3600


def test_fire_danger_ratings_empty():
    from dfes_wa.feed import parse_fdr

    with pytest.raises(FeedParseError):
        parse_fdr(b"<rss><channel></channel></rss>")


def test_warning_geojson():
    advice, watch = parse_feed(_load("fixtures_warnings.xml"), KIND_WARNING)
    gj = watch.geojson
    assert gj["type"] == "Feature"
    ring = gj["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]  # closed
    assert ring[0] == [115.9, -31.7]  # [lon, lat]
    assert gj["properties"]["alert_level"] == LEVEL_WATCH_AND_ACT
    incident = parse_feed(_load("fixtures_incidents.xml"), KIND_INCIDENT)[0]
    assert incident.geojson is None
