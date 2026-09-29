"""Controlli di qualità sui prezzi in SQL (DuckDB), per borsa. Le funzioni Python di `checks.py` sono il riferimento: i test
confrontano i due risultati sulle stesse serie finte.

Ogni funzione riceve una connessione con le viste di `store/catalog.py` e una borsa, e restituisce righe (tuple) o un
riepilogo (dict).
"""
from __future__ import annotations

import math

from market_data.quality import checks as Q

SOGLIA_BUCHI = 0.05
SALTO_IMPOSSIBILE = 0.90


BARRE_PER_BLOCCO = 15_000_000


def filtro_blocco(blocco: tuple[int, int] | None) -> str:
    """La condizione che tiene solo i codici del blocco `(k, n)`, o niente se non si lavora a blocchi.

    Si divide per codice perche' i due controlli a finestra mobile partizionano per codice: ogni serie sta tutta
    dentro un blocco, quindi i risultati a blocchi sono gli stessi di un giro unico. Dividere per data, invece,
    spezzerebbe le finestre e cambierebbe le risposte."""
    if blocco is None:
        return ""
    k, n = blocco
    return " AND hash(code) % {n:d} = {k:d}".format(n=n, k=k)


def blocchi_per(con, borsa: str) -> list[tuple[int, int] | None]:
    """In quanti blocchi conviene dividere questa borsa: uno ogni `BARRE_PER_BLOCCO` barre.

    Senza blocchi il picco di memoria e' quello di tutta la borsa in una volta: negli USA sono 113 milioni di
    barre e il computer resta senza RAM mentre lavora. A blocchi il picco e' una frazione, e il tempo totale
    cambia poco perche' il lavoro e' lo stesso."""
    barre = con.execute("SELECT count(*) FROM prezzi WHERE exchange = ?", [borsa]).fetchone()[0]
    n = max(1, -(-barre // BARRE_PER_BLOCCO))
    return [None] if n == 1 else [(k, n) for k in range(n)]


def _serie(borsa: str, blocco: tuple[int, int] | None = None) -> str:
    """Barre ordinate con la chiusura precedente e il numero di barra per codice."""
    return """
    SELECT code, date, open, close, adjusted_close, volume,
           lag(close) OVER w AS close_prima, lag(adjusted_close) OVER w AS adj_prima,
           row_number() OVER w AS n
    FROM prezzi WHERE exchange = '{b}'{blocco}
    WINDOW w AS (PARTITION BY code ORDER BY date)
    """.format(b=borsa.replace("'", "''"), blocco=filtro_blocco(blocco))


def buchi(con, borsa: str, soglia: float = SOGLIA_BUCHI) -> dict:
    """Sedute del calendario fra la prima e l'ultima barra di ogni codice senza una barra. Titoli oltre la soglia."""
    righe = con.execute("""
        WITH cal AS (SELECT date, row_number() OVER (ORDER BY date) AS i FROM calendario WHERE exchange = ?),
        inizio AS (SELECT min(date) AS d FROM cal),
        barre AS (SELECT p.code, p.date, (c.date IS NOT NULL) AS in_seduta,
                         p.date < (SELECT d FROM inizio) AS prima_del_calendario
                  FROM prezzi p LEFT JOIN cal c ON c.date = p.date WHERE p.exchange = ?),
        per_codice AS (
            SELECT code, min(date) AS prima_vera, greatest(min(date), (SELECT d FROM inizio)) AS prima, max(date) AS ultima,
                   count(*) FILTER (WHERE in_seduta) AS barre_in_seduta,
                   count(*) FILTER (WHERE NOT in_seduta AND NOT prima_del_calendario) AS barre_fuori_seduta,
                   count(*) FILTER (WHERE prima_del_calendario) AS barre_prima_del_calendario
            FROM barre GROUP BY code),
        con_primo AS (SELECT p.*, c1.i AS i_prima FROM per_codice p ASOF LEFT JOIN cal c1 ON p.prima <= c1.date),
        con_ultimo AS (SELECT p.*, c2.i AS i_ultima FROM con_primo p ASOF LEFT JOIN cal c2 ON p.ultima >= c2.date),
        sedute AS (SELECT *, CASE WHEN i_prima IS NULL OR i_ultima IS NULL OR i_ultima < i_prima THEN 0
                                  ELSE i_ultima - i_prima + 1 END AS sedute FROM con_ultimo)
        SELECT code, prima_vera, ultima, sedute, barre_in_seduta, barre_fuori_seduta,
               CASE WHEN sedute > 0 THEN (sedute - barre_in_seduta)::DOUBLE / sedute END AS quota_mancante,
               barre_prima_del_calendario
        FROM sedute ORDER BY quota_mancante DESC NULLS LAST, code
    """, [borsa, borsa]).fetchall()
    sopra = [r for r in righe if r[6] is not None and r[6] > soglia]
    return {"titoli": len(righe), "senza_calendario": sum(1 for r in righe if not r[3]),
            "sopra_soglia": len(sopra), "barre_fuori_seduta": sum(r[5] for r in righe),
            "barre_prima_del_calendario": sum(r[7] for r in righe),
            "titoli_sopra_soglia": [{"code": r[0], "prima": str(r[1]), "ultima": str(r[2]), "sedute": r[3],
                                     "mancanti": r[3] - r[4], "quota": round(r[6], 4)} for r in sopra]}


def duplicati(con, borsa: str) -> dict:
    righe = con.execute("SELECT code, duplicates, first_date FROM doppioni WHERE exchange = ? ORDER BY duplicates DESC, code",
                        [borsa]).fetchall()
    return {"titoli": len(righe), "righe": sum(r[1] for r in righe),
            "esempi": [{"code": r[0], "doppioni": r[1], "prima_data": str(r[2])} for r in righe[:20]]}


def prezzi_impossibili(con, borsa: str) -> dict:
    """Chiusure (grezze e rettificate) a zero o negative; salti giornalieri oltre il 90% (in su o in giù) senza split
    registrato quel giorno."""
    non_positive = con.execute("SELECT count(*), count(DISTINCT code) FROM prezzi WHERE exchange = ? AND close <= 0",
                               [borsa]).fetchone()
    rettificate = con.execute("SELECT count(*), count(DISTINCT code) FROM prezzi WHERE exchange = ? AND adjusted_close <= 0",
                              [borsa]).fetchone()
    salti = con.execute("""
        WITH s AS ({serie})
        SELECT s.code, s.date, s.close_prima, s.close FROM s
        WHERE s.close_prima > 0 AND s.close > 0 AND abs(s.close / s.close_prima - 1) > {soglia}
          AND NOT EXISTS (SELECT 1 FROM split x WHERE x.exchange = ? AND x.code = s.code AND x.date = s.date)
        ORDER BY s.code, s.date
    """.format(serie=_serie(borsa), soglia=SALTO_IMPOSSIBILE), [borsa]).fetchall()
    return {"chiusure_non_positive": non_positive[0], "titoli_con_chiusure_non_positive": non_positive[1],
            "rettificate_non_positive": rettificate[0], "titoli_con_rettificate_non_positive": rettificate[1],
            "salti_oltre_90": len(salti), "titoli_con_salti_oltre_90": len({r[0] for r in salti}),
            "esempi_salti": [{"code": r[0], "data": str(r[1]), "rapporto": round(r[3] / r[2], 4)} for r in salti[:20]]}


FATTORE_MINIMO_COERENZA = 1.5


def coerenza_split(con, borsa: str) -> dict:
    """Per ogni split registrato (fattore f): alla prima barra dal giorno dello split la chiusura grezza si divide per circa f
    e la chiusura rettificata resta continua. Coerente se |ln(grezza · f)| < |ln f| / 2 e |ln(rettificata)| < |ln f| / 2.
    Solo per f ≥ 1,5 o f ≤ 1/1,5: con fattori vicini a 1 (aumenti di capitale, dividendi in azioni, 1,03) metà del salto è
    più piccola di un movimento giornaliero normale e il controllo non distingue nulla; quei casi si contano a parte."""
    righe = con.execute("""
        WITH s AS ({serie}),
        sp AS (SELECT code, date, factor FROM split WHERE exchange = ? AND factor > 0 AND factor <> 1)
        SELECT sp.code, sp.date, sp.factor, b.close / b.close_prima AS grezza, b.adjusted_close / b.adj_prima AS rettificata
        FROM sp ASOF JOIN s b ON b.code = sp.code AND b.date >= sp.date
        WHERE b.close_prima > 0 AND b.adj_prima > 0 AND b.close > 0 AND b.adjusted_close > 0
    """.format(serie=_serie(borsa)), [borsa]).fetchall()
    senza_barra = con.execute("SELECT count(*) FROM split WHERE exchange = ? AND factor > 0 AND factor <> 1", [borsa]).fetchone()[0] - len(righe)
    incoerenti, piccoli = [], 0
    for code, data, f, grezza, rett in righe:
        if abs(math.log(f)) < math.log(FATTORE_MINIMO_COERENZA):
            piccoli += 1
            continue
        mezzo = abs(math.log(f)) / 2
        if not (abs(math.log(grezza * f)) < mezzo and abs(math.log(rett)) < mezzo):
            incoerenti.append({"code": code, "data": str(data), "fattore": f, "grezza": round(grezza, 4), "rettificata": round(rett, 4)})
    return {"split": len(righe), "senza_barre_intorno": senza_barra, "fattore_vicino_a_1_non_valutabili": piccoli,
            "valutati": len(righe) - piccoli, "incoerenti": len(incoerenti), "esempi": incoerenti[:20]}


def salti_split_mancanti(con, borsa: str, tolleranza: float = Q.TOLLERANZA,
                         blocco: tuple[int, int] | None = None) -> list[dict]:
    """Stessa regola di `checks.esamina_salti` (segnalati): rapporto tipico ±tolleranza, nessun ritorno oltre il punto medio
    nelle 20 sedute dopo (tutte con chiusura positiva), nessuno split registrato quel giorno. Con fascia di prezzo e volume."""
    candidati = " OR ".join("abs((close / close_prima) / {k!r} - 1) <= {t!r}".format(k=k, t=tolleranza + Q.EPS) for k in Q.CANDIDATI)
    righe = con.execute("""
        WITH s AS (
            SELECT code, date, close, close_prima, volume, adj_prima, adjusted_close,
                   count(close) FILTER (WHERE close > 0) OVER dopo AS n_dopo,
                   count(*) OVER dopo AS righe_dopo,
                   min(close) OVER dopo AS min_dopo, max(close) OVER dopo AS max_dopo,
                   median(volume) FILTER (WHERE volume > 0) OVER prima20 AS v_prima,
                   median(volume) FILTER (WHERE volume > 0) OVER da_t AS v_dopo
            FROM ({serie})
            WINDOW dopo AS (PARTITION BY code ORDER BY date ROWS BETWEEN 1 FOLLOWING AND {n} FOLLOWING),
                   prima20 AS (PARTITION BY code ORDER BY date ROWS BETWEEN {nv} PRECEDING AND 1 PRECEDING),
                   da_t AS (PARTITION BY code ORDER BY date ROWS BETWEEN CURRENT ROW AND {nv1} FOLLOWING)
        )
        SELECT code, date, close_prima, close, n_dopo, righe_dopo, min_dopo, max_dopo, v_prima, v_dopo,
               adj_prima, adjusted_close, volume FROM s
        WHERE close_prima > 0 AND close > 0 AND ({candidati})
          AND NOT EXISTS (SELECT 1 FROM split x WHERE x.exchange = ? AND x.code = s.code AND x.date = s.date)
        ORDER BY code, date
    """.format(serie=_serie(borsa, blocco), n=Q.SEDUTE_DOPO, nv=Q.SEDUTE_VOLUME, nv1=Q.SEDUTE_VOLUME - 1,
               candidati=candidati),
        [borsa]).fetchall()
    out = []
    for code, data, c0, c1, n_dopo, righe_dopo, mn, mx, vp, vd, a0, a1, volume in righe:
        r = c1 / c0
        k = Q.rapporto_tipico(r, tolleranza)
        if k is None or righe_dopo < Q.SEDUTE_DOPO or n_dopo < Q.SEDUTE_DOPO:
            continue                                            # non valutabile: non segnalato
        soglia = abs(math.log(k)) / 2
        torna = math.log(mx / c1) >= soglia if r < 1 else math.log(mn / c1) <= -soglia
        if torna:
            continue
        coerente = None if vp is None or vd is None else ((r < 1 and vd > vp) or (r > 1 and vd < vp))
        r_rett = (a1 / a0) if (a0 and a1 and a0 > 0 and a1 > 0) else None
        voce = {"code": code, "data": data, "chiusura_prima": c0, "chiusura": c1, "rapporto": r, "rapporto_tipico": k,
                "volume_coerente": coerente, "rapporto_rettificata": r_rett, "volume": volume,
                "rettificata_continua": Q.rettificata_continua(r, r_rett)}
        voce["fascia"] = Q.fascia_prezzo(voce)
        out.append(voce)
    return out


def sequenze_volume_zero(con, borsa: str, minimo: int = Q.SEDUTE_PIATTE,
                         blocco: tuple[int, int] | None = None) -> list[tuple]:
    """Stessa regola di `checks.sequenze_volume_zero`: sedute consecutive con volume zero e chiusura identica, almeno `minimo`."""
    return con.execute("""
        WITH s AS (
            SELECT code, date, close, volume,
                   row_number() OVER (PARTITION BY code ORDER BY date) AS n,
                   CASE WHEN volume = 0 AND close IS NOT NULL THEN 1 ELSE 0 END AS piatta
            FROM prezzi WHERE exchange = ?{blocco}),
        g AS (
            SELECT *, n - row_number() OVER (PARTITION BY code, piatta, close ORDER BY date) AS isola FROM s WHERE piatta = 1)
        SELECT code, min(date) AS da, max(date) AS a, count(*) AS sedute
        FROM g GROUP BY code, close, isola HAVING count(*) >= ? ORDER BY code, da
    """.format(blocco=filtro_blocco(blocco)), [borsa, minimo]).fetchall()
