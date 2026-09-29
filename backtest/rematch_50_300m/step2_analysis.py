"""Passi 2 e 3 del ri-test 50-300M: controllo appaiato, placebo, scomposizione, verdetto.

Pre-registrazione `130b0fe`, addendum 1 `e48cfb9`, addendum 2 `3322f7e`, addendum 3 `fd28e71`.
Legge la popolazione di `survival.py` (`step2_prep/popolazione.jsonl`) e i prezzi dei deal
(`step2_prep/deal.jsonl`). Nessuna chiamata di rete, nessun modello linguistico.

    python backtest/rematch_50_300m/step2_analysis.py --diagnostica   # conteggi, nessuna media
    python backtest/rematch_50_300m/step2_analysis.py                 # tutto

NELL'ORDINE
  1. pool dei peer (ADR-005): per ogni emittente e sessione IWM, close entro 5 sessioni e
     azioni XBRL con `filed` <= data; righe del corpus per il quiet (ADR-007);
  2. per ogni evento: D, cap ricalcolata per la sola distanza (ADR-006), peer M_size e M_mom
     (ADR-008) col quiet primario e con quello a +-365;
  3. gambe sul calendario comune con l'ingresso dell'addendum 2, giuntura per gli osservati
     finiti in finestra (addendum 3 §2), placebo P1 e P2 (ADR-009);
  4. terminati in finestra della cella P ai valori del §6 dell'addendum 3;
  5. statistica (CR1 per emittente, bootstrap per emittente), placebo ~ 0, sel, tabella
     R0'-R6, limite k, criterio secondario.

SCELTE D'IMPLEMENTAZIONE CHE LE PRE-REGISTRAZIONI NON FISSANO, dichiarate nel report:
  - ticker del peer: fra i ticker del CIK nel corpus con serie in `prices/`, quello visto per
    ultimo (data di deposito piu' recente);
  - D non di borsa: close all'ultima sessione <= D; azioni con `filed` <= D esatto;
  - sd della standardizzazione di M_mom: popolazione (ddof = 0);
  - cap dell'evento non ricalcolabile: distanza con la cap della fascia, flag;
  - peer della serie finita prima dell'uscita: ultimo close piatto, come l'evento; serie viva
    ma ferma da piu' di 5 sessioni all'uscita: coppia esclusa e contata;
  - terminati in finestra: M_mom non si calcola (senza serie non c'e' r12), negli scenari di
    entrambi i matching entra il peer M_size scelto con la cap insider; cambio EUR alla
    sessione s0 all'ingresso;
  - giuntura: primo ticker di oggi, nell'ordine delle submissions, con una serie che riprende
    entro 5 sessioni.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import hashlib
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import backtest_event_time as B  # noqa: E402
import step1_analysis as S1  # noqa: E402
import survival as SV  # noqa: E402
from form4_scanner.classify import classify_insider  # noqa: E402
from form4_scanner.cluster import IssuerCluster  # noqa: E402
from form4_scanner.flags import score_v3  # noqa: E402
from form4_scanner.parse import Transaction  # noqa: E402

OUT = HERE / "step2"
PREP = HERE / "step2_prep"

H = 126
MAX_STALE = 5
DELIST_GAP = 10
QUIET_GIORNI = 365
R12_SESSIONI = 252
PLACEBO = (("P1", -252, -126), ("P2", -504, -378))
SOGLIA_PLACEBO = 0.015
FINESTRA_SCANNER = 60
GUARDIA_DEAL = (0.05, 20.0)
BANDE = {"<50M": (0.0, 50e6), "50-300M": (50e6, 300e6), ">300M": (300e6, float("inf"))}
MATCHING = ("M_size", "M_mom")
QUIET = ("primario", "pm365")
USCITA_NON_OSSERVATA = ("USCITO_DOPO",)
VIVI_NON_OSSERVATI = ("USCITO_DOPO", "VIVO_SENZA_STORIA", "GUASTO_FONTE")

# --------------------------------------------------------------- sessioni --
IDS = S1.IDS
LAST = len(IDS) - 1
ORD = np.array(IDS, dtype="datetime64[D]").astype(np.int64)
IPX = np.asarray(S1.IPX, dtype=float)
FXS = np.array([B.value_on(S1.FDS, S1.FPX, d) or np.nan for d in IDS], dtype=float)
LIMITE_DELISTING = ORD[LAST - DELIST_GAP]


def giorno(d):
    return int(np.datetime64(d, "D").astype(np.int64))


def sessione(d):
    return bisect.bisect_right(IDS, d) - 1


class Serie:
    """Una serie di close: giorni come interi, prezzi, sessione IWM di ogni barra."""

    __slots__ = ("o", "px", "s")

    def __init__(self, ds, px):
        self.o = np.array(ds, dtype="datetime64[D]").astype(np.int64)
        self.px = np.asarray(px, dtype=float)
        self.s = np.searchsorted(ORD, self.o, side="right") - 1

    def a_sessione(self, s):
        """Ultimo close <= sessione s, entro MAX_STALE sessioni; altrimenti None."""
        if s < 0 or s > LAST:
            return None
        k = int(np.searchsorted(self.o, ORD[s], side="right")) - 1
        if k < 0 or int(self.s[k]) < s - MAX_STALE:
            return None
        return float(self.px[k])


def carica(path):
    """Stesso parsing di backtest_event_time.load_series, da un percorso."""
    ds, px = [], []
    with Path(path).open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            d = d.strip()
            if len(d) != 10:
                continue
            try:
                f = float(v)
            except ValueError:
                continue
            if f > 0:
                ds.append(d)
                px.append(f)
    return Serie(ds, px) if len(ds) >= 2 else None


def ritorno(p0, s0, p1, s1):
    """Rendimento in euro fra due sessioni, None se manca un cambio o e' un artefatto."""
    f0, f1 = FXS[s0], FXS[s1]
    if not (np.isfinite(f0) and np.isfinite(f1)) or p0 is None or p1 is None or p0 <= 0:
        return None
    r = (p1 / f1) / (p0 / f0) - 1.0
    return r if abs(r) <= B.ARTEFACT else None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def impronta_dir(d):
    h, n = hashlib.sha256(), 0
    for f in sorted(Path(d).glob("*.csv")):
        h.update(f.name.encode())
        h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
        n += 1
    return h.hexdigest(), n


# ------------------------------------------------------------------ corpus --
def leggi_corpus(emittenti_cluster):
    """Ticker per CIK, righe per il quiet, righe complete degli emittenti della cella cluster."""
    tick = collections.defaultdict(dict)
    td, fd, cik = [], [], []
    righe = collections.defaultdict(list)
    for f in sorted(B.CORPUS.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                c = (r.get("issuer_cik") or "").lstrip("0")
                if not c:
                    continue
                t = (r.get("ticker") or "").upper()
                dep = r.get("filed_date") or ""
                if t and t not in ("NONE", "N/A", "[NONE]") and dep > tick[c].get(t, ""):
                    tick[c][t] = dep
                tr = r.get("transaction_date") or ""
                if len(tr) == 10 and len(dep) == 10:
                    td.append(tr)
                    fd.append(dep)
                    cik.append(c)
                if c in emittenti_cluster:
                    righe[c].append(r)
    return tick, (td, fd, cik), righe


# -------------------------------------------------------------------- pool --
class Pool:
    """ADR-005 e ADR-006: emittenti con azioni in shares/ e serie in prices/."""

    def __init__(self, tick, quiet_righe):
        prezzi = {p.stem.upper(): p for p in SV.FONTI[0].glob("*.csv")}
        scelti = []
        for c, per in tick.items():
            if not (SV.S / "shares" / "{}.json".format(c)).exists():
                continue
            con_serie = sorted(((dep, t) for t, dep in per.items() if SV.chiave(t) in prezzi), reverse=True)
            if con_serie:
                scelti.append((int(c), c, prezzi[SV.chiave(con_serie[0][1])]))
        scelti.sort()
        self.ciks = [c for _, c, _ in scelti]
        self.idx = {c: i for i, c in enumerate(self.ciks)}
        n, m = len(scelti), LAST + 1
        self.C = np.full((n, m), np.nan)
        self.A = np.full((n, m), np.nan)
        self.ultimo_s = np.zeros(n, dtype=np.int64)
        self.ultimo_o = np.zeros(n, dtype=np.int64)
        self.ultimo_px = np.zeros(n)
        self.fuori_sessione = collections.defaultdict(list)     # giorno non IWM -> [(i, azioni)]
        sessioni = set(IDS)
        passi = np.arange(m)
        for i, (_, c, path) in enumerate(scelti):
            ser = carica(path)
            if ser is not None:
                k = np.searchsorted(ser.o, ORD, side="right") - 1
                kk = np.where(k >= 0, k, 0)
                ok = (k >= 0) & (ser.s[kk] >= passi - MAX_STALE)
                self.C[i] = np.where(ok, ser.px[kk], np.nan)
                self.ultimo_s[i], self.ultimo_o[i], self.ultimo_px[i] = ser.s[-1], ser.o[-1], ser.px[-1]
            by = {}
            for r in json.loads((SV.S / "shares" / "{}.json".format(c)).read_text(encoding="utf-8")).get("primary") or []:
                if r.get("filed") and r.get("val"):
                    by[r["filed"]] = float(r["val"])
            if by:
                fdate = sorted(by)
                fo = np.array(fdate, dtype="datetime64[D]").astype(np.int64)
                vals = np.array([by[x] for x in fdate])
                k2 = np.searchsorted(fo, ORD, side="right") - 1
                self.A[i] = np.where(k2 >= 0, vals[np.where(k2 >= 0, k2, 0)], np.nan)
                for x in fdate:
                    if x not in sessioni:
                        self.fuori_sessione[x].append((i, by[x]))
            if i % 1000 == 0:
                print("  pool {:,}/{:,}".format(i, n), flush=True)
        td, fd, ck = quiet_righe
        ordine = np.argsort(np.array(td, dtype="datetime64[D]").astype(np.int64), kind="stable")
        self.q_td = np.array(td, dtype="datetime64[D]").astype(np.int64)[ordine]
        self.q_fd = np.array(fd, dtype="datetime64[D]").astype(np.int64)[ordine]
        self.q_i = np.array([self.idx.get(c, -1) for c in ck], dtype=np.int64)[ordine]
        self._cache = {}

    def candidati(self, D):
        """(cap, r12, quiet primario, quiet +-365) di tutti gli emittenti del pool a D."""
        if D in self._cache:
            return self._cache[D]
        sD = sessione(D)
        n = len(self.ciks)
        if sD < 0:
            vuoto = np.full(n, np.nan)
            return vuoto, vuoto, np.zeros(n, bool), np.zeros(n, bool)
        az = self.A[:, sD].copy()
        g = date.fromisoformat(IDS[sD]) + timedelta(days=1)
        while g.isoformat() <= D:
            for i, v in self.fuori_sessione.get(g.isoformat(), ()):
                az[i] = v
            g += timedelta(days=1)
        close = self.C[:, sD]
        cap = az * close
        if sD - R12_SESSIONI >= 0:
            with np.errstate(divide="ignore", invalid="ignore"):
                r12 = close / self.C[:, sD - R12_SESSIONI] - 1.0
            r12[~np.isfinite(r12) | (np.abs(r12) > B.ARTEFACT)] = np.nan
        else:
            r12 = np.full(n, np.nan)
        d0 = giorno(D)
        i0 = int(np.searchsorted(self.q_td, d0 - QUIET_GIORNI, side="left"))
        i1 = int(np.searchsorted(self.q_td, d0, side="right"))
        i2 = int(np.searchsorted(self.q_td, d0 + QUIET_GIORNI, side="right"))
        q1 = np.ones(n, bool)
        sporchi = self.q_i[i0:i1][(self.q_fd[i0:i1] <= d0) & (self.q_i[i0:i1] >= 0)]
        q1[sporchi] = False
        q2 = np.ones(n, bool)
        sporchi2 = self.q_i[i0:i2][self.q_i[i0:i2] >= 0]
        q2[sporchi2] = False
        out = (cap, r12, q1, q2)
        self._cache[D] = out
        return out

    def appaia(self, D, banda, cap_e, r12_e, cik_e):
        """{(matching, quiet): indice del peer o None}. Pareggi: CIK numerico minore (argmin)."""
        cap, r12, q1, q2 = self.candidati(D)
        lo, hi = BANDE[banda]
        out = {}
        with np.errstate(divide="ignore", invalid="ignore"):
            lcap = np.log(cap)
            in_banda = np.isfinite(cap) & (cap > 0) & (cap >= lo) & (cap < hi)
            if cik_e in self.idx:
                in_banda[self.idx[cik_e]] = False
            for qn, q in zip(QUIET, (q1, q2)):
                base = in_banda & q
                out[("M_size", qn)] = None
                out[("M_mom", qn)] = None
                if cap_e and cap_e > 0 and base.any():
                    d = np.where(base, np.abs(lcap - math.log(cap_e)), np.inf)
                    j = int(np.argmin(d))
                    out[("M_size", qn)] = j if np.isfinite(d[j]) else None
                mom = base & np.isfinite(r12)
                if cap_e and cap_e > 0 and r12_e is not None and mom.sum() >= 2:
                    mu1, sd1 = lcap[mom].mean(), lcap[mom].std()
                    mu2, sd2 = r12[mom].mean(), r12[mom].std()
                    if sd1 > 0 and sd2 > 0:
                        z = ((lcap - math.log(cap_e)) / sd1) ** 2 + ((r12 - r12_e) / sd2) ** 2
                        z = np.where(mom, z, np.inf)
                        j = int(np.argmin(z))
                        out[("M_mom", qn)] = j if np.isfinite(z[j]) else None
        return out

    def gamba(self, i, s0, s1):
        """(rendimento, flag) del peer fra le sessioni s0 e s1; rendimento None se la coppia cade."""
        a = self.C[i, s0]
        if not np.isfinite(a):
            return None, "PEER_SENZA_INGRESSO"
        b, fl = self.C[i, s1], None
        if not np.isfinite(b):
            if self.ultimo_o[i] < LIMITE_DELISTING and self.ultimo_s[i] < s1:
                b, fl = self.ultimo_px[i], "PEER_FINITO"
            else:
                return None, "PEER_FERMO"
        r = ritorno(float(a), s0, float(b), s1)
        return (r, fl) if r is not None else (None, "PEER_ARTEFATTO")

    def prezzo(self, i, s):
        v = self.C[i, s] if 0 <= s <= LAST else np.nan
        return float(v) if np.isfinite(v) else None


# ------------------------------------------------------------ gamba evento --
SERIE_IDX = SV.indice_serie()


def giuntura(ser, cik):
    """Addendum 3 §2: ticker di oggi con una serie che riprende entro 5 sessioni dall'ultima barra."""
    d, _dep = SV.submissions(cik)
    for t in (d or {}).get("tickers") or []:
        p = SERIE_IDX.get(SV.chiave(t))
        nuova = carica(p) if p else None
        if nuova is None:
            continue
        j = int(np.searchsorted(nuova.o, ser.o[-1], side="right"))
        if j >= len(nuova.o) or int(nuova.s[j]) - int(ser.s[-1]) > MAX_STALE:
            continue
        g = Serie([], [])
        g.o = np.concatenate([ser.o, nuova.o[j:]])
        g.px = np.concatenate([ser.px, nuova.px[j:]])
        g.s = np.concatenate([ser.s, nuova.s[j:]])
        return g
    return None


def gamba_evento(ser, filed, cik, osservato):
    """(stato, e0, rendimento, flag). Addendum 2, con la giuntura dell'addendum 3."""
    s0 = bisect.bisect_right(IDS, filed)
    if s0 > LAST:
        return "TOO_RECENT", None, None, None
    j = int(np.searchsorted(ser.o, ORD[s0], side="left"))
    if j >= len(ser.o) or int(ser.s[j]) - s0 > MAX_STALE:
        return "NO_ENTRY_BAR", None, None, None
    e0 = int(ser.s[j])
    if ser.o[j] <= giorno(filed):
        raise SystemExit("ingresso non successivo al deposito: {} {}".format(cik, filed))
    if e0 + H > LAST:
        return "TOO_RECENT", e0, None, None
    uscita = ORD[e0 + H]
    flag = None
    if osservato and ser.o[-1] < uscita and ser.o[-1] < LIMITE_DELISTING:
        g = giuntura(ser, cik)
        if g is not None:
            ser, flag = g, "GIUNTURA"
    k = int(np.searchsorted(ser.o, uscita, side="right")) - 1
    stato = "OK"
    if ser.o[-1] < uscita and ser.o[-1] < LIMITE_DELISTING:
        stato, k = "ENDED_IN_WINDOW", len(ser.o) - 1
    elif (e0 + H) - int(ser.s[k]) > MAX_STALE:
        return "STALE_EXIT", e0, None, flag
    r = ritorno(float(ser.px[j]), e0, float(ser.px[k]), e0 + H)
    if r is None:
        return "ARTEFACT", e0, None, flag
    return stato, e0, r, flag


# ------------------------------------------------------------- cella cluster --
def punteggio_v3(e, righe, history):
    """score_v3 invariato su transazioni del corpus: deposito <= evento, transazione nei 60 giorni prima."""
    fd = e["filed"]
    lo = (date.fromisoformat(fd) - timedelta(days=FINESTRA_SCANNER)).isoformat()
    txns = []
    for r in righe.get(e["cik"], ()):
        tr = r.get("transaction_date") or ""
        if (r.get("filed_date") or "9") > fd or not (lo <= tr <= fd) or len(tr) != 10:
            continue
        txns.append(Transaction(
            accession=r.get("accession") or "", filed_at=date.fromisoformat(r["filed_date"]),
            issuer_cik=e["cik"], issuer_name=r.get("issuer_name") or "", ticker=r.get("ticker") or "",
            owner_cik=(r.get("owner_cik") or "").lstrip("0"), owner_name=r.get("owner_name") or "",
            is_director=bool(r.get("is_director")), is_officer=bool(r.get("is_officer")),
            is_ten_pct=bool(r.get("is_ten_pct")), officer_title=r.get("officer_title") or "",
            txn_date=date.fromisoformat(tr), code="P", acquired_disposed="A",
            shares=float(r.get("shares") or 0), price=float(r.get("price") or 0),
            value=float(r.get("value") or 0), shares_after=float(r.get("shares_owned_after") or 0),
            direct=True, is_derivative=False, plan_10b5_1=bool(r.get("is_10b5_1")),
            txn_index=int(r.get("txn_index") if r.get("txn_index") is not None else -1)))
    if not txns:
        return None
    cl = IssuerCluster(e["cik"], txns[0].issuer_name, txns[0].ticker, txns)
    as_of = date(int(fd[:4]), 1, 1)
    labels = {}
    for o in {t.owner_cik for t in txns}:
        prior = [date.fromisoformat(x) for x in history.get(o, []) if x < as_of.isoformat()]
        labels[o] = classify_insider(o, "", prior, as_of).label
    return score_v3(cl, labels)


# ------------------------------------------------------------ statistica --
def blocco(coppie):
    """coppie = [(valore, cik)]."""
    return S1.blocco([x for x, _ in coppie], [g for _, g in coppie]) if coppie else None


def circa_zero(d):
    """Addendum 1 §3: IC CR1 include 0 e |media| < 1,5 punti. Senza IC, non ~ 0."""
    if not d or d.get("cr1_lo") is None:
        return False
    return d["cr1_lo"] <= 0.0 <= d["cr1_hi"] and abs(d["mean"]) < SOGLIA_PLACEBO


def sopravvive(d):
    return bool(d and d["mean"] > 0 and d.get("cr1_lo") is not None and d["cr1_lo"] > 0)


def scegli_sel(st):
    q = {"M_size": circa_zero(st["M_size"]["P1"]) and circa_zero(st["M_size"]["P2"]),
         "M_mom": circa_zero(st["M_mom"]["P2"])}
    cand = [m for m in MATCHING if q[m]]
    sel = min(cand, key=lambda m: (abs(st[m]["P2"]["mean"]), abs(st[m]["P2"]["t_cr1"] or 0.0),
                                   MATCHING.index(m))) if cand else None
    return q, sel


def verdetto(st, q, sel, r0_cambia):
    """Tabella ordinata dell'addendum 1 §4, con R0' dell'addendum 3 §7."""
    s = {m: sopravvive(st[m]["main"]) for m in MATCHING}
    if sel and r0_cambia:
        return "R0'", "INCONCLUSIVO", "sopravvivenza"
    if not sel:
        return "R1", "INCONCLUSIVO", "placebo non ~ 0, nessun matching lo corregge"
    if s["M_size"] and not s["M_mom"]:
        if q["M_mom"]:
            return "R2a", "NON REGGE", "effetto reversal, non effetto insider"
        return "R2b", "INCONCLUSIVO", "reversal non escludibile: il matching con momentum non e' credibile"
    if st[sel]["main"]["mean"] <= 0:
        return "R3", "NON REGGE", "media del matching di riferimento <= 0"
    if s[sel] and s["M_mom"] and q["M_mom"]:
        return "R4", "REGGE", ""
    if s[sel]:
        return "R5", "INCONCLUSIVO", "reversal non escludibile"
    return "R6", "INCONCLUSIVO", "sotto potenza"


# ------------------------------------------------------------------ main --
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--diagnostica", action="store_true",
                    help="costruisce pool, abbinamenti e stati delle gambe; nessuna media, nessun verdetto")
    a = ap.parse_args()
    S1.verifica_cr1()
    OUT.mkdir(parents=True, exist_ok=True)

    pop = [json.loads(l) for l in (PREP / "popolazione.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    deal = {json.loads(l)["cik"]: json.loads(l) for l in (PREP / "deal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    esito_val = json.loads((PREP / "validazione_esito.json").read_text(encoding="utf-8"))
    valutati = [r for r in pop if r["stato"] in ("OSSERVATO", "RISOLTO")]
    cella_p = {r["cik"] for r in valutati if r["banda"] == "50-300M"}

    print("corpus...", flush=True)
    tick, quiet_righe, righe_cluster = leggi_corpus(cella_p)
    print("pool...", flush=True)
    pool = Pool(tick, quiet_righe)
    print("  pool: {:,} emittenti".format(len(pool.ciks)), flush=True)
    caps = SV.caps_backfill()
    azioni = SV.Azioni()
    history = json.loads(B.HISTORY.read_text(encoding="utf-8"))

    # ------------------------------------------------ eventi valutati
    diag = collections.Counter()
    eventi = []
    per_serie = collections.defaultdict(list)
    for r in valutati:
        per_serie[r["serie"]].append(r)
    fatti = 0
    for path, gruppo in per_serie.items():
        ser = carica(ROOT / path)
        for r in gruppo:
            e = dict(r)
            fatti += 1
            osservato = r["stato"] == "OSSERVATO"
            if osservato:
                xs = caps.get(r["cik"]) or []
                j = bisect.bisect_right([d for d, _ in xs], r["filed"]) - 1
                e["D"] = xs[j][0] if j >= 0 else r["filed"]
            else:
                e["D"] = r["data_insider"] or r["filed"]
            sD = sessione(e["D"])
            az = azioni.at(r["cik"], e["D"])
            px_d = ser.a_sessione(sD) if ser is not None else None
            e["cap_ric"] = az * px_d if (az and px_d) else None
            e["cap_distanza"] = e["cap_ric"] or r["cap"]
            if e["cap_ric"] is None:
                diag["cap evento non ricalcolabile: distanza con la cap della fascia"] += 1
            elif SV.banda(e["cap_ric"]) != r["banda"]:
                diag["cap ricalcolata fuori dalla fascia originale"] += 1
            e["r12"] = None
            if ser is not None and sD - R12_SESSIONI >= 0:
                p_old = ser.a_sessione(sD - R12_SESSIONI)
                if px_d and p_old:
                    v = px_d / p_old - 1.0
                    e["r12"] = v if abs(v) <= B.ARTEFACT else None
            if ser is None:
                e["stato_gamba"], e["e0"], e["r_e"], e["flag"] = "NO_SERIES", None, None, None
            else:
                e["stato_gamba"], e["e0"], e["r_e"], e["flag"] = gamba_evento(ser, r["filed"], r["cik"], osservato)
            e["peer"] = pool.appaia(e["D"], r["banda"], e["cap_distanza"], e["r12"], r["cik"])
            e["legs"], e["placebo"] = {}, {}
            if e["r_e"] is not None:
                e0 = e["e0"]
                e["r_iwm"] = ritorno(IPX[e0], e0, IPX[e0 + H], e0 + H)
                for key, i in e["peer"].items():
                    if i is None:
                        continue
                    rp, fl = pool.gamba(i, e0, e0 + H)
                    e["legs"][key] = (rp, fl, pool.ciks[i])
                    if key[1] != "primario" or rp is None:
                        continue
                    for nome, lo, hi in PLACEBO:
                        sa, sb = e0 + lo, e0 + hi
                        if sa < 0:
                            continue
                        re_ = ritorno(ser.a_sessione(sa), sa, ser.a_sessione(sb), sb)
                        rp_ = ritorno(pool.prezzo(i, sa), sa, pool.prezzo(i, sb), sb)
                        if re_ is not None and rp_ is not None:
                            e["placebo"][(key[0], nome)] = re_ - rp_
            e["v3"] = punteggio_v3(e, righe_cluster, history) if r["banda"] == "50-300M" else None
            eventi.append(e)
            if fatti % 2000 == 0:
                print("  eventi {:,}/{:,}".format(fatti, len(valutati)), flush=True)

    # ------------------------------------------------ terminati in finestra, cella P
    terminati = []
    for r in pop:
        if r["banda"] != "50-300M" or r["stato"] != "TERMINATO_IN_FINESTRA":
            continue
        t = dict(r)
        s0 = bisect.bisect_right(IDS, r["filed"])
        t["s0"] = s0
        peer = pool.appaia(r["data_insider"], "50-300M", r["cap"], None, r["cik"])
        i = peer[("M_size", "primario")]
        t["r_iwm"] = ritorno(IPX[s0], s0, IPX[s0 + H], s0 + H)
        t["r_peer"], t["flag_peer"] = pool.gamba(i, s0, s0 + H) if i is not None else (None, "SENZA_PEER")
        t["peer_cik"] = pool.ciks[i] if i is not None else None
        classe, dl, flags = r["classe"], deal.get(r["cik"]) or {}, []
        r_stock = None
        if not esito_val["classificatore_valido"]:
            scen = "S_zero"
            flags.append("CLASSIFICATORE_NON_VALIDATO")
        elif classe == "FALLIMENTO":
            scen, r_stock = "S0", -1.0
        elif classe in ("ACQUISIZIONE", "LIQUIDAZIONE"):
            px_ins = r.get("prezzo_insider")
            if dl.get("esito") == "CONTANTI" and dl.get("prezzo") and px_ins:
                rapporto = dl["prezzo"] / px_ins
                if GUARDIA_DEAL[0] <= rapporto <= GUARDIA_DEAL[1]:
                    scen = "S_acq"
                    r_stock = (dl["prezzo"] / FXS[s0 + H]) / (px_ins / FXS[s0]) - 1.0
                    flags.append("INGRESSO_NON_ALLA_DATA_DI_DEPOSITO")
                else:
                    scen = "S_zero"
                    flags.append("IMPLAUSIBILE")
            else:
                scen = "S_zero"
                flags.append("DEAL_" + (dl.get("esito") or "NON_CERCATO"))
        elif classe == "VOLONTARIO_OTC":
            scen = "S_zero"
            flags.append("OTC_SENZA_PREZZO")
        else:
            scen = "S_zero"
            flags.append("NON_RISOLTO")
        t["scenario"], t["r_stock"], t["flags"] = scen, r_stock, flags
        terminati.append(t)

    stati = collections.Counter((e["banda"], e["stato_gamba"]) for e in eventi)
    abbinati = collections.Counter()
    esclusi = collections.Counter()
    for e in eventi:
        for key, i in e["peer"].items():
            abbinati[(e["banda"], key, i is not None)] += 1
        for key, (rp, fl, _c) in e["legs"].items():
            esclusi[(e["banda"], key, fl or "OK")] += 1

    if a.diagnostica:
        print("\nDIAGNOSTICA -- nessuna media, nessun verdetto")
        print("pool:", len(pool.ciks))
        for k, v in sorted(diag.items()):
            print("  {}: {:,}".format(k, v))
        print("stati della gamba evento:")
        for k, v in sorted(stati.items()):
            print("  {} {}: {:,}".format(k[0], k[1], v))
        print("abbinamenti (banda, matching, quiet, trovato):")
        for k, v in sorted(abbinati.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
            print("  {} {} {} {}: {:,}".format(k[0], k[1][0], k[1][1], k[2], v))
        print("gambe del peer (banda, matching, quiet, esito):")
        for k, v in sorted(esclusi.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
            print("  {} {} {} {}: {:,}".format(k[0], k[1][0], k[1][1], k[2], v))
        plac = collections.Counter((e["banda"], k) for e in eventi for k in e["placebo"])
        print("placebo disponibili:")
        for k, v in sorted(plac.items()):
            print("  {} {}: {:,}".format(k[0], k[1], v))
        print("cella P: v3 calcolato {:,}, cluster {:,}, 4/4 {:,}".format(
            sum(1 for e in eventi if e["v3"]), sum(1 for e in eventi if e["v3"] and e["v3"]["cluster"]),
            sum(1 for e in eventi if e["v3"] and e["v3"]["score"] == 4)))
        print("terminati in finestra P:", dict(collections.Counter(t["scenario"] for t in terminati)),
              dict(collections.Counter(f for t in terminati for f in t["flags"])),
              "senza gamba peer:", sum(1 for t in terminati if t["r_peer"] is None))
        return 0

    return scrivi(eventi, terminati, pop, pool, diag, stati, abbinati, esclusi, esito_val)


# ----------------------------------------------------------------- report --
def pct(v):
    return "—" if v is None else "{:+.2%}".format(v)


def num(v):
    return "—" if v is None else "{:.2f}".format(v)


def coppie(evs, cosa, quiet="primario"):
    """[(valore, cik)] per 'iwm', 'M_size', 'M_mom' su eventi con gamba valida."""
    out = []
    for e in evs:
        if e["r_e"] is None or e.get("r_iwm") is None:
            continue
        if cosa == "iwm":
            out.append((e["r_e"] - e["r_iwm"], e["cik"]))
            continue
        leg = e["legs"].get((cosa, quiet))
        if leg and leg[0] is not None:
            out.append((e["r_e"] - leg[0], e["cik"]))
    return out


def coppie_placebo(evs, m, nome):
    return [(e["placebo"][(m, nome)], e["cik"]) for e in evs
            if (m, nome) in e["placebo"] and e["r_e"] is not None
            and (e["legs"].get((m, "primario")) or (None,))[0] is not None]


def scrivi(eventi, terminati, pop, pool, diag, stati, abbinati, esclusi, esito_val):
    celle = collections.OrderedDict()
    celle["P (50-300M)"] = [e for e in eventi if e["banda"] == "50-300M"]
    celle["<50M"] = [e for e in eventi if e["banda"] == "<50M"]
    celle[">300M"] = [e for e in eventi if e["banda"] == ">300M"]
    celle["cluster"] = [e for e in celle["P (50-300M)"] if e["v3"] and e["v3"]["cluster"]]
    celle["4/4"] = [e for e in celle["P (50-300M)"] if e["v3"] and e["v3"]["score"] == 4]
    P = celle["P (50-300M)"]

    tab = {}
    for nome, evs in celle.items():
        tab[nome] = {"iwm": blocco(coppie(evs, "iwm"))}
        for m in MATCHING:
            tab[nome][m] = {"main": blocco(coppie(evs, m)),
                            "P1": blocco(coppie_placebo(evs, m, "P1")),
                            "P2": blocco(coppie_placebo(evs, m, "P2"))}
    st = tab["P (50-300M)"]

    # ---- sopravvivenza: scenari e R0'
    def media_scenari(m_or_iwm, nr_a_s0):
        xs = [x for x, _ in (coppie(P, "iwm") if m_or_iwm == "iwm" else coppie(P, m_or_iwm))]
        n_t = 0
        for t in terminati:
            gamba = t["r_iwm"] if m_or_iwm == "iwm" else t["r_peer"]
            if gamba is None:
                continue
            if t["classe"] == "NON_RISOLTO" and nr_a_s0 and esito_val["classificatore_valido"]:
                xs.append(-1.0 - gamba)
            elif t["r_stock"] is None:
                xs.append(0.0)
            else:
                xs.append(t["r_stock"] - gamba)
            n_t += 1
        return (float(np.mean(xs)) if xs else None), len(xs), n_t

    q, sel = scegli_sel(st)
    r0_cambia = False
    if sel:
        a0, _, _ = media_scenari(sel, False)
        a1, _, _ = media_scenari(sel, True)
        r0_cambia = (a0 is not None and a1 is not None) and ((a0 > 0) != (a1 > 0))
    riga, esito, motivo = verdetto(st, q, sel, r0_cambia)

    # ---- differenza evento per evento M_size - M_mom
    diff = []
    for e in P:
        a_, b_ = e["legs"].get(("M_size", "primario")), e["legs"].get(("M_mom", "primario"))
        if e["r_e"] is not None and a_ and b_ and a_[0] is not None and b_[0] is not None:
            diff.append(((e["r_e"] - a_[0]) - (e["r_e"] - b_[0]), e["cik"]))
    d_diff = blocco(diff)

    # ---- copertura e limite k
    cp = collections.Counter(r["stato"] for r in pop if r["banda"] == "50-300M")
    n_or = cp["OSSERVATO"] + cp["RISOLTO"]
    n_term = cp["TERMINATO_IN_FINESTRA"]
    n_vivi = sum(cp[s] for s in VIVI_NON_OSSERVATI)
    n_u = sum(cp[s] for s in USCITA_NON_OSSERVATA)
    copertura = n_or / (n_or + n_term + n_vivi)

    def limite(d):
        if not d:
            return None
        m, n_v = d["mean"], d["n"]
        righe = {k: m - k * n_u / (n_v + n_u) for k in (0.0, 0.05, 0.10, 0.20)}
        return righe, (m * (n_v + n_u) / n_u if m > 0 else None)

    # ---- scomposizione per anno
    def scomposizione(m):
        per = collections.defaultdict(list)
        for e in P:
            leg = e["legs"].get((m, "primario"))
            if e["r_e"] is None or e.get("r_iwm") is None or not leg or leg[0] is None:
                continue
            per[e["filed"][:4]].append((e["r_e"] - e["r_iwm"], e["r_e"] - leg[0], leg[0] - e["r_iwm"], e["cik"]))
        return per

    identita = 0.0
    for e in P:
        for m in MATCHING:
            leg = e["legs"].get((m, "primario"))
            if e["r_e"] is not None and e.get("r_iwm") is not None and leg and leg[0] is not None:
                identita = max(identita, abs((e["r_e"] - e["r_iwm"]) - ((e["r_e"] - leg[0]) + (leg[0] - e["r_iwm"]))))
    if identita > 1e-12:
        raise SystemExit("scomposizione non esatta: {}".format(identita))

    # ---- criterio secondario
    p_iwm = st["iwm"]
    c_ref = sel or "M_size"
    c_blk = st[c_ref]["main"]
    s_zero_iwm, _, _ = media_scenari("iwm", False)
    mde = None
    if p_iwm and p_iwm.get("sd") and p_iwm.get("t_cr1"):
        se_iid = p_iwm["sd"] / math.sqrt(p_iwm["n"])
        se_cr1 = abs(p_iwm["mean"] / p_iwm["t_cr1"])
        mde = 2.80 * se_iid * (se_cr1 / se_iid)

    # ---------------------------------------------------------------- testo
    ph, pn = impronta_dir(SV.FONTI[1])
    T = S1.TESTATA
    L = ["# Passi 2 e 3 — controllo appaiato, placebo, verdetto", "",
         "Generato da `python backtest/rematch_50_300m/step2_analysis.py`. Pre-registrazione `130b0fe`, "
         "addendum 1 `e48cfb9`, addendum 2 `3322f7e`, addendum 3 `fd28e71`. Nessuna chiamata di rete; "
         "modelli linguistici: token e costo **0**.", "",
         "| input | sha256 |", "|---|---|",
         "| `step2_prep/popolazione.jsonl` | `{}` |".format(sha(PREP / "popolazione.jsonl")),
         "| `step2_prep/deal.jsonl` | `{}` |".format(sha(PREP / "deal.jsonl")),
         "| `state/backfill/prices_resolved/` | `{}` ({} file) |".format(ph, pn), ""]

    L += ["## Verdetto primario", "",
          "> **{} — {}**{}".format(esito, riga, (": " + motivo) if motivo else ""), "",
          "| | M_size | M_mom |", "|---|---|---|",
          "| P1 ≈ 0 | {} | compresso per costruzione |".format("sì" if circa_zero(st["M_size"]["P1"]) else "no"),
          "| P2 ≈ 0 | {} | {} |".format("sì" if circa_zero(st["M_size"]["P2"]) else "no",
                                        "sì" if circa_zero(st["M_mom"]["P2"]) else "no"),
          "| Q (placebo credibile) | {} | {} |".format("sì" if q["M_size"] else "no", "sì" if q["M_mom"] else "no"),
          "| S (media > 0 e IC CR1 esclude 0) | {} | {} |".format(
              "sì" if sopravvive(st["M_size"]["main"]) else "no", "sì" if sopravvive(st["M_mom"]["main"]) else "no"),
          "", "Matching di riferimento **sel = {}**. {}".format(
              sel or "non esiste",
              ("R0′: il segno {} quando il terminato in finestra senza classe passa da S_zero a S0 "
               "(addendum 3 §7: non vincola).".format("cambia" if r0_cambia else "non cambia")) if sel else
              "R0′ non si applica senza sel; il test di segno per ciascun confronto è nella tabella degli "
              "scenari (§6)."), "",
          "Placebo ≈ 0 ⟺ IC 95% CR1 include lo zero **e** |media| < 1,5 punti (addendum 1 §3).", ""]

    L += ["## 1. Cella × confronto, 126 sessioni", "",
          "Popolazione primaria dell'addendum 1 sull'unione dell'addendum 3; sul verdetto entrano osservati "
          "e risolti. Excess in euro, calendario comune, ingresso dell'addendum 2.", ""]
    for nome in celle:
        L += ["### {}".format(nome), "", T,
              S1.riga_tab("vs IWM", tab[nome]["iwm"]),
              S1.riga_tab("vs peer dimensione (M_size)", tab[nome]["M_size"]["main"]),
              S1.riga_tab("vs peer dimensione + momentum (M_mom)", tab[nome]["M_mom"]["main"]), ""]
        if nome == "4/4":
            L += ["La cella 4/4 non è testabile (addendum 1 §8): si legge solo n = **{:,}** eventi con "
                  "`score_v3` = 4 su {:,} eventi della cella P con punteggio calcolato.".format(
                      len(evs), sum(1 for e in P if e["v3"])), ""]

    L += ["## 2. Placebo (passo 3)", "",
          "Stesso peer scelto alla data dell'evento; P1 = (−252, −126], P2 = (−504, −378] sessioni "
          "dall'ingresso.", ""]
    for nome in celle:
        L += ["### {}".format(nome), "", T]
        for m in MATCHING:
            L.append(S1.riga_tab("{} P1".format(m), tab[nome][m]["P1"]))
            L.append(S1.riga_tab("{} P2".format(m), tab[nome][m]["P2"]))
        L.append("")
    L += ["### Media a 126 sessioni ristretta alle coppie col placebo — cella P", "",
          "| | coppie con P1 | media | coppie con P2 | media |", "|---|---:|---:|---:|---:|"]
    for m in MATCHING:
        con1 = [e for e in P if (m, "P1") in e["placebo"]]
        con2 = [e for e in P if (m, "P2") in e["placebo"]]
        b1, b2 = blocco(coppie(con1, m)), blocco(coppie(con2, m))
        L.append("| {} | {:,} | {} | {:,} | {} |".format(m, b1["n"] if b1 else 0, pct(b1["mean"] if b1 else None),
                                                        b2["n"] if b2 else 0, pct(b2["mean"] if b2 else None)))
    L += ["", "### Differenza evento per evento, M_size − M_mom — cella P", "", T,
          S1.riga_tab("(r_e − r_M_size) − (r_e − r_M_mom)", d_diff), "",
          "Descrittiva (addendum 1 §4, conciliazione 3): non cambia la tabella.", ""]

    L += ["## 3. Scomposizione per anno — cella P", "",
          "Sullo stesso calendario, per evento: (r_e − r_IWM) = (r_e − r_peer) + (r_peer − r_IWM). "
          "Verificata esatta (scarto massimo {:.1e}). Quota = media (r_peer − r_IWM) ÷ media (r_e − r_IWM).".format(identita), ""]
    for m in MATCHING:
        per = scomposizione(m)
        L += ["### {}{}".format(m, " — matching di riferimento" if m == sel else ""), "",
              "| anno | n | r_e − r_IWM | r_e − r_peer | r_peer − r_IWM | quota del peer |",
              "|---|---:|---:|---:|---:|---:|"]
        tutti = []
        for y in sorted(per):
            xs = per[y]
            tutti += xs
            a_, b_, c_ = (float(np.mean([x[k] for x in xs])) for k in (0, 1, 2))
            L.append("| {} | {:,} | {} | {} | {} | {} |".format(y, len(xs), pct(a_), pct(b_), pct(c_),
                                                             "{:.0%}".format(c_ / a_) if a_ > 0 else "—"))
        if tutti:
            a_, b_, c_ = (float(np.mean([x[k] for x in tutti])) for k in (0, 1, 2))
            L.append("| **tutti** | **{:,}** | **{}** | **{}** | **{}** | **{}** |".format(
                len(tutti), pct(a_), pct(b_), pct(c_), "{:.0%}".format(c_ / a_) if a_ > 0 else "—"))
            if a_ > 0 and c_ / a_ > 0.5:
                L += ["", "**La maggior parte dell'excess contro IWM è la differenza fra il peer e IWM, non fra "
                      "l'evento e il peer.**"]
        L.append("")

    L += ["## 4. Per anno — cella P", "", T]
    anni = sorted({e["filed"][:4] for e in P})
    for y in anni:
        evs = [e for e in P if e["filed"][:4] == y]
        L.append(S1.riga_tab("**{}** vs IWM".format(y), blocco(coppie(evs, "iwm"))))
        for m in MATCHING:
            L.append(S1.riga_tab("**{}** vs {}".format(y, m), blocco(coppie(evs, m))))
    L += ["", "Sotto {} emittenti la t con cluster non si calcola.".format(S1.MIN_CLUSTER), ""]

    L += ["## 5. Sensibilità descrittive — cella P", "", T]
    for m in MATCHING:
        L.append(S1.riga_tab("{} con quiet ±365 (lookahead, a favore di REGGE)".format(m), blocco(coppie(P, m, "pm365"))))
    sub = [e for e in P if "2022" <= e["filed"][:4] <= "2025"]
    L.append(S1.riga_tab("2022–2025 vs IWM", blocco(coppie(sub, "iwm"))))
    for m in MATCHING:
        L.append(S1.riga_tab("2022–2025 vs {}".format(m), blocco(coppie(sub, m))))
    L.append("")

    L += ["## 6. Sopravvivenza — cella P", "",
          "| stato | eventi |", "|---|---:|"]
    for s_, v in sorted(cp.items()):
        L.append("| `{}` | {:,} |".format(s_, v))
    L += ["", "**Copertura** = (osservati + risolti) ÷ (osservati + risolti + terminati in finestra + vivi non "
          "osservati) = {:,} ÷ {:,} = **{:.1%}**.".format(n_or, n_or + n_term + n_vivi, copertura), "",
          "Classificatore d'uscita: concordanza {:.1%} su {} emittenti → {}.".format(
              esito_val["concordanza"], esito_val["n"], "valido" if esito_val["classificatore_valido"] else "NON valido"), "",
          "### Terminati in finestra ai valori del §6", "",
          "| scenario | eventi |", "|---|---:|"]
    for k, v in sorted(collections.Counter(t["scenario"] for t in terminati).items()):
        L.append("| {} | {:,} |".format(k, v))
    L += ["", "| flag | eventi |", "|---|---:|"]
    for k, v in sorted(collections.Counter(f for t in terminati for f in t["flags"]).items()):
        L.append("| `{}` | {:,} |".format(k, v))
    L += ["", "Senza gamba del peer (esclusi dagli scenari contro peer): {:,}.".format(
        sum(1 for t in terminati if t["r_peer"] is None)), "",
          "### Tabella degli scenari", "",
          "| confronto | osservati + risolti | + terminati ai valori del §6 | + NON_RISOLTO in finestra a S0 |",
          "|---|---:|---:|---:|"]
    for cosa in ("iwm",) + MATCHING:
        base = blocco(coppie(P, cosa))
        a0, n0, _ = media_scenari(cosa, False)
        a1, n1, _ = media_scenari(cosa, True)
        L.append("| {} | {} (n {:,}) | {} (n {:,}) | {} (n {:,}) |".format(
            "vs IWM" if cosa == "iwm" else "vs " + cosa, pct(base["mean"] if base else None),
            base["n"] if base else 0, pct(a0), n0, pct(a1), n1))
    L += ["", "Negli scenari contro M_mom i terminati usano il peer M_size: senza serie non c'è r12.", "",
          "### Limite dei vivi non osservati (addendum 3 §8)", "",
          "USCITO_DOPO nella cella: n_u = {:,}. media_k = m − k · n_u / (n_v + n_u).".format(n_u), "",
          "| confronto | m | k = 5 | k = 10 | k = 20 | k* |", "|---|---:|---:|---:|---:|---:|"]
    lim_out = {}
    for cosa in ("iwm",) + MATCHING:
        d = st["iwm"] if cosa == "iwm" else st[cosa]["main"]
        lm = limite(d)
        if not lm:
            continue
        righe, kstar = lm
        lim_out[cosa] = {"media_k": righe, "k_star": kstar}
        L.append("| {} | {} | {} | {} | {} | {} |".format(
            "vs IWM" if cosa == "iwm" else "vs " + cosa, pct(righe[0.0]), pct(righe[0.05]), pct(righe[0.10]),
            pct(righe[0.20]), "{:.1f} punti".format(kstar * 100) if kstar is not None else "— (m ≤ 0)"))
    L.append("")

    L += ["## 7. Criterio secondario (svedese, addendum 1 §6)", "",
          "*Il test svedese sta in un repo separato: <https://github.com/WilliePim/fi-insider-scanner>.*", "",
          "> **INCONCLUSIVO — copertura 54,4% < 60%**, scritto prima dei rendimenti. I pezzi, per confronto:", "",
          "| pezzo | valore |", "|---|---|",
          "| P vs IWM: media, t CR1 | {} , {} |".format(pct(p_iwm["mean"] if p_iwm else None), num(p_iwm["t_cr1"] if p_iwm else None)),
          "| C vs peer ({}): media, t CR1 | {} , {} |".format(c_ref, pct(c_blk["mean"] if c_blk else None), num(c_blk["t_cr1"] if c_blk else None)),
          "| P vs IWM con i terminati a S_zero | {} |".format(pct(s_zero_iwm)),
          "| MDE di P (2,80 · SE CR1) | {} |".format(pct(mde)),
          "| IC bootstrap semplice di P | {} – {} |".format(pct(p_iwm["ci_lo"] if p_iwm else None), pct(p_iwm["ci_hi"] if p_iwm else None)), ""]

    riuso = {}
    for m in MATCHING:
        usati = collections.Counter(e["legs"][(m, "primario")][2] for e in P
                                    if (m, "primario") in e["legs"] and e["legs"][(m, "primario")][0] is not None)
        riuso[m] = (sum(usati.values()), len(usati), max(usati.values()) if usati else 0)
    L += ["## 8. Diagnostica", "",
          "| | |", "|---|---:|",
          "| emittenti nel pool (ADR-005: 4.765 attesi) | {:,} |".format(len(pool.ciks))]
    for k, v in sorted(diag.items()):
        L.append("| {} | {:,} |".format(k, v))
    for m in MATCHING:
        L.append("| {} cella P: coppie, peer distinti, riuso massimo | {:,} / {:,} / {:,} |".format(m, *riuso[m]))
    L += ["", "| banda | stato della gamba evento | eventi |", "|---|---|---:|"]
    for (b, s_), v in sorted(stati.items()):
        L.append("| {} | `{}` | {:,} |".format(b, s_, v))
    L += ["", "| banda | matching | quiet | esito della gamba del peer | coppie |", "|---|---|---|---|---:|"]
    for (b, key, fl), v in sorted(esclusi.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        L.append("| {} | {} | {} | `{}` | {:,} |".format(b, key[0], key[1], fl, v))
    L += ["", "| banda | matching | quiet | peer trovato | eventi |", "|---|---|---|---|---:|"]
    for (b, key, ok), v in sorted(abbinati.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        L.append("| {} | {} | {} | {} | {:,} |".format(b, key[0], key[1], "sì" if ok else "no", v))
    L += ["", "## 9. Scelte d'implementazione non fissate dalle pre-registrazioni", "",
          "Dichiarate nel docstring di `step2_analysis.py`, prima del primo rendimento:", "",
          "- ticker del peer: fra i ticker del CIK nel corpus con serie in `prices/`, il più recente;",
          "- D non di borsa: close all'ultima sessione ≤ D, azioni con `filed` ≤ D esatto;",
          "- standardizzazione di M_mom con sd di popolazione (ddof = 0);",
          "- cap dell'evento non ricalcolabile: distanza con la cap della fascia (contata sopra);",
          "- peer finito prima dell'uscita: ultimo close piatto; peer fermo più di 5 sessioni: coppia esclusa;",
          "- terminati in finestra: peer M_size con la cap insider in entrambi i matching; cambio a s0;",
          "- giuntura: primo ticker di oggi, nell'ordine delle submissions, che riprende entro 5 sessioni.", "",
          "## 10. Cosa manca in questo passo", "",
          "- **Closed period** (passo 4): richiede gli shard delle submissions non in cache; script separato.",
          "- **Passo 5**: solo se il verdetto primario è REGGE.", ""]

    (OUT / "report.md").write_text("\n".join(L), encoding="utf-8")

    with (OUT / "eventi.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cik", "banda", "stato", "filed", "D", "cap", "cap_ric", "r12", "stato_gamba", "flag",
                    "r_e", "r_iwm", "peer_size", "r_size", "peer_mom", "r_mom", "p1_size", "p2_size",
                    "p1_mom", "p2_mom", "cluster", "score_v3"])
        for e in eventi:
            ls, lm = e["legs"].get(("M_size", "primario")), e["legs"].get(("M_mom", "primario"))
            w.writerow([e["cik"], e["banda"], e["stato"], e["filed"], e["D"], e["cap"], e["cap_ric"], e["r12"],
                        e["stato_gamba"], e["flag"] or "", e["r_e"], e.get("r_iwm"),
                        ls[2] if ls else "", ls[0] if ls else "", lm[2] if lm else "", lm[0] if lm else "",
                        e["placebo"].get(("M_size", "P1")), e["placebo"].get(("M_size", "P2")),
                        e["placebo"].get(("M_mom", "P1")), e["placebo"].get(("M_mom", "P2")),
                        (e["v3"] or {}).get("cluster"), (e["v3"] or {}).get("score")])
    numeri = {"verdetto": {"riga": riga, "esito": esito, "motivo": motivo, "sel": sel, "Q": q,
                           "r0_cambia": r0_cambia},
              "celle": {n: {"iwm": t["iwm"], **{m: t[m] for m in MATCHING}} for n, t in tab.items()},
              "differenza_size_mom": d_diff, "copertura": copertura, "stati_cella_P": dict(cp),
              "limite_k": {k: {"media_k": {str(kk): vv for kk, vv in v["media_k"].items()}, "k_star": v["k_star"]}
                           for k, v in lim_out.items()},
              "terminati": [{k: t[k] for k in ("cik", "filed", "classe", "scenario", "r_stock", "r_peer",
                                               "r_iwm", "flags", "peer_cik")} for t in terminati],
              "secondario": {"mde_P": mde, "s_zero_iwm": s_zero_iwm}}
    (OUT / "numbers.json").write_text(json.dumps(numeri, indent=1, default=str), encoding="utf-8")
    print("{} — {}{} -- scritto {}".format(esito, riga, (": " + motivo) if motivo else "", OUT / "report.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
