"""E3, fasi 5-6 — rendimenti extra, statistica, controlli e verdetti (fermata 2).

Tutto quello che c'è qui è scritto nella pre-registrazione (`2026-09-22_preregistrazione.md`) e nell'addendum della
fermata 1 (`2026-09-22_addendum_fermata1.md`), prima di calcolare qualunque rendimento. I paragrafi citati sono della
pre-registrazione.

- **Rendimento extra** (§8): caso meno la media dei peer, sulle stesse date, sulla chiusura rettificata;
  `russell_exits/rendimenti.rendimento_extra` riusato così com'è (almeno 3 peer con prezzo; delistati all'ultimo
  prezzo o al prezzo in contanti dell'offerta, dal documento
  scaricato se non in cache e contato nel tetto). Le serie seguono i cambi di ticker (`serie_seguita`).
- **Celle**: ingressi A, B, C delle rotte e ingresso unico delle forti, × 63, 126, 252 sedute; placebo = la finestra
  di 252 sedute spostata in avanti di 126, con gli stessi peer; base di coorte = ogni IPO classificata alla data di
  controllo, senza filtri.
- **Statistica** (§8) per anno di coorte, t sulle medie annuali, sottoperiodi 2012-2018 e 2019-2024, coorte 2020-2021
  descrittiva.
- **Verdetto** (§1 e addendum §3): REGGE se valgono tutti e cinque i criteri; INCONCLUSIVO se la mediana e la media
  delle medie annuali sono positive con t fra 1 e 2, **oppure** se la cella non raggiunge il criterio 1, qualunque
  sia il segno; altrimenti NON REGGE.

Scrive `state/backfill/ipo_e3/rendimenti.csv` (una riga per caso, ingresso e finestra) e `risultati/verdetto.json`.

    python backtest/ipo_e3/analisi.py
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import io
import json
import math
import statistics
import zipfile

import comune as C

ORIZZONTI = (63, 126, 252)
PLACEBO_SPOSTAMENTO, PLACEBO_ORIZZONTE = 126, 252
SOTTOPERIODI = (("2012-2018", 2012, 2018), ("2019-2024", 2019, 2024))
BOLLA = (2020, 2021)
MIN_CASI, MIN_ANNI = 80, 8
SOGLIA_T, SOGLIA_T_BASSA = 2.0, 1.0
VERDETTI = {"1. IPO rotte": ("B", 252), "2. IPO forti": ("forte", 252)}
RIGHE = C.STATO / "rendimenti.csv"
JSON = C.RISULTATI / "verdetto.json"
ZIPS_FORM345 = [C.STATO.parent / "sec_bulk", C.STATO.parent / "zips"]


# ---------------------------------------------------------------------------------------------- statistica ---
def _media_delle_medie(per_anno: dict[int, list[float]]):
    medie = {a: statistics.fmean(v) for a, v in sorted(per_anno.items()) if v}
    mom = statistics.fmean(medie.values()) if medie else None
    t = None
    if len(medie) >= 2 and statistics.stdev(medie.values()) > 0:
        t = mom / (statistics.stdev(medie.values()) / math.sqrt(len(medie)))
    return medie, mom, t


def statistiche(per_anno: dict[int, list[float]]) -> dict:
    per_anno = {a: v for a, v in per_anno.items() if v}
    tutti = [x for v in per_anno.values() for x in v]
    medie, mom, t = _media_delle_medie(per_anno)
    fuori = {"casi": len(tutti), "anni": len(medie),
             "media": statistics.fmean(tutti) if tutti else None,
             "mediana": statistics.median(tutti) if tutti else None,
             "quota_positivi": sum(1 for x in tutti if x > 0) / len(tutti) if tutti else None,
             "medie_per_anno": medie, "casi_per_anno": {a: len(v) for a, v in sorted(per_anno.items())},
             "media_delle_medie": mom, "t": t, "gradi": len(medie) - 1 if t is not None else None,
             "sottoperiodi": {}}
    for nome, da, a in SOTTOPERIODI:
        parte = {y: v for y, v in per_anno.items() if da <= y <= a}
        _m, mom_p, t_p = _media_delle_medie(parte)
        fuori["sottoperiodi"][nome] = {"casi": sum(len(v) for v in parte.values()), "anni": len(parte),
                                       "media_delle_medie": mom_p, "t": t_p}
    return fuori


def verdetto(cella: dict, placebo: dict) -> tuple[str, dict]:
    """(esito, criteri) secondo il §1 e l'addendum §3. Un criterio che non si può calcolare è falso."""
    mom, t, sub = cella["media_delle_medie"], cella["t"], cella["sottoperiodi"]
    criteri = {
        "1. almeno 80 casi e almeno 8 anni": cella["casi"] >= MIN_CASI and cella["anni"] >= MIN_ANNI,
        "2. mediana > 0": cella["mediana"] is not None and cella["mediana"] > 0,
        "3. media delle medie annuali > 0 con t ≥ 2": mom is not None and mom > 0 and t is not None and t >= SOGLIA_T,
        "4. media > 0 in 2012-2018 e in 2019-2024": all(
            sub[n]["media_delle_medie"] is not None and sub[n]["media_delle_medie"] > 0 for n, _a, _b in SOTTOPERIODI),
        "5. placebo con |t| < 2 e media più bassa": (
            placebo["t"] is not None and abs(placebo["t"]) < SOGLIA_T and placebo["media_delle_medie"] is not None
            and mom is not None and placebo["media_delle_medie"] < mom),
    }
    if all(criteri.values()):
        return "REGGE", criteri
    if not criteri["1. almeno 80 casi e almeno 8 anni"]:
        return "INCONCLUSIVO", criteri
    if criteri["2. mediana > 0"] and mom is not None and mom > 0 and t is not None and SOGLIA_T_BASSA <= t < SOGLIA_T:
        return "INCONCLUSIVO", criteri
    return "NON REGGE", criteri


# --------------------------------------------------------------------------------------------------- insider ---
def _data_bulk(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s[:11], fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def insider(finestre: dict[str, tuple[str, str, str]]) -> dict[str, dict]:
    """{cik: {"depositi": n, "vendite": n}} per le rotte. `finestre`: cik -> (collocamento, S, ingresso B).

    Depositi = Form 3/4/5 dell'emittente fra collocamento e ingresso; vendite = transazioni non derivate con codice S,
    data fra S e l'ingresso escluso, di un Officer o Director (addendum §3)."""
    fuori = {k: {"depositi": 0, "vendite": 0} for k in finestre}
    for cartella in ZIPS_FORM345:
        for zp in sorted(cartella.glob("*form345*.zip")):
            with zipfile.ZipFile(zp) as z:
                def righe(nome):
                    with z.open(nome) as fh:
                        yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
                                                  delimiter="\t")
                acc = {}
                for r in righe("SUBMISSION.tsv"):
                    k = (r.get("ISSUERCIK") or "").strip().zfill(10)
                    if k in finestre:
                        d = _data_bulk(r.get("FILING_DATE"))
                        coll, _s, ing = finestre[k]
                        if coll <= d < ing:
                            fuori[k]["depositi"] += 1
                        acc[r["ACCESSION_NUMBER"]] = k
                if not acc:
                    continue
                ruolo = collections.defaultdict(str)
                for r in righe("REPORTINGOWNER.tsv"):
                    if r["ACCESSION_NUMBER"] in acc:
                        ruolo[r["ACCESSION_NUMBER"]] += "," + (r.get("RPTOWNER_RELATIONSHIP") or "")
                for r in righe("NONDERIV_TRANS.tsv"):
                    a = r["ACCESSION_NUMBER"]
                    if a not in acc or (r.get("TRANS_CODE") or "").strip() != "S":
                        continue
                    if "Officer" not in ruolo[a] and "Director" not in ruolo[a]:
                        continue
                    k = acc[a]
                    _c, s, ing = finestre[k]
                    if s <= _data_bulk(r.get("TRANS_DATE")) < ing:
                        fuori[k]["vendite"] += 1
    return fuori


# --------------------------------------------------------------------------------------------------- offerta ---
def offerta(cik: str, ultima_data: str, budget) -> float | None:
    """Il prezzo in contanti dell'offerta di acquisto, o None. Come `russell_exits/rendimenti.offerta_in_cache`, ma i
    depositi vengono dallo zip in blocco delle submissions (ADR-046) e un documento che non è in cache si scarica,
    contato nel tetto di E3 (addendum §3). Candidati: l'8-K del completamento (voci 2.01, 5.01, 8.01), il DEFM14A/C,
    l'SC TO-T, fra 180 giorni prima e 60 dopo l'ultima barra. Vale solo un esito CONTANTI di `survival.leggi_deal`."""
    import bulk
    import rendimenti as R
    import survival as SV
    if not cik:
        return None
    _t, dep = bulk.submissions(cik)
    if not dep:
        return None
    fine = dt.date.fromisoformat(ultima_data)
    lo = (fine - dt.timedelta(days=R.GIORNI_OFFERTA_PRIMA)).isoformat()
    hi = (fine + dt.timedelta(days=R.GIORNI_OFFERTA_DOPO)).isoformat()
    finestra = [x for x in dep if lo <= x[0] <= hi]
    candidati = []
    otto = SV.scegli_8k(finestra, ("2.01", "5.01", "8.01"))
    if otto:
        candidati.append(otto)
    for forma in R.FORME_OFFERTA:
        candidati += [x for x in reversed(finestra) if x[1] == forma][:1]
    for _data, _forma, _voci, acc, doc in candidati:
        if not doc:
            continue
        url = SV.url_documento(cik, acc, doc)
        if not SV.in_cache(url) and bulk.liberi() < bulk.SOGLIA_LIBERI:
            #  Soglia degli 8 GB (ADR-046): ci si ferma, non si ripiega sull'ultimo prezzo in silenzio.
            raise SystemExit("meno di 8 GB liberi su C: prima di scaricare {}: fermo".format(url))
        testo = SV.leggi_cache(url) if SV.in_cache(url) else budget.get(url)
        if not testo:
            continue
        esito, prezzo, _citazione = SV.leggi_deal(SV.testo(testo))
        if esito == "CONTANTI" and prezzo:
            return prezzo
    return None


# ------------------------------------------------------------------------------------------------ rendimenti ---
def main() -> int:
    import rendimenti as R                               # backtest/russell_exits/rendimenti.py
    import serie_eodhd as SE
    ids = C.ids()
    last = len(ids) - 1
    casi = {x["cik"]: x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8"))}
    peer = [p for p in csv.DictReader((C.STATO / "peer.csv").open(encoding="utf-8"))]
    conta_peer = collections.Counter((p["ingresso"], p["esito"]) for p in peer)
    ok = [p for p in peer if p["esito"] == "ok"]
    offerte: dict[tuple, float | None] = {}
    budget = C.budget()

    def offerta_di(t, fine):
        chiave = (t.get("cik"), ids[fine])
        if chiave not in offerte:
            offerte[chiave] = offerta(t.get("cik"), ids[fine], budget)
        return offerte[chiave]

    righe = []
    #  A gruppi, per tenere bassa la memoria: le serie di un gruppo si liberano prima del successivo.
    for gruppo in (("B", "A", "C"), ("forte",), ("base",)):
        sel = [p for p in ok if p["ingresso"] in gruppo]
        codici = {casi[p["cik"]]["codice"] for p in sel} | {v["codice"] for p in sel for v in json.loads(p["peer"])}
        SE._cache.clear()
        SE.carica(codici, ids)
        seguite = {c: SE.serie_seguita(c, ids)[0] for c in codici}
        serie = seguite.get
        for p in sel:
            x = casi[p["cik"]]
            s = bisect.bisect_left(ids, p["data_ingresso"])
            caso = {"cik": x["cik"], "codice": x["codice"]}
            pp = [{"cik": v["cik"], "codice": v["codice"]} for v in json.loads(p["peer"])]
            finestre = [(str(h), s, s + h) for h in ORIZZONTI]
            if p["ingresso"] != "base":
                finestre.append(("placebo", s + PLACEBO_SPOSTAMENTO, s + PLACEBO_SPOSTAMENTO + PLACEBO_ORIZZONTE))
            for nome, a, b in finestre:
                extra, esito, n = R.rendimento_extra(caso, pp, a, b, last, serie, offerta_di)
                righe.append({"cik": x["cik"], "nome": x["nome"], "anno": x["anno"], "gruppo": x["gruppo"],
                              "ingresso": p["ingresso"], "data_ingresso": p["data_ingresso"], "finestra": nome,
                              "extra": "" if extra is None else round(extra, 6), "esito": esito, "peer_con_prezzo": n})
        print("gruppo", gruppo, "fatto:", len(sel), "richieste", flush=True)
    with RIGHE.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)

    # ---------------------------------------------------------------------------------------------- celle ---
    def cella(ingresso, finestra, anni=None):
        per = collections.defaultdict(list)
        for r in righe:
            if r["ingresso"] == ingresso and r["finestra"] == finestra and r["extra"] != "" \
                    and (anni is None or int(r["anno"]) in anni):
                per[int(r["anno"])].append(float(r["extra"]))
        return statistiche(per)

    celle = {}
    for ing in ("A", "B", "C", "forte", "base"):
        for fin in [str(h) for h in ORIZZONTI] + (["placebo"] if ing != "base" else []):
            celle["{} × {}".format(ing, fin)] = cella(ing, fin)
    bolla = {"{} × 252, coorte 2020-2021".format(ing): cella(ing, "252", BOLLA) for ing in ("B", "forte", "base")}
    esiti = collections.defaultdict(collections.Counter)
    for r in righe:
        esiti["{} × {}".format(r["ingresso"], r["finestra"])][r["esito"] if r["extra"] != "" else "fuori: " + r["esito"]] += 1
    verdetti = {}
    for domanda, (ing, h) in VERDETTI.items():
        v, criteri = verdetto(celle["{} × {}".format(ing, h)], celle["{} × placebo".format(ing)])
        verdetti[domanda] = {"cella": "{} × {}".format(ing, h), "esito": v, "criteri": criteri}

    # ---------------------------------------------------------------------------------- finestre descrittive ---
    import casi as K
    SE._cache.clear()
    rotte = [x for x in casi.values() if x["gruppo"] == "rotta" and x["ingresso_B"]]
    SE.carica({x["codice"] for x in rotte}, ids)
    in_cella = {r["cik"] for r in righe if r["ingresso"] == "B" and r["finestra"] == "252" and r["extra"] != ""}
    fin_descr = collections.defaultdict(lambda: collections.defaultdict(list))
    for x in rotte:
        ser, _ = SE.serie_seguita(x["codice"], ids)
        if ser is None:
            continue
        close = ser[0]
        s = bisect.bisect_left(ids, x["S"])
        b = bisect.bisect_left(ids, x["ingresso_B"])
        off = float(x["prezzo"]) / K.fattore_dopo(ser[3], x["prima_barra"])
        punti = [off, R.ultimo_prima(close, s - 10), R.ultimo_prima(close, s + 10), R.ultimo_prima(close, b)]
        nomi = ("collocamento → S − 10", "S − 10 → S + 10", "S + 10 → ingresso B")
        for i, nome in enumerate(nomi):
            if punti[i] and punti[i + 1]:
                v = punti[i + 1] / punti[i] - 1.0
                fin_descr["tutte le rotte con un ingresso B"][nome].append(v)
                if x["cik"] in in_cella:
                    fin_descr["rotte della cella del verdetto"][nome].append(v)
    finestre_out = {pop: {n: {"casi": len(v), "mediana": statistics.median(v), "media": statistics.fmean(v)}
                          for n, v in d.items() if v} for pop, d in fin_descr.items()}

    # ------------------------------------------------------------------------------------------------ insider ---
    cella_b = [r for r in righe if r["ingresso"] == "B" and r["finestra"] == "252" and r["extra"] != ""]
    fin_ins = {r["cik"]: (casi[r["cik"]]["data_collocamento"], casi[r["cik"]]["S"], r["data_ingresso"])
               for r in cella_b}
    ins = insider(fin_ins)
    gruppi_ins = collections.defaultdict(list)
    for r in cella_b:
        d = ins[r["cik"]]
        g = "senza dati Form 4" if not d["depositi"] else ("con vendite" if d["vendite"] else "senza vendite")
        gruppi_ins[g].append((r["nome"], float(r["extra"]), d["vendite"]))
    insider_out = {g: {"casi": len(v), "mediana": statistics.median([e for _n, e, _v in v]),
                       "media": statistics.fmean([e for _n, e, _v in v]),
                       "nomi": [(n, round(e, 4), k) for n, e, k in sorted(v, key=lambda t: t[1])]}
                   for g, v in gruppi_ins.items()}

    stato = json.loads(C.CALLS.read_text(encoding="utf-8"))
    out = {"verdetti": verdetti, "celle": celle, "coorte_2020_2021": bolla, "esiti": esiti,
           "peer": {"{} {}".format(*k): v for k, v in sorted(conta_peer.items())},
           "finestre_descrittive": finestre_out, "insider": insider_out,
           "cella_verdetto_1": [{"nome": r["nome"], "anno": r["anno"], "ingresso": r["data_ingresso"],
                                 "extra": r["extra"], "esito": r["esito"]} for r in cella_b],
           "chiamate_edgar": stato, "offerte_trovate": sum(1 for v in offerte.values() if v),
           "offerte_cercate": len(offerte)}
    C.RISULTATI.mkdir(exist_ok=True)
    JSON.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    for d, v in verdetti.items():
        print(d, v["cella"], v["esito"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
