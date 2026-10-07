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
_salti: dict = {}                 # (borsa, codice) -> righe di `salti_classificati`, finché non si chiama `refresh()`
VERIFICHE_SALTI = ("azioni",)


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
    _salti.clear()


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


def prices(symbols, start=None, end=None, clean: bool = True, verifica_salti: str | None = None,
           barre_isolate: str | None = None):
    """Prezzi giornalieri: open, high, low, close (grezzi), adjusted_close (split e dividendi), volume, currency.

    `verifica_salti="azioni"` (solo con `clean=True`, mai di default): un periodo tolto per un `salto_sospetto` torna
    nei prezzi puliti se le azioni in circolazione depositate alla SEC prima e dopo il salto dicono che è stato un
    movimento vero del prezzo (`salti_classificati`, docs/adr/010). Split veri e casi non determinabili restano esclusi.

    `barre_isolate="scarta"` (solo con `clean=True`, mai di default): toglie le barre la cui `adjusted_close` va oltre
    il 50% da entrambe le barre vicine e torna (docs/adr/011). L'elenco: `barre_isolate(...)`."""
    if verifica_salti is not None and verifica_salti not in VERIFICHE_SALTI:
        raise ValueError("verifica_salti sconosciuta: {!r} (ammesso: {})".format(verifica_salti, ", ".join(VERIFICHE_SALTI)))
    if verifica_salti is not None and not clean:
        raise ValueError("verifica_salti vale solo per i prezzi puliti (clean=True)")
    if barre_isolate is not None:
        from market_data.quality import barre_isolate as BI
        if barre_isolate not in BI.OPZIONI:
            raise ValueError("barre_isolate sconosciuta: {!r} (ammesso: {})".format(barre_isolate, ", ".join(BI.OPZIONI)))
        if not clean:
            raise ValueError("barre_isolate vale solo per i prezzi puliti (clean=True)")
        tutta = prices(symbols, clean=True, verifica_salti=verifica_salti)        # la serie intera: le date dopo
        df = tutta[~_maschera_isolate(tutta)]
        if start is not None:
            df = df[df["date"] >= str(_data(start))]
        if end is not None:
            df = df[df["date"] <= str(_data(end))]
        return df.reset_index(drop=True)
    if not clean:
        return _per_simboli("prezzi", symbols, start, end)
    coppie = _simboli(symbols)
    if not coppie:
        return _con().execute("SELECT * FROM prezzi WHERE false").df()
    if verifica_salti is not None:
        return _prezzi_con_salti_verificati(coppie, start, end)
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


def _righe_salti(coppie) -> list[dict]:
    """Le righe di `salti_classificati` per questi (codice, borsa), con memoria per processo."""
    from market_data import sec as S
    from market_data.quality import salti_azioni as SA
    mancano = [c for c in coppie if (c[1], c[0]) not in _salti]
    for i in range(0, len(mancano), 2000):
        blocco = mancano[i:i + 2000]
        valori, par = _valori(blocco)
        seg = _con().execute("""
            SELECT g.exchange, g.code, g.from_date, g.to_date, g.detail, a.cik
            FROM segnalazioni g JOIN (VALUES {v}) AS s(exchange, code) USING (exchange, code)
            LEFT JOIN anagrafica a ON a.exchange = g.exchange AND a.code = g.code
            WHERE g.controllo = ? AND g.esclude
            ORDER BY g.exchange, g.code, g.from_date, g.to_date""".format(v=valori), par + [SA.CONTROLLO]).fetchall()
        righe = [{"exchange": e, "code": c, "from_date": f, "to_date": t, "detail": d,
                  "cik": int(k) if isinstance(k, str) and k.strip().isdigit() else None} for e, c, f, t, d, k in seg]
        cik = sorted({r["cik"] for r in righe if r["cik"] is not None})
        azioni = S.lettore(C.archivio()).bilancio(cik, S.VOCI_AZIONI, cache=True) if cik else None
        per: dict = {(c[1], c[0]): [] for c in blocco}
        for r in SA.classifica_segnalazioni(righe, azioni, S.VOCI_AZIONI):
            per[(r["exchange"], r["code"])].append(r)
        _salti.update(per)
    return [r for c in coppie for r in _salti[(c[1], c[0])]]


def salti_classificati(symbols=None):
    """I `salto_sospetto` che escludono, classificati con le azioni in circolazione depositate alla SEC prima e dopo
    il salto: `esito` = `split_vero`, `movimento_vero` o `non_determinabile`, con la voce usata, le due osservazioni e il
    motivo. Senza `symbols`: tutti i titoli USA con un salto segnalato. Non cambia niente nell'archivio: è il calcolo che
    `prices(..., verifica_salti="azioni")` usa. Legge i file SEC in blocco con la cache (docs/adr/009, 010)."""
    import pandas as pd
    from market_data.quality import salti_azioni as SA
    if symbols is None:
        coppie = [(c, e) for e, c in _con().execute(
            "SELECT DISTINCT exchange, code FROM segnalazioni WHERE controllo = ? AND esclude AND exchange = 'US' "
            "ORDER BY exchange, code", [SA.CONTROLLO]).fetchall()]
    else:
        coppie = _simboli(symbols)
    df = pd.DataFrame(_righe_salti(coppie), columns=list(SA.COLONNE))
    for c in ("from_date", "to_date", "data_salto", "fine_prima", "fine_dopo"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["cik"] = df["cik"].astype("Int64")
    return df


def _prezzi_con_salti_verificati(coppie, start, end):
    """`prices(clean=True)` in cui valgono come verifiche anche i salti classificati «movimento vero»."""
    from market_data.quality import salti_azioni as SA
    from market_data.store import catalog
    veri = [r for r in _righe_salti(coppie) if r["esito"] == SA.MOVIMENTO_VERO]
    valori, par_s = _valori(coppie)
    filtri, par_d = "", []
    if start is not None:
        filtri += " AND p.date >= ?"
        par_d.append(_data(start))
    if end is not None:
        filtri += " AND p.date <= ?"
        par_d.append(_data(end))
    in_piu, par_v = "", []
    if veri:
        in_piu = " UNION ALL SELECT * FROM (VALUES {}) AS z(exchange, code, controllo, from_date, to_date)".format(
            ", ".join("(?, ?, ?, CAST(? AS DATE), CAST(? AS DATE))" for _ in veri))
        par_v = [x for r in veri for x in (r["exchange"], r["code"], SA.CONTROLLO, r["from_date"], r["to_date"])]
    sql = """
        WITH s(exchange, code) AS (VALUES {v}),
        p AS (SELECT p.* FROM prezzi p JOIN s USING (exchange, code) WHERE {valido} {f}),
        seg AS (SELECT g.* FROM segnalazioni g JOIN (VALUES {v}) AS s2(exchange, code) USING (exchange, code)
                WHERE g.esclude),
        ver AS (SELECT x.exchange, x.code, x.controllo, x.from_date, x.to_date
                FROM verifiche x JOIN (VALUES {v}) AS s3(exchange, code) USING (exchange, code){in_piu}),
        aperte AS (SELECT seg.* FROM seg WHERE NOT EXISTS (
            SELECT 1 FROM ver WHERE ver.exchange = seg.exchange AND ver.code = seg.code AND ver.controllo = seg.controllo
              AND ver.from_date <= seg.from_date AND ver.to_date >= seg.to_date))
        SELECT p.* FROM p WHERE NOT EXISTS (
            SELECT 1 FROM aperte a WHERE a.exchange = p.exchange AND a.code = p.code AND p.date BETWEEN a.from_date AND a.to_date)
        ORDER BY exchange, code, date
    """.format(v=valori, f=filtri, valido=catalog.PREZZO_VALIDO.format(p="p"), in_piu=in_piu)
    return _con().execute(sql, par_s + par_d + par_s + par_s + par_v).df()


def _maschera_isolate(df):
    """Vero per le righe di `df` (prezzi puliti, in ordine di borsa, codice e data) che sono barre isolate (ADR 011)."""
    import numpy as np
    from market_data.quality import barre_isolate as BI
    out = np.zeros(len(df), dtype=bool)
    if not len(df):
        return out
    chiave = (df["exchange"].astype(str) + "\x00" + df["code"].astype(str)).to_numpy()
    giorni = df["date"].to_numpy().astype("datetime64[D]").astype("int64")
    valori = df["adjusted_close"].to_numpy(dtype=float)
    tagli = np.flatnonzero(chiave[1:] != chiave[:-1]) + 1
    for a, b in zip(np.r_[0, tagli], np.r_[tagli, len(df)]):
        out[a:b] = BI.isolate(giorni[a:b], valori[a:b])
    return out


def barre_isolate(symbols, verifica_salti: str | None = None):
    """Le barre che `prices(..., barre_isolate="scarta")` toglie: una riga per barra, con la barra prima e la barra
    dopo (`date_prima`, `close_prima`, `adjusted_prima`, …, `date_dopo`, `close_dopo`, `adjusted_dopo`) e il volume.
    Non cambia niente nell'archivio (docs/adr/011)."""
    import numpy as np
    df = prices(symbols, clean=True, verifica_salti=verifica_salti)
    k = np.flatnonzero(_maschera_isolate(df))
    out = df.iloc[k][["exchange", "code", "date", "close", "adjusted_close", "volume"]].reset_index(drop=True)
    for nome, passo in (("prima", -1), ("dopo", 1)):
        v = df.iloc[k + passo] if len(k) else df.iloc[[]]
        out["date_" + nome] = v["date"].to_numpy()
        out["close_" + nome] = v["close"].to_numpy()
        out["adjusted_" + nome] = v["adjusted_close"].to_numpy()
    return out


def regola_barre_isolate(giorni, valori, volumi=None, variante: str = "prezzo", gruppi: bool = False):
    """La regola pura delle barre isolate su una serie già letta (maschera booleana), per chi deve contare che cosa
    scarterebbe una variante: `variante` = "prezzo" (quella dell'opzione), "prezzo_e_volume", "prezzo_o_volume";
    `gruppi=True` = l'estensione a 2-3 barre consecutive, non adottata (docs/adr/011)."""
    from market_data.quality import barre_isolate as BI
    return BI.gruppi(giorni, valori) if gruppi else BI.isolate(giorni, valori, volumi, variante)


def salti_di_livello(symbols, verifica_salti: str | None = None, barre_isolate: str | None = None,
                     direzione: str = "rialzi", esenta_movimento_vero: bool = True):
    """I salti di livello non spiegati (docs/adr/012): una riga per salto, con `date` (il giorno del salto),
    `date_prima`, `close_prima`, `close`, `rapporto`, `direzione` (`rialzo`, `ribasso`), `volume`.

    **Regola adottata (i valori di default)**: chiusura grezza ≥ 5 volte la barra precedente (entro 10 giorni di
    calendario), senza uno split registrato in quella data con un fattore compatibile (tabella `split`, o nota
    `split_del_fornitore`), con le 5 barre successive entro il 50% dal nuovo livello, e **mai** un salto che la verifica
    con le azioni classifica «movimento vero» (`salti_classificati`, docs/adr/010: legge i file SEC).
    **Variante «alla lettera»**: `direzione="entrambe"` (anche ≤ 1/5) e `esenta_movimento_vero=False`.

    Valutati sulla serie pulita intera che `prices(clean=True, verifica_salti=…, barre_isolate=…)` restituisce: le
    barre isolate vanno tolte prima. **Non toglie niente dai prezzi e non scrive niente**: che cosa fare della serie
    lo decide chi usa l'elenco."""
    import numpy as np
    import pandas as pd
    from market_data.quality import salti_livello as SL
    if direzione not in SL.DIREZIONI:
        raise ValueError("direzione sconosciuta: {!r} (ammesso: {})".format(direzione, ", ".join(SL.DIREZIONI)))
    colonne = ["exchange", "code", "date", "date_prima", "close_prima", "close", "rapporto", "direzione", "volume"]
    df = prices(symbols, clean=True, verifica_salti=verifica_salti, barre_isolate=barre_isolate)
    if not len(df):
        return pd.DataFrame(columns=colonne)
    giorno = lambda col: col.to_numpy().astype("datetime64[D]").astype("int64")  # noqa: E731
    sp, per_split = splits(symbols), {}
    for e, c, d, f in zip(sp["exchange"], sp["code"], giorno(sp["date"]) if len(sp) else [], sp["factor"]):
        if f == f and f:
            per_split.setdefault((e, c), []).append((int(d), float(f)))
    fl, per_nota = flags(symbols), {}
    fl = fl[fl["controllo"] == "split_del_fornitore"]
    for e, c, d in zip(fl["exchange"], fl["code"], giorno(fl["from_date"]) if len(fl) else []):
        per_nota.setdefault((e, c), []).append(int(d))
    borsa, codice = df["exchange"].to_numpy(), df["code"].to_numpy()
    chiave = (df["exchange"].astype(str) + "\x00" + df["code"].astype(str)).to_numpy()
    g, cl, vol, date = giorno(df["date"]), df["close"].to_numpy(dtype=float), df["volume"].to_numpy(), df["date"].to_numpy()
    tagli = np.flatnonzero(chiave[1:] != chiave[:-1]) + 1
    esenti: dict = {}
    if esenta_movimento_vero:
        from market_data.quality import salti_azioni as SA
        for r in _righe_salti(_simboli(symbols)):
            if r["esito"] == SA.MOVIMENTO_VERO and r["data_salto"] is not None:
                esenti.setdefault((r["exchange"], r["code"]), []).append(int(np.datetime64(str(r["data_salto"])[:10], "D").astype("int64")))
    righe = []
    for a, b in zip(np.r_[0, tagli], np.r_[tagli, len(df)]):
        k = (borsa[a], codice[a])
        for i in SL.salti(g[a:b], cl[a:b], per_split.get(k, ()), per_nota.get(k, ()), direzione, esenti.get(k, ())):
            j = a + i
            righe.append((borsa[a], codice[a], date[j], date[j - 1], cl[j - 1], cl[j], cl[j] / cl[j - 1],
                          "rialzo" if cl[j] > cl[j - 1] else "ribasso", vol[j]))
    return pd.DataFrame(righe, columns=colonne)


def regola_salti_di_livello(giorni, chiusure, split=(), note=(), soglia: float = 5.0, persistenza: float = 0.5) -> list:
    """La regola pura dei salti di livello su una serie già letta: `[(posizione, rapporto, esito)]` per ogni barra con
    rapporto ≥ `soglia` o ≤ 1/`soglia`, dove esito è `preso` o il motivo del no. Per contare le varianti (docs/adr/012)."""
    from market_data.quality import salti_livello as SL
    return SL.esamina(giorni, chiusure, split, note, soglia, persistenza)


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


def fred(serie: str, *, inizio=None, fine=None, al_giorno=None):
    """Serie FRED (`date`, `value`; osservazioni mancanti tolte), scaricata al massimo una volta al giorno nel grezzo dell'archivio.

    Senza `al_giorno`: il CSV pubblico di FRED, senza chiave, cioè la serie come è oggi (revisioni comprese).
    Con `al_giorno`: la versione storica ALFRED, la serie come si leggeva quel giorno; serve `FRED_API_KEY` nel `.env`
    (l'ambiente vince): senza, `ConfigError` prima di qualunque richiesta; se ALFRED non ha una versione per quel giorno,
    `fred.ErroreFonte`. Mai un ripiego silenzioso sui dati di oggi (docs/adr/008)."""
    from market_data import fred as F
    return F.Lettore(C.archivio()).serie(serie, inizio=_data(inizio), fine=_data(fine), al_giorno=_data(al_giorno))


def ebp(*, inizio=None, fine=None):
    """Excess bond premium (Gilchrist-Zakrajšek) dal CSV della Fed: `date` (primo del mese), `gz_spread`, `ebp`, `est_prob`.
    La serie viene ristimata a ogni aggiornamento e non ha versioni storiche: ogni download resta nel grezzo con la sua data."""
    from market_data import fred as F
    return F.Lettore(C.archivio()).ebp(inizio=_data(inizio), fine=_data(fine))


def gsw(*, inizio=None, fine=None):
    """Curva dei Treasury di Gürkaynak-Sack-Wright (feds200628.csv della Fed), giornaliera dal 1961: parametri di Svensson
    (`BETA0`..`BETA3`, `TAU1`, `TAU2`), zero-coupon `SVENY01`..`SVENY30`, forward `SVENF01`.., par `SVENPY01`..; `NA` → NaN."""
    from market_data import fred as F
    return F.Lettore(C.archivio()).gsw(inizio=_data(inizio), fine=_data(fine))


def sec_azioni(cik, *, cache: bool = False):
    """Azioni in circolazione depositate alla SEC da una società (o da un elenco di società), dal file in blocco
    `companyfacts`: tutte le osservazioni di `dei:EntityCommonStockSharesOutstanding` (frontespizio),
    `us-gaap:CommonStockSharesOutstanding` (stato patrimoniale) e `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic`
    (media ponderata del periodo). Colonne come `sec_bilancio`. **Nessuna scelta dentro**: quale osservazione vale a una
    data, quale voce, e gli errori di scala dei depositi sono affare di chi legge (docs/adr/009)."""
    from market_data import sec as S
    return S.lettore(C.archivio()).bilancio(cik, S.VOCI_AZIONI, cache=cache)


def sec_bilancio(cik, voci, *, cache: bool = False):
    """Voci di bilancio XBRL di una società (o di un elenco), con la data di deposito: `cik`, `voce`
    (`tassonomia:Voce`), `unita`, `inizio` (vuoto per un valore istantaneo), `fine`, `valore`, `depositato` (`filed`),
    `modulo` (10-K, 10-Q, …), `esercizio` e `periodo` (`fy`, `fp` del deposito), `accn`, `frame`.

    `voci`: nomi con o senza tassonomia (`Revenues` = `us-gaap:Revenues`; `dei:EntityPublicFloat`). Una riga per fatto
    e per deposito che lo riporta: lo stesso periodo torna nei bilanci successivi. Un CIK senza file dà zero righe
    (`sec_cik()` dice chi c'è). Senza rete: se il file in blocco manca, `sec.FileMancante`. `cache=True` tiene nella
    cartella dei dati le società già lette per quelle voci."""
    from market_data import sec as S
    return S.lettore(C.archivio()).bilancio(cik, voci, cache=cache)


def sec_cik(file: str = "companyfacts") -> frozenset:
    """I CIK che hanno un file in `companyfacts` (o una testata in `submissions`)."""
    from market_data import sec as S
    return S.lettore(C.archivio()).cik_presenti(file)


def sec_societa(cik, *, cache: bool = False):
    """Testata `submissions` di una società (o di un elenco): `cik`, `nome`, `sic`, `sic_descrizione`, `tipo`,
    `categoria`, `stato`, `chiusura_esercizio`, `ticker`, `borse`, `altri_file`. **Sono i dati di oggi**, non di una data."""
    from market_data import sec as S
    return S.lettore(C.archivio()).societa(cik, cache=cache)


def sec_depositi(cik, moduli=None, *, tutti: bool = False, cache: bool = False):
    """Depositi di una società (o di un elenco) dal file `submissions`: `cik`, `accn`, `modulo`, `depositato`,
    `data_rapporto`, `voci_8k` (le voci di un 8-K, per esempio «1.03,9.01»). `moduli` filtra per modulo. Senza `tutti`
    solo i 1.000 depositi più recenti della testata; con `tutti=True` anche i file dei depositi più vecchi."""
    from market_data import sec as S
    return S.lettore(C.archivio()).depositi(cik, moduli, tutti=tutti, cache=cache)


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
