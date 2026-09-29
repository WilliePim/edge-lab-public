"""Viste DuckDB sull'archivio normalizzato. Le stesse definizioni servono al catalogo su disco (`<archivio>/catalog.duckdb`)
e a `market_data.api`, che le crea in memoria sul percorso della configurazione (l'archivio si può spostare).

Viste: `prezzi`, `dividendi`, `split`, `cambi`, `tesoro`, `identificativi`, `anagrafica`, `calendario`, `barre_tolte`,
`doppioni`, `segnalazioni` (controlli della fase 4; `esclude` distingue i periodi da togliere dalle note), `verifiche`
(periodi segnalati ma verificati con un'altra fonte), `prezzi_puliti` (prezzi senza i periodi da escludere e senza le
barre a chiusura zero o negativa), `liquidita` (quota di barre senza prezzo per titolo, con il segno oltre il 20%).

**Verifiche**: file scritto a mano `<archivio>/eodhd/verifiche.jsonl`, una riga JSON per periodo con code, exchange,
controllo, from_date, to_date, source, note. Si legge in Python in modo tollerante (BOM, UTF-16, righe vuote); le righe non
valide si saltano e si restituiscono come problemi. Un file sbagliato non blocca mai la lettura dei prezzi.

Una tabella che non esiste ancora diventa una vista vuota con le sue colonne. Nel catalogo su disco questo vale solo fino
alla ricostruzione successiva: `quality.esegui` e `store.ricostruisci` lo riscrivono alla fine.

    .venv/Scripts/python.exe -m market_data.store.catalog
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pyarrow as pa

from market_data import config as C
from market_data.store import normalize as N

#  `esclude`: la segnalazione toglie il periodo dai prezzi puliti (vero) oppure lo annota soltanto (falso).
#  Le note esistono perche' un salto spiegato -- split applicato dal fornitore, movimento confermato dal bilancio
#  della societa' -- va detto, non nascosto, ma non deve togliere dati.
SCHEMA_SEGNALAZIONI = pa.schema([("code", pa.string()), ("controllo", pa.string()), ("from_date", pa.date32()),
                                 ("to_date", pa.date32()), ("detail", pa.string()), ("esclude", pa.bool_())])
SCHEMA_VERIFICHE = pa.schema([("code", pa.string()), ("exchange", pa.string()), ("controllo", pa.string()),
                              ("from_date", pa.date32()), ("to_date", pa.date32()), ("source", pa.string()), ("note", pa.string())])
SCHEMA_CALENDARIO = pa.schema([("date", pa.date32())])
N.SCHEMI.setdefault("segnalazioni", SCHEMA_SEGNALAZIONI)
N.SCHEMI.setdefault("calendario", SCHEMA_CALENDARIO)

TABELLE_PARTIZIONATE = ("prezzi", "dividendi", "split", "cambi", "tesoro", "identificativi", "anagrafica", "calendario",
                        "barre_tolte", "doppioni", "segnalazioni")
TIPI_DUCKDB = {pa.string(): "VARCHAR", pa.date32(): "DATE", pa.float64(): "DOUBLE", pa.int64(): "BIGINT", pa.bool_(): "BOOLEAN"}
CAMPI_VERIFICHE = ("code", "exchange", "controllo", "from_date", "to_date")


def _schema(tabella: str) -> pa.Schema:
    if tabella == "anagrafica":
        from market_data.store import identity  # noqa: F401  (registra lo schema)
    return N.SCHEMI[tabella]


def sql_vista(archivio: Path, tabella: str, nome: str | None = None) -> str:
    """La vista sui parquet di `tabella`. `nome` la fa chiamare diversamente: serve a `segnalazioni`, che si legge
    grezza e poi si ripresenta normalizzata sotto il suo nome."""
    cartella = archivio / "eodhd" / "parquet" / tabella
    file = sorted(cartella.glob("exchange=*/*.parquet")) if cartella.exists() else []
    if file:
        percorso = (cartella / "exchange=*" / "*.parquet").as_posix()
        return "CREATE OR REPLACE VIEW {} AS SELECT * FROM read_parquet('{}', hive_partitioning = true, union_by_name = true)".format(
            nome or tabella, percorso.replace("'", "''"))
    colonne = ", ".join("CAST(NULL AS {}) AS {}".format(TIPI_DUCKDB[f.type], f.name) for f in _schema(tabella))
    return "CREATE OR REPLACE VIEW {} AS SELECT {}, CAST(NULL AS VARCHAR) AS exchange WHERE false".format(
        nome or tabella, colonne)


def leggi_verifiche(archivio: Path) -> tuple[pa.Table, list[str]]:
    """(tabella delle verifiche valide, problemi). Tollerante: BOM, UTF-16, righe vuote; una riga non valida si salta."""
    f = archivio / "eodhd" / "verifiche.jsonl"
    righe, problemi = [], []
    if f.exists():
        dati = f.read_bytes()
        testo = dati.decode("utf-16", "replace") if dati[:2] in (b"\xff\xfe", b"\xfe\xff") else dati.decode("utf-8-sig", "replace")
        for n, riga in enumerate(testo.splitlines(), 1):
            if not riga.strip():
                continue
            try:
                r = json.loads(riga)
                mancanti = [k for k in CAMPI_VERIFICHE if not r.get(k)]
                if mancanti:
                    raise ValueError("campi mancanti: " + ", ".join(mancanti))
                righe.append({"code": str(r["code"]), "exchange": str(r["exchange"]), "controllo": str(r["controllo"]),
                              "from_date": dt.date.fromisoformat(str(r["from_date"])[:10]),
                              "to_date": dt.date.fromisoformat(str(r["to_date"])[:10]),
                              "source": None if r.get("source") is None else str(r["source"]),
                              "note": None if r.get("note") is None else str(r["note"])})
            except (ValueError, TypeError, AttributeError) as e:
                problemi.append("riga {}: {}".format(n, e))
    return pa.Table.from_pylist(righe, schema=SCHEMA_VERIFICHE), problemi


#  Due regole, non una. La prima toglie i periodi segnalati che escludono (`esclude`): le segnalazioni che sono
#  note -- lo split che il fornitore ha applicato, il salto confermato dal bilancio della societa' -- restano
#  visibili in `segnalazioni` ma non tolgono niente. La seconda toglie le barre senza prezzo: una chiusura a zero
#  o negativa non e' un prezzo, e in un backtest varrebbe un rendimento del -100%. Sparisce come barra, non
#  diventa uno zero (decisione dell'utente, ADR 006 punto 66).
#  Le due condizioni stanno qui, in un posto solo, perche' `market_data.api.prices` non usa questa vista: per
#  filtrare prima sui simboli si scrive la sua query, e finche' le condizioni erano copiate le due strade hanno
#  divergito senza che nessuno se ne accorgesse. Un test le confronta su ogni titolo dell'archivio di prova.
PREZZO_VALIDO = "{p}.close > 0 AND ({p}.adjusted_close IS NULL OR {p}.adjusted_close > 0)"

SQL_PREZZI_PULITI = """
CREATE OR REPLACE VIEW prezzi_puliti AS
SELECT p.* FROM prezzi p
WHERE {prezzo_valido}
  AND NOT EXISTS (
    SELECT 1 FROM segnalazioni s
    WHERE s.exchange = p.exchange AND s.code = p.code AND s.esclude AND p.date BETWEEN s.from_date AND s.to_date
      AND NOT EXISTS (SELECT 1 FROM verifiche v
                      WHERE v.exchange = s.exchange AND v.code = s.code AND v.controllo = s.controllo
                        AND v.from_date <= s.from_date AND v.to_date >= s.to_date))
""".format(prezzo_valido=PREZZO_VALIDO.format(p="p"))

#  Quota di barre senza prezzo per titolo. Sopra `QUOTA_LIQUIDITA_INSUFFICIENTE` il titolo non ha abbastanza
#  sedute con un prezzo per starci dentro un backtest: la vista lo dice, non lo toglie (decisione dell'utente).
QUOTA_LIQUIDITA_INSUFFICIENTE = 0.20
SQL_LIQUIDITA = """
CREATE OR REPLACE VIEW liquidita AS
SELECT exchange, code, count(*) AS barre,
       count(*) FILTER (WHERE NOT (close > 0)) AS barre_senza_prezzo,
       round(count(*) FILTER (WHERE NOT (close > 0)) / count(*), 4) AS quota_senza_prezzo,
       count(*) FILTER (WHERE NOT (close > 0)) / count(*) > {soglia} AS liquidita_insufficiente
FROM prezzi GROUP BY exchange, code
""".format(soglia=QUOTA_LIQUIDITA_INSUFFICIENTE)


def normalizza_segnalazioni(con) -> None:
    """Fa esistere `esclude` anche sulle partizioni scritte prima che la colonna ci fosse.

    Dove manca, o dove e' nulla, vale TRUE: e' il comportamento di prima della fermata 3, quando ogni periodo
    segnalato usciva dai prezzi puliti. Un dato mancante non deve mai diventare un permesso."""
    colonne = {r[0] for r in con.execute("DESCRIBE segnalazioni_grezze").fetchall()}
    if "esclude" in colonne:
        con.execute("CREATE OR REPLACE VIEW segnalazioni AS "
                    "SELECT * REPLACE (COALESCE(esclude, TRUE) AS esclude) FROM segnalazioni_grezze")
    else:
        con.execute("CREATE OR REPLACE VIEW segnalazioni AS SELECT *, TRUE AS esclude FROM segnalazioni_grezze")


def crea_viste(con, archivio: Path, materializza_verifiche: bool = False) -> list[str]:
    """Crea le viste; restituisce i problemi trovati nel file delle verifiche."""
    for t in TABELLE_PARTIZIONATE:
        con.execute(sql_vista(archivio, t, nome="segnalazioni_grezze" if t == "segnalazioni" else None))
    normalizza_segnalazioni(con)
    verifiche, problemi = leggi_verifiche(archivio)
    if materializza_verifiche:                                   # catalogo su disco: tabella vera
        con.register("verifiche_arrow", verifiche)
        con.execute("CREATE OR REPLACE TABLE verifiche AS SELECT * FROM verifiche_arrow")
        con.unregister("verifiche_arrow")
    else:
        con.register("verifiche", verifiche)
    con.execute(SQL_PREZZI_PULITI)
    con.execute(SQL_LIQUIDITA)
    return problemi


def costruisci_catalogo(archivio: Path, log=print) -> Path:
    """Scrive il catalogo in un file nuovo e poi lo sostituisce; se il vecchio è aperto da un altro processo lo lascia e lo
    dice (le viste in memoria di `market_data.api` non ne dipendono)."""
    import duckdb
    percorso = archivio / "catalog.duckdb"
    tmp = archivio / "catalog.duckdb.nuovo"
    for f in (tmp, Path(str(tmp) + ".wal")):
        if f.exists():
            f.unlink()
    con = C.applica_limiti(duckdb.connect(str(tmp)))
    try:
        problemi = crea_viste(con, archivio, materializza_verifiche=True)
    finally:
        con.close()
    if problemi:
        log("verifiche.jsonl: {} righe saltate: {}".format(len(problemi), "; ".join(problemi[:5])))
    try:
        os.replace(tmp, percorso)
    except PermissionError:
        log("catalog.duckdb è aperto da un altro processo: resta la versione precedente, la nuova è in {}".format(tmp.name))
        return tmp
    return percorso


def main() -> int:
    print(costruisci_catalogo(C.archivio()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
