# RavitBornes

[🇬🇧 English](README.md) · 🇫🇷 Français

Intégration Home Assistant qui repère les **bornes de recharge disponibles** autour de la voiture pendant le trajet, et les affiche dans **Android Auto** via le companion app Home Assistant.

> ⚠️ **État : preuve de concept (POC), jamais testée de bout en bout.** Toute la chaîne est en place et couverte par des tests automatiques, mais elle n'a **pas encore été essayée sur une vraie instance Home Assistant ni en voiture**. Feuille de route : [docs/WIP.md](docs/WIP.md).

## Fonctionnement

1. La position de la voiture est lue depuis une ou plusieurs entités Home Assistant (`device_tracker` du téléphone et/ou de la voiture, ou `person`) ; la plus récemment mise à jour l'emporte. Aucune recherche n'est faite tant que vous êtes à la maison.
2. Quand la voiture a bougé — et, si vous choisissez une entité de *trajet* comme le capteur Android Auto du companion app, toutes les 3 minutes tant qu'elle est allumée, même à l'arrêt — l'intégration demande à **TomTom** les bornes autour de vous et leur **disponibilité en temps réel** (libre / occupée / hors service, par type de connecteur et puissance).
3. Les bornes sont filtrées selon les connecteurs de la voiture et un profil de recharge — **autoroute** (DC, 50 kW ou plus, à moins de 5 km) ou **visite** (toute puissance, à moins de 2 km) — puis triées par distance.
4. Les 6 plus proches sont exposées sous forme de capteurs **Borne 1…6**, par exemple `IONITY (A6, Aire X) · 150 kW · 1,2 km · 3/6 libres` (ou `50 kW libre (max 350)` si seules des prises plus lentes sont libres, ou `complet` si aucune ne l'est). En France, un **tarif approximatif** s'ajoute quand le fichier national IRVE (open data) en donne un lisible, ex. `· 0,29 €/kWh` ; le prix réel dépend de votre badge ou abonnement. Les tarifs se récupèrent en ligne (par défaut), depuis une copie locale du fichier téléchargée chaque semaine (~120 Mo, plus discret), ou se désactivent. Chacun porte la latitude / longitude de la borne, pour **lancer la navigation depuis Android Auto**. Un bouton **Rechercher des bornes (30 min)** lance une recherche tout de suite puis toutes les 3 minutes pendant 30 minutes, même hors trajet ou à la maison. Un bouton **Masquer la borne N** écarte une borne dont vous ne voulez pas (mauvaise expérience, trop fréquentée, peu accessible…), au besoin seulement pendant la recharge ; les bornes masquées restent sur votre Home Assistant et se réaffichent depuis les options de l'intégration.

Prévu : une notification voiture sur opportunité, la recherche le long de l'itinéraire.

## Prérequis

- Home Assistant 2026.10 ou plus récent.
- Une **clé API TomTom** (offre d'évaluation gratuite) : à créer sur [my.tomtom.com](https://my.tomtom.com). Chaque utilisateur utilise sa propre clé ; le projet ne redistribue aucune donnée.
- Le companion app Home Assistant avec Android Auto, pour l'affichage en voiture.

## Installation (HACS)

1. HACS → ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/SeguinMichael/ha-ravitbornes` comme **Intégration**.
2. Installer **RavitBornes**, redémarrer Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration → RavitBornes*, saisir la clé API TomTom, puis choisir les sources de position, une entité de trajet facultative, les connecteurs de la voiture et le profil de recharge (modifiables ensuite dans les options de l'intégration).

## Vie privée et sécurité

- La clé API est stockée dans l'entrée de configuration Home Assistant et n'est jamais écrite dans les journaux.
- La position est **arrondie à une zone** avant tout appel à une API externe : TomTom reçoit une zone, pas la position exacte.
- Pour les tarifs, data.gouv.fr reçoit la position des **bornes affichées** (6 au plus, puis cache d'une journée), pas la vôtre ; comme elles sont proches de vous, elles situent tout de même votre zone à quelques kilomètres près, comme la zone envoyée à TomTom. Avec l'option *fichier local*, aucune position n'est envoyée pour les tarifs.
- Tous les appels partent du serveur Home Assistant, jamais du téléphone. Aucun appel n'est fait quand vous êtes à la maison, sauf si vous appuyez sur *Rechercher des bornes*.
- Les diagnostics (pour signaler un bug) ne contiennent ni la clé, ni l'entité de position, ni aucune coordonnée.

## Sources de données

Bornes et disponibilité : © TomTom. L'utilisation des API TomTom est soumise aux [conditions de TomTom](https://docs.tomtom.com/legal/terms-and-conditions). Ce projet n'extrait de données d'aucun site ni application.

## Développement

Les documents de travail (`docs/`) sont en français. Lancer les tests :

```bash
pip install -r requirements_test.txt
pytest
```

## Licence

[MIT](LICENSE).
