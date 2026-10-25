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

- `nearbySearch` (rayon 3 km, limite 5) centré sur une **aire d'autoroute choisie au hasard** (deux aires face à face) : **un seul résultat**, une borne **AC** de village à 1,1 km (2 × Type 2 22 kW + 2 prises domestiques). **Aucune borne sur les aires elles-mêmes.**
- Aire choisie au hasard ; **vérifié par l'utilisateur (2026-10-25)** : l'aire n'a effectivement **pas de borne**, et il y en a bien dans le village voisin. TomTom est **exact** sur ce cas (absence sur l'aire, borne du village trouvée).
- `chargingAvailability` sur cette borne : OK ; libellés de connecteur et puissances **identiques** entre recherche et disponibilité (`StandardHouseholdCountrySpecific` 3 kW, `IEC62196Type2Outlet` 22 kW). Le code (`parse_stations`, `parse_availability`, `rank_stations`) donne sur ces réponses réelles : 22 kW, 1,1 km, 2/2 libres, prise domestique non comptée pour une voiture Type 2.
- **Échantillon DC (2026-10-25)** : seconde aire d'autoroute, où l'utilisateur sait qu'il y a des bornes rapides : TomTom trouve **le hub de recharge de l'aire** (4 × CCS 350 kW, 1 × CCS 50 kW, 1 × CHAdeMO 50 kW, 1 × Type 2 câblé 43 kW AC), avec identifiant de disponibilité ; un seul résultat dans 2 km (autres réseaux éventuels de l'aire : à vérifier).
- Disponibilité du hub : libellés DC **identiques** à la recherche (`IEC62196Type2CCS`, `Chademo`), puissances distinctes par niveau (350 / 50 kW) ; statuts `unknown` et `outOfService` présents. Réponses anonymisées versées en données de test (`nearby_search_dc.json`, `charging_availability_dc.json`).
- **Défaut d'affichage révélé** : CCS 350 kW tous occupés ou inconnus, seul le CCS 50 kW libre → l'affichage annonçait « 350 kW · 1/5 libres ». Corrigé (décision utilisateur 2026-10-25) : puissance de la meilleure prise libre en tête, « 50 kW libre (max 350) · … · 1/5 ».
- Couverture des aires : **2 aires vérifiées sur le terrain, 2 concordances** (une sans borne, une avec un hub DC trouvé). Encourageant, mais échantillon trop petit pour conclure : tester d'autres aires, dont une avec **plusieurs réseaux**, pour vérifier qu'ils remontent tous.

### Q2 — ville moyenne, filtres côté TomTom (2026-10-25)

- Sans filtre (rayon 3 km, limite 10) : 50 bornes au total ; les 10 plus proches sont surtout de l'AC 22 kW et des DC 24-25 kW ; **une seule** borne utile en profil autoroute. Avec la limite de 50 du coordinateur, une borne rapide plus lointaine pouvait être **écartée sans le savoir**.
- **`connectorSet` et `minPowerKW` sont bien appliqués par TomTom** (rayon 6 km, CCS, ≥ 50 kW) : 18 résultats, tous avec du CCS ≥ 100 kW ; les DC 25 kW disparaissent. Implémenté.
- **Plusieurs réseaux remontent** dans une même zone : ChargePoint, Electra, Fastned, Izivia, TotalEnergies, syndicat départemental. Aucun Tesla vu (présence locale non vérifiée).
- 9 résultats sur 10 avec identifiant de disponibilité (sans filtre).
- **Doublons ambigus** : deux entrées du même opérateur à ~10 m, **chacune avec son identifiant de disponibilité** et des connecteurs différents → le dédoublonnage en garde une, la disponibilité de l'autre est perdue. Voir TODO.
- **Noms peu lisibles** : 6 bornes sur 10 portent le même nom long d'opérateur public (tronqué, identique d'une ligne à l'autre). Voir TODO.

### IRVE dynamique vs TomTom (2026-10-25)

Question : l'IRVE (statique + dynamique, open data) pourrait-elle remplacer TomTom ?

- L'**IRVE statique** donne position, prises, puissance et **tarif** (texte libre, souvent vide), mais **pas la disponibilité** ; France seulement ; qualité inégale (coordonnées non vérifiées pour certains opérateurs, données d'un grand réseau figées depuis mars 2026 selon le suivi qualité du PAN).
- L'**IRVE dynamique** (consolidation nationale du PAN, obligation AFIR) : suivi qualité du PAN au 2026-10-09 — part des points avec un statut de moins de 30 min : **0 %** pour Izivia, Aldi, Qovoltis, Electra ; 19 % Ionity ; 47 % Tesla. Flux GIREVE **figé depuis le 2026-06-15** (33 606 points). Une intégration domotique tierce qui l'utilise constate qu'à peine plus de la moitié des points publics d'une grande ville ont un état.
- **TomTom sur ces mêmes réseaux** (ville moyenne d'Île-de-France) : Electra 300 kW → 3 libres / 1 occupée ; Izivia 150 kW → 4/4 libres ; aucun statut « inconnu ». Les statuts sont renseignés là où l'IRVE dynamique n'a rien. Limite : sans horodatage, la fraîcheur n'est pas prouvée (une prise occupée chez Electra suggère une donnée vivante) → Q3, comparaison avec l'appli de l'opérateur au même instant.
- **Conclusion** : **TomTom reste la source de disponibilité** ; l'IRVE statique sert aux **tarifs**. L'IRVE dynamique pourra être réévaluée comme source complémentaire si sa couverture progresse.

## Reste à faire

Q2 (EVzen, aire multi-réseaux dont Tesla), Q3 (fraîcheur : comparer avec l'appli d'un opérateur au même instant), Q4 mesuré, Q5 (croisement IRVE pour les tarifs), Q6.

## Livrable

Une page de conclusions : go / no-go TomTom, couverture mesurée, coût mensuel estimé, mode de chargement du corridor, alternative en cas de no-go (concentrateur national IRVE dynamique). Plus deux lignes de retour d'expérience.
