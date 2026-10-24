# CHANGELOG

## 2026-10-24

- Création du dépôt : squelette d'intégration HA compatible HACS (config flow qui enregistre la clé API TomTom, chargement / déchargement sans entité), tests, CI (tests, hassfest, validation HACS, audit de dépendances, bandit).
- Documentation reprise du cadrage : `WIP.md`, `TODO.md`, `conception.md`, `spike-tomtom.md`.
- CI : permission `pull-requests: read` pour gitleaks (le job échouait sur les PR Dependabot) ; mises à jour Dependabot fusionnées (checkout v7, setup-python v7, gitleaks-action v3). La validation HACS échoue tant que le dépôt est privé (l'action ne valide que les dépôts publics) : attendu.
- Chantier 3 (client TomTom), hors recherche le long d'un itinéraire : `api.py` (recherche de bornes autour d'un point, disponibilité, validation de clé, erreurs auth / quota / connexion, position arrondie à ~1 km, clé jamais journalisée), `models.py` (agrégation des connecteurs, dédoublonnage à 25 m, disponibilité), validation de la clé dans le config flow. Tests sur réponses réelles anonymisées (19 tests).
- Score v1 (`scoring.py`) : profils autoroute / visite en filtre, tri par distance, statut disponible / indisponible (grisé) / inconnu calculé sur les prises compatibles. 25 tests.
- Chantiers 4 et 5, en autonomie (choix à valider, listés dans `conception.md`) : configuration véhicule et position (2ᵉ étape + options), cache en mémoire, coordinateur déclenché par le déplacement (rien à la maison), 6 capteurs « Borne N » avec position pour la navigation, textes fr/en, diagnostics sans clé ni position. 42 tests ; contrôle de pertinence par mutation de 4 comportements du coordinateur.
- Retour d'expérience : les erreurs aiohttp peuvent embarquer l'URL complète, donc la clé passée en paramètre ; il faut les convertir sans les chaîner (`from None`) et le vérifier par un test, pas seulement filtrer les logs.
