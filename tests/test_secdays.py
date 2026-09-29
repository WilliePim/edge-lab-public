"""Prove sul calendario dei depositi EDGAR.

Le date NON sono verificate a memoria: si verificano le PROPRIETA' della
regola. «Labor Day e' il 2026-09-07» sarebbe un test che ripete l'errore del
codice se il codice sbaglia; «Labor Day e' il primo lunedi' di settembre» no.

Le due eccezioni sono i due casi che hanno un aggancio esterno: il 2026-07-03,
che il commento in `scan.py` cita come il 403 «benigno» del primo giro
pianificato, e il 2021-12-31, che e' il difetto trovato scrivendo questa suite.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner import secdays as S

YEARS = range(2015, 2031)


# ------------------------------------------------- le regole, come proprieta'

def test_weekday_rules():
    for y in YEARS:
        h = {v: k for k, v in S.federal_holidays(y).items()}

        labor = h["Labor Day"]
        check("{}: Labor Day e' un lunedi' di settembre".format(y),
              labor.weekday() == 0 and labor.month == 9, str(labor))
        check("{}: ...ed e' il PRIMO".format(y), labor.day <= 7, str(labor))

        tg = h["Thanksgiving"]
        check("{}: Thanksgiving e' un giovedi' di novembre".format(y),
              tg.weekday() == 3 and tg.month == 11, str(tg))
        check("{}: ...ed e' il QUARTO".format(y), 22 <= tg.day <= 28, str(tg))

        mlk = h["Martin Luther King"]
        check("{}: MLK e' il terzo lunedi' di gennaio".format(y),
              mlk.weekday() == 0 and mlk.month == 1 and 15 <= mlk.day <= 21,
              str(mlk))

        mem = h["Memorial Day"]
        check("{}: Memorial Day e' l'ultimo lunedi' di maggio".format(y),
              mem.weekday() == 0 and mem.month == 5
              and (mem + timedelta(days=7)).month == 6, str(mem))

        col = h["Columbus Day"]
        check("{}: Columbus Day e' il secondo lunedi' di ottobre".format(y),
              col.weekday() == 0 and col.month == 10 and 8 <= col.day <= 14,
              str(col))


def test_observed_never_on_a_weekend():
    """Una festa osservata non cade mai di sabato o domenica: per questo esiste
    lo spostamento. Se questa cade, lo spostamento e' rotto."""
    for y in YEARS:
        for d, name in S.federal_holidays(y).items():
            check("{} {}: non e' un fine settimana".format(y, name),
                  d.weekday() < 5, "{} ({})".format(d, d.strftime("%a")))


def test_juneteenth_only_from_2021():
    for y in range(2015, 2021):
        check("{}: Juneteenth non era festa federale".format(y),
              "Juneteenth" not in S.federal_holidays(y).values())
    for y in range(2021, 2031):
        check("{}: Juneteenth e' festa federale".format(y),
              "Juneteenth" in S.federal_holidays(y).values())


# ------------------------------------------------------- i due casi ancorati

def test_independence_day_2026_shifts_back():
    """Il 4 luglio 2026 e' un sabato, quindi si osserva venerdi' 3.

    E' il giorno che il commento in scan.py cita come 403 benigno del primo
    giro pianificato: la regola deve riconoscerlo.
    """
    check("il 2026-07-04 e' un sabato", date(2026, 7, 4).weekday() == 5)
    check("PROVA POSITIVA: il 2026-07-03 e' Independence Day osservato",
          S.reason(date(2026, 7, 3)) == "Independence Day",
          S.reason(date(2026, 7, 3)))
    check("...e non e' un giorno di deposito",
          not S.is_filing_day(date(2026, 7, 3)))


def test_new_year_shifts_into_the_previous_year():
    """Capodanno di sabato slitta al 31 dicembre PRECEDENTE.

    Il difetto trovato scrivendo questa suite: la ricerca guardava solo
    `federal_holidays(day.year)`, e una festa del 31 dicembre appartiene
    all'anno DOPO. Capodanno 2022 era un sabato, quindi il 2021-12-31 era
    chiuso e veniva contato come buco.
    """
    check("il 2022-01-01 e' un sabato", date(2022, 1, 1).weekday() == 5)
    check("PROVA POSITIVA: il 2021-12-31 e' riconosciuto come Capodanno",
          S.holiday_name(date(2021, 12, 31)) == "Capodanno",
          str(S.holiday_name(date(2021, 12, 31))))
    check("...e non e' un giorno di deposito",
          not S.is_filing_day(date(2021, 12, 31)))


# ------------------------------------------------------------ giorni di deposito

def test_is_filing_day():
    check("un mercoledi' normale e' un giorno di deposito",
          S.is_filing_day(date(2026, 9, 9)))
    check("sabato no", not S.is_filing_day(date(2026, 9, 5)))
    check("domenica no", not S.is_filing_day(date(2026, 9, 6)))
    check("Labor Day no", not S.is_filing_day(date(2026, 9, 7)))
    check("una chiusura per ordine esecutivo no",
          not S.is_filing_day(date(2025, 1, 9)))


def test_closures_are_consistent():
    """La lista osservata non deve sovrapporsi alla regola ne' contenere
    fine settimana: se lo facesse, sarebbe scritta male o ridondante."""
    for iso, why in S.CLOSURES.items():
        d = date.fromisoformat(iso)
        check("chiusura {} e' un giorno lavorativo".format(iso),
              d.weekday() < 5, d.strftime("%a"))
        check("chiusura {} non e' gia' una festa federale".format(iso),
              S.holiday_name(d) is None, str(S.holiday_name(d)))
        check("chiusura {} ha una ragione scritta".format(iso), bool(why))


# ----------------------------------------------------------- classificazione

def test_why_missing():
    today = date(2026, 9, 10)

    kind, why = S.why_missing(date(2026, 9, 7), today)
    check("Labor Day -> festivo", kind == S.FESTIVO, kind)
    check("...con il nome", why == "Labor Day", why)

    kind, _ = S.why_missing(date(2025, 1, 9), today)
    check("lutto nazionale -> chiusura", kind == S.CHIUSURA, kind)

    kind, _ = S.why_missing(today, today)
    check("il giorno del giro -> non ancora pubblicato",
          kind == S.NON_ANCORA, kind)

    kind, _ = S.why_missing(date(2026, 9, 11), today)
    check("un giorno futuro -> non ancora pubblicato",
          kind == S.NON_ANCORA, kind)

    kind, _ = S.why_missing(date(2026, 8, 13), today)
    check("PROVA POSITIVA: un giovedi' normale non letto -> ILLEGGIBILE",
          kind == S.ILLEGGIBILE, kind)

    kind, _ = S.why_missing(date(2026, 9, 5), today)
    check("sabato -> weekend", kind == S.WEEKEND, kind)


def test_classify():
    today = date(2026, 9, 10)
    groups = S.classify(
        ["2026-09-07", "2026-09-10", "2026-08-13", "2025-01-09"], today
    )
    check("un solo festivo", [d for d, _ in groups[S.FESTIVO]] == ["2026-09-07"],
          str(groups[S.FESTIVO]))
    check("una sola chiusura",
          [d for d, _ in groups[S.CHIUSURA]] == ["2025-01-09"],
          str(groups[S.CHIUSURA]))
    check("un solo non-ancora",
          [d for d, _ in groups[S.NON_ANCORA]] == ["2026-09-10"],
          str(groups[S.NON_ANCORA]))
    check("UN SOLO BUCO VERO su quattro date",
          [d for d, _ in groups[S.ILLEGGIBILE]] == ["2026-08-13"],
          str(groups[S.ILLEGGIBILE]))
    check("accetta anche oggetti date",
          S.classify([date(2026, 9, 7)], today)[S.FESTIVO][0][0]
          == "2026-09-07")


def test_run_header_carries_the_breakdown():
    """L'archivio deve conservare la RAGIONE, non solo la data.

    E `index_unavailable` non cambia significato: le righe scritte prima di
    questo lavoro restano confrontabili con quelle scritte dopo.
    """
    from form4_scanner.observations import run_header

    h = run_header(date(2026, 9, 10), 60, "sha", "now", {}, {},
                   index_unavailable=["2026-09-07", "2026-09-10", "2026-08-13"])

    check("index_unavailable conserva TUTTE le date",
          h["index_unavailable"]
          == ["2026-09-07", "2026-09-10", "2026-08-13"],
          str(h["index_unavailable"]))
    check("index_unreadable tiene solo il buco vero",
          h["index_unreadable"] == ["2026-08-13"], str(h["index_unreadable"]))
    check("index_not_filing_day porta data e ragione",
          h["index_not_filing_day"]
          == [{"date": "2026-09-07", "reason": "Labor Day"}],
          str(h["index_not_filing_day"]))
    check("index_not_yet tiene il giorno del giro",
          h["index_not_yet"] == ["2026-09-10"], str(h["index_not_yet"]))


test_weekday_rules()
test_observed_never_on_a_weekend()
test_juneteenth_only_from_2021()
test_independence_day_2026_shifts_back()
test_new_year_shifts_into_the_previous_year()
test_is_filing_day()
test_closures_are_consistent()
test_why_missing()
test_classify()
test_run_header_carries_the_breakdown()

if __name__ == "__main__":
    sys.exit(report("ALL SEC-CALENDAR TESTS PASSED"))
