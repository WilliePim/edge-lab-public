"""Russell 2000, uscite verso il basso — identità: dai nomi delle partecipazioni di IWM al CIK (piano B2).

Nessuna fonte gratuita dà CUSIP → CIK, e i N-Q/N-CSR (2015-2019) non hanno nemmeno il CUSIP. Regola in cascata:

1. **Indice dei nomi** da tre fonti, tutte già su disco o in cache EDGAR:
   - corpus Form 4 (`form4_raw/`, `sales.jsonl`): nome dell'emittente, CIK, ticker, data di deposito;
   - `company_tickers_exchange.json` della SEC (CIK, nome e ticker di oggi);
   - `cik-lookup-data.txt` della SEC (ogni nome mai usato, con il CIK).
2. **Chiavi**: nome normalizzato (maiuscolo, senza punteggiatura, classi di azioni, sigle di stato «/NC», suffissi
   societari; abbreviazioni EDGAR sciolte) e la stessa chiave con le parole in ordine alfabetico e le iniziali unite
   («HB Fuller Co.» = «FULLER H B CO»).
3. **Candidati** per chiave esatta, poi chiave ordinata, poi somiglianza ≥ 0,92 (difflib) sui nomi del corpus e dei
   ticker di oggi. Ordine: CIK con Form 4 negli anni dell'istantanea, poi ticker di oggi, poi solo elenco storico.
4. **Verifica** (in `verifica_identita.py`, dopo il download dei prezzi): valore / azioni della posizione del fondo =
   chiusura del titolo alla data, entro il 3%. È la verifica che decide; i candidati qui sono solo proposte.

Output `state/backfill/russell/identita_candidati.csv`. Nessuna chiamata di rete (le due liste SEC sono in cache).

    python backtest/russell_exits/identita.py
"""
from __future__ import annotations

import collections
import csv
import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import sec  # noqa: E402

STATE = ROOT / "state" / "backfill"
HOLD = STATE / "russell" / "holdings"
INDICE = STATE / "russell" / "indice_nomi.json"
OUT = STATE / "russell" / "identita_candidati.csv"
TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
MAX_CANDIDATI = 4
SOGLIA_SIMILE = 0.92

SUFFISSI = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "LLC", "LP", "NV",
            "SA", "AG", "SE", "THE", "HOLDINGS CO"}
SINONIMI = {"BANCORPORATION": "BANCORP", "INTL": "INTERNATIONAL", "HLDGS": "HOLDINGS", "HLDG": "HOLDING",
            "SVCS": "SERVICES", "SVC": "SERVICE", "FINL": "FINANCIAL", "COS": "COMPANIES", "MFG": "MANUFACTURING",
            "PHARMS": "PHARMACEUTICALS", "SYS": "SYSTEMS", "INDS": "INDUSTRIES", "GRP": "GROUP", "MGMT": "MANAGEMENT",
            "PPTYS": "PROPERTIES", "RLTY": "REALTY", "INVT": "INVESTMENT", "ENTMT": "ENTERTAINMENT",
            "TECHNOLOGY": "TECHNOLOGIES", "COMMUNICATION": "COMMUNICATIONS", "BANCSHARES": "BANCSHARES"}


# -------------------------------------------------------------- normalizzazione --
def norm(nome):
    s = (nome or "").upper().strip()
    s = re.sub(r"^[—\-\s]+", "", s)
    s = re.sub(r"\(THE\)|,\s*THE\b|^THE\s+", " ", s)
    s = re.sub(r"\b(CLASS|CL|SERIES)\s+[A-Z]\b", " ", s)
    s = re.sub(r"\bNON[- ]VOTING\b|\bNVS\b|\bREDH\b|\bADR\b", " ", s)
    for _ in range(3):
        m = re.search(r"\s*/\s*([A-Z][A-Z0-9 .,]{0,18})/?\s*$", s)
        if not m or len(re.sub(r"[.,]", " ", s[:m.start()]).split()) < 2:
            break                                   # «B/E Aerospace»: la barra e' dentro il nome
        s = s[:m.start()].strip()
    s = s.replace("&", " AND ")
    s = re.sub(r"[.,'’()\-/:;!]", " ", s)
    tok = [SINONIMI.get(t, t) for t in s.split()]
    #  «U S» → «US», iniziali consecutive unite
    unite, buf = [], ""
    for t in tok:
        if len(t) == 1 and t.isalpha():
            buf += t
        else:
            if buf:
                unite.append(buf)
                buf = ""
            unite.append(t)
    if buf:
        unite.append(buf)
    while unite and unite[-1] in SUFFISSI:
        unite.pop()
    while unite and unite[0] == "THE":
        unite.pop(0)
    return " ".join(unite)


def chiave_ordinata(n):
    return " ".join(sorted(n.split()))


# ----------------------------------------------------------------------- indice --
def costruisci_indice():
    """{"corpus": {cik: {nomi, ticker: {t: [primo, ultimo]}, anni: [min, max]}}, "tickers": {cik: [nome, ticker]},
    "lookup": {chiave: [cik, ...]}} — salvato in `indice_nomi.json`."""
    corpus = {}
    for f in sorted((STATE / "form4_raw").glob("*.jsonl")) + [STATE / "sales.jsonl"]:
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                c = str(d.get("issuer_cik") or d.get("issuer") or "").lstrip("0")
                if not c:
                    continue
                fd = d.get("filed_date") or d.get("filed") or ""
                x = corpus.setdefault(c, {"nomi": set(), "ticker": {}, "anni": [9999, 0]})
                if d.get("issuer_name"):
                    x["nomi"].add(d["issuer_name"].strip())
                t = (d.get("ticker") or "").strip().upper()
                if t and fd:
                    a, b = x["ticker"].get(t, [fd, fd])
                    x["ticker"][t] = [min(a, fd), max(b, fd)]
                if fd[:4].isdigit():
                    x["anni"] = [min(x["anni"][0], int(fd[:4])), max(x["anni"][1], int(fd[:4]))]
        print("  letto", f.name, "emittenti", len(corpus), flush=True)
    tick = {}
    raw = sec.cache_path(TICKERS_URL).read_text(encoding="utf-8")
    dd = json.loads(raw)
    for riga in dd["data"]:
        x = dict(zip(dd["fields"], riga))
        tick[str(x["cik"])] = [x["name"], x["ticker"], x["exchange"]]
    lookup = collections.defaultdict(set)
    with sec.cache_path(LOOKUP_URL).open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parti = line.rstrip("\n").rsplit(":", 2)
            if len(parti) < 3 or not parti[0].strip():
                continue
            c = parti[1].lstrip("0")
            n = norm(parti[0])
            if n:
                lookup[n].add(c)
    out = {"corpus": {c: {"nomi": sorted(x["nomi"]), "ticker": x["ticker"], "anni": x["anni"]} for c, x in corpus.items()},
           "tickers": tick, "lookup": {k: sorted(v) for k, v in lookup.items()}}
    INDICE.write_text(json.dumps(out), encoding="utf-8")
    return out


def carica_indice():
    return json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else costruisci_indice()


# ------------------------------------------------------------------ candidati --
class Ricerca:
    def __init__(self, idx):
        self.idx = idx
        self.esatta = collections.defaultdict(set)
        self.ordinata = collections.defaultdict(set)
        self.fonte = collections.defaultdict(set)
        for c, x in idx["corpus"].items():
            for n in x["nomi"]:
                k = norm(n)
                self.esatta[k].add(c)
                self.ordinata[chiave_ordinata(k)].add(c)
                self.fonte[c].add("corpus")
        for c, (n, _t, _e) in idx["tickers"].items():
            k = norm(n)
            self.esatta[k].add(c)
            self.ordinata[chiave_ordinata(k)].add(c)
            self.fonte[c].add("tickers")
        self.lookup = idx["lookup"]
        self.lookup_ord = collections.defaultdict(set)
        for k, cs in self.lookup.items():
            self.lookup_ord[chiave_ordinata(k)].update(cs)
        self.blocchi = collections.defaultdict(list)
        for k in self.esatta:
            for t in set(k.split()):
                if len(t) >= 4:
                    self.blocchi[t].append(k)

    def rango(self, c, anno):
        x = self.idx["corpus"].get(c)
        attivo = bool(x and x["anni"][0] <= anno + 1 and x["anni"][1] >= anno - 1)
        return (0 if attivo else 1, 0 if "corpus" in self.fonte[c] else 1, 0 if c in self.idx["tickers"] else 1, int(c))

    def candidati(self, nome, anno):
        k = norm(nome)
        if not k:
            return k, "VUOTO", []
        for metodo, insieme in (("ESATTA", self.esatta.get(k)), ("ORDINATA", self.ordinata.get(chiave_ordinata(k))),
                                ("ELENCO_STORICO", set(self.lookup.get(k, [])) or None),
                                ("ELENCO_STORICO_ORDINATA", self.lookup_ord.get(chiave_ordinata(k)))):
            if insieme:
                return k, metodo, sorted(insieme, key=lambda c: self.rango(c, anno))[:MAX_CANDIDATI]
        pool = set()
        for t in set(k.split()):
            pool.update(self.blocchi.get(t, ()))
        punteggi = sorted(((difflib.SequenceMatcher(None, k, p).ratio(), p) for p in pool), reverse=True)[:3]
        if punteggi and punteggi[0][0] >= SOGLIA_SIMILE:
            cs = set()
            for s, p in punteggi:
                if s >= SOGLIA_SIMILE:
                    cs.update(self.esatta[p])
            return k, "SIMILE_{:.2f}".format(punteggi[0][0]), sorted(cs, key=lambda c: self.rango(c, anno))[:MAX_CANDIDATI]
        return k, "NON_TROVATO", []


# ----------------------------------------------------------------------- main --
def main() -> int:
    idx = carica_indice()
    print("indice: corpus", len(idx["corpus"]), "ticker di oggi", len(idx["tickers"]), "chiavi storiche", len(idx["lookup"]), flush=True)
    r = Ricerca(idx)
    man = json.loads((HOLD / "_manifest.json").read_text(encoding="utf-8"))
    righe, visti = [], {}
    conta = collections.Counter()
    for chiave in sorted(man):
        if man[chiave].get("esito") != "OK" or not chiave.startswith("IWM"):
            continue
        anno = int(chiave.split("_")[1][:4])
        with (HOLD / "{}.csv".format(chiave)).open(encoding="utf-8", newline="") as fh:
            for h in csv.DictReader(fh):
                nome = h["titolo"] or h["nome"]
                ck = (nome, anno)
                if ck not in visti:
                    visti[ck] = r.candidati(nome, anno)
                k, metodo, cs = visti[ck]
                conta[metodo.split("_")[0] if metodo.startswith("SIMILE") else metodo] += 1
                righe.append({"istantanea": chiave, "nome": h["nome"], "titolo": h["titolo"], "cusip": h["cusip"],
                              "azioni": h["azioni"], "valore": h["valore"], "chiave": k, "metodo": metodo,
                              "candidati": ";".join(cs)})
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe[0]))
        w.writeheader()
        w.writerows(righe)
    print("righe IWM:", len(righe), "| metodo:", dict(conta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
