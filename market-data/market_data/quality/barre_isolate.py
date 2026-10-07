"""Barre isolate: una chiusura che va e torna (docs/adr/011).

Regola pura, senza archivio. Una barra è isolata se la sua chiusura si discosta di oltre il 50% **sia** dalla barra
precedente **sia** dalla successiva dello stesso codice, dalla stessa parte, le due vicine distano al più 10 giorni di
calendario dalla barra, e la successiva torna entro il 10% dalla precedente. La prima e l'ultima barra di una serie non
sono valutabili. Si valuta una volta sola sulla serie data (nessuna iterazione).

`api.prices(..., barre_isolate="scarta")` usa `isolate(...)` con la variante `PREZZO` sulla `adjusted_close`; le altre
varianti servono solo a contare (ADR 011).
"""
from __future__ import annotations

import numpy as np

SCOSTAMENTO = 0.5          # oltre il 50% da entrambe le vicine: x > 1,5·vicina oppure x < 0,5·vicina
RITORNO = 0.10             # la successiva entro il 10% dalla precedente
GIORNI_MAX = 10            # giorni di calendario fra la barra e ciascuna vicina
VOLUME_MINIMO = 1000       # varianti con il volume: «quasi nessuno ha scambiato»
PREZZO, PREZZO_E_VOLUME, PREZZO_O_VOLUME = "prezzo", "prezzo_e_volume", "prezzo_o_volume"
VARIANTI = (PREZZO, PREZZO_E_VOLUME, PREZZO_O_VOLUME)
OPZIONI = ("scarta",)


def isolate(giorni, valori, volumi=None, variante: str = PREZZO):
    """Maschera delle barre isolate di una serie di un solo codice, in ordine di data.

    `giorni`: giorni come numeri interi (ordinali o giorni dall'epoca); `valori`: la chiusura guardata; `volumi`: serve
    solo alle varianti con il volume. Una barra con il valore mancante o non positivo, o con una vicina così, non è
    valutabile (falso)."""
    if variante not in VARIANTI:
        raise ValueError("variante sconosciuta: {!r}".format(variante))
    g = np.asarray(giorni, dtype=np.int64)
    v = np.asarray(valori, dtype=float)
    out = np.zeros(len(v), dtype=bool)
    if len(v) < 3:
        return out
    p, x, s = v[:-2], v[1:-1], v[2:]
    with np.errstate(invalid="ignore", divide="ignore"):
        buone = np.isfinite(p) & np.isfinite(x) & np.isfinite(s) & (p > 0) & (x > 0) & (s > 0)
        vicine = (g[1:-1] - g[:-2] <= GIORNI_MAX) & (g[2:] - g[1:-1] <= GIORNI_MAX)
        sopra = (x > (1.0 + SCOSTAMENTO) * p) & (x > (1.0 + SCOSTAMENTO) * s)
        sotto = (x < (1.0 - SCOSTAMENTO) * p) & (x < (1.0 - SCOSTAMENTO) * s)
        torna = np.abs(s / p - 1.0) <= RITORNO
    base = buone & vicine & (sopra | sotto)
    if variante == PREZZO:
        out[1:-1] = base & torna
        return out
    if volumi is None:
        raise ValueError("la variante {!r} vuole i volumi".format(variante))
    poco = np.asarray(volumi, dtype=float)[1:-1] < VOLUME_MINIMO
    out[1:-1] = base & torna & poco if variante == PREZZO_E_VOLUME else base & (torna | poco)
    return out


def gruppi(giorni, valori, massimo: int = 3):
    """ESTENSIONE NON ADOTTATA (ADR 011: resta solo nei conteggi): maschera delle barre in gruppi di 2..`massimo` barre
    consecutive tutte oltre il 50% dalla stessa parte rispetto alla barra prima del gruppo e alla barra dopo, con la
    barra dopo entro il 10% dalla barra prima e non più di 10 giorni di calendario fra la barra prima e la barra dopo.
    Le barre isolate singole (`isolate`) non sono comprese."""
    g = np.asarray(giorni, dtype=np.int64)
    v = np.asarray(valori, dtype=float)
    n = len(v)
    out = np.zeros(n, dtype=bool)
    buono = np.isfinite(v) & (v > 0)
    for k in range(2, massimo + 1):
        if n < k + 2:
            break
        p, s = v[:n - k - 1], v[k + 1:]
        with np.errstate(invalid="ignore", divide="ignore"):
            ok = buono[:n - k - 1] & buono[k + 1:] & (g[k + 1:] - g[:n - k - 1] <= GIORNI_MAX) & (np.abs(s / p - 1.0) <= RITORNO)
            alto, basso = ok.copy(), ok.copy()
            for j in range(1, k + 1):
                x = v[j:n - k - 1 + j]
                alto &= buono[j:n - k - 1 + j] & (x > (1.0 + SCOSTAMENTO) * np.maximum(p, s))
                basso &= buono[j:n - k - 1 + j] & (x < (1.0 - SCOSTAMENTO) * np.minimum(p, s))
        for i in np.flatnonzero(alto | basso):
            out[i + 1:i + 1 + k] = True
    return out
