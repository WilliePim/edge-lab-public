"""Russell 2000, uscite verso il basso — casi, esclusioni, filtri, peer, ingressi e conteggi (fermata 1).

Pre-registrazione `2026-09-16_preregistrazione.md`. Con `--conteggi` nessun rendimento extra è calcolato: si usano solo
prezzi e volumi fino al Rank Day (terzile, capitalizzazione, volume di riferimento) e le regole d'ingresso.

**Le tre decisioni prese dopo la pre-registrazione, e dove stanno** (§9: «da rifare dopo le decisioni dell'utente sulla
definizione, sul 2024 e sulla fonte dei prezzi»):
- **definizione delle uscite** (ADR-039, addendum 1): assente o al massimo il 50% delle azioni di marzo rettificate, e
  non in IWB, con l'abbinamento per emittente. Si usa `falsi_positivi.Anno.classe`, cioè lo stesso classificatore
  validato contro le liste ufficiali FTSE Russell: i casi sono esattamente quelli che hanno passato il controllo;
- **istantanea «dopo»** del 30 settembre per il 2019 e il 2024 (il 30 giugno cade di domenica, zero sedute dopo la
  ricostituzione); per quegli anni gli eventi societari della fase 1 contano fino al 30 settembre (decisione del
  22-09-2026, addendum del 21-09);
- **prezzi e identità dall'archivio EODHD** (ADR-040) tramite `serie_eodhd.py` e `identita_eodhd.csv`, letti solo
  con `market_data.api`. Yahoo non conserva i delistati: fra le uscite del 2015-2018 l'identità risolta passa dal
  23-32% all'89-95%.

Riuso: calendario delle sedute di IWM (`step1_analysis.IDS`), `survival.submissions`/`TERM`/`ACQ` (depositi in cache),
`filtri_xbrl.py`, `ingressi.py`, `verifica_identita.Serie`. Chiamate EDGAR solo per depositi e companyfacts mancanti,
sul tetto di `sec.py` (3.000 per tutto il Russell).

    python backtest/russell_exits/analisi.py --conteggi
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import json
import math
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", HERE):
    sys.path.insert(0, str(p))

import falsi_positivi as FP  # noqa: E402
import filtri_xbrl as F  # noqa: E402
import identita as I  # noqa: E402
import ingressi as G  # noqa: E402
import scarica_ohlcv as O  # noqa: E402
import sec  # noqa: E402
import rendimenti as R  # noqa: E402
import serie_eodhd as E  # noqa: E402
import step1_analysis as S1  # noqa: E402
import survival as SV  # noqa: E402
import verifica_identita as V  # noqa: E402

STATE = ROOT / "state" / "backfill" / "russell"
HOLD = STATE / "holdings"
OUT = HERE / "risultati"
IDS = S1.IDS
LAST = len(IDS) - 1
ANNI = range(2015, 2026)
TETTO_EDGAR = 3000
PREZZI_MIN = 0.8
SEDUTE_RENDIMENTO_PRIMA = 126
ORIZZONTI = (63, 126, 252)
INGRESSI_NOMI = ("A", "B1", "B2", "B3", "C")
N_PEER, MIN_PEER = 5, 3
#  Per quali anni la definizione delle uscite è stata confrontata con la lista ufficiale FTSE Russell delle
#  cancellazioni (`falsi_positivi_ricalcolati.md`). 2018 e 2020 non hanno una lista finale pubblica; il 2019
#  nemmeno, e serve solo a costruire il campione (decisione dell'utente del 22-09-2026).
VERIFICA_LISTA = {2016: "sì", 2017: "sì", 2021: "sì", 2022: "sì", 2023: "sì", 2024: "sì (istantanea di settembre)",
                  2025: "sì", 2015: "no: lista non cercata", 2018: "no: nessuna lista", 2019: "no: nessuna lista",
                  2020: "no: solo l'aggiornamento del 19 giugno"}
ALTRE_FUSIONE = frozenset({"PREM14A", "PREM14C"})
FINESTRE_DICEMBRE = (("anticipo", "k", "p"), ("vendita", "p", "r"), ("coda", "r", "r13"), ("recupero", "r13", "r32"))


# ------------------------------------------------------------------- date --
def date_anni():
    out = {}
    with (HERE / "date_ricostituzione.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["anno"].isdigit():
                out[int(r["anno"])] = {"k": IDS.index(r["rank_day"]), "p": IDS.index(r["liste_preliminari"]),
                                       "r": IDS.index(r["ricostituzione"]), "stato": r["stato_fonte"]}
    return out


def sessione_le(giorno):
    return bisect.bisect_right(IDS, giorno) - 1


# ----------------------------------------------------------------- EDGAR --
class Sec:
    """Depositi e companyfacts da EDGAR (cache del repo, poi rete sul tetto). In memoria restano solo i risultati:
    SIC e i depositi dei moduli usati; i filtri XBRL già calcolati per tutti i Rank Day (un companyfacts pesa decine
    di MB e si scarta subito)."""

    MODULI = SV.TERM | SV.ACQ | ALTRE_FUSIONE

    def __init__(self, rank_days):
        self.b = sec.Budget(tetto=TETTO_EDGAR)
        self.rank_days = rank_days                 # {anno: data ISO}
        self._sub, self._filtri = {}, {}

    def depositi(self, cik):
        """({"sic": …} o None, [(data, modulo, voci)]) con i soli moduli di interesse e gli 8-K con voce 1.03."""
        if cik not in self._sub:
            url = SV.SUB + "CIK{:010d}.json".format(int(cik))
            if not SV.in_cache(url):
                self.b.get(url)
            d, dep = SV.submissions(cik)
            if d:
                for f in (d.get("filings") or {}).get("files") or []:
                    if f.get("filingFrom", "9999") <= "2025-12-31" and f.get("filingTo", "0000") >= "2014-01-01"                             and not SV.in_cache(SV.SUB + f["name"]):
                        self.b.get(SV.SUB + f["name"])
                d, dep = SV.submissions(cik)
            info = {"sic": str((d or {}).get("sic") or "").strip()} if d else None
            ridotti = [(z[0], z[1], z[2]) for z in dep if z[1] in self.MODULI or (z[1].startswith("8-K") and "1.03" in z[2])]
            self._sub[cik] = (info, ridotti)
        return self._sub[cik]

    def filtri(self, cik, splits):
        """{anno: {"f1": …, "f2": …, "f3": …}} per tutti i Rank Day."""
        if cik not in self._filtri:
            txt = self.b.get("https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json".format(int(cik)))
            try:
                cf = json.loads(txt) if txt else None
            except ValueError:
                cf = None
            out = {}
            for anno, rif in self.rank_days.items():
                if cf is None:
                    out[anno] = {k: (None, "companyfacts assenti") for k in ("f1", "f2", "f3")}
                else:
                    out[anno] = {"f1": F.f1_flusso_cassa(cf, rif), "f2": F.f2_leva(cf, rif),
                                 "f3": F.f3_azioni(cf, rif, fattore_split(splits))}
            self._filtri[cik] = out
            del cf, txt
        return self._filtri[cik]


# ----------------------------------------------------------------- serie --
_serie = {}


def allineata(codice, man=None):
    """(close, adj, vol, split, ultima data) dall'archivio EODHD, allineati al calendario (NaN dove manca), o None.

    `man` resta per compatibilità con le chiamate vecchie e non serve piu': le serie non vengono dai file Yahoo."""
    return E.serie(codice)


def _c(x):
    return x is not None and x == x


def come_lista(arr):
    return [x if x == x else None for x in arr]


def ultimo_prima(xs, s, stale=5):
    for i in range(s, max(-1, s - stale - 1), -1):
        if 0 <= i < len(xs) and _c(xs[i]):
            return xs[i]
    return None


def copertura(xs, a, b):
    parte = xs[max(0, a):b + 1]
    return sum(1 for x in parte if _c(x)) / max(1, len(parte))


def fattore_split(splits):
    def f(a, b):
        out = 1.0
        for d, s in splits:
            if a < d <= b:
                out *= s
        return out
    return f


# ----------------------------------------------------------------- casi --
def chiave_membro(r):
    return r["cusip"] if r.get("cusip") else "N:" + I.norm(r.get("titolo") or r["nome"])


def leggi_identita():
    """{istantanea: righe} della verifica d'identità sui prezzi EODHD (`verifica_identita_eodhd.py`)."""
    per = collections.defaultdict(list)
    with (STATE / "identita_eodhd.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            per[r["istantanea"]].append(r)
    return per


def leggi_holdings(chiave):
    p = HOLD / "{}.csv".format(chiave)
    if not p.exists():
        return None
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fine_eventi(anno, r):
    """Fin dove contano gli eventi societari della fase 1: la ricostituzione, o l'istantanea «dopo» dove e' stata
    spostata a settembre (2019, 2024: decisione dell'utente del 22-09-2026)."""
    dopo = FP.ISTANTANEA_DOPO.get(anno)
    return max(IDS[r], dopo[0]) if dopo else IDS[r]


def valuta_titolo(x, anno, d, man, s_ec, motivi):
    """Esclusioni e filtri di un titolo (uscita o rimasto). Aggiorna x; ritorna True se resta."""
    k, p, r = d["k"], d["p"], d["r"]
    if x["esito_identita"] == "NON_VERIFICATA":
        x["esclusione"] = "identità: " + (x["motivo_identita"] or "non verificata")
        return False
    ser = allineata(x["codice"])
    fine_serie = ser[4] if ser else None
    dep_d, dep = s_ec.depositi(x["cik"])
    lo, hi = "{}-03-31".format(anno), fine_eventi(anno, r)
    nel = [z for z in dep if lo < z[0] <= hi]
    term = [z for z in nel if z[1] in SV.TERM]
    acq = [z for z in nel if z[1] in SV.ACQ or z[1] in ALTRE_FUSIONE]
    fall = [z for z in nel if z[1].startswith("8-K") and "1.03" in z[2]]
    if fine_serie and r + 5 <= LAST and fine_serie < IDS[r + 5]:
        x["esclusione"] = "acquisita, in fusione o delistata nel trimestre: serie finita il {}".format(fine_serie)
        return False
    if term or acq or fall:
        forme = sorted({z[1] for z in term + acq} | ({"8-K 1.03"} if fall else set()))
        x["esclusione"] = "acquisita, in fusione o delistata nel trimestre: " + ", ".join(forme)
        return False
    if ser is None or copertura(ser[0], k - SEDUTE_RENDIMENTO_PRIMA, r) < PREZZI_MIN or \
            copertura(ser[2], k - SEDUTE_RENDIMENTO_PRIMA, r) < PREZZI_MIN:
        x["esclusione"] = "prezzi e volumi insufficienti"
        return False
    close, adj, vol, splits, _ = ser
    a_k, a_0 = ultimo_prima(adj, k), ultimo_prima(adj, k - SEDUTE_RENDIMENTO_PRIMA)
    c_k, c_m = ultimo_prima(close, k), ultimo_prima(close, sessione_le("{}-03-31".format(anno)))
    if not (a_k and a_0 and c_k and c_m):
        x["esclusione"] = "prezzi e volumi insufficienti"
        return False
    x["rend_6m"] = a_k / a_0 - 1.0
    x["cap"] = float(x["valore"]) * c_k / c_m
    sic = (dep_d or {}).get("sic") or ""
    x["sic"] = sic
    if sic == "6770":
        x["esclusione"] = "SPAC (SIC 6770)"
        return False
    # ---- filtri
    ff = s_ec.filtri(x["cik"], splits)[anno]
    f1, f2, f3 = ff["f1"], ff["f2"], ff["f3"]
    lista = IDS[p]
    fus = [z for z in dep if (date.fromisoformat(lista) - timedelta(days=365)).isoformat() <= z[0] <= lista
           and (z[1] in SV.ACQ or z[1] in ALTRE_FUSIONE)]
    f4 = ((not fus), "annunci: " + ", ".join(sorted({z[1] for z in fus}))) if dep_d else (None, "depositi assenti")
    x["filtri"] = {"f1": f1, "f2": f2, "f3": f3, "f4": f4}
    for nome, (esito, _nota) in x["filtri"].items():
        motivi[nome][{True: "passa", False: "non passa", None: "non verificabile"}[esito]] += 1
    if all(v[0] is True for v in x["filtri"].values()):
        return True
    x["esclusione"] = "filtri: " + ", ".join("{} {}".format(n, "non verificabile" if v[0] is None else "non passa")
                                              for n, v in x["filtri"].items() if v[0] is not True)
    return False


def motivo_breve(e):
    if e.startswith("identità"):
        return e                                   # il motivo dell'identità resta intero
    return "filtri" if e.startswith("filtri") else e.split(":")[0]


def migliaia(v):
    return "{:,.0f}".format(v).replace(",", ".")


def terzile(v, tagli):
    return 0 if v <= tagli[0] else (1 if v <= tagli[1] else 2)


def peer_di(x, universo, esclusi):
    cand = [u for u in universo if u["terzile"] == x["terzile"] and u["cik"] not in esclusi and u["cik"] != x["cik"]]
    cand.sort(key=lambda u: (abs(math.log(u["cap"]) - math.log(x["cap"])), int(u["cik"])))
    return cand[:N_PEER]


# ------------------------------------------------------------------ main --
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--conteggi", action="store_true", help="nessun rendimento extra")
    ap.add_argument("--verdetto", action="store_true",
                    help="rendimenti extra e verdetto, dopo la conferma della fermata 1 (22-09-2026)")
    ap.add_argument("--anni", nargs="*", type=int, help="solo questi anni (prove); il conteggio ufficiale li usa tutti")
    a = ap.parse_args()
    if not (a.conteggi or a.verdetto):
        raise SystemExit("scegliere --conteggi (fermata 1) o --verdetto (dopo la conferma della fermata 1)")
    OUT.mkdir(parents=True, exist_ok=True)
    date_y = date_anni()
    man = json.loads(O.MANIFEST.read_text(encoding="utf-8"))
    ident = leggi_identita()
    s_ec = Sec({a_: IDS[v["k"]] for a_, v in date_y.items()})
    tab = collections.OrderedDict()
    casi_tutti, placebo_tutti, esempio, tutte, persi = [], [], None, [], []
    for anno in (a.anni or ANNI):
        d = date_y[anno]
        m_ch = "IWM_{}-03-31".format(anno)
        t = collections.Counter()
        motivi_usc = collections.Counter()
        motivi_rim = collections.Counter()
        filtri_usc = collections.defaultdict(collections.Counter)
        filtri_rim = collections.defaultdict(collections.Counter)
        M = ident.get(m_ch)
        try:
            A = FP.Anno(anno)                 # il classificatore validato contro le liste ufficiali FTSE Russell
        except FileNotFoundError as e:
            A = None
            mancante = str(e)
        if not M or A is None:
            tab[anno] = {"stato": "istantanea mancante: " + (m_ch if not M else mancante)}
            print(anno, tab[anno]["stato"], flush=True)
            continue
        #  Più righe della stessa società (classi di azioni) valgono come una sola, e la società esce solo se escono
        #  tutte (§3). Il gruppo è il CIK dell'identità verificata; senza identità, la riga da sola.
        per_cik = collections.OrderedDict()
        for r in M:
            per_cik.setdefault(r["cik"] or ("?" + FP.chiave(r)), []).append(r)
        uscite, rimasti = [], []
        for chiave, righe in per_cik.items():
            stati = [A.classe(FP.chiave(r), per_emittente=True)[0] if FP.chiave(r) in A.az_m else None for r in righe]
            if "alto" in stati:
                direzione = "alto"
            elif stati and all(st == "basso" for st in stati):
                direzione = "basso"
            elif any(st is None for st in stati):
                direzione = None
            else:
                direzione = "rimasto"
            r0 = max(righe, key=lambda r: float(r["valore"] or 0))
            x = {"anno": anno, "cik": r0["cik"], "codice": r0["codice_eodhd"], "ticker": r0["codice_eodhd"],
                 "nome": r0["titolo"] or r0["nome"],
                 "valore": sum(float(r["valore"] or 0) for r in righe), "esito_identita": r0["esito"],
                 "motivo_identita": r0["motivo"], "esclusione": "", "filtri": {}, "rend_6m": None, "cap": None, "sic": ""}
            if direzione == "rimasto":
                t["rimasti"] += 1
                rimasti.append(x)
            elif direzione == "alto":
                t["uscite verso l'alto (in IWB)"] += 1
                x["direzione"] = "alto"
                tutte.append(x)
            elif direzione == "basso":
                t["uscite verso il basso"] += 1
                x["direzione"] = "basso"
                uscite.append(x)
                tutte.append(x)
            else:
                t["non classificabili (quota residua non calcolabile)"] += 1
        E.carica([x["codice"] for x in uscite + rimasti if x["codice"]], IDS)
        for x in uscite:
            if valuta_titolo(x, anno, d, man, s_ec, filtri_usc):
                t["uscite dopo esclusioni e filtri"] += 1
            else:
                motivi_usc[motivo_breve(x["esclusione"])] += 1
        #  Copertura, nell'ordine delle esclusioni del §3: identità, poi eventi societari, poi prezzi e volumi.
        con_id = [x for x in uscite if not x["esclusione"].startswith("identità")]
        dopo_eventi = [x for x in con_id if not x["esclusione"].startswith("acquisita")]
        con_prezzi = [x for x in dopo_eventi if not x["esclusione"].startswith("prezzi e volumi")]
        t["uscite con identità verificata (EODHD)"] = len(con_id)
        t["uscite dopo gli eventi societari della fase 1"] = len(dopo_eventi)
        t["uscite con prezzi e volumi sufficienti"] = len(con_prezzi)
        #  Per la riga descrittiva del referto: uscite perse perché mancano i prezzi, con la fascia di grandezza
        #  (terzili del valore della posizione di IWM a marzo fra le uscite dell'anno).
        tagli_val = statistics.quantiles([x["valore"] for x in uscite], n=3) if len(uscite) >= 3 else None
        for x in uscite:
            e_ = x["esclusione"]
            if e_.startswith("prezzi e volumi") or e_ == "identità: NESSUN_PREZZO_EODHD":
                fascia = ("bassa", "media", "alta")[terzile(x["valore"], tagli_val)] if tagli_val else "—"
                persi.append({"anno": anno, "codice": x["codice"], "motivo": motivo_breve(e_), "fascia": fascia})
        universo = []
        for i_r, x in enumerate(rimasti):
            if i_r % 250 == 0:
                print("  {} rimasti valutati {}/{} | chiamate EDGAR {}".format(anno, i_r, len(rimasti), s_ec.b.usate), flush=True)
            if valuta_titolo(x, anno, d, man, s_ec, filtri_rim):
                universo.append(x)
            else:
                motivi_rim[motivo_breve(x["esclusione"])] += 1
        t["rimasti dopo esclusioni e filtri (universo dei peer)"] = len(universo)
        buone = [x for x in uscite if not x["esclusione"]]
        if len(universo) >= 3:
            tagli = statistics.quantiles([u["rend_6m"] for u in universo], n=3)
            for u in universo + buone:
                u["terzile"] = terzile(u["rend_6m"], tagli)
        usati = set()
        for x in buone:
            x["peer"] = peer_di(x, universo, set())
            usati.update(u["cik"] for u in x["peer"])
            if len(x["peer"]) < MIN_PEER:
                x["esclusione"] = "meno di {} peer".format(MIN_PEER)
        buone = [x for x in buone if not x["esclusione"]]
        t["uscite con almeno {} peer".format(MIN_PEER)] = len(buone)
        # ---- placebo: rimasti con la capitalizzazione più bassa, non usati come peer
        cand_pl = sorted((u for u in universo if u["cik"] not in usati), key=lambda u: (u["cap"], int(u["cik"])))
        placebo = cand_pl[:len(buone)]
        esclusi_pl = {u["cik"] for u in placebo}
        for u in placebo:
            u["peer"] = peer_di(u, universo, esclusi_pl)
        t["falsi eventi (placebo)"] = sum(1 for u in placebo if len(u["peer"]) >= MIN_PEER)
        # ---- ingressi
        for x in buone + placebo:
            close, _adj, vol, _s, _f = allineata(x["codice"])
            x["ingressi"] = G.ingressi(come_lista(close), come_lista(vol), d["k"], d["p"], d["r"])
        for x in buone:
            x["anno"] = anno
        casi_tutti += buone
        placebo_tutti += placebo
        if esempio is None and anno == 2023 and buone:
            esempio = sorted(buone, key=lambda x: x["cap"])[len(buone) // 2]
        tab[anno] = {"stato": "ok", "date": {n: IDS[d[n]] for n in ("k", "p", "r")}, "conteggi": dict(t),
                     "esclusioni_uscite": dict(motivi_usc), "esclusioni_rimasti": dict(motivi_rim),
                     "filtri_uscite": {k: dict(v) for k, v in filtri_usc.items()},
                     "filtri_rimasti": {k: dict(v) for k, v in filtri_rim.items()}}
        print(anno, dict(t), "| chiamate EDGAR", s_ec.b.usate, flush=True)
    with (OUT / "uscite_tutte.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["anno", "direzione", "cik", "ticker", "nome", "esito_identita", "motivo_identita",
                                           "esclusione", "sic", "cap", "rend_6m"], extrasaction="ignore")
        w.writeheader()
        w.writerows(tutte)
    scrivi_conteggi(tab, casi_tutti, placebo_tutti, esempio, date_y, s_ec)
    if a.verdetto:
        scrivi_verdetto(casi_tutti, placebo_tutti, date_y, persi, s_ec)
    return 0


# --------------------------------------------------------------------------------------------- verdetto --
def _offerte():
    """Il prezzo dell'offerta in contanti di un titolo delistato, dai documenti già in cache (§5), una volta sola."""
    memo = {}

    def offerta(t, fine):
        chiave = (t.get("cik"), fine)
        if chiave not in memo:
            memo[chiave] = R.offerta_in_cache(t.get("cik"), IDS[fine])
        return memo[chiave]
    return offerta


def celle_rendimenti(casi, placebo, date_y):
    """{cella: (statistiche, esiti)}. Celle del verdetto, loro placebo, e le descrittive (§7, §8)."""
    offerta = _offerte()
    fuori = {}

    def cella(nome, elementi, finestra):
        per_anno = collections.defaultdict(list)
        esiti = collections.Counter()
        for x in elementi:
            s, e = finestra(x)
            if s is None:
                esiti["ingresso non decidibile"] += 1
                continue
            v, esito, _n = R.rendimento_extra(x, x["peer"], s, e, LAST, E.serie, offerta)
            esiti[esito] += 1
            if v is not None:
                per_anno[x["anno"]].append(v)
        fuori[nome] = (R.statistiche(per_anno), dict(esiti))

    def r_(x):
        return date_y[x["anno"]]["r"]

    #  le due celle del verdetto e i loro placebo (§1, tabella)
    cella("VERDETTO investimento: B2 × 252", casi,
          lambda x: (x["ingressi"]["B2"][0], x["ingressi"]["B2"][0] + 252 if x["ingressi"]["B2"][0] is not None else None))
    cella("PLACEBO investimento: falsi eventi, B2 × 252", placebo,
          lambda x: (x["ingressi"]["B2"][0], x["ingressi"]["B2"][0] + 252 if x["ingressi"]["B2"][0] is not None else None))
    cella("VERDETTO scheda di dicembre: A × 32", casi, lambda x: (r_(x), r_(x) + 32))
    cella("PLACEBO scheda di dicembre: finestra spostata di 63 sedute", casi, lambda x: (r_(x) + 63, r_(x) + 95))
    #  descrittive
    for nome in INGRESSI_NOMI:
        for h in ORIZZONTI:
            cella("{} × {}".format(nome, h), casi,
                  lambda x, n=nome, h=h: (x["ingressi"][n][0], x["ingressi"][n][0] + h if x["ingressi"][n][0] is not None else None))
    for nome, a_, b_ in FINESTRE_DICEMBRE:
        def fin(x, a_=a_, b_=b_):
            d = date_y[x["anno"]]
            pos = {"k": d["k"], "p": d["p"], "r": d["r"], "r13": d["r"] + 13, "r32": d["r"] + 32}
            return pos[a_], pos[b_]
        cella("dicembre: " + nome, casi, fin)

    #  approssimazione di dicembre (§8, descrittiva): a −30% o peggio all'ultima seduta di ottobre dall'ultima
    #  seduta dell'anno prima; dal secondo venerdì di dicembre all'ultima seduta di gennaio dopo
    def approssimazione(x):
        anno = x["anno"]
        ser = E.serie(x["codice"])
        i_ott = R.ultima_seduta_entro(IDS, "{}-10-31".format(anno))
        i_dic = R.ultima_seduta_entro(IDS, "{}-12-31".format(anno - 1))
        if ser is None or i_ott is None or i_dic is None:
            return False
        a_ott, a_dic = R.ultimo_prima(ser[1], i_ott), R.ultimo_prima(ser[1], i_dic)
        return bool(a_ott and a_dic and a_ott / a_dic - 1.0 <= -0.30)

    def fin_appross(x):
        s = R.prima_seduta_da(IDS, R.secondo_venerdi_di_dicembre(x["anno"]))
        e = R.ultima_seduta_entro(IDS, "{}-01-31".format(x["anno"] + 1))
        return (s, e) if s is not None and e is not None else (None, None)
    cella("approssimazione di dicembre", [x for x in casi if approssimazione(x)], fin_appross)
    return fuori


def _f(x, pct=True, dec=1):
    if x is None:
        return "—"
    return ("{:+.%df}%%" % dec).format(100 * x) if pct else ("{:.%df}" % dec).format(x)


def _git(*argomenti):
    import subprocess
    try:
        return subprocess.run(["git", *argomenti], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def scrivi_verdetto(casi, placebo, date_y, persi, s_ec):
    celle = celle_rendimenti(casi, placebo, date_y)
    esiti_v = {}
    for domanda, cv, cp in (("1. Investimento", "VERDETTO investimento: B2 × 252", "PLACEBO investimento: falsi eventi, B2 × 252"),
                            ("2. Scheda di dicembre", "VERDETTO scheda di dicembre: A × 32",
                             "PLACEBO scheda di dicembre: finestra spostata di 63 sedute")):
        esito, criteri = R.verdetto(celle[cv][0], celle[cp][0])
        esiti_v[domanda] = (esito, criteri, cv, cp)

    prereg = _git("log", "-1", "--format=%h %ad", "--date=short", "--", "backtest/russell_exits/2026-09-16_preregistrazione.md")
    codice = _git("rev-parse", "--short", "HEAD")
    sporco = _git("status", "--porcelain", "--", "backtest/russell_exits/*.py", "backtest/rematch_50_300m/survival.py")
    L = ["# Russell 2000, uscite verso il basso — referto del verdetto", "",
         "Generato da `python backtest/russell_exits/analisi.py --verdetto`. Pre-registrazione "
         "`2026-09-16_preregistrazione.md` (ultimo commit {}), addenda del 21 e 22 settembre, decisioni ADR-039, 040, "
         "071-075. Codice al commit `{}`{}.".format(prereg, codice, ", **con modifiche non committate**" if sporco else ""),
         "", "**Il verdetto si legge solo sulle due celle pre-registrate.** Tutto il resto è descrittivo e non decide "
         "niente.", "", "## Verdetti", "",
         "| domanda | cella | casi | anni | mediana | media delle medie annuali | t (gradi) | 2015-19 | 2020-25 | placebo: media, t | **esito** |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for domanda, (esito, _criteri, cv, cp) in esiti_v.items():
        st, pl = celle[cv][0], celle[cp][0]
        sub = st.get("sottoperiodi", {})
        L.append("| {} | {} | {} | {} | {} | {} | {} ({}) | {} | {} | {}, t {} | **{}** |".format(
            domanda, cv.split(": ", 1)[1], st["casi"], st["anni"], _f(st["mediana"]), _f(st["media_delle_medie"]),
            _f(st["t"], pct=False, dec=2), st["gradi"] if st["gradi"] is not None else "—",
            _f((sub.get("2015-2019") or {}).get("media_delle_medie")), _f((sub.get("2020-2025") or {}).get("media_delle_medie")),
            _f(pl["media_delle_medie"]), _f(pl["t"], pct=False, dec=2), esito))
    for domanda, (esito, criteri, _cv, _cp) in esiti_v.items():
        L += ["", "**{} — {}.** Criteri del §1, nell'ordine:".format(domanda, esito), ""]
        L += ["- {} {}".format("vero —" if ok else "**falso** —", c) for c, ok in criteri.items()]

    L += ["", "## Medie per anno, celle del verdetto", "",
          "| anno | investimento: casi | media | placebo falsi eventi: casi | media | dicembre: casi | media | placebo dicembre: casi | media |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    nomi = ["VERDETTO investimento: B2 × 252", "PLACEBO investimento: falsi eventi, B2 × 252",
            "VERDETTO scheda di dicembre: A × 32", "PLACEBO scheda di dicembre: finestra spostata di 63 sedute"]
    anni = sorted({a for n in nomi for a in celle[n][0]["medie_per_anno"]})
    for a in anni:
        riga = ["{}".format(a)]
        for n in nomi:
            st = celle[n][0]
            riga += [str(st["casi_per_anno"].get(a, 0)), _f(st["medie_per_anno"].get(a))]
        L.append("| " + " | ".join(riga) + " |")

    L += ["", "## Chi è fuori dalle celle del verdetto, e come sono trattati i delistati", "",
          "| cella | completo | delistato: ultimo prezzo | delistato: offerta in contanti | fuori: finestra oltre i dati | "
          "fuori: senza prezzo all'ingresso | fuori: buco all'uscita | fuori: meno di 3 peer | ingresso non decidibile |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for n in nomi:
        es = celle[n][1]
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            n, es.get("completo", 0), es.get("delistato: ultimo prezzo", 0), es.get("delistato: prezzo dell'offerta", 0),
            es.get("finestra oltre i dati", 0), es.get("senza prezzo all'ingresso", 0), es.get("buco all'uscita", 0),
            es.get("meno di 3 peer con prezzo", 0), es.get("ingresso non decidibile", 0)))

    #  la riga sui casi persi per prezzi mancanti (descrittiva, senza rendimenti)
    mercato = E.mercati()
    per_mercato = collections.Counter(mercato.get(x["codice"], "senza codice EODHD") if x["codice"] else "senza codice EODHD"
                                      for x in persi)
    per_fascia = collections.Counter(x["fascia"] for x in persi)
    per_anno_p = collections.Counter(x["anno"] for x in persi)
    L += ["", "## Casi persi per prezzi mancanti (descrittivo, nessun rendimento)", "",
          "{} uscite verso il basso non entrano per prezzi mancanti (prezzi e volumi insufficienti, o nessun prezzo "
          "EODHD per verificare l'identità). Per anno: {}. Per mercato: {}. Per fascia di grandezza (terzili del valore "
          "della posizione di IWM a marzo fra le uscite dell'anno): {}.".format(
              len(persi), ", ".join("{} {}".format(a, n) for a, n in sorted(per_anno_p.items())),
              ", ".join("{} {}".format(m, n) for m, n in per_mercato.most_common()),
              ", ".join("{} {}".format(f, per_fascia[f]) for f in ("bassa", "media", "alta") if per_fascia[f]))]

    L += ["", "## Celle descrittive (non decidono niente)", "",
          "| cella | casi | anni | media | mediana | quota positivi | media delle medie annuali | t |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for n, (st, _es) in celle.items():
        if n.startswith(("VERDETTO", "PLACEBO")):
            continue
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            n, st["casi"], st["anni"], _f(st["media"]), _f(st["mediana"]),
            _f(st["quota_positivi"]).replace("+", "") if st["quota_positivi"] is not None else "—",
            _f(st["media_delle_medie"]), _f(st["t"], pct=False, dec=2)))
    L += ["", "Chiamate EDGAR usate: {} (tetto {}); il prezzo delle offerte si legge solo da documenti già in cache."
          .format(s_ec.b.usate, TETTO_EDGAR), ""]
    (OUT / "verdetto.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / "verdetto.json").write_text(json.dumps(
        {"verdetti": {d: {"esito": e, "criteri": c, "cella": cv, "placebo": cp} for d, (e, c, cv, cp) in esiti_v.items()},
         "celle": {n: {"statistiche": st, "esiti": es} for n, (st, es) in celle.items()},
         "persi_per_prezzi": persi, "codice": codice, "preregistrazione": prereg}, indent=1, default=str),
        encoding="utf-8")
    print("\n".join(L[:40]))


# ---------------------------------------------------------------- report --
def distribuzione_ingressi(casi, date_y):
    out = {}
    for nome, (n, lim) in G.SCAGLIONI.items():
        c = collections.Counter()
        sedute = []
        for x in casi:
            s, esito = x["ingressi"][nome]
            r = date_y[x["anno"]]["r"]
            if s is None:
                c["non decidibile: " + esito] += 1
            elif esito == "FORZATO":
                c["forzato al limite"] += 1
                sedute.append(s - r)
            elif s == r + n:
                c["primo giorno possibile"] += 1
                sedute.append(s - r)
            else:
                c["in mezzo"] += 1
                sedute.append(s - r)
        decisi = sum(v for k, v in c.items() if not k.startswith("non"))
        estremi = c["primo giorno possibile"] + c["forzato al limite"]
        quartili = statistics.quantiles(sedute, n=4) if len(sedute) >= 4 else None
        out[nome] = {"conteggi": dict(c), "mediana_sedute": statistics.median(sedute) if sedute else None,
                     "minimo": min(sedute) if sedute else None, "massimo": max(sedute) if sedute else None,
                     "quartili": [round(q, 1) for q in quartili] if quartili else None,
                     "limiti": (n, lim), "quota_estremi": estremi / decisi if decisi else None}
    return out


def disponibili(casi, date_y):
    out = {}
    for nome in INGRESSI_NOMI:
        for h in ORIZZONTI:
            anni = collections.Counter()
            for x in casi:
                s, _ = x["ingressi"][nome]
                if s is not None and s + h <= LAST:
                    anni[x["anno"]] += 1
            out["{} x {}".format(nome, h)] = {"casi": sum(anni.values()), "anni": sorted(anni)}
    for nome, a_, b_ in FINESTRE_DICEMBRE:
        anni = collections.Counter()
        for x in casi:
            dd = date_y[x["anno"]]
            pos = {"k": dd["k"], "p": dd["p"], "r": dd["r"], "r13": dd["r"] + 13, "r32": dd["r"] + 32}
            if pos[b_] <= LAST:
                anni[x["anno"]] += 1
        out["dicembre: " + nome] = {"casi": sum(anni.values()), "anni": sorted(anni)}
    return out


def pc(v):
    return "—" if v is None else "{:.1f}%".format(100 * v)


def scrivi_conteggi(tab, casi, placebo, esempio, date_y, s_ec):
    dist = distribuzione_ingressi(casi, date_y)
    disp = disponibili(casi, date_y)
    L = ["# Russell 2000, uscite verso il basso — conteggi della fermata 1", "",
         "Generato da `python backtest/russell_exits/analisi.py --conteggi`. **Nessun rendimento extra calcolato o "
         "guardato.** Chiamate EDGAR usate: {} (tetto {}).".format(s_ec.b.usate, TETTO_EDGAR), "",
         "Rifatti dopo le tre decisioni che il §9 della pre-registrazione aspettava:",
         "- **definizione** di ADR-039 (assente o ≤ 50% delle azioni di marzo, non in IWB, abbinamento per emittente), "
         "con il classificatore validato contro le liste ufficiali: nessun anno controllato sopra il 10% di falsi "
         "positivi (`falsi_positivi_ricalcolati.md`);",
         "- **istantanea «dopo» del 30 settembre** per il 2019 e il 2024, con gli eventi societari della fase 1 contati "
         "fino a quella data;",
         "- **prezzi, volumi e identità dall'archivio EODHD** (ADR-040), che conserva i delistati che Yahoo perde.", "",
         "## Casi per anno", "",
         "| anno | definizione verificata sulla lista ufficiale | uscite verso il basso | verso l'alto | dopo esclusioni e filtri | con ≥ 3 peer | rimasti | universo dei peer | falsi eventi |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for anno, v in tab.items():
        if v["stato"] != "ok":
            L.append("| {} | | {} | | | | | | |".format(anno, v["stato"]))
            continue
        c = v["conteggi"]
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            anno, VERIFICA_LISTA.get(anno, "no"), c.get("uscite verso il basso", 0), c.get("uscite verso l'alto (in IWB)", 0),
            c.get("uscite dopo esclusioni e filtri", 0), c.get("uscite con almeno 3 peer", 0), c.get("rimasti", 0),
            c.get("rimasti dopo esclusioni e filtri (universo dei peer)", 0), c.get("falsi eventi (placebo)", 0)))
    L += ["", "## Copertura: identità e prezzi, per anno", "",
          "Nell'ordine delle esclusioni del §3. **Identità** = il prezzo implicito nella posizione del fondo coincide con "
          "la chiusura grezza EODHD entro il 3%. **Eventi** = restano dopo gli eventi societari del trimestre (Form "
          "25/15, fusioni, 8-K 1.03). **Prezzi** = almeno l'80% di chiusure e volumi puliti dal Rank Day − 126 sedute "
          "alla ricostituzione.", "",
          "| anno | uscite verso il basso | con identità | | dopo gli eventi | con prezzi sufficienti | copertura prezzi |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for anno, v in tab.items():
        if v["stato"] != "ok":
            continue
        c = v["conteggi"]
        n = c.get("uscite verso il basso", 0)
        i_ = c.get("uscite con identità verificata (EODHD)", 0)
        e_ = c.get("uscite dopo gli eventi societari della fase 1", 0)
        p_ = c.get("uscite con prezzi e volumi sufficienti", 0)
        L.append("| {} | {} | {} | {} | {} | {} | {} |".format(anno, n, i_, pc(i_ / n if n else None), e_, p_,
                                                                pc(p_ / e_ if e_ else None)))
    tot = collections.Counter()
    for v in tab.values():
        if v["stato"] == "ok":
            tot.update(v["esclusioni_uscite"])
    L += ["", "## Esclusioni delle uscite verso il basso (tutti gli anni)", "", "| motivo | casi |", "|---|---:|"]
    L += ["| {} | {} |".format(k, n) for k, n in tot.most_common()]
    L += ["", "## Filtri sulle uscite che arrivano ai filtri (tutti gli anni)", "",
          "| filtro | passa | non passa | non verificabile |", "|---|---:|---:|---:|"]
    nomi_f = {"f1": "flusso di cassa operativo 12 mesi > 0", "f2": "cassa netta o debito netto / EBITDA < 3",
              "f3": "azioni +5% o meno in 12 mesi", "f4": "nessuna fusione annunciata alle liste preliminari"}
    for f, nome in nomi_f.items():
        c = collections.Counter()
        for v in tab.values():
            if v["stato"] == "ok":
                c.update(v["filtri_uscite"].get(f, {}))
        L.append("| {} | {} | {} | {} |".format(nome, c["passa"], c["non passa"], c["non verificabile"]))
    L += ["", "## Quando scatta l'ingresso (uscite dopo esclusioni, filtri e peer)", "",
          "| scaglione | primo giorno possibile | forzato al limite | in mezzo | non decidibile | mediana sedute dopo la ricostituzione | quota agli estremi |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for nome, x in dist.items():
        c = x["conteggi"]
        L.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            nome, c.get("primo giorno possibile", 0), c.get("forzato al limite", 0), c.get("in mezzo", 0),
            sum(v for k, v in c.items() if k.startswith("non")), x["mediana_sedute"], pc(x["quota_estremi"])))
    L += ["", "Sedute dopo la ricostituzione a cui scatta l'ingresso, per scaglione (N = sedute minime, limite = "
          "ingresso forzato):", "",
          "| scaglione | N | limite | minimo | primo quartile | mediana | terzo quartile | massimo |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for nome, x in dist.items():
        q = x.get("quartili") or [None, None, None]
        L.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            nome, x["limiti"][0], x["limiti"][1], x["minimo"], q[0], x["mediana_sedute"], q[2], x["massimo"]))
    oltre = [n for n, x in dist.items() if x["quota_estremi"] is not None and x["quota_estremi"] > 0.5]
    L += ["", ("**Attenzione: in {} più della metà degli ingressi cade al primo giorno possibile o al limite: la regola "
               "distingue poco.**".format(", ".join(oltre))) if oltre else "In nessuno scaglione più della metà degli ingressi cade agli estremi.", ""]
    L += ["## Casi disponibili per orizzonte", "", "| cella | casi | anni |", "|---|---:|---|"]
    L += ["| {} | {} | {} |".format(k, v["casi"], ", ".join(str(a) for a in v["anni"])) for k, v in disp.items()]
    per_anno_pl = collections.Counter(u["anno"] for u in placebo)
    decidibili_pl = collections.Counter(u["anno"] for u in placebo if u["ingressi"]["B2"][0] is not None)
    L += ["", "## Falsi eventi per il placebo", "",
          "Per ogni anno, i rimasti dell'universo con la capitalizzazione più bassa non usati come peer, tanti quante le "
          "uscite con almeno 3 peer (ADR-045): un falso evento per caso, per costruzione; ingresso B2.", "",
          "| anno | falsi eventi | con ingresso B2 decidibile |", "|---|---:|---:|"]
    L += ["| {} | {} | {} |".format(a_, per_anno_pl[a_], decidibili_pl[a_]) for a_ in sorted(per_anno_pl)]
    L += ["| **totale** | **{}** | **{}** |".format(len(placebo), sum(decidibili_pl.values())), ""]
    if esempio:
        L += ["## Un caso completo (senza rendimenti)", "",
              "**{}** ({}, CIK {}), anno {}: valore della posizione di IWM riportato al Rank Day ${} (misura proporzionale "
              "alla capitalizzazione flottante, non la capitalizzazione), rendimento a 6 mesi nel terzile {} (1 = peggiore)."
              .format(esempio["nome"], esempio["ticker"], esempio["cik"], esempio["anno"], migliaia(esempio["cap"]),
                      esempio["terzile"] + 1), "",
              "| peer | ticker | CIK | valore della posizione di IWM al Rank Day |", "|---|---|---|---:|"]
        L += ["| {} | {} | {} | ${} |".format(u["nome"], u["ticker"], u["cik"], migliaia(u["cap"])) for u in esempio["peer"]]
        r = date_y[esempio["anno"]]["r"]
        L += ["", "Ricostituzione {}. Ingressi: ".format(IDS[r]) + "; ".join(
            "{} {} ({} sedute dopo, {})".format(n, IDS[s] if s is not None else "—", (s - r) if s is not None else "—", e)
            for n, (s, e) in esempio["ingressi"].items() if n.startswith("B")) + ".", ""]
    (OUT / "conteggi.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    righe = []
    for x in casi + placebo:
        righe.append({"tipo": "placebo" if x in placebo else "uscita", "anno": x["anno"], "cik": x["cik"], "ticker": x["ticker"],
                      "nome": x["nome"], "cap": x["cap"], "terzile": x.get("terzile"), "sic": x["sic"],
                      "peer": ";".join(u["cik"] for u in x.get("peer", [])),
                      **{"ingresso_" + n: (IDS[s] if s is not None else "") for n, (s, _e) in x["ingressi"].items()},
                      **{"esito_" + n: e for n, (_s, e) in x["ingressi"].items()}})
    if righe:
        with (OUT / "casi_conteggi.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(righe[0]))
            w.writeheader()
            w.writerows(righe)
    (OUT / "conteggi.json").write_text(json.dumps({"anni": tab, "ingressi": dist, "disponibili": disp,
                                                   "chiamate_edgar": s_ec.b.usate}, indent=1, default=str), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
