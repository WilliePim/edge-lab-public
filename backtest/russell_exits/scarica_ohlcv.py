"""Russell 2000, uscite verso il basso — prezzi e volumi giornalieri da Yahoo (piano B4).

Per le prime due società candidate di ogni riga di IWM (`identita_candidati.csv`): ticker di oggi dalla SEC e ticker
usati nei Form 4 negli anni vicini all'istantanea. Yahoo con `auto_adjust=False`, `actions=True`, dal 2014-01-01:
`Close` (rettificata per split), `Adj Close` (split e dividendi), `Volume`, `Stock Splits`. Un file per ticker in
`state/backfill/russell/ohlcv/`, manifesto con esito. Gruppi da 25 ticker, pausa di 2 secondi. I titoli delistati non
ci sono: limite dichiarato (decisione dell'utente). Nessun rendimento qui.

    python backtest/russell_exits/scarica_ohlcv.py
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import identita as I  # noqa: E402

STATE = ROOT / "state" / "backfill" / "russell"
OUT = STATE / "ohlcv"
MANIFEST = OUT / "_manifest.json"
GRUPPO, PAUSA, INIZIO, FINE = 25, 2.0, "2014-01-01", "2026-08-29"
COLONNE = ("Close", "Adj Close", "Volume", "Stock Splits")
CANDIDATI_PER_RIGA = 2


#  Nomi riservati di Windows: «CON.csv» è la console, non un file (scriverlo stampa a video, leggerlo resta in attesa).
RISERVATI = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}


def percorso(t):
    return OUT / "{}{}.csv".format("_" if t.upper() in RISERVATI else "", t)


def yahoo(t):
    """Simbolo Yahoo, o "" se contiene caratteri che non sono un ticker (virgole, punti interrogativi, spazi)."""
    y = (t or "").strip().upper().replace(".", "-").replace("/", "-")
    return y if re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{0,9}", y) else ""


def ticker_per_cik(idx, cik, anno):
    out = []
    tk = idx["tickers"].get(cik)
    if tk:
        out.append(tk[1])
    per = (idx["corpus"].get(cik) or {}).get("ticker") or {}
    vicini = [t for t, (a, b) in per.items() if int(a[:4]) <= anno + 1 and int(b[:4]) >= anno - 2]
    out += sorted(vicini, key=lambda t: per[t][1], reverse=True)
    if not out and per:
        out.append(max(per, key=lambda t: per[t][1]))
    visti, pulito = set(), []
    for t in out:
        y = yahoo(t)
        if y and y not in visti and " " not in y and y not in ("NONE", "N/A"):
            visti.add(y)
            pulito.append(y)
    return pulito


def cella(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return repr(f) if math.isfinite(f) else ""


def main() -> int:
    import yfinance as yf

    OUT.mkdir(parents=True, exist_ok=True)
    idx = I.carica_indice()
    richiesti = set()
    with (STATE / "identita_candidati.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            anno = int(r["istantanea"].split("_")[1][:4])
            for c in [x for x in r["candidati"].split(";") if x][:CANDIDATI_PER_RIGA]:
                richiesti.update(ticker_per_cik(idx, c, anno))
    richiesti.add("IWM")
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    da_fare = sorted(t for t in richiesti if t not in man)
    print("ticker richiesti:", len(richiesti), "da scaricare:", len(da_fare), flush=True)
    for g in range(0, len(da_fare), GRUPPO):
        blocco = da_fare[g:g + GRUPPO]
        try:
            df = yf.download(blocco, start=INIZIO, end=FINE, auto_adjust=False, actions=True, progress=False,
                             threads=True, group_by="ticker")
        except Exception as ex:                                            # noqa: BLE001
            df = None
            for t in blocco:
                man[t] = {"esito": "ERRORE_" + type(ex).__name__, "righe": 0}
        if df is not None:
            for t in blocco:
                try:
                    #  con group_by="ticker" le colonne hanno due livelli anche per un gruppo di un solo ticker
                    sub = df[t] if (len(blocco) > 1 or getattr(df.columns, "nlevels", 1) > 1) else df
                    sub = sub.dropna(subset=["Close"])
                except Exception:                                          # noqa: BLE001
                    sub = None
                if sub is None or not len(sub):
                    man[t] = {"esito": "NESSUN_DATO", "righe": 0}
                    continue
                p = percorso(t)
                with p.open("w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(("Date",) + COLONNE)
                    for d, riga in sub.iterrows():
                        w.writerow([d.strftime("%Y-%m-%d")] + [cella(riga.get(k)) for k in COLONNE])
                man[t] = {"esito": "OK", "righe": int(len(sub)), "da": sub.index.min().strftime("%Y-%m-%d"),
                          "a": sub.index.max().strftime("%Y-%m-%d")}
        if (g // GRUPPO) % 10 == 0:
            MANIFEST.write_text(json.dumps(man, indent=0, sort_keys=True), encoding="utf-8")
            ok = sum(1 for v in man.values() if v["esito"] == "OK")
            print("  {}/{} ok {}".format(g + len(blocco), len(da_fare), ok), flush=True)
        time.sleep(PAUSA)
    MANIFEST.write_text(json.dumps(man, indent=0, sort_keys=True), encoding="utf-8")
    conta = {}
    for v in man.values():
        conta[v["esito"]] = conta.get(v["esito"], 0) + 1
    print("esiti:", conta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
