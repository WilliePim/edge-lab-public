"""Anagrafica: un record per titolo e periodo di vita. Distingue due società che hanno usato lo stesso ticker.

Un **codice EODHD** in una borsa è un periodo di vita di un titolo: `P` (Everpure) e `P_old` (Pandora) sono due record
con lo stesso **ticker di base** `P`, ISIN diversi e periodi separati (dopo aver tolto da `P` le barre copiate da `P_old`,
`store/normalize.py`). L'identità si legge da **codice + borsa**, con l'**ISIN** come conferma; mai dal ticker o dal nome
(il nome può essere il ticker: Papa Murphy's è registrata come «FRSH»). Regola dei gemelli: `normalize.ticker_di_base`.

Record: i codici delle liste più recenti (azioni ordinarie ed ETF) **più i codici che hanno prezzi ma non sono più nelle
liste** (codice cambiato dal fornitore, tipo cambiato): per questi `status` è «non nelle liste», i dati vengono dall'ultima
versione delle liste che li conteneva e `superseded_by` indica i codici delle liste attuali con lo stesso ISIN.

Colonne (partizione `exchange`): code, symbol, ticker, name, venue, country, isin, type, currency, status, listed_in,
downloaded, excluded_reason, first_date, last_date, bars, removed_bars, cik, cusip, figi, twins, same_isin, superseded_by.

    .venv/Scripts/python.exe -m market_data.store.identity
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow as pa

from market_data import config as C
from market_data.eodhd import download as D
from market_data.store import normalize as N

SCHEMA = pa.schema([
    ("code", pa.string()), ("symbol", pa.string()), ("ticker", pa.string()), ("name", pa.string()), ("venue", pa.string()),
    ("country", pa.string()), ("isin", pa.string()), ("type", pa.string()), ("currency", pa.string()),
    ("status", pa.string()), ("listed_in", pa.string()), ("downloaded", pa.bool_()), ("excluded_reason", pa.string()),
    ("first_date", pa.date32()), ("last_date", pa.date32()), ("bars", pa.int64()), ("removed_bars", pa.int64()),
    ("cik", pa.string()), ("cusip", pa.string()), ("figi", pa.string()), ("twins", pa.string()), ("same_isin", pa.string()),
    ("superseded_by", pa.string()),
])
N.SCHEMI["anagrafica"] = SCHEMA


def ticker_di_base(codice: str, codici_borsa: set[str], borsa: str = "US", delistati: set[str] | None = None) -> str:
    return N.ticker_di_base(codice, codici_borsa, borsa, delistati)


def record_borsa(borsa: str, attivi: list[dict], delistati: list[dict], statistiche: dict[str, tuple],
                 tolte: dict[str, int], identificativi: dict[str, dict], xetra: tuple[set[str], set[str]],
                 storico: dict[str, dict] | None = None) -> list[dict]:
    """Record dell'anagrafica per una borsa. `statistiche`: codice -> (prima data, ultima data, barre); `storico`: ultimo
    record noto per codice da tutte le versioni delle liste (per i codici con prezzi non più nelle liste)."""
    titoli = D.titoli_da_liste(borsa, attivi, delistati)
    liste = defaultdict(set)
    for righe, dove in ((attivi, "attivi"), (delistati, "delistati")):
        for r in righe:
            if r.get("Code"):
                liste[r["Code"]].add(dove)
    info = {r["Code"]: r for righe in (delistati, attivi) for r in righe if r.get("Code")}
    nelle_liste = {t.codice for t in titoli}
    for codice in sorted(set(statistiche) - nelle_liste):
        r = (storico or {}).get(codice, {})
        titoli.append(D.Titolo(borsa, codice, r.get("Type") or "", "non nelle liste", r.get("Isin") or "", r.get("Name") or "",
                               r.get("Currency") or ""))
        info.setdefault(codice, r)
    codici = {t.codice for t in titoli}
    codici_delistati = {t.codice for t in titoli if t.stato != "attivo"}
    per_base, per_isin = defaultdict(list), defaultdict(list)
    for t in titoli:
        per_base[ticker_di_base(t.codice, codici, borsa, codici_delistati)].append(t.codice)
        if t.isin:
            per_isin[t.isin.upper()].append(t.codice)
    out = []
    for t in titoli:
        base = ticker_di_base(t.codice, codici, borsa, codici_delistati)
        prima, ultima, barre = statistiche.get(t.codice, (None, None, 0))
        scaricato = barre > 0
        escluso = D.motivo_esclusione_francoforte(t.isin, t.stato if t.stato != "non nelle liste" else "delistato", *xetra) \
            if borsa == "F" and not scaricato else None
        ids = identificativi.get(t.codice, {})
        stesso_isin = [c for c in per_isin.get((t.isin or "").upper(), []) if c != t.codice]
        out.append({
            "code": t.codice, "symbol": "{}.{}".format(t.codice, borsa), "ticker": base, "name": t.nome or None,
            "venue": info.get(t.codice, {}).get("Exchange"), "country": info.get(t.codice, {}).get("Country"),
            "isin": t.isin or None, "type": t.tipo or None, "currency": (t.valuta or None) if t.valuta != "NA" else None,
            "status": t.stato, "listed_in": ",".join(sorted(liste.get(t.codice, ()))) or None, "downloaded": scaricato,
            "excluded_reason": escluso, "first_date": prima, "last_date": ultima, "bars": barre,
            "removed_bars": tolte.get(t.codice, 0), "cik": ids.get("cik"), "cusip": ids.get("cusip"), "figi": ids.get("figi"),
            "twins": ",".join(sorted(c for c in per_base[base] if c != t.codice)) or None,
            "same_isin": ",".join(sorted(stesso_isin)) or None,
            "superseded_by": (",".join(sorted(c for c in stesso_isin if c in nelle_liste)) or None)
            if t.stato == "non nelle liste" else None,
        })
    return out


class Anagrafica:
    def __init__(self, archivio: Path, log=print):
        self.archivio, self.log = archivio, log
        self.norm = N.Normalizzatore(archivio, log=log)
        self.grezzo = self.norm.grezzo
        self.parquet = archivio / "eodhd" / "parquet"
        self.man = archivio / "eodhd" / "manifest"

    def lista(self, borsa: str, delistati: bool) -> tuple[list[dict], dict | None]:
        voce = self.grezzo.gia_scaricato("exchange-symbol-list/" + borsa,
                                         {"delisted": "1", "fmt": "json"} if delistati else {"fmt": "json"})
        return (json.loads(self.grezzo.leggi(voce)), voce) if voce else ([], None)

    def _sql(self, tabella: str, borsa: str, sql: str) -> list[tuple]:
        cartella = self.parquet / tabella / "exchange={}".format(borsa)
        if not cartella.exists():
            return []
        import duckdb
        return C.applica_limiti(duckdb.connect()).execute(sql, [str(cartella / "*.parquet")]).fetchall()

    def statistiche(self, borsa: str) -> dict[str, tuple]:
        return {r[0]: (r[1], r[2], r[3]) for r in
                self._sql("prezzi", borsa, "SELECT code, min(date), max(date), count(*) FROM read_parquet(?) GROUP BY code")}

    def tolte(self, borsa: str) -> dict[str, int]:
        return dict(self._sql("barre_tolte", borsa, "SELECT code, sum(removed) FROM read_parquet(?) GROUP BY code"))

    def identificativi(self, borsa: str) -> dict[str, dict]:
        return {r[0]: {"cik": r[1], "cusip": r[2], "figi": r[3]} for r in
                self._sql("identificativi", borsa, "SELECT code, cik, cusip, figi FROM read_parquet(?)")}

    def costruisci(self, borse: list[str] | None = None) -> dict:
        borse = borse or [b for blocco in D.BLOCCHI.values() for b in blocco["borse"]]
        xetra = D.isin_xetra(self.lista("XETRA", False)[0], self.lista("XETRA", True)[0])
        esito = {}
        for borsa in borse:
            attivi, va = self.lista(borsa, False)
            delistati, vd = self.lista(borsa, True)
            statistiche = self.statistiche(borsa)
            if va is None and vd is None and not statistiche:
                continue
            storico = self.norm.liste().get(borsa, {}).get("info", {})
            record = record_borsa(borsa, attivi, delistati, statistiche, self.tolte(borsa), self.identificativi(borsa),
                                  xetra, storico)
            part = N.Partizione(self.parquet, self.man, "anagrafica", borsa)
            if record:
                part.aggiungi(pa.Table.from_pylist(record, schema=SCHEMA))
            sorgenti = [{"file": v["file"], "sha256": v["sha256"]} for v in (va, vd) if v]
            esito[borsa] = part.chiudi(sorgenti)
            self.log("anagrafica {}: {} record, {} con prezzi, {} non nelle liste".format(
                borsa, len(record), sum(r["downloaded"] for r in record), sum(r["status"] == "non nelle liste" for r in record)))
        return esito


def main(argv=None) -> int:
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    borse = [b for b in (argv or sys.argv[1:])] or None
    print(json.dumps(Anagrafica(C.archivio()).costruisci(borse), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
