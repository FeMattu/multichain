#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# POESIA / wPoA — simulazioni Shadow multi-livello.
#
#   ./run.sh area=regionale
#   ./run.sh area=intercontinentale tbt=5 blocks=300
#   ./run.sh area=nazionale topology=orig            # solo per 'regionale'
#   ./run.sh /percorso/a/shadow/bin area=continentale
#
# Parametri (tutti key=value, tutti opzionali tranne area):
#   area=<regionale|nazionale|continentale|intercontinentale>
#   tbt=<s>        target-block-time            (default 15)
#   blocks=<n>     blocchi della finestra di misura (default 200)
#   setup=<n>      setup-first-blocks    (default: calcolato da tbt ed epochlen)
#   epochlen=<n>   weight-epoch-length          (default 12)
#   seed=<n>       seme di riproducibilita'     (default 20260827)
#   topology=<model|orig>  sorgente del .gml    (default model)
#   vdso=<lat>     --unblocked-vdso-latency     (default 20us)
#   dry=1          prepara tutto ma non lancia Shadow
#
# Il primo argomento, se non contiene '=', e' interpretato come percorso da
# anteporre al PATH (compatibilita' con lo script originale).
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$ROOT/tools"
BINDIR="${BINDIR:-$(cd "$ROOT/../src" && pwd)}"
. "$ROOT/config/params.overrides"

if [ "$#" -ge 1 ] && [[ "$1" != *=* ]]; then
    echo "Prepending $1 to PATH"
    export PATH="$1:${PATH}"
    shift
fi

# I default vengono da config/params.overrides: unica fonte di verita.
AREA=""; TBT="$TARGET_BLOCK_TIME"; BLOCKS=200; SETUP=""
EPOCHLEN="$WEIGHT_EPOCH_LENGTH"; SEED=20260827
TOPOLOGY=model; VDSO=20us; DRY=0
for arg in "$@"; do
    case "$arg" in
        area=*)     AREA="${arg#*=}" ;;
        tbt=*)      TBT="${arg#*=}" ;;
        blocks=*)   BLOCKS="${arg#*=}" ;;
        setup=*)    SETUP="${arg#*=}" ;;
        epochlen=*) EPOCHLEN="${arg#*=}" ;;
        seed=*)     SEED="${arg#*=}" ;;
        topology=*) TOPOLOGY="${arg#*=}" ;;
        vdso=*)     VDSO="${arg#*=}" ;;
        dry=*)      DRY="${arg#*=}" ;;
        *) echo "ERRORE: argomento sconosciuto '$arg'" >&2; exit 2 ;;
    esac
done

case "$AREA" in
    regionale|nazionale|continentale|intercontinentale) ;;
    "") echo "ERRORE: manca area=<livello>. Usa --help nel commento di testa." >&2; exit 2 ;;
    *)  echo "ERRORE: livello sconosciuto '$AREA'" >&2; exit 2 ;;
esac

LEVEL_JSON="$ROOT/config/levels/$AREA.json"
LEVEL_DIR="$ROOT/$AREA"
GML="$LEVEL_DIR/topologia_myledger_$AREA.gml"
RUN="$LEVEL_DIR/run"
CHAIN="poesia$AREA"

# La fase di setup (PoA nativa) deve durare abbastanza da far confermare
# membership + ESG, seppellire l'epoca che li contiene (epoca + 6 blocchi di
# margine di stabilita') e pubblicare i pesi su wpoa-weights. Se la wPoA
# subentra prima, la mappa dei pesi e' vuota e la catena si ferma con
# "cannot score (unsynced or unweighted)".
#
#   setup > (istante di registrazione)/tbt + epoca + margine + slack
#
# T_REGISTER e T_TRAFFIC sono gli stessi valori usati da gen_shadow_yaml.py.
T_TRAFFIC=340
MIN_SETUP=$(( (T_TRAFFIC + TBT - 1) / TBT + EPOCHLEN + 6 + 12 ))
if [ -z "$SETUP" ]; then
    SETUP=$(( MIN_SETUP > 60 ? MIN_SETUP : 60 ))
    echo "[run] setup-first-blocks non specificato: uso $SETUP (minimo calcolato: $MIN_SETUP)"
elif [ "$SETUP" -lt "$MIN_SETUP" ]; then
    echo "ERRORE: setup=$SETUP e' troppo corto per tbt=$TBT ed epochlen=$EPOCHLEN." >&2
    echo "       Con questa combinazione la wPoA subentrerebbe prima che esistano" >&2
    echo "       pesi pubblicati e la catena si fermerebbe. Serve setup >= $MIN_SETUP." >&2
    exit 2
fi

echo "════════════════════════════════════════════════════════════════════"
echo "  POESIA / wPoA — livello: $AREA"
echo "  target-block-time=${TBT}s  setup=${SETUP}  misura=${BLOCKS} blocchi  epoca=${EPOCHLEN}"
echo "════════════════════════════════════════════════════════════════════"

# --- 1. treasury (una tantum) ----------------------------------------------
bash "$TOOLS/gen_treasury.sh"

# --- 2. topologia -----------------------------------------------------------
if [ "$TOPOLOGY" = "orig" ]; then
    ORIG="$LEVEL_DIR/topologia_myledger_$AREA.gml.orig"
    [ -f "$ORIG" ] || { echo "ERRORE: $ORIG non esiste (solo 'regionale' ne ha una)" >&2; exit 2; }
    # Il file originale usa blocchi node/edge compatti e latenze non intere:
    # due sintassi che il parser GML di Shadow 3.3 rifiuta. Lo si normalizza
    # conservandone i valori e cambiandone solo la forma.
    GML="$LEVEL_DIR/topologia_myledger_$AREA.orig.normalizzata.gml"
    python3 "$TOOLS/gen_topology.py" "$LEVEL_JSON" --from-gml "$ORIG" -o "$GML" --table
    echo "[run] topologia: file originale fornito, normalizzato per Shadow"
    echo "[run] ATTENZIONE: le sue latenze di dorsale non seguono il modello"
    echo "[run] comune, il confronto con gli altri livelli non e' valido."
else
    python3 "$TOOLS/gen_topology.py" "$LEVEL_JSON" -o "$GML" --table
fi
python3 "$TOOLS/check_topology.py" "$GML" --matrix | tail -16

# --- 3. directory di run ----------------------------------------------------
rm -rf "$RUN"
mkdir -p "$RUN/data" "$RUN/shared" "$RUN/metrics"
HOSTS="$(python3 -c "import json,sys;print(' '.join(n['host'] for n in json.load(open(sys.argv[1]))['nodes']))" "$LEVEL_JSON")"

# --- 4. params.dat (nativo: e' l'unico passo fuori dalla simulazione) -------
bash "$TOOLS/prepare_params.sh" --run "$RUN" --chain "$CHAIN" \
     --tbt "$TBT" --setup "$SETUP" --epochlen "$EPOCHLEN" --hosts "$HOSTS"

# --- 5. shadow.yaml ---------------------------------------------------------
python3 "$TOOLS/gen_shadow_yaml.py" "$LEVEL_JSON" \
    --gml "$GML" --run "$RUN" --tools "$TOOLS" --bindir "$BINDIR" \
    --chain "$CHAIN" --tbt "$TBT" --setup-blocks "$SETUP" \
    --measure-blocks "$BLOCKS" --epoch-len "$EPOCHLEN" --rng-seed "$SEED" \
    -o "$LEVEL_DIR/shadow.yaml"

if [ "$DRY" = "1" ]; then
    echo "[run] dry=1: preparazione completata, Shadow non lanciato."
    exit 0
fi

# --- 6. simulazione ---------------------------------------------------------
# --unblocked-vdso-latency e' OBBLIGATORIO: con il default (10 ns) il loop
# Strengthen() di random.cpp — che gira su clock_gettime/gettimeofday, entrambe
# vDSO — non termina mai in tempo utile e il nodo non arriva mai ad avviarsi.
echo "[run] avvio Shadow (--unblocked-vdso-latency $VDSO)..."
START=$(date +%s)
set +e
shadow -d "$RUN/shadow.data" --unblocked-vdso-latency "$VDSO" \
       "$LEVEL_DIR/shadow.yaml" > "$RUN/shadow.log" 2>&1
RC=$?
set -e
ELAPSED=$(( $(date +%s) - START ))
echo "[run] Shadow terminato (rc=$RC) in ${ELAPSED}s di wall clock."
[ "$RC" -ne 0 ] && tail -20 "$RUN/shadow.log"

# --- 7. metriche ------------------------------------------------------------
python3 "$TOOLS/collect_metrics.py" --run "$RUN" --chain "$CHAIN" \
        --level "$AREA" --setup-blocks "$SETUP" --epoch-len "$EPOCHLEN" \
        --delta "$WPOA_SORTITION_DELTA" \
        --tbt "$TBT" || true

echo "[run] output: $RUN"
exit "$RC"
