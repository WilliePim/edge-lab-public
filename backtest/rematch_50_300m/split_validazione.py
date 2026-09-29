"""Addendum 4: rilevatore degli split dalle riesposizioni XBRL, e la sua validazione.

    python backtest/rematch_50_300m/split_validazione.py rileva       # zero rete
    python backtest/rematch_50_300m/split_validazione.py campione     # EDGAR, tetto dell'addendum 3
    python backtest/rematch_50_300m/split_validazione.py concordanza

Nessun rendimento. L'ordine e' la regola (addendum 4 §8): le etichette vere si scrivono in
step2c_prep/validazione_split/_verita_split.json leggendo gli estratti, SENZA aprire
_rilevatore.json, e si committano prima di lanciare `concordanza`.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import survival as SV  # noqa: E402

OUT = HERE / "step2c_prep"
VAL = OUT / "validazione_split"
CACHE = ROOT / ".edgar_cache"
CONCETTI = ("WeightedAverageNumberOfSharesOutstandingBasic", "CommonStockSharesOutstanding")
PULITI = (1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 35, 40, 50)
SEED = 20260915
N_CAMPIONE = 40
SOGLIA = 0.90
FTS = ("https://efts.sec.gov/LATEST/search-index?q=%22stock%20split%22&ciks={cik:010d}"
       "&forms=8-K,10-Q,10-K&dateRange=custom&startdt={a}&enddt={b}")
TIPI = ("SPLIT", "NESSUNO_SPLIT", "NON_DETERMINABILE")


def piu(d, n):
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()


def pulito(r):
    x = r if r >= 1 else 1 / r
    return any(abs(x / p - 1) <= 0.03 for p in PULITI)


def companyfacts(c):
    u = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json".format(int(c))
    p = CACHE / (hashlib.sha256(u.encode()).hexdigest()[:24] + ".cache")
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else None
    except ValueError:
        return None


def candidati(cf):
    """Addendum 4 §4: rapporti fra depositi consecutivi dello stesso periodo, fusi."""
    cand = []
    gaap = ((cf or {}).get("facts") or {}).get("us-gaap") or {}
    for nome in CONCETTI:
        gruppi = collections.defaultdict(dict)
        for x in ((gaap.get(nome) or {}).get("units") or {}).get("shares") or []:
            if x.get("filed") and x.get("val"):
                gruppi[(x.get("start"), x.get("end"))].setdefault(x["filed"], float(x["val"]))
        for vals in gruppi.values():
            seq = sorted(vals.items())
            for (f0, v0), (f1, v1) in zip(seq, seq[1:]):
                if v0 > 0 and f0 != f1:
                    r = v1 / v0
                    if (r <= 0.55 or r >= 1.8) and 1 / 50 <= r <= 50:
                        cand.append([f0, f1, r])
    fusi = []
    for lo, hi, r in sorted(cand, key=lambda z: (z[2], z[0])):
        for g in fusi:
            if abs(math.log(r) - math.log(g[2])) < math.log(1.1) and lo < g[1] and g[0] < hi:
                g[0], g[1] = max(g[0], lo), min(g[1], hi)
                g[3] += 1
                break
        else:
            fusi.append([lo, hi, r, 1])
    return sorted(g for g in fusi if g[0] < g[1] and not (g[2] > 1 and not pulito(g[2])))


# ------------------------------------------------------------------ rileva --
def rileva(_a) -> int:
    import step2_analysis as S

    OUT.mkdir(parents=True, exist_ok=True)
    righe_p = []
    with (HERE / "step2" / "eventi.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["banda"] == "50-300M":
                righe_p.append(r)
    ciks = {r["cik"] for r in righe_p} | {r[k] for r in righe_p for k in ("peer_size", "peer_mom") if r[k]}

    tick, quiet_righe, _ = S.leggi_corpus(set())
    pool = S.Pool(tick, quiet_righe)
    serie_path = SV.indice_serie()
    tx = collections.defaultdict(list)
    for (c, _f), vs in SV.righe_insider().items():
        for td, _sh, px in vs:
            if len(td) == 10 and px > 0:
                tx[c].append((td, px))
    for c in tx:
        tx[c].sort()
    serie = {}

    def f_at(c, td, px):
        s = S.sessione(td)
        if c in pool.idx:
            close = pool.prezzo(pool.idx[c], s)
        else:
            if c not in serie:
                path = next((serie_path[SV.chiave(t)] for t, _d in
                             sorted((tick.get(c) or {}).items(), key=lambda kv: kv[1], reverse=True)
                             if SV.chiave(t) in serie_path), None)
                serie[c] = S.carica(path) if path else None
            close = serie[c].a_sessione(s) if serie[c] else None
        return px / close if close else None

    accettati, conte = {}, collections.Counter()
    for c in sorted(ciks):
        gs = candidati(companyfacts(c))
        ts = tx.get(c) or []
        buoni = []
        for lo, hi, r, n in gs:
            cat = ("pulito" if pulito(r) else "non_pulito") + ("_reverse" if r < 1 else "_avanti")
            prima = [x for x in ts if piu(lo, -365) <= x[0] <= lo]
            dopo = [x for x in ts if hi < x[0] <= piu(hi, 365)]
            fb = f_at(c, *prima[-1]) if prima else None
            fa = f_at(c, *dopo[0]) if dopo else None
            if fb and fa:
                atteso = 1.0
                for lo2, hi2, r2, _n2 in gs:
                    if prima[-1][0] <= lo2 and hi2 < dopo[0][0]:
                        atteso *= r2
                rap = fb / fa
                ver = ("confermato" if abs(math.log(rap) - math.log(atteso)) < math.log(1.5)
                       else "piatto" if abs(math.log(rap)) < math.log(1.25) else "discorde")
            else:
                ver = "non_verificabile"
            ok = ver == "confermato" or (ver == "non_verificabile" and cat.startswith("pulito"))
            conte[(cat, ver, ok)] += 1
            if ok:
                buoni.append({"lo": lo, "hi": hi, "rapporto": r, "categoria": cat, "verifica": ver, "supporto": n})
        accettati[c] = buoni

    toccati = set()
    for r in righe_p:
        for c in (r["cik"], r["peer_size"], r["peer_mom"]):
            for g in accettati.get(c) or []:
                if r["D"] <= g["lo"] or g["lo"] < r["D"] < g["hi"]:
                    toccati.add("{}_{}_{}".format(c, g["lo"], g["hi"]))
    (OUT / "split.json").write_text(json.dumps({"accettati": accettati, "toccati_cella_P": sorted(toccati)},
                                               indent=1, sort_keys=True), encoding="utf-8")
    print("CIK esaminati: {:,}".format(len(ciks)))
    for (cat, ver, ok), v in sorted(conte.items()):
        print("  {:20s} {:18s} {:10s} {:,}".format(cat, ver, "accettato" if ok else "scartato", v))
    print("split accettati: {:,}; che toccano una F(D) della cella P: {:,}".format(
        sum(len(v) for v in accettati.values()), len(toccati)))
    return 0


# ---------------------------------------------------------------- campione --
def campione(_a) -> int:
    VAL.mkdir(parents=True, exist_ok=True)
    dati = json.loads((OUT / "split.json").read_text(encoding="utf-8"))
    per_id = {}
    for c, gs in dati["accettati"].items():
        for g in gs:
            per_id["{}_{}_{}".format(c, g["lo"], g["hi"])] = (c, g)
    scelti = sorted(random.Random(SEED).sample(dati["toccati_cella_P"], N_CAMPIONE))
    budget = SV.Budget()
    rilevatore, indice = {}, []
    for sid in scelti:
        c, g = per_id[sid]
        rilevatore[sid] = {"rapporto": g["rapporto"], "categoria": g["categoria"], "verifica": g["verifica"]}
        url = FTS.format(cik=int(c), a=piu(g["lo"], -30), b=piu(g["hi"], 30))
        raw = budget.get(url)
        hits = []
        try:
            hits = ((json.loads(raw) if raw else {}).get("hits") or {}).get("hits") or []
        except ValueError:
            pass
        L = ["# {} — CIK {}".format(sid, c), "",
             "Finestra dello split rilevato: dopo il deposito del {} ed entro quello del {}. Ricerca full-text "
             "`stock split`, forme 8-K/10-Q/10-K, {} → {}.".format(g["lo"], g["hi"], piu(g["lo"], -30), piu(g["hi"], 30)), "",
             "Risultati (primi 10): {}".format(len(hits)), ""]
        for h in hits[:10]:
            s = h.get("_source") or {}
            L.append("- {} `{}` {} — {}".format(s.get("file_date"), s.get("root_form") or s.get("form"),
                                               h.get("_id"), "; ".join(s.get("display_names") or [])[:80]))
        doc = None
        if hits:
            acc, _, fname = (hits[0].get("_id") or "").partition(":")
            doc = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(int(c), acc.replace("-", ""), fname)
            t = SV.testo(budget.get(doc))
            L += ["", "## Primo documento: `{}` — {}".format(acc, doc), ""]
            pezzi = [t[max(0, m.start() - 500):m.end() + 500] for m in re.finditer(r"stock\s+split", t, re.I)][:4]
            L += pezzi or ["_nessuna occorrenza di «stock split» nel testo scaricato_"]
        (VAL / "{}.md".format(sid)).write_text("\n\n".join(L) if False else "\n".join(L), encoding="utf-8")
        indice.append({"id": sid, "cik": c, "documento": doc, "risultati": len(hits)})
    (VAL / "_rilevatore.json").write_text(json.dumps(rilevatore, indent=1, sort_keys=True), encoding="utf-8")
    (VAL / "_campione.json").write_text(json.dumps({"seed": SEED, "toccati": len(dati["toccati_cella_P"]),
                                                    "estratti": indice}, indent=1), encoding="utf-8")
    print("campione di {} split; chiamate EDGAR usate in totale (tetto addendum 3): {}".format(len(scelti), budget.usate))
    return 0


# ------------------------------------------------------------- concordanza --
def concordanza(_a) -> int:
    verita = json.loads((VAL / "_verita_split.json").read_text(encoding="utf-8"))
    ril = json.loads((VAL / "_rilevatore.json").read_text(encoding="utf-8"))
    righe, conc = [], 0
    for sid in sorted(ril):
        v = verita.get(sid) or {}
        tipo = v.get("tipo", "MANCANTE")
        if tipo not in TIPI:
            raise SystemExit("tipo non ammesso per {}: {}".format(sid, tipo))
        ok = tipo == "SPLIT" and v.get("rapporto") and abs(math.log(v["rapporto"]) - math.log(ril[sid]["rapporto"])) < math.log(1.1)
        conc += bool(ok)
        righe.append((sid, ril[sid]["rapporto"], tipo, v.get("rapporto"), ok, v.get("citazione", "")))
    n = len(ril)
    p = conc / n if n else 0.0
    valido = p >= SOGLIA
    L = ["# Validazione del rilevatore di split (addendum 4 §5)", "",
         "{} split, seme {}. Concordanti: **{} su {} = {:.1%}**, soglia {:.0%}: **{}**.".format(
             n, SEED, conc, n, p, SOGLIA, "rilevatore VALIDO" if valido else "rilevatore NON VALIDO — nessuna correzione"), "",
         "| split | rapporto rilevato | lettura | rapporto letto | concorda | citazione |", "|---|---:|---|---:|---|---|"]
    for sid, rr, tipo, rv, ok, cit in righe:
        L.append("| {} | {:.4g} | {} | {} | {} | {} |".format(sid, rr, tipo, "—" if rv is None else "{:.4g}".format(rv),
                                                           "sì" if ok else "**no**", cit.replace("|", "/")[:150]))
    (OUT / "validazione_split.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / "validazione_split_esito.json").write_text(json.dumps(
        {"n": n, "concordanti": conc, "concordanza": p, "soglia": SOGLIA, "valido": valido}, indent=1), encoding="utf-8")
    print("concordanza {:.1%} -> {}".format(p, "VALIDO" if valido else "NON VALIDO"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nome, fn in (("rileva", rileva), ("campione", campione), ("concordanza", concordanza)):
        sp.add_parser(nome).set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
