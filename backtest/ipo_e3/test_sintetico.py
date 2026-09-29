"""E3 su dati SINTETICI: classificazione rotta / forte / intermedia, coerenza della serie, statistica e verdetto.

Il codice di E3 legge prezzi dall'archivio EODHD (`market_data.api`, licenza d'uso personale, non ridistribuibile)
e prospetti da EDGAR. Qui le funzioni pure girano su IPO inventate — ticker AAA … EEE, CIK fittizi 0000000001 …,
prezzi scritti a mano — senza archivio e senza rete:

    python backtest/ipo_e3/test_sintetico.py
"""
from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "tests")]

from harness import check, report  # noqa: E402

import analisi as A  # noqa: E402
import casi as K  # noqa: E402


# ------------------------------------------------------------------- calendario --
def sedute(n, inizio=dt.date(2019, 1, 2)):
    out, d = [], inizio
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


IDS = sedute(420)
PRIMA = 5                                    # prima barra: seduta 5; la copertina dice la seduta 4


def riga(cik, codice):
    return {"cik": cik, "nome": codice + " INC (sintetica)", "anno": "2019", "forma": "424B4",
            "data_prospetto": IDS[PRIMA - 1], "codice": codice, "prima_barra": IDS[PRIMA], "mercato": "NASDAQ",
            "costituita_fuori_usa": ""}


def prospetto(prezzo=10.0, lockup=180):
    return {"esito": "letto", "prezzo": prezzo, "lockup_giorni": lockup, "data_copertina": IDS[PRIMA - 1],
            "lockup_durate": {str(lockup): 1}, "azioni_offerte": 1_000_000, "azioni_dopo": 10_000_000}


def serie(prezzi_da_prima, splits=()):
    """close allineate al calendario: None prima della prima barra, poi i prezzi dati, poi l'ultimo ripetuto."""
    close = [None] * PRIMA + list(prezzi_da_prima)
    close += [close[-1]] * (len(IDS) - len(close))
    vol = [None if c is None else 100_000.0 for c in close]
    return (close, list(close), vol, list(splits), IDS[-1]), None


def lineare(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


#  scadenza del lock-up: copertina + 180 giorni, portata sulla prima seduta; controllo = S + 10
S = next(i for i, d in enumerate(IDS) if d >= (dt.date.fromisoformat(IDS[PRIMA - 1]) + dt.timedelta(days=180)).isoformat())
C_ = S + K.CONTROLLO
DURATA = C_ - PRIMA + 1

SERIE = {
    "AAA": serie(lineare(10.5, 6.0, DURATA) + lineare(6.0, 7.0, 60)),       # rotta: -40% al controllo
    "BBB": serie(lineare(11.0, 16.0, DURATA)),                               # forte: mai sotto 10
    "CCC": serie([10.5, 9.5] + lineare(9.5, 9.0, DURATA - 2)),               # intermedia: -10%
    "DDD": serie(lineare(40.0, 42.0, DURATA)),                               # prima chiusura 4x il collocamento
    "EEE": serie(lineare(21.0, 24.0, DURATA), splits=[(IDS[PRIMA + 20], 0.5)]),   # raggruppamento 1:2 dopo l'IPO
}
ser_di = SERIE.__getitem__

x = K.valuta(riga("0000000001", "AAA"), prospetto(), IDS, ser_di)
check("AAA: -40% alla data di controllo -> rotta", x["esito"] == "classificata" and x["gruppo"] == "rotta", x)
check("AAA: S e data di controllo = S + 10", x["S"] == IDS[S] and x["controllo"] == IDS[C_], (x["S"], x["controllo"]))
check("AAA: ingresso A = prima seduta dopo la data di scadenza",
      x["ingresso_A"] == next(d for d in IDS if d > x["scadenza"]), (x["scadenza"], x["ingresso_A"]))
check("AAA: ingresso C = S + 63", x["ingresso_C"] == IDS[S + K.C_SEDUTE], x["ingresso_C"])
check("AAA: la regola B decide o forza, mai oltre S + 126",
      x["esito_B"] in ("REGOLA", "FORZATO") and K.B_PRIMA <= x["offset_B"] <= K.B_FORZATO, (x["esito_B"], x["offset_B"]))

x = K.valuta(riga("0000000002", "BBB"), prospetto(), IDS, ser_di)
check("BBB: mai sotto il collocamento fino al controllo -> forte, entra al controllo",
      x["gruppo"] == "forte" and x["ingresso_forte"] == IDS[C_], x)

x = K.valuta(riga("0000000003", "CCC"), prospetto(), IDS, ser_di)
check("CCC: sotto il collocamento ma sopra -30% -> intermedia", x["gruppo"] == "intermedia", x)

x = K.valuta(riga("0000000004", "DDD"), prospetto(), IDS, ser_di)
check("DDD: prima chiusura 4x il collocamento -> fuori (ADR-051)",
      x["esito"] == "fuori" and "incoerente" in x["motivo"] and x["rapporto_prima_chiusura"] == 4.0, x)

x = K.valuta(riga("0000000005", "EEE"), prospetto(), IDS, ser_di)
check("EEE: raggruppamento 1:2 dopo la prima barra -> collocamento riportato a 20, forte (ADR-052)",
      x["gruppo"] == "forte" and abs(x["rapporto_prima_chiusura"] - 21.0 / 20.0) < 1e-9, x)

p = prospetto(); p["lp_unita"] = True
check("common units di una LP/LLC: fuori (decisione della fermata 1)",
      K.valuta(riga("0000000006", "AAA"), p, IDS, ser_di)["esito"] == "fuori")
p = prospetto(); p["lockup_giorni"] = None
check("lock-up non trovato: fuori", "lock-up" in K.valuta(riga("0000000007", "AAA"), p, IDS, ser_di)["motivo"])


# ----------------------------------------------------------- statistica e verdetto --
def cella(per_anno):
    return A.statistiche({a: v for a, v in per_anno.items()})


rng = random.Random(3)
#  Come la cella delle rotte: 17 casi in 7 anni -> criterio 1 falso -> INCONCLUSIVO qualunque sia il segno.
rotte = {2012: [0.10], 2014: [-0.05, -0.27], 2015: [0.25, 0.39], 2017: [-0.28, -0.44], 2018: [-0.22, -0.74, -0.30],
         2019: [0.33], 2021: [-0.31, -0.57, -0.22, -0.14, 1.23, -0.88]}
c = cella(rotte)
check("statistiche: 17 casi, 7 anni", c["casi"] == 17 and c["anni"] == 7, (c["casi"], c["anni"]))
placebo = cella({a: [v - 0.01 for v in vs] for a, vs in rotte.items()})
check("popolazione rara (17 casi, 7 anni): INCONCLUSIVO", A.verdetto(c, placebo)[0] == "INCONCLUSIVO")

#  Cella grande, mediana negativa, pochi vincitori grossi: t fra 1 e 2 ma mediana < 0 -> NON REGGE.
forti = {a: [-0.10] * 20 + [1.5] * (2 if a % 2 else 1) for a in range(2012, 2025)}
c = cella(forti)
pl = cella({a: [0.0] * 21 + [-0.05] for a in range(2012, 2025)})
check("cella grande con mediana < 0: NON REGGE anche con media positiva", A.verdetto(c, pl)[0] == "NON REGGE",
      (c["mediana"], c["media_delle_medie"], c["t"]))

#  Tutti e cinque i criteri veri -> REGGE; stesso ma placebo piu' alto -> NON REGGE.
buoni = {a: [0.04 + rng.uniform(-0.01, 0.01) for _ in range(10)] for a in range(2012, 2025)}
c = cella(buoni)
basso = cella({a: [rng.uniform(-0.02, 0.02) for _ in range(10)] for a in range(2012, 2025)})
check("130 casi in 13 anni, tutti positivi, placebo ~ 0: REGGE", A.verdetto(c, basso)[0] == "REGGE", A.verdetto(c, basso))
alto = cella({a: [0.2 + rng.uniform(-0.3, 0.3) for _ in range(10)] for a in range(2012, 2025)})
check("stessa cella, placebo con media piu' alta: NON REGGE", A.verdetto(c, alto)[0] == "NON REGGE")

#  Mediana > 0, media delle medie > 0, t fra 1 e 2 -> INCONCLUSIVO.
misti = {a: ([0.08] * 10 if a % 2 == 0 else [0.01] * 6 + [-0.115] * 4) for a in range(2012, 2025)}   # medie 8% / -4%
c = cella(misti)
check("t per anno fra 1 e 2 con mediana > 0: INCONCLUSIVO",
      1.0 <= (c["t"] or 0) < 2.0 and A.verdetto(c, basso)[0] == "INCONCLUSIVO", (c["t"], A.verdetto(c, basso)[0]))

if __name__ == "__main__":
    sys.exit(report("TEST SINTETICI DI E3 PASSATI"))
