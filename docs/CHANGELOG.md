# CHANGELOG

## 2026-10-24

- Création du dépôt : squelette d'intégration HA compatible HACS (config flow qui enregistre la clé API TomTom, chargement / déchargement sans entité), tests, CI (tests, hassfest, validation HACS, audit de dépendances, bandit).
- Documentation reprise du cadrage : `WIP.md`, `TODO.md`, `conception.md`, `spike-tomtom.md`.
- CI : permission `pull-requests: read` pour gitleaks (le job échouait sur les PR Dependabot) ; mises à jour Dependabot fusionnées (checkout v7, setup-python v7, gitleaks-action v3). La validation HACS échoue tant que le dépôt est privé (l'action ne valide que les dépôts publics) : attendu.
- Chantier 3 (client TomTom), hors recherche le long d'un itinéraire : `api.py` (recherche de bornes autour d'un point, disponibilité, validation de clé, erreurs auth / quota / connexion, position arrondie à ~1 km, clé jamais journalisée), `models.py` (agrégation des connecteurs, dédoublonnage à 25 m, disponibilité), validation de la clé dans le config flow. Tests sur réponses réelles anonymisées (19 tests).
- Score v1 (`scoring.py`) : profils autoroute / visite en filtre, tri par distance, statut disponible / indisponible (grisé) / inconnu calculé sur les prises compatibles. 25 tests.
- Chantiers 4 et 5, en autonomie (choix à valider, listés dans `conception.md`) : configuration véhicule et position (2ᵉ étape + options), cache en mémoire, coordinateur déclenché par le déplacement (rien à la maison), 6 capteurs « Borne N » avec position pour la navigation, textes fr/en, diagnostics sans clé ni position. 42 tests ; contrôle de pertinence par mutation de 4 comportements du coordinateur.
- Retour d'expérience (chantiers 4-5) : faire échouer volontairement chaque comportement clé (mutation à la main) confirme que les tests le couvrent vraiment ; 42 tests verts ne le prouvaient pas à eux seuls.
- Retour d'expérience : les erreurs aiohttp peuvent embarquer l'URL complète, donc la clé passée en paramètre ; il faut les convertir sans les chaîner (`from None`) et le vérifier par un test, pas seulement filtrer les logs.

## 2026-10-25

- Décisions de l'utilisateur (détail dans `conception.md`) : trajet = Android Auto connecté (rafraîchissement toutes les 3 min même à l'arrêt), position la plus récente parmi plusieurs sources, bornes masquables au volant.
- Entité de trajet facultative ; plusieurs sources de position (`last_reported`) ; 6 boutons « Masquer la borne N » ; liste persistante dans `.storage`, reconnue par ID ou position, démasquage dans les options ; adresse de la borne conservée ; diagnostics étendus sans donnée personnelle. 49 tests.
- **Rupture** : l'option `position_entity` devient `position_entities` (liste). Pas de migration : aucune installation existante (pré-alpha).
- Retour d'expérience : HA n'émet pas de `state_changed` quand une entité renvoie exactement la même valeur, et ne recharge pas une intégration dont les options n'ont pas changé ; deux tests l'ont révélé (démasquage sans rafraîchissement : corrigé). Écrire les tests sur le scénario réel (une voiture qui roule change de position) plutôt que sur une valeur réutilisée.
