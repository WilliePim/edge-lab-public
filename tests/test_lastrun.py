"""Prove sull'esito dell'ultimo giro.

Questo file esiste perche' qualcosa FUORI dal repository lo legge -- uno script
di notifica, un collegamento, domani forse un'altra macchina. Un campo che
cambia nome o un percorso che diventa relativo rompono un consumatore che non
gira nella suite, e si scopre dal fatto che una mattina non arriva l'avviso.

Le due cose che vanno tenute ferme: i percorsi sono ASSOLUTI, e `index_unreadable`
contiene SOLO i buchi veri. Un festivo dentro quel campo farebbe suonare la
notifica ogni Labor Day.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner import lastrun


def test_write_and_read():
    with tempfile.TemporaryDirectory() as td:
        st = Path(td)
        p = lastrun.write(
            st, date(2026, 9, 12),
            report="reports/daily_2026-09-12.md",
            spinoff_watch="reports/spinoffs/_watch.md",
            verdicts="reports/verdicts_2026-09.md",
            csv="out/scan_20260912.csv",
            new=9, repeat=271, issuers_evaluated=374, seconds=626.23,
            missing_index=["2026-09-07"], sha="abc123",
        )
        check("il file sta in state/daily/last_run.json",
              p == st / "daily" / "last_run.json", str(p))

        d = lastrun.read(st)
        check("si rilegge", d is not None)
        check("la data del giro", d["run_date"] == "2026-09-12", d["run_date"])
        check("i numeri passano interi",
              (d["new"], d["repeat"], d["issuers_evaluated"]) == (9, 271, 374),
              str((d["new"], d["repeat"], d["issuers_evaluated"])))
        check("i secondi sono arrotondati a un decimale",
              d["seconds"] == 626.2, str(d["seconds"]))
        check("lo sha e' conservato", d["scanner_git_sha"] == "abc123")

        #  Il consumatore non gira nella cartella del repository: un percorso
        #  relativo lo obbligherebbe a indovinare da dove.
        for campo in ("report", "spinoff_watch", "verdicts", "csv"):
            check("{} e' un percorso assoluto".format(campo),
                  Path(d[campo]).is_absolute(), d[campo])


def test_holiday_is_not_a_gap():
    """Il campo che fa suonare la notifica non deve contenere festivi."""
    with tempfile.TemporaryDirectory() as td:
        st = Path(td)
        lastrun.write(st, date(2026, 9, 12), report="r.md",
                      missing_index=["2026-09-07",    # Labor Day
                                     "2026-09-12",    # il giorno del giro
                                     "2026-08-13"])   # buco vero
        d = lastrun.read(st)
        check("PROVA POSITIVA: il buco vero c'e'",
              d["index_unreadable"] == ["2026-08-13"], str(d["index_unreadable"]))
        check("il festivo NON e' fra i buchi",
              "2026-09-07" not in d["index_unreadable"])
        check("il giorno del giro NON e' fra i buchi",
              "2026-09-12" not in d["index_unreadable"])
        check("il festivo e' riportato con la sua ragione",
              d["index_not_filing_day"]
              == [{"date": "2026-09-07", "reason": "Labor Day"}],
              str(d["index_not_filing_day"]))


def test_watch_hits_counted_from_the_ledger():
    """I riscontri si contano dal registro, non si fanno passare.

    Il registro e' un fatto gia' su disco; chiedere il numero a chi produce il
    report vorrebbe dire cambiargli la firma per un dato che si puo' leggere.
    """
    with tempfile.TemporaryDirectory() as td:
        st = Path(td)
        led = st / "watch" / "seen.jsonl"
        led.parent.mkdir(parents=True)
        righe = [
            {"watch_id": "a", "accession": "1", "first_seen": "2026-09-12"},
            {"watch_id": "a", "accession": "2", "first_seen": "2026-09-12"},
            {"watch_id": "b", "accession": "3", "first_seen": "2026-09-01"},
            {"rotta": True},
        ]
        led.write_text(
            "\n".join(json.dumps(r) for r in righe) + "\n{ non json\n",
            encoding="utf-8")

        lastrun.write(st, date(2026, 9, 12), report="r.md")
        check("PROVA POSITIVA: conta i due di oggi",
              lastrun.read(st)["watch_hits"] == 2,
              str(lastrun.read(st)["watch_hits"]))

        lastrun.write(st, date(2026, 9, 1), report="r.md")
        check("e solo quello del primo settembre",
              lastrun.read(st)["watch_hits"] == 1)

        lastrun.write(st, date(2026, 9, 30), report="r.md")
        check("un giorno senza riscontri conta zero",
              lastrun.read(st)["watch_hits"] == 0)


def test_missing_and_broken():
    with tempfile.TemporaryDirectory() as td:
        check("stato vuoto -> None", lastrun.read(Path(td)) is None)
        p = Path(td) / "daily" / "last_run.json"
        p.parent.mkdir(parents=True)
        p.write_text("{ rotto", encoding="utf-8")
        check("file rotto -> None, non un'eccezione",
              lastrun.read(Path(td)) is None)


def test_summary():
    check("nessun giro", lastrun.summary(None) == "nessun giro registrato")
    s = lastrun.summary({"new": 9, "repeat": 271, "issuers_evaluated": 374,
                         "watch_hits": 0, "index_unreadable": []})
    check("i tre numeri, in ordine",
          s == "9 nuovi · 271 gia' visti · 374 valutati", s)
    s2 = lastrun.summary({"new": 9, "watch_hits": 2,
                          "index_unreadable": ["2026-08-13", "2026-08-20"]})
    check("la sorveglianza compare quando scatta", "SORVEGLIANZA: 2" in s2, s2)
    check("i buchi compaiono al plurale",
          "2 giorni non osservati" in s2, s2)


test_write_and_read()
test_holiday_is_not_a_gap()
test_watch_hits_counted_from_the_ledger()
test_missing_and_broken()
test_summary()

if __name__ == "__main__":
    sys.exit(report("ALL LASTRUN TESTS PASSED"))
