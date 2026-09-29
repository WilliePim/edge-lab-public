"""Calendario delle sedute per borsa: libreria `exchange_calendars`, confrontata con le date di un titolo molto liquido.

La libreria dà sessioni e festività senza chiamate; EODHD All World non ha l'endpoint delle festività. Il confronto con
un titolo liquido della borsa trova le differenze nei due sensi:
- **solo nella libreria**: sedute senza prezzo per il titolo (buco nei dati, sospensione, o seduta che la libreria
  sbaglia);
- **solo nel titolo**: prezzi in giorni che la libreria considera chiusi (festività mancante nella libreria, o barra
  spuria nei dati).

TSX Venture (`V`) non ha un calendario suo nella libreria: usa quello di Toronto (docs/adr/005-fase1-scelte.md).
"""
from __future__ import annotations

CALENDARI = {
    "US": "XNYS", "ST": "XSTO", "HE": "XHEL", "CO": "XCSE", "OL": "XOSL", "LSE": "XLON", "XETRA": "XETR", "F": "XFRA",
    "PA": "XPAR", "AS": "XAMS", "BR": "XBRU", "LS": "XLIS", "MI": "XMIL", "SW": "XSWX", "MC": "XMAD", "VI": "XWBO",
    "TO": "XTSE", "V": "XTSE", "TSE": "XTKS", "AU": "XASX", "HK": "XHKG",
}
INIZIO_DESIDERATO = "1990-01-01"


def sessioni(borsa: str, da: str, a: str) -> list[str]:
    """Sessioni della libreria fra da e a (compresi), come date ISO. Parte dal primo giorno che la libreria accetta."""
    import exchange_calendars as xc        # import pigro: il resto del package non ne dipende
    from exchange_calendars.errors import CalendarError
    codice = CALENDARI[borsa]
    classe = xc.get_calendar(codice).__class__
    limite = classe.bound_min() if hasattr(classe, "bound_min") else None
    inizio_richiesto = da if limite is None else max(da, limite.date().isoformat())
    try:
        cal = xc.get_calendar(codice, start=inizio_richiesto, end=max(a, inizio_richiesto))
    except (ValueError, CalendarError):    # fuori dai limiti, o nessuna seduta (un fine settimana)
        cal = xc.get_calendar(codice)          # finestra predefinita: il periodo del confronto lo dichiara
    inizio = max(da, cal.first_session.date().isoformat())
    fine = min(a, cal.last_session.date().isoformat())
    if inizio > fine:
        return []
    return [d.date().isoformat() for d in cal.sessions_in_range(inizio, fine)]


def confronta(sessioni_libreria: list[str], date_titolo: list[str]) -> dict:
    """Differenze nel periodo comune (dal più tardo dei due inizi al più presto delle due fini)."""
    if not sessioni_libreria or not date_titolo:
        return {"periodo": None, "sessioni_libreria": len(sessioni_libreria), "barre_titolo": len(date_titolo),
                "solo_libreria": [], "solo_titolo": []}
    da = max(sessioni_libreria[0], min(date_titolo))
    a = min(sessioni_libreria[-1], max(date_titolo))
    lib = {d for d in sessioni_libreria if da <= d <= a}
    tit = {d for d in date_titolo if da <= d <= a}
    return {"periodo": (da, a), "sessioni_libreria": len(lib), "barre_titolo": len(tit),
            "solo_libreria": sorted(lib - tit), "solo_titolo": sorted(tit - lib)}


INIZIO_TABELLA = "1960-01-01"      # prima del 1985 non verificato: la libreria non chiude tutti i Capodanni


def scrivi_calendario(archivio, borse=None, fine: str | None = None) -> dict:
    """Tabella `calendario` (partizione per borsa): sedute della libreria dal 1960 (o dal suo limite) a un anno da oggi."""
    import datetime as dt

    import pyarrow as pa

    from market_data.store import catalog  # noqa: F401  (registra lo schema del calendario)
    from market_data.store import normalize as N

    fine = fine or (dt.date.today() + dt.timedelta(days=365)).isoformat()
    base, man = archivio / "eodhd" / "parquet", archivio / "eodhd" / "manifest"
    out = {}
    for borsa in borse or sorted(CALENDARI):
        giorni = sessioni(borsa, INIZIO_TABELLA, fine)
        part = N.Partizione(base, man, "calendario", borsa)
        part.aggiungi(pa.table({"date": [dt.date.fromisoformat(g) for g in giorni]}, schema=N.SCHEMI["calendario"]))
        out[borsa] = part.chiudi([{"file": "exchange_calendars", "sha256": "libreria {}".format(CALENDARI[borsa])}])
    return out
