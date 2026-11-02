#!/usr/bin/env bash
# Testes do InventarIA (só Python 3, sem instalar nada):
#
#   tests/run.sh               unitários e de integração
#   tests/run.sh unit          só os unitários
#   tests/run.sh integration   só os de integração
#   tests/run.sh e2e [nomes]   os visuais (precisam do playwright; veja tests/e2e/run.sh)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export TZ="${TZ:-America/Sao_Paulo}"
what="${1:-all}"
code=0
run() {
  echo "== $1"
  (cd "$HERE/$1" && "${PYTHON:-python3}" -W error::ResourceWarning -m unittest discover -s . -t . -p 'test_*.py' "${@:2}") || code=1
}
case "$what" in
  unit) run unit ;;
  integration) run integration ;;
  e2e) shift; exec "$HERE/e2e/run.sh" "$@" ;;
  all) run unit; run integration ;;
  *) echo "uso: $0 [unit|integration|e2e]"; exit 2 ;;
esac
exit $code
