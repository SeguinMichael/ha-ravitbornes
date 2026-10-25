# TODO — non planifié

## Questions ouvertes

- **Rendu « grisé » dans Android Auto** : le companion app HA n'offre pas de mise en forme des favoris ; à déterminer au mini-spike (texte d'état, icône, ou autre). Le statut `unavailable` est déjà calculé (`scoring.py`).
- **Notification voiture** : déclenchée par l'intégration elle-même, ou par un *blueprint* d'automatisation fourni à côté ? (à trancher après le mini-spike Android Auto)
- **Quota de l'API de disponibilité TomTom** : non communiqué pour l'offre d'évaluation ; la journalisation des appels donnera la consommation réelle (décision 2026-10-24 : on avance sans le connaître).
- **Durée de cache autorisée par les CGU TomTom** : non précisée publiquement ; cache court retenu. À confirmer auprès du support si un cache long devient utile.
- **Licence** du dépôt : à choisir (sans licence, le code public reste « tous droits réservés »).
- **Icône / brand** de l'intégration pour HA et HACS.
- **Durcissement CI** : épingler les actions GitHub par SHA plutôt que par tag ; activer côté GitHub le *secret scanning* et la *push protection* (gratuits sur dépôt public).

- **Ré-authentification** : si TomTom refuse la clé en cours d'usage, les capteurs deviennent indisponibles sans proposer de ressaisir la clé (flux `reauth` à ajouter).
- **Zones denses** : atténué par le filtrage côté TomTom (connecteurs, puissance) ; en profil visite (AC, sans plancher), 50 résultats peuvent encore ne pas couvrir tout le rayon.
- **Doublons à deux identifiants de disponibilité** (même opérateur, ~10 m, connecteurs différents) : un seul site listé deux fois, ou deux bornes distinctes ? Selon la réponse, fusionner en additionnant les disponibilités ou garder les deux lignes. Aujourd'hui, la seconde disponibilité est perdue.
- **Tarifs** : aucune API tarifaire dans l'offre libre-service TomTom constatée à ce jour (la notion n'apparaît que dans l'offre automobile sous contrat) ; l'« EV Search API » n'est pas dans le périmètre de la clé d'évaluation, son contenu n'a pas été vérifié. Décision 2026-10-25 : source tarifaire interchangeable, TomTom si la clé le permet, IRVE sinon (voir `conception.md`).
- **Toucher une ligne → confirmation → guidage** (demande utilisateur, 2026-10-25) : à valider au mini-spike Android Auto (écran « Navigation » du companion app, confirmation ou non ; sinon notification voiture avec action « Y aller »).

## Évolutions envisagées

### Métriques du véhicule (idées de l'utilisateur, 2026-10-25)

Le companion app expose, pendant une session Android Auto, des capteurs voiture (`car_battery` en %, `car_range_remaining` en m, `car_charging_status`…) ; les intégrations constructeur en exposent d'autres. Pistes, chacune comme entité facultative à choisir dans la configuration :

- **Garde « en charge »** pour le bouton « Masquer » (décision utilisateur : à faire) — n'accepter l'appui que pendant une recharge, pour la sécurité au volant.
- **Seuil de batterie** : déclencher la notification voiture sous X %.
- **Autonomie restante** : écarter les bornes hors de portée (surtout utile avec le corridor).
- **En charge** : suspendre les rafraîchissements pendant la recharge (économie de quota).

- **Tarifs** : croisement avec le fichier consolidé IRVE (data.gouv.fr) par coordonnées GPS ; précision approximative assumée (le prix réel dépend du contrat eMSP). TomTom ne fournit pas de tarifs en libre-service.
- **Score v2** : temps d'accès réel en minutes via Matrix Routing (un appel pour les 10-15 meilleurs candidats), métrique « temps total perdu = détour + temps de charge » sur autoroute.
- **Sources multiples** (ex. concentrateur national IRVE dynamique de transport.data.gouv.fr) : justifierait une collecte asynchrone et un cache partagé type Redis.
- **App Android Auto dédiée** (templates car-app) si la voie HA s'avère trop limitée ; synthèse technique dans `conception.md`.
