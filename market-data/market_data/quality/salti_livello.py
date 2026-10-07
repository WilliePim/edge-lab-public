"""Salto di livello non spiegato: una chiusura che sale di cinque volte e resta (docs/adr/012).

Regola pura, senza archivio. **Regola adottata (versione 2, 07-10-2026): solo i rialzi.** La barra del
giorno G è un salto di livello non spiegato se il rapporto fra la sua chiusura grezza e quella della barra precedente
(entro 10 giorni di calendario) è ≥ 5, nessuno split registrato in quella data lo spiega (fattore compatibile entro
±25%, oppure una nota `split_del_fornitore`), le 5 barre successive restano entro il 50% dal nuovo livello, e il giorno
non è fra gli esenti (i salti che la verifica con le azioni di ADR 010 classifica «movimento vero»: li passa chi
chiama). Meno di 5 barre dopo: non valutabile, non preso.

La **variante «alla lettera»** (prima versione della regola: entrambe le direzioni, rapporto ≥ 5 oppure ≤ 0,2, nessuna
esenzione) resta disponibile con `direzione=ENTRAMBE` e senza esenti: serve a chi vuole misurare quanto pesa la scelta.
"""
from __future__ import annotations

import math

import numpy as np

SOGLIA = 5.0               # rapporto ≥ 5 oppure ≤ 1/5, estremi compresi
PERSISTENZA = 0.5          # le barre successive entro il 50% dal nuovo livello
BARRE_DOPO = 5
GIORNI_MAX = 10            # giorni di calendario fra le due chiusure consecutive
TOLLERANZA_SPLIT = 1.25    # rapporto × fattore dello split fra 1/1,25 e 1,25
PRESO, NON_PERSISTE, POCHE_BARRE, SPLIT, LONTANE = "preso", "non persiste", "meno di 5 barre dopo", "split compatibile", "barre lontane"
RIALZI, ENTRAMBE = "rialzi", "entrambe"
DIREZIONI = (RIALZI, ENTRAMBE)


def esamina(giorni, chiusure, split=(), note=(), soglia: float = SOGLIA, persistenza: float = PERSISTENZA) -> list:
    """Per ogni barra con rapporto ≥ `soglia` o ≤ 1/`soglia` rispetto alla precedente: `(posizione, rapporto, esito)`,
    con esito `PRESO` o il motivo per cui non lo è (nell'ordine: barre lontane, split compatibile, meno di 5 barre
    dopo, non persiste).

    `giorni`: giorni come interi, in ordine; `chiusure`: la serie guardata; `split`: `[(giorno, fattore)]` con fattore =
    azioni nuove / vecchie; `note`: giorni con una nota `split_del_fornitore`."""
    g = np.asarray(giorni, dtype=np.int64)
    c = np.asarray(chiusure, dtype=float)
    n = len(c)
    if n < 2:
        return []
    per_giorno: dict = {}
    for d, f in split:
        per_giorno.setdefault(int(d), []).append(float(f))
    note = {int(d) for d in note}
    with np.errstate(invalid="ignore", divide="ignore"):
        r = c[1:] / c[:-1]
        buone = np.isfinite(r) & (c[1:] > 0) & (c[:-1] > 0)
        grandi = buone & ((r >= soglia) | (r <= 1.0 / soglia))
    out = []
    for i in (np.flatnonzero(grandi) + 1).tolist():
        rapporto = float(r[i - 1])
        if g[i] - g[i - 1] > GIORNI_MAX:
            out.append((i, rapporto, LONTANE))
        elif int(g[i]) in note or any(f > 0 and abs(math.log(rapporto * f)) <= math.log(TOLLERANZA_SPLIT) for f in per_giorno.get(int(g[i]), ())):
            out.append((i, rapporto, SPLIT))
        elif i + BARRE_DOPO >= n:
            out.append((i, rapporto, POCHE_BARRE))
        else:
            dopo = c[i + 1:i + 1 + BARRE_DOPO]
            fermo = bool(np.all(np.isfinite(dopo) & (dopo > 0) & (np.abs(dopo / c[i] - 1.0) <= persistenza)))
            out.append((i, rapporto, PRESO if fermo else NON_PERSISTE))
    return out


def salti(giorni, chiusure, split=(), note=(), direzione: str = RIALZI, esenti=()) -> list:
    """Le posizioni dei salti di livello non spiegati. Con i valori di default è la regola adottata: solo i rialzi
    (rapporto ≥ 5); `esenti` = giorni da non prendere mai (i «movimento vero» di ADR 010). `direzione=ENTRAMBE` e
    nessun esente = la variante «alla lettera»."""
    if direzione not in DIREZIONI:
        raise ValueError("direzione sconosciuta: {!r} (ammesso: {})".format(direzione, ", ".join(DIREZIONI)))
    g = np.asarray(giorni, dtype=np.int64)
    esenti = {int(d) for d in esenti}
    return [i for i, r, esito in esamina(giorni, chiusure, split, note)
            if esito == PRESO and (direzione == ENTRAMBE or r > 1.0) and int(g[i]) not in esenti]
