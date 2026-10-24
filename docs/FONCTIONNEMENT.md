# Fonctionnement actuel

> Ce document décrit ce que fait le code **aujourd'hui**. Il est corrigé en place à chaque évolution.

## État au 2026-10-24 : squelette

- L'intégration `ravitbornes` se charge dans Home Assistant et s'installe par HACS (dépôt personnalisé).
- **Configuration** (`config_flow.py`) : un seul écran qui demande la clé API TomTom et l'enregistre dans l'entrée de configuration. Une seule instance autorisée. La clé **n'est pas encore validée** auprès de TomTom.
- **Chargement / déchargement** (`__init__.py`) : n'instancie rien pour l'instant ; aucune entité, aucun appel réseau.

## Tests

- `tests/test_config_flow.py` : création de l'entrée, refus d'une seconde instance.
- `tests/test_init.py` : chargement et déchargement de l'entrée.
