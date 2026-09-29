"""E3, fase 3 — i peer: universo, filtri 1-2 alla data d'ingresso, terzile del rendimento a 6 mesi, i 5 più vicini per
capitalizzazione. **Nessun rendimento dopo l'ingresso**: qui si guarda solo il prima.

Due passi, dopo `casi.py` e `filtri.py`:

    python backtest/ipo_e3/peer.py fatti     # filtri 1-2 e azioni di ogni CIK candidato, alle sole date d'ingresso
    python backtest/ipo_e3/peer.py scegli    # i peer di ogni caso (rotte a ogni ingresso, forti al controllo)

`fatti` legge ogni companyfacts una volta sola dallo zip in blocco (ADR-046) e tiene soltanto l'esito dei filtri 1-2 e
le azioni in circolazione alle date d'ingresso che servono: tenere in memoria i fatti di migliaia di società
costerebbe gigabyte.

**Universo dei peer** (fase 3 della direttiva; ADR-050):
- azioni ordinarie americane dell'archivio EODHD con CIK, quotate su una borsa (NASDAQ, NYSE, NYSE MKT/AMEX, BATS,
  NYSE ARCA): i titoli fuori borsa non sono paragonabili a un'IPO su una borsa;
- quotate da **almeno 3 anni** alla data d'ingresso, contati dalla prima barra del CIK su qualunque suo codice (un
  cambio di ticker non fa ripartire l'orologio): questo esclude da sé le IPO recenti;
- una barra entro 5 sedute dall'ingresso e una 126 sedute prima;
- filtri 1 e 2 della fase 2 alla data d'ingresso, sui fatti depositati prima (`filtri_xbrl`, invariati);
- il caso stesso escluso;
- **fuori le stesse categorie tolte dalle IPO** (decisione dell'utente alla fermata 1): SPAC, REIT, banche e casse di
  risparmio, sul codice SIC della testata di `submissions` (`universo.SIC_ESCLUSI`). Il SIC è quello di oggi, non
  quello alla data d'ingresso: limite dichiarato.

**Scelta**: terzile del rendimento dei 6 mesi prima dell'ingresso (`adjusted_close`, 126 sedute), con i tagli
calcolati sull'universo di quel giorno; fra i titoli del terzile del caso, i **5** più vicini per capitalizzazione
(distanza sul logaritmo, a parità il CIK più basso, come `russell_exits/analisi.peer_di`). Capitalizzazione =
chiusura grezza all'ingresso × azioni dell'ultimo deposito prima dell'ingresso (`dei:EntityCommonStockSharesOutstanding`,
classi sommate). Per il caso, se nessun deposito dopo il collocamento riporta le azioni, quelle in circolazione dopo
l'offerta secondo il prospetto (contato).

**Rendimento a 6 mesi del caso**: serve una barra 126 sedute prima dell'ingresso. Le IPO con lock-up corto entrano
con meno di 126 sedute di storia: il loro terzile **non è calcolabile** e il caso resta senza peer, contato. Nessuna
sostituzione: è una decisione dell'utente alla fermata 1.
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json
import math
import pickle
import sys
from array import array

import bulk
import comune as C

BORSE = frozenset({"NASDAQ", "NYSE", "NYSE MKT", "AMEX", "BATS", "NYSE ARCA"})
ANNI_QUOTAZIONE = 3
SEDUTE_6M = 126
STALE = 5
N_PEER = 5
FATTI = C.STATO / "peer_fatti.pkl"
USCITA = C.STATO / "peer.csv"
BLOCCO = 400


def anagrafica() -> tuple[dict[str, list[tuple[str, str, str]]], dict[str, str]]:
    """({cik: [(codice, prima barra, ultima barra)] su una borsa}, {cik: prima barra su qualunque codice})."""
    from market_data import api
    df = api.listings(exchange="US")
    borsa, prima = collections.defaultdict(list), {}
    for code, cik, tipo, fd, ld, venue in zip(df["code"], df["cik"], df["type"], df["first_date"], df["last_date"],
                                             df["venue"]):
        if not cik or tipo != "Common Stock" or fd is None or fd != fd:
            continue
        k = str(cik).zfill(10)
        fd, ld = str(fd)[:10], str(ld)[:10]
        prima[k] = min(prima.get(k, fd), fd)
        if (venue or "") in BORSE:
            borsa[k].append((code, fd, ld))
    return borsa, prima


def richieste() -> list[tuple[dict, str, str]]:
    """[(caso, ingresso, data)] per cui servono peer: rotte che passano i filtri a quell'ingresso, forti al controllo, e
    ogni IPO classificata alla data di controllo senza condizioni né filtri («base», la base di coorte del §8)."""
    casi = [x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8")) if x["gruppo"]]
    filtri = {(r["cik"], r["ingresso"]): r for r in csv.DictReader((C.STATO / "filtri.csv").open(encoding="utf-8"))}
    fuori = [(x, "base", x["controllo"]) for x in casi]
    for x in (x for x in casi if x["gruppo"] in ("rotta", "forte")):
        for nome in (("A", "B", "C") if x["gruppo"] == "rotta" else ("forte",)):
            data = x.get("ingresso_" + nome, "")
            f = filtri.get((x["cik"], nome))
            if data and f and f["passa"] == "sì":
                fuori.append((x, nome, data))
    return fuori


_sic: dict[str, str] = {}


def sic_escluso(cik: str) -> bool:
    """Vero se il SIC della testata di `submissions` è fra quelli esclusi dall'universo delle IPO."""
    from universo import SIC_ESCLUSI
    if cik not in _sic:
        testa = bulk._json("submissions", "CIK{}.json".format(str(cik).zfill(10))) or {}
        _sic[cik] = str(testa.get("sic") or "")
    return _sic[cik] in SIC_ESCLUSI


def candidati_a(borsa, prima, data: str) -> dict[str, str]:
    """{cik: codice} dei candidati all'universo a quella data, prima dei filtri di bilancio e dei prezzi."""
    limite = (dt.date.fromisoformat(data) - dt.timedelta(days=365 * ANNI_QUOTAZIONE)).isoformat()
    fuori = {}
    for cik, cod in borsa.items():
        if prima.get(cik, "9999") > limite:
            continue
        vivo = [c for c in cod if c[1] <= data <= c[2]]
        if vivo:
            fuori[cik] = min(vivo, key=lambda c: c[1])[0]
    return fuori


# ------------------------------------------------------------------------------------------------ fatti ---
def estrai_fatti() -> int:
    """Per ogni CIK candidato, alle date d'ingresso che gli servono: passa i filtri 1-2, e le azioni in circolazione.

    In forma compatta, perché con la base di coorte le date sono centinaia e le coppie CIK-data milioni:
    `{"date": [date ordinate], "cik": {cik: (passa, azioni)}}`, con `passa` un array di byte (1 passa, 0 no, −1 data
    non richiesta) e `azioni` un array float32 (NaN se manca), tutti e due indicizzati sulle date."""
    import filtri_xbrl as FX
    borsa, prima = anagrafica()
    date = sorted({d for _x, _n, d in richieste()})
    serve = collections.defaultdict(list)
    for j, d in enumerate(date):
        for cik in candidati_a(borsa, prima, d):
            serve[cik].append(j)
    print("{} date d'ingresso, {} CIK candidati, {} coppie CIK-data".format(
        len(date), len(serve), sum(len(v) for v in serve.values())), flush=True)
    fuori, senza = {}, 0
    for i, (cik, jj) in enumerate(sorted(serve.items()), 1):
        passa, azioni = array("b", [-1]) * len(date), array("f", [float("nan")]) * len(date)
        cf = bulk.companyfacts(cik)
        if not cf:
            senza += 1
            for j in jj:
                passa[j] = 0
        else:
            for j in jj:
                d = date[j]
                passa[j] = int(FX.f1_flusso_cassa(cf, d)[0] is True and FX.f2_leva(cf, d)[0] is True)
                per, _tag = FX.azioni_per_deposito(cf, d)
                if per:
                    azioni[j] = per[max(per)]
        fuori[cik] = (passa, azioni)
        if i % 1000 == 0:
            print("{} CIK letti, {} senza companyfacts".format(i, senza), flush=True)
    with FATTI.open("wb") as fh:
        pickle.dump({"date": date, "cik": fuori}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    print("fatti di {} CIK; {} senza companyfacts".format(len(fuori), senza))
    return 0


# ----------------------------------------------------------------------------------------------- prezzi ---
_adj: dict[str, array] = {}
_raw: dict[str, array] = {}


def carica_prezzi(codici, ids: list[str]) -> None:
    """adjusted_close e chiusura grezza, float32, allineate a `ids`. Barre pulite dell'archivio."""
    from market_data import api
    pos = {d: i for i, d in enumerate(ids)}
    n = len(ids)
    mancano = sorted({c for c in codici if c and c not in _adj})
    for i in range(0, len(mancano), BLOCCO):
        blocco = mancano[i:i + BLOCCO]
        df = api.prices(["{}.US".format(c) for c in blocco], start=ids[0], end=ids[-1], clean=True)
        for c in blocco:
            _adj[c], _raw[c] = array("f", [float("nan")]) * n, array("f", [float("nan")]) * n
        for code, d, cl, a in zip(df["code"], df["date"], df["close"], df["adjusted_close"]):
            k = pos.get(str(d)[:10])
            if k is not None and code in _adj:
                _raw[code][k] = float(cl)
                _adj[code][k] = float(a) if a == a and a is not None else float("nan")


def ultimo_prima(xs, s: int, stale: int = STALE):
    for i in range(s, max(-1, s - stale - 1), -1):
        if 0 <= i < len(xs) and xs[i] == xs[i] and xs[i] > 0:
            return float(xs[i])
    return None


def rendimento_6m(codice: str, s: int):
    a1, a0 = ultimo_prima(_adj[codice], s), ultimo_prima(_adj[codice], s - SEDUTE_6M)
    return a1 / a0 - 1.0 if (a1 and a0) else None


def terzile(v: float, tagli: tuple[float, float]) -> int:
    return 0 if v <= tagli[0] else (1 if v <= tagli[1] else 2)


def scegli() -> int:
    import filtri_xbrl as FX
    ids = C.ids()
    borsa, prima = anagrafica()
    fatti = pickle.load(FATTI.open("rb"))
    pos_data = {d: j for j, d in enumerate(fatti["date"])}
    rich = richieste()
    date = sorted({d for _x, _n, d in rich})
    candidati = {d: candidati_a(borsa, prima, d) for d in date}
    carica_prezzi({c for v in candidati.values() for c in v.values()} | {x["codice"] for x, _n, _d in rich}, ids)
    print("{} richieste su {} date; prezzi per {} codici".format(len(rich), len(date), len(_adj)), flush=True)

    universo_di: dict[str, list[dict]] = {}
    righe, conta = [], collections.Counter()
    for x, nome, data in rich:
        s = bisect.bisect_left(ids, data)
        if data not in universo_di:
            u = []
            for cik, codice in candidati[data].items():
                j, f = pos_data.get(data), fatti["cik"].get(cik)
                if j is None or f is None or f[0][j] != 1:
                    continue
                azioni = float(f[1][j])
                if not azioni == azioni or azioni <= 0 or sic_escluso(cik):
                    continue
                r6, raw = rendimento_6m(codice, s), ultimo_prima(_raw[codice], s)
                if r6 is None or not raw:
                    continue
                u.append({"cik": cik, "codice": codice, "rend_6m": r6, "cap": raw * azioni})
            universo_di[data] = u
        u = universo_di[data]
        riga = {"cik": x["cik"], "nome": x["nome"], "anno": x["anno"], "gruppo": x["gruppo"], "ingresso": nome,
                "data_ingresso": data, "universo": len(u), "rend_6m": "", "cap": "", "fonte_azioni": "",
                "terzile": "", "esito": "", "peer": ""}
        r6 = rendimento_6m(x["codice"], s)
        raw = ultimo_prima(_raw[x["codice"]], s)
        per, _t = FX.azioni_per_deposito(bulk.companyfacts(x["cik"]), data)
        dopo = sorted(k for k in per if k[0] >= x["data_collocamento"])
        azioni, fonte = (per[dopo[-1]], "XBRL") if dopo else \
            ((float(x["azioni_dopo"]), "prospetto") if x["azioni_dopo"] else (None, ""))
        cap = raw * azioni if (raw and azioni) else None
        riga["fonte_azioni"] = fonte
        if r6 is None:
            riga["esito"] = "rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia)"
        elif cap is None:
            riga["esito"] = "capitalizzazione non calcolabile"
        elif len(u) < 3 * N_PEER:
            riga["esito"] = "universo dei peer troppo piccolo ({})".format(len(u))
        else:
            valori = sorted(v["rend_6m"] for v in u)
            tagli = (valori[len(valori) // 3], valori[2 * len(valori) // 3])
            t = terzile(r6, tagli)
            cand = [v for v in u if terzile(v["rend_6m"], tagli) == t and v["cik"] != x["cik"]]
            cand.sort(key=lambda v: (abs(math.log(v["cap"]) - math.log(cap)), int(v["cik"])))
            scelti = cand[:N_PEER]
            riga.update({"rend_6m": round(r6, 6), "cap": round(cap), "terzile": t,
                         "esito": "ok" if len(scelti) == N_PEER else "meno di 5 peer",
                         "peer": json.dumps([{"cik": v["cik"], "codice": v["codice"], "cap": round(v["cap"]),
                                              "rend_6m": round(v["rend_6m"], 6)} for v in scelti])})
        conta[(x["gruppo"], nome, riga["esito"])] += 1
        righe.append(riga)
    with USCITA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)
    for k, v in sorted(conta.items()):
        print(k, v)
    return 0


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "fatti":
        raise SystemExit(estrai_fatti())
    if comando == "scegli":
        raise SystemExit(scegli())
    raise SystemExit("uso: peer.py fatti | scegli")
