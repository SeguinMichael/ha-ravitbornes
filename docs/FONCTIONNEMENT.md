# Fonctionnement actuel

> Ce document décrit ce que fait le code **aujourd'hui**. Il est corrigé en place à chaque évolution.

## État au 2026-10-24

Chaîne complète en place, **jamais testée dans une vraie installation HA ni dans une voiture** : position de la voiture → recherche TomTom → disponibilité → 6 capteurs « Borne N ».

### Configuration (`config_flow.py`)

1. **Clé API TomTom**, validée par une recherche minimale (1 requête Search API). Erreurs : clé refusée (401/403), quota atteint (429), TomTom injoignable.
2. **Véhicule et position** : entité de position (`device_tracker` ou `person`), connecteurs compatibles (au moins un ; par défaut CCS Combo 2, prise Type 2, câble Type 2 attaché), profil (par défaut autoroute).
- Ces réglages sont modifiables ensuite (**options**) ; l'intégration se recharge alors.
- Clé dans `data`, réglages dans `options`. Une seule instance.

### Coordinateur (`coordinator.py`)

- **Pas de minuterie** : rafraîchissement déclenché par un changement de l'entité de position, seulement si la voiture a bougé d'au moins **200 m** depuis le dernier rafraîchissement ; au plus un rafraîchissement par **minute** (anti-rebond).
- **À la maison** (état `home`) ou position inconnue : aucun appel ; la liste est vidée en rentrant.
- **Liste des bornes** : recherche autour de la position **arrondie** (~1 km), rayon = rayon du profil + 1 km, 50 résultats au plus, doublons fusionnés ; gardée en mémoire **6 h** par (zone, profil).
- **Disponibilité** : demandée seulement pour les bornes affichées (tri par distance, donc connu avant), gardée **3 min** par borne.
- **Erreurs** : quota atteint ou réseau pendant les appels de disponibilité → on garde ce qu'on a, les bornes restantes passent en « inconnu » (avertissement dans le journal) ; clé refusée ou recherche impossible → capteurs indisponibles (au démarrage : nouvelle tentative plus tard).
- Caches en mémoire uniquement, perdus au redémarrage.

### Capteurs (`sensor.py`, `display.py`)

- 6 capteurs « Borne 1 » à « Borne 6 » (`sensor.ravitbornes_station_N`), rattachés à un appareil de service « RavitBornes ». Inconnus s'il y a moins de bornes.
- **État** : texte court dans la langue de HA (fr ou en), ex. `Ionity · 150 kW · 1,2 km · 3/6 libres`, `… · complet` (aucune prise compatible libre : forme texte de la ligne grisée), `… · dispo ?` (pas de donnée).
- **Attributs** : `latitude` / `longitude` **de la borne** (pour la navigation depuis Android Auto), `station`, `distance_km`, `power_kw`, `available`, `total`, `status`.

### Diagnostics (`diagnostics.py`)

- Clé API et entité de position masquées ; aucune coordonnée ; seulement le nombre de bornes et leurs statuts.

### Filtrage et classement (`scoring.py`)

- Deux profils en dur : **autoroute** (DC uniquement, ≥ 50 kW, rayon 5 km) et **visite** (AC accepté, pas de plancher, rayon 2 km).
- `rank_stations` garde les bornes qui ont au moins un connecteur compatible avec le véhicule et le profil, dans le rayon, puis les **trie par distance** (position exacte utilisée localement uniquement) ; 6 au maximum.
- Statut par borne, calculé sur les **prises compatibles seulement** : `available`, `unavailable` (aucune libre : la borne garde son rang), `unknown` (pas de donnée).

### Client TomTom (`api.py`) et modèles (`models.py`)

- `nearby_stations`, `charging_availability`, `validate_key` ; position arrondie à 2 décimales avant tout appel ; délai maximal 10 s.
- **Clé jamais exposée** : seuls l'endpoint, le code HTTP et la latence sont journalisés (debug) ; les erreurs aiohttp, qui peuvent contenir l'URL, ne sont pas chaînées.
- Connecteurs agrégés par (type, puissance, AC/DC) ; résultats à moins de 25 m fusionnés en gardant celui qui a un identifiant de disponibilité.

## Tests

- `tests/fixtures/` : réponses TomTom réelles, structure conservée, contenu anonymisé.
- `test_sensor.py` (bout en bout) : bornes les plus proches et leurs états, petit déplacement ignoré, cache réutilisé, nouvelle zone, rien à la maison, quota partiel, clé refusée au démarrage.
- `test_scoring.py`, `test_models.py`, `test_api.py` (dont **absence de la clé** dans logs et erreurs), `test_cache.py`, `test_display.py`, `test_diagnostics.py` (**ni clé, ni entité, ni coordonnées**), `test_config_flow.py` (deux étapes, erreurs, options), `test_init.py`.
- Contrôle de pertinence (2026-10-24) : désactiver le seuil de 200 m, le cache de disponibilité, l'exception « maison » ou la dégradation sur quota fait échouer un test.
