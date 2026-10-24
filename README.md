# RavitBornes

🇬🇧 English · [🇫🇷 Français](README.fr.md)

Home Assistant integration that finds **available EV charging stations** around your car while you drive, and surfaces them on **Android Auto** through the Home Assistant companion app.

> ⚠️ **Status: pre-alpha.** The whole chain is implemented and covered by automated tests, but it has **not yet been tried on a real Home Assistant instance nor in a car**. See [docs/WIP.md](docs/WIP.md) for the roadmap.

## How it works

1. Your phone's position is read from a Home Assistant entity (companion app `device_tracker` or `person`). Nothing is looked up while you are at home.
2. When the car has moved, the integration asks **TomTom** for charging stations around you and for their **real-time availability** (free / occupied / out of service, per connector type and power level).
3. Stations are filtered for your car's connectors and a charging profile — **highway** (DC, 50 kW or more, within 5 km) or **visit** (any power, within 2 km) — and ordered by distance.
4. The 6 nearest are exposed as sensors **Station 1…6**, e.g. `Ionity · 150 kW · 1.2 km · 3/6 free` (or `full` when no compatible connector is free). Each carries the station's latitude / longitude, so you can **navigate to it from Android Auto**.

Planned: a car notification for good opportunities, search along the route, approximate prices.

## Requirements

- Home Assistant 2026.10 or later.
- A **TomTom API key** (free evaluation tier): create one at [my.tomtom.com](https://my.tomtom.com). Each user brings their own key; this project redistributes no data.
- The Home Assistant companion app with Android Auto, for in-car display.

## Installation (HACS)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/SeguinMichael/ha-ravitbornes` as an **Integration**.
2. Install **RavitBornes**, restart Home Assistant.
3. *Settings → Devices & services → Add integration → RavitBornes*, enter your TomTom API key, then choose the position entity, your car's connectors and the charging profile (changeable later in the integration options).

## Privacy and security

- Your API key is stored in the Home Assistant config entry and is never written to logs.
- Your position is **rounded to a coarse area** before any call to an external API: TomTom receives a zone, not your exact location.
- All calls are made from your Home Assistant server, never from your phone. No call is made while you are at home.
- Diagnostics (for bug reports) contain neither your key, nor your position entity, nor any coordinates.

## Data sources

Charging station data and availability: © TomTom. Use of the TomTom APIs is subject to [TomTom's terms](https://docs.tomtom.com/legal/terms-and-conditions). This project does not scrape any website or app.

## Development

Internal working documents (`docs/`) are written in French. Run the tests with:

```bash
pip install -r requirements_test.txt
pytest
```
