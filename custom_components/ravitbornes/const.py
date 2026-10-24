"""Constants for the RavitBornes integration."""

DOMAIN = "ravitbornes"

CONF_POSITION_ENTITY = "position_entity"
CONF_CONNECTORS = "connectors"
CONF_PROFILE = "profile"

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
