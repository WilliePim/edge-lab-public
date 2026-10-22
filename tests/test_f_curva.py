"""La lettura della curva GSW nel Test F (`backtest/drawdown_alpha/test_f.py`, ADR-071).

Il file della Fed ha una riga anche nei giorni festivi, con `NA` al posto dei parametri. Fino al 04-10-2026 il segnale
dei tassi prendeva la riga del giorno t - 11 anche se era `NA` e restava mancante: 30 fini mese senza composito, 23
delle quali nel periodo del Test G. La regola corretta: l'ultimo giorno valido precedente, mai uno successivo, non piu'
vecchio di sette giorni. Righe sintetiche, nessuna rete e nessun archivio.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest" / "drawdown_alpha"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report, section

import test_f as F


def _niente_rete(*_a, **_k):
    raise AssertionError("questa suite non deve leggere dati")


for _nome in ("fred", "prices", "gsw", "ebp"):
    setattr(F.api, _nome, _niente_rete)

NA = float("nan")


def riga(giorno: dt.date, b0: float) -> dict:
    """Una riga della curva: piatta al livello b0 (per cento), oppure `NA` come nei festivi."""
    return {"date": giorno, "BETA0": b0, "BETA1": NA if b0 != b0 else 0.0, "BETA2": NA if b0 != b0 else 0.0,
            "BETA3": NA, "TAU1": NA if b0 != b0 else 1.0, "TAU2": NA}


VEN, LUN, MAR = dt.date(2020, 1, 17), dt.date(2020, 1, 20), dt.date(2020, 1, 21)
#  2020-01-20 e' Martin Luther King: nel file vero la riga c'e' ed e' NA. E' il caso della fine mese 2020-01-31.
CURVA = [riga(dt.date(2020, 1, 16), 1.0), riga(VEN, 2.0), riga(LUN, NA), riga(MAR, 9.0)]


def test_riga_valida():
    section("riga NA: ultimo giorno valido precedente")
    check("2020-01-31 meno 11 giorni e' il 2020-01-20", dt.date(2020, 1, 31) - dt.timedelta(days=F.RITARDO_GSW) == LUN)
    r = F.riga_gsw(CURVA, LUN)
    check("PROVA POSITIVA: riga NA del lunedi' festivo -> la riga del venerdi' prima",
          r is not None and r["date"] == VEN, str(r))
    check("...e MAI quella del martedi' dopo", r is not None and r["BETA0"] == 2.0, str(r))
    r = F.riga_gsw(CURVA, VEN)
    check("giorno valido: la sua riga, come prima della correzione", r is not None and r["date"] == VEN, str(r))
    r = F.riga_gsw(CURVA, dt.date(2020, 1, 19))
    check("giorno senza riga (domenica): l'ultima riga precedente", r is not None and r["date"] == VEN, str(r))
    check("prima dell'inizio della curva: mancante", F.riga_gsw(CURVA, dt.date(2020, 1, 15)) is None)
    check("BETA0 None conta come NA",
          F.riga_gsw([riga(VEN, 2.0), {"date": LUN, "BETA0": None}], LUN)["date"] == VEN)


def test_limite_di_eta():
    section("limite di eta': sette giorni, poi resta mancante")
    check("il limite e' sette giorni", F.MAX_GIORNI_CURVA == 7)
    buco = [riga(dt.date(2020, 1, 10), 2.0)] + [riga(dt.date(2020, 1, 10) + dt.timedelta(days=k), NA) for k in range(1, 12)]
    r = F.riga_gsw(buco, dt.date(2020, 1, 17))
    check("sette giorni esatti: ancora buona", r is not None and r["date"] == dt.date(2020, 1, 10), str(r))
    check("otto giorni: mancante, non una riga vecchia", F.riga_gsw(buco, dt.date(2020, 1, 18)) is None)
    check("solo righe NA: mancante", F.riga_gsw([riga(LUN, NA)], LUN) is None)


class _Dati:
    gsw = CURVA
    dtb3 = [(VEN, 1.50), (MAR, 8.00)]


def test_segnale():
    section("il segnale dei tassi alla fine mese 2020-01-31")
    fm = dt.date(2020, 1, 31)
    l = F.segnale_ntfs(_Dati, fm, "gsw")
    check("versione tutta GSW: il segnale esiste (prima era mancante)", l.acceso is not None, str(l))
    check("...e dichiara la curva del venerdi'", "2020-01-17" in l.dati and "2020-01-21" not in l.dati, l.dati)
    l = F.segnale_ntfs(_Dati, fm)
    check("versione DTB3: il segnale esiste", l.acceso is not None, str(l))
    check("...con la curva e il DTB3 del venerdi', non quelli del martedi'", l.dati.count("2020-01-17") == 2
          and "8.00" not in l.dati, l.dati)
    check("curva piatta al 2% contro DTB3 1,50% di sconto: spread positivo, segnale spento",
          l.acceso is False and l.valore is not None and 0.4 < l.valore < 0.5, str(l.valore))

    class Vuoti:
        gsw = [riga(LUN, NA)]
        dtb3 = _Dati.dtb3
    check("nessuna riga valida entro sette giorni: il segnale resta mancante (fail-closed)",
          F.segnale_ntfs(Vuoti, fm).acceso is None and F.segnale_ntfs(Vuoti, fm, "gsw").acceso is None)


test_riga_valida()
test_limite_di_eta()
test_segnale()

if __name__ == "__main__":
    sys.exit(report("ALL TEST-F CURVE TESTS PASSED"))
