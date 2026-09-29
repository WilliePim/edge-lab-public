"""Test dei rendimenti extra, della statistica e del verdetto (pre-registrazione §1, §5, §7, §8). Dati finti.

    python backtest/russell_exits/test_rendimenti.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests"))

from harness import check, report  # noqa: E402

import rendimenti as R  # noqa: E402

NAN = float("nan")
LAST = 20

# ---- rendimento di un titolo
adj = [100.0] * 5 + [110.0] * 6 + [121.0] * 10          # 21 sedute
close = list(adj)
r, e = R.rendimento(adj, close, 2, 8, LAST)
check("finestra completa: 100 -> 110 = +10%", abs(r - 0.10) < 1e-12 and e == "completo", (r, e))
r, e = R.rendimento(adj, close, 2, 21, LAST)
check("finestra oltre l'ultima seduta: esclusa", r is None and e == "finestra oltre i dati")
r, e = R.rendimento([NAN] * 21, close, 2, 8, LAST)
check("senza prezzo all'ingresso: escluso", r is None and e == "senza prezzo all'ingresso")

corto = [100.0] * 5 + [80.0] * 3 + [NAN] * 13           # delistato dopo la seduta 7
r, e = R.rendimento(corto, corto, 2, 15, LAST)
check("delistato nella finestra: ultimo prezzo, -20%", abs(r + 0.20) < 1e-12 and e == "delistato: ultimo prezzo", (r, e))
r, e = R.rendimento(corto, corto, 2, 15, LAST, offerta=90.0)
check("delistato con offerta in contanti: 80 x 90/80 = 90, -10%",
      abs(r + 0.10) < 1e-12 and e == "delistato: prezzo dell'offerta", (r, e))
adj_div = [100.0] * 5 + [78.0] * 3 + [NAN] * 13         # rettificata sotto la grezza per un dividendo
grezza = [100.0] * 5 + [80.0] * 3 + [NAN] * 13
r, _ = R.rendimento(adj_div, grezza, 2, 15, LAST, offerta=90.0)
check("l'offerta grezza si applica sopra la rettificata dell'ultima barra: 78 x 90/80 / 100",
      abs(r - (78.0 * 90.0 / 80.0 / 100.0 - 1)) < 1e-12, r)

buco = list(adj)
buco[10] = buco[9] = NAN
r, e = R.rendimento(buco, buco, 2, 10, LAST)
check("buco all'uscita entro 5 sedute: vale l'ultima chiusura", r is not None and e == "completo", (r, e))
buco_lungo = list(adj)
for i in range(3, 11):
    buco_lungo[i] = NAN
r, e = R.rendimento(buco_lungo, buco_lungo, 2, 10, LAST)
check("buco all'uscita oltre 5 sedute con la serie che continua: escluso", r is None and e == "buco all'uscita", (r, e))

# ---- rendimento extra: peer sulle stesse date, almeno 3
serie = {"C": (close, adj), "P1": ([100.0] * 21, [100.0] * 21), "P2": ([100.0] * 21, [100.0] * 5 + [105.0] * 16),
         "P3": ([100.0] * 21, [100.0] * 5 + [95.0] * 16), "P4": ([NAN] * 21, [NAN] * 21)}


def s_(c):
    x = serie.get(c)
    return (x[0], x[1], None, [], None) if x else None


x, esito, n = R.rendimento_extra({"codice": "C"}, [{"codice": p} for p in ("P1", "P2", "P3")], 2, 8, LAST, s_)
check("extra = +10% - media(0, +5%, -5%) = +10%", abs(x - 0.10) < 1e-12 and n == 3, (x, n))
x, esito, n = R.rendimento_extra({"codice": "C"}, [{"codice": p} for p in ("P1", "P2", "P4")], 2, 8, LAST, s_)
check("un peer senza prezzo esce dalla media: ne restano 2, il caso non entra", x is None and n == 2, (x, esito, n))
x, esito, n = R.rendimento_extra({"codice": "C"}, [{"codice": p} for p in ("P1", "P2", "P3", "P4")], 2, 8, LAST, s_)
check("con 4 peer di cui uno senza prezzo ne restano 3: entra", x is not None and n == 3, (x, n))

# ---- statistica: t sulle medie annuali
st = R.statistiche({2016: [0.10, 0.20], 2017: [0.00], 2018: [0.05, 0.15, 0.10], 2021: [0.30]})
medie = [0.15, 0.0, 0.10, 0.30]
mom = sum(medie) / 4
sd = math.sqrt(sum((m - mom) ** 2 for m in medie) / 3)
check("casi e anni", st["casi"] == 7 and st["anni"] == 4)
check("media delle medie annuali", abs(st["media_delle_medie"] - mom) < 1e-12, st["media_delle_medie"])
check("t = media delle medie / (sd / radice degli anni), gradi = anni - 1",
      abs(st["t"] - mom / (sd / 2)) < 1e-9 and st["gradi"] == 3, st["t"])
check("sottoperiodi: 2015-2019 ha 3 anni, 2020-2025 ne ha 1",
      st["sottoperiodi"]["2015-2019"]["anni"] == 3 and st["sottoperiodi"]["2020-2025"]["anni"] == 1)
check("un anno solo: t non calcolabile", R.statistiche({2020: [0.1, 0.2]})["t"] is None)


# ---- verdetto, nell'ordine del §1
def cella(casi=230, anni=11, mediana=0.02, mom=0.03, t=2.5, sub=(0.02, 0.04)):
    return {"casi": casi, "anni": anni, "mediana": mediana, "media_delle_medie": mom, "t": t,
            "sottoperiodi": {"2015-2019": {"media_delle_medie": sub[0]}, "2020-2025": {"media_delle_medie": sub[1]}}}


buon_placebo = {"t": 0.5, "media_delle_medie": 0.001}
check("tutti e cinque veri: REGGE", R.verdetto(cella(), buon_placebo)[0] == "REGGE")
check("t >= 2 ma un sottoperiodo negativo: NON REGGE (alla lettera)",
      R.verdetto(cella(sub=(-0.01, 0.05)), buon_placebo)[0] == "NON REGGE")
check("t >= 2 ma placebo con |t| >= 2: NON REGGE", R.verdetto(cella(), {"t": 2.3, "media_delle_medie": 0.0})[0] == "NON REGGE")
check("placebo con media piu' alta della cella: NON REGGE",
      R.verdetto(cella(), {"t": 0.1, "media_delle_medie": 0.05})[0] == "NON REGGE")
check("t fra 1 e 2, mediana e media positive: INCONCLUSIVO", R.verdetto(cella(t=1.5), buon_placebo)[0] == "INCONCLUSIVO")
check("criterio 1 non raggiunto, mediana e media positive: INCONCLUSIVO",
      R.verdetto(cella(casi=80, t=3.0), buon_placebo)[0] == "INCONCLUSIVO")
check("t sotto 1: NON REGGE", R.verdetto(cella(t=0.8), buon_placebo)[0] == "NON REGGE")
check("mediana negativa: NON REGGE anche con t alto", R.verdetto(cella(mediana=-0.01), buon_placebo)[0] == "NON REGGE")
check("placebo senza t (un anno solo): il criterio 5 e' falso, niente REGGE",
      R.verdetto(cella(), {"t": None, "media_delle_medie": 0.0})[0] != "REGGE")

# ---- date di dicembre
check("secondo venerdi' di dicembre 2025: 12", R.secondo_venerdi_di_dicembre(2025) == "2025-12-12")
check("secondo venerdi' di dicembre 2023 (il 1 e' venerdi'): 8", R.secondo_venerdi_di_dicembre(2023) == "2023-12-08")

# ---- cambi di ticker: seguire la società sul codice nuovo (aggiunto dopo il verdetto Russell, che non lo usa)
def s(close, adj=None):
    close = [float(x) if x is not None else NAN for x in close]
    adj = [float(x) if x is not None else NAN for x in adj] if adj is not None else list(close)
    return (close, adj, [1000.0 if x == x else NAN for x in close])


N = [None]
vecchio = s([10, 10, 11, 12, 12, 12] + N * 15)                          # ultima barra alla seduta 5
contiguo = s(N * 7 + [13, 13, 14] + [15] * 11)                          # riprende due sedute dopo
ser, seguiti = R.segui(vecchio, {"NUOVO": contiguo})
check("rinomo contiguo: seguito", seguiti == "NUOVO", seguiti)
check("dopo l'aggancio la rettificata prosegue con i rendimenti del nuovo: 12 x 15/13",
      abs(ser[1][20] - 12 * 15 / 13) < 1e-12, ser[1][20])
check("dopo l'aggancio close e volume sono quelli veri del nuovo", ser[0][20] == 15.0 and ser[2][20] == 1000.0)
check("prima dell'aggancio la serie vecchia non cambia", ser[1][:6] == vecchio[1][:6])
r, e = R.rendimento(ser[1], ser[0], 1, 20, LAST)
check("rendimento sulla serie seguita: completo, 10 -> 12 x 15/13", abs(r - (12 * 15 / 13 / 10 - 1)) < 1e-12 and e == "completo", (r, e))
r, e = R.rendimento(vecchio[1], vecchio[0], 1, 20, LAST)
check("senza seguire: delistato, come nel referto Russell", e == "delistato: ultimo prezzo", e)

copia = s([10, 10, 11, 12, 12, 12] + [12.5] * 15)                       # il nuovo ricopia la storia
check("rinomo che ricopia la storia: aggancio all'ultima barra del vecchio", R.aggancio(vecchio, copia) == 5)
fusione = s([x * 1.5 if x else None for x in [10, 10, 11, 12, 12, 12]] + [19.5] * 15)   # AAA -> BBB, conversione 1,5 (sintetico)
check("rapporto costante 1,5 (conversione delle azioni): seguito", R.segui(vecchio, {"BBB": fusione})[1] == "BBB")
ser, _ = R.segui(vecchio, {"BBB": fusione})
check("con il rapporto 1,5 la rettificata segue i rendimenti: 12 x 19,5/18", abs(ser[1][20] - 12 * 19.5 / 18) < 1e-12, ser[1][20])
centesimi_v = s([0.4225, 0.37, 0.3299, 0.325, 0.31, 0.2696] + N * 15)  # sintetico: il nuovo codice quota al centesimo
centesimi_n = s([0.42, 0.37, 0.33, 0.33, 0.31, 0.27] + [0.3] * 15)
check("quotazione arrotondata al centesimo: seguita", R.aggancio(centesimi_v, centesimi_n) == 5)

tardi = s(N * 12 + [3] * 9)                                             # riquotazione mesi dopo (sintetico)
check("riquotazione oltre STALE sedute: non seguita", R.aggancio(vecchio, tardi) is None)
parallela = s([4, 5, 4, 6, 5, 4] + [5] * 15)                            # altra classe, prezzi diversi (sintetico)
check("altra classe dello stesso emittente, prezzi non in rapporto costante: non seguita",
      R.aggancio(vecchio, parallela) is None)
ferma_v = s([0.4] * 6 + N * 15)                                         # sintetico: codice fermo, gemello fuori borsa vivo
ferma_n = s([0.07, 0.21, 0.09, 0.10, 0.08, 0.09] + [0.1] * 15)
check("quotazione ferma contro quotazione viva: non seguita", R.aggancio(ferma_v, ferma_n) is None)
una = s(N * 5 + [18] + [19] * 15)                                       # una sola seduta in comune, livello diverso
check("una sola seduta in comune: il rapporto deve essere 1", R.aggancio(vecchio, una) is None)
finisce = s(N * 7 + [13, 13] + N * 12)
check("il nuovo finisce prima del vecchio: non seguito",
      R.aggancio(s([10] * 10 + N * 11), finisce) is None)
check("due candidati buoni: non si segue niente", R.segui(vecchio, {"A": contiguo, "B": copia})[1] is None)
check("nessun candidato: serie invariata", R.segui(vecchio, {})[0] is vecchio)

anello1 = s(N * 6 + [12, 13, 13, 13] + N * 11)                          # AAA -> BBB -> CCC (sintetico)
anello2 = s(N * 11 + [13, 14] + [14] * 8)
ser, seguiti = R.segui(vecchio, {"B": anello1, "C": anello2})
check("catena di due rinomi: seguiti tutti e due, nell'ordine", seguiti == "B→C", seguiti)
check("catena: la rettificata finale è 12 x 13/12 x 14/13", abs(ser[1][20] - 14.0) < 1e-12, ser[1][20])

sys.exit(report("TEST RENDIMENTI PASSATI"))
