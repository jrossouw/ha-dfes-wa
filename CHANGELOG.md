# Changelog

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
