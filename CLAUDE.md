# CLAUDE.md — règles du dépôt

Intégration Home Assistant (custom component distribué par HACS) : bornes de recharge disponibles autour de la voiture, via les API TomTom, affichées dans Android Auto par le companion app HA. Dépôt **public**.

## Où écrire quoi

- `README.md` (anglais) / `README.fr.md` (français) : présentation utilisateur, courts, tenus synchronisés.
- `docs/FONCTIONNEMENT.md` : ce que fait le code **aujourd'hui** ; corrigé en place.
- `docs/WIP.md` : chantiers décidés et planifiés (ordre, cadrage, décisions datées).
- `docs/TODO.md` : reste à faire non planifié, questions ouvertes.
- `docs/CHANGELOG.md` : ce qui a été fait, en ajout seulement.
- Fiches par sujet, lues seulement si la tâche les concerne : `docs/conception.md` (choix d'architecture, score, cache), `docs/spike-tomtom.md` (résultats du spike sur les données).
- Cycle d'une idée : TODO → WIP → CHANGELOG. Toute décision de l'utilisateur est **datée** et notée là où elle s'applique.

## Langues

Code, commentaires, messages de log, `strings` et `README.md` en **anglais**. `docs/` et ce fichier en **français**.

## Code

- Fichiers de moins de ~400 lignes ; découper par responsabilité quand on les modifie.
- Diff minimal et chirurgical : rien de non demandé, pas d'abstraction spéculative, épouser le style existant. Code mort : le signaler, ne pas le supprimer.
- Expliciter avant de coder : si une demande a plusieurs lectures, les présenter et trancher avec l'utilisateur.
- Tests rapides (`pytest`, sans réseau) pour tout comportement ajouté. Les données de test reprennent la **structure de réponses TomTom réelles** (anonymisées), pas une structure inventée.
- Async uniquement (session HTTP de HA via `async_get_clientsession`), aucun appel bloquant dans la boucle.

## Sécurité et vie privée (exigences, testées)

- La clé API TomTom n'apparaît **jamais** dans les logs, exceptions, diagnostics ni URL journalisées.
- La position est **arrondie** (tuile / geohash) avant tout appel externe ; la position exacte ne sert qu'au calcul local de distance.
- Aucun secret dans le dépôt : pas de `.env`, pas de `.config.sh`. Vérifier `git diff --cached --stat` avant chaque commit.
- Pas de scraping de sites ou d'applis (Chargemap, opérateurs) : uniquement des API officielles.
- Dépôt public : aucune donnée personnelle (adresses, positions réelles, noms d'hôtes privés) dans le code, les tests ou les docs.

## Exploitation

- Ne jamais installer de paquets sur l'hôte pour contourner une panne : conteneur jetable (`docker run --rm …`) ou venv dédié.
- Scripts de spike jetables dans `spikes/` (ignoré par git) ; seules les conclusions vont dans `docs/`.
- Après chaque push : `docs/push_to_trilium.sh` (publie `docs/` dans Trilium sans relecture ; config locale dans `.config.sh`, non versionné).

## Commandes

```bash
pip install -r requirements_test.txt
pytest
```
