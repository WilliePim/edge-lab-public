"""Passo 4 del ri-test 50-300M: closed period, con le date dei report lette su EDGAR.

Pre-registrazione §8 e ADR-011. Legge le coppie del passo 2 (`step2/eventi.csv`), le righe
insider del corpus per T, e le submissions EDGAR (`recent` + shard).

    python backtest/rematch_50_300m/step4_closed_period.py --conta   # shard necessari, zero rete
    python backtest/rematch_50_300m/step4_closed_period.py           # scarica quelli, poi misura

REGOLE (§8)
  T  = la transaction_date piu' vecchia fra le righe dell'evento.
  R  = ultima filingDate <= T fra 10-Q, 10-K, 10-KT (senza /A).
  k  = sessioni IWM in (R, T].  Dentro W  <=>  k <= W;  W = 10 principale, 5 e 20 sensibilita'.
  UNKNOWN se nessun R nei 200 giorni di calendario prima di T.
  Descrittivo: R = ultimo 8-K con item 2.02 <= T, W = 10.

SHARD. Si scaricano solo gli shard delle submissions il cui intervallo [filingFrom, filingTo]
interseca [T - 200 giorni, T] di almeno un evento. Il tetto e' il numero di shard dichiarato
al §0 della pre-registrazione (373), con contatore su disco: una chiamata oltre il tetto non
parte, e l'evento il cui shard manca va a UNKNOWN con flag. 0,15 s fra le richieste,
User-Agent dichiarato. Nessun modello linguistico.

SENZA SEL. Il passo 2 ha dato R1: nessun matching di riferimento. Il §8 chiede la misura
"contro il matching primario": si riportano vs IWM, vs M_size e vs M_mom, tutti e tre.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import step1_analysis as S1  # noqa: E402
import survival as SV  # noqa: E402

OUT = HERE / "step4"
EVENTI = HERE / "step2" / "eventi.csv"
FORME = frozenset({"10-Q", "10-K", "10-KT"})
FINESTRE = (5, 10, 20)
PRINCIPALE = 10
GIORNI_UNKNOWN = 200
TETTO = 373
CONFRONTI = (("vs IWM", "r_iwm"), ("vs M_size", "r_size"), ("vs M_mom", "r_mom"))


def f(x):
    return float(x) if x not in ("", None) else None


def carica_eventi():
    out = []
    with EVENTI.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["banda"] != "50-300M" or f(r["r_e"]) is None or f(r["r_iwm"]) is None:
                continue
            out.append({"cik": r["cik"], "filed": r["filed"], "r_e": f(r["r_e"]), "r_iwm": f(r["r_iwm"]),
                        "r_size": f(r["r_size"]), "r_mom": f(r["r_mom"])})
    return out


def meno(d, giorni):
    return (date.fromisoformat(d) - timedelta(days=giorni)).isoformat()


class Rete:
    """Tetto persistente sulle chiamate EDGAR del passo 4."""

    FILE = OUT / "edgar_calls.json"

    def __init__(self):
        from edgar_llm.config import get as env_get
        from form4_scanner.edgar import EdgarClient

        ua = env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")
        if not ua or "@" not in ua:
            raise SystemExit("serve EDGAR_USER_AGENT con nome ed email")
        self.client = EdgarClient(ua, cache_dir=SV.CACHE, min_interval=0.15)
        self.usate = json.loads(self.FILE.read_text(encoding="utf-8"))["network"] if self.FILE.exists() else 0

    def get(self, url):
        if not SV.cache_path(url).exists() and self.usate >= TETTO:
            return None
        prima = self.client.stats["network"]
        txt = self.client.get(url)
        self.usate += self.client.stats["network"] - prima
        self.FILE.parent.mkdir(parents=True, exist_ok=True)
        self.FILE.write_text(json.dumps({"network": self.usate, "tetto": TETTO}), encoding="utf-8")
        return txt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--conta", action="store_true", help="conta gli shard necessari, nessuna chiamata")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    eventi = carica_eventi()
    righe = SV.righe_insider()
    for e in eventi:
        tds = [x[0] for x in righe.get((e["cik"], e["filed"]), []) if len(x[0]) == 10]
        e["T"] = min(tds) if tds else None

    #  Shard necessari: intervallo che interseca [T - 200, T] di almeno un evento.
    necessari = {}
    for e in eventi:
        if not e["T"]:
            continue
        p = SV.cache_path(SV.SUB + "CIK{:010d}.json".format(int(e["cik"])))
        if not p.exists():
            e["senza_submissions"] = True
            continue
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        lo = meno(e["T"], GIORNI_UNKNOWN)
        for sh in d["filings"].get("files") or []:
            if (sh.get("filingTo") or "") >= lo and (sh.get("filingFrom") or "9") <= e["T"]:
                necessari[sh["name"]] = e["cik"]
    mancanti = sorted(n for n in necessari if not SV.cache_path(SV.SUB + n).exists())
    print("eventi {:,}; senza T {:,}; shard necessari {:,}, non in cache {:,}; tetto {}".format(
        len(eventi), sum(1 for e in eventi if not e["T"]), len(necessari), len(mancanti), TETTO))
    if a.conta:
        return 0

    rete = Rete() if mancanti else None
    non_scaricati = []
    for n in mancanti:
        if rete.get(SV.SUB + n) is None:
            non_scaricati.append(n)
    impronte = []
    for n in sorted(necessari):
        p = SV.cache_path(SV.SUB + n)
        if p.exists():
            impronte.append((n, hashlib.sha256(p.read_bytes()).hexdigest()))
    h = hashlib.sha256()
    for n, s in impronte:
        h.update(n.encode())
        h.update(s.encode())

    # ---------------------------------------------------------- misura
    sub = {}
    buchi = set()
    for n in non_scaricati:
        buchi.add(necessari[n])
    for e in eventi:
        e["R"], e["R202"], e["flag"] = None, None, None
        if not e["T"] or e.get("senza_submissions"):
            e["flag"] = "SENZA_T" if not e["T"] else "SENZA_SUBMISSIONS"
            continue
        if e["cik"] not in sub:
            sub[e["cik"]] = SV.submissions(e["cik"])[1]
        dep = sub[e["cik"]]
        lo = meno(e["T"], GIORNI_UNKNOWN)
        rs = [x[0] for x in dep if x[1] in FORME and lo <= x[0] <= e["T"]]
        e["R"] = max(rs) if rs else None
        r2 = [x[0] for x in dep if x[1] == "8-K" and "2.02" in x[2] and lo <= x[0] <= e["T"]]
        e["R202"] = max(r2) if r2 else None
        if e["R"] is None and e["cik"] in buchi:
            e["flag"] = "SHARD_NON_SCARICATO"

    def k(e, chiave):
        if not e.get(chiave):
            return None
        return SV.sessione(e["T"]) - SV.sessione(e[chiave])

    def gruppi(chiave, W):
        out = {"dentro": [], "fuori": [], "UNKNOWN": []}
        for e in eventi:
            kk = k(e, chiave) if e["T"] else None
            out["UNKNOWN" if kk is None else ("dentro" if kk <= W else "fuori")].append(e)
        return out

    def blk(evs, col):
        xs = [(e["r_e"] - e[col], e["cik"]) for e in evs if e[col] is not None]
        return S1.blocco([x for x, _ in xs], [g for _, g in xs]) if xs else None

    L = ["# Passo 4 — closed period", "",
         "Generato da `python backtest/rematch_50_300m/step4_closed_period.py`. Pre-registrazione §8, "
         "ADR-011. Coppie del passo 2 (cella P, 126 sessioni, gamba dell'evento valida). Modelli linguistici: "
         "token e costo **0**.", "",
         "Il passo 2 ha dato **R1**, nessun matching di riferimento: si riportano i tre confronti.", "",
         "| | |", "|---|---:|",
         "| eventi | {:,} |".format(len(eventi)),
         "| senza T | {:,} |".format(sum(1 for e in eventi if not e["T"])),
         "| shard necessari ([T − 200 giorni, T]) | {:,} |".format(len(necessari)),
         "| di cui scaricati in questo passo | {:,} |".format(len(mancanti) - len(non_scaricati)),
         "| non scaricati (tetto o errore) | {:,} |".format(len(non_scaricati)),
         "| chiamate EDGAR di questo passo, cumulate | {} / {} |".format(rete.usate if rete else 0, TETTO),
         "| impronta degli shard necessari (sha256 di nome + sha256, in ordine) | `{}` |".format(h.hexdigest()),
         ""]
    numeri = {"shard": impronte, "non_scaricati": non_scaricati, "finestre": {}}
    for chiave, titolo, finestre in (("R", "10-Q, 10-K, 10-KT", FINESTRE), ("R202", "8-K item 2.02 (descrittivo)", (PRINCIPALE,))):
        for W in finestre:
            g = gruppi(chiave, W)
            n_tot = sum(len(v) for v in g.values())
            L += ["## {} — W = {} sessioni{}".format(titolo, W, " (principale)" if chiave == "R" and W == PRINCIPALE else ""), "",
                  "Dentro {:,} · fuori {:,} · UNKNOWN {:,} ({:.1%}).".format(
                      len(g["dentro"]), len(g["fuori"]), len(g["UNKNOWN"]), len(g["UNKNOWN"]) / n_tot if n_tot else 0), "",
                  S1.TESTATA]
            numeri["finestre"]["{} W{}".format(chiave, W)] = {}
            for lato in ("dentro", "fuori"):
                for nome, col in CONFRONTI:
                    d = blk(g[lato], col)
                    numeri["finestre"]["{} W{}".format(chiave, W)]["{} {}".format(lato, nome)] = d
                    L.append(S1.riga_tab("{} {}".format(lato, nome), d))
            L.append("")
    L += ["## Flag", "", "| flag | eventi |", "|---|---:|"]
    for fl, v in sorted(collections.Counter(e["flag"] for e in eventi if e["flag"]).items()):
        L.append("| `{}` | {:,} |".format(fl, v))
    L += ["", "Potenza (pre-registrazione §10): con 1.000–1.500 eventi per lato l'MDE contro peer è 4,8–6,4%; "
          "sotto il 5% il confronto dentro/fuori non ha potenza.", ""]
    (OUT / "report.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "numbers.json").write_text(json.dumps(numeri, indent=1, default=str), encoding="utf-8")
    print("scritto {}".format(OUT / "report.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
