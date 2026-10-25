# Fonctionnement actuel

> Ce document décrit ce que fait le code **aujourd'hui**. Il est corrigé en place à chaque évolution.

## État au 2026-10-25

Chaîne complète en place, **jamais testée dans une vraie installation HA ni dans une voiture** : position de la voiture → recherche TomTom → disponibilité → 6 capteurs « Borne N » et 6 boutons « Masquer la borne N ».

### Configuration (`config_flow.py`)

1. **Clé API TomTom**, validée par une recherche minimale (1 requête Search API). Erreurs : clé refusée (401/403), quota atteint (429), TomTom injoignable.
2. **Position, trajet et véhicule** : une ou plusieurs **sources de position** (`device_tracker` ou `person` : téléphone, voiture…), une **entité de trajet** facultative (`binary_sensor`, ex. Android Auto connecté), connecteurs compatibles (au moins un ; par défaut CCS Combo 2, prise Type 2, câble Type 2 attaché), profil (par défaut autoroute).
- Ces réglages sont modifiables ensuite (**options**) ; l'intégration se recharge alors. Les options listent aussi les **bornes masquées** (cochées) : décocher les réaffiche.
- Clé dans `data`, réglages dans `options`. Une seule instance.

### Coordinateur (`coordinator.py`)

- **Position** : parmi les sources configurées ayant des coordonnées, celle **rapportée le plus récemment** (`last_reported`).
- **Sans entité de trajet** : pas de minuterie ; rafraîchissement déclenché par un changement d'une source de position, seulement si la voiture a bougé d'au moins **200 m** ; au plus un par **minute** (anti-rebond).
- **Avec entité de trajet** : allumée → rafraîchissement **toutes les 3 min même à l'arrêt**, plus les déplacements ; éteinte → aucun appel automatique, liste vidée, déplacements ignorés.
- **Recherche manuelle** (bouton « Rechercher des bornes (30 min) ») : recherche immédiate puis toutes les 3 min pendant 30 min, hors trajet et à la maison compris ; un nouvel appui relance les 30 min ; à l'échéance, liste vidée aussitôt sauf trajet en cours.
- **À la maison** (état `home` de la source retenue) ou position inconnue : aucun appel hors recherche manuelle ; la liste est vidée en rentrant.
- Les **bornes masquées** sont retirées avant le classement.
- **Liste des bornes** : recherche autour de la position **arrondie** (~1 km), rayon = rayon du profil + 1 km, 50 résultats au plus, doublons fusionnés ; gardée en mémoire **6 h** par (zone, profil).
- **Disponibilité** : demandée seulement pour les bornes affichées (tri par distance, donc connu avant), gardée **3 min** par borne.
- **Erreurs** : quota atteint ou réseau pendant les appels de disponibilité → on garde ce qu'on a, les bornes restantes passent en « inconnu » (avertissement dans le journal) ; clé refusée ou recherche impossible → capteurs indisponibles (au démarrage : nouvelle tentative plus tard).
- Caches en mémoire uniquement, perdus au redémarrage.

### Capteurs (`sensor.py`, `display.py`)

- 6 capteurs « Borne 1 » à « Borne 6 » (`sensor.ravitbornes_station_N`), rattachés à un appareil de service « RavitBornes ». Inconnus s'il y a moins de bornes.
- **État** : texte court dans la langue de HA (fr ou en), ex. `Ionity · 150 kW · 1,2 km · 3/6 libres`, `… · complet` (aucune prise compatible libre : forme texte de la ligne grisée), `… · dispo ?` (pas de donnée).
- **Attributs** : `latitude` / `longitude` **de la borne** (pour la navigation depuis Android Auto), `station`, `distance_km`, `power_kw`, `available`, `total`, `status`.

### Boutons et bornes masquées (`button.py`, `exclusions.py`)

- Bouton « Rechercher des bornes (30 min) » (`button.ravitbornes_search_stations_30_min`), toujours disponible.
- 6 boutons « Masquer la borne N » (`button.ravitbornes_hide_station_N`), indisponibles quand l'emplacement est vide. Un appui masque la borne affichée et réaffiche la liste aussitôt, depuis les caches (sans nouvel appel TomTom tant que les caches sont valides).
- Liste **persistante** dans `.storage/ravitbornes.<entry_id>.excluded` (ID TomTom, nom, adresse, position de la borne) ; supprimée quand l'intégration est retirée.
- Une borne est reconnue comme masquée par son ID **ou** par sa position (≤ 25 m), au cas où TomTom change l'ID.

### Diagnostics (`diagnostics.py`)

- Clé API et entités (position, trajet) masquées ; aucune coordonnée ; nombre de bornes, statuts, état du trajet, **nombre** de bornes masquées (pas leur liste).

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
- `test_manual_search.py` : pas de minuterie sans entité de trajet (non-régression), bouton à la maison et hors trajet, sans entité de trajet, effacement immédiat à l'échéance, relance de la fenêtre, fin de trajet pendant la fenêtre.
- `test_trip_and_exclusions.py` : rafraîchissement toutes les 3 min pendant le trajet et arrêt ensuite, déplacements ignorés hors trajet, source de position la plus récente, bouton « Masquer » (persistance, rechargement, aucun appel TomTom), reconnaissance par position, emplacement vide, démasquage dans les options.
- Contrôle de pertinence : désactiver le seuil de 200 m, le cache de disponibilité, l'exception « maison », la dégradation sur quota (2026-10-24), la minuterie de trajet, l'entité de trajet, le choix par fraîcheur, le filtrage des bornes masquées la reconnaissance par position, la dérogation « maison » du bouton, la relance de la fenêtre, l'effacement à l'échéance ou la minuterie sans entité de trajet (2026-10-25) fait échouer au moins un test.
