"""Constants for the RavitBornes integration."""

DOMAIN = "ravitbornes"

CONF_POSITION_ENTITIES = "position_entities"
CONF_TRIP_ENTITY = "trip_entity"
CONF_CONNECTORS = "connectors"
CONF_PROFILE = "profile"
# Where approximate prices come from (decision 2026-10-25): nowhere, the IRVE
# online API around the shown stations, or a weekly local copy of the IRVE file.
CONF_TARIFFS = "tariffs"
TARIFFS_OFF = "off"
TARIFFS_ONLINE = "online"
TARIFFS_LOCAL = "local"
TARIFF_SOURCES = [TARIFFS_OFF, TARIFFS_ONLINE, TARIFFS_LOCAL]
DEFAULT_TARIFFS = TARIFFS_ONLINE
# Options-flow field only; the exclusion list itself lives in the HA store.
CONF_EXCLUDED = "excluded"

# Option key -> TomTom connector type (keys must be snake_case for translations).
CONNECTORS = {
    "ccs2": "IEC62196Type2CCS",
    "type2_outlet": "IEC62196Type2Outlet",
    "type2_cable": "IEC62196Type2CableAttached",
    "chademo": "Chademo",
    "type1": "IEC62196Type1",
    "ccs1": "IEC62196Type1CCS",
    "tesla": "Tesla",
    "household": "StandardHouseholdCountrySpecific",
}
# Typical European EV: CCS for fast charging, Type 2 for AC.
DEFAULT_CONNECTORS = ["ccs2", "type2_outlet", "type2_cable"]
DEFAULT_PROFILE = "highway"

# Number of station sensors (Android Auto shows at most 6 rows while driving).
STATION_SLOTS = 6
