# Conception

> Fiche de référence des choix d'architecture. Décisions datées ; à lire pour tout chantier qui touche au score, au cache ou à l'affichage.

## Cache (décision 2026-10-24)

Contexte : cas d'usage = **voyage en voiture** ; on repasse rarement dans la même zone, un cache partagé entre trajets n'apporte presque rien. Source unique en v1 : TomTom.

- **Liste des bornes du trajet** : chargée au départ le long du corridor, conservée **le temps du voyage** (quelques heures). *Implémentation actuelle (2026-10-24) : par zone traversée, faute de recherche le long d'un itinéraire ; voir « Choix pris en autonomie ».*
- **Disponibilité** : TTL **~3 min par borne** (rythme de rafraîchissement annoncé par TomTom). Entre deux rafraîchissements, les rayons de recherche successifs se recouvrent largement (≈ 6,5 km parcourus en 3 min à 130 km/h pour un rayon de 5 km) : le TTL évite de réinterroger les mêmes bornes.
- **Stockage** : en mémoire. Pas de cache long (durée autorisée par les CGU TomTom non précisée).
- **Redis : reporté, pas abandonné.** Il se justifie avec plusieurs sources, une collecte asynchrone et une lecture synchrone depuis HA. Règle conservée pour ce cas : pas d'historique, sauf repli sur le dernier prix connu.

## Choix pris en autonomie (2026-10-24) — à valider

Pris par Claude pendant que l'utilisateur était absent (« avance au maximum sans moi »). Chacun est une constante ou un défaut, facile à changer.

| Sujet | Choix | Où |
|---|---|---|
| Configuration | 2ᵉ étape du config flow + options modifiables : entité de position, connecteurs, profil | `config_flow.py` |
| Défauts | Connecteurs CCS Combo 2 + prise Type 2 + câble Type 2 ; profil autoroute | `const.py` |
| Déclenchement | Sur changement de position uniquement (pas de minuterie), si déplacement ≥ 200 m ; anti-rebond 1 min | `coordinator.py` |
| Domicile | État `home` : aucun appel, liste vidée | `coordinator.py` |
| Liste des bornes | Par zone arrondie (~1 km) et profil, 6 h ; rayon de recherche = rayon du profil + 1 km ; 50 résultats max | `coordinator.py` |
| Disponibilité | Seulement pour les 6 bornes affichées ; 3 min | `coordinator.py` |
| Quota / réseau | Résultats partiels (« inconnu ») + avertissement ; clé refusée → capteurs indisponibles | `coordinator.py` |
| Capteurs | 6 « Borne N » ; état `Nom · kW · km · x/y libres` ; grisé = « complet » en texte (provisoire) ; attributs lat/lon de la borne | `sensor.py`, `display.py` |
| Langue des états | Français si HA est en français, sinon anglais | `display.py` |
| Diagnostics | Clé et entité de position masquées, aucune coordonnée | `diagnostics.py` |
| Puissance du véhicule | Non demandée (inutile avec le tri par distance) | — |

Limites connues : pas de flux de ré-authentification ; à l'arrêt (pas de déplacement), la disponibilité n'est plus rafraîchie ; en zone très dense, 50 résultats peuvent ne pas couvrir tout le rayon.

## Entrée et vie privée (décision 2026-10-24)

- Entrée = **position GPS (lat/lon)** lue depuis une entité HA ; jamais d'adresse, donc pas de géocodage.
- Avant tout appel externe, la position est **arrondie** (tuile / geohash) : le fournisseur reçoit une zone (minimisation des données).
- Les appels partent du serveur HA, jamais du téléphone.
- La position exacte ne sert qu'au calcul local de distance et au tri.

## Configuration véhicule (saisie une fois)

- ~~**Puissance max de charge** : seul paramètre véhicule qui change le classement en v1.~~ Depuis le tri par distance (2026-10-24), elle ne change plus rien en v1 : **non demandée** (redeviendra utile en v2, temps de charge).
- **Connecteurs compatibles** : évite de proposer une borne physiquement incompatible (CCS Combo dans la grande majorité des cas).
- Capacité batterie et consommation : volontairement exclues (redeviendraient utiles en v2 pour un temps de charge).

## Profils de recharge = presets complets

Deux situations aux fonctions de coût opposées. En itinérance, le temps de charge est du temps perdu → la puissance domine. En visite, on charge pendant qu'on fait autre chose → le prix reprend tout le poids.

| | Autoroute | Visite |
|---|---|---|
| Connecteurs | DC uniquement | AC accepté |
| Puissance mini | ≥ 50 kW | pas de plancher |
| Rayon / détour max | ~5 km sur le corridor | ~2 km autour de la destination |
| Fonction de score | minutes perdues | €/kWh |

Deux presets en dur en v1, surchargeables plus tard. La puissance minimale n'est pas un réglage propre : elle découle du profil.

## Score

- **v1 — décision de l'utilisateur (2026-10-24)** : tri **par distance à vol d'oiseau uniquement**, pour les deux profils. Pas de note pondérée.
  - Le profil agit comme **filtre** : connecteurs compatibles avec le véhicule, DC uniquement (autoroute), puissance minimale, rayon maximal.
  - **Aucune prise compatible libre** (toutes occupées, réservées ou hors service) → la borne reste à son rang de distance, **ligne grisée**. Remplace la règle antérieure « bornes `outOfService` écartées ».
  - Choix d'implémentation (2026-10-24, modifiables) : seules les prises **compatibles** comptent (une prise domestique libre ne rend pas disponible une borne pour une voiture Type 2) ; **pas de donnée de disponibilité** → statut « inconnu », ligne **non** grisée ; 6 bornes maximum.
  - Conséquence : la puissance max du véhicule ne change plus le classement en v1.
  - À vérifier sur données réelles (spike Q2) : la disponibilité est rapprochée des connecteurs par (type, puissance) ; un écart de libellé entre la recherche et la disponibilité donnerait « inconnu ».
- **v2** : temps d'accès réel en minutes (Matrix Routing, un appel pour les 10-15 meilleurs candidats). Sur autoroute, métrique cible = **temps total perdu = détour + temps de charge** : passer de 50 à 180 kW fait gagner 20-30 min, un détour de 5 min pèse peu à côté. Tout exprimer en minutes fait entrer la puissance dans le score sans pondération arbitraire.

## Tarifs — limite assumée

TomTom ne fournit pas de tarifs en libre-service. Le champ tarif de l'IRVE est mal renseigné et le prix réel dépend du contrat eMSP (badge, roaming, abonnement). Objectif : « dispo fiable + tarif approximatif ». Badge / pass eMSP écarté de la configuration.

## Exposition dans la voiture (décision 2026-10-24)

Voie retenue : **companion app HA dans Android Auto**. D'après sa documentation (non testé, voir mini-spike dans `WIP.md`) :

- notifications avec `car_ui: true` affichées sur l'écran de la voiture → déclencheur ;
- capteurs affichables en favoris → liste (états textuels, sans mise en forme) ;
- navigation vers les entités `sensor` / `device_tracker` / `zone` / `person` **porteuses d'une position** → exposer les meilleures bornes comme capteurs avec `latitude` / `longitude` ;
- limites : nombre d'entités plafonné par le véhicule, pas de mise en forme, l'app HA doit rester visible dans le lanceur Android Auto pour les notifications `car_ui`, HA doit être joignable en mobilité.

### Modèle d'interaction

1. **Notification voiture** = déclencheur. Texte court, silencieuse par défaut, alerte seulement sur opportunité réelle.
2. **Liste comparative** : 6 éléments maximum en roulant, triés en amont (par distance en v1 ; borne sans prise compatible libre **grisée**). Une ligne = titre + 2 lignes de texte. Format cible : « **Ionity Exemple** — 150 kW · 8 km · 3/6 libres · 0,39 €/kWh ».
3. **Choix d'une borne → navigation**, puis retour à l'application de guidage.

### Pour mémoire : app Android Auto dédiée (reportée)

- App Android obligatoire (Kotlin, `androidx.car.app:app-projected`, catégorie POI), test via DHU.
- Templates imposés, pas d'UI libre ; pas de multi-fenêtre (une app POI passe en plein écran et masque la navigation, qui continue en fond).
- Publication Play Store soumise aux *Driver Distraction Guidelines* ; sideload possible en mode développeur.
- Navigation : `Intent(CarContext.ACTION_NAVIGATE, Uri.parse("geo:0,0?q=lat,lon(Nom)"))` ouvre l'app de navigation par défaut ; un lien `waze://` est inopérant depuis le contexte voiture.
