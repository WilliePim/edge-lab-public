"""Russell 2000, uscite verso il basso — regole d'ingresso (piano B6, fase 4 della direttiva). Funzioni pure.

Liste allineate al calendario comune delle sedute (indice = sessione di IWM), None dove la barra manca.
Chiusure: `Close` di Yahoo (rettificata per split; i dividendi non cambiano i minimi di poche settimane).

- **A**: chiusura del giorno della ricostituzione (sessione r).
- **C**: r + 32.
- **B(N, limite)**, uguale per i tre scaglioni (10, 60), (20, 126), (40, 189): primo t con r + N ≤ t ≤ r + limite in cui
  1. nelle ultime N sedute (t−N+1 … t) nessuna chiusura è sotto il minimo di chiusura registrato dalle liste
     preliminari (sessione p) fino alla seduta t−N compresa;
  2. volume medio delle ultime 10 sedute ≤ volume mediano delle 60 sedute che finiscono al Rank Day (sessione k).
  Se non accade, ingresso forzato a r + limite. Copertura: almeno l'80% delle barre in ogni finestra, altrimenti la seduta
  non decide e si passa alla successiva. None se i dati finiscono prima che la regola decida o se manca il volume di
  riferimento.
"""
from __future__ import annotations

import statistics

SCAGLIONI = {"B1": (10, 60), "B2": (20, 126), "B3": (40, 189)}
C_SEDUTE = 32
COPERTURA = 0.8
MEDIA_VOLUME, RIFERIMENTO_VOLUME = 10, 60


def _presenti(xs):
    return [x for x in xs if x is not None]


def volume_riferimento(volumi, k):
    """Mediana dei volumi delle 60 sedute che finiscono al Rank Day, o None."""
    if k < RIFERIMENTO_VOLUME - 1 or k >= len(volumi):
        return None
    v = _presenti(volumi[k - RIFERIMENTO_VOLUME + 1:k + 1])
    return statistics.median(v) if len(v) >= COPERTURA * RIFERIMENTO_VOLUME and statistics.median(v) > 0 else None


def ingresso_b(chiusure, volumi, k, p, r, n, limite):
    """(sessione d'ingresso, "REGOLA" | "FORZATO") o (None, motivo)."""
    med = volume_riferimento(volumi, k)
    if med is None:
        return None, "VOLUME_DI_RIFERIMENTO_ASSENTE"
    for t in range(r + n, r + limite + 1):
        if t >= len(chiusure):
            return None, "DATI_FINITI"
        finestra = _presenti(chiusure[t - n + 1:t + 1])
        storia = _presenti(chiusure[p:t - n + 1])
        v10 = _presenti(volumi[t - MEDIA_VOLUME + 1:t + 1])
        if len(finestra) < COPERTURA * n or not storia or len(v10) < COPERTURA * MEDIA_VOLUME:
            continue
        if min(finestra) >= min(storia) and sum(v10) / len(v10) <= med:
            return t, "REGOLA"
    if r + limite >= len(chiusure):
        return None, "DATI_FINITI"
    return r + limite, "FORZATO"


def ingressi(chiusure, volumi, k, p, r):
    """{"A": (r, "FISSO"), "B1": …, "B2": …, "B3": …, "C": (r + 32, "FISSO")}; None se la sessione non esiste."""
    out = {"A": (r, "FISSO") if r < len(chiusure) else (None, "DATI_FINITI")}
    for nome, (n, lim) in SCAGLIONI.items():
        out[nome] = ingresso_b(chiusure, volumi, k, p, r, n, lim)
    out["C"] = (r + C_SEDUTE, "FISSO") if r + C_SEDUTE < len(chiusure) else (None, "DATI_FINITI")
    return out
