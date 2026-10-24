#!/bin/bash
# push_to_trilium.sh — convertit docs/*.md en HTML et les pousse vers Trilium (sans les lire : aucun token consommé)
#
# Cible : note d'atterrissage du projet (TRILIUM_LANDING_NOTE_ID), une sous-note par fichier
# (créée si absente, sinon contenu remplacé) :
#   FONCTIONNEMENT.md -> fonctionnement
#   WIP.md            -> wip
#   TODO.md           -> todo
#   CHANGELOG.md      -> changelog
#   conception.md     -> conception
#   spike-tomtom.md   -> spike_tomtom
#
# Usage : docs/push_to_trilium.sh [-n|--dry-run] [fonctionnement|wip|todo|changelog|conception|spike_tomtom ...]
# Config : TRILIUM_URL, TRILIUM_TOKEN (ETAPI) et TRILIUM_LANDING_NOTE_ID lus dans .config.sh à la racine
#          du dépôt (non versionné ; modèle : .config.sh.example).
# Markdown -> HTML (markdown-it-py, tables GFM, HTML brut du markdown échappé) ; notes de type "text".

set -euo pipefail

DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$DOCS_DIR")"

# titre de la sous-note -> fichier source
declare -A SOURCES=(
    [fonctionnement]="FONCTIONNEMENT.md"
    [wip]="WIP.md"
    [todo]="TODO.md"
    [changelog]="CHANGELOG.md"
    [conception]="conception.md"
    [spike_tomtom]="spike-tomtom.md"
)
ORDER=(fonctionnement wip todo changelog conception spike_tomtom)

dry_run=0
targets=()
for arg in "$@"; do
    case "$arg" in
        -n|--dry-run) dry_run=1 ;;
        -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *)
            [[ -n "${SOURCES[$arg]:-}" ]] || { echo "[!] cible inconnue : $arg (attendu : ${ORDER[*]})" >&2; exit 1; }
            targets+=("$arg") ;;
    esac
done
[[ ${#targets[@]} -eq 0 ]] && targets=("${ORDER[@]}")

# shellcheck disable=SC1091
source "$REPO_DIR/.config.sh"
: "${TRILIUM_URL:?TRILIUM_URL non défini (.config.sh)}"
: "${TRILIUM_TOKEN:?TRILIUM_TOKEN non défini (.config.sh)}"
: "${TRILIUM_LANDING_NOTE_ID:?TRILIUM_LANDING_NOTE_ID non défini (.config.sh)}"
LANDING_NOTE_ID="$TRILIUM_LANDING_NOTE_ID"
command -v jq >/dev/null || { echo "[!] jq requis" >&2; exit 1; }
python3 -c 'import markdown_it' 2>/dev/null || { echo "[!] python3-markdown-it requis (apt install python3-markdown-it)" >&2; exit 1; }

md_to_html() {  # md_to_html <fichier.md> -> HTML sur stdout
    python3 -I -c '
import sys
from markdown_it import MarkdownIt
md = MarkdownIt("commonmark", {"html": False}).enable("table")
sys.stdout.write(md.render(open(sys.argv[1], encoding="utf-8").read()))
' "$1"
}

etapi() {  # etapi <méthode> <chemin> [args curl...]
    local method="$1" path="$2"; shift 2
    curl -sS --fail-with-body -X "$method" -H "Authorization: Bearer $TRILIUM_TOKEN" \
        "${TRILIUM_URL%/}/etapi/$path" "$@"
}

# ID de la sous-note de titre $1 sous la note d'atterrissage (vide si absente)
find_child() {
    local title="$1" query
    query=$(jq -rn --arg t "note.title = \"$title\"" '$t|@uri')
    etapi GET "notes?search=${query}&ancestorNoteId=${LANDING_NOTE_ID}&ancestorDepth=eq1" \
        | jq -r '.results[0].noteId // empty'
}

rc=0
for title in "${targets[@]}"; do
    file="$DOCS_DIR/${SOURCES[$title]}"
    if [[ ! -f "$file" ]]; then
        echo "[!] $file introuvable" >&2; rc=1; continue
    fi
    if (( dry_run )); then
        echo "[dry-run] ${SOURCES[$title]} -> « $title » sous $LANDING_NOTE_ID ($(wc -c < "$file") octets)"
        continue
    fi
    note_id=$(find_child "$title")
    if [[ -z "$note_id" ]]; then
        note_id=$(jq -n --arg p "$LANDING_NOTE_ID" --arg t "$title" \
            '{parentNoteId:$p,title:$t,type:"text",mime:"text/html",content:""}' \
            | etapi POST create-note -H "Content-Type: application/json" -d @- \
            | jq -r '.note.noteId')
        echo "[+] note « $title » créée ($note_id)"
    fi
    if [[ "$(etapi GET "notes/$note_id" | jq -r '.type')" != "text" ]]; then
        etapi PATCH "notes/$note_id" -H "Content-Type: application/json" -d '{"type":"text","mime":"text/html"}' >/dev/null
        echo "[~] note « $title » convertie en type text"
    fi
    md_to_html "$file" | etapi PUT "notes/$note_id/content" -H "Content-Type: application/octet-stream" --data-binary @- >/dev/null
    echo "[✓] ${SOURCES[$title]} -> « $title » ($note_id)"
done
exit $rc
