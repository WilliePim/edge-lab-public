"""Livello normalizzato: tabelle Parquet partizionate per borsa, costruite dal livello grezzo. Si ricostruiscono sempre da capo
(il grezzo non cambia mai), una partizione alla volta, scrivendo a flusso in una cartella temporanea che poi sostituisce
la vecchia.

    <archivio>/eodhd/parquet/<tabella>/exchange=<BORSA>/part-00000.parquet
    <archivio>/eodhd/manifest/normalizzato.jsonl                      una riga per file Parquet
    <archivio>/eodhd/manifest/sorgenti/<tabella>__<BORSA>.json         i file grezzi usati, con sha256

Tabelle (colonne e significato in `DATA_DICTIONARY.md`):
- `prezzi`: code, date, open, high, low, close, adjusted_close, volume, currency — titoli delle borse e indici (`INDX`);
- `dividendi`: code, date, declaration_date, record_date, payment_date, period, value, unadjusted_value, currency,
  currency_from_listing;
- `split`: code, date, ratio, new_shares, old_shares, factor;
- `cambi`: pair, date, open, high, low, close, adjusted_close, volume (borsa `FOREX`);
- `tesoro`: curve, date, tenor, rate, discount, coupon, avg_discount, avg_coupon, maturity_date, cusip, rate_type,
  extrapolation_factor (borsa `US`);
- `identificativi`: symbol, code, isin, figi, lei, cusip, cik (borsa del simbolo);
- `doppioni`: code, duplicates, first_date — date ripetute nella serie grezza (vale la prima riga);
- `barre_tolte`: code, twin, removed, first_date, last_date — barre copiate da un gemello (sotto).

**Serie per titolo**: per ogni codice vale la versione più recente scaricata; il CSV vale prima del JSON (campioni delle
fasi 0-1, stessi valori). **Una versione nuova vuota o con meno della metà delle righe della più lunga già scaricata non
sostituisce le altre**: si usa la più recente fra quelle con almeno metà delle righe e la sostituzione mancata si registra.

**Gemelli** (storia della società che usava prima lo stesso ticker): `X_old`, `X_oldN` in ogni borsa; `X` più una cifra
solo negli USA e solo se quel codice è delistato. Da un codice si tolgono le barre con **stessa data e stessa chiusura** di
un gemello e **volume uguale entro lo 0,5%** (il fornitore arrotonda i volumi copiati), solo se formano **blocchi di almeno
20 sedute consecutive**: le coincidenze isolate restano.

**Dati in blocco per data** (aggiornamenti): letti da DuckDB a flusso, **solo per allungare serie già scaricate per titolo**
(nessuna serie nasce dal blocco: i titoli nuovi si scaricano per intero, con i filtri del download) e **solo dopo l'ultima
barra** della serie (o dopo il giorno del download, se la serie era vuota). Dividendi e split del blocco si aggiungono solo
per date che la serie per titolo non ha. File in blocco più vecchi di 10 giorni prima del download per titolo non si leggono.

**Valuta**: dalle liste dei titoli della borsa (tutte le versioni scaricate: vale l'ultima nota per il codice). Per i
dividendi vale la valuta del dividendo; se manca si usa quella della lista e `currency_from_listing` è vero (attenzione:
a Londra la lista dice GBX, i dividendi spesso GBP).

    .venv/Scripts/python.exe -m market_data.store.normalize [--tabelle prezzi,dividendi] [--borse US,LSE]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from market_data import config as C
from market_data.store.raw import Grezzo

RIGHE_PER_FILE = 2_000_000
RIGHE_PER_GRUPPO = 500_000
COMPRESSIONE = "zstd"
TWIN_OLD = re.compile(r"^(?P<base>.+?)_old\d*$")
TWIN_CIFRA = re.compile(r"^(?P<base>.+?)\d$")
TIPI_INCLUSI = ("Common Stock", "ETF")
MINIMO_BLOCCO_COPIATO = 20
TOLLERANZA_VOLUME = 0.005
QUOTA_MINIMA_VERSIONE = 0.5
GIORNI_PRIMA_DEL_DOWNLOAD = 10

SCHEMI = {
    "prezzi": pa.schema([("code", pa.string()), ("date", pa.date32()), ("open", pa.float64()), ("high", pa.float64()),
                         ("low", pa.float64()), ("close", pa.float64()), ("adjusted_close", pa.float64()),
                         ("volume", pa.int64()), ("currency", pa.string())]),
    "dividendi": pa.schema([("code", pa.string()), ("date", pa.date32()), ("declaration_date", pa.date32()),
                            ("record_date", pa.date32()), ("payment_date", pa.date32()), ("period", pa.string()),
                            ("value", pa.float64()), ("unadjusted_value", pa.float64()), ("currency", pa.string()),
                            ("currency_from_listing", pa.bool_())]),
    "split": pa.schema([("code", pa.string()), ("date", pa.date32()), ("ratio", pa.string()), ("new_shares", pa.float64()),
                        ("old_shares", pa.float64()), ("factor", pa.float64())]),
    "cambi": pa.schema([("pair", pa.string()), ("date", pa.date32()), ("open", pa.float64()), ("high", pa.float64()),
                        ("low", pa.float64()), ("close", pa.float64()), ("adjusted_close", pa.float64()),
                        ("volume", pa.int64())]),
    "tesoro": pa.schema([("curve", pa.string()), ("date", pa.date32()), ("tenor", pa.string()), ("rate", pa.float64()),
                         ("discount", pa.float64()), ("coupon", pa.float64()), ("avg_discount", pa.float64()),
                         ("avg_coupon", pa.float64()), ("maturity_date", pa.date32()), ("cusip", pa.string()),
                         ("rate_type", pa.string()), ("extrapolation_factor", pa.float64())]),
    "identificativi": pa.schema([("symbol", pa.string()), ("code", pa.string()), ("isin", pa.string()), ("figi", pa.string()),
                                 ("lei", pa.string()), ("cusip", pa.string()), ("cik", pa.string())]),
    "doppioni": pa.schema([("code", pa.string()), ("duplicates", pa.int64()), ("first_date", pa.date32())]),
    "barre_tolte": pa.schema([("code", pa.string()), ("twin", pa.string()), ("removed", pa.int64()),
                              ("first_date", pa.date32()), ("last_date", pa.date32())]),
}
TABELLE = tuple(SCHEMI)


# ------------------------------------------------------------- utilità pure --
def data_o_none(v):
    if not v or not isinstance(v, str) or len(v) < 10:
        return None
    try:
        return dt.date.fromisoformat(v[:10])
    except ValueError:
        return None


def numero_o_none(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def intero_o_none(v):
    x = numero_o_none(v)
    return None if x is None else int(round(x))


def rapporto_split(testo) -> tuple[float | None, float | None, float | None]:
    """"2.000000/1.000000" → (2.0, 1.0, 2.0): azioni nuove, vecchie, fattore nuove/vecchie."""
    try:
        nuove, vecchie = (float(x) for x in str(testo).split("/"))
        return nuove, vecchie, (nuove / vecchie if vecchie else None)
    except (ValueError, TypeError):
        return None, None, None


def simbolo(endpoint: str) -> tuple[str, str] | None:
    """"eod/SMRT_old.US" → ("SMRT_old", "US"). Il codice può contenere punti: la borsa è dopo l'ultimo."""
    parte = unquote(endpoint.split("/", 1)[1]) if "/" in endpoint else ""
    if "." not in parte:
        return None
    codice, borsa = parte.rsplit(".", 1)
    return (codice, borsa) if codice and borsa else None


def ticker_di_base(codice: str, codici_borsa: set[str], borsa: str = "US", delistati: set[str] | None = None) -> str:
    """X_old, X_oldN → X in ogni borsa; X più una cifra → X solo negli USA, se il codice è delistato e X esiste."""
    m = TWIN_OLD.match(codice)
    if m:
        return m.group("base")
    if borsa == "US" and delistati is not None and codice in delistati:
        m = TWIN_CIFRA.match(codice)
        if m and m.group("base") in codici_borsa and m.group("base") != codice:
            return m.group("base")
    return codice


def gemelli(codici: set[str], borsa: str = "US", delistati: set[str] | None = None) -> dict[str, list[str]]:
    """{codice: [gemelli]} secondo `ticker_di_base`."""
    out = defaultdict(list)
    for c in codici:
        base = ticker_di_base(c, codici, borsa, delistati)
        if base != c and base in codici:
            out[base].append(c)
    return {k: sorted(v) for k, v in out.items()}


def _volumi_vicini(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(1, TOLLERANZA_VOLUME * max(abs(a), abs(b)))


def togli_barre_copiate(serie: pa.Table, gemelli_serie: dict[str, pa.Table],
                        minimo: int = MINIMO_BLOCCO_COPIATO) -> tuple[pa.Table, list[dict]]:
    """Toglie da `serie` i blocchi di almeno `minimo` sedute consecutive con data e chiusura uguali a un gemello e volume
    uguale entro lo 0,5%."""
    if serie.num_rows == 0 or not gemelli_serie:
        return serie, []
    date = serie.column("date").to_pylist()
    close = serie.column("close").to_pylist()
    vol = serie.column("volume").to_pylist()
    togli = [False] * serie.num_rows
    registro = []
    for nome, g in sorted(gemelli_serie.items()):
        mappa = {d: (c, v) for d, c, v in zip(g.column("date").to_pylist(), g.column("close").to_pylist(),
                                              g.column("volume").to_pylist())}
        uguali = [not togli[i] and date[i] in mappa and close[i] is not None and close[i] == mappa[date[i]][0]
                  and _volumi_vicini(vol[i], mappa[date[i]][1]) for i in range(serie.num_rows)]
        tolte, i = [], 0
        while i < serie.num_rows:
            if not uguali[i]:
                i += 1
                continue
            j = i
            while j < serie.num_rows and uguali[j]:
                j += 1
            if j - i >= minimo:
                tolte.extend(range(i, j))
            i = j
        for k in tolte:
            togli[k] = True
        if tolte:
            registro.append({"twin": nome, "removed": len(tolte), "first_date": date[tolte[0]], "last_date": date[tolte[-1]]})
    if not registro:
        return serie, []
    return serie.filter(pa.array([not x for x in togli])), registro


def _ordina_senza_doppioni(t: pa.Table) -> tuple[pa.Table, int, object]:
    """(tabella ordinata per data senza date ripetute, righe tolte, prima data ripetuta). Ordinamento stabile: vale la
    prima riga del fornitore."""
    t = t.filter(pc.is_valid(t.column("date")))
    if t.num_rows == 0:
        return t, 0, None
    t = t.sort_by("date")
    date = t.column("date").to_pylist()
    tieni = [i == 0 or date[i] != date[i - 1] for i in range(len(date))]
    if all(tieni):
        return t, 0, None
    prima = next(date[i] for i, k in enumerate(tieni) if not k)
    return t.filter(pa.array(tieni)), tieni.count(False), prima


def scegli_versione(storia: list[dict]) -> tuple[dict, dict | None]:
    """(versione da usare, sostituzione mancata o None). La più recente con almeno metà delle righe della più lunga."""
    note = [v for v in storia if v.get("righe") is not None]
    if not note:
        return storia[-1], None
    massimo = max(v["righe"] for v in note)
    valide = [v for v in storia if v.get("righe") is None or v["righe"] >= QUOTA_MINIMA_VERSIONE * massimo]
    scelta = valide[-1] if valide else storia[-1]
    if scelta is not storia[-1]:
        return scelta, {"endpoint": storia[-1]["endpoint"], "scartata": storia[-1]["file"], "righe_scartata": storia[-1].get("righe"),
                        "usata": scelta["file"], "righe_usata": scelta.get("righe")}
    return scelta, None


# ------------------------------------------------------------ lettura grezzo --
def leggi_prezzi(corpo: bytes, formato: str, codice: str, valuta: str) -> pa.Table:
    """Serie di prezzi dal CSV o dal JSON del fornitore, nello schema di `prezzi`, ordinata per data, senza doppioni."""
    return leggi_prezzi_con_doppioni(corpo, formato, codice, valuta)[0]


def leggi_prezzi_con_doppioni(corpo: bytes, formato: str, codice: str, valuta: str) -> tuple[pa.Table, int, object]:
    """Come `leggi_prezzi`, più il numero di righe con data ripetuta tolte e la prima data ripetuta."""
    schema = SCHEMI["prezzi"]
    if formato == "csv":
        if corpo.count(b"\n") < 1 or not corpo.split(b"\n", 1)[1].strip():
            return schema.empty_table(), 0, None
        t = pacsv.read_csv(io.BytesIO(corpo), convert_options=pacsv.ConvertOptions(
            column_types={"Date": pa.string(), "Open": pa.float64(), "High": pa.float64(), "Low": pa.float64(),
                          "Close": pa.float64(), "Adjusted_close": pa.float64(), "Volume": pa.float64()},
            strings_can_be_null=True))
        n = t.num_rows
        righe = {"date": [data_o_none(x) for x in t.column("Date").to_pylist()],
                 "open": t.column("Open"), "high": t.column("High"), "low": t.column("Low"), "close": t.column("Close"),
                 "adjusted_close": t.column("Adjusted_close"),
                 "volume": [None if v is None or v != v else int(round(v)) for v in t.column("Volume").to_pylist()]}
    else:
        dati = json.loads(corpo) if corpo.strip() else []
        dati = dati if isinstance(dati, list) else []
        n = len(dati)
        righe = {"date": [data_o_none(b.get("date")) for b in dati],
                 **{k: [numero_o_none(b.get(k)) for b in dati] for k in ("open", "high", "low", "close", "adjusted_close")},
                 "volume": [intero_o_none(b.get("volume")) for b in dati]}
    t = pa.table({"code": pa.array([codice] * n, pa.string()), **righe,
                  "currency": pa.array([valuta or None] * n, pa.string())}, schema=schema)
    return _ordina_senza_doppioni(t)


def leggi_dividendi(corpo: bytes, codice: str, valuta_lista: str = "") -> pa.Table:
    dati = json.loads(corpo) if corpo.strip() else []
    dati = dati if isinstance(dati, list) else []
    valute = [d.get("currency") or None for d in dati]
    return pa.table({"code": [codice] * len(dati),
                     "date": [data_o_none(d.get("date")) for d in dati],
                     "declaration_date": [data_o_none(d.get("declarationDate")) for d in dati],
                     "record_date": [data_o_none(d.get("recordDate")) for d in dati],
                     "payment_date": [data_o_none(d.get("paymentDate")) for d in dati],
                     "period": [None if d.get("period") is None else str(d.get("period")) for d in dati],
                     "value": [numero_o_none(d.get("value", d.get("dividend"))) for d in dati],
                     "unadjusted_value": [numero_o_none(d.get("unadjustedValue")) for d in dati],
                     "currency": [v or (valuta_lista or None) for v in valute],
                     "currency_from_listing": [v is None and bool(valuta_lista) for v in valute]}, schema=SCHEMI["dividendi"])


def leggi_split(corpo: bytes, codice: str) -> pa.Table:
    dati = json.loads(corpo) if corpo.strip() else []
    dati = dati if isinstance(dati, list) else []
    rapporti = [rapporto_split(d.get("split")) for d in dati]
    return pa.table({"code": [codice] * len(dati), "date": [data_o_none(d.get("date")) for d in dati],
                     "ratio": [d.get("split") for d in dati], "new_shares": [r[0] for r in rapporti],
                     "old_shares": [r[1] for r in rapporti], "factor": [r[2] for r in rapporti]}, schema=SCHEMI["split"])


# ------------------------------------------------------------------ scrittura --
def _rinomina(da: Path, a: Path, tentativi: int = 5) -> None:
    for i in range(tentativi):
        try:
            da.rename(a)
            return
        except PermissionError:
            if i == tentativi - 1:
                raise
            time.sleep(0.5 * (i + 1))


class Partizione:
    """Scrive una partizione a flusso: gruppi da RIGHE_PER_GRUPPO righe, file da RIGHE_PER_FILE, poi scambio della cartella
    (con ritorno alla versione vecchia se lo scambio non riesce)."""

    def __init__(self, base: Path, man: Path, tabella: str, borsa: str):
        self.base, self.man, self.tabella, self.borsa = base, man, tabella, borsa
        self.schema = SCHEMI[tabella]
        self.finale = base / tabella / "exchange={}".format(borsa)
        self.tmp = base / tabella / ".tmp_exchange={}".format(borsa)
        if self.tmp.exists():
            shutil.rmtree(self.tmp)
        self.tmp.mkdir(parents=True)
        self.buffer, self.in_buffer = [], 0
        self.writer, self.righe_file, self.n_file, self.totale = None, 0, 0, 0
        self.file_scritti = []

    def aggiungi(self, t: pa.Table) -> None:
        if t.num_rows:
            self.buffer.append(t.cast(self.schema))
            self.in_buffer += t.num_rows
            if self.in_buffer >= RIGHE_PER_GRUPPO:
                self._svuota()

    def _svuota(self) -> None:
        if not self.buffer:
            return
        t = pa.concat_tables(self.buffer)
        self.buffer, self.in_buffer = [], 0
        while t.num_rows:
            if self.writer is None:
                f = self.tmp / "part-{:05d}.parquet".format(self.n_file)
                self.writer = pq.ParquetWriter(f, self.schema, compression=COMPRESSIONE)
                self.file_scritti.append([f, 0])
                self.righe_file = 0
            pezzo = t.slice(0, RIGHE_PER_FILE - self.righe_file)
            self.writer.write_table(pezzo)
            self.righe_file += pezzo.num_rows
            self.file_scritti[-1][1] += pezzo.num_rows
            self.totale += pezzo.num_rows
            t = t.slice(pezzo.num_rows)
            if self.righe_file >= RIGHE_PER_FILE:
                self._chiudi_file()

    def _chiudi_file(self) -> None:
        if self.writer is not None:
            self.writer.close()
            self.writer, self.n_file = None, self.n_file + 1

    def ferma_scrittura(self) -> None:
        """Svuota il buffer e chiude il file aperto: dopo, i file della cartella temporanea si possono leggere."""
        self._svuota()
        self._chiudi_file()

    def aggiungi_da_sql(self, con, sql: str, parametri: list | None = None) -> int:
        """Scrive in un file nuovo della partizione il risultato di una query DuckDB (a flusso). Righe scritte."""
        self.ferma_scrittura()
        f = self.tmp / "part-{:05d}.parquet".format(self.n_file)
        con.execute("COPY ({}) TO '{}' (FORMAT parquet, COMPRESSION zstd)".format(sql, f.as_posix().replace("'", "''")),
                    parametri or [])
        righe = pq.ParquetFile(f).metadata.num_rows if f.exists() else 0
        if righe:
            self.file_scritti.append([f, righe])
            self.totale += righe
            self.n_file += 1
        elif f.exists():
            f.unlink()
        return righe

    def file_temporanei(self) -> str:
        return (self.tmp / "*.parquet").as_posix()

    def chiudi(self, sorgenti: list[dict]) -> int:
        self.ferma_scrittura()
        if not self.file_scritti:                            # partizione vuota: un file vuoto con lo schema
            f = self.tmp / "part-00000.parquet"
            pq.write_table(self.schema.empty_table(), f, compression=COMPRESSIONE)
            self.file_scritti.append([f, 0])
        adesso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        impronta = hashlib.sha256("\n".join(sorted(s["sha256"] for s in sorgenti)).encode()).hexdigest()
        righe_man = [{"tabella": self.tabella, "borsa": self.borsa,
                      "file": (Path("eodhd") / "parquet" / self.tabella / self.finale.name / f.name).as_posix(),
                      "righe": n, "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "sorgenti": len(sorgenti),
                      "impronta_sorgenti": impronta, "creato": adesso} for f, n in self.file_scritti]
        vecchia = self.base / self.tabella / ".old_exchange={}".format(self.borsa)
        if vecchia.exists():
            shutil.rmtree(vecchia)
        if self.finale.exists():
            _rinomina(self.finale, vecchia)
        try:
            _rinomina(self.tmp, self.finale)
        except PermissionError:
            if vecchia.exists() and not self.finale.exists():
                _rinomina(vecchia, self.finale)             # si torna alla versione di prima: mai una borsa senza cartella
            raise
        if vecchia.exists():
            shutil.rmtree(vecchia, ignore_errors=True)
        (self.man / "sorgenti").mkdir(parents=True, exist_ok=True)
        (self.man / "sorgenti" / "{}__{}.json".format(self.tabella, self.borsa)).write_text(json.dumps(sorgenti), encoding="utf-8")
        from market_data import registri
        for r in righe_man:
            registri.appendi(self.man / "normalizzato.jsonl", r)
        return self.totale


class Normalizzatore:
    def __init__(self, archivio: Path, log=print):
        self.archivio = archivio
        self.grezzo = Grezzo(archivio)
        self.base = archivio / "eodhd" / "parquet"
        self.man = archivio / "eodhd" / "manifest"
        self.log = log
        self.sostituzioni_mancate: list[dict] = []
        self._liste = None
        self._registro: list[dict] | None = None
        self._riusi: dict[tuple[str, str], str] | None = None

    def voci(self) -> list[dict]:
        """Ultima voce con stato 200 per chiave (endpoint + parametri) del livello grezzo."""
        return list(self.grezzo._ok.values())

    def liste(self) -> dict[str, dict]:
        """Per borsa: `info` (ultimo record noto per codice, da tutte le versioni delle liste), `ultime` (codici nelle
        liste più recenti), `delistati` (codici delistati nelle liste più recenti)."""
        if self._liste is None:
            out = defaultdict(lambda: {"info": {}, "ultime": set(), "delistati": set()})
            for voce in self.voci():
                if not voce["endpoint"].startswith("exchange-symbol-list/"):
                    continue
                borsa = voce["endpoint"].split("/", 1)[1]
                delistata = voce["parametri"].get("delisted") == "1"
                lette = set()
                for versione in self.grezzo.storia(voce):
                    if versione.get("sha256") in lette:
                        continue
                    lette.add(versione.get("sha256"))
                    for r in json.loads(self.grezzo.leggi(versione)):
                        if r.get("Code"):
                            out[borsa]["info"][r["Code"]] = dict(r, _stato="delistato" if delistata else "attivo")
                for r in json.loads(self.grezzo.leggi(voce)):
                    if r.get("Code"):
                        out[borsa]["ultime"].add(r["Code"])
                        if delistata:
                            out[borsa]["delistati"].add(r["Code"])
            self._liste = dict(out)
        return self._liste

    def valuta(self, codice: str, borsa: str) -> str:
        v = (self.liste().get(borsa, {}).get("info", {}).get(codice) or {}).get("Currency") or ""
        return "" if v == "NA" else v

    def registro_aggiornamenti(self) -> list[dict]:
        """Righe di `manifest/aggiornamenti.jsonl` (scritto dall'aggiornamento incrementale)."""
        if self._registro is None:
            from market_data import registri
            self._registro = registri.leggi(self.man / "aggiornamenti.jsonl")[0]
        return self._registro

    def riusi(self) -> dict[tuple[str, str], str]:
        """(borsa, codice) -> istante dell'ultimo segno di riuso. Letto una volta per normalizzazione."""
        if self._riusi is None:
            out: dict[tuple[str, str], str] = {}
            for r in self.registro_aggiornamenti():
                if r.get("tipo") == "riuso" and r.get("borsa") and r.get("codice") and r.get("dal"):
                    chiave = (r["borsa"], r["codice"])
                    out[chiave] = max(out.get(chiave, ""), r["dal"])
            self._riusi = out
        return self._riusi

    def dopo_il_riuso(self, voce: dict, storia: list[dict]) -> list[dict]:
        """Versioni scaricate dopo l'ultimo segno di riuso del codice: quelle prima sono di un'altra società. Vuota se
        la serie nuova non è ancora arrivata (il codice resta senza dati per quella tabella)."""
        s = simbolo(voce["endpoint"])
        dal = self.riusi().get((s[1], s[0])) if s else None
        return [v for v in storia if v["scaricato"] >= dal] if dal else storia

    def gruppi(self, tabelle: set[str], borse: set[str] | None) -> dict:
        """tabella -> borsa -> codice -> (voce, formato). Solo serie complete (unico parametro fmt); CSV prima di JSON; fra
        le versioni dello stesso formato, `scegli_versione`."""
        out = defaultdict(lambda: defaultdict(dict))
        for voce in self.voci():
            ep = voce["endpoint"]
            tipo = ep.split("/", 1)[0]
            if tipo not in ("eod", "div", "splits") or set(voce["parametri"]) != {"fmt"}:
                continue
            s = simbolo(ep)
            if not s:
                continue
            codice, borsa = s
            tabella = {"eod": "cambi" if borsa == "FOREX" else "prezzi", "div": "dividendi", "splits": "split"}[tipo]
            if tabella not in tabelle or (borse and borsa not in borse):
                continue
            formato = voce["parametri"]["fmt"]
            storia = self.dopo_il_riuso(voce, self.grezzo.storia(voce))
            if not storia:
                continue
            scelta, mancata = scegli_versione(storia)
            if mancata:
                self.sostituzioni_mancate.append(mancata)
            prima = out[tabella][borsa].get(codice)
            if prima is None or (formato == "csv" and prima[1] != "csv"):
                out[tabella][borsa][codice] = (scelta, formato)
        return out

    def blocchi(self, tabella: str, borsa: str, dal: str) -> list[str]:
        """File dei dati in blocco (prezzi, split o dividendi) della borsa con data dal giorno `dal` in poi."""
        tipo = {"prezzi": None, "split": "splits", "dividendi": "dividends"}[tabella]
        out = []
        for voce in self.voci():
            if voce["endpoint"] != "eod-bulk-last-day/" + borsa or voce["parametri"].get("type") != tipo:
                continue
            if str(voce["parametri"].get("date", "")) >= dal and (voce.get("righe") or 0) > 0 and self._lista_json(voce):
                out.append(str(self.archivio / voce["file"]))
        return sorted(out)

    def _lista_json(self, voce: dict) -> bool:
        """Vero se il file comincia con una lista JSON: un errore del fornitore in un oggetto fermerebbe DuckDB."""
        import gzip
        try:
            with gzip.open(self.archivio / voce["file"], "rb") as fh:
                inizio = fh.read(256).lstrip()
        except OSError:
            return False
        return inizio[:1] == b"["

    def _unisci_blocco(self, part: Partizione, tabella: str, borsa: str, per_codice: dict) -> tuple[int, list[dict]]:
        """Righe del blocco aggiunte alla partizione (a flusso con DuckDB) e file usati."""
        if tabella not in ("prezzi", "dividendi", "split") or not per_codice:
            return 0, []
        scaricati = [v["scaricato"][:10] for v, _f in per_codice.values()]
        dal = (dt.date.fromisoformat(min(scaricati)) - dt.timedelta(days=GIORNI_PRIMA_DEL_DOWNLOAD)).isoformat()
        file = self.blocchi(tabella, borsa, dal)
        if not file:
            return 0, []
        import duckdb
        con = C.applica_limiti(duckdb.connect())
        part.ferma_scrittura()
        riusi = self.riusi()
        scaricato = {c: dt.date.fromisoformat(per_codice[c][0]["scaricato"][:10]) for c in per_codice}
        codici = pa.table({"code": sorted(per_codice),
                           "scaricato": [scaricato[c] for c in sorted(per_codice)],
                           #  eventi dal blocco da questo giorno: il giorno prima del download (eventi pubblicati in
                           #  ritardo), o il giorno stesso per un codice riusato (prima c'era l'altra società)
                           "eventi_dal": [scaricato[c] - dt.timedelta(days=0 if (borsa, c) in riusi else 1) for c in sorted(per_codice)],
                           "valuta": [self.valuta(c, borsa) or None for c in sorted(per_codice)]})
        con.register("codici_t", codici)
        lista = "[" + ", ".join("'{}'".format(Path(f).as_posix().replace("'", "''")) for f in file) + "]"
        esistenti = "read_parquet('{}')".format(part.file_temporanei()) if part.file_scritti else None
        if tabella == "prezzi":
            ultima = ("SELECT c.code, coalesce(max(e.date), c.scaricato - INTERVAL 1 DAY) AS ultima FROM codici_t c "
                      "LEFT JOIN {} e USING (code) GROUP BY c.code, c.scaricato".format(esistenti)) if esistenti else \
                     "SELECT code, scaricato - INTERVAL 1 DAY AS ultima FROM codici_t"
            sql = """
                WITH b AS (SELECT CAST(code AS VARCHAR) AS code, CAST(date AS DATE) AS date, CAST(open AS DOUBLE) AS open,
                                  CAST(high AS DOUBLE) AS high, CAST(low AS DOUBLE) AS low, CAST(close AS DOUBLE) AS close,
                                  CAST(adjusted_close AS DOUBLE) AS adjusted_close,
                                  CAST(round(CAST(volume AS DOUBLE)) AS BIGINT) AS volume
                           FROM read_json({lista}, format = 'array', columns = {{code: 'VARCHAR', date: 'VARCHAR', open: 'DOUBLE',
                                high: 'DOUBLE', low: 'DOUBLE', close: 'DOUBLE', adjusted_close: 'DOUBLE', volume: 'DOUBLE'}})),
                     u AS ({ultima})
                SELECT b.code, b.date, b.open, b.high, b.low, b.close, b.adjusted_close, b.volume, c.valuta AS currency
                FROM b JOIN u USING (code) JOIN codici_t c USING (code)
                WHERE b.date > u.ultima
                QUALIFY row_number() OVER (PARTITION BY b.code, b.date ORDER BY b.close) = 1
                ORDER BY code, date""".format(lista=lista, ultima=ultima)
        elif tabella == "split":
            gia = "AND NOT EXISTS (SELECT 1 FROM {} e WHERE e.code = b.code AND e.date = b.date)".format(esistenti) if esistenti else ""
            sql = """
                WITH b AS (SELECT CAST(code AS VARCHAR) AS code, CAST(date AS DATE) AS date, CAST(split AS VARCHAR) AS ratio
                           FROM read_json({lista}, format = 'array', columns = {{code: 'VARCHAR', date: 'VARCHAR', split: 'VARCHAR'}}))
                SELECT b.code, b.date, b.ratio, TRY_CAST(split_part(b.ratio, '/', 1) AS DOUBLE) AS new_shares,
                       TRY_CAST(split_part(b.ratio, '/', 2) AS DOUBLE) AS old_shares,
                       TRY_CAST(split_part(b.ratio, '/', 1) AS DOUBLE) / NULLIF(TRY_CAST(split_part(b.ratio, '/', 2) AS DOUBLE), 0) AS factor
                FROM b JOIN codici_t c USING (code) WHERE b.date >= c.eventi_dal {gia}
                QUALIFY row_number() OVER (PARTITION BY b.code, b.date ORDER BY b.ratio) = 1
                ORDER BY code, date""".format(lista=lista, gia=gia)
        else:
            gia = "AND NOT EXISTS (SELECT 1 FROM {} e WHERE e.code = b.code AND e.date = b.date)".format(esistenti) if esistenti else ""
            sql = """
                WITH b AS (SELECT CAST(code AS VARCHAR) AS code, CAST(date AS DATE) AS date,
                                  TRY_CAST(declarationDate AS DATE) AS declaration_date, TRY_CAST(recordDate AS DATE) AS record_date,
                                  TRY_CAST(paymentDate AS DATE) AS payment_date, CAST(period AS VARCHAR) AS period,
                                  TRY_CAST(dividend AS DOUBLE) AS value, TRY_CAST(unadjustedValue AS DOUBLE) AS unadjusted_value,
                                  NULLIF(CAST(currency AS VARCHAR), '') AS currency
                           FROM read_json({lista}, format = 'array', columns = {{code: 'VARCHAR', date: 'VARCHAR',
                                declarationDate: 'VARCHAR', recordDate: 'VARCHAR', paymentDate: 'VARCHAR', period: 'VARCHAR',
                                dividend: 'VARCHAR', unadjustedValue: 'VARCHAR', currency: 'VARCHAR'}}))
                SELECT b.code, b.date, b.declaration_date, b.record_date, b.payment_date, b.period, b.value, b.unadjusted_value,
                       coalesce(b.currency, c.valuta) AS currency, (b.currency IS NULL AND c.valuta IS NOT NULL) AS currency_from_listing
                FROM b JOIN codici_t c USING (code) WHERE b.date >= c.eventi_dal {gia}
                QUALIFY row_number() OVER (PARTITION BY b.code, b.date ORDER BY b.value) = 1
                ORDER BY code, date""".format(lista=lista, gia=gia)
        righe = part.aggiungi_da_sql(con, sql)
        con.close()
        usati = set(file)
        voci = [v for v in self.voci() if str(self.archivio / v["file"]) in usati]
        return righe, [{"file": v["file"], "sha256": v["sha256"]} for v in voci]

    def per_titolo(self, tabelle: set[str], borse: set[str] | None) -> dict:
        esito = {}
        for tabella, per_borsa in self.gruppi(tabelle, borse).items():
            for borsa, per_codice in sorted(per_borsa.items()):
                part = Partizione(self.base, self.man, tabella, borsa)
                tolte_part = Partizione(self.base, self.man, "barre_tolte", borsa) if tabella == "prezzi" else None
                doppi_part = Partizione(self.base, self.man, "doppioni", borsa) if tabella == "prezzi" else None
                delistati = self.liste().get(borsa, {}).get("delistati", set())
                gem = gemelli(set(per_codice), borsa, delistati) if tabella == "prezzi" else {}
                sorgenti, n_tolte = [], 0

                def serie(cod, registra=False):
                    v, f = per_codice[cod]
                    s, n_doppi, prima = leggi_prezzi_con_doppioni(self.grezzo.leggi(v), f, cod, self.valuta(cod, borsa))
                    if registra and n_doppi:
                        doppi_part.aggiungi(pa.table({"code": [cod], "duplicates": [n_doppi], "first_date": [prima]},
                                                     schema=SCHEMI["doppioni"]))
                    return s

                for codice in sorted(per_codice):
                    voce, formato = per_codice[codice]
                    sorgenti.append({"file": voce["file"], "sha256": voce["sha256"]})
                    if tabella == "prezzi":
                        t = serie(codice, registra=True)
                        if codice in gem:
                            t, reg = togli_barre_copiate(t, {g: serie(g) for g in gem[codice]})
                            if reg:
                                n_tolte += sum(r["removed"] for r in reg)
                                tolte_part.aggiungi(pa.table({k: [r.get(k) if k != "code" else codice for r in reg]
                                                              for k in SCHEMI["barre_tolte"].names}, schema=SCHEMI["barre_tolte"]))
                        part.aggiungi(t)
                    elif tabella == "cambi":
                        t = leggi_prezzi(self.grezzo.leggi(voce), formato, codice, "")
                        part.aggiungi(pa.table({"pair": t.column("code"), **{k: t.column(k) for k in SCHEMI["cambi"].names[1:]}},
                                               schema=SCHEMI["cambi"]))
                    elif tabella == "dividendi":
                        part.aggiungi(leggi_dividendi(self.grezzo.leggi(voce), codice, self.valuta(codice, borsa)))
                    else:
                        part.aggiungi(leggi_split(self.grezzo.leggi(voce), codice))
                righe_blocco, sorgenti_blocco = self._unisci_blocco(part, tabella, borsa, per_codice)
                esito["{} {}".format(tabella, borsa)] = part.chiudi(sorgenti + sorgenti_blocco)
                if righe_blocco:
                    esito["{} {} dal blocco".format(tabella, borsa)] = righe_blocco
                if tolte_part is not None:
                    tolte_part.chiudi(sorgenti)
                    doppi_part.chiudi(sorgenti)
                    esito["barre_tolte {}".format(borsa)] = n_tolte
                self.log("{} {}: {} righe da {} file grezzi".format(tabella, borsa, esito["{} {}".format(tabella, borsa)],
                                                                  len(sorgenti) + len(sorgenti_blocco)))
        if self.sostituzioni_mancate:
            esito["sostituzioni_mancate"] = len(self.sostituzioni_mancate)
            self.log("versioni nuove vuote o troppo corte non usate: {}".format(len(self.sostituzioni_mancate)))
        return esito

    def tesoro(self) -> int:
        tabs, sorgenti = [], []
        for voce in sorted(self.voci(), key=lambda v: (v["endpoint"], json.dumps(v["parametri"], sort_keys=True))):
            if not voce["endpoint"].startswith("ust/"):
                continue
            curva = voce["endpoint"].split("/", 1)[1]
            dati = (json.loads(self.grezzo.leggi(voce)) or {}).get("data") or []
            sorgenti.append({"file": voce["file"], "sha256": voce["sha256"]})
            tabs.append(pa.table({
                "curve": [curva] * len(dati), "date": [data_o_none(d.get("date")) for d in dati],
                "tenor": [d.get("tenor") for d in dati], "rate": [numero_o_none(d.get("rate")) for d in dati],
                "discount": [numero_o_none(d.get("discount")) for d in dati], "coupon": [numero_o_none(d.get("coupon")) for d in dati],
                "avg_discount": [numero_o_none(d.get("avg_discount")) for d in dati],
                "avg_coupon": [numero_o_none(d.get("avg_coupon")) for d in dati],
                "maturity_date": [data_o_none(d.get("maturity_date")) for d in dati], "cusip": [d.get("cusip") for d in dati],
                "rate_type": [d.get("rate_type") for d in dati],
                "extrapolation_factor": [numero_o_none(d.get("extrapolation_factor")) for d in dati]}, schema=SCHEMI["tesoro"]))
        if not sorgenti:
            return 0
        part = Partizione(self.base, self.man, "tesoro", "US")
        t = pa.concat_tables(tabs)
        part.aggiungi(t.sort_by([("curve", "ascending"), ("date", "ascending")]) if t.num_rows else t)
        return part.chiudi(sorgenti)

    def voci_identificativi(self) -> list[dict]:
        """Pagine della mappatura: quelle dell'ultima mappatura completa registrata dall'aggiornamento, se c'è; altrimenti
        l'ultima versione di ogni pagina (download in massa). In ordine di pagina."""
        righe = [r for r in self.registro_aggiornamenti() if r.get("tipo") == "identificativi"]
        complete = [r for r in righe if r.get("file")]
        if complete:
            file = set(complete[-1]["file"])
            voci = {v["file"]: v for vv in self.grezzo._storia.values() for v in vv if v["file"] in file}
            scelte = list(voci.values())
        elif righe:                                  # primo salvataggio interrotto: le pagine di prima
            limite = righe[0].get("quando") or ""
            scelte = []
            for storia in self.grezzo._storia.values():
                prima = [v for v in storia if v["endpoint"] == "id-mapping" and v["scaricato"] < limite]
                if prima:
                    scelte.append(prima[-1])
        else:
            scelte = [v for v in self.voci() if v["endpoint"] == "id-mapping"]
        return sorted((v for v in scelte if v["endpoint"] == "id-mapping"),
                      key=lambda v: int(v["parametri"].get("page[offset]", 0) or 0))

    def identificativi(self) -> dict:
        per_borsa, sorgenti, visti = defaultdict(list), defaultdict(dict), set()
        for voce in self.voci_identificativi():
            for d in (json.loads(self.grezzo.leggi(voce)) or {}).get("data") or []:
                sym = d.get("symbol") or ""
                if "." not in sym:
                    continue
                codice, borsa = sym.rsplit(".", 1)
                sorgenti[borsa][voce["file"]] = voce["sha256"]
                if sym not in visti:
                    visti.add(sym)
                    per_borsa[borsa].append((sym, codice, d))
        out = {}
        for borsa, righe in sorted(per_borsa.items()):
            righe.sort(key=lambda r: r[0])
            part = Partizione(self.base, self.man, "identificativi", borsa)
            part.aggiungi(pa.table({"symbol": [r[0] for r in righe], "code": [r[1] for r in righe],
                                    **{k: [(str(r[2].get(k)).strip() or None) if r[2].get(k) is not None else None for r in righe]
                                       for k in ("isin", "figi", "lei", "cusip", "cik")}},     # "" del fornitore = mancante
                                   schema=SCHEMI["identificativi"]))
            out[borsa] = part.chiudi([{"file": f, "sha256": s} for f, s in sorted(sorgenti[borsa].items())])
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Costruisce le tabelle Parquet dal livello grezzo")
    ap.add_argument("--tabelle", default="prezzi,dividendi,split,cambi,tesoro,identificativi")
    ap.add_argument("--borse", default="")
    a = ap.parse_args(argv)
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    scelte = {t.strip() for t in a.tabelle.split(",") if t.strip()}
    borse = {b.strip() for b in a.borse.split(",") if b.strip()} or None
    n = Normalizzatore(C.archivio())
    esito = n.per_titolo(scelte & {"prezzi", "dividendi", "split", "cambi"}, borse)
    if "tesoro" in scelte:
        esito["tesoro US"] = n.tesoro()
    if "identificativi" in scelte:
        esito.update({"identificativi " + b: v for b, v in n.identificativi().items()})
    print(json.dumps(esito, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
