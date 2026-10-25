# Spike — TomTom comme source de disponibilité temps réel

> Décidé le 2026-10-24. Code jetable (dans `spikes/`, non versionné) ; seules les conclusions sont consignées ici.

## Question à trancher

TomTom peut-il être la source principale de disponibilité temps réel, en usage personnel, à coût nul ou quasi nul ?

## Constats documentaires (2026-10-24)

- Free tier **mensuel et par API**, sans carte bancaire ; au-delà, **HTTP 429** (pas de facturation surprise). Exemples : Search API 2 500/mois, Places Search Discover / Details 5 000/mois, Matrix Routing 2 500/mois, Routing 20 000/mois. QPS par défaut : Search 5, Routing 5.
- L'**EV Charging Stations Availability API** n'apparaît pas sur la page de tarifs en libre-service, mais elle est **incluse dans la clé d'évaluation**, sans date d'expiration. **Son quota n'est pas communiqué.**
- Disponibilité rafraîchie toutes les 3 min selon la doc, agrégée par type de connecteur et puissance. Une variante Orbis est en *private preview*.
- L'appel de disponibilité exige un identifiant obtenu par une recherche préalable (au moins 2 appels par station).
- **Pas de tarifs** dans les API en libre-service (la notion n'existe que dans l'offre automobile sous contrat).
- **CGU** : durée de stockage des résultats non précisée publiquement ; cache court retenu.
- **Serveur MCP officiel** (`tomtom-international/tomtom-maps-mcp`, Apache 2.0) : outils de recherche de bornes et de recherche le long d'un itinéraire, **aucun outil de disponibilité** → n'évite pas le développement.

## Questions

1. **Accès** : une clé gratuite peut-elle appeler l'API de disponibilité ?
2. **Couverture** : sur des trajets réels (dont DC d'autoroute et réseau EVzen), quelle part des stations a une disponibilité ?
3. **Fraîcheur** : la disponibilité concorde-t-elle avec le terrain (comparaison manuelle, pas de scraping) ?
4. **Coût** : nombre d'appels pour « bornes du trajet + dispo », projection mensuelle.
5. **Croisement IRVE** : rapprochement des stations TomTom et IRVE par coordonnées (tolérance à mesurer).
6. **Chargement du corridor** : *Along Route Search* (Search API v2, catégorie 7309) charge-t-il les bornes d'un trajet en un ou quelques appels ? Mesurer le nombre max de résultats par appel, le détour max, la présence des identifiants de disponibilité, le coût sur un trajet type (1 appel Routing + N appels Search), et comparer avec des `nearbySearch` échelonnés.

## Résultats

### Q1 — accès : OK (2026-10-24)

- Clé en mode évaluation, périmètre incluant EV Charging Stations Availability, Search, Places Search, Routing, Matrix Routing v2. **Pas d'expiration.**
- `search/2/nearbySearch` (catégorie 7309, rayon 5 km, zone urbaine d'Île-de-France) : OK, 100 résultats au total, 10 renvoyés, jugés cohérents avec le terrain.
- Sur 7 stations exploitables, **5 portent un `dataSources.chargingAvailability.id`** (~70 %, échantillon trop petit pour généraliser).
- **Doublons** : un même lieu peut apparaître deux fois (même position, connecteurs différents), une entrée avec identifiant de disponibilité et l'autre sans → dédoublonnage par position.
- Échantillon urbain : uniquement de l'AC ≤ 22 kW, rien sur le profil autoroute.
- Réponses volumineuses (un connecteur par prise) → agréger par (type, puissance) dès l'ingestion.
- `search/2/chargingAvailability` : OK. Réponse compacte : par type de connecteur, `total` et compteurs `available / occupied / reserved / unknown / outOfService`, détaillés par puissance (ex. Type 2 22 kW : 12 au total, 8 libres, 2 occupées, 2 hors service).
- **Aucun horodatage** dans la réponse : la fraîcheur n'est pas vérifiable par l'API → Q3 passe par le terrain.
- `outOfService` est exploitable directement pour écarter les bornes en panne.
- Compteurs d'usage du dashboard restés à zéro après les premiers appels (délai de remontée probable).

### Q4 — piste de conception

- Liste des bornes chargée au départ et conservée le temps du trajet ; disponibilité en TTL ~3 min par borne (voir `conception.md`).
- Le quota Search n'est consommé qu'au chargement du corridor ; la contrainte de coût porte sur le quota (inconnu) de l'API de disponibilité.
- Ordre de grandeur (**estimation, non mesurée**) : ~10 appels de disponibilité par rafraîchissement, toutes les 3 min sur 1 h ≈ 200 appels/h avant déduplication par le TTL.

### Q2 — couverture autoroute : premier essai (2026-10-25), à compléter

- `nearbySearch` (rayon 3 km, limite 5) centré sur une **aire d'autoroute** d'un trajet habituel (deux aires face à face) : **un seul résultat**, une borne **AC** de village à 1,1 km (2 × Type 2 22 kW + 2 prises domestiques). **Aucune borne sur les aires elles-mêmes.**
- Deux lectures possibles : pas de borne rapide sur ces aires, ou **trou de couverture TomTom**. À trancher par une source indépendante (vérification manuelle dans Chargemap, sans extraction).
- `chargingAvailability` sur cette borne : OK ; libellés de connecteur et puissances **identiques** entre recherche et disponibilité (`StandardHouseholdCountrySpecific` 3 kW, `IEC62196Type2Outlet` 22 kW). Le code (`parse_stations`, `parse_availability`, `rank_stations`) donne sur ces réponses réelles : 22 kW, 1,1 km, 2/2 libres, prise domestique non comptée pour une voiture Type 2.
- **Échantillon DC (2026-10-25)** : seconde aire d'autoroute, où l'utilisateur sait qu'il y a des bornes rapides : TomTom trouve **le hub de recharge de l'aire** (4 × CCS 350 kW, 1 × CCS 50 kW, 1 × CHAdeMO 50 kW, 1 × Type 2 câblé 43 kW AC), avec identifiant de disponibilité ; un seul résultat dans 2 km (autres réseaux éventuels de l'aire : à vérifier).
- Disponibilité du hub : libellés DC **identiques** à la recherche (`IEC62196Type2CCS`, `Chademo`), puissances distinctes par niveau (350 / 50 kW) ; statuts `unknown` et `outOfService` présents. Réponses anonymisées versées en données de test (`nearby_search_dc.json`, `charging_availability_dc.json`).
- **Défaut d'affichage révélé** : CCS 350 kW tous occupés ou inconnus, seul le CCS 50 kW libre → l'affichage annonçait « 350 kW · 1/5 libres ». Corrigé (décision utilisateur 2026-10-25) : puissance de la meilleure prise libre en tête, « 50 kW libre (max 350) · … · 1/5 ».
- Couverture des aires : 1 aire sur 2 sans aucune borne trouvée ; la seconde aire ne prouve pas l'absence de trou (à recouper avec Chargemap).

## Reste à faire

Q2 (couverture des aires, DC, EVzen), Q3, Q4 mesuré, Q5, Q6.

## Livrable

Une page de conclusions : go / no-go TomTom, couverture mesurée, coût mensuel estimé, mode de chargement du corridor, alternative en cas de no-go (concentrateur national IRVE dynamique). Plus deux lignes de retour d'expérience.
