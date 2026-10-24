# RavitBornes

[🇬🇧 English](README.md) · 🇫🇷 Français

Intégration Home Assistant qui repère les **bornes de recharge disponibles** autour de la voiture pendant le trajet, et les affiche dans **Android Auto** via le companion app Home Assistant.

> ⚠️ **État : pré-alpha.** Le dépôt ne contient pour l'instant que le squelette de l'intégration (configuration qui enregistre la clé API). Rien n'est encore récupéré ni affiché. Feuille de route : [docs/WIP.md](docs/WIP.md).

## Fonctionnement prévu

1. La position du téléphone est lue depuis une entité Home Assistant (`device_tracker` ou `person` du companion app).
2. L'intégration interroge les API **TomTom** pour obtenir les bornes le long du trajet et leur **disponibilité en temps réel** (libre / occupée / hors service, par type de connecteur et puissance).
3. Les bornes sont filtrées (connecteurs compatibles, puissance minimale) et classées selon deux profils de recharge : **autoroute** (la puissance d'abord) et **visite** (le prix d'abord).
4. Les meilleures bornes sont exposées sous forme de capteurs Home Assistant porteurs d'une position, pour **lancer la navigation depuis Android Auto** ; une notification voiture peut signaler une opportunité.

## Prérequis

- Home Assistant 2026.10 ou plus récent.
- Une **clé API TomTom** (offre d'évaluation gratuite) : à créer sur [my.tomtom.com](https://my.tomtom.com). Chaque utilisateur utilise sa propre clé ; le projet ne redistribue aucune donnée.
- Le companion app Home Assistant avec Android Auto, pour l'affichage en voiture.

## Installation (HACS)

1. HACS → ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/SeguinMichael/ha-ravitbornes` comme **Intégration**.
2. Installer **RavitBornes**, redémarrer Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration → RavitBornes*, puis saisir la clé API TomTom.

## Vie privée et sécurité

- La clé API est stockée dans l'entrée de configuration Home Assistant et n'est jamais écrite dans les journaux.
- La position est **arrondie à une zone** avant tout appel à une API externe : TomTom reçoit une zone, pas la position exacte.
- Tous les appels partent du serveur Home Assistant, jamais du téléphone.

## Sources de données

Bornes et disponibilité : © TomTom. L'utilisation des API TomTom est soumise aux [conditions de TomTom](https://docs.tomtom.com/legal/terms-and-conditions). Ce projet n'extrait de données d'aucun site ni application.

## Développement

Les documents de travail (`docs/`) sont en français. Lancer les tests :

```bash
pip install -r requirements_test.txt
pytest
```
