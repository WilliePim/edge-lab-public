"""Split dei titoli del panel: la correzione del limite §15.4, una volta per ogni backtest sullo stesso panel.

Addendum 5 della pre-registrazione del ri-test (ADR-034). Decisione dell'utente del 2026-09-15.

IL DIFETTO. La market cap e' `azioni XBRL as-reported x adj_close`. Le azioni sono quelle dichiarate
alla data del documento; `adj_close` e' rettificato da Yahoo per ogni split successivo, fino al
download. Su un titolo che splitta DOPO la data, il prodotto sbaglia del fattore di split, in silenzio.

LA CORREZIONE. Con r_t = azioni nuove / azioni vecchie (2:1 -> 2, 1:10 -> 0,1) e `end` = data del
record di azioni:

    cap(D) = azioni(end) * adj_close(D) * prod_{end < t <= ultima barra} r_t

LE FONTI. (1) La tabella degli split di Yahoo, la stessa che ha prodotto `adj_close`. (2) Per i ticker
che Yahoo non serve piu' e che mostrano un salto del rapporto prezzo insider / adj_close, lo split letto
su EDGAR, accettato solo se il rapporto spiega il salto (addendum 5 §2.1). Un ticker senza nessuna delle
due resta SCONOSCIUTO: fattore 1, con flag (fail-closed).

    python backtest/splits.py scarica | riprova   # rete Yahoo: la tabella (gia' fatto il 2026-09-15)
    python backtest/splits.py prepara             # transazioni insider per CIK e ticker per CIK, zero rete
    python backtest/splits.py valida              # addendum 5 §4, zero rete
    python backtest/splits.py salti --popolazione backtest/rematch_50_300m/step2_prep/popolazione.jsonl
                                                  # addendum 5 §2.1, selezione, zero rete
    python backtest/splits.py edgar               # addendum 5 §2.1, rete EDGAR con tetto 500
    python backtest/splits.py stato
"""
from __future__ import annotations

import argparse
import bisect
import collections
import glob
import hashlib
import json
import math
import re
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "backfill"
FONTI = (STATE / "prices", STATE / "prices_resolved")
FILE = STATE / "splits.json"
EDGAR_FILE = STATE / "splits_edgar.json"
SALTI_FILE = STATE / "splits_salti.json"
INSIDER_FILE = STATE / "insider_prezzi_per_cik.json"
VALIDAZIONE_MD = ROOT / "backtest" / "splits_validazione.md"
VALIDAZIONE_JSON = ROOT / "backtest" / "splits_validazione.json"
EDGAR_MD = ROOT / "backtest" / "splits_edgar.md"
CALLS = ROOT / "backtest" / "split_edgar_calls.json"
CACHE = ROOT / ".edgar_cache"
LOTTO = 80

INIZIO_VALIDA, FINE_VALIDA = "2014-01-01", "2026-08-28"
FINESTRA_GIORNI = 365
SOGLIA_VALIDA = 0.90
SALTO = math.log(1.8)
TETTO_EDGAR = 500
FTS = ("https://efts.sec.gov/LATEST/search-index?q=%22stock%20split%22&ciks={cik:010d}"
       "&dateRange=custom&startdt={a}&enddt={b}")
ARCH = "https://www.sec.gov/Archives/edgar/data/"


def _ultima_barra(path):
    last = None
    with Path(path).open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d = line.split(",", 1)[0].strip()
            if len(d) == 10:
                last = d
    return last


def tickers():
    """{nome del file: (percorso, None)} per ogni serie del panel, `prices/` prima."""
    out = {}
    for d in FONTI:
        for p in sorted(d.glob("*.csv")):
            out.setdefault(p.stem, (p, None))
    return out


def serie(path):
    ds, px = [], []
    with Path(path).open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            d = d.strip()
            try:
                f = float(v)
            except ValueError:
                continue
            if len(d) == 10 and f > 0:
                ds.append(d)
                px.append(f)
    return ds, px


def piu(d, n):
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()


# --------------------------------------------------------------- Yahoo --
def scarica(_a) -> int:
    import yfinance as yf

    fatto = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"tickers": {}}
    tut = tickers()
    todo = sorted(t for t in tut if t not in fatto["tickers"])
    print("ticker nel panel {:,}, gia' fatti {:,}, da fare {:,}".format(len(tut), len(fatto["tickers"]), len(todo)),
          flush=True)
    for i in range(0, len(todo), LOTTO):
        chunk = todo[i:i + LOTTO]
        try:
            df = yf.download(chunk, period="max", actions=True, auto_adjust=False, progress=False,
                             threads=True, group_by="ticker")
        except Exception as e:                                          # noqa: BLE001
            print("  lotto {} fallito: {}".format(i, e), flush=True)
            time.sleep(10)
            continue
        for t in chunk:
            try:
                sub = df[t] if len(chunk) > 1 else df
                col = sub["Stock Splits"].dropna()
                ok = len(sub["Close"].dropna()) > 0
            except (KeyError, TypeError):
                fatto["tickers"][t] = {"stato": "SCONOSCIUTO", "split": []}
                continue
            if not ok:
                fatto["tickers"][t] = {"stato": "SCONOSCIUTO", "split": []}
                continue
            fatto["tickers"][t] = {"stato": "OK", "split": [[d.strftime("%Y-%m-%d"), float(v)]
                                                             for d, v in col.items() if v and float(v) > 0]}
        fatto["scaricato"] = date.today().isoformat()
        tmp = FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(fatto, sort_keys=True), encoding="utf-8")
        tmp.replace(FILE)
        print("  {:,}/{:,}".format(min(i + LOTTO, len(todo)), len(todo)), flush=True)
    return stato(_a)


def ticker_correnti():
    """{nome del file: ticker con cui la serie e' stata scaricata}: il recupero del panel ha salvato le
    serie dei ticker cambiati col nome VECCHIO (ABC.csv contiene COR). `price_failures_classified.json`."""
    p = STATE / "price_failures_classified.json"
    if not p.exists():
        return {}
    return {old.upper(): new.upper() for old, new in json.loads(p.read_text(encoding="utf-8")).get("changed") or []}


def riprova(_a) -> int:
    """Ripete i SCONOSCIUTO a lotti piccoli, col ticker corrente dove e' cambiato."""
    import yfinance as yf

    fatto = json.loads(FILE.read_text(encoding="utf-8"))
    nuovi = ticker_correnti()
    todo = sorted(t for t, v in fatto["tickers"].items() if v["stato"] != "OK")
    print("da riprovare {:,}".format(len(todo)), flush=True)
    for i in range(0, len(todo), 25):
        chunk = todo[i:i + 25]
        yahoo = {t: nuovi.get(t.upper(), t) for t in chunk}
        nomi = sorted(set(yahoo.values()))
        try:
            df = yf.download(nomi, period="max", actions=True, auto_adjust=False, progress=False,
                             threads=False, group_by="ticker")
        except Exception:                                               # noqa: BLE001
            df = None
        for t in chunk:
            try:
                sub = df[yahoo[t]] if len(nomi) > 1 else df
                if len(sub["Close"].dropna()) == 0:
                    continue
                col = sub["Stock Splits"].dropna()
            except (KeyError, TypeError):
                continue
            fatto["tickers"][t] = {"stato": "OK", "yahoo": yahoo[t],
                                   "split": [[d.strftime("%Y-%m-%d"), float(v)] for d, v in col.items()
                                             if v and float(v) > 0]}
        tmp = FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(fatto, sort_keys=True), encoding="utf-8")
        tmp.replace(FILE)
        time.sleep(3)
    return stato(_a)


def stato(_a) -> int:
    fatto = json.loads(FILE.read_text(encoding="utf-8"))["tickers"]
    ok = [v for v in fatto.values() if v["stato"] == "OK"]
    ed = json.loads(EDGAR_FILE.read_text(encoding="utf-8"))["tickers"] if EDGAR_FILE.exists() else {}
    print("ticker {:,}: OK {:,} (con almeno uno split {:,}), SCONOSCIUTO {:,}, di cui con split EDGAR {:,}".format(
        len(fatto), len(ok), sum(1 for v in ok if v["split"]), len(fatto) - len(ok), len(ed)))
    return 0


# ------------------------------------------------- transazioni insider --
def prepara(_a) -> int:
    """{cik: [[data, prezzo medio ponderato del giorno]]} da acquisti e vendite, e {ticker: [cik]}."""
    somme = collections.defaultdict(lambda: [0.0, 0.0])
    per_ticker = collections.defaultdict(set)

    def assorbi(r):
        c = (r.get("issuer_cik") or "").lstrip("0")
        t = (r.get("ticker") or "").upper().replace("/", "_")
        if c and t and t not in ("NONE", "N/A", "[NONE]"):
            per_ticker[t].add(c)
        try:
            px, sh = float(r.get("price") or 0), float(r.get("shares") or 0)
        except (TypeError, ValueError):
            return
        d = r.get("transaction_date") or ""
        if c and px > 0 and sh > 0 and len(d) == 10:
            s = somme[(c, d)]
            s[0] += px * sh
            s[1] += sh

    for fn in sorted(glob.glob(str(STATE / "form4_raw" / "*.jsonl"))):
        with open(fn, encoding="utf-8") as fh:
            for line in fh:
                try:
                    assorbi(json.loads(line))
                except ValueError:
                    continue
    n = 0
    with (STATE / "sales.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                assorbi(json.loads(line))
            except ValueError:
                continue
            n += 1
            if n % 1_000_000 == 0:
                print("  vendite {:,}".format(n), flush=True)
    per_cik = collections.defaultdict(list)
    for (c, d), (v, s) in somme.items():
        per_cik[c].append([d, v / s, s])
    for v in per_cik.values():
        v.sort()
    INSIDER_FILE.write_text(json.dumps({"per_cik": per_cik, "cik_per_ticker": {t: sorted(c) for t, c in per_ticker.items()}}),
                            encoding="utf-8")
    print("CIK con prezzi insider {:,}, ticker mappati {:,}".format(len(per_cik), len(per_ticker)))
    return 0


def _insider():
    d = json.loads(INSIDER_FILE.read_text(encoding="utf-8"))
    return d["per_cik"], d["cik_per_ticker"]


def rapporti_f(stem, per_cik, cik_per_ticker):
    """[(data, f)] con f = prezzo insider / adj_close alla stessa data (ultimo close entro 7 giorni)."""
    p = tickers().get(stem) if not hasattr(rapporti_f, "_t") else rapporti_f._t.get(stem)
    if not p:
        return []
    ds, px = serie(p[0])
    out = []
    for c in cik_per_ticker.get(stem.upper(), []):
        for d, pr, *_ in per_cik.get(c, []):
            j = bisect.bisect_right(ds, d) - 1
            if j >= 0 and (date.fromisoformat(d) - date.fromisoformat(ds[j])).days <= 7:
                out.append((d, pr / px[j]))
    out.sort()
    return out


def classifica_split(osservato, atteso):
    """Addendum 4 §4, come riscritto nell'addendum 5 §4."""
    dist = abs(math.log(osservato / atteso))
    if dist <= math.log(1.5) and dist < abs(math.log(osservato)):
        return "CONFERMATO"
    if abs(math.log(osservato)) <= math.log(1.25):
        return "PIATTO"
    return "DISCORDE"


def valida(_a) -> int:
    tab = json.loads(FILE.read_text(encoding="utf-8"))["tickers"]
    per_cik, cik_per_ticker = _insider()
    rapporti_f._t = tickers()
    conta = collections.Counter()
    righe = []
    for stem, rec in sorted(tab.items()):
        if rec["stato"] != "OK":
            continue
        sp = [(d, r) for d, r in rec["split"] if INIZIO_VALIDA <= d <= FINE_VALIDA]
        if not sp:
            continue
        fs = rapporti_f(stem, per_cik, cik_per_ticker)
        if not fs:
            conta["NON_VERIFICABILE"] += len(sp)
            continue
        date_f = [d for d, _ in fs]
        for d, r in sp:
            i = bisect.bisect_left(date_f, d) - 1
            j = bisect.bisect_left(date_f, d)
            if i < 0 or j >= len(fs) or (date.fromisoformat(d) - date.fromisoformat(fs[i][0])).days > FINESTRA_GIORNI \
                    or (date.fromisoformat(fs[j][0]) - date.fromisoformat(d)).days > FINESTRA_GIORNI:
                conta["NON_VERIFICABILE"] += 1
                continue
            atteso = 1.0
            for d2, r2 in rec["split"]:
                if fs[i][0] < d2 <= fs[j][0]:
                    atteso *= r2
            esito = classifica_split(fs[i][1] / fs[j][1], atteso)
            conta[esito] += 1
            righe.append({"ticker": stem, "data": d, "rapporto": r, "atteso": atteso,
                          "osservato": fs[i][1] / fs[j][1], "esito": esito})
    verificabili = conta["CONFERMATO"] + conta["PIATTO"] + conta["DISCORDE"]
    quota = conta["CONFERMATO"] / verificabili if verificabili else 0.0
    valida_ok = quota >= SOGLIA_VALIDA
    VALIDAZIONE_JSON.write_text(json.dumps({"conta": conta, "quota": quota, "soglia": SOGLIA_VALIDA,
                                            "valida": valida_ok, "righe": righe}, indent=1), encoding="utf-8")
    L = ["# Validazione della tabella degli split di Yahoo", "",
         "Generato da `python backtest/splits.py valida`. Addendum 5 §4. Zero chiamate di rete.", "",
         "| esito | split |", "|---|---:|"]
    L += ["| {} | {:,} |".format(k, v) for k, v in sorted(conta.items())]
    L += ["", "**CONFERMATI / verificabili = {:,} / {:,} = {:.1%}**, soglia {:.0%}: **{}**.".format(
        conta["CONFERMATO"], verificabili, quota, SOGLIA_VALIDA,
        "tabella VALIDA, la correzione si applica" if valida_ok else "tabella NON VALIDA, nessuna correzione"), "",
          "## Discordi", "", "| ticker | data | rapporto | atteso | osservato |", "|---|---|---:|---:|---:|"]
    L += ["| {} | {} | {:g} | {:.3g} | {:.3g} |".format(x["ticker"], x["data"], x["rapporto"], x["atteso"], x["osservato"])
          for x in righe if x["esito"] == "DISCORDE"]
    VALIDAZIONE_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))
    return 0


# ------------------------------------------------------ salti ed EDGAR --
def insieme_usato(popolazioni):
    """Ticker delle serie del pool e delle popolazioni indicate.

    `popolazioni`: percorsi obbligatori, senza default. Un `.jsonl` con il campo `serie` (per esempio
    `backtest/rematch_50_300m/step2_prep/popolazione.jsonl`, rigenerabile con `survival.py popolazione`)
    oppure un `.csv` con le colonne `serie` e/o `serie_madre`. Un file mancante ferma il comando.
    """
    import csv

    prezzi = {p.stem.upper(): p for p in FONTI[0].glob("*.csv")}
    tick = collections.defaultdict(dict)
    for fn in sorted(glob.glob(str(STATE / "form4_raw" / "*.jsonl"))):
        with open(fn, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                c = (r.get("issuer_cik") or "").lstrip("0")
                t = (r.get("ticker") or "").upper()
                if c and t and t not in ("NONE", "N/A", "[NONE]") and (r.get("filed_date") or "") > tick[c].get(t, ""):
                    tick[c][t] = r.get("filed_date") or ""
    out = set()
    for c, per in tick.items():
        if not (STATE / "shares" / "{}.json".format(c)).exists():
            continue
        xs = sorted(((d, t) for t, d in per.items() if t.replace("/", "_") in prezzi), reverse=True)
        if xs:
            out.add(prezzi[xs[0][1].replace("/", "_")].stem)
    for pop in popolazioni:
        pop = Path(pop)
        if not pop.exists():
            raise SystemExit("popolazione non trovata: {}".format(pop))
        if pop.suffix == ".jsonl":
            for line in pop.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r.get("serie"):
                    out.add(Path(r["serie"]).stem)
        else:
            with pop.open(encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    for k in ("serie", "serie_madre"):
                        if r.get(k):
                            out.add(Path(r[k]).stem)
    return out


def salti(_a) -> int:
    tab = json.loads(FILE.read_text(encoding="utf-8"))["tickers"]
    per_cik, cik_per_ticker = _insider()
    rapporti_f._t = tickers()
    usati = insieme_usato(_a.popolazione)
    sconosciuti = sorted(t for t in usati if (tab.get(t) or {}).get("stato") != "OK")
    out, conta = {}, collections.Counter()
    for stem in sconosciuti:
        fs = rapporti_f(stem, per_cik, cik_per_ticker)
        if len(fs) < 2:
            conta["non verificabili"] += 1
            continue
        finestre = []
        for (da, fa), (db, fb) in zip(fs, fs[1:]):
            if (date.fromisoformat(db) - date.fromisoformat(da)).days <= FINESTRA_GIORNI and abs(math.log(fa / fb)) > SALTO:
                if finestre and da <= finestre[-1]["b"]:
                    finestre[-1]["b"], finestre[-1]["osservato"] = db, finestre[-1]["osservato"] * fa / fb
                else:
                    finestre.append({"a": da, "b": db, "osservato": fa / fb})
        if finestre:
            ciks = cik_per_ticker.get(stem.upper(), [])
            out[stem] = {"ciks": ciks, "finestre": finestre}
            conta["con salto"] += 1
        else:
            conta["senza salto"] += 1
    SALTI_FILE.write_text(json.dumps({"conta": conta, "ticker": out}, indent=1, sort_keys=True), encoding="utf-8")
    print("ticker usati {:,}, senza tabella {:,}: {}".format(len(usati), len(sconosciuti), dict(conta)))
    print("finestre da cercare su EDGAR: {:,}".format(sum(len(v["finestre"]) for v in out.values())))
    return 0


PAROLE = {w: i for i, w in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                                      "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                                      "seventeen", "eighteen", "nineteen", "twenty"])}
PAROLE.update({"twenty-five": 25, "thirty": 30, "thirty-five": 35, "forty": 40, "fifty": 50, "sixty": 60,
               "seventy": 70, "seventy-five": 75, "eighty": 80, "one hundred": 100, "hundred": 100})
NUM = r"(\d{1,4}|twenty-five|thirty-five|seventy-five|one hundred|[a-z]+)"
RX_RAPPORTO = re.compile(NUM + r"[- ](?:for|to)[- ]" + NUM + r"\)?\s+(reverse\s+)?(?:stock\s+|share\s+)?split", re.I)
DATA = r"([A-Z][a-z]+ \d{1,2}, \d{4})"
RX_EFFETTIVA = re.compile(r"effective[^.]{0,60}?" + DATA)


def _numero(w):
    w = w.lower()
    if w.isdigit():
        return float(w)
    return float(PAROLE[w]) if w in PAROLE else None


def _data(s):
    try:
        return datetime.strptime(s, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def leggi_split(testo):
    """(rapporto, data effettiva o None, citazione) dal testo, o None."""
    t = re.sub(r"\s+", " ", testo or "")
    trovati = []
    for m in RX_RAPPORTO.finditer(t):
        a, b = _numero(m.group(1)), _numero(m.group(2))
        if not a or not b or a == b:
            continue
        r = a / b
        e = RX_EFFETTIVA.search(t[max(0, m.start() - 300):m.end() + 300])
        trovati.append((round(r, 6), _data(e.group(1)) if e else None, t[max(0, m.start() - 150):m.end() + 150]))
    if not trovati:
        return None
    c = collections.Counter(r for r, _, _ in trovati)
    top = max(c.values())
    r = next(x for x, _, _ in trovati if c[x] == top)
    d = next((dd for x, dd, _ in trovati if x == r and dd), None)
    cit = next(cc for x, _, cc in trovati if x == r)
    return r, d, cit


class Budget:
    def __init__(self):
        sys.path.insert(0, str(ROOT))
        from edgar_llm.config import get as env_get
        from form4_scanner.edgar import EdgarClient

        ua = env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")
        if not ua or "@" not in ua:
            raise SystemExit("serve EDGAR_USER_AGENT con nome ed email")
        self.client = EdgarClient(ua, cache_dir=CACHE, min_interval=0.15)
        self.usate = json.loads(CALLS.read_text(encoding="utf-8"))["network"] if CALLS.exists() else 0

    def get(self, url):
        p = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".cache")
        if not p.exists() and self.usate >= TETTO_EDGAR:
            return None
        prima = self.client.stats["network"]
        txt = self.client.get(url)
        self.usate += self.client.stats["network"] - prima
        CALLS.write_text(json.dumps({"network": self.usate, "tetto": TETTO_EDGAR}), encoding="utf-8")
        return txt


def edgar(_a) -> int:
    sys.path.insert(0, str(ROOT))
    from edgar_llm.fetch import UnreadableDocument, to_text

    sal = json.loads(SALTI_FILE.read_text(encoding="utf-8"))["ticker"]
    budget = Budget()
    accettati, righe = {}, []
    for stem, v in sorted(sal.items()):
        for w in v["finestre"]:
            riga = {"ticker": stem, "a": w["a"], "b": w["b"], "osservato": w["osservato"], "esito": "NESSUN_DOCUMENTO"}
            documenti = []
            for cik in v["ciks"]:
                raw = budget.get(FTS.format(cik=int(cik), a=piu(w["a"], -30), b=piu(w["b"], 60)))
                if raw is None:
                    riga["esito"] = "NON_SCARICATO"
                    continue
                try:
                    hits = json.loads(raw)["hits"]["hits"]
                except (ValueError, KeyError, TypeError):
                    continue
                for h in hits:
                    s = h.get("_source") or {}
                    adsh, _, doc = (h.get("_id") or "").partition(":")
                    if adsh and doc:
                        documenti.append((0 if (s.get("form") or "").startswith("8-K") else 1, s.get("file_date") or "",
                                          cik, adsh, doc, s.get("form")))
            visti = set()
            letti = 0
            for _p, fd, cik, adsh, doc, form in sorted(documenti):
                if letti >= 2 or (adsh, doc) in visti:
                    continue
                visti.add((adsh, doc))
                raw = budget.get("{}{}/{}/{}".format(ARCH, int(cik), adsh.replace("-", ""), doc))
                letti += 1
                if raw is None:
                    continue
                try:
                    testo = to_text(raw)
                except UnreadableDocument:
                    continue
                trovato = leggi_split(testo)
                if not trovato:
                    continue
                r, d_eff, cit = trovato
                data_split = d_eff or fd
                riga.update({"rapporto": r, "data": data_split, "data_da_deposito": d_eff is None,
                             "accession": adsh, "forma": form, "citazione": cit[:300]})
                spiega = abs(math.log(w["osservato"] / r)) <= math.log(1.5)
                in_finestra = piu(w["a"], -30) < data_split <= w["b"]
                riga["esito"] = "ACCETTATO" if (spiega and in_finestra) else (
                    "RAPPORTO_NON_SPIEGA_IL_SALTO" if not spiega else "DATA_FUORI_FINESTRA")
                break
            if riga["esito"] == "ACCETTATO":
                accettati.setdefault(stem, []).append([riga["data"], riga["rapporto"]])
            righe.append(riga)
        print("  {} chiamate {}".format(stem, budget.usate), flush=True)
    EDGAR_FILE.write_text(json.dumps({"tickers": {k: {"stato": "OK_EDGAR", "split": sorted(v)} for k, v in accettati.items()},
                                      "righe": righe}, indent=1, sort_keys=True), encoding="utf-8")
    conta = collections.Counter(r["esito"] for r in righe)
    L = ["# Split da EDGAR per i ticker senza tabella Yahoo", "",
         "Generato da `python backtest/splits.py edgar`. Addendum 5 §2.1. Chiamate EDGAR: **{}** su {}.".format(
             budget.usate, TETTO_EDGAR), "", "| esito | finestre |", "|---|---:|"]
    L += ["| {} | {} |".format(k, v) for k, v in sorted(conta.items())]
    L += ["", "| ticker | finestra | osservato | rapporto letto | data | esito | accession |", "|---|---|---:|---:|---|---|---|"]
    L += ["| {} | {} – {} | {:.3g} | {} | {} | {} | {} |".format(r["ticker"], r["a"], r["b"], r["osservato"],
                                                               r.get("rapporto", "—"), r.get("data", "—"), r["esito"],
                                                               r.get("accession", "—")) for r in righe]
    EDGAR_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("esiti:", dict(conta), "ticker con split accettato:", len(accettati))
    return 0


# ------------------------------------------------------------- fattore --
def registri_azioni(cik, con_fallback=False):
    """{filed: (val, end)} di `shares/<cik>.json`, stessa regola di `survival.Azioni` e del `Pool`
    (a parita' di `filed` vince l'ultimo). `con_fallback=True` e' la regola di `marketcap_build.py`."""
    p = STATE / "shares" / "{}.json".format(cik)
    by = {}
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        righe = (d.get("primary") or d.get("fallback") or []) if con_fallback else (d.get("primary") or [])
        for r in righe:
            if r.get("filed") and r.get("val"):
                by[r["filed"]] = (float(r["val"]), r.get("end") or r["filed"])
    return by


class Split:
    """Fattore di correzione. Nessuna rete: legge la tabella Yahoo e gli split EDGAR accettati."""

    def __init__(self):
        self.tab = json.loads(FILE.read_text(encoding="utf-8"))["tickers"]
        self.edgar = json.loads(EDGAR_FILE.read_text(encoding="utf-8"))["tickers"] if EDGAR_FILE.exists() else {}
        self._ultima = {}
        self._paths = tickers()

    def ultima_barra(self, ticker):
        if ticker not in self._ultima:
            p = self._paths.get(ticker)
            self._ultima[ticker] = _ultima_barra(p[0]) if p else None
        return self._ultima[ticker]

    def fattore(self, ticker, data_azioni):
        """(fattore, stato): OK, OK_EDGAR, SCONOSCIUTO. Split con data_azioni < t <= ultima barra."""
        rec = self.tab.get(ticker)
        if rec and rec["stato"] == "OK":
            stato = "OK"
        elif ticker in self.edgar:
            rec, stato = self.edgar[ticker], "OK_EDGAR"
        else:
            return 1.0, "SCONOSCIUTO"
        fine = self.ultima_barra(ticker) or "9999-12-31"
        f = 1.0
        for d, r in rec["split"]:
            if data_azioni < d <= fine:
                f *= r
        return f, stato


def correggi_pool(pool, tick, split, ids):
    """Riscrive in place `pool.A` e `pool.fuori_sessione` di `step2_analysis.Pool` con le azioni moltiplicate
    per il fattore. Il ticker di ogni emittente e' scelto con la regola del Pool. Ritorna un Counter degli
    stati del fattore sui record di azioni."""
    import numpy as np

    prezzi = {p.stem.upper(): p for p in FONTI[0].glob("*.csv")}
    ords = np.array(ids, dtype="datetime64[D]").astype(np.int64)
    sessioni = set(ids)
    conta = collections.Counter()
    pool.fuori_sessione = collections.defaultdict(list)
    for i, c in enumerate(pool.ciks):
        per = tick[c]
        con_serie = sorted(((dep, t) for t, dep in per.items() if (t or "").replace("/", "_").upper() in prezzi),
                           reverse=True)
        stem = prezzi[con_serie[0][1].replace("/", "_").upper()].stem
        by = registri_azioni(c)
        if not by:
            continue
        fdate = sorted(by)
        vals = []
        for x in fdate:
            v, end = by[x]
            f, st = split.fattore(stem, end)
            conta[st] += 1
            vals.append(v * f)
            if x not in sessioni:
                pool.fuori_sessione[x].append((i, v * f))
        fo = np.array(fdate, dtype="datetime64[D]").astype(np.int64)
        vals = np.array(vals)
        k2 = np.searchsorted(fo, ords, side="right") - 1
        pool.A[i] = np.where(k2 >= 0, vals[np.where(k2 >= 0, k2, 0)], np.nan)
    pool._cache = {}
    return conta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nome, fn in (("scarica", scarica), ("riprova", riprova), ("stato", stato), ("prepara", prepara),
                     ("valida", valida), ("salti", salti), ("edgar", edgar)):
        p = sp.add_parser(nome)
        p.set_defaults(fn=fn)
        if nome == "salti":
            p.add_argument("--popolazione", nargs="+", required=True, metavar="FILE",
                           help="popolazioni degli eventi (.jsonl con `serie` o .csv con `serie`/`serie_madre`)")
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
