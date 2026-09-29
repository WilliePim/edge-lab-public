"""Unico punto di accesso ai dati per gli altri package. Nessuno legge i file dell'archivio direttamente.

Le funzioni leggono le viste DuckDB (`store/catalog.py`) create in memoria sull'archivio della configurazione
(`MARKET_DATA_DIR`) e restituiscono `pandas.DataFrame`.

**Simboli**: `CODICE.BORSA` come in EODHD (`AAPL.US`, `P_old.US`, `SAP.XETRA`, `BRK.B.US`). Il codice individua un periodo
di vita di un titolo: per sapere quale codice usare a una data, `listings(ticker=...)` (vedi `DATA_DICTIONARY.md`).

**Prezzi puliti per default**: `prices()` toglie i periodi segnalati dai controlli (salti sospetti, volume zero ripetuto,
barre prima della quotazione) che non sono stati verificati con un'altra fonte. `clean=False` restituisce tutto. Il filtro
per simbolo si applica prima dell'esclusione, così una richiesta legge solo i titoli chiesti.
"""
from __future__ import annotations

import datetime as dt
import itertools
import threading

from market_data import config as C

_locale = threading.local()
_generazione = itertools.count(1)
_attuale = [next(_generazione)]


class NonAncoraDisponibile(NotImplementedError):
    pass


def _con():
    con = getattr(_locale, "con", None)
    if con is None or getattr(_locale, "generazione", None) != _attuale[0]:
        import duckdb
        from market_data.store import catalog
        if con is not None:
            con.close()
        con = C.applica_limiti(duckdb.connect())
        _locale.problemi_verifiche = catalog.crea_viste(con, C.archivio())
        _locale.con, _locale.generazione = con, _attuale[0]
    return con


def refresh() -> None:
    """Ricrea le viste in tutti i thread alla prossima richiesta (dopo una normalizzazione, un aggiornamento, una verifica)."""
    _attuale[0] = next(_generazione)


def verification_problems() -> list[str]:
    """Righe del file delle verifiche saltate perché non valide."""
    _con()
    return list(getattr(_locale, "problemi_verifiche", []))


def _simboli(symbols) -> list[tuple[str, str]]:
    if isinstance(symbols, str):
        symbols = [symbols]
    out = []
    for s in symbols:
        if "." not in s:
            raise ValueError("simbolo senza borsa: {!r} (usa CODICE.BORSA, per esempio AAPL.US)".format(s))
        codice, borsa = s.rsplit(".", 1)
        if (codice, borsa) not in out:
            out.append((codice, borsa))
    return out


def _data(d) -> dt.date | None:
    if d is None or isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


def _valori(coppie) -> tuple[str, list]:
    return ", ".join("(?, ?)" for _ in coppie), [x for c in coppie for x in (c[1], c[0])]


def _per_simboli(vista: str, symbols, start, end, colonna_data: str = "date", ordine: str = "exchange, code, date"):
    coppie = _simboli(symbols)
    if not coppie:
        return _con().execute("SELECT * FROM {} WHERE false".format(vista)).df()
    valori, parametri = _valori(coppie)
    sql = "SELECT v.* FROM {} v JOIN (VALUES {}) AS s(exchange, code) USING (exchange, code) WHERE true".format(vista, valori)
    if start is not None:
        sql += " AND v.{} >= ?".format(colonna_data)
        parametri.append(_data(start))
    if end is not None:
        sql += " AND v.{} <= ?".format(colonna_data)
        parametri.append(_data(end))
    return _con().execute(sql + " ORDER BY " + ordine, parametri).df()


def prices(symbols, start=None, end=None, clean: bool = True):
    """Prezzi giornalieri: open, high, low, close (grezzi), adjusted_close (split e dividendi), volume, currency."""
    if not clean:
        return _per_simboli("prezzi", symbols, start, end)
    coppie = _simboli(symbols)
    if not coppie:
        return _con().execute("SELECT * FROM prezzi WHERE false").df()
    valori, par_s = _valori(coppie)
    filtri, par_d = "", []
    if start is not None:
        filtri += " AND p.date >= ?"
        par_d.append(_data(start))
    if end is not None:
        filtri += " AND p.date <= ?"
        par_d.append(_data(end))
    from market_data.store import catalog
    sql = """
        WITH s(exchange, code) AS (VALUES {v}),
        p AS (SELECT p.* FROM prezzi p JOIN s USING (exchange, code) WHERE {valido} {f}),
        seg AS (SELECT g.* FROM segnalazioni g JOIN (VALUES {v}) AS s2(exchange, code) USING (exchange, code)
                WHERE g.esclude),
        ver AS (SELECT x.* FROM verifiche x JOIN (VALUES {v}) AS s3(exchange, code) USING (exchange, code)),
        aperte AS (SELECT seg.* FROM seg WHERE NOT EXISTS (
            SELECT 1 FROM ver WHERE ver.exchange = seg.exchange AND ver.code = seg.code AND ver.controllo = seg.controllo
              AND ver.from_date <= seg.from_date AND ver.to_date >= seg.to_date))
        SELECT p.* FROM p WHERE NOT EXISTS (
            SELECT 1 FROM aperte a WHERE a.exchange = p.exchange AND a.code = p.code AND p.date BETWEEN a.from_date AND a.to_date)
        ORDER BY exchange, code, date
    """.format(v=valori, f=filtri, valido=catalog.PREZZO_VALIDO.format(p="p"))
    return _con().execute(sql, par_s + par_d + par_s + par_s).df()


def dividends(symbols, start=None, end=None):
    """Dividendi per data di stacco: value (rettificato per gli split noti al download), unadjusted_value, currency, date di
    dichiarazione, registrazione e pagamento."""
    return _per_simboli("dividendi", symbols, start, end)


def splits(symbols, start=None, end=None):
    """Split e raggruppamenti: ratio (testo del fornitore, nuove/vecchie), factor = nuove / vecchie."""
    return _per_simboli("split", symbols, start, end)


def listings(exchange: str | None = None, ticker: str | None = None, isin: str | None = None, code: str | None = None):
    """Anagrafica: un record per codice (periodo di vita), con ISIN, date della prima e dell'ultima barra, gemelli."""
    sql, parametri = "SELECT * FROM anagrafica WHERE true", []
    for colonna, valore in (("exchange", exchange), ("ticker", ticker), ("isin", isin), ("code", code)):
        if valore is not None:
            sql += " AND {} = ?".format(colonna)
            parametri.append(valore)
    return _con().execute(sql + " ORDER BY exchange, ticker, first_date NULLS LAST, code", parametri).df()


def fx(pairs, start=None, end=None):
    """Cambi giornalieri (EODHD `FOREX`): pair come «EURUSD» = dollari per un euro."""
    if isinstance(pairs, str):
        pairs = [pairs]
    return _per_simboli("(SELECT *, pair AS code FROM cambi)", ["{}.FOREX".format(p) for p in pairs], start, end)


def trading_days(exchange: str, start=None, end=None) -> list[dt.date]:
    """Sedute della borsa dalla libreria `exchange_calendars` (Parigi e Xetra: non affidabile prima del 1999)."""
    sql, parametri = "SELECT date FROM calendario WHERE exchange = ?", [exchange]
    if start is not None:
        sql += " AND date >= ?"
        parametri.append(_data(start))
    if end is not None:
        sql += " AND date <= ?"
        parametri.append(_data(end))
    return [r[0] for r in _con().execute(sql + " ORDER BY date", parametri).fetchall()]


def treasury(curve: str | None = None, start=None, end=None):
    """Tesoro USA: curve «yield-rates», «bill-rates», «long-term-rates», «real-yield-rates»."""
    sql, parametri = "SELECT * FROM tesoro WHERE true", []
    for cond, valore in (("curve = ?", curve), ("date >= ?", _data(start)), ("date <= ?", _data(end))):
        if valore is not None:
            sql += " AND " + cond
            parametri.append(valore)
    return _con().execute(sql + " ORDER BY curve, date, tenor", parametri).df()


def flags(symbols=None):
    """Periodi segnalati dai controlli di qualità, con `verified` vero se una verifica da un'altra fonte li copre.

    `esclude` distingue le due cose che stanno in questa tabella: i periodi tolti dai prezzi puliti (vero) e le note
    che spiegano un salto senza togliere niente (falso) -- lo split che il fornitore ha applicato alla chiusura
    rettificata, il salto che il bilancio della società conferma come movimento vero."""
    base = """(SELECT g.*, EXISTS (SELECT 1 FROM verifiche v WHERE v.exchange = g.exchange AND v.code = g.code
                                   AND v.controllo = g.controllo AND v.from_date <= g.from_date AND v.to_date >= g.to_date)
               AS verified FROM segnalazioni g)"""
    if symbols is None:
        return _con().execute("SELECT * FROM {} ORDER BY exchange, code, from_date".format(base)).df()
    return _per_simboli(base, symbols, None, None, ordine="exchange, code, from_date")


def verifications(symbols=None):
    """Verifiche fatte a mano (file `verifiche.jsonl`) che rimettono nei prezzi puliti un periodo segnalato."""
    if symbols is None:
        return _con().execute("SELECT * FROM verifiche ORDER BY exchange, code, from_date").df()
    return _per_simboli("verifiche", symbols, None, None, ordine="exchange, code, from_date")


def liquidity(symbols=None):
    """Barre senza prezzo per titolo: quante, che quota, e se supera il 20% oltre il quale il titolo non ha abbastanza
    sedute quotate per starci dentro un backtest. Le barre senza prezzo non compaiono in `prices(clean=True)`."""
    if symbols is None:
        return _con().execute("SELECT * FROM liquidita ORDER BY exchange, code").df()
    return _per_simboli("liquidita", symbols, None, None, colonna_data=None, ordine="exchange, code")
