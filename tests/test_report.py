"""Il rapporto giornaliero: che cosa finisce nel file che legge un umano.

`report.py` e' il modulo piu' lungo del pacchetto e quasi nessuna delle sue righe era
coperta: l'unica suite che lo importava esercitava due funzioni su ventitre'. Qui si
chiama `write_daily` con due schede finte e si guarda il file prodotto -- niente rete,
nessun client (la colonna `emissione` resta spenta, come quando `anthropic` non c'e').

Serve anche da rete di sicurezza: il rapporto e' testo, e un rifacimento che lo cambia
senza accorgersene si vede qui.
"""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.cluster import IssuerCluster
from form4_scanner.flags import Card
from form4_scanner.parse import Transaction
from form4_scanner.report import write_daily

GIORNO = date(2026, 9, 18)


def txn(cik="1111111", accession="0001-26-000001", giorno=date(2026, 9, 15)):
    return Transaction(
        accession=accession, filed_at=giorno, issuer_cik="777", issuer_name="Acme Inc",
        ticker="ACME", owner_cik=cik, owner_name="Rossi Mario", is_director=True,
        is_officer=False, is_ten_pct=False, officer_title="", txn_date=giorno,
        code="P", acquired_disposed="A", shares=1000.0, price=10.0, value=10_000.0,
        shares_after=5000.0, direct=True, is_derivative=False, plan_10b5_1=False,
        txn_index=1)


def carta(ticker="ACME", punteggio=2, bloccata=False):
    c = Card(ticker=ticker, issuer_name=f"{ticker} Inc", issuer_cik="777",
             v3={"score": punteggio, "cluster": False, "director": True,
                 "no_10pct": True, "terreno": False})
    c.context = {"_total_value": 10_000.0, "_first_buy": "2026-09-15",
                 "_market_cap": 400e6, "survivability": "net cash"}
    c.inputs = {"cluster": {"buyers_in_window": 1}}
    return c


with tempfile.TemporaryDirectory() as tmp:
    stato = Path(tmp) / "state"
    rapporti = Path(tmp) / "reports"
    cluster = IssuerCluster(issuer_cik="777", issuer_name="Acme Inc", ticker="ACME",
                            txns=[txn()])

    print("[report] il giro scrive un file che si puo' leggere")
    percorso, nuovi, ripetuti = write_daily(
        [carta()], rapporti, GIORNO, stato, 60,
        funnel={"form4_filings_parsed": 10, "issuers_evaluated": 1},
        edgar={"network": 12, "cache": 340, "backoff": 0, "fail": 0},
        seconds=42.0, missing_index=["2026-09-07"], clusters=[cluster],
        ticker_status={"risolti": 1}, min_cap=50e6, max_cap=2e9, client=None)
    testo = percorso.read_text(encoding="utf-8")

    check("il file porta la data nel nome", percorso.name == "daily_2026-09-18.md",
          percorso.name)
    check("la prima scheda e' nuova", (nuovi, ripetuti) == (1, 0), str((nuovi, ripetuti)))
    check("il titolo c'e'", testo.startswith("#") or "# Form 4 — 2026-09-18" in testo,
          testo[:80])
    check("la finestra e' dichiarata", "Finestra 60 giorni" in testo)
    check("l'universo dice le fasce, non due numeri nudi",
          "fasce **micro, small**" in testo, testo[:400])
    check("il titolo valutato compare", "ACME" in testo)
    check("il giorno senza indice e' scritto, non taciuto", "2026-09-07" in testo,
          "manca la riga del giorno non osservato")
    check("le statistiche EDGAR finiscono nel rapporto", "340" in testo and "12" in testo)

    print("[report] un secondo giro sugli stessi acquisti non li chiama nuovi")
    _p2, nuovi2, ripetuti2 = write_daily(
        [carta()], rapporti, date(2026, 9, 19), stato, 60,
        clusters=[cluster], client=None)
    check("la stessa accession e' gia' vista", (nuovi2, ripetuti2) == (0, 1),
          str((nuovi2, ripetuti2)))

    print("[report] una scheda vetata non entra nell'elenco")
    class Veto:
        blocked = True
        verdict = "BLOCKED"
        reasons = ["424B5 filed 3d after the buy"]

        def summary(self):
            return "BLOCKED: 424B5 filed 3d after the buy"

    vetata = carta(ticker="VETO")
    vetata.dilution = Veto()
    #  Il veto e' spento per default (dilution.veto_attivo): il comportamento storico si prova accendendolo.
    os.environ["EDGE_LAB_DILUTION_VETO"] = "1"
    _p3, nuovi3, _r3 = write_daily([vetata], rapporti, date(2026, 9, 20), stato, 60,
                                   clusters=[cluster], client=None)
    testo3 = _p3.read_text(encoding="utf-8")
    check("una vetata non conta come nuova", nuovi3 == 0, str(nuovi3))
    #  Vetata non vuol dire nascosta: il nome esce con la ragione, fuori dalle
    #  tabelle. Un veto silenzioso sarebbe indistinguibile da un titolo che non
    #  ha mai comprato.
    check("...ma compare col motivo, fuori dalle tabelle",
          "**VETO**" in testo3 and "BLOCKED" in testo3, testo3[-400:])
    check("...e non in una riga di tabella", not any(
        r.startswith("|") and "VETO" in r for r in testo3.splitlines()), "riga di tabella")
    del os.environ["EDGE_LAB_DILUTION_VETO"]

    print("[report] veto spento (default): la stessa scheda non e' fermata ne' nascosta")
    rapporti_off = Path(tmp) / "reports_off"
    stato_off = Path(tmp) / "state_off"
    _p4, nuovi4, _r4 = write_daily([vetata], rapporti_off, date(2026, 9, 20), stato_off, 60,
                                   clusters=[cluster], client=None)
    testo4 = _p4.read_text(encoding="utf-8")
    check("veto spento: nessuna sezione dei fermati", "Fermati dal cancello" not in testo4, testo4[-400:])
    check("veto spento: il nome e' nell'elenco", any(
        r.startswith("|") and "VETO" in r for r in testo4.splitlines()), testo4[-600:])
    check("veto spento: l'avviso dice che il veto e' spento", "spento" in testo4, testo4[:400])

sys.exit(report("ALL REPORT TESTS PASSED"))
