"""Rate-limited SEC EDGAR client.

SEC requires a declared User-Agent (name + email) and caps traffic at ~10 req/s.
We stay well under. Responses are cached on disk because the 3-year insider
history walk re-fetches the same submission files constantly.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

ARCHIVES = "https://www.sec.gov/Archives"
DAILY_INDEX = "https://www.sec.gov/Archives/edgar/daily-index"
SUBMISSIONS = "https://data.sec.gov/submissions"


class EdgarClient:
    def __init__(
        self,
        user_agent: str,
        cache_dir: str | Path = ".edgar_cache",
        min_interval: float = 0.15,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a User-Agent like 'Nome Cognome nome@example.com'. "
                "Requests without one get blocked."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_call = 0.0
        #  What the run cost the SEC, and what the cache saved. A daily job
        #  that quietly doubles its request count is the thing that gets a
        #  User-Agent blocked, and nobody notices until the 403s arrive.
        self.stats = {"network": 0, "cache": 0, "backoff": 0, "fail": 0}

    # ---------- plumbing ----------

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_call
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last_call = time.monotonic()

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()[:24]
        return self.cache_dir / f"{h}.cache"

    def _leggi_cache(self, cp: Path) -> str | None:
        """Il corpo dalla cache, compresso o no, o None se non c'e'.

        Si scrive gzip (misurato: 19,5 GB di cache diventano ~1,7; la
        decompressione costa meno dell'apertura del file) e si leggono anche i
        file vecchi in chiaro, cosi' nessuna voce gia' scaricata si invalida.
        Si tenta la lettura invece di chiedere prima se il file esiste: due
        syscall per ogni colpo di cache, e i colpi sono decine di migliaia.
        """
        try:
            return gzip.decompress(cp.with_suffix(".cache.gz").read_bytes()).decode(
                "utf-8", errors="replace")
        except FileNotFoundError:
            pass
        except (OSError, EOFError) as e:                  # file troncato: si riscarica
            log.warning("cache illeggibile %s: %s", cp.name, e)
        try:
            return cp.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return None

    def get(self, url: str, use_cache: bool = True) -> str | None:
        """Return response text, or None on a persistent 404/failure."""
        cp = self._cache_path(url)
        if use_cache:
            corpo = self._leggi_cache(cp)
            if corpo is not None:
                self.stats["cache"] += 1
                return corpo

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
                    tmp = cp.with_suffix(".cache.tmp")
                    tmp.write_bytes(gzip.compress(r.text.encode("utf-8"), 6))
                    tmp.replace(cp.with_suffix(".cache.gz"))
                return r.text
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429, 503):
                # SEC throttling or an egress proxy blocking the domain
                wait = 2.0 * (attempt + 1)
                self.stats["backoff"] += 1
                log.warning("HTTP %s on %s, backing off %.1fs", r.status_code, url, wait)
                time.sleep(wait)
                last_err = RuntimeError(f"HTTP {r.status_code}")
                continue
            last_err = RuntimeError(f"HTTP {r.status_code}")
            break

        self.stats["fail"] += 1
        log.error("Giving up on %s (%s)", url, last_err)
        return None

    def get_json(self, url: str, use_cache: bool = True) -> dict | None:
        txt = self.get(url, use_cache=use_cache)
        if txt is None:
            return None
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            log.error("Bad JSON from %s", url)
            return None

    # ---------- endpoints ----------

    def daily_master_index(self, day) -> str | None:
        """master.YYYYMMDD.idx for one filing day. None if not a filing day.

        master.idx is pipe-delimited (CIK|Name|Form|Date|File); form.idx is
        space-padded and breaks on company names containing runs of spaces.
        """
        q = (day.month - 1) // 3 + 1
        url = f"{DAILY_INDEX}/{day.year}/QTR{q}/master.{day:%Y%m%d}.idx"
        # Don't cache today's index -- it fills in through the evening.
        return self.get(url, use_cache=day < _today())

    def submissions(self, cik: str) -> dict | None:
        """Full filing history for any CIK (issuer or reporting owner)."""
        return self.get_json(f"{SUBMISSIONS}/CIK{int(cik):010d}.json")

    def company_concept(self, cik: str, taxonomy: str, tag: str) -> dict | None:
        """XBRL facts for one concept, e.g. dei/EntityCommonStockSharesOutstanding.

        Used to measure realised dilution: share count now vs a year ago.
        """
        return self.get_json(
            f"https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{int(cik):010d}/{taxonomy}/{tag}.json"
        )

    def filing_index(self, cik: str, accession: str) -> dict | None:
        acc = accession.replace("-", "")
        return self.get_json(f"{ARCHIVES}/edgar/data/{int(cik)}/{acc}/index.json")

    def ownership_xml(self, cik: str, accession: str) -> str | None:
        """Locate and fetch the ownership XML inside a Form 3/4/5 filing folder."""
        idx = self.filing_index(cik, accession)
        if not idx:
            return None
        items = idx.get("directory", {}).get("item", [])
        candidates = [
            i["name"]
            for i in items
            if i["name"].lower().endswith(".xml")
            and not i["name"].lower().endswith("index.xml")
        ]
        if not candidates:
            return None
        # Prefer a file that looks like a primary ownership doc
        candidates.sort(key=lambda n: (0 if "form" in n.lower() or n.lower().startswith("wk") else 1, len(n)))
        acc = accession.replace("-", "")
        for name in candidates:
            txt = self.get(f"{ARCHIVES}/edgar/data/{int(cik)}/{acc}/{name}")
            if txt and "ownershipDocument" in txt:
                return txt
        return None


def submission_rows(client, cik: str) -> list:
    """Every filing a CIK has ever made: [{accession, form, filed}, ...].

    A submissions document holds only the recent filings inline; the rest spill
    into separate JSON shards listed under `filings.files`. Reading `recent`
    alone quietly truncates the history at a few hundred filings, which for an
    old filer means missing everything before it -- a BDC that elected status a
    decade ago has its N-54A in a shard, not in `recent`.

    A free function rather than a method so the duck-typed fakes throughout the
    test suite keep working: it needs only `submissions` and `get_json`, which
    they already provide.
    """
    subs = client.submissions(cik)
    if not subs:
        return []

    filings = subs.get("filings") or {}
    out: list = []

    def absorb(block: dict) -> None:
        forms = block.get("form", [])
        accs = block.get("accessionNumber", [])
        dates = block.get("filingDate", [])

        #  `form` is the spine: every filing has one, and the other columns are
        #  attributes of a row that already exists. Zipping all three would let
        #  a short or absent accession column silently drop every row -- which
        #  is how this refactor first broke four suites, since a caller asking
        #  only "which forms did this CIK file" does not need accessions at all.
        for i, form in enumerate(forms):
            out.append({
                "accession": accs[i] if i < len(accs) else "",
                "form": str(form or "").strip().upper(),
                "filed": dates[i] if i < len(dates) else "",
            })

    absorb(filings.get("recent") or {})
    for extra in filings.get("files") or []:
        name = (extra or {}).get("name")
        if not name:
            continue
        shard = client.get_json(f"{SUBMISSIONS}/{name}")
        if shard:
            absorb(shard)
    return out


def _today():
    from datetime import date

    return date.today()
