# Fonctionnement actuel

> Ce document décrit ce que fait le code **aujourd'hui**. Il est corrigé en place à chaque évolution.

## État au 2026-10-24

L'intégration se configure et sait interroger TomTom, mais n'expose encore **aucune entité** : le client n'est appelé que par la configuration.

### Configuration (`config_flow.py`)

- Un écran demande la clé API TomTom de l'utilisateur ; une seule instance autorisée.
- La clé est **validée** par une recherche minimale (1 requête Search API). Erreurs affichées : clé refusée (401/403), quota atteint (429), TomTom injoignable (réseau, délai, autre code HTTP).

### Client TomTom (`api.py`)

- `nearby_stations(lat, lon, radius_m, limit)` : bornes autour d'un point (Search API v2 `nearbySearch`, catégorie 7309).
- `charging_availability(availability_id)` : disponibilité temps réel d'une station.
- `validate_key()` : recherche minimale en (0, 0).
- **Arrondi de la position** à 2 décimales (≈ 1 km) avant tout appel : TomTom reçoit une zone.
- **Clé jamais exposée** : seuls le nom d'endpoint, le code HTTP et la latence sont journalisés (niveau debug) ; les erreurs aiohttp, qui peuvent contenir l'URL et donc la clé, ne sont pas chaînées.
- Délai maximal par requête : 10 s.

### Modèles (`models.py`)

- `parse_stations` : une `Station` par résultat, connecteurs **agrégés** par (type, puissance, AC/DC) avec un nombre de prises ; identifiant de disponibilité s'il existe ; résultats sans position ignorés.
- `dedupe_stations` : deux résultats à moins de 25 m sont la même station ; on garde celui qui a un identifiant de disponibilité.
- `parse_availability` : compteurs libre / occupé / réservé / inconnu / hors service, par type de connecteur et niveau de puissance.

### Filtrage et classement (`scoring.py`)

- Deux profils en dur : **autoroute** (DC uniquement, ≥ 50 kW, rayon 5 km) et **visite** (AC accepté, pas de plancher, rayon 2 km).
- `rank_stations` garde les bornes qui ont au moins un connecteur compatible avec le véhicule et le profil, dans le rayon, puis les **trie par distance** (position exacte utilisée localement uniquement) ; 6 au maximum.
- Statut par borne, calculé sur les **prises compatibles seulement** : `available` (au moins une libre), `unavailable` (aucune libre : à afficher grisé, la borne garde son rang), `unknown` (pas de donnée de disponibilité).
- Non encore appelé : sera branché par le coordinateur (chantier 4).

### Chargement (`__init__.py`)

- N'instancie rien pour l'instant ; aucune entité.

## Tests

- `tests/fixtures/` : réponses TomTom réelles, structure conservée, contenu anonymisé.
- `test_models.py` : agrégation, DC, absence de disponibilité, dédoublonnage, disponibilité.
- `test_api.py` : arrondi de la position, mapping des erreurs HTTP, timeout, **absence de la clé dans les logs et les erreurs**.
- `test_scoring.py` : filtre par profil, tri par distance, borne grisée gardée à son rang, prise incompatible non comptée, disponibilité inconnue, limite.
- `test_config_flow.py` : création avec validation, erreurs, instance unique.
- `test_init.py` : chargement et déchargement.
