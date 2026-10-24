# Changelog

## 1.1.0

- **Emergency aircraft** (optional, off by default): water bombers, helitacks, air attack, RAC Rescue, RFDS and police aircraft as moving `geo_location` pins (`kind: aircraft`), from the free adsb.lol feed with airplanes.live as a fallback
- Recognised by broadcast flight ID (`BMBR`, `HLTK`, `FBIR`, `BDOG`, `PKAR`, `SPTR`, `RSCU`, `FD`, `POL`), plus your own list of callsigns, registrations or hex codes
- New entities: **Emergency aircraft nearby** sensor and **Firefighting aircraft nearby** binary sensor
- New event: `dfes_wa_aircraft_spotted`
- Options: aircraft radius, update interval (default 30 s), extra aircraft, and **Show all aircraft** to map every aircraft in range (sensors and events still count emergency aircraft only)
- An ADS-B outage never affects incidents, warnings or Fire Danger Ratings
- Aircraft pins carry a top-down picture rotated to the heading (`display: marker` in map-card points them in the direction of flight)
- Enhanced dashboard: aircraft pointing along their heading, coloured by role, with 30-minute trails

## 1.0.0

First public release.

- Live map pins (`geo_location`) for Emergency WA incidents and warnings within a configurable radius, added and removed as the feed changes
- Warning affected areas as GeoJSON on map pins, for shading on map-card
- Sensors: incidents and warnings nearby (with lists and `radius_km`), nearest incident / fire / warning, statewide incidents
- Binary sensors: fire nearby, Watch and Act / Emergency Warning, home in warning area
- Fire Danger Ratings for today and tomorrow, for a chosen fire weather district
- `dfes_wa_new_incident` / `dfes_wa_new_warning` events for every new item in WA, with `in_radius`; nothing re-fires after a restart
- `dfes_wa.select_pin` / `dfes_wa.clear_selection` actions and the **Selected on map** sensor
- Options: radius, "fire nearby" radius, ignore burn offs, map visibility, update interval, feed URLs
- Ready-made dashboards: enhanced (map-card + auto-entities) and standard (built-in cards)
