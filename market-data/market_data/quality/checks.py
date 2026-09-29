"""Controlli di qualità per borsa (fase 4). Funzioni pure su serie già caricate; nessuna chiamata di rete.

## Split mancanti (regola dell'utente, 17-09-2026; tolleranza portata al ±5% alla fermata 2)

Un salto giornaliero fra la chiusura di t−1 e quella di t è **segnalato** quando valgono tutte e tre:
1. il rapporto `close[t] / close[t−1]` è entro ±5% (relativo al rapporto tipico) da un rapporto tipico di split: 2, 3, 4,
   5, 8, 10, 15, 20, 25, 50, 100 o gli inversi;
2. nelle 20 sedute dopo t il prezzo **non torna indietro**: nessuna chiusura torna verso il livello di prima oltre il punto
   medio in logaritmo (per un salto in giù: `ln(close[t+j] / close[t]) < |ln k| / 2`; per un salto in su il simmetrico).
   Allontanarsi ancora dal livello di prima non conta come ritorno;
3. **non c'è uno split registrato** in quella data.

**Volume**: per ogni salto si riporta se il volume si muove in senso opposto al prezzo, come in uno split vero (mediana
delle 20 sedute prima contro mediana delle 20 sedute da t in poi). Non decide la segnalazione. La frase della regola
«Se c'è, controlla anche il volume» può riferirsi al volume o allo split registrato: il volume si riporta in tutti e due i
casi, anche per i salti con uno split registrato (`split_registrati`).

**Non valutabili** (dato mancante = sconosciuto, mai pulito): salti con rapporto tipico ma meno di 20 sedute dopo, o con
una chiusura mancante o non positiva nelle 20 sedute. Sono elencati a parte, non segnalati e non puliti.

**Test di accettazione dell'utente**: Iconix il 17-12-2015 (rapporto fra le chiusure 0,1046, cioè 4,6% da 1/10) è
segnalato con il ±5% (con il ±3% iniziale non lo era: decisione dell'utente alla fermata 2).

**Fasce di prezzo** per il resoconto: sotto 0,05, fra 0,05 e 1, sopra 1 (prezzo più basso fra le due chiusure del salto).

## Volume zero ripetuto (regola dell'utente, fermata 2)

**Sequenza sospetta**: almeno 20 sedute consecutive con volume zero e chiusura identica. Sono prezzi riportati, non
scambi (esempio: BHP in Australia 1988-1998). Nei backtest quei periodi si escludono, come i salti sospetti. Un volume
mancante (non zero) interrompe la sequenza: non si sa se ci sono stati scambi.

La soglia dei salti impossibili resta al 90% (decisione dell'utente): è un controllo diverso, non questo.
"""
from __future__ import annotations

import math
from statistics import median

RAPPORTI_SPLIT = (2, 3, 4, 5, 8, 10, 15, 20, 25, 50, 100)
CANDIDATI = tuple(float(k) for k in RAPPORTI_SPLIT) + tuple(1.0 / k for k in RAPPORTI_SPLIT)
TOLLERANZA = 0.05
EPS = 1e-9                      # il bordo esatto della tolleranza resta dentro nonostante l'arrotondamento
SEDUTE_DOPO = 20
SEDUTE_VOLUME = 20


def rapporto_tipico(r: float | None, tolleranza: float = TOLLERANZA) -> float | None:
    """Il rapporto tipico di split entro ±tolleranza (relativa) da r, o None."""
    if not r or r <= 0:
        return None
    for k in CANDIDATI:
        if abs(r / k - 1.0) <= tolleranza + EPS:
            return k
    return None


def _positivo(c) -> bool:
    return c is not None and c == c and c > 0


def rettificata_continua(rapporto: float, rapporto_rettificata: float | None) -> bool | None:
    """La chiusura rettificata attraversa il salto senza saltare: il fornitore conosce lo split e l'ha applicato.

    Il confronto e' col mezzo logaritmo del salto grezzo, la stessa misura che serve altrove a dire se il prezzo
    «torna indietro»: sotto la meta', la rettificata non ha fatto il salto. None se la rettificata manca -- ignoto,
    non continuo."""
    if rapporto_rettificata is None or rapporto_rettificata <= 0 or rapporto <= 0:
        return None
    return abs(math.log(rapporto_rettificata)) < abs(math.log(rapporto)) / 2


def _volume_coerente(barre: list[dict], t: int, r: float) -> bool | None:
    v_prima = [b.get("volume") for b in barre[max(0, t - SEDUTE_VOLUME):t] if b.get("volume")]
    v_dopo = [b.get("volume") for b in barre[t:t + SEDUTE_VOLUME] if b.get("volume")]
    if not v_prima or not v_dopo:
        return None
    vp, vd = median(v_prima), median(v_dopo)
    return (r < 1 and vd > vp) or (r > 1 and vd < vp)


def esamina_salti(barre: list[dict], date_split: set[str] | frozenset[str],
                  tolleranza: float = TOLLERANZA) -> dict[str, list[dict]]:
    """`barre`: dict con date, close, volume (opzionale), in ordine di data; `date_split`: date degli split registrati.
    Ritorna {"segnalati", "non_valutabili", "split_registrati"}."""
    out = {"segnalati": [], "non_valutabili": [], "split_registrati": []}
    n = len(barre)
    for t in range(1, n):
        c0, c1 = barre[t - 1].get("close"), barre[t].get("close")
        if not (_positivo(c0) and _positivo(c1)):
            continue
        r = c1 / c0
        k = rapporto_tipico(r, tolleranza)
        if k is None:
            continue
        a0, a1 = barre[t - 1].get("adjusted_close"), barre[t].get("adjusted_close")
        r_rett = (a1 / a0) if (_positivo(a0) and _positivo(a1)) else None
        voce = {"data": barre[t]["date"], "chiusura_prima": c0, "chiusura": c1, "rapporto": r, "rapporto_tipico": k,
                "volume_coerente": _volume_coerente(barre, t, r), "rapporto_rettificata": r_rett,
                "rettificata_continua": rettificata_continua(r, r_rett)}
        if barre[t]["date"] in date_split:
            out["split_registrati"].append(voce)
            continue
        dopo = [barre[t + j].get("close") for j in range(1, SEDUTE_DOPO + 1) if t + j < n]
        if len(dopo) < SEDUTE_DOPO or not all(_positivo(c) for c in dopo):
            out["non_valutabili"].append(dict(voce, motivo="meno di 20 sedute dopo" if len(dopo) < SEDUTE_DOPO
                                              else "chiusura mancante nelle 20 sedute dopo"))
            continue
        soglia = abs(math.log(k)) / 2
        if r < 1:
            torna = any(math.log(c / c1) >= soglia for c in dopo)
        else:
            torna = any(math.log(c / c1) <= -soglia for c in dopo)
        if not torna:
            out["segnalati"].append(voce)
    return out


def salti_split_mancanti(barre: list[dict], date_split: set[str] | frozenset[str]) -> list[dict]:
    """Solo i salti segnalati (vedi `esamina_salti`)."""
    return esamina_salti(barre, date_split)["segnalati"]


FASCE_PREZZO = ((0.05, "sotto 0,05"), (1.0, "fra 0,05 e 1"), (float("inf"), "sopra 1"))
SEDUTE_PIATTE = 20


def fascia_prezzo(salto: dict) -> str:
    """Fascia del prezzo più basso fra le due chiusure del salto."""
    p = min(salto["chiusura_prima"], salto["chiusura"])
    return next(nome for soglia, nome in FASCE_PREZZO if p < soglia)


def sequenze_volume_zero(barre: list[dict], minimo: int = SEDUTE_PIATTE) -> list[dict]:
    """Sequenze di almeno `minimo` sedute consecutive con volume zero e chiusura identica: [{"da", "a", "sedute"}]."""
    out = []
    inizio = None
    for i, b in enumerate(barre):
        piatta = b.get("volume") == 0 and b.get("close") is not None and (
            inizio is not None and b.get("close") == barre[inizio].get("close"))
        if piatta:
            continue
        if inizio is not None and i - inizio >= minimo:
            out.append({"da": barre[inizio]["date"], "a": barre[i - 1]["date"], "sedute": i - inizio})
        inizio = i if b.get("volume") == 0 and b.get("close") is not None else None
    if inizio is not None and len(barre) - inizio >= minimo:
        out.append({"da": barre[inizio]["date"], "a": barre[-1]["date"], "sedute": len(barre) - inizio})
    return out

