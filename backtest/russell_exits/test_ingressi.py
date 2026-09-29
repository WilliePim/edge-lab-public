"""Test delle regole d'ingresso del backtest Russell. Il primo blocco è obbligatorio: nessun dato dopo la seduta
d'ingresso la decide. Convenzione del repo: harness.

    python backtest/russell_exits/test_ingressi.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests"))

from harness import check, report  # noqa: E402

import ingressi as G  # noqa: E402

K, P, R, LUNG = 70, 85, 100, 400        # Rank Day, liste preliminari, ricostituzione, lunghezza delle liste


def base(prezzo=10.0, volume=1000.0):
    return [prezzo] * LUNG, [volume] * LUNG


# ---- 1. nessun dato successivo all'ingresso lo decide
rng = random.Random(611)
rotture, prove = 0, 0
for _ in range(120):
    c = [rng.uniform(5, 15) for _ in range(LUNG)]
    v = [rng.uniform(500, 1500) if rng.random() > 0.03 else None for _ in range(LUNG)]
    for nome, (n, lim) in G.SCAGLIONI.items():
        t, esito = G.ingresso_b(c, v, K, P, R, n, lim)
        if t is None:
            continue
        prove += 1
        c2, v2 = list(c), list(v)
        for i in range(t + 1, LUNG):
            c2[i] = rng.choice([None, 0.01, 1e6])
            v2[i] = rng.choice([None, 0.0, 1e12])
        if G.ingresso_b(c2, v2, K, P, R, n, lim) != (t, esito):
            rotture += 1
        if G.ingresso_b(c[:t + 1], v[:t + 1], K, P, R, n, lim) != (t, esito):
            rotture += 1
check("l'ingresso non cambia alterando o togliendo i dati dopo la seduta d'ingresso ({} prove)".format(prove), rotture == 0 and prove > 100, str(rotture))

# ---- 2. le regole
c, v = base()
check("prezzi e volumi piatti: B1 al primo giorno possibile (r + 10)", G.ingresso_b(c, v, K, P, R, 10, 60) == (R + 10, "REGOLA"))
check("B2 al primo giorno possibile (r + 20), B3 (r + 40)", G.ingresso_b(c, v, K, P, R, 20, 126) == (R + 20, "REGOLA")
      and G.ingresso_b(c, v, K, P, R, 40, 189) == (R + 40, "REGOLA"))

c, v = base()
for i in range(P, LUNG):
    c[i] = 10.0 - 0.01 * (i - P)             # nuovo minimo ogni giorno
check("nuovi minimi continui: B1 forzato a r + 60", G.ingresso_b(c, v, K, P, R, 10, 60) == (R + 60, "FORZATO"))

c, v = base()
for i in range(P, R + 30):
    c[i] = 10.0 - 0.05 * (i - P)             # vendita fino a r + 29, poi piatto
for i in range(R + 30, LUNG):
    c[i] = c[R + 29]
check("ultimo minimo a r + 29: B1 a r + 39 (10 sedute senza nuovi minimi)", G.ingresso_b(c, v, K, P, R, 10, 60) == (R + 39, "REGOLA"),
      str(G.ingresso_b(c, v, K, P, R, 10, 60)))
check("stessa serie: B2 a r + 49, B3 a r + 69", G.ingresso_b(c, v, K, P, R, 20, 126) == (R + 49, "REGOLA")
      and G.ingresso_b(c, v, K, P, R, 40, 189) == (R + 69, "REGOLA"))

c, v = base()
c[R + 5] = 11.0                              # rimbalzo, poi nuovo minimo a r + 15
c[R + 15] = 9.0
for i in range(R + 16, LUNG):
    c[i] = 9.5
check("rimbalzo, poi nuovo minimo a r + 15: B1 entra sul rimbalzo (r + 10), B2 aspetta la fine vera (r + 35)", G.ingresso_b(c, v, K, P, R, 10, 60) == (R + 10, "REGOLA")
      and G.ingresso_b(c, v, K, P, R, 20, 126) == (R + 35, "REGOLA"))

c, v = base()
for i in range(R - 5, R + 50):
    v[i] = 3000.0                            # volume alto fino a r + 49
check("volume alto: B1 aspetta che la media a 10 sedute torni sotto la mediana (r + 59)",
      G.ingresso_b(c, v, K, P, R, 10, 60) == (R + 59, "REGOLA"), str(G.ingresso_b(c, v, K, P, R, 10, 60)))
check("chiusura uguale al minimo non è un nuovo minimo", G.ingresso_b(*base(), K, P, R, 10, 60)[1] == "REGOLA")

c, v = base()
for i in range(K - 59, K + 1):
    v[i] = None
check("volume di riferimento assente: nessun ingresso", G.ingresso_b(c, v, K, P, R, 10, 60) == (None, "VOLUME_DI_RIFERIMENTO_ASSENTE"))
c, v = base()
for i in range(P, LUNG):
    c[i] = 10.0 - 0.01 * (i - P)
check("dati finiti prima del limite: nessun ingresso", G.ingresso_b(c[:R + 50], v[:R + 50], K, P, R, 10, 60) == (None, "DATI_FINITI"))

c, v = base()
out = G.ingressi(c, v, K, P, R)
check("A = r, C = r + 32", out["A"] == (R, "FISSO") and out["C"] == (R + 32, "FISSO"))

if __name__ == "__main__":
    sys.exit(report("TEST INGRESSI PASSATI"))
