#!/usr/bin/env bash
# Sobe o InventarIA no computador, fora do Home Assistant: http://127.0.0.1:8099
#
#   dev/run.sh             com a casa de teste (inventada, tests/fixtures/casa) e a IA simulada
#   dev/run.sh --vazio     sem nada, como numa instalação nova (tela de boas-vindas)
#   dev/run.sh --limpar    apaga o que foi mudado e começa de novo
#
# Os dados ficam em .dev/ (fora do git). INV_PORT muda a porta.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV="$ROOT/.dev"
SEED="$ROOT/tests/fixtures/casa"
for a in "$@"; do
  case "$a" in
    --vazio) SEED="$ROOT/inventario/seed"; DEV="$ROOT/.dev-vazio" ;;
    --limpar) rm -rf "$ROOT/.dev" "$ROOT/.dev-vazio" ;;
    *) echo "uso: $0 [--vazio] [--limpar]"; exit 2 ;;
  esac
done
mkdir -p "$DEV/data" "$DEV/share" "$DEV/media"
cd "$ROOT/inventario/app"
echo "InventarIA em http://127.0.0.1:${INV_PORT:-8099} (dados em $DEV)"
exec env INV_DEV=1 INV_AI_MOCK=1 INV_DATA="$DEV/data" INV_SEED="$SEED" INV_WEB="$ROOT/inventario/app/web" \
  INV_SHARE="$DEV/share" INV_MEDIA="$DEV/media" INV_PORT="${INV_PORT:-8099}" python3 server.py
