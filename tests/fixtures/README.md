# Test fixtures

Real TomTom responses (Search API v2 `nearbySearch`, `chargingAvailability`, October 2026) with their **structure kept as-is** and their content anonymized: station names, addresses, phone numbers, URLs, positions and identifiers are fictional. `irve_tabular.json` holds real rows of the data.gouv.fr IRVE tabular API, with the columns of the national access point resource (from a real response), and operators, contacts, identifiers, addresses and positions replaced. `irve_file.csv` holds the same rows as CSV (column order of the API; boolean encoding `true` / `false` assumed, not checked against the real file).

Do not commit raw API responses.
