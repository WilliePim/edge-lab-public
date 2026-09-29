"""Test dei filtri di bilancio del backtest Russell. Fatti sintetici. Convenzione del repo: harness.

    python backtest/russell_exits/test_filtri.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests"))

from harness import check, report  # noqa: E402

import filtri_xbrl as F  # noqa: E402


def cf(**tags):
    """tags: nome → lista di (start, end, val, filed[, accn]); start None = istantaneo."""
    ug = {}
    for tag, righe in tags.items():
        ug[tag] = {"units": {"USD": [{"start": r[0], "end": r[1], "val": r[2], "filed": r[3],
                                      "accn": r[4] if len(r) > 4 else r[3]} for r in righe]}}
        if ug[tag]["units"]["USD"] and ug[tag]["units"]["USD"][0]["start"] is None:
            for x in ug[tag]["units"]["USD"]:
                x.pop("start")
    return {"facts": {"us-gaap": ug}}


OCF = "NetCashProvidedByUsedInOperatingActivities"

# ---- 12 mesi: anno + progressivo − progressivo dell'anno prima
c = cf(**{OCF: [("2023-01-01", "2023-12-31", 100, "2024-02-20"),
                ("2024-01-01", "2024-03-31", 30, "2024-05-02"),
                ("2023-01-01", "2023-03-31", 10, "2023-05-03"),
                ("2023-01-01", "2023-03-31", 12, "2024-05-02")]})
v, fine, m = F.dodici_mesi(c, [OCF], "2024-05-10")
check("anno + progressivo − progressivo precedente (con la riesposizione più recente)", v == 100 + 30 - 12 and fine == "2024-03-31", str((v, fine, m)))
v, fine, m = F.dodici_mesi(c, [OCF], "2024-04-30")
check("prima del deposito del trimestre: solo l'anno fiscale", v == 100 and fine == "2023-12-31", str((v, fine, m)))
v, fine, m = F.dodici_mesi(c, [OCF], "2024-02-20")
check("deposito nello stesso giorno della data: escluso (filed < data)", v is None, str((v, fine, m)))
v, fine, m = F.dodici_mesi(c, [OCF], "2025-03-01")
check("dati più vecchi di 270 giorni: non verificabile", v is None and "vecchi" in m, str((v, fine, m)))

c = cf(**{OCF: [("2023-01-01", "2023-03-31", 10, "2023-05-01"), ("2023-04-01", "2023-06-30", 20, "2023-08-01"),
                ("2023-07-01", "2023-09-30", 30, "2023-11-01"), ("2023-10-01", "2023-12-31", 40, "2024-02-01")]})
v, fine, m = F.dodici_mesi(c, [OCF], "2024-03-01")
check("senza anno fiscale: quattro trimestri consecutivi", v == 100 and m == "quattro trimestri", str((v, fine, m)))
c = cf(**{OCF: [("2023-01-01", "2023-03-31", 10, "2023-05-01"), ("2023-01-01", "2023-03-31", 10, "2023-05-02"),
                ("2023-07-01", "2023-09-30", 30, "2023-11-01"), ("2023-10-01", "2023-12-31", 40, "2024-02-01")]})
v, fine, m = F.dodici_mesi(c, [OCF], "2024-03-01")
check("trimestri duplicati o non consecutivi: non si sommano", v is None, str((v, fine, m)))

# ---- filtro 1
c = cf(**{OCF: [("2023-01-01", "2023-12-31", -5, "2024-02-20")]})
check("flusso di cassa negativo: non passa", F.f1_flusso_cassa(c, "2024-04-30")[0] is False)
check("tag mancante: non verificabile", F.f1_flusso_cassa(cf(), "2024-04-30")[0] is None)

# ---- filtro 2
base = {"Assets": [(None, "2023-12-31", 1000, "2024-02-20")],
        "CashAndCashEquivalentsAtCarryingValue": [(None, "2023-12-31", 50, "2024-02-20")],
        "LongTermDebtNoncurrent": [(None, "2023-12-31", 200, "2024-02-20")],
        "OperatingIncomeLoss": [("2023-01-01", "2023-12-31", 40, "2024-02-20")],
        "DepreciationDepletionAndAmortization": [("2023-01-01", "2023-12-31", 20, "2024-02-20")]}
esito, nota = F.f2_leva(cf(**base), "2024-04-30")
check("debito netto 150 / EBITDA 60 = 2,5 < 3: passa (debito corrente assente con bilancio letto)", esito is True, nota)
b2 = dict(base, OperatingIncomeLoss=[("2023-01-01", "2023-12-31", 20, "2024-02-20")])
esito, nota = F.f2_leva(cf(**b2), "2024-04-30")
check("150 / 40 = 3,75: non passa", esito is False, nota)
b3 = dict(base, OperatingIncomeLoss=[("2023-01-01", "2023-12-31", -30, "2024-02-20")])
esito, nota = F.f2_leva(cf(**b3), "2024-04-30")
check("EBITDA ≤ 0 con debito netto > 0: non passa", esito is False, nota)
b4 = dict(base, CashAndCashEquivalentsAtCarryingValue=[(None, "2023-12-31", 500, "2024-02-20")])
check("cassa netta: passa senza EBITDA", F.f2_leva(cf(**{k: v for k, v in b4.items() if k in ("Assets", "CashAndCashEquivalentsAtCarryingValue", "LongTermDebtNoncurrent")}), "2024-04-30")[0] is True)
b5 = {k: v for k, v in base.items() if k != "Assets"}
check("debito corrente assente senza bilancio letto: non verificabile", F.f2_leva(cf(**b5), "2024-04-30")[0] is None)

# ---- filtro 3
def az(*righe, tass="dei", tag="EntityCommonStockSharesOutstanding"):
    return {"facts": {tass: {tag: {"units": {"shares": [{"end": e, "val": v, "filed": f, "accn": a} for e, v, f, a in righe]}}}}}


c = az(("2023-04-20", 100, "2023-05-01", "q1"), ("2024-04-20", 104, "2024-05-01", "q2"))
check("+4% in 12 mesi: passa", F.f3_azioni(c, "2024-05-10")[0] is True, F.f3_azioni(c, "2024-05-10")[1])
c = az(("2023-04-20", 100, "2023-05-01", "q1"), ("2024-04-20", 106, "2024-05-01", "q2"))
check("+6%: non passa", F.f3_azioni(c, "2024-05-10")[0] is False)
c = az(("2023-04-20", 60, "2023-05-01", "q1"), ("2023-04-20", 40, "2023-05-01", "q1"), ("2024-04-20", 100, "2024-05-01", "q2"))
check("classi dello stesso deposito sommate: 60 + 40 → 100, +0%", F.f3_azioni(c, "2024-05-10")[0] is True, F.f3_azioni(c, "2024-05-10")[1])
c = az(("2023-04-20", 100, "2023-05-01", "q1"), ("2024-04-20", 200, "2024-05-01", "q2"))
check("raddoppio con split 2:1 fra le date: corretto, passa", F.f3_azioni(c, "2024-05-10", lambda a, b: 2.0)[0] is True)
check("raddoppio senza split: non passa", F.f3_azioni(c, "2024-05-10")[0] is False)
c = az(("2024-01-20", 100, "2024-02-01", "q1"), ("2024-04-20", 100, "2024-05-01", "q2"))
check("nessun deposito 9-15 mesi prima: non verificabile", F.f3_azioni(c, "2024-05-10")[0] is None)
c = az(("2023-04-20", 100, "2023-05-01", "q1"), ("2024-04-20", 104, "2024-05-12", "q2"))
check("deposito dopo la data: ignorato, resta solo quello vecchio → non verificabile", F.f3_azioni(c, "2024-05-10")[0] is None)


# ---- plausibilità del fallback us-gaap (ADR E3, 22-23/09/2026)
def cf_plausibilita(us_gaap=(), dei=(), flottante=()):
    """us_gaap/dei: (end, val, filed[, accn]) per le azioni. flottante: (end, val, filed) per EntityPublicFloat."""
    def righe_azioni(voci):
        fatti = []
        for x in voci:
            e, v, f = x[0], x[1], x[2]
            a = x[3] if len(x) > 3 else f
            fatti.append({"end": e, "val": v, "filed": f, "accn": a})
        return {"units": {"shares": fatti}}
    facts = {"us-gaap": {}, "dei": {}}
    if us_gaap:
        facts["us-gaap"]["CommonStockSharesOutstanding"] = righe_azioni(us_gaap)
    if dei:
        facts["dei"]["EntityCommonStockSharesOutstanding"] = righe_azioni(dei)
    if flottante:
        facts["dei"]["EntityPublicFloat"] = {"units": {"USD": [{"end": e, "val": v, "filed": f} for e, v, f in flottante]}}
    return {"facts": facts}


#  livello 1: un dei futuro esiste, il rapporto decide
c = cf_plausibilita(us_gaap=[("2019-06-17", 100, "2019-12-09")],
                    dei=[("2020-02-19", 134448344, "2020-02-19")])
per, tag = F.azioni_per_deposito(c, "2019-12-24")
check("livello 1 — rapporto 100/134.448.344 sotto il 20%: scartato", per == {}, str(per))
esito, nota = F.stato_plausibilita(c, "2019-12-24", 100)
check("livello 1 — stato coerente", esito == "scartato" and "dei futuro" in nota, nota)

c = cf_plausibilita(us_gaap=[("2013-03-31", 8000000, "2014-02-04")],
                    dei=[("2025-10-31", 8100000, "2025-11-05")])
per, tag = F.azioni_per_deposito(c, "2014-02-05")
check("livello 1 — rapporto 8.000.000/8.100.000 sopra il 20%: accettato", per == {("2014-02-04", "2014-02-04"): 8000000.0}, str(per))

#  livello 2: nessun dei futuro, un flottante vicino verifica il prezzo implicito
c = cf_plausibilita(us_gaap=[("2014-06-30", 5160971, "2014-09-29")],
                    flottante=[("2014-12-26", 34000000, "2015-01-01")])
per, tag = F.azioni_per_deposito(c, "2014-09-30")
check("livello 2 — prezzo implicito $6,59/azione, plausibile: accettato",
      per == {("2014-09-29", "2014-09-29"): 5160971.0}, str(per))
esito, nota = F.stato_plausibilita(c, "2014-09-30", 5160971)
check("livello 2 — stato ok, dal flottante", esito == "ok" and "flottante" in nota, nota)

c = cf_plausibilita(us_gaap=[("2019-06-17", 100, "2019-12-09")],
                    flottante=[("2019-12-01", 1700000000, "2020-01-01")])
per, tag = F.azioni_per_deposito(c, "2019-12-24")
check("livello 2 — prezzo implicito $17.000.000/azione, assurdo: scartato", per == {}, str(per))

#  livello 3: né dei futuro né flottante — soglia assoluta, Chewy come esempio del guscio
c = cf_plausibilita(us_gaap=[("2019-06-17", 100, "2019-12-09")])
per, tag = F.azioni_per_deposito(c, "2019-12-24")
check("livello 3 — Chewy: 100 azioni sotto la soglia assoluta, nessun altro segnale: scartato", per == {}, str(per))
esito, nota = F.stato_plausibilita(c, "2019-12-24", 100)
check("livello 3 — stato coerente sul caso Chewy", esito == "scartato" and "soglia assoluta" in nota, nota)

c = cf_plausibilita(us_gaap=[("2013-03-31", 587866, "2016-02-11")])
per, tag = F.azioni_per_deposito(c, "2016-02-23")
check("livello 3 — 587.866 azioni sopra soglia, nessun altro segnale: accettato ma non verificato",
      per == {("2016-02-11", "2016-02-11"): 587866.0}, str(per))
esito, nota = F.stato_plausibilita(c, "2016-02-23", 587866)
check("livello 3 — stato «non_verificato», non scartato", esito == "non_verificato", nota)

if __name__ == "__main__":
    sys.exit(report("TEST FILTRI PASSATI"))
