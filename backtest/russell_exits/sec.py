"""Russell 2000, uscite verso il basso — accesso a EDGAR con tetto di chiamate proprio.

Stesso client del repo (`form4_scanner/edgar.py::EdgarClient`: cache `.edgar_cache`, 0,15 s fra le chiamate, User-Agent
da `EDGAR_USER_AGENT`), contatore persistente in `backtest/russell_exits/edgar_calls.json`. Le chiamate servite dalla
cache non contano.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / ".edgar_cache"
CALLS = HERE / "edgar_calls.json"
TETTO = 300                      # fase 0: elenchi e documenti dei fondi (ADR del Russell)


def cache_path(url):
    return CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".cache")


class Budget:
    def __init__(self, tetto=TETTO, calls: Path = CALLS):
        from edgar_llm.config import get as env_get
        from form4_scanner.edgar import EdgarClient

        ua = env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")
        if not ua or "@" not in ua:
            raise SystemExit("serve EDGAR_USER_AGENT con nome ed email")
        self.client = EdgarClient(ua, cache_dir=CACHE, min_interval=0.15)
        self.tetto = tetto
        self.calls = Path(calls)
        self.stato = json.loads(self.calls.read_text(encoding="utf-8")) if self.calls.exists() else {"network": 0}
        self.usate = self.stato["network"]
        self.negate = 0

    def get(self, url):
        """Testo, o None. None anche quando il tetto impedirebbe la chiamata."""
        if not (cache_path(url).exists() or cache_path(url).with_suffix(".cache.gz").exists()) \
                and self.usate >= self.tetto:
            self.negate += 1
            return None
        prima = self.client.stats["network"]
        txt = self.client.get(url)
        self.usate += self.client.stats["network"] - prima
        self.stato.update({"network": self.usate, "tetto": self.tetto})
        self.calls.write_text(json.dumps(self.stato), encoding="utf-8")
        return txt
