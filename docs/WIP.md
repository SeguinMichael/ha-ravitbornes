# WIP — chantiers décidés et planifiés

> Ordre d'exécution. Chaque chantier se termine par une mise à jour de `FONCTIONNEMENT.md` et du `CHANGELOG.md`, et deux lignes de retour d'expérience.

## Décisions de cadrage (2026-10-24)

- **Forme** : intégration Home Assistant **autonome**, publiée sur GitHub, compatible HACS. Elle appelle TomTom directement ; pas de backend séparé en v1.
- **Affichage voiture** : companion app HA dans Android Auto (notifications `car_ui`, capteurs en favoris, navigation vers des entités porteuses d'une position). Pas d'app Android dédiée en v1.
- **Source de données v1** : TomTom uniquement (recherche de bornes + disponibilité temps réel). Clé TomTom propre à chaque utilisateur.
- **Entrée** : position GPS (lat/lon) lue depuis une entité HA, jamais une adresse ; arrondie avant tout appel externe.
- **Cache** : en mémoire, calé sur la durée du trajet (voir `conception.md`). Redis reporté.
- **Dépôt** : GitHub uniquement. README en anglais + README en français.

## 1. Mini-spike HA ↔ Android Auto (manuel, utilisateur)

But : valider l'affichage voiture **avant** d'écrire l'intégration, sans code.

- Créer dans HA un capteur `template:` avec attributs `latitude` / `longitude` (une borne connue) et un état textuel (« 150 kW · 3/6 libres »).
- Vérifier dans Android Auto : le capteur apparaît-il dans la **navigation** ? Le guidage se lance-t-il ? L'état est-il lisible en favori ?
- Envoyer une notification avec `car_ui: true` : s'affiche-t-elle sur l'écran de la voiture, avec quelles actions ?
- Livrable : constats dans `conception.md` (section exposition) ; go / no-go de la voie HA.

## 2. Fin du spike TomTom

Détail et résultats déjà acquis : `spike-tomtom.md`. Questions restantes :

- Q2 couverture sur trajets réels (dont bornes DC d'autoroute et réseau EVzen) ;
- Q3 fraîcheur de la disponibilité (comparaison terrain) ;
- Q4 coût réel en requêtes avec le cache ;
- Q5 croisement avec l'IRVE (pour les tarifs) ;
- Q6 chargement du corridor par *Along Route Search*.

Scripts jetables dans `spikes/` ; seules les conclusions sont versionnées.

## 3. Client TomTom

> **Fait le 2026-10-24**, sauf la recherche le long d'un itinéraire (attend la question 6 du spike). Voir `FONCTIONNEMENT.md` et `CHANGELOG.md`. Décision de l'utilisateur (2026-10-24) : avancer sur ce chantier avant le mini-spike Android Auto (HA indisponible ce jour-là).

- Module `api.py` asynchrone : `nearby_search`, `along_route_search` *(reste à faire)*, `charging_availability`.
- Agrégation des connecteurs par (type, puissance) dès l'ingestion ; dédoublonnage des stations par position (~20-30 m) en gardant celle qui a un identifiant de disponibilité.
- Gestion du 429 (quota atteint) : état explicite, pas de nouvelle tentative en boucle.
- Validation de la clé dans le config flow (un appel peu coûteux).
- Journalisation des appels (endpoint, code, latence) **sans la clé** ; test qui le garantit.
- Tests sur réponses réelles anonymisées.

## 4. Position, cache et coordinateur

- Choix de l'entité de position dans le config flow (`device_tracker` / `person`).
- Arrondi de la position avant appel externe ; test qui le garantit.
- Liste des bornes du trajet conservée le temps du voyage ; disponibilité en TTL ~3 min par borne.
- `DataUpdateCoordinator` déclenché par le déplacement, pas de polling hors trajet.

## 5. Score et entités

- Configuration véhicule : connecteurs compatibles ; profil par défaut (autoroute / visite). Voir `conception.md`.
- ~~Score v1~~ **fait le 2026-10-24** (`scoring.py`) : tri par distance, profil en filtre, borne sans prise compatible libre grisée (décision utilisateur du 2026-10-24, voir `conception.md`).
- Entités : N capteurs « borne 1…N » (état textuel court, attributs `latitude` / `longitude`, puissance, dispo), N ≤ 6.
