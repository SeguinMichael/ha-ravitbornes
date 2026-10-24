# CHANGELOG

## 2026-10-24

- Création du dépôt : squelette d'intégration HA compatible HACS (config flow qui enregistre la clé API TomTom, chargement / déchargement sans entité), tests, CI (tests, hassfest, validation HACS, audit de dépendances, bandit).
- Documentation reprise du cadrage : `WIP.md`, `TODO.md`, `conception.md`, `spike-tomtom.md`.
- CI : permission `pull-requests: read` pour gitleaks (le job échouait sur les PR Dependabot) ; mises à jour Dependabot fusionnées (checkout v7, setup-python v7, gitleaks-action v3). La validation HACS échoue tant que le dépôt est privé (l'action ne valide que les dépôts publics) : attendu.
