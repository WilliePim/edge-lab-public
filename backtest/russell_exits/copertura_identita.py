"""Russell 2000, uscite verso il basso — quanta identità è risolta, per anno, fra i casi e fra i peer.

L'identità di una riga di un fondo è «risolta» quando il nome porta a un CIK e il prezzo implicito (valore diviso
azioni) coincide con la chiusura non rettificata del ticker a quella data entro il 3% (pre-registrazione §3). Senza
identità risolta il titolo non ha prezzi, non ha bilanci e non ha depositi: **non può stare né fra i casi né fra i
peer**, quindi il campione si assottiglia.

Serve saperlo per anno, perché la copertura non è uniforme: nelle istantanee vecchie manca il CUSIP e l'abbinamento
riesce solo per nome. È la stessa causa per cui i falsi positivi del 2016 e del 2017 sembravano molti — il
classificatore non riusciva a leggere EDGAR per quei titoli.

**Casi** = uscite verso il basso secondo la definizione dell'addendum 1. **Peer** = titoli rimasti in IWM, che
formano l'universo di confronto. Per ciascuno: quanti sono e quanti hanno identità verificata.

    python backtest/russell_exits/copertura_identita.py            # 2015-2018, gli anni in questione
    python backtest/russell_exits/copertura_identita.py 2015 2025  # un intervallo qualsiasi
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", HERE):
    sys.path.insert(0, str(p))

import falsi_positivi as FP  # noqa: E402

RISULTATI = HERE / "risultati"
STATI_CASO = ("basso",)


#  Le due verifiche d'identità: con Yahoo (pre-registrata, `verifica_identita.py`) e con l'archivio EODHD
#  (`verifica_identita_eodhd.py`), che conserva i delistati che Yahoo perde.
FILE_IDENTITA = {"yahoo": "identita.csv", "eodhd": "identita_eodhd.csv"}


def esiti_identita(istantanea: str, fonte: str = "yahoo") -> dict[str, str]:
    """chiave -> esito della verifica d'identità per quell'istantanea."""
    fuori = {}
    with (FP.STATE / FILE_IDENTITA[fonte]).open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["istantanea"] == istantanea:
                fuori[FP.chiave(r)] = r["esito"]
    return fuori


def copertura(anno: int) -> dict:
    A = FP.Anno(anno, con_capitale=False)         # senza XBRL: qui conta l'identità, non la quota precisa
    per_fonte = {f: esiti_identita("IWM_" + A.da, f) for f in FILE_IDENTITA
                 if (FP.STATE / FILE_IDENTITA[f]).exists()}
    casi, peer = [], []
    for k in A.az_m:
        stato, _q, _m, _c = A.classe(k, per_emittente=True)
        (casi if stato in STATI_CASO else peer).append(k)

    def conta(chiavi, esiti):
        verificate = sum(1 for k in chiavi if esiti.get(k, "").startswith("VERIFICATA"))
        return {"totale": len(chiavi), "identita_risolta": verificate,
                "quota": round(verificate / len(chiavi), 3) if chiavi else None}

    return {"anno": anno, "istantanea_marzo": A.da, "istantanea_dopo": A.a,
            **{f: {"casi": conta(casi, e), "peer": conta(peer, e)} for f, e in per_fonte.items()}}


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    da, a = (int(args[0]), int(args[1])) if len(args) >= 2 else (2015, 2018)
    fuori = []
    for anno in range(da, a + 1):
        if not (FP.HOLD / "IWM_{}-03-31.csv".format(anno)).exists():
            print("{}: senza istantanea di marzo, saltato".format(anno))
            continue
        try:
            fuori.append(copertura(anno))
        except (FileNotFoundError, KeyError) as e:
            print("{}: non calcolabile ({})".format(anno, e))
    if not fuori:
        return 1

    print("%-6s %-12s | %-34s | %-34s" % ("anno", "dopo", "casi: Yahoo -> EODHD", "peer: Yahoo -> EODHD"))
    for r in fuori:
        y, e = r.get("yahoo"), r.get("eodhd")
        def cella(parte):
            a, b = (y or {}).get(parte, {}), (e or {}).get(parte, {})
            return "%4d: %4.0f%% -> %4.0f%%" % (a.get("totale", 0), 100 * (a.get("quota") or 0), 100 * (b.get("quota") or 0))
        print("%-6d %-12s | %-34s | %-34s" % (r["anno"], r["istantanea_dopo"], cella("casi"), cella("peer")))

    righe = ["# Copertura dell'identità risolta, per anno: Yahoo e archivio EODHD", "",
             "Generato da `python backtest/russell_exits/copertura_identita.py {} {}`. ".format(da, a)
             + "Identità risolta = nome → CIK e prezzo implicito coerente con la chiusura grezza entro il 3% "
             + "(pre-registrazione §3). Senza identità il titolo non ha prezzi né bilanci: esce dal campione. "
             + "Casi = uscite verso il basso con la definizione di ADR-039. Nessun rendimento calcolato.", "",
             "| anno | istantanea «dopo» | casi | identità con Yahoo | con EODHD | peer | identità con Yahoo | con EODHD |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in fuori:
        y, e = r.get("yahoo", {}), r.get("eodhd", {})
        righe.append("| {} | {} | {} | {} ({:.0%}) | **{} ({:.0%})** | {} | {} ({:.0%}) | **{} ({:.0%})** |".format(
            r["anno"], r["istantanea_dopo"],
            y["casi"]["totale"], y["casi"]["identita_risolta"], y["casi"]["quota"] or 0,
            e["casi"]["identita_risolta"], e["casi"]["quota"] or 0,
            y["peer"]["totale"], y["peer"]["identita_risolta"], y["peer"]["quota"] or 0,
            e["peer"]["identita_risolta"], e["peer"]["quota"] or 0))
    (RISULTATI / "copertura_identita.md").write_text("\n".join(righe) + "\n", encoding="utf-8")
    (RISULTATI / "copertura_identita.json").write_text(json.dumps(fuori, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
