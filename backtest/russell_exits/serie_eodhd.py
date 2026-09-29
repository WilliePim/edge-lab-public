"""Russell 2000, uscite verso il basso — serie di prezzi e volumi dall'archivio EODHD, nella forma di quelle Yahoo.

`analisi.py` lavora su tuple `(close, adj, vol, frazionamenti, ultima data)` allineate al calendario delle sedute,
come le restituiva `verifica_identita.serie_allineata` leggendo i file Yahoo. Qui le stesse tuple si costruiscono
dall'archivio EODHD, letto solo tramite `market_data.api` (ADR-040).

**Tre corrispondenze, e perché.**

- `close` è la **chiusura rettificata per i soli frazionamenti**, come la `Close` di Yahoo che la pre-registrazione
  prescrive (§6). EODHD non la dà pronta: ha la chiusura grezza e quella rettificata anche per i dividendi. Si
  ricostruisce dalla grezza, dividendo per i frazionamenti con data successiva. Verificato su Apple: il 28-08-2020
  la grezza è 499,23, il frazionamento 4:1 del 31 agosto la porta a 124,81, che è la `Close` di Yahoo.
- `adj` è la `adjusted_close` di EODHD, rettificata per frazionamenti e dividendi come la `Adj Close` di Yahoo.
  Serve al rendimento a sei mesi del terzile (§5).
- `vol` è il volume di EODHD, **già rettificato per i frazionamenti dal fornitore** come quello di Yahoo: il
  28-08-2020 Apple ha 187,6 milioni, cioè 46,9 milioni di azioni prima del 4:1, moltiplicate per quattro.

**I frazionamenti** vengono dalla tabella del fornitore più le note `split_del_fornitore` dell'archivio: i salti in
cui la chiusura rettificata resta continua, cioè frazionamenti che il fornitore ha applicato ai prezzi rettificati
ma non ha messo in tabella. Senza queste, la chiusura ricostruita salterebbe dove il titolo non ha fatto niente. Il
fattore di una nota è il rapporto tipico più vicino al salto della grezza, con la stessa lista di rapporti e la
stessa tolleranza del controllo che ha scritto la nota.

**Prezzi puliti.** Le serie vengono da `api.prices(clean=True)`: senza i periodi esclusi dai controlli di qualità
(salti sospetti non verificati, volume zero ripetuto, barre prima della quotazione) e senza le chiusure a zero. Dove
manca una barra la serie ha un buco, e la regola dell'80% di barre presenti (§3, esclusione 3) lo conta.
"""
from __future__ import annotations

import datetime as dt
import math
from array import array

from market_data import api

NAN = float("nan")
BLOCCO = 400                      # codici per richiesta: il picco di memoria resta basso

#  La stessa lista e la stessa tolleranza del controllo dei salti dell'archivio, che ha scritto le note.
RAPPORTI_SPLIT = (2, 3, 4, 5, 8, 10, 15, 20, 25, 50, 100)
CANDIDATI = tuple(float(k) for k in RAPPORTI_SPLIT) + tuple(1.0 / k for k in RAPPORTI_SPLIT)
TOLLERANZA = 0.05

_cache: dict[str, tuple | None] = {}


def rapporto_tipico(r: float) -> float | None:
    """Il rapporto tipico di frazionamento entro ±5% da `r`, o None."""
    if not r or r <= 0:
        return None
    for k in CANDIDATI:
        if abs(r / k - 1.0) <= TOLLERANZA + 1e-9:
            return k
    return None


def _giorno(x) -> str:
    return str(x)[:10]


def frazionamenti(tabella: list[tuple[str, float]], note: list[str], grezza: dict[str, float]) -> list[tuple[str, float]]:
    """Frazionamenti della tabella più quelli delle note `split_del_fornitore`, senza doppioni.

    Il fattore di una nota è l'inverso del rapporto tipico del salto della grezza: un 4:1 porta la grezza da 499 a
    129, rapporto 0,258, tipico 1/4, fattore 4 -- la convenzione di Yahoo e della tabella di EODHD."""
    fuori = {d: f for d, f in tabella if f and f > 0}
    date_ordinate = sorted(grezza)
    prima = {date_ordinate[i]: date_ordinate[i - 1] for i in range(1, len(date_ordinate))}
    for d in note:
        if d in fuori or d not in prima:
            continue
        k = rapporto_tipico(grezza[d] / grezza[prima[d]])
        if k:
            fuori[d] = 1.0 / k
    return sorted(fuori.items())


def rettificata_per_frazionamenti(grezza: dict[str, float], split: list[tuple[str, float]]) -> dict[str, float]:
    """Chiusura divisa per il prodotto dei frazionamenti con data successiva: la `Close` di Yahoo."""
    fuori = {}
    for d, c in grezza.items():
        f = 1.0
        for ds, s in split:
            if ds > d:
                f *= s
        fuori[d] = c / f
    return fuori


def carica(codici, ids: list[str]) -> None:
    """Porta in memoria le serie di questi codici EODHD americani, allineate a `ids`. A blocchi."""
    mancano = sorted({c for c in codici if c and c not in _cache})
    pos = {d: i for i, d in enumerate(ids)}
    n = len(ids)
    inizio, fine = ids[0], ids[-1]
    for i in range(0, len(mancano), BLOCCO):
        blocco = mancano[i:i + BLOCCO]
        simboli = ["{}.US".format(c) for c in blocco]
        prezzi = api.prices(simboli, start=inizio, end=fine, clean=True)
        tabella = api.splits(simboli)
        segnalazioni = api.flags(simboli)
        per_codice = {c: {"grezza": {}, "adj": {}, "vol": {}} for c in blocco}
        for code, d, c, a, v in zip(prezzi["code"], prezzi["date"], prezzi["close"],
                                    prezzi["adjusted_close"], prezzi["volume"]):
            g = _giorno(d)
            per_codice[code]["grezza"][g] = float(c)
            per_codice[code]["adj"][g] = float(a) if a == a and a is not None else NAN
            per_codice[code]["vol"][g] = float(v) if v == v and v is not None else NAN
        split_tab = {c: [] for c in blocco}
        for code, d, f in zip(tabella["code"], tabella["date"], tabella["factor"]):
            if code in split_tab and f == f and f:
                split_tab[code].append((_giorno(d), float(f)))
        note = {c: [] for c in blocco}
        for code, controllo, d in zip(segnalazioni["code"], segnalazioni["controllo"], segnalazioni["from_date"]):
            if code in note and controllo == "split_del_fornitore":
                note[code].append(_giorno(d))
        for c in blocco:
            s = per_codice[c]
            if not s["grezza"]:
                _cache[c] = None
                continue
            split = frazionamenti(split_tab[c], note[c], s["grezza"])
            close_sa = rettificata_per_frazionamenti(s["grezza"], split)
            close, adj, vol = array("d", [NAN]) * n, array("d", [NAN]) * n, array("d", [NAN]) * n
            for d, v in close_sa.items():
                k = pos.get(d)
                if k is not None:
                    close[k], adj[k], vol[k] = v, s["adj"].get(d, NAN), s["vol"].get(d, NAN)
            _cache[c] = (close, adj, vol, split, max(s["grezza"]))


def serie(codice: str | None) -> tuple | None:
    """(close, adj, vol, frazionamenti, ultima data) di un codice già caricato, o None."""
    if not codice:
        return None
    return _cache.get(codice)


_stesso_cik: dict[str, list[str]] | None = None


def stesso_cik(codice: str) -> list[str]:
    """Gli altri codici EODHD americani di azioni ordinarie con lo stesso CIK di `codice`, dall'anagrafica."""
    global _stesso_cik
    if _stesso_cik is None:
        df = api.listings(exchange="US")
        per_cik, cik_di = {}, {}
        for c, cik, tipo in zip(df["code"], df["cik"], df["type"]):
            if cik and tipo == "Common Stock":
                per_cik.setdefault(str(cik), []).append(c)
                cik_di[c] = str(cik)
        _stesso_cik = {c: [x for x in per_cik[k] if x != c] for c, k in cik_di.items()}
    return _stesso_cik.get(codice, [])


def serie_seguita(codice: str | None, ids: list[str]) -> tuple[tuple | None, str | None]:
    """(serie, codici seguiti o None): la serie di `codice` che prosegue sul codice nuovo quando la società cambia
    ticker, con le regole di `rendimenti.segui`. Carica da sé i codici dello stesso CIK."""
    import rendimenti as R
    ser = serie(codice)
    if ser is None:
        return None, None
    altri = stesso_cik(codice)
    carica(altri, ids)
    return R.segui(ser, {c: serie(c) for c in altri if serie(c) is not None})


def mercati() -> dict[str, str]:
    """codice EODHD americano -> mercato di quotazione (NASDAQ, NYSE, PINK, …) dall'anagrafica dell'archivio."""
    df = api.listings(exchange="US")
    return {c: (v or "sconosciuto") for c, v in zip(df["code"], df["venue"])}
