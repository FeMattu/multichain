#!/usr/bin/env python3
"""
Validazione Monte Carlo dell'algoritmo di elezione wPoA (Sez. 7.3 / 7.7.1).

Reimplementa in Python puro la trasformazione di score Efraimidis-Spirakis usata
dal selettore (`src/wpoa/wpoa_selector.h`) e la esegue N volte su scenari
dichiarati qui dentro, confrontando le frequenze osservate con quelle attese dal
Teor. 5.3 (`Pr[i eletto] = w_i / W_tot`) con un chi-quadro.

    python3 tools/valida_sortition_montecarlo.py
    python3 tools/valida_sortition_montecarlo.py --estrazioni 100000 --seed 7
    python3 tools/valida_sortition_montecarlo.py --dump-function sqrt

COSA VERIFICA E COSA NO. Questo script **non legge le run Shadow** (salvo un
solo scenario, che ne prende in prestito i rapporti di peso per confronto) e non
esegue il binario C++: verifica la FORMULA, non l'implementazione compilata.
E' il complemento necessario al chi-quadro sulle run vere, che ha campione
troppo piccolo per dire alcunche' — qui il campione lo si sceglie. Verificare il
binario resta lavoro futuro: richiederebbe esporre `ComputeScore` a un harness
dedicato o pilotare `multichaind` da un test funzionale.

Output: `analisi/fogli-di-analisi/validazione_sortition.csv`.

Sola libreria standard.
"""

import argparse
import csv
import glob
import math
import random
import sys
from collections import Counter
from pathlib import Path

# Valori critici della chi-quadro al 5%, per gradi di liberta'.
CHI2_CRIT_05 = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
                6: 12.592, 7: 14.067, 8: 15.507, 9: 16.919, 10: 18.307}

TWO64 = 18446744073709551616.0      # 2^64, esatto in double come nel sorgente


# --------------------------------------------------------------------------
# la trasformazione di score, riga per riga come in wpoa_selector.h
# --------------------------------------------------------------------------

def apply_dumping(weight, dump_function):
    """g(.) di Def. 5.9 — WPoASelector::ApplyDumping."""
    if dump_function == "sqrt":
        return math.sqrt(float(weight))
    if dump_function == "log":
        return math.log(1.0 + float(weight))
    return float(weight)


def score_from_entropy64(d, weight, dump_function="none"):
    """WPoASelector::ScoreFromEntropy64.

    u = (d+1)/2^64 in (0,1];  E = -ln(u) ~ Exp(1);  score = E / g(w).

    Un peso nullo restituisce +inf **prima** di qualunque divisione, esattamente
    come nel sorgente: e' cosi' che il Cor. 5.4 e' garantito per costruzione e
    non da un ramo di esclusione esplicito.
    """
    if weight == 0:
        return float("inf")
    u = (float(d) + 1.0) / TWO64
    return -math.log(u) / apply_dumping(weight, dump_function)


def select_proposer(rng, weights, dump_function="none"):
    """argmin dello score, con pareggio risolto sull'indirizzo lessicograficamente
    minore — l'ordinamento totale che rende il risultato indipendente dall'ordine
    di iterazione della mappa.

    L'entropia a 64 bit viene qui da `random.getrandbits(64)` invece che da un
    VRF: la Prop. 5.11 richiede al VRF proprio di essere indistinguibile da
    un'uniforme, quindi sostituirlo con un'uniforme e' esattamente il test
    dell'algoritmo a monte della sorgente di casualita'.
    """
    best_addr, best_score = None, None
    for addr in sorted(weights):
        s = score_from_entropy64(rng.getrandbits(64), weights[addr], dump_function)
        if best_score is None or s < best_score or (s == best_score and addr < best_addr):
            best_addr, best_score = addr, s
    return best_addr


# --------------------------------------------------------------------------
# scenari
# --------------------------------------------------------------------------

def scenari_statici():
    """Gli scenari dichiarati, indipendenti da qualunque run."""
    return [
        ("pesi uniformi (3 candidati)",
         {"n1": 100, "n2": 100, "n3": 100},
         "il caso degenere: la wPoA deve ridursi a un'estrazione equiprobabile"),
        ("pesi fortemente sbilanciati (95/4/1)",
         {"n1": 95, "n2": 4, "n3": 1},
         "il caso che il chi-quadro sulle run non riesce a testare: la classe "
         "piu' piccola ha attesa sufficiente solo con molte estrazioni"),
        ("un candidato a peso nullo (Cor. 5.4)",
         {"n1": 60, "n2": 40, "n_zero": 0},
         "verifica diretta del Cor. 5.4: il candidato a peso nullo deve avere "
         "ZERO selezioni esatte, non poche"),
        ("due candidati a peso uguale piu' uno nullo",
         {"n1": 50, "n2": 50, "n_zero": 0},
         "il Cor. 5.4 regge anche quando i restanti sono indistinguibili fra loro"),
    ]


def scenario_da_run(pattern, min_attesa=5.0):
    """I rapporti di peso di un'epoca REALE della campagna Shadow.

    Serve a rispondere a una domanda precisa: se la stessa configurazione di pesi
    che nella run Shadow non era testabile viene estratta N volte invece che una
    dozzina, l'algoritmo torna? Se si', lo scarto osservato sulla run e' campione,
    non protocollo.

    Sceglie l'epoca con il criterio piu' forte disponibile, e **dichiara quale**:

    1. `campione_sufficiente_epoca = 1` — attesa >= 5 blocchi per classe nella
       singola epoca. Con `weight-epoch-length = 12` e tre miner a quote
       sbilanciate non si verifica quasi mai;
    2. `campione_sufficiente_finestra = 1` — attesa >= 5 sulla finestra scorrevole
       di epoche, il compromesso adottato dalla pipeline;
    3. nessuno dei due — l'epoca viene comunque presa, ma la nota lo dice.

    In tutti e tre i casi il campione del Monte Carlo e' quello scelto da
    `--estrazioni`: la sufficienza qui riguarda solo la rappresentativita' dei
    RAPPORTI DI PESO presi in prestito, non la potenza del test.
    """
    candidati = []
    for path in sorted(glob.glob(pattern)):
        per_epoca, criterio_epoca = {}, {}
        for row in csv.DictReader(open(path, encoding="utf-8", newline="")):
            peso = row.get("peso_efficace_epoca") or row.get("peso_pubblicato_epoca")
            try:
                w = int(float(peso))
            except (TypeError, ValueError):
                continue
            e = row["epoca"]
            per_epoca.setdefault(e, {})[row["host"]] = w
            rango = (2 if row.get("campione_sufficiente_epoca") == "1"
                     else 1 if row.get("campione_sufficiente_finestra") == "1" else 0)
            criterio_epoca[e] = max(criterio_epoca.get(e, 0), rango)
        for e, pesi in per_epoca.items():
            if len(pesi) >= 2 and sum(pesi.values()) > 0:
                candidati.append((criterio_epoca.get(e, 0), int(e), path, pesi))
    if not candidati:
        return None
    # il criterio piu' forte; a parita', l'epoca piu' avanzata (pesi piu' divergenti)
    rango, epoca, path, pesi = max(candidati, key=lambda t: (t[0], t[1]))
    criterio = {2: "attesa >= 5 nella singola epoca",
                1: "attesa >= 5 solo sulla finestra scorrevole di epoche; nella "
                   "singola epoca il campione della run NON basta",
                0: "campione insufficiente sia per epoca sia a finestra: i rapporti "
                   "di peso sono comunque quelli misurati"}[rango]
    run_id = "/".join(Path(path).parts[-3:-1])
    return ("pesi osservati in una run reale (%s, epoca %s)" % (run_id, epoca), pesi,
            "gli stessi rapporti di peso misurati sulla catena, estratti pero' N "
            "volte invece che una dozzina. Criterio di scelta dell'epoca: %s"
            % criterio)


# --------------------------------------------------------------------------
# esecuzione
# --------------------------------------------------------------------------

def esegui(nome, pesi, nota, n, seed, dump_function):
    rng = random.Random(seed)
    vinte = Counter()
    for _ in range(n):
        vinte[select_proposer(rng, pesi, dump_function)] += 1

    # L'attesa e' sul peso EFFICACE g(w), non su w: e' g(w) a entrare nello
    # score, quindi con dump-function non lineare le due attese divergono e
    # confrontare con w sarebbe il modo piu' rapido di "trovare" una violazione
    # che non c'e'.
    eff = {a: apply_dumping(w, dump_function) for a, w in pesi.items()}
    tot = sum(eff.values())
    positivi = sorted(a for a in pesi if eff[a] > 0)
    nulli = sorted(a for a in pesi if eff[a] <= 0)

    chi = df = crit = comp = attesa_min = ""
    if tot > 0 and len(positivi) >= 2:
        attese = {a: n * eff[a] / tot for a in positivi}
        chi = sum((vinte[a] - attese[a]) ** 2 / attese[a] for a in positivi)
        df = len(positivi) - 1
        crit = CHI2_CRIT_05.get(df, "")
        comp = int(chi <= crit) if crit else ""
        attesa_min = min(attese.values())

    vinte_nulli = sum(vinte[a] for a in nulli)
    return {
        "scenario": nome,
        "pesi": " ".join("%s:%s" % (a, pesi[a]) for a in sorted(pesi)),
        "dump_function": dump_function,
        "n_estrazioni": n,
        "seed": seed,
        "chi2": round(chi, 4) if chi != "" else "",
        "df": df,
        "critico_5pct": crit,
        "compatibile": comp,
        "attesa_minima": round(attesa_min, 2) if attesa_min != "" else "",
        "campione_sufficiente": int(attesa_min >= 5) if attesa_min != "" else "",
        "candidati_peso_nullo": len(nulli),
        "selezioni_candidati_nulli": vinte_nulli,
        "cor_5_4_rispettato": (int(vinte_nulli == 0) if nulli else ""),
        "quote_osservate": " ".join("%s:%.4f" % (a, vinte[a] / n) for a in sorted(pesi)),
        "quote_attese": " ".join(
            "%s:%.4f" % (a, (eff[a] / tot) if tot > 0 else 0.0) for a in sorted(pesi)),
        "nota": nota,
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estrazioni", type=int, default=10000,
                    help="numero di elezioni simulate per scenario (default 10000)")
    ap.add_argument("--seed", type=int, default=20260829,
                    help="seed del generatore: fissato, cosi' il risultato e' "
                         "riproducibile byte per byte")
    ap.add_argument("--dump-function", default="none", choices=("none", "sqrt", "log"),
                    dest="dump_function",
                    help="g(.) applicata al peso prima dell'estrazione (Def. 5.9)")
    ap.add_argument("--out", default="analisi/fogli-di-analisi/validazione_sortition.csv",
                    help="file CSV di output")
    ap.add_argument("--peso-riconciliazione",
                    default="analisi/esperimenti/*/*/peso_riconciliazione.csv",
                    dest="peso_path",
                    help="glob delle tabelle da cui prendere i rapporti di peso di "
                         "un'epoca reale; se non ce n'e' nessuna, quello scenario "
                         "viene saltato e dichiarato, non sostituito")
    args = ap.parse_args()

    scenari = list(scenari_statici())
    reale = scenario_da_run(args.peso_path)
    if reale:
        scenari.append(reale)
    else:
        print("ATTENZIONE: nessuna tabella peso_riconciliazione.csv leggibile in %s: "
              "lo scenario 'pesi osservati in una run reale' e' assente "
              "dall'output, non sostituito da un ripiego." % args.peso_path,
              file=sys.stderr)

    righe = [esegui(nome, pesi, nota, args.estrazioni, args.seed + i, args.dump_function)
             for i, (nome, pesi, nota) in enumerate(scenari)]

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(righe[0]))
        writer.writeheader()
        writer.writerows(righe)

    print("scritto %s (%d scenari, %d estrazioni ciascuno, g=%s)"
          % (out, len(righe), args.estrazioni, args.dump_function))
    print()
    print("%-52s %10s %5s %10s %14s" % ("scenario", "chi2", "df", "critico", "verdetto"))
    for r in righe:
        if r["chi2"] == "":
            verdetto = "non testabile"
        else:
            verdetto = "compatibile" if r["compatibile"] else "NON compatibile"
        print("%-52s %10s %5s %10s %14s"
              % (r["scenario"][:52], r["chi2"], r["df"], r["critico_5pct"], verdetto))
        if r["candidati_peso_nullo"]:
            esito = "OK" if r["cor_5_4_rispettato"] else "VIOLATO"
            print("      Cor. 5.4: %d candidati a peso nullo, %d selezioni -> %s"
                  % (r["candidati_peso_nullo"], r["selezioni_candidati_nulli"], esito))

    violazioni = [r for r in righe if r["cor_5_4_rispettato"] == 0]
    incompatibili = [r for r in righe if r["compatibile"] == 0]
    if violazioni:
        print("\nCor. 5.4 VIOLATO in %d scenari: un candidato a peso nullo e' stato "
              "eletto." % len(violazioni))
        return 1
    if incompatibili:
        print("\n%d scenari NON compatibili con il Teor. 5.3 al 5%%: %s"
              % (len(incompatibili), ", ".join(r["scenario"] for r in incompatibili)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
