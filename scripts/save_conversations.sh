#!/usr/bin/env bash
# Copie les sessions Claude Code actives vers data/conversations/
# Usage : ./scripts/save_conversations.sh
#
# Exécuter en fin de journée pour capturer l'état courant des conversations
# avant que le format interne Claude Code change, que tu nettoies le projet,
# ou simplement pour avoir une réserve hors ~/.claude/.

set -euo pipefail

SRC_DIR="$HOME/.claude/projects/-Users-mathias-Desktop-m-moire-v2"
DEST_DIR="data/conversations"

mkdir -p "$DEST_DIR"

# Copie toutes les sessions modifiées aujourd'hui (dernières 24h)
# en les nommant avec leur ID court pour traçabilité
DATE_TAG=$(date +%Y-%m-%d)
COUNT=0

for src in "$SRC_DIR"/*.jsonl; do
    [ -e "$src" ] || continue
    # Ne copie que les fichiers modifiés dans les dernières 24h
    if [ -n "$(find "$src" -mtime -1 -print 2>/dev/null)" ]; then
        session_id=$(basename "$src" .jsonl)
        short_id="${session_id:0:8}"
        dest="$DEST_DIR/session_${DATE_TAG}_${short_id}.jsonl"
        cp "$src" "$dest"
        size=$(ls -lh "$dest" | awk '{print $5}')
        echo "  [$short_id] $size → $dest"
        COUNT=$((COUNT + 1))
    fi
done

echo ""
echo "$COUNT session(s) copiée(s) vers $DEST_DIR"
