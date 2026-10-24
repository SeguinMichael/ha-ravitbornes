# RavitBornes

🇬🇧 English · [🇫🇷 Français](README.fr.md)

Home Assistant integration that finds **available EV charging stations** around your car while you drive, and surfaces them on **Android Auto** through the Home Assistant companion app.

> ⚠️ **Status: pre-alpha.** The setup flow validates your API key and the TomTom client is in place, but no entity is created yet: nothing is displayed. See [docs/WIP.md](docs/WIP.md) for the roadmap.

## How it will work

1. Your phone's position is read from a Home Assistant entity (companion app `device_tracker` or `person`).
2. The integration queries the **TomTom** APIs for charging stations along your route and their **real-time availability** (free / occupied / out of service, per connector type and power level).
3. Stations are filtered (compatible connectors, minimum power) and ranked for two charging profiles: **highway** (power first) and **visit** (price first).
4. The best stations are exposed as Home Assistant sensors carrying a location, so you can **navigate to them from Android Auto**, and a car notification can alert you when a good opportunity shows up.

## Requirements

- Home Assistant 2026.10 or later.
- A **TomTom API key** (free evaluation tier): create one at [my.tomtom.com](https://my.tomtom.com). Each user brings their own key; this project redistributes no data.
- The Home Assistant companion app with Android Auto, for in-car display.

## Installation (HACS)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/SeguinMichael/ha-ravitbornes` as an **Integration**.
2. Install **RavitBornes**, restart Home Assistant.
3. *Settings → Devices & services → Add integration → RavitBornes*, then enter your TomTom API key.

## Privacy and security

- Your API key is stored in the Home Assistant config entry and is never written to logs.
- Your position is **rounded to a coarse area** before any call to an external API: TomTom receives a zone, not your exact location.
- All calls are made from your Home Assistant server, never from your phone.

## Data sources

Charging station data and availability: © TomTom. Use of the TomTom APIs is subject to [TomTom's terms](https://docs.tomtom.com/legal/terms-and-conditions). This project does not scrape any website or app.

## Development

Internal working documents (`docs/`) are written in French. Run the tests with:

```bash
pip install -r requirements_test.txt
pytest
```
