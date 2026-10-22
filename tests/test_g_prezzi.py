"""Prove sul prezzo Black-Scholes del Test G (`backtest/drawdown_alpha/test_g_dati.py`).

Nessuna rete e nessun archivio: i lettori dei dati sono sostituiti da una funzione che fallisce, cosi' una prova che
leggesse dati veri cadrebbe invece di passare per caso. Si verificano tre cose: un valore noto di manuale (Hull,
«Options, Futures, and Other Derivatives», esempio del capitolo su Black-Scholes-Merton: S = 42, K = 40, r = 10%,
sigma = 20%, T = 0,5 -> d1 = 0,7693, d2 = 0,6278, call 4,76, put 0,81; e, con il rendimento da dividendo, l'esempio
dell'opzione su indice: S = 930, K = 900, r = 8%, q = 3%, sigma = 20%, T = 2/12 -> d1 = 0,5444, d2 = 0,4628, call
51,83), le proprieta' che un prezzo sbagliato viola (parita' put-call, limiti, monotonia), e le due regole di data e
di buco che la pre-registrazione fissa. Il dividendo principale e' q = 2% (ADR-072); q = 0 e' una sensibilita'.
"""
import datetime as dt
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest" / "drawdown_alpha"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, near, raises, report, section

import test_g_dati as G


def _niente_rete(*_a, **_k):
    raise AssertionError("questa suite non deve leggere dati")


G.api.fred = _niente_rete
G.api.prices = _niente_rete

#  Griglia realistica per l'S&P 500: prezzo, tempo, tasso (anche zero e negativo, come nel 2015 e nel 2020), VIX.
GRIGLIA = [(S, T, r, vix)
           for S in (300.0, 1277.58, 6000.0)
           for T in (1 / 365.0, 0.25, 0.5, 0.75, 1.0)
           for r in (-0.0005, 0.0, 0.0172, 0.08)
           for vix in (9.14, 21.99, 45.0, 82.69)]


# ------------------------------------------------------------- normale

def test_normale():
    section("normale standard")
    check("N(0) = 0,5", near(G.N(0.0), 0.5, 1e-12), str(G.N(0.0)))
    check("N(1,96) = 0,975002 (tavola)", near(G.N(1.96), 0.9750021, 1e-6), str(G.N(1.96)))
    check("N(-1,645) = 0,05 (tavola)", near(G.N(-1.645), 0.05, 2e-5), str(G.N(-1.645)))
    check("N(-x) = 1 - N(x)", all(near(G.N(-x) + G.N(x), 1.0, 1e-12) for x in (0.1, 0.77, 2.5, 6.0)))


# ------------------------------------------------------------- il valore di manuale

def test_hull():
    section("valore noto di manuale (Hull: S=42, K=40, r=10%, sigma=20%, T=0,5)")
    d1, d2 = G.d1_d2(42.0, 40.0, 0.5, 0.10, 0.20, 0.0)
    check("d1 = 0,7693", near(d1, 0.7693, 5e-5), str(d1))
    check("d2 = 0,6278", near(d2, 0.6278, 5e-5), str(d2))
    put = G.bs_put(42.0, 40.0, 0.5, 0.10, 0.20, 0.0)
    call = G.bs_call(42.0, 40.0, 0.5, 0.10, 0.20, 0.0)
    check("put = 0,81", near(put, 0.81, 0.005), str(put))
    check("call = 4,76", near(call, 4.76, 0.005), str(call))

    section("valore noto di manuale con dividendo (Hull, opzione su indice: S=930, K=900, r=8%, q=3%, sigma=20%, T=2/12)")
    d1, d2 = G.d1_d2(930.0, 900.0, 2 / 12.0, 0.08, 0.20, 0.03)
    check("d1 = 0,5444 (il manuale tronca: il valore e' 0,54448)", near(d1, 0.5444, 1e-4), str(d1))
    check("d2 = 0,4628", near(d2, 0.4628, 5e-5), str(d2))
    call = G.bs_call(930.0, 900.0, 2 / 12.0, 0.08, 0.20, 0.03)
    put = G.bs_put(930.0, 900.0, 2 / 12.0, 0.08, 0.20, 0.03)
    check("call = 51,83", near(call, 51.83, 0.005), str(call))
    check("la put dello stesso esempio rispetta la parita': put = call - S*exp(-qT) + K*exp(-rT)",
          near(put, call - 930.0 * math.exp(-0.03 * 2 / 12.0) + 900.0 * math.exp(-0.08 * 2 / 12.0), 1e-9), str(put))
    check("il dividendo alza la put: q = 3% > q = 0", put > G.bs_put(930.0, 900.0, 2 / 12.0, 0.08, 0.20, 0.0))


# ------------------------------------------------------------- parita' e limiti

def test_parita_e_limiti():
    section("parita' put-call e limiti")
    for q in (0.02, 0.0):                                             # la scelta principale e la sensibilita'
        parita, non_neg, sotto, sopra = [], [], [], []
        for S, T, r, vix in GRIGLIA:
            for k in (0.75, 0.95, 1.0, 1.2):
                K, s = k * S, vix / 100.0
                p, c = G.bs_put(S, K, T, r, s, q), G.bs_call(S, K, T, r, s, q)
                sconto, termine = K * math.exp(-r * T), S * math.exp(-q * T)
                if not near(c - p, termine - sconto, 1e-8 * S):
                    parita.append((S, K, T, r, s))
                if p < 0:
                    non_neg.append((S, K, T, r, s, p))
                if p < max(sconto - termine, 0.0) - 1e-9 * S:
                    sotto.append((S, K, T, r, s, p))
                if p > sconto + 1e-9 * S:
                    sopra.append((S, K, T, r, s, p))
        check("q = {}: call - put = S*exp(-qT) - K*exp(-rT) su tutta la griglia".format(q), not parita, str(parita[:2]))
        check("q = {}: put >= 0".format(q), not non_neg, str(non_neg[:2]))
        check("q = {}: put >= max(K*exp(-rT) - S*exp(-qT), 0)".format(q), not sotto, str(sotto[:2]))
        check("q = {}: put <= K*exp(-rT)".format(q), not sopra, str(sopra[:2]))
    check("senza q esplicito vale il dividendo principale (2%)",
          G.bs_put(100.0, 95.0, 1.0, 0.03, 0.2) == G.bs_put(100.0, 95.0, 1.0, 0.03, 0.2, 0.02))
    check("parita' anche con un dividendo q > 0",
          near(G.bs_call(100.0, 95.0, 1.0, 0.03, 0.2, 0.02) - G.bs_put(100.0, 95.0, 1.0, 0.03, 0.2, 0.02),
               100.0 * math.exp(-0.02) - 95.0 * math.exp(-0.03), 1e-10))


def test_monotonia():
    section("monotonia")
    check("la put cresce con la volatilita'",
          G.bs_put(100.0, 95.0, 1.0, 0.02, 0.30) > G.bs_put(100.0, 95.0, 1.0, 0.02, 0.20) > G.bs_put(100.0, 95.0, 1.0, 0.02, 0.10))
    check("la put cresce con lo strike",
          G.bs_put(100.0, 95.0, 1.0, 0.02, 0.20) > G.bs_put(100.0, 75.0, 1.0, 0.02, 0.20))
    check("la put scende se il prezzo sale",
          G.bs_put(90.0, 95.0, 1.0, 0.02, 0.20) > G.bs_put(100.0, 95.0, 1.0, 0.02, 0.20))


# ------------------------------------------------------------- lo spread

def test_spread():
    section("put spread 95/75")
    k1, k2 = G.strike(1000.0)
    check("strike: 5% e 25% sotto il prezzo", near(k1, 950.0, 1e-9) and near(k2, 750.0, 1e-9), "{} {}".format(k1, k2))
    oltre, negativi, ordine = [], [], []
    for S, T, r, vix in GRIGLIA:
        a, b = G.strike(S)
        tetto = (a - b) * math.exp(-r * T)
        for prezzo in (S, 0.9 * S, 0.7 * S, 0.5 * S, 1.3 * S):       # anche a strike fissi con il prezzo che si muove
            for q in (0.02, 0.0):
                v = {i: G.put_spread(prezzo, a, b, T, r, vix, inclinazione=i, q=q) for i in (0.0, 5.0, 10.0)}
                if any(x > tetto + 1e-9 * S for x in v.values()):
                    oltre.append((prezzo, a, b, T, r, vix, q, v))
                if v[0.0] < -1e-9 * S:
                    negativi.append((prezzo, a, b, T, r, vix, q, v[0.0]))
                if not (v[0.0] >= v[5.0] >= v[10.0]):
                    ordine.append((prezzo, a, b, T, r, vix, q, v))
    check("spread <= differenza degli strike scontata, con inclinazione 0, 5 e 10", not oltre, str(oltre[:1]))
    check("spread >= 0 con inclinazione 0", not negativi, str(negativi[:1]))
    check("piu' inclinazione = spread meno caro (0 >= 5 >= 10)", not ordine, str(ordine[:1]))
    check("l'inclinazione di default e' 5 punti",
          G.put_spread(1000.0, 950.0, 750.0, 1.0, 0.02, 20.0) == G.put_spread(1000.0, 950.0, 750.0, 1.0, 0.02, 20.0, inclinazione=5.0))
    check("lo spread e' la differenza delle due put (VIX e VIX + 5)",
          near(G.put_spread(1000.0, 950.0, 750.0, 1.0, 0.02, 20.0),
               G.bs_put(1000.0, 950.0, 1.0, 0.02, 0.20) - G.bs_put(1000.0, 750.0, 1.0, 0.02, 0.25), 1e-12))
    check("strike invertiti: errore", raises(lambda: G.put_spread(1000.0, 750.0, 950.0, 1.0, 0.02, 20.0), ValueError))
    check("con q = 2% lo spread costa piu' che con q = 0",
          G.put_spread(1000.0, 950.0, 750.0, 1.0, 0.02, 20.0) > G.put_spread(1000.0, 950.0, 750.0, 1.0, 0.02, 20.0, q=0.0))


def test_tetto_teorico():
    section("parte coperta e guadagno massimo (tetto teorico, nessun valore a scadenza)")
    check("larghezza dello spread: 20% del prezzo di ingresso", near(G.LARGHEZZA, 0.20, 1e-12), str(G.LARGHEZZA))
    check("premio 3%, spread al 4% dell'indice: parte coperta 75%", near(G.parte_coperta(0.03, 0.04), 0.75, 1e-12))
    check("...e guadagno massimo 15% del portafoglio", near(G.guadagno_massimo(0.03, 0.04), 0.15, 1e-12))
    check("spread all'1%: parte coperta 300%, nessun limite al 100%", near(G.parte_coperta(0.03, 0.01), 3.0, 1e-12))
    check("costo zero: errore, non una copertura infinita", raises(lambda: G.parte_coperta(0.03, 0.0), ValueError))
    check("il guadagno massimo e' il valore a T = 0 con l'indice sotto lo strike venduto, sul prezzo di ingresso",
          near(G.put_spread(700.0, *G.strike(1000.0), 0.0, 0.02, 20.0) / 1000.0, G.LARGHEZZA, 1e-12))
    check("premi della versione A: 1,5% a 3 mesi, 3% a 6, 9 e 12", G.PREMIO["A"] == {3: 0.015, 6: 0.03, 9: 0.03, 12: 0.03})
    check("...cioe' 6% x mesi/12, massimo 3%",
          all(near(G.PREMIO["A"][m], min(0.06 * m / 12, 0.03), 1e-12) for m in G.SCADENZE_MESI))
    check("premi della versione B: 3% sempre", set(G.PREMIO["B"].values()) == {0.03} and set(G.PREMIO["B"]) == {3, 6, 9, 12})


def test_scadenza_e_errori():
    section("T = 0 e ingressi non validi")
    check("T = 0, prezzo sopra lo strike: zero", G.bs_put(100.0, 95.0, 0.0, 0.02, 0.2) == 0.0)
    check("T = 0, prezzo sotto lo strike: valore intrinseco", near(G.bs_put(80.0, 95.0, 0.0, 0.02, 0.2), 15.0, 1e-12))
    check("T = 0, prezzo sotto i due strike: lo spread vale la differenza degli strike",
          near(G.put_spread(600.0, 950.0, 750.0, 0.0, 0.02, 20.0), 200.0, 1e-12))
    check("T = 0, prezzo fra i due strike: strike comprato meno prezzo",
          near(G.put_spread(800.0, 950.0, 750.0, 0.0, 0.02, 20.0), 150.0, 1e-12))
    check("T = 0, prezzo sopra i due strike: zero", G.put_spread(1000.0, 950.0, 750.0, 0.0, 0.02, 20.0) == 0.0)
    check("volatilita' zero: errore, non un numero", raises(lambda: G.bs_put(100.0, 95.0, 1.0, 0.02, 0.0), ValueError))
    check("volatilita' NaN: errore", raises(lambda: G.bs_put(100.0, 95.0, 1.0, 0.02, float("nan")), ValueError))
    check("prezzo zero: errore", raises(lambda: G.bs_put(0.0, 95.0, 1.0, 0.02, 0.2), ValueError))
    check("tempo negativo: errore", raises(lambda: G.bs_put(100.0, 95.0, -0.1, 0.02, 0.2), ValueError))


# ------------------------------------------------------------- tasso, date, buchi

def test_tasso():
    section("DTB3 -> tasso continuo")
    atteso = (365.0 / 91.0) * math.log(1.0 / (1.0 - 0.0169 * 91.0 / 360.0))
    check("1,69% di sconto -> (365/91)*ln(1/P), P = 1 - d*91/360", near(G.tasso_continuo(1.69), atteso, 1e-12),
          str(G.tasso_continuo(1.69)))
    check("...che sta sopra lo sconto", G.tasso_continuo(1.69) > 0.0169)
    check("sconto zero -> tasso zero", G.tasso_continuo(0.0) == 0.0)
    check("sconto negativo -> tasso negativo", G.tasso_continuo(-0.05) < 0.0)


def _feriali(da: dt.date, a: dt.date) -> list:
    out, d = [], da
    while d <= a:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def test_date():
    section("scadenza e tempo")
    sedute = _feriali(dt.date(2020, 1, 1), dt.date(2021, 12, 31))
    check("2021-04-04 e' una domenica", dt.date(2021, 4, 4).weekday() == 6)
    check("3 mesi dal 2021-01-04: la seduta PRIMA del 2021-04-04, mai dopo",
          G.scadenza(dt.date(2021, 1, 4), 3, sedute) == dt.date(2021, 4, 2), str(G.scadenza(dt.date(2021, 1, 4), 3, sedute)))
    check("12 mesi dal 2020-09-02: lo stesso giorno, se e' una seduta",
          G.scadenza(dt.date(2020, 9, 2), 12, sedute) == dt.date(2021, 9, 2))
    check("3 mesi dal 2020-11-30: febbraio non ha il 30, quindi il 28 (domenica) -> venerdi' 26",
          G.scadenza(dt.date(2020, 11, 30), 3, sedute) == dt.date(2021, 2, 26), str(G.scadenza(dt.date(2020, 11, 30), 3, sedute)))
    check("scadenza oltre l'ultima seduta: DatoMancante, non l'ultima disponibile",
          raises(lambda: G.scadenza(dt.date(2021, 6, 1), 12, sedute), G.DatoMancante))
    check("tempo = giorni di calendario / 365", near(G.anni(dt.date(2008, 9, 2), dt.date(2009, 9, 2)), 1.0, 1e-12))
    check("...e un anno bisestile dura 366/365", near(G.anni(dt.date(2020, 1, 2), dt.date(2021, 1, 2)), 366 / 365.0, 1e-12))


def test_buchi():
    section("buchi: ultimo valore noto, mai in avanti")
    s = G.Serie("PROVA", [(dt.date(2020, 1, 2), 10.0), (dt.date(2020, 1, 3), 11.0), (dt.date(2020, 1, 7), 99.0),
                          (dt.date(2020, 2, 3), 12.0)])
    check("giorno presente: il suo valore", s.ultimo_noto(dt.date(2020, 1, 3)) == (dt.date(2020, 1, 3), 11.0))
    check("PROVA POSITIVA: giorno mancante -> il valore di prima, non quello di dopo",
          s.ultimo_noto(dt.date(2020, 1, 6)) == (dt.date(2020, 1, 3), 11.0), str(s.ultimo_noto(dt.date(2020, 1, 6))))
    check("valore piu' vecchio di 7 giorni: DatoMancante", raises(lambda: s.ultimo_noto(dt.date(2020, 1, 20)), G.DatoMancante))
    check("7 giorni esatti: ancora buono", s.ultimo_noto(dt.date(2020, 1, 14)) == (dt.date(2020, 1, 7), 99.0))
    check("prima dell'inizio della serie: DatoMancante", raises(lambda: s.ultimo_noto(dt.date(2019, 12, 31)), G.DatoMancante))


def test_costanti():
    section("costanti della pre-registrazione")
    check("strike 95% e 75%", (G.STRIKE_COMPRATA, G.STRIKE_VENDUTA) == (0.95, 0.75))
    check("inclinazione 5 punti", G.INCLINAZIONE == 5.0)
    check("scadenze 3, 6, 9, 12 mesi", G.SCADENZE_MESI == (3, 6, 9, 12))
    check("periodo 1990-2025", G.PERIODO == (dt.date(1990, 1, 1), dt.date(2025, 12, 31)))
    check("dividendo principale q = 2% nel prezzo delle put", G.DIVIDENDO == 0.02)


test_normale()
test_hull()
test_parita_e_limiti()
test_monotonia()
test_spread()
test_tetto_teorico()
test_scadenza_e_errori()
test_tasso()
test_date()
test_buchi()
test_costanti()

if __name__ == "__main__":
    sys.exit(report("ALL TEST-G PRICE TESTS PASSED"))
