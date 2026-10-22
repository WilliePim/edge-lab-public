"""Eventi del Test F (segnali precoci): ribassi dell'S&P 500 di almeno il 15% dal massimo delle chiusure dei 12 mesi
precedenti, affiancati alla definizione comune del filone (massimo storico, `episodi.py`, non modificato).

Fermata 1 (30-09-2026): solo la lista degli eventi e la loro classificazione. Nessun segnale, nessun colpito, nessun
rendimento. Dati solo da `market_data.api`: chiusure di `GSPC.INDX` (archivio EODHD, dal 1927-12-30) e `USRECM`
(FRED, 1 dal mese del picco NBER al mese del minimo compreso; verificato contro la tabella NBER il 30-09-2026).

Regola dell'evento a 12 mesi (proposta alla fermata 1, ADR-060):
- M_t = massimo delle chiusure nei 12 mesi di calendario che finiscono in t, t compresa e il giorno t − 1 anno escluso
  (circa 252 sedute). Serve un anno intero di storia prima di t.
- Un evento **parte** alla prima seduta T in cui chiusura_T <= (1 − 15%) × M_T mentre nessun evento è aperto. Il
  **massimo dell'evento** è la seduta P della chiusura M_T (la prima, in caso di parità): P è fissato a T e non cambia.
- L'evento **resta aperto** finché l'indice non segna un nuovo massimo a 12 mesi: la prima seduta R > T con chiusura
  strettamente superiore a tutte le chiusure dei 12 mesi precedenti. **Fondo** = chiusura minima fra P e R. Se R non
  arriva entro la fine della serie, l'evento è aperto e il fondo è provvisorio.
- Nessun nuovo evento parte mentre uno è aperto, quindi la stessa discesa non si conta due volte; il massimo del nuovo
  evento è sempre >= R del precedente (a R la chiusura supera tutto l'anno prima, quindi nessuna seduta prima di R può
  essere il massimo a 12 mesi di una seduta successiva).

    python backtest/drawdown_alpha/eventi_f.py
"""
from __future__ import annotations

import datetime as dt
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from market_data import api

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from episodi import Episodio, episodi_drawdown  # noqa: E402  (definizione comune del filone: massimo storico)

INDICE = "GSPC.INDX"
SOGLIA = 0.15
PERIODO = (dt.date(1973, 1, 1), dt.date(2025, 12, 31))
MESI_PRIMA_RECESSIONE = 12
#  24 mesi interi di tutti e cinque i segnali prima del massimo: l'EBP parte dal gennaio 1973 (la serie più corta),
#  quindi il primo massimo con la finestra completa è il 1975-01-01. ICSA parte dal 1967-01-07: per il composito a
#  quattro segnali (senza EBP) la media a 52 settimane esiste dal gennaio 1968 e la finestra completa dal 1970-01-01.
PRIMO_MASSIMO_CON_24_MESI = dt.date(1975, 1, 1)
PRIMO_MASSIMO_CON_24_MESI_SENZA_EBP = dt.date(1970, 1, 1)


@dataclass(frozen=True, slots=True)
class Evento:
    massimo_data: dt.date
    massimo: float
    soglia_data: dt.date          # prima chiusura <= massimo × (1 − 15%)
    sedute_alla_soglia: int       # sedute da P a T
    fondo_data: dt.date
    fondo: float
    chiusura_data: dt.date | None  # R: nuovo massimo (a 12 mesi, o storico); None = ancora aperto
    profondita: float             # fondo / massimo − 1, negativa


def chiusure() -> list[tuple[dt.date, float]]:
    p = api.prices(INDICE)        # prezzi puliti; GSPC.INDX non ha segnalazioni (api.flags, letto il 30-09-2026)
    if len(p) == 0:
        raise RuntimeError("{}: nessuna chiusura nell'archivio -- fermarsi, non inventare dati".format(INDICE))
    return [(d.date(), float(c)) for d, c in zip(p["date"], p["close"])]


def un_anno_prima(d: dt.date) -> dt.date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:            # 29 febbraio
        return d.replace(year=d.year - 1, day=28)


def eventi_12_mesi(righe: list[tuple[dt.date, float]], soglia: float = SOGLIA) -> list[Evento]:
    date = [d for d, _ in righe]
    val = [v for _, v in righe]
    coda: deque[int] = deque()    # indici della finestra con chiusure decrescenti: in testa il massimo (il primo, a parità)
    aperto: dict | None = None
    out: list[Evento] = []

    def chiudi(a: dict, r: int | None) -> Evento:
        p, t, f = a["picco"], a["soglia"], a["fondo"]
        return Evento(date[p], val[p], date[t], t - p, date[f], val[f], date[r] if r is not None else None,
                      val[f] / val[p] - 1.0)

    for i, (d, v) in enumerate(righe):
        limite = un_anno_prima(d)
        while coda and date[coda[0]] <= limite:
            coda.popleft()
        while coda and val[coda[-1]] < v:
            coda.pop()
        coda.append(i)
        i_max = coda[0]
        if aperto is None:
            if date[0] <= limite and v <= (1.0 - soglia) * val[i_max]:
                aperto = {"picco": i_max, "soglia": i, "fondo": i}
        else:
            if v < val[aperto["fondo"]]:
                aperto["fondo"] = i
            if i_max == i:        # chiusura strettamente sopra tutto l'anno prima: nuovo massimo a 12 mesi
                out.append(chiudi(aperto, i))
                aperto = None
    if aperto is not None:
        out.append(chiudi(aperto, None))
    return out


def eventi_massimo_storico(righe: list[tuple[dt.date, float]], soglia: float = SOGLIA) -> list[Evento]:
    """La definizione comune del filone (`episodi.py`), con in più la data del −15% e le sedute per arrivarci."""
    per_data = {d: i for i, (d, _) in enumerate(righe)}
    val = [v for _, v in righe]
    out = []
    ep: Episodio
    for ep in episodi_drawdown([(d.isoformat(), v) for d, v in righe], soglia):
        p = per_data[dt.date.fromisoformat(ep.picco_data)]
        t = next(i for i in range(p + 1, len(val)) if val[i] <= (1.0 - soglia) * val[p])
        out.append(Evento(righe[p][0], ep.picco_valore, righe[t][0], t - p, dt.date.fromisoformat(ep.fondo_data),
                          ep.fondo_valore, dt.date.fromisoformat(ep.recupero_data) if ep.recupero_data else None,
                          -ep.drawdown))
    return out


def fine_mese(d: dt.date) -> dt.date:
    return (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)


def mesi_prima(d: dt.date, mesi: int) -> dt.date:
    """`mesi` mesi di calendario prima (negativi: dopo); il giorno resta, o scende all'ultimo del mese se non esiste."""
    m = d.month - mesi
    anno, mese = d.year + (m - 1) // 12, (m - 1) % 12 + 1
    ultimo = fine_mese(dt.date(anno, mese, 1)).day
    return dt.date(anno, mese, min(d.day, ultimo))


def recessioni() -> list[tuple[dt.date, dt.date]]:
    """(primo giorno del mese di picco NBER, ultimo giorno del mese di minimo), da USRECM."""
    df = api.fred("USRECM")
    out, inizio, precedente = [], None, None
    for d, v in zip(df["date"], df["value"]):
        d = d.date()
        if v >= 0.5 and inizio is None:
            inizio = d
        elif v < 0.5 and inizio is not None:
            out.append((inizio, fine_mese(precedente)))
            inizio = None
        precedente = d
    if inizio is not None:
        out.append((inizio, fine_mese(precedente)))
    return out


def recessione_associata(ev: Evento, rec: list[tuple[dt.date, dt.date]], mese_dopo_il_picco: bool = False,
                         mesi: int = MESI_PRIMA_RECESSIONE) -> tuple[dt.date, dt.date] | None:
    """La recessione il cui inizio è nei `mesi` dopo il massimo (inclusi) o che contiene il massimo.

    Inizio = mese del picco NBER (USRECM), oppure il mese dopo (USREC, «la recessione inizia il mese dopo il picco»)
    con `mese_dopo_il_picco`: le due convenzioni si confrontano per segnalare i casi al limite."""
    for inizio, fine in rec:
        ini = (fine_mese(inizio) + dt.timedelta(days=1)) if mese_dopo_il_picco else inizio
        if mesi_prima(ini, mesi) <= ev.massimo_data <= fine:
            return inizio, fine
    return None


def stato(ev: Evento, rec_ass, senza_ebp: bool = False) -> str:
    if not (PERIODO[0] <= ev.massimo_data and ev.soglia_data <= PERIODO[1]):
        return "non incluso (fuori dal 1973-2025)"
    if rec_ass is None:
        return "descrittivo (senza recessione)"
    primo = PRIMO_MASSIMO_CON_24_MESI_SENZA_EBP if senza_ebp else PRIMO_MASSIMO_CON_24_MESI
    if ev.massimo_data < primo:
        return "descrittivo (meno di 24 mesi di dati)"
    return "verdetto"


def _f(d: dt.date | None) -> str:
    return d.isoformat() if d else "aperto"


def tabella(nome: str, eventi: list[Evento], rec: list[tuple[dt.date, dt.date]], dal: dt.date) -> str:
    righe = ["### {}".format(nome), "",
             "| # | massimo | data −15% | sedute | fondo | profondità | chiusura evento | recessione NBER | stato |",
             "|---|---|---|---:|---|---:|---|---|---|"]
    n = 0
    for ev in eventi:
        if ev.massimo_data < dal:
            continue
        n += 1
        r1 = recessione_associata(ev, rec)
        r2 = recessione_associata(ev, rec, mese_dopo_il_picco=True)
        testo_rec = "{} → {}".format(r1[0].strftime("%Y-%m"), r1[1].strftime("%Y-%m")) if r1 else "no"
        if (r1 is None) != (r2 is None):
            testo_rec += " **(al limite: {} con l'inizio al mese dopo il picco)**".format("no" if r2 is None else "sì")
        righe.append("| {} | {} ({:,.2f}) | {} | {} | {} ({:,.2f}) | {:.1%} | {} | {} | {} |".format(
            n, ev.massimo_data, ev.massimo, ev.soglia_data, ev.sedute_alla_soglia, ev.fondo_data, ev.fondo,
            ev.profondita, _f(ev.chiusura_data), testo_rec, stato(ev, r1)))
    return "\n".join(righe)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")       # la console di Windows è cp1252: le frecce delle tabelle non ci stanno
    righe = chiusure()
    print("{}: {} sedute, {} → {}\n".format(INDICE, len(righe), righe[0][0], righe[-1][0]))
    rec = recessioni()
    print("Recessioni NBER da USRECM (mese del picco → mese del minimo): " + ", ".join(
        "{}→{}".format(a.strftime("%Y-%m"), b.strftime("%Y-%m")) for a, b in rec if a.year >= 1960) + "\n")
    dal = dt.date(1966, 1, 1)
    print(tabella("A — massimo delle chiusure degli ultimi 12 mesi (regola del Test F)", eventi_12_mesi(righe), rec, dal))
    print()
    print(tabella("B — massimo storico (definizione comune del filone, `episodi.py`)", eventi_massimo_storico(righe), rec, dal))
    sys.exit(0)
