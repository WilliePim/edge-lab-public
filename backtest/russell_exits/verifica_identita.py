"""Russell 2000, uscite verso il basso — verifica dell'identità con il prezzo implicito (piano B2, passo 4).

Per ogni riga di IWM: prezzo implicito = valore della posizione / azioni. Per ogni candidato (in ordine) e ogni suo
ticker con serie Yahoo: chiusura non rettificata alla data dell'istantanea = `Close` (rettificata per split) × prodotto
dei frazionamenti successivi alla data. L'identità è VERIFICATA se lo scarto è entro il 3%; VERIFICATA_SENZA_SPLIT se lo
è la `Close` così com'è (tabella dei frazionamenti di Yahoo incompleta); altrimenti NON_VERIFICATA con il motivo. Vale
il primo candidato verificato.

Lettura in due passate per stare in poca memoria: prima si raccolgono le date che servono per ogni ticker, poi ogni file
si legge una volta tenendo solo quelle chiusure e i frazionamenti. `serie_allineata` dà la serie completa come array
compatti (NaN dove manca la barra) per `analisi.py`.

Output `state/backfill/russell/identita.csv` e riepilogo per istantanea. Nessuna rete.

    python backtest/russell_exits/verifica_identita.py
"""
from __future__ import annotations

import bisect
import collections
import csv
import json
import math
import sys
from array import array
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import identita as I  # noqa: E402
import scarica_ohlcv as O  # noqa: E402

STATE = ROOT / "state" / "backfill" / "russell"
OUT = STATE / "identita.csv"
RIEPILOGO = HERE / "risultati" / "identita_riepilogo.json"
TOLLERANZA = 0.03
GIORNI_MAX = 7
NAN = float("nan")


def _float(s):
    try:
        f = float(s)
    except (TypeError, ValueError):
        return NAN
    return f if math.isfinite(f) else NAN


def chiusure_alle_date(path, giorni):
    """{giorno: (chiusura non rettificata, chiusura Yahoo)} per le date richieste (ultima barra ≤ giorno entro 7 giorni)."""
    richieste = sorted(giorni)
    limiti = [(date.fromisoformat(g) - timedelta(days=GIORNI_MAX)).isoformat() for g in richieste]
    primo = limiti[0] if limiti else "9999"
    ultime = {}                       # giorno -> (data barra, close)
    split = []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        testata = next(r)
        i_d, i_c, i_s = testata.index("Date"), testata.index("Close"), testata.index("Stock Splits")
        j = 0
        for riga in r:
            d = riga[i_d]
            c = _float(riga[i_c])
            s = _float(riga[i_s])
            if s == s and s > 0:
                split.append((d, s))
            if c != c or d < primo:
                continue
            while j < len(richieste) and richieste[j] < d:
                j += 1
            #  la barra d vale per ogni giorno richiesto g con g - 7 giorni <= d <= g (le barre successive la sostituiscono)
            for jj in range(j, len(richieste)):
                if d < limiti[jj]:
                    break
                ultime[richieste[jj]] = (d, c)
    out = {}
    for g, (db, c) in ultime.items():
        fattore = 1.0
        for sd, s in split:
            if sd > db:
                fattore *= s
        out[g] = (c * fattore, c)
    return out


def serie_allineata(path, ids):
    """(close, adj, vol) come array('d') allineati a `ids` (NaN dove manca), frazionamenti [(data, rapporto)], ultima data."""
    pos = {d: i for i, d in enumerate(ids)}
    n = len(ids)
    close, adj, vol = array("d", [NAN]) * n, array("d", [NAN]) * n, array("d", [NAN]) * n
    split, ultima = [], None
    with Path(path).open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        testata = next(r)
        i_d, i_c, i_a, i_v, i_s = (testata.index(k) for k in ("Date", "Close", "Adj Close", "Volume", "Stock Splits"))
        for riga in r:
            d = riga[i_d]
            s = _float(riga[i_s])
            if s == s and s > 0:
                split.append((d, s))
            c = _float(riga[i_c])
            if c == c:
                ultima = d
            k = pos.get(d)
            if k is not None:
                close[k], adj[k], vol[k] = c, _float(riga[i_a]), _float(riga[i_v])
    return close, adj, vol, split, ultima


def main() -> int:
    idx = I.carica_indice()
    man = json.loads(O.MANIFEST.read_text(encoding="utf-8"))
    ok = {t for t, v in man.items() if v["esito"] == "OK"}
    with (STATE / "identita_candidati.csv").open(encoding="utf-8", newline="") as fh:
        righe = list(csv.DictReader(fh))
    servono = collections.defaultdict(set)
    for r in righe:
        giorno, anno = r["istantanea"].split("_")[1], int(r["istantanea"].split("_")[1][:4])
        r["_giorno"], r["_anno"] = giorno, anno
        for c in [x for x in r["candidati"].split(";") if x]:
            for t in O.ticker_per_cik(idx, c, anno):
                if t in ok:
                    servono[t].add(giorno)
    print("ticker da leggere:", len(servono), flush=True)
    prezzi = {}
    for n, (t, giorni) in enumerate(sorted(servono.items())):
        prezzi[t] = chiusure_alle_date(O.percorso(t), giorni)
        if n % 500 == 0:
            print("  letti", n, flush=True)

    righe_out = []
    riep = collections.defaultdict(collections.Counter)
    valore = collections.defaultdict(collections.Counter)
    for r in righe:
        giorno, anno = r["_giorno"], r["_anno"]
        try:
            implicito = float(r["valore"]) / float(r["azioni"])
        except (ValueError, ZeroDivisionError):
            implicito = None
        esito, cik, tick, scarto, motivo = "NON_VERIFICATA", "", "", "", ""
        cands = [c for c in r["candidati"].split(";") if c]
        if not cands:
            motivo = "NESSUN_CANDIDATO"
        elif implicito is None or implicito <= 0:
            motivo = "PREZZO_IMPLICITO_ASSENTE"
        else:
            visto, migliore = False, None
            for c in cands:
                for t in O.ticker_per_cik(idx, c, anno):
                    g = (prezzi.get(t) or {}).get(giorno)
                    if not g:
                        continue
                    visto = True
                    grezza, yahoo = g
                    e1 = abs(math.log(grezza / implicito)) if grezza > 0 else 9.0
                    e2 = abs(math.log(yahoo / implicito)) if yahoo > 0 else 9.0
                    if migliore is None or min(e1, e2) < migliore:
                        migliore = min(e1, e2)
                    if e1 <= TOLLERANZA or e2 <= TOLLERANZA:
                        esito = "VERIFICATA" if e1 <= TOLLERANZA else "VERIFICATA_SENZA_SPLIT"
                        cik, tick, scarto = c, t, round(min(e1, e2), 4)
                        break
                if esito != "NON_VERIFICATA":
                    break
            if esito == "NON_VERIFICATA":
                motivo = "PREZZO_DIVERSO" if visto else "NESSUN_PREZZO_YAHOO"
                scarto = round(migliore, 4) if migliore is not None else ""
        riep[r["istantanea"]][esito if esito != "NON_VERIFICATA" else motivo] += 1
        valore[r["istantanea"]]["totale"] += float(r["valore"] or 0)
        if esito != "NON_VERIFICATA":
            valore[r["istantanea"]]["verificato"] += float(r["valore"] or 0)
        righe_out.append({"istantanea": r["istantanea"], "nome": r["nome"], "titolo": r["titolo"], "cusip": r["cusip"],
                          "azioni": r["azioni"], "valore": r["valore"], "prezzo_implicito": implicito,
                          "chiave": r["chiave"], "metodo": r["metodo"], "candidati": r["candidati"], "esito": esito,
                          "motivo": motivo, "cik": cik, "ticker": tick, "scarto_log": scarto})
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe_out[0]))
        w.writeheader()
        w.writerows(righe_out)
    out = {k: {"righe": dict(v), "quota_valore_verificato": round(valore[k]["verificato"] / valore[k]["totale"], 4)}
           for k, v in sorted(riep.items())}
    RIEPILOGO.parent.mkdir(parents=True, exist_ok=True)
    RIEPILOGO.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out.items():
        n = sum(v["righe"].values())
        ver = v["righe"].get("VERIFICATA", 0) + v["righe"].get("VERIFICATA_SENZA_SPLIT", 0)
        print("{} righe {} verificate {} ({:.1%}) valore verificato {:.1%} | {}".format(
            k, n, ver, ver / n, v["quota_valore_verificato"], dict(v["righe"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
