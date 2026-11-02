#!/usr/bin/env bash
# Testes visuais do InventarIA: cada script sobe o app com a casa de teste fictícia (e, quando precisa,
# um Home Assistant e uma loja de mentira), abre as telas no Chromium (Playwright) como celular, tablet
# ou computador, clica, confere o que aparece e grava capturas de tela.
#
#   tests/e2e/run.sh                     todos
#   tests/e2e/run.sh e2e_itens e2e_mais  só esses
#   E2E_JOBS=4 tests/e2e/run.sh          quatro de cada vez (cada um usa portas livres próprias)
#
# Precisa de python3 e playwright (pip install playwright; playwright install chromium).
# Capturas em $E2E_TMP/shots, saídas em $E2E_TMP/logs.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export E2E_TMP="${E2E_TMP:-$(mktemp -d)}"
export TZ="${TZ:-America/Sao_Paulo}"
JOBS="${E2E_JOBS:-1}"
mkdir -p "$E2E_TMP/shots" "$E2E_TMP/logs"

if [ $# -gt 0 ]; then names=("${@%.py}"); else names=($(cd "$HERE" && ls e2e_*.py | grep -v '_lib.py$' | sed 's/\.py$//' | sort)); fi

one() {
  local t="$1" f="$HERE/$1.py" log="$E2E_TMP/logs/$1.txt"
  [ -f "$f" ] || { echo "?? $t (não existe)" > "$log.res"; return; }
  (cd "$HERE" && timeout 900 python3 -u "$f") > "$log" 2>&1
  local code=$? last
  last=$(tail -1 "$log")
  if [ $code -ne 0 ] || grep -q "^FAIL" "$log"; then
    { echo "XX $t: $last"; grep -h "^FAIL" "$log" | head -5 | sed 's/^/     /'; } > "$log.res"
  else
    echo "ok $t: $last" > "$log.res"
  fi
}
export -f one
export HERE

if [ "$JOBS" -gt 1 ]; then
  printf '%s\n' "${names[@]}" | xargs -P "$JOBS" -I{} bash -c 'one "$@"' _ {}
else
  for t in "${names[@]}"; do one "$t"; cat "$E2E_TMP/logs/$t.txt.res"; done
fi

pass=0; fail=0; bad=()
for t in "${names[@]}"; do
  res="$E2E_TMP/logs/$t.txt.res"
  [ "$JOBS" -gt 1 ] && cat "$res"
  if head -1 "$res" | grep -q "^ok "; then pass=$((pass+1)); else fail=$((fail+1)); bad+=("$t"); fi
done
echo
echo "$pass ok, $fail com falha · capturas e saídas em $E2E_TMP"
[ $fail -eq 0 ] || { echo "Falharam: ${bad[*]}"; exit 1; }
