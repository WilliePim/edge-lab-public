"""Client EDGAR minimale: throttle, cache su disco, backoff.

PERCHE' UN SECONDO CLIENT, quando il progetto ospite ne ha gia' uno.

Questo package e' pensato per essere pubblicato da solo, e un package che
importa meta' di un altro repo non e' autosufficiente. Il costo della copia e'
zero in termini di rete: la cache e' indicizzata sull'hash dell'URL, quindi i
due client si servono dagli stessi file su disco e nessuna richiesta viene
ripetuta perche' e' partita di qui invece che di la'.

Cio' che questo client sa fare in piu' del suo gemello: raggiungere il
DOCUMENTO PRIMARIO di un deposito. Nessuno nello scanner ha mai scaricato il
testo di un filing -- prende indici, JSON e XML di ownership -- e senza il testo
non c'e' niente da estrarre.

La SEC chiede un User-Agent con nome ed email veri e tiene il traffico sotto le
10 richieste al secondo. Il nome NON sta nel codice: arriva da EDGAR_USER_AGENT
(o FORM4_USER_AGENT), perche' il codice e' pubblico e il contatto no.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import requests

from .config import get as env_get

log = logging.getLogger(__name__)

ARCHIVES = "https://www.sec.gov/Archives"
SUBMISSIONS = "https://data.sec.gov/submissions"

#  La stessa directory che usa lo scanner. Condividerla non e' un accoppiamento:
#  e' un dettaglio di deployment, e su un clone pulito la cache nasce vuota.
DEFAULT_CACHE = ".edgar_cache"


class MissingUserAgent(RuntimeError):
    pass


def user_agent_from_env() -> str:
    """Nome e contatto da variabile d'ambiente. Mai da un letterale."""
    ua = env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")
    if not ua or "@" not in ua:
        raise MissingUserAgent(
            "EDGAR vuole un User-Agent con nome ed email reali. Imposta "
            "EDGAR_USER_AGENT='Nome Cognome tu@dominio' nell'ambiente o in un "
            "file .env -- vedi .env.example. `python -m edgar_llm.config` dice "
            "cosa vede."
        )
    return ua


class EdgarClient:
    def __init__(self, user_agent: str | None = None,
                 cache_dir: str | Path = DEFAULT_CACHE,
                 min_interval: float = 0.15, timeout: int = 30,
                 max_retries: int = 3):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or user_agent_from_env(),
            "Accept-Encoding": "gzip, deflate",
        })
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_call = 0.0
        self.stats = {"network": 0, "cache": 0, "backoff": 0, "fail": 0}

    # ---------- plumbing ----------

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_call
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last_call = time.monotonic()

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".cache")

    def get(self, url: str, use_cache: bool = True) -> str | None:
        cp = self._cache_path(url)
        if use_cache and cp.exists():
            self.stats["cache"] += 1
            return cp.read_text(encoding="utf-8", errors="replace")

        last_err = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                self.stats["network"] += 1
                r = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
                continue

            if r.status_code == 200:
                if use_cache:
                    cp.write_text(r.text, encoding="utf-8")
                return r.text
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429, 503):
                self.stats["backoff"] += 1
                wait = 2.0 * (attempt + 1)
                log.warning("HTTP %s su %s, attendo %.1fs", r.status_code, url, wait)
                time.sleep(wait)
                last_err = RuntimeError("HTTP {}".format(r.status_code))
                continue
            last_err = RuntimeError("HTTP {}".format(r.status_code))
            break

        self.stats["fail"] += 1
        log.error("Rinuncio su %s (%s)", url, last_err)
        return None

    def get_json(self, url: str, use_cache: bool = True) -> dict | None:
        txt = self.get(url, use_cache=use_cache)
        if txt is None:
            return None
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            log.error("JSON illeggibile da %s", url)
            return None

    # ---------- endpoint ----------

    def submissions(self, cik: str) -> dict | None:
        return self.get_json("{}/CIK{:010d}.json".format(SUBMISSIONS, int(cik)))

    def document(self, cik: str, accession: str, filename: str) -> str | None:
        """Il testo grezzo di un documento dentro la cartella di un deposito."""
        return self.get(document_url(cik, accession, filename))


def document_url(cik: str, accession: str, filename: str) -> str:
    return "{}/edgar/data/{}/{}/{}".format(
        ARCHIVES, int(cik), accession.replace("-", ""), filename)
