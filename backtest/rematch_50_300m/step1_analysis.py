"""Passo 1 del ri-test 50-300M: la replica dell'originale, e cio' che le mancava.

Legge cio' che `tools/backtest_event_time.py` -- invariato -- ha scritto in `step1/`,
lanciato con il comando del §11 della pre-registrazione.

  1. RIPRODUZIONE. Le righe delle tabelle aggregate nel report appena rigenerato
     devono coincidere carattere per carattere con quelle del report del
     2026-09-01. Se non coincidono lo script esce con codice 1, e il ri-test si
     ferma (§11).
  2. L'INFERENZA CHE MANCAVA. Accanto alla t semplice dell'originale, la t CR1 per
     emittente; accanto al bootstrap semplice, l'IC da t CR1 e il bootstrap per
     emittente (ADR-002, ADR-014). Anche per anno di deposito.
  3. IL PONTE. Gli stessi eventi sul calendario comune di IWM, con l'ingresso
     dell'addendum 2 (ADR-020): prima escludendo i delistati come l'originale,
     poi con l'ultimo prezzo tenuto piatto (ADR-010).

Nessun matching e nessun placebo: sono il passo 2. Nessuna chiamata di rete.

    python backtest/rematch_50_300m/step1_analysis.py
"""
from __future__ import annotations

import bisect
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import backtest_event_time as B  # noqa: E402

HERE = Path(__file__).resolve().parent
STEP1 = HERE / "step1"
ORIGINALE = ROOT / "reports" / "backtest-event-time-2026-09-01-dilution-50-300M.md"

HORIZONS = (21, 63, 126)
COOLDOWN_REPLICA = 126
SEED = 12345
DRAWS = 1000
MAX_STALE = 5          # sessioni, addendum 2
DELIST_GAP = 10        # sessioni prima della fine della cache, ADR-010
MIN_CLUSTER = 10       # sotto, nessuna t con cluster (come nel test svedese: github.com/WilliePim/fi-insider-scanner)

SEZIONI = ("### (a) tutti gli eventi",
           "### (b) un evento per emittente, cooldown 126gg",
           "## Aggregato, excess netto del costo")


# ------------------------------------------------------------ statistica --
def cr1(xs, groups):
    """(media, se, t, G) di una media, sandwich CR1 per gruppo.

    V = G/(G-1) * sum_g (sum_{i in g} (x_i - media))^2 / N^2: il fattore di
    tools/table3_regression.py::ols_cluster con K = 1. None sotto MIN_CLUSTER.
    """
    x = np.asarray(xs, dtype=float)
    n = len(x)
    m = float(x.mean())
    somme = defaultdict(float)
    for g, u in zip(groups, x - m):
        somme[g] += float(u)
    G = len(somme)
    if G < MIN_CLUSTER or n < 2:
        return m, None, None, G
    meat = sum(v * v for v in somme.values())
    se = math.sqrt((G / (G - 1)) * meat / (n * n))
    return m, se, (m / se if se > 0 else None), G


def t_inv_975(df):
    """Quantile 0,975 della t di Student, espansione di Cornish-Fisher.

    Nessuna dipendenza nuova. Per df = 10 da' 2,2280 contro 2,2281 esatto; qui
    df e' il numero di emittenti meno uno, cioe' decine o centinaia.
    """
    z = 1.959963984540054
    v = float(df)
    return (z + (z ** 3 + z) / (4 * v)
            + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * v ** 2)
            + (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * v ** 3))


def boot_emittente(xs, groups, draws=DRAWS, seed=SEED):
    """IC percentile 95% ricampionando EMITTENTI con reinserimento (ADR-014)."""
    per = defaultdict(list)
    for x, g in zip(xs, groups):
        per[g].append(x)
    chiavi = sorted(per)
    somme = np.array([sum(per[k]) for k in chiavi])
    conte = np.array([len(per[k]) for k in chiavi])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(chiavi), size=(draws, len(chiavi)))
    medie = somme[idx].sum(axis=1) / conte[idx].sum(axis=1)
    return float(np.percentile(medie, 2.5)), float(np.percentile(medie, 97.5))


def verifica_cr1():
    """ADR-021: con un cluster per osservazione la t CR1 E' la t iid."""
    rng = np.random.default_rng(7)
    x = list(rng.normal(0.01, 0.3, size=500))
    _, _, t_c, _ = cr1(x, list(range(len(x))))
    t_i = B.tstat(x)
    if abs(t_c - t_i) > 1e-9:
        raise SystemExit("CR1 con cluster singoli {} != t iid {}: funzione rotta".format(t_c, t_i))


def blocco(xs, groups):
    if not xs:
        return None
    d = B.describe(xs)                      # la statistica dell'originale, invariata
    m, se, t_c, G = cr1(xs, groups)
    d.update({"G": G, "t_cr1": t_c, "cr1_lo": None, "cr1_hi": None,
              "cb_lo": None, "cb_hi": None})
    if se is not None:
        q = t_inv_975(G - 1)
        d["cr1_lo"], d["cr1_hi"] = m - q * se, m + q * se
        d["cb_lo"], d["cb_hi"] = boot_emittente(xs, groups)
    return d


# -------------------------------------------------------------- report --
def righe_aggregate(testo):
    """{sezione: [righe | **N giorni** ...]} dalle tabelle aggregate del report."""
    out, cur = {}, None
    for riga in testo.splitlines():
        s = riga.strip()
        if s.startswith("#"):
            cur = s if s in SEZIONI else None
            continue
        if cur and s.startswith("| **") and "giorni**" in s:
            out.setdefault(cur, []).append(s)
    return out


def trova(pattern):
    xs = sorted(p for p in STEP1.glob(pattern) if "-curve-" not in p.name)
    if len(xs) != 1:
        raise SystemExit("atteso un file {} in {}, trovati {}".format(
            pattern, STEP1, [p.name for p in xs]))
    return xs[0]


def carica_csv(p):
    rows = []
    with p.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            e = {"cik": r["cik"], "filed": r["filed"], "ticker": r["ticker"] or None,
                 "flag": r["flag"], "t0": r["t0"]}
            for k in list(r):
                if k.startswith(("exc_", "excnet_", "ret_")):
                    e[k] = float(r[k]) if r[k] != "" else None
            rows.append(e)
    return rows


# ---------------------------------------------------- calendario comune --
IDS, IPX = B.load_series("IWM")
FDS, FPX = B.load_series(B.FX)
LAST = len(IDS) - 1


def sessione(d):
    """Indice dell'ultima sessione IWM <= d."""
    return bisect.bisect_right(IDS, d) - 1


def in_euro(px, d):
    f = B.value_on(FDS, FPX, d)
    return px / f if f else None


def excess_comune(ticker, filed, h):
    """(stato, excess in euro contro IWM, data di ingresso). Addendum 2."""
    ds, px = B.load_series(ticker) if ticker else (None, None)
    if ds is None:
        return "NO_SERIES", None, None
    s0 = bisect.bisect_right(IDS, filed)              # prima sessione dopo il deposito
    if s0 > LAST:
        return "TOO_RECENT", None, None
    j = bisect.bisect_left(ds, IDS[s0])               # prima barra >= s0, mai prima
    if j >= len(ds):
        return "NO_ENTRY_BAR", None, None
    e0 = sessione(ds[j])
    if e0 - s0 > MAX_STALE:
        return "NO_ENTRY_BAR", None, None
    if ds[j] <= filed:                                 # ADR-020: non deve succedere mai
        raise SystemExit("ingresso {} non successivo al deposito {}".format(ds[j], filed))
    if e0 + h > LAST:
        return "TOO_RECENT", None, ds[j]
    uscita = IDS[e0 + h]
    k = bisect.bisect_right(ds, uscita) - 1
    stato = "OK"
    if ds[-1] < uscita and ds[-1] < IDS[LAST - DELIST_GAP]:
        stato, k = "ENDED_IN_WINDOW", len(ds) - 1
    elif (e0 + h) - sessione(ds[k]) > MAX_STALE:
        return "STALE_EXIT", None, ds[j]
    p0, p1 = in_euro(px[j], IDS[e0]), in_euro(px[k], uscita)
    b0, b1 = in_euro(IPX[e0], IDS[e0]), in_euro(IPX[e0 + h], uscita)
    if not (p0 and p1 and b0 and b1):
        return "NO_FX", None, ds[j]
    r, br = p1 / p0 - 1.0, b1 / b0 - 1.0
    if abs(r) > B.ARTEFACT or abs(br) > B.ARTEFACT:
        return "ARTEFACT", None, ds[j]
    return stato, r - br, ds[j]


# ------------------------------------------------------------------ main --
def pct(v):
    return "—" if v is None else "{:+.2%}".format(v)


def num(v):
    return "—" if v is None else "{:.2f}".format(v)


def riga_tab(nome, d):
    if not d:
        return "| {} | — | — | — | — | — | — | — | — | — |".format(nome)
    return "| {} | {:,} | {} | {} | {} | {} | {:,} | {} – {} | {} – {} | {} – {} |".format(
        nome, d["n"], pct(d["mean"]), pct(d["median"]), num(d["t"]), num(d["t_cr1"]),
        d["G"], pct(d["ci_lo"]), pct(d["ci_hi"]), pct(d["cr1_lo"]), pct(d["cr1_hi"]),
        pct(d["cb_lo"]), pct(d["cb_hi"]))


TESTATA = ("| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice "
           "| IC da t CR1 | IC bootstrap per emittente |\n"
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")


def main() -> int:
    verifica_cr1()

    md_nuovo = trova("backtest-event-time-*-dilution-50-300M.md")
    csv_nuovo = trova("backtest-event-time-*-dilution-50-300M.csv")

    # 1. riproduzione, carattere per carattere
    vecchie = righe_aggregate(ORIGINALE.read_text(encoding="utf-8"))
    nuove = righe_aggregate(md_nuovo.read_text(encoding="utf-8"))
    confronto, riprodotto = [], True
    for s in SEZIONI:
        a, b = vecchie.get(s, []), nuove.get(s, [])
        uguale = a == b and len(a) == 3
        riprodotto &= uguale
        confronto.append((s, uguale, a, b))

    rows = carica_csv(csv_nuovo)
    vb = B.cooldown_filter(rows, COOLDOWN_REPLICA)
    numeri = {"riprodotto": riprodotto, "eventi_fascia": len(rows), "eventi_b": len(vb),
              "emittenti_b": len({r["cik"] for r in vb})}

    # 2. inferenza clusterizzata sugli stessi numeri
    def serie(pop, chiave):
        xs = [(r[chiave], r["cik"]) for r in pop if r.get(chiave) is not None]
        return [x for x, _ in xs], [g for _, g in xs]

    tab = {}
    for nome, pop, pref in (("(b) lordo", vb, "exc_"), ("(a) lordo", rows, "exc_"),
                            ("(b) netto 100bp", vb, "excnet_")):
        for h in HORIZONS:
            xs, gs = serie(pop, "{}{}".format(pref, h))
            tab[(nome, h)] = blocco(xs, gs)

    per_anno = {}
    for y in sorted({r["filed"][:4] for r in vb}):
        xs, gs = serie([r for r in vb if r["filed"][:4] == y], "exc_126")
        per_anno[y] = blocco(xs, gs)

    # 3. il ponte sul calendario comune
    stati = Counter()
    esiti = []
    for r in vb:
        st, x, entrata = excess_comune(r["ticker"], r["filed"], 126)
        stati[st] += 1
        esiti.append((r, st, x))
    come_orig = [(x, r["cik"]) for r, st, x in esiti if st == "OK"]
    piatto = [(x, r["cik"]) for r, st, x in esiti if st in ("OK", "ENDED_IN_WINDOW")]
    ponte = {
        "originale": tab[("(b) lordo", 126)],
        "comune_come_originale": blocco([x for x, _ in come_orig], [g for _, g in come_orig]),
        "comune_ultimo_prezzo": blocco([x for x, _ in piatto], [g for _, g in piatto]),
    }
    ponte_anno = {}
    for y in sorted(per_anno):
        sel = [(x, r["cik"]) for r, st, x in esiti
               if st in ("OK", "ENDED_IN_WINDOW") and r["filed"][:4] == y]
        ponte_anno[y] = blocco([x for x, _ in sel], [g for _, g in sel])

    # ----------------------------------------------------------- scrittura
    L = ["# Passo 1 — replica del test originale", "",
         "Generato da `python backtest/rematch_50_300m/step1_analysis.py`, sull'output di "
         "`tools/backtest_event_time.py` invariato (comando al §11 della pre-registrazione). "
         "Pre-registrazione `130b0fe`, addendum 1 `e48cfb9`, addendum 2 per il ponte.", "",
         "Nessuna chiamata a modelli linguistici: token e costo **0**.", "",
         "## 1. Riproduzione", "",
         "**{}** — le righe delle tabelle aggregate del report rigenerato, confrontate "
         "carattere per carattere con [il report del 2026-09-01]"
         "(../../../reports/backtest-event-time-2026-09-01-dilution-50-300M.md).".format(
             "RIPRODOTTO" if riprodotto else "NON RIPRODOTTO"), ""]
    for s, uguale, a, b in confronto:
        L += ["### {} — {}".format(s.lstrip("# "), "identiche" if uguale else "DIVERSE"), ""]
        if uguale:
            L += ["```"] + a + ["```", ""]
        else:
            L += ["2026-09-01:", "```"] + (a or ["(assenti)"]) + ["```", "oggi:", "```"] \
                 + (b or ["(assenti)"]) + ["```", ""]

    if not riprodotto:
        L += ["**Il ri-test si ferma qui** (§11): prima si capisce perche' i numeri non "
              "coincidono, poi si va avanti.", ""]
        (STEP1 / "report.md").write_text("\n".join(L), encoding="utf-8")
        (STEP1 / "numbers.json").write_text(json.dumps(numeri, indent=1), encoding="utf-8")
        print("NON RIPRODOTTO -- scritto {}".format(STEP1 / "report.md"))
        return 1

    L += ["## 2. La stessa replica, con l'inferenza clusterizzata", "",
          "Popolazione: {:,} eventi in fascia; variante (b) {:,} eventi su {:,} emittenti. "
          "La t semplice e il bootstrap semplice sono quelli dell'originale; t CR1, IC da t CR1 "
          "e bootstrap per emittente sono aggiunti (ADR-002, ADR-014).".format(
              numeri["eventi_fascia"], numeri["eventi_b"], numeri["emittenti_b"]), ""]
    for nome in ("(b) lordo", "(a) lordo", "(b) netto 100bp"):
        L += ["### {}".format(nome), "", TESTATA]
        for h in HORIZONS:
            L.append(riga_tab("**{} sessioni**".format(h), tab[(nome, h)]))
        L.append("")

    L += ["## 3. Per anno di deposito — variante (b), 126 sessioni, lordo", "", TESTATA]
    for y, d in per_anno.items():
        L.append(riga_tab("**{}**".format(y), d))
    L += ["", "Sotto {} emittenti la t con cluster non si calcola.".format(MIN_CLUSTER), ""]

    L += ["## 4. Il ponte sul calendario comune", "",
          "Gli stessi {:,} eventi della variante (b), 126 sessioni, sulle sessioni IWM con "
          "l'ingresso dell'addendum 2: prima barra del titolo dopo il deposito entro 5 "
          "sessioni, mai un prezzo anteriore.".format(len(vb)), "",
          "| stato | eventi |", "|---|---:|"]
    for k, v in sorted(stati.items(), key=lambda kv: -kv[1]):
        L.append("| `{}` | {:,} |".format(k, v))
    L += ["", TESTATA,
          riga_tab("originale (barre del titolo)", ponte["originale"]),
          riga_tab("comune, delistati esclusi", ponte["comune_come_originale"]),
          riga_tab("comune, ultimo prezzo piatto", ponte["comune_ultimo_prezzo"]), "",
          "### Ponte per anno — calendario comune, ultimo prezzo piatto", "", TESTATA]
    for y, d in ponte_anno.items():
        L.append(riga_tab("**{}**".format(y), d))

    #  Verifica del ponte. L'excess sul calendario comune e' ricalcolato dalle
    #  serie prezzi, non riletto dal CSV: se le righe coincidono con l'originale
    #  deve essere perche' i calendari coincidono, e qui lo si misura invece di
    #  assumerlo.
    diff_max, date_diverse, confrontati = 0.0, 0, 0
    finiti = []
    for r, st, x in esiti:
        if st == "ENDED_IN_WINDOW":
            ds, _ = B.load_series(r["ticker"])
            finiti.append((r["ticker"], r["filed"], ds[-1], x))
        if st != "OK" or r.get("exc_126") is None:
            continue
        confrontati += 1
        diff_max = max(diff_max, abs(x - r["exc_126"]))
        ds, _ = B.load_series(r["ticker"])
        i0 = bisect.bisect_right(ds, r["filed"])
        e0 = sessione(ds[bisect.bisect_left(ds, IDS[bisect.bisect_right(IDS, r["filed"])])])
        if i0 + 126 < len(ds) and ds[i0 + 126] != IDS[e0 + 126]:
            date_diverse += 1
    L += ["", "### Perche' le prime due righe coincidono", "",
          "L'excess sul calendario comune e' ricalcolato da capo dalle serie prezzi, non riletto "
          "dal CSV dell'originale. Su {:,} eventi confrontati la differenza massima fra i due "
          "excess e' **{:.2%}**, e la data di uscita cambia per **{:,}** eventi: le serie hanno "
          "una barra per ogni sessione di borsa, quindi contare barre del titolo e contare "
          "sessioni IWM porta quasi sempre alla stessa data.".format(
              confrontati, diff_max, date_diverse), "",
          "Gli eventi `ENDED_IN_WINDOW` entrano solo nella terza riga. Una serie che finisce "
          "prima dell'uscita puo' essere un delisting o un cambio di ticker: la regola "
          "dell'ADR-010 non li distingue.", "",
          #  Copia pubblica: solo il conteggio, niente ticker, date ed excess per titolo.
          "Eventi `ENDED_IN_WINDOW` in questo confronto: **{}**.".format(len(finiti))]
    numeri["verifica_ponte"] = {"confrontati": confrontati, "diff_max": diff_max,
                                "date_uscita_diverse": date_diverse,
                                "ended_in_window": len(finiti)}
    L += ["", "## 5. Cosa non c'e' in questo passo", "",
          "Nessun matching, nessun placebo, nessuna scomposizione: sono il passo 2 e il passo 3, "
          "sulla popolazione primaria dell'addendum 1 (un evento per emittente ogni 365 giorni). "
          "La popolazione di questa pagina e' la replica, variante (b) a 126 giorni, e non entra "
          "nel verdetto.", ""]

    for k, d in tab.items():
        numeri["{} {}".format(*k)] = d
    numeri["per_anno"] = per_anno
    numeri["ponte"] = ponte
    numeri["ponte_per_anno"] = ponte_anno
    numeri["stati_ponte"] = dict(stati)
    (STEP1 / "report.md").write_text("\n".join(L), encoding="utf-8")
    (STEP1 / "numbers.json").write_text(json.dumps(numeri, indent=1, default=str),
                                        encoding="utf-8")
    print("RIPRODOTTO -- scritto {}".format(STEP1 / "report.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
