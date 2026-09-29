"""Ri-test 50-300M su dati SINTETICI: statistica, regola del verdetto, sopravvivenza, excess sul calendario comune.

Il codice del ri-test legge all'import il panel prezzi (`state/backfill/prices/`, derivato da Yahoo, non
pubblicato). Questo test lo sostituisce con serie inventate scritte in una cartella temporanea:

- `IWM`: 100 x 1,001^i su 400 sedute feriali dal 2020-01-02;
- `EURUSD=X`: 1,25 costante (il cambio si elide nell'excess, ma il percorso in euro gira);
- `AAA`: 50 fino alla seduta 199, 60 dopo (un salto noto);
- `BBB`: come IWM ma finisce alla seduta 150 (delistato dentro la finestra);
- `CCC`: presente, ma usato con un deposito troppo vicino alla fine dei dati.

Nessun ticker, prezzo o CIK reale; nessuna rete. Si lancia con:

    python backtest/rematch_50_300m/test_sintetico.py
"""
from __future__ import annotations

import datetime as dt
import math
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]

from harness import check, report  # noqa: E402

import backtest_event_time as B  # noqa: E402


# ------------------------------------------------------------------ dati sintetici --
def sedute(n, inizio=dt.date(2020, 1, 2)):
    out, d = [], inizio
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


N = 400
IDS_SINT = sedute(N)
SERIE = {
    "IWM": [100 * 1.001 ** i for i in range(N)],
    "EURUSD=X": [1.25] * N,
    "AAA": [50.0 if i < 200 else 60.0 for i in range(N)],
    "BBB": [100 * 1.001 ** i for i in range(151)],
    "CCC": [20.0] * N,
}

TMP = Path(tempfile.mkdtemp(prefix="edge_lab_sintetico_"))
for nome, px in SERIE.items():
    righe = ["Date,Adj Close"] + ["{},{:.6f}".format(d, p) for d, p in zip(IDS_SINT, px)]   # formato del panel
    (TMP / "{}.csv".format(nome)).write_text("\n".join(righe) + "\n", encoding="utf-8")

#  Il panel vero sta sotto state/: qui lo si punta alla cartella temporanea PRIMA di importare il ri-test.
B.PRICES = TMP

import step1_analysis as S1  # noqa: E402
import survival as SV  # noqa: E402
import step2_analysis as S2  # noqa: E402

check("il calendario comune e' quello sintetico", S1.IDS == IDS_SINT and S1.LAST == N - 1)

# ---------------------------------------------------------------------- CR1 e IC --
S1.verifica_cr1()                       # ADR-021: un cluster per osservazione -> t CR1 == t iid, altrimenti SystemExit
check("CR1 con un cluster per osservazione coincide con la t iid", True)

xs = [0.10, 0.12, -0.02, 0.05, 0.07, 0.01, 0.03, -0.04, 0.09, 0.02, 0.06, 0.00]
gruppi = ["AAA", "AAA", "BBB", "BBB", "CCC", "CCC", "DDD", "DDD", "EEE", "EEE", "FFF", "FFF"]
m, se, t, G = S1.cr1(xs, gruppi)
check("sotto MIN_CLUSTER gruppi nessuna t con cluster", se is None and t is None and G == 6, (se, t, G))

xs2 = [((i * 37) % 11 - 4) / 100.0 for i in range(40)]
g2 = ["G{:02d}".format(i // 2) for i in range(40)]         # 20 gruppi da 2
m2, se2, t2, G2 = S1.cr1(xs2, g2)
media = sum(xs2) / len(xs2)
somme = {}
for x, g in zip(xs2, g2):
    somme[g] = somme.get(g, 0.0) + (x - media)
se_mano = math.sqrt(G2 / (G2 - 1) * sum(v * v for v in somme.values()) / len(xs2) ** 2)
check("CR1 = formula della pre-registrazione §3.1, calcolata a mano", abs(se2 - se_mano) < 1e-15, (se2, se_mano))
check("t CR1 = media / SE", abs(t2 - media / se_mano) < 1e-12)
check("t(19; 0,975) con Cornish-Fisher entro 1e-3 dal valore esatto 2,0930", abs(S1.t_inv_975(19) - 2.0930) < 1e-3,
      S1.t_inv_975(19))
d = S1.blocco(xs2, g2)
check("IC CR1 contiene la media", d["cr1_lo"] < d["mean"] < d["cr1_hi"], d)
check("IC bootstrap per emittente contiene la media", d["cb_lo"] <= d["mean"] <= d["cb_hi"], d)

# -------------------------------------------------------- regola del verdetto (R0'-R6) --
def cella(media, lo, hi, t=1.0):
    return {"mean": media, "cr1_lo": lo, "cr1_hi": hi, "t_cr1": t}


zero = cella(0.002, -0.01, 0.014)                 # placebo ~ 0: IC include 0 e |media| < 1,5 punti
non_zero = cella(0.03, 0.01, 0.05, 3.0)           # placebo lontano da 0
pos = cella(0.03, 0.01, 0.05, 3.0)                # effetto che sopravvive
pos_debole = cella(0.018, -0.009, 0.047, 1.3)     # positivo ma IC include 0

check("placebo con IC che include 0 e |media| < 1,5 punti: ~ 0", S2.circa_zero(zero))
check("placebo con |media| >= 1,5 punti: non ~ 0 anche se l'IC include 0",
      not S2.circa_zero(cella(0.02, -0.01, 0.05)))
check("placebo senza IC: non ~ 0", not S2.circa_zero(cella(0.0, None, None)))


def st(p1_size, p2_size, p2_mom, main_size, main_mom):
    return {"M_size": {"P1": p1_size, "P2": p2_size, "main": main_size},
            "M_mom": {"P2": p2_mom, "main": main_mom}}


#  Com'e' andato il ri-test vero (step2/report.md): P1 di M_size ~ 0, P2 no per entrambi -> nessun matching credibile.
s = st(zero, non_zero, non_zero, pos_debole, pos_debole)
q, sel = S2.scegli_sel(s)
check("P2 non ~ 0 per entrambi i matching: nessun matching di riferimento", sel is None and q == {"M_size": False, "M_mom": False})
check("-> R1, INCONCLUSIVO (la riga del ri-test)", S2.verdetto(s, q, sel, False)[:2] == ("R1", "INCONCLUSIVO"))

s = st(zero, zero, zero, pos, pos)
q, sel = S2.scegli_sel(s)
check("tutti i placebo ~ 0 e l'effetto sopravvive in entrambi: R4 REGGE", S2.verdetto(s, q, sel, False)[:2] == ("R4", "REGGE"))
check("stessa situazione ma la sopravvivenza cambia il segno: R0', INCONCLUSIVO",
      S2.verdetto(s, q, sel, True)[:2] == ("R0'", "INCONCLUSIVO"))
s = st(zero, zero, zero, pos, pos_debole)
q, sel = S2.scegli_sel(s)
check("l'effetto sopravvive solo a M_size e M_mom e' credibile: R2a, NON REGGE (reversal)",
      S2.verdetto(s, q, sel, False)[:2] == ("R2a", "NON REGGE"))
neg = cella(-0.01, -0.03, 0.01, -1.0)
s = st(zero, zero, zero, neg, neg)
q, sel = S2.scegli_sel(s)
check("media del matching di riferimento <= 0: R3, NON REGGE", S2.verdetto(s, q, sel, False)[:2] == ("R3", "NON REGGE"))
s = st(zero, zero, zero, pos_debole, pos_debole)
q, sel = S2.scegli_sel(s)
check("positivo con IC che include 0 ovunque: R6, INCONCLUSIVO (sotto potenza)",
      S2.verdetto(s, q, sel, False)[:2] == ("R6", "INCONCLUSIVO"))

# ------------------------------------------------------------- sopravvivenza (addendum 3) --
check("fascia: 49,9M -> <50M, 50M -> 50-300M, 300M -> >300M",
      (SV.banda(49.9e6), SV.banda(50e6), SV.banda(300e6), SV.banda(None)) == ("<50M", "50-300M", ">300M", None))
dep_fall = [("2021-03-01", "8-K", "1.03,7.01"), ("2021-04-15", "25-NSE", "")]
dep_acq = [("2021-02-01", "DEFM14A", ""), ("2021-03-10", "8-K", "2.01,5.01"), ("2021-03-11", "25-NSE", "")]
dep_vol = [("2021-05-01", "8-K", "3.01"), ("2021-05-20", "25", "")]
dep_nulla = [("2021-01-10", "10-Q", "")]
anag = {"name": "AAA HOLDINGS INC", "formerNames": []}
check("8-K voce 1.03 nella finestra: FALLIMENTO", SV.classifica(anag, dep_fall) == ("FALLIMENTO", "2021-04-15"))
check("DEFM14A e 8-K 5.01 nella finestra: ACQUISIZIONE", SV.classifica(anag, dep_acq)[0] == "ACQUISIZIONE")
check("solo Form 25 e 8-K 3.01: VOLONTARIO_OTC", SV.classifica(anag, dep_vol)[0] == "VOLONTARIO_OTC")
check("nome con LIQUIDAT: LIQUIDAZIONE",
      SV.classifica({"name": "BBB LIQUIDATING TRUST", "formerNames": []}, dep_vol)[0] == "LIQUIDAZIONE")
check("nessun deposito di uscita: NON_RISOLTO", SV.classifica(anag, dep_nulla)[0] == "NON_RISOLTO")

# ------------------------------------------------- excess sul calendario comune (addendum 2) --
depositato = IDS_SINT[150]                                 # ingresso alla seduta 151, uscita alla 277
stato, x, ingresso = S1.excess_comune("AAA", depositato, 126)
atteso = (60.0 / 50.0 - 1.0) - (1.001 ** 126 - 1.0)
check("AAA: ingresso alla prima seduta DOPO il deposito", ingresso == IDS_SINT[151], ingresso)
check("AAA: excess = rendimento del titolo - rendimento di IWM, il cambio si elide",
      stato == "OK" and abs(x - atteso) < 1e-6, (stato, x, atteso))   # i CSV hanno 6 decimali
stato, x, _ = S1.excess_comune("BBB", IDS_SINT[100], 126)
check("BBB finisce dentro la finestra: ENDED_IN_WINDOW, titolo fino all'ultimo close contro IWM su tutta la finestra",
      stato == "ENDED_IN_WINDOW" and abs(x - (1.001 ** 49 - 1.001 ** 126)) < 1e-6, (stato, x))
check("CCC depositato a 100 sedute dalla fine: TOO_RECENT", S1.excess_comune("CCC", IDS_SINT[-100], 126)[0] == "TOO_RECENT")
check("ticker senza serie: NO_SERIES", S1.excess_comune("ZZZ", IDS_SINT[10], 126)[0] == "NO_SERIES")

shutil.rmtree(TMP, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(report("TEST SINTETICI DEL RI-TEST PASSATI"))
