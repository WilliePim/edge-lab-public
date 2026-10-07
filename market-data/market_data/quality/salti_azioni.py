"""Verifica dei salti sospetti con le azioni in circolazione depositate alla SEC prima e dopo il salto.

Un `salto_sospetto` (`checks.py`) è un salto giornaliero vicino a un rapporto di split, senza split registrato e senza
ritorno: può essere uno split che il fornitore non conosce (la serie prima del salto è su un'altra scala) oppure un
movimento vero del prezzo (un crollo della metà, un raddoppio). Finché non si sa, i prezzi puliti tolgono tutta la
storia prima del salto. Dal 2019 il confronto con i massimi dichiarati nel 10-K non è più possibile (`bilanci.py`).
Qui la domanda si fa alle azioni in circolazione:

- **split vero**: le azioni cambiano dell'inverso del salto del prezzo (prezzo dimezzato, azioni raddoppiate);
- **movimento vero**: le azioni non cambiano;
- **non determinabile**: tutto il resto. Resta com'è oggi: escluso.

**Opzione esplicita, mai il default.** Niente di questo modulo entra in `prices(clean=True)` se non lo si chiede con
`verifica_salti="azioni"`; le segnalazioni, le verifiche scritte a mano e i prezzi puliti di default restano identici.
Decisioni, tolleranze e rischio residuo in docs/adr/010.

## Regola

Per ogni salto del giorno G con rapporto tipico k (0,5 per un dimezzamento, 2 per un raddoppio, …) e per ognuna delle
tre voci di `api.sec_azioni` (frontespizio, stato patrimoniale, media ponderata), con unità `shares`:

- **prima** = l'osservazione con la data di riferimento più recente fra quelle con `fine < G` **e** `depositato < G`
  (depositata prima del salto: così non è un comparativo riesposto dopo uno split), non più vecchia di 200 giorni;
- **dopo** = l'osservazione con la data di riferimento più vicina fra quelle con `fine >= G` (per la media ponderata
  `inizio >= G`: il periodo sta tutto dopo), entro 200 giorni; a parità di data, il primo deposito;
- per la media ponderata valgono solo i periodi di al più 125 giorni (un trimestre);
- più valori con la stessa data nello stesso deposito si sommano (classi riportate separatamente).

Con q = azioni dopo / azioni prima: la voce dice **movimento vero** se q sta entro ±25% da 1 (|ln q| ≤ ln 1,25), **split
vero** se q sta entro ±25% da 1/k (|ln(q·k)| ≤ ln 1,25), altrimenti niente. L'esito del salto è quello della prima voce,
nell'ordine, che dice qualcosa; se un'altra voce dice il contrario, o nessuna dice niente, o mancano CIK, rapporto o
osservazioni: **non determinabile**, con il motivo.
"""
from __future__ import annotations

import datetime as dt
import math
import re

FINESTRA_GIORNI = 200
TOLLERANZA = 1.25               # rapporto: entro ±25% (in logaritmo)
MEDIA_GIORNI_MAX = 125
UNITA = "shares"
SPLIT_VERO, MOVIMENTO_VERO, NON_DETERMINABILE = "split_vero", "movimento_vero", "non_determinabile"
CONTROLLO = "salto_sospetto"
DETTAGLIO = re.compile(r"salto del (\d{4}-\d{2}-\d{2}): rapporto (\d+(?:\.\d+)?) vicino a (\d+(?:\.\d+)?(?:e-?\d+)?)")
COLONNE = ("exchange", "code", "from_date", "to_date", "data_salto", "rapporto", "rapporto_tipico", "cik", "esito", "voce",
           "azioni_prima", "fine_prima", "azioni_dopo", "fine_dopo", "rapporto_azioni", "motivo")


def leggi_dettaglio(detail) -> tuple[dt.date, float, float] | None:
    """(giorno del salto, rapporto, rapporto tipico) dal testo della segnalazione, o None se non ha quella forma."""
    m = DETTAGLIO.search(detail if isinstance(detail, str) else "")
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1)), float(m.group(2)), float(m.group(3))
    except ValueError:
        return None


def giudizio(azioni_prima: float, azioni_dopo: float, rapporto_tipico: float) -> str | None:
    """Che cosa dice una coppia di osservazioni: movimento vero, split vero, o None."""
    if not (azioni_prima and azioni_dopo and rapporto_tipico) or azioni_prima <= 0 or azioni_dopo <= 0 or rapporto_tipico <= 0:
        return None
    q, soglia = azioni_dopo / azioni_prima, math.log(TOLLERANZA) + 1e-12
    if abs(math.log(q)) <= soglia:
        return MOVIMENTO_VERO
    if abs(math.log(q * rapporto_tipico)) <= soglia:
        return SPLIT_VERO
    return None


def _somma_per_deposito(osservazioni) -> list[tuple]:
    """(inizio, fine, depositato, accn) → somma dei valori: le classi riportate separatamente nello stesso deposito."""
    per: dict = {}
    for inizio, fine, valore, depositato, accn in osservazioni:
        k = (inizio, fine, depositato, accn)
        per[k] = per.get(k, 0.0) + valore
    return [(i, f, v, d, a) for (i, f, d, a), v in per.items()]


def attorno(osservazioni, giorno: dt.date, media: bool = False):
    """((azioni, fine) prima, (azioni, fine) dopo) per una voce; ciascuno None se manca dentro la finestra.

    `osservazioni`: (inizio o None, fine, valore, depositato, accn), date come `datetime.date`."""
    oss = _somma_per_deposito(osservazioni)
    if media:
        oss = [o for o in oss if o[0] is not None and (o[1] - o[0]).days + 1 <= MEDIA_GIORNI_MAX]
    finestra = dt.timedelta(days=FINESTRA_GIORNI)
    prima = [o for o in oss if o[1] < giorno and o[3] < giorno and giorno - o[1] <= finestra]
    dopo = [o for o in oss if (o[0] if media else o[1]) >= giorno and o[1] - giorno <= finestra]
    p = max(prima, key=lambda o: (o[1], o[3], o[4])) if prima else None
    d = min(dopo, key=lambda o: (o[1], o[3], o[4])) if dopo else None
    return ((p[2], p[1]) if p else None), ((d[2], d[1]) if d else None)


def classifica(per_voce: dict, voci, giorno: dt.date, rapporto_tipico: float) -> dict:
    """Esito di un salto: `per_voce` = {voce: osservazioni}; `voci` = le tre voci nell'ordine (l'ultima è la media)."""
    detti, senza_coppia = [], 0
    for i, voce in enumerate(voci):
        prima, dopo = attorno(per_voce.get(voce) or (), giorno, media=(i == len(voci) - 1))
        if prima is None or dopo is None:
            senza_coppia += 1
            continue
        detti.append((giudizio(prima[0], dopo[0], rapporto_tipico), voce, prima, dopo))
    vuoto = {"esito": NON_DETERMINABILE, "voce": None, "azioni_prima": None, "fine_prima": None, "azioni_dopo": None,
             "fine_dopo": None, "rapporto_azioni": None}
    if not detti:
        return dict(vuoto, motivo="nessuna voce con azioni prima e dopo il salto entro {} giorni".format(FINESTRA_GIORNI))
    chiari = [d for d in detti if d[0] is not None]
    scelto = chiari[0] if chiari else detti[0]
    _g, voce, prima, dopo = scelto
    riga = {"voce": voce, "azioni_prima": prima[0], "fine_prima": prima[1], "azioni_dopo": dopo[0], "fine_dopo": dopo[1],
            "rapporto_azioni": dopo[0] / prima[0] if prima[0] else None}
    if not chiari:
        return dict(riga, esito=NON_DETERMINABILE, motivo="le azioni non sono né ferme né cambiate dell'inverso del salto")
    if len({d[0] for d in chiari}) > 1:
        return dict(riga, esito=NON_DETERMINABILE, motivo="le voci delle azioni sono in disaccordo")
    return dict(riga, esito=scelto[0], motivo=None)


def _data(x) -> dt.date | None:
    if x is None or x != x:
        return None
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    return dt.date.fromisoformat(str(x)[:10])


def classifica_segnalazioni(segnalazioni: list[dict], azioni, voci) -> list[dict]:
    """Una riga (`COLONNE`) per segnalazione `salto_sospetto`.

    `segnalazioni`: dict con exchange, code, from_date, to_date, detail, cik (o None).
    `azioni`: la tabella di `api.sec_azioni` per i CIK presenti (può essere vuota)."""
    per_cik: dict = {}
    if azioni is not None and len(azioni):
        buone = azioni[azioni["unita"] == UNITA]
        for cik, voce, inizio, fine, valore, depositato, accn in zip(buone["cik"], buone["voce"], buone["inizio"], buone["fine"],
                                                                    buone["valore"], buone["depositato"], buone["accn"]):
            f, d = _data(fine), _data(depositato)
            if f is None or d is None:
                continue
            per_cik.setdefault(int(cik), {}).setdefault(voce, []).append((_data(inizio), f, float(valore), d, accn))
    out = []
    for s in segnalazioni:
        base = {"exchange": s["exchange"], "code": s["code"], "from_date": _data(s["from_date"]), "to_date": _data(s["to_date"]),
                "data_salto": None, "rapporto": None, "rapporto_tipico": None, "cik": s.get("cik"), "esito": NON_DETERMINABILE,
                "voce": None, "azioni_prima": None, "fine_prima": None, "azioni_dopo": None, "fine_dopo": None,
                "rapporto_azioni": None, "motivo": None}
        letto = leggi_dettaglio(s.get("detail"))
        if letto is None:
            out.append(dict(base, motivo="la segnalazione non riporta giorno e rapporto del salto"))
            continue
        base.update(data_salto=letto[0], rapporto=letto[1], rapporto_tipico=letto[2])
        if s.get("cik") is None:
            out.append(dict(base, motivo="titolo senza CIK"))
            continue
        if int(s["cik"]) not in per_cik:
            out.append(dict(base, motivo="nessuna osservazione delle azioni nei file SEC"))
            continue
        out.append(dict(base, **classifica(per_cik[int(s["cik"])], voci, letto[0], letto[2])))
    return out
