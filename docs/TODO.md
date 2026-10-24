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
- **Détection du trajet** : le capteur « Android Auto connecté » du companion app pourrait servir de déclencheur (rafraîchir aussi à l'arrêt, en voiture) plutôt que le seul déplacement.
- **Zones denses** : 50 résultats de recherche peuvent ne pas couvrir tout le rayon ; à mesurer (spike Q2).

## Évolutions envisagées

- **Tarifs** : croisement avec le fichier consolidé IRVE (data.gouv.fr) par coordonnées GPS ; précision approximative assumée (le prix réel dépend du contrat eMSP). TomTom ne fournit pas de tarifs en libre-service.
- **Score v2** : temps d'accès réel en minutes via Matrix Routing (un appel pour les 10-15 meilleurs candidats), métrique « temps total perdu = détour + temps de charge » sur autoroute.
- **Sources multiples** (ex. concentrateur national IRVE dynamique de transport.data.gouv.fr) : justifierait une collecte asynchrone et un cache partagé type Redis.
- **App Android Auto dédiée** (templates car-app) si la voie HA s'avère trop limitée ; synthèse technique dans `conception.md`.
