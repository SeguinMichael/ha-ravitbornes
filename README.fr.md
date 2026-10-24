# RavitBornes

[🇬🇧 English](README.md) · 🇫🇷 Français

Intégration Home Assistant qui repère les **bornes de recharge disponibles** autour de la voiture pendant le trajet, et les affiche dans **Android Auto** via le companion app Home Assistant.

> ⚠️ **État : pré-alpha.** Toute la chaîne est en place et couverte par des tests automatiques, mais elle n'a **pas encore été essayée sur une vraie instance Home Assistant ni en voiture**. Feuille de route : [docs/WIP.md](docs/WIP.md).

## Fonctionnement

1. La position du téléphone est lue depuis une entité Home Assistant (`device_tracker` ou `person` du companion app). Aucune recherche n'est faite tant que vous êtes à la maison.
2. Quand la voiture a bougé, l'intégration demande à **TomTom** les bornes autour de vous et leur **disponibilité en temps réel** (libre / occupée / hors service, par type de connecteur et puissance).
3. Les bornes sont filtrées selon les connecteurs de la voiture et un profil de recharge — **autoroute** (DC, 50 kW ou plus, à moins de 5 km) ou **visite** (toute puissance, à moins de 2 km) — puis triées par distance.
4. Les 6 plus proches sont exposées sous forme de capteurs **Borne 1…6**, par exemple `Ionity · 150 kW · 1,2 km · 3/6 libres` (ou `complet` si aucune prise compatible n'est libre). Chacun porte la latitude / longitude de la borne, pour **lancer la navigation depuis Android Auto**.

Prévu : une notification voiture sur opportunité, la recherche le long de l'itinéraire, des tarifs approximatifs.

## Prérequis

- Home Assistant 2026.10 ou plus récent.
- Une **clé API TomTom** (offre d'évaluation gratuite) : à créer sur [my.tomtom.com](https://my.tomtom.com). Chaque utilisateur utilise sa propre clé ; le projet ne redistribue aucune donnée.
- Le companion app Home Assistant avec Android Auto, pour l'affichage en voiture.

## Installation (HACS)

1. HACS → ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/SeguinMichael/ha-ravitbornes` comme **Intégration**.
2. Installer **RavitBornes**, redémarrer Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration → RavitBornes*, saisir la clé API TomTom, puis choisir l'entité de position, les connecteurs de la voiture et le profil de recharge (modifiables ensuite dans les options de l'intégration).

## Vie privée et sécurité

- La clé API est stockée dans l'entrée de configuration Home Assistant et n'est jamais écrite dans les journaux.
- La position est **arrondie à une zone** avant tout appel à une API externe : TomTom reçoit une zone, pas la position exacte.
- Tous les appels partent du serveur Home Assistant, jamais du téléphone. Aucun appel n'est fait quand vous êtes à la maison.
- Les diagnostics (pour signaler un bug) ne contiennent ni la clé, ni l'entité de position, ni aucune coordonnée.

## Sources de données

Bornes et disponibilité : © TomTom. L'utilisation des API TomTom est soumise aux [conditions de TomTom](https://docs.tomtom.com/legal/terms-and-conditions). Ce projet n'extrait de données d'aucun site ni application.

## Développement

Les documents de travail (`docs/`) sont en français. Lancer les tests :

```bash
pip install -r requirements_test.txt
pytest
```
