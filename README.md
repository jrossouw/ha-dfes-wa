# DFES Emergency WA for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/jrossouw/ha-dfes-wa/actions/workflows/validate.yml/badge.svg)](https://github.com/jrossouw/ha-dfes-wa/actions/workflows/validate.yml)

Western Australian **DFES / Emergency WA incidents, warnings and Fire Danger Ratings** in Home Assistant: live map pins with warning areas, sensors you can put on a dashboard, and events you can build notifications on. A ready-made dashboard is included.

> ⚠️ **Not an official DFES product and not a warning service.** Feeds can be delayed, incomplete or change without notice. Always use [Emergency WA](https://www.emergency.wa.gov.au/), the Emergency WA app, ABC local radio and 13 DFES (13 3337) for emergency information. **In an emergency call 000.**

## Features

- 🗺️ **Live map pins**: every incident and warning within your radius appears on the map and disappears when it clears.
- 🟨 **Warning areas**: warnings carry their affected area, so maps can shade it the way Emergency WA does.
- ✈️ **Emergency aircraft** (optional): water bombers, helitacks, air attack, RAC Rescue, RFDS and police aircraft move live on the map with trails, from free community ADS-B feeds.
- 🔥 **Fire Danger Ratings**: today's and tomorrow's rating for your fire weather district.
- 🚨 **Safety sensors**: fire nearby, Watch and Act / Emergency Warning in your area, and home inside a warning area.
- 📏 **Nearest incident, fire and warning** distance sensors, plus counts with full lists.
- 👆 **Tap a pin for details**: actions and a sensor that power a "Selected on map" panel.
- 🔔 **Events for every new incident or warning in WA**: fired once each, never re-sent after a restart. You can alert on incidents near home or near wherever a person is.
- 🧯 Optionally ignore planned burn offs.
- 🏠 UI setup, with multiple locations supported (for example home and a holiday house).

## Requirements

- Home Assistant 2025.1 or newer
- For the **enhanced** dashboard only: [map-card](https://github.com/nathan-gs/ha-map-card) and [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) (both in HACS)

## Installation

### HACS (recommended)

1. In HACS, open ⋮ → **Custom repositories**.
2. Add `https://github.com/jrossouw/ha-dfes-wa` with category **Integration**.
3. Search for **DFES Emergency WA**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/dfes_wa` into your `config/custom_components/` folder and restart Home Assistant.

## Setup

Go to **Settings → Devices & services → Add integration → DFES Emergency WA**.

| Option | Default | Notes |
|---|---|---|
| Name | DFES Home | Becomes the entity prefix (`sensor.dfes_home_…`). The dashboards assume this name. |
| Location | Your home | Must be in WA. Add the integration again for extra locations. |
| Tracking radius | 50 km | Incidents and warnings within this distance are mapped and counted. |
| "Fire nearby" radius | 10 km | Drives the **Fire nearby** binary sensor. |
| Ignore burn offs | Off | Hides planned burns everywhere: map, sensors and events. |
| Fire weather district | – | Optional. Adds the Fire Danger Rating sensors (see below). |

Under **Configure** you can change all of these later. You can also hide incidents or warnings from the map, change the update interval (default 2 minutes), turn on emergency aircraft tracking (see below), and override the feed URLs if Emergency WA ever moves them.

## Dashboard

Two ready-made dashboards are in the [`dashboards`](dashboards) folder:

| File | Needs | What you get |
|---|---|---|
| [`fire-and-emergencies.yaml`](dashboards/fire-and-emergencies.yaml) | map-card + auto-entities | Pins coloured by type and alert level, shaded warning areas, street map, a **Selected on map** panel when you tap a pin, an optional wind layer |
| [`fire-and-emergencies-standard.yaml`](dashboards/fire-and-emergencies-standard.yaml) | Nothing extra | The built-in map card with all incident and warning pins. Tapping a pin opens its details dialog. |

Both include a heading that follows your tracking radius ("Within 50 km of home") and a **Status** panel with:
- active incidents
- fire nearby
- official warnings
- Watch and Act / Emergency
- Fire Danger Rating today and tomorrow
- lists of current warnings and incidents with links to Emergency WA

**To add one:**

1. **Settings → Dashboards → Add dashboard → New dashboard from scratch**, and name it (for example *Fire and Emergencies*).
2. Open the new dashboard, then ⋮ → **Edit dashboard** → ⋮ → **Raw configuration editor**.
3. Replace everything with the contents of the YAML file and **Save**.

If you named the integration something other than *DFES Home*, find-and-replace `dfes_home` with your prefix before saving. The fire danger tiles need a fire weather district to be set.

**Optional wind layer (enhanced dashboard):** OpenWeatherMap can shade the map by wind speed. Get a free API key at [openweathermap.org](https://openweathermap.org/) under **My API keys**. Then uncomment the `tile_layers` block in the YAML and paste in your key. New keys can take a couple of hours to activate. Anyone who can open the dashboard can see the key.

## Entities

Entity IDs below assume the entry is named "DFES Home".

| Entity | Description |
|---|---|
| `geo_location.*` | One per incident or warning in range (for example `geo_location.bushfire_muchea`). The state is its distance in km. |
| `sensor.dfes_home_incidents_nearby` | Count, with the list (nearest first) in `incidents` and the tracking radius in `radius_km` |
| `sensor.dfes_home_warnings_nearby` | Count, with the list in `warnings` and `radius_km` |
| `sensor.dfes_home_nearest_incident` | km to the closest incident |
| `sensor.dfes_home_nearest_fire` | km to the closest fire, excluding burn offs |
| `sensor.dfes_home_nearest_warning` | km to the closest warning (0 if you're inside its area) |
| `sensor.dfes_home_fire_danger_rating_today` | Today's Fire Danger Rating for your district |
| `sensor.dfes_home_fire_danger_rating_tomorrow` | Tomorrow's Fire Danger Rating |
| `sensor.dfes_home_selected_on_map` | The incident, warning or aircraft picked with `dfes_wa.select_pin` |
| `sensor.dfes_home_statewide_incidents` | Total incidents in WA (disabled by default) |
| `binary_sensor.dfes_home_fire_nearby` | A fire (not a burn off) is within the "fire nearby" radius |
| `binary_sensor.dfes_home_watch_and_act_or_emergency_warning` | A Watch and Act or Emergency Warning is within the tracking radius |
| `binary_sensor.dfes_home_home_in_warning_area` | Your location is inside a warning's affected area |

**Attributes:**
- Every incident has `type`, `suburb`, `lga`, `region`, `incident_number`, `link` and `published`.
- Warnings also have `alert_level` (`Advice`, `Watch and Act` or `Emergency Warning`).
- Map pins for warnings that have an affected area carry it as a GeoJSON Feature in `geojson`.

## Emergency aircraft

Turn on **Track emergency aircraft** under **Configure** to put WA's emergency aircraft on the map as they fly. Positions come from the free, unfiltered community ADS-B feeds [adsb.lol](https://adsb.lol) (with [airplanes.live](https://airplanes.live) as a fallback). No account or API key is needed.

Aircraft are recognised by the flight ID they broadcast:

| Role | Flight IDs | Examples |
|---|---|---|
| `bomber` | `BMBR…` | Air Tractor AT-802s (BMBR601–619), large air tankers (BMBR132, BMBR138) |
| `helitack` | `HLTK…` | Black Hawks, Bell 214s |
| `air_attack` | `FBIR…`, `BDOG…`, `PKAR…`, `SPTR…` | Firebirds, Birddogs, Spotters |
| `rescue` | `RSCU…` | RAC Rescue (RSCU651, RSCU652) |
| `medical` | `FD` + 3 digits | Royal Flying Doctor Service |
| `police` | `POL…`, `POLAIR` | WA Police Air Wing |
| `other` | your list | Anything in **Extra aircraft to track** |
| `general` | – | Every other aircraft, only with **Show all aircraft** on |

**Extra aircraft to track** takes callsigns, registrations (`VH-ABC`) or ICAO hex codes (`7C1234`), separated by commas or new lines. Use it for aircraft that don't broadcast a recognisable flight ID.

| Option | Default | Notes |
|---|---|---|
| Track emergency aircraft | Off | Adds the entities below |
| Aircraft radius | 50 km | Up to 460 km |
| Aircraft update interval | 30 s | Minimum 15 s. Please be kind to the free feeds. |
| Show all aircraft | Off | Map every aircraft in range, not just emergency ones. Handy for seeing it work. The sensors, alert and event still count emergency aircraft only. |
| Extra aircraft to track | – | See above |

**Entities:**
- `geo_location.<callsign>`, for example `geo_location.bmbr611`: one per emergency aircraft in range, with `kind: aircraft`, `role`, `callsign`, `registration`, `aircraft_type`, `altitude_ft`, `on_ground`, `ground_speed_kmh`, `heading`, `vertical_rate_fpm`, `squawk` and a `link` to the live track. It moves with every update and is removed when the aircraft leaves the area. Its `entity_picture` is a top-down plane, or a helicopter for rotorcraft (by ADS-B emitter category, then type designator, then role), coloured by role and rotated to its heading, so map-card's `display: marker` points it in the direction of flight. Because the entity keeps its ID while the aircraft is in range, map-card's `history_start` draws its trail.
- `sensor.dfes_home_emergency_aircraft_nearby`: count, with the list (nearest first) in `aircraft`.
- `binary_sensor.dfes_home_firefighting_aircraft_nearby`: on while a bomber, helitack or air attack aircraft is within the "fire nearby" radius.
- Event `dfes_wa_aircraft_spotted`: fired when an emergency aircraft enters the aircraft radius, with the same data as the map pin plus `in_alert_radius`, `is_firefighting` and `config_entry_id`. Aircraft already in range at startup don't fire.

The enhanced dashboard points each aircraft along its heading, shows its details (registration, type, altitude, speed, climb rate, squawk and a live-track link) in the **Selected on map** panel when tapped, colours it by role and draws a 30-minute trail (other aircraft are small, grey and keep a 10-minute trail). The standard dashboard shows them automatically.

**Optional: a trails on/off switch.** Map-card can take the trail length from an entity and redraws when it changes. Create a Toggle helper (`input_boolean.aircraft_trails`) and a Template sensor helper (`sensor.aircraft_trail_minutes`) with the state `{{ 30 if is_state('input_boolean.aircraft_trails', 'on') else 0 }}`. Then give each aircraft rule in the enhanced dashboard

```yaml
history_start:
  entity: sensor.aircraft_trail_minutes
  suffix: minutes ago
```

and add a tile for `input_boolean.aircraft_trails`.

Coverage depends on volunteer receivers. Low-flying aircraft in the hills, or far from Perth, can drop in and out. Not every aircraft transmits ADS-B, and an aircraft can fly under a different flight ID.

## Fire Danger Ratings

Ratings come from the Emergency WA Fire Danger Ratings feed, which covers today and tomorrow for each of WA's 49 fire weather districts. The feed has no district boundaries, so you pick your district in the integration's setup or **Configure** dialog. To find it, look up your local council in the [DFES list of fire weather districts](https://www.dfes.wa.gov.au/documents/WA-Fire-Weather-Districts-and-Local-Government-Authorities.pdf) or check [Emergency WA](https://www.emergency.wa.gov.au/fire-danger-ratings).

The state is one of `no_rating`, `moderate`, `high`, `extreme` or `catastrophic`, and is shown translated in the UI. Each rating sensor also has:
- `level`: 0 for no rating up to 4 for catastrophic, handy for automations
- `colour`: the official rating colour
- `district`, `date` and `issued`

```yaml
# Example trigger: High or above tomorrow
triggers:
  - trigger: numeric_state
    entity_id: sensor.dfes_home_fire_danger_rating_tomorrow
    attribute: level
    above: 1
```

The ratings feed is checked every 30 minutes. If it can't be read, the incident and warning sensors keep working and the rating sensors keep their last value.

## Map pins: details and warning areas

Two actions let a map show a tapped pin's details instead of its history:

| Action | What it does |
|---|---|
| `dfes_wa.select_pin` | Shows an incident, warning or aircraft (`pin: geo_location.…`) in `sensor.dfes_home_selected_on_map` |
| `dfes_wa.clear_selection` | Clears it again |

The sensor's state is the incident name (an aircraft's callsign), or `Cleared` once it leaves the feed or flies out of range. A selected aircraft's details follow it with every ADS-B update. Its attributes hold the same details as the other sensors. With map-card and auto-entities, give each pin:

```yaml
tap_action:
  action: call-service
  service: dfes_wa.select_pin
  data:
    pin: this.entity_id
```

To shade a warning's affected area with map-card:

```yaml
options:
  geojson:
    attribute: geojson
    color: "#fbc02d"
    fill_opacity: 0.25
```

With only the built-in map card:

```yaml
type: map
geo_location_sources:
  - dfes_wa
entities:
  - zone.home
hours_to_show: 0
default_zoom: 9
```

## Notifications

Build alerts on the integration's events rather than on sensors, so each incident only alerts once. `dfes_wa_new_incident` and `dfes_wa_new_warning` fire for every new item **anywhere in WA**, with `in_radius` showing whether it's within your tracking radius. Nothing is re-sent after a restart.

```yaml
alias: DFES incident near home
mode: queued
triggers:
  - trigger: event
    event_type: dfes_wa_new_incident
    event_data:
      is_burn_off: false
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.distance_km <= 10 }}"  # km from the configured location
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "🔥 {{ trigger.event.data.type }} – {{ trigger.event.data.suburb }}"
      message: "{{ trigger.event.data.distance_km }} km from home"
      data:
        url: "{{ trigger.event.data.link }}"
        clickAction: "{{ trigger.event.data.link }}"
        push:
          interruption-level: time-sensitive
```

Because events cover the whole state, you can also alert on incidents near a **person**, wherever they are:

```yaml
conditions:
  - condition: template
    value_template: >
      {{ distance(trigger.event.data.latitude, trigger.event.data.longitude,
                  'person.alex') <= 10 }}
```

### Event data

| Key | Example |
|---|---|
| `type` | `Bushfire` |
| `title` | Full feed title |
| `suburb`, `lga`, `region` | `Muchea`, `Shire Of Chittering`, `Metro North East` |
| `latitude`, `longitude` | `-31.58`, `115.95` |
| `distance_km` | `7.6` (from the configured location) |
| `in_radius` | `true` if within the tracking radius, and so on the map |
| `incident_number` | `825904` |
| `alert_level` | `Watch and Act` (warnings only) |
| `is_fire`, `is_burn_off` | `true`, `false` |
| `link` | Emergency WA page |
| `published` | ISO timestamp |
| `config_entry_id` | Which configured location fired it |

## Troubleshooting

- **Setup fails with "Could not parse … feed":** the log shows the start of what the feed returned. If Emergency WA has moved its feeds, update the URLs under **Configure**. The defaults are `https://api.emergency.wa.gov.au/v1/rss/incidents`, `…/warnings` and `…/fire-danger-ratings`.
- **Something isn't on the map:** check that it's within your tracking radius. Planned burns are hidden if **Ignore burn offs** is on.
- **Fire danger sensors missing:** choose a fire weather district under **Configure**.
- **No aircraft showing:** check **Track emergency aircraft** is on and the radius is big enough. If both ADS-B feeds are down, the aircraft entities show as unavailable while incidents and warnings carry on.
- **Debug logging:**

  ```yaml
  logger:
    logs:
      custom_components.dfes_wa: debug
  ```

## Migrating from REST/template sensors

If you previously pulled the Emergency WA RSS feeds in with `rest:` and `template:` YAML:
1. Set this integration up first.
2. Move your automations and dashboards to the new entities and events.
3. Remove the YAML and restart.

## Development

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install pytest pytest-homeassistant-custom-component
pytest tests tests_ha
```

`tests/` covers the feed and ADS-B parsers without Home Assistant. `tests_ha/` runs the full integration (setup and options, entities, map pins, events, actions, Fire Danger Ratings and emergency aircraft) in a Home Assistant test instance. GitHub Actions runs hassfest, the HACS validation check and the tests on every push.

## Data and licence

Data comes from the public Emergency WA RSS feeds published by the Department of Fire and Emergency Services, Western Australia. This project is not affiliated with or endorsed by DFES. Released under the [GNU General Public License v3.0](LICENSE).
