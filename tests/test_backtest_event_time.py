"""Il backtest event-time, sui casi che possono sbagliarsi in silenzio.

Prezzi sintetici scritti in una cartella temporanea: nessuna rete, nessuna
dipendenza dal panel reale. Quello che si verifica e' l'aritmetica -- l'excess
al centesimo, la conversione in euro, la lunghezza della curva -- e i due modi
in cui un evento puo' non essere misurabile senza che nessuno se ne accorga.
"""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

import backtest_event_time as B

TMP = Path(tempfile.mkdtemp())
B.PRICES = TMP


def write_series(ticker, start, n, fn):
    """n barre giornaliere consecutive (giorni feriali), prezzo da fn(i)."""
    rows, d, i = [], date.fromisoformat(start), 0
    while len(rows) < n:
        if d.weekday() < 5:
            rows.append("{},{}".format(d.isoformat(), fn(i)))
            i += 1
        d += timedelta(days=1)
    (TMP / "{}.csv".format(ticker)).write_text(
        "Date,adj_close\n" + "\n".join(rows) + "\n", encoding="utf-8")


#  Titolo: +10% a 21 giorni, poi piatto. Benchmark: +4% a 21, poi piatto.
#  Cambio fisso a 1.0, cosi' l'euro non muove nulla in questo primo caso.
write_series("AAA", "2020-01-01", 400,
             lambda i: 100.0 * (1.10 if i >= 22 else 1.0))
write_series("BENCH", "2020-01-01", 400,
             lambda i: 50.0 * (1.04 if i >= 22 else 1.0))
write_series("FXFLAT", "2020-01-01", 400, lambda i: 1.0)

bench = B.load_series("BENCH")
fx = B.load_series("FXFLAT")


def one(ticker="AAA", filed="2020-01-01", buyers=1):
    return {"cik": "1", "ticker": ticker, "filed": filed, "name": "X",
            "owners": ["9"], "owner": "9", "buyers": buyers, "usd": 1.0}


print("[backtest] l'excess e' giusto al centesimo")
e = one()
B.measure([e], (bench[0], bench[1], False), fx, [21, 63, 126], 0.0)
check("il titolo fa +10% a 21 giorni",
      abs(e["ret_21"] - 0.10) < 1e-9, str(e.get("ret_21")))
check("l'excess e' +6,00 punti, non +10",
      abs(e["exc_21"] - 0.06) < 1e-9, str(e.get("exc_21")))
check("a 63 giorni resta +6,00: entrambi piatti dopo",
      abs(e["exc_63"] - 0.06) < 1e-9, str(e.get("exc_63")))
check("il flag e' OK", e["flag"] == "OK", e["flag"])

print("[backtest] il costo e' un haircut sulla sola gamba titolo")
e = one()
B.measure([e], (bench[0], bench[1], False), fx, [21], 100.0)
check("netto = lordo meno l'1%",
      abs(e["excnet_21"] - (e["exc_21"] - 0.01)) < 1e-12,
      "{} vs {}".format(e.get("excnet_21"), e.get("exc_21")))

print("[backtest] conversione in euro")
#  Titolo +10% in dollari, EUR/USD +5%: in euro circa +4,8%.
write_series("USD10", "2020-01-01", 400,
             lambda i: 100.0 * (1.10 if i >= 22 else 1.0))
write_series("FXUP", "2020-01-01", 400,
             lambda i: 1.0 * (1.05 if i >= 22 else 1.0))
fxup = B.load_series("FXUP")
flat = B.load_series("BENCH")
e = one(ticker="USD10")
#  Benchmark piatto in euro, cosi' l'excess isola l'effetto cambio.
write_series("BFLAT", "2020-01-01", 400, lambda i: 50.0)
bflat = B.load_series("BFLAT")
B.measure([e], (bflat[0], bflat[1], False), fxup, [21], 0.0)
check("+10% in dollari con cambio +5% fa circa +4,8% in euro",
      abs(e["ret_21"] - (1.10 / 1.05 - 1.0)) < 1e-9, str(e.get("ret_21")))
check("...che e' fra il 4,7% e il 4,8%",
      0.047 < e["ret_21"] < 0.048, "{:.4%}".format(e["ret_21"]))

print("[backtest] storico insufficiente -> PARTIAL")
#  Serie corta: 30 barre, quindi 21 si chiude e 63 no.
write_series("SHORT", "2020-01-01", 30, lambda i: 100.0)
e = one(ticker="SHORT")
B.measure([e], (bench[0], bench[1], False), fx, [21, 63, 126], 0.0)
check("21 giorni si chiude", "exc_21" in e, str(sorted(e)))
check("63 non si chiude", "exc_63" not in e)
check("il flag dice PARTIAL", e["flag"] == "PARTIAL", e["flag"])

print("[backtest] ticker inesistente -> DELISTED_NO_DATA, nessuna eccezione")
e = one(ticker="NOSUCHTICKER")
B.measure([e], (bench[0], bench[1], False), fx, [21], 0.0)
check("flag DELISTED_NO_DATA", e["flag"] == "DELISTED_NO_DATA", e["flag"])
check("nessun rendimento scritto", "exc_21" not in e)
e = one(ticker=None)
B.measure([e], (bench[0], bench[1], False), fx, [21], 0.0)
check("anche senza ticker non solleva", e["flag"] == "DELISTED_NO_DATA", e["flag"])

print("[backtest] bootstrap: campioni identici collassano sulla media")
lo, hi = B.bootstrap_ci([0.05] * 50)
check("l'intervallo collassa sulla media",
      abs(lo - 0.05) < 1e-12 and abs(hi - 0.05) < 1e-12, "{} {}".format(lo, hi))
lo, hi = B.bootstrap_ci([0.0, 0.10] * 40)
check("...e su un campione con varianza non collassa", hi > lo, "{} {}".format(lo, hi))

print("[backtest] la curva event-time ha 127 punti e parte da zero")
e = one()
B.measure([e], (bench[0], bench[1], False), fx, [21], 0.0)
e["label"] = B.OPPORTUNISTIC
curves, counts = B.event_curve([e], (bench[0], bench[1], False), fx)
c = curves[B.OPPORTUNISTIC]
check("127 punti, da 0 a 126", len(c) == 127, str(len(c)))
check("il giorno 0 e' zero", abs(c[0]) < 1e-12, str(c[0]))
check("il giorno 21 e' l'excess a 21 giorni",
      abs(c[21] - 0.06) < 1e-9, str(c[21]))

print("[backtest] il cooldown tiene il primo della sequenza")
evs = [one(filed="2020-01-01"), one(filed="2020-02-01"),
       one(filed="2021-06-01")]
kept = B.cooldown_filter(evs, days=126)
check("due eventi su tre", len(kept) == 2, str(len(kept)))
check("il primo della sequenza e' quello tenuto",
      kept[0]["filed"] == "2020-01-01", kept[0]["filed"])
check("...e il secondo e' oltre il cooldown",
      kept[1]["filed"] == "2021-06-01", kept[1]["filed"])

print("[backtest] la mappatura a tre classi e' quella dichiarata")
check("novel finisce in UNCLASSIFIED", B.THREE[B.NOVEL] == "UNCLASSIFIED")
check("sparse finisce in UNCLASSIFIED", B.THREE[B.SPARSE] == "UNCLASSIFIED")
check("routine resta ROUTINE", B.THREE[B.ROUTINE] == "ROUTINE")
check("routine e' l'ultima nella precedenza: solo se TUTTI lo sono",
      B.PRECEDENCE[-1] == B.ROUTINE, str(B.PRECEDENCE))

if __name__ == "__main__":
    sys.exit(report("ALL BACKTEST EVENT-TIME TESTS PASSED"))
