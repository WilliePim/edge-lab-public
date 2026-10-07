"""Serie della Fed: FRED (CSV pubblico), ALFRED (versioni storiche), excess bond premium (EBP) e curva GSW del Board.

Le funzioni pubbliche stanno in `api.py` (`fred`, `ebp`, `gsw`); qui la lettura, il livello grezzo e il parsing.
Solo libreria standard per la rete (`urllib`, come `eodhd/client.py`); pandas per il risultato. Trasporto iniettabile:
i test non fanno nessuna chiamata vera. Decisioni in docs/adr/008.

**Fonti** (verificate con una chiamata reale il 30-09-2026):
- FRED, senza chiave: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIE` — la versione di oggi della serie.
- ALFRED, con chiave `FRED_API_KEY`: `https://api.stlouisfed.org/fred/series/observations` con
  `realtime_start = realtime_end = al_giorno` — la serie come si leggeva quel giorno. Senza chiave l'API risponde
  400 «Variable api_key is not set»: qui ci si ferma prima, con `ConfigError`, e non si ripiega sui dati di oggi.
- EBP (Gilchrist-Zakrajšek, pagina della Fed «Updating the Recession Risk and the Excess Bond Premium»):
  `https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv`, mensile dal gennaio 1973, colonne
  `date,gz_spread,ebp,est_prob`. Ristimato a ogni aggiornamento, nessuna versione storica: ogni download resta con la
  sua data.
- Curva GSW (Gürkaynak-Sack-Wright): `https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv`,
  giornaliera dal 14-06-1961, 9 righe di nota prima dell'intestazione `Date,BETA0,...`, `NA` per i valori mancanti.

**Livello grezzo**: `<archivio>/fred/raw/<AAAA-MM-GG>/…` e `<archivio>/fred/manifest/grezzo.jsonl`, con `store/raw.py`
(`Grezzo(archivio, "fred")`): ogni download è un file nuovo con la sua data, mai sovrascritto, chiave mai scritta.
**Riuso**: il CSV di FRED, l'EBP e la curva GSW cambiano nel tempo, quindi si riscaricano al massimo una volta al giorno
(UTC) e per il resto del giorno si rilegge il file; una versione ALFRED è immutabile e si scarica una volta sola.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from market_data import config as C
from market_data.eodhd.client import oscura
from market_data.store.raw import Grezzo

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ALFRED = "https://api.stlouisfed.org/fred/series/observations"
EBP_URL = "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv"
GSW_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
USER_AGENT = "market-data/0.1 (uso personale)"
TIMEOUT = 60
LIMITE_ALFRED = 100_000                      # osservazioni per richiesta, il massimo dell'API


class ErroreFonte(RuntimeError):
    """La fonte non ha risposto 200, o ha risposto senza dati: ci si ferma, non si inventa e non si ripiega."""


def trasporto_urllib(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""


def _numero(v) -> float | None:
    v = (v or "").strip()
    if v in ("", ".", "NA", "ND"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def leggi_fredgraph(corpo: bytes, serie: str) -> list[tuple[dt.date, float]]:
    """`observation_date,SERIE`; le righe senza valore (`.`) si tolgono."""
    righe = list(csv.DictReader(io.StringIO(corpo.decode("utf-8-sig"))))
    if not righe or serie not in righe[0]:
        raise ErroreFonte("FRED {}: risposta senza la colonna della serie (intestazione: {})".format(
            serie, list(righe[0].keys()) if righe else "vuota"))
    out = []
    for r in righe:
        v = _numero(r.get(serie))
        if v is not None:
            out.append((dt.date.fromisoformat(r["observation_date"]), v))
    return out


def leggi_alfred(corpo: bytes, serie: str, al_giorno: dt.date) -> list[tuple[dt.date, float]]:
    try:
        dati = json.loads(corpo)
    except ValueError as e:
        raise ErroreFonte("ALFRED {} al {}: risposta non JSON".format(serie, al_giorno)) from e
    if "error_message" in dati:
        raise ErroreFonte("ALFRED {} al {}: {}".format(serie, al_giorno, dati["error_message"]))
    oss = dati.get("observations") or []
    if not oss:
        raise ErroreFonte("ALFRED {} al {}: nessuna versione della serie nota quel giorno (observations vuoto; la prima "
                          "versione in ALFRED è più recente, o la serie non ha versioni storiche)".format(serie, al_giorno))
    if int(dati.get("count", len(oss))) > len(oss):
        raise ErroreFonte("ALFRED {} al {}: risposta troncata ({} di {} osservazioni)".format(
            serie, al_giorno, len(oss), dati.get("count")))
    out = []
    for o in oss:
        v = _numero(o.get("value"))
        if v is not None:
            out.append((dt.date.fromisoformat(o["date"]), v))
    return out


def leggi_ebp(corpo: bytes) -> list[dict]:
    """`date,gz_spread,ebp,est_prob`, date come `1/1/1973` (mese/giorno/anno)."""
    righe = list(csv.DictReader(io.StringIO(corpo.decode("utf-8-sig"))))
    if not righe or "ebp" not in righe[0]:
        raise ErroreFonte("EBP: risposta senza la colonna `ebp` (intestazione: {})".format(
            list(righe[0].keys()) if righe else "vuota"))
    out = []
    for r in righe:
        m, g, a = (int(x) for x in r["date"].split("/"))
        out.append({"date": dt.date(a, m, g), **{k: _numero(r.get(k)) for k in ("gz_spread", "ebp", "est_prob")}})
    return out


def leggi_gsw(corpo: bytes) -> tuple[list[str], list[dict]]:
    """Salta le righe di nota fino a `Date,...`; `NA` diventa None. Restituisce (colonne, righe)."""
    testo = corpo.decode("utf-8-sig")
    righe_testo = testo.splitlines()
    inizio = next((i for i, r in enumerate(righe_testo) if r.startswith("Date,")), None)
    if inizio is None:
        raise ErroreFonte("GSW: intestazione `Date,...` non trovata nel file")
    lettore = csv.DictReader(io.StringIO("\n".join(righe_testo[inizio:])))
    colonne = [c for c in lettore.fieldnames if c != "Date"]
    out = []
    for r in lettore:
        if not r.get("Date"):
            continue
        out.append({"date": dt.date.fromisoformat(r["Date"]), **{c: _numero(r.get(c)) for c in colonne}})
    return colonne, out


def _df(righe: list[dict], colonne: list[str]):
    import pandas as pd
    df = pd.DataFrame(righe, columns=["date"] + colonne)
    df["date"] = pd.to_datetime(df["date"])
    for c in colonne:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _taglia(df, inizio: dt.date | None, fine: dt.date | None):
    import pandas as pd
    if inizio is not None:
        df = df[df["date"] >= pd.Timestamp(inizio)]
    if fine is not None:
        df = df[df["date"] <= pd.Timestamp(fine)]
    return df.reset_index(drop=True)


class Lettore:
    def __init__(self, archivio: Path, trasporto: Callable[[str], tuple[int, bytes]] | None = None,
                 adesso: Callable[[], datetime] | None = None, env_file: Path | None = None):
        self.grezzo = Grezzo(archivio, "fred")
        self._trasporto = trasporto or trasporto_urllib
        self._adesso = adesso or (lambda: datetime.now(timezone.utc))
        self._env_file = env_file
        self.chiamate = 0

    def _scarica(self, endpoint: str, params: dict, url: str, immutabile: bool) -> bytes:
        """Il corpo: dal grezzo se già scaricato (oggi, o mai se `immutabile`), altrimenti dalla rete, salvato con la sua data."""
        voce = self.grezzo.gia_scaricato(endpoint, params)
        oggi = self._adesso().date().isoformat()
        if voce is not None and (immutabile or voce["scaricato"][:10] == oggi):
            return self.grezzo.leggi(voce)
        stato, corpo = self._trasporto(url)
        self.chiamate += 1
        self.grezzo.salva(endpoint, params, stato, corpo, adesso=self._adesso())
        if stato != 200:
            raise ErroreFonte("{}: HTTP {} da {}".format(endpoint, stato, oscura(url)))
        return corpo

    def serie(self, serie: str, inizio: dt.date | None = None, fine: dt.date | None = None,
              al_giorno: dt.date | None = None):
        if not serie or not serie.replace("_", "").isalnum():
            raise ValueError("serie FRED non valida: {!r}".format(serie))
        if al_giorno is None:
            url = FRED_CSV + "?" + urllib.parse.urlencode({"id": serie})
            corpo = self._scarica("fredgraph/" + serie, {"id": serie, "fmt": "csv"}, url, immutabile=False)
            righe = leggi_fredgraph(corpo, serie)
        else:
            chiave = C.chiave_fred(env_file=self._env_file)          # prima di qualunque richiesta
            giorno = al_giorno.isoformat()
            parametri = {"series_id": serie, "realtime_start": giorno, "realtime_end": giorno, "file_type": "json",
                         "limit": str(LIMITE_ALFRED)}
            url = ALFRED + "?" + urllib.parse.urlencode({**parametri, "api_key": chiave})
            corpo = self._scarica("alfred/" + serie, {**parametri, "fmt": "json"}, url, immutabile=True)
            righe = leggi_alfred(corpo, serie, al_giorno)
        df = _df([{"date": d, "value": v} for d, v in righe], ["value"])
        return _taglia(df, inizio, fine)

    def ebp(self, inizio: dt.date | None = None, fine: dt.date | None = None):
        corpo = self._scarica("ebp", {"fmt": "csv"}, EBP_URL, immutabile=False)
        return _taglia(_df(leggi_ebp(corpo), ["gz_spread", "ebp", "est_prob"]), inizio, fine)

    def gsw(self, inizio: dt.date | None = None, fine: dt.date | None = None):
        corpo = self._scarica("gsw", {"fmt": "csv"}, GSW_URL, immutabile=False)
        colonne, righe = leggi_gsw(corpo)
        return _taglia(_df(righe, colonne), inizio, fine)
