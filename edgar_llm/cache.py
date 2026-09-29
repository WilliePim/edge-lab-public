"""Cache delle estrazioni: un documento si paga una volta sola.

LA CHIAVE NON E' IL DOCUMENTO. E' `sha256(testo_inviato + prompt_version +
model)` — ADR-005. Con la chiave sul solo documento, cambiare il prompt e
rilanciare le evals avrebbe restituito i risultati del prompt vecchio, senza
una chiamata, e la regola «nessun prompt cambia senza rieseguire le evals»
sarebbe stata inapplicabile proprio mentre sembrava rispettata. Un'eval che non
chiama nulla passa sempre.

Due modi:

  RECORD   chiama l'API quando manca, e scrive.
  REPLAY   legge e basta; se manca, alza. E' il modo della CI: deterministico,
           senza chiave, a costo zero.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import get as env_get

RECORD = "record"
REPLAY = "replay"

DEFAULT_DIR = ".llm_cache"


class CacheMiss(KeyError):
    """Manca, e siamo in replay. Non e' un errore da nascondere."""


def mode_from_env() -> str:
    m = (env_get("EDGAR_LLM_MODE") or RECORD).strip().lower()
    return m if m in (RECORD, REPLAY) else RECORD


def key_for(sent_text: str, prompt_version: str, model: str) -> str:
    h = hashlib.sha256()
    #  I separatori impediscono che due componenti diversi si incollino in una
    #  stringa identica: ("ab", "c") e ("a", "bc") devono dare chiavi diverse.
    for part in (sent_text, prompt_version, model):
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()


class Cache:
    def __init__(self, directory: str | Path = DEFAULT_DIR, mode: str | None = None):
        self.dir = Path(directory)
        self.mode = mode or mode_from_env()
        self.stats = {"hit": 0, "miss": 0, "write": 0}

    def path(self, key: str) -> Path:
        #  Due livelli di sottodirectory: una cartella piatta con decine di
        #  migliaia di file e' lenta da elencare su ogni filesystem.
        return self.dir / key[:2] / key[2:4] / (key + ".json")

    def get(self, key: str):
        p = self.path(key)
        if p.exists():
            try:
                self.stats["hit"] += 1
                return json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                #  Un file corrotto e' un miss, non un crash: si riscrive.
                pass
        self.stats["miss"] += 1
        if self.mode == REPLAY:
            raise CacheMiss(
                "nessuna estrazione in cache per {} e il modo e' replay. "
                "Rilancia in record (EDGAR_LLM_MODE=record) con una chiave API."
                .format(key[:12]))
        return None

    def put(self, key: str, payload) -> Path:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                indent=1), encoding="utf-8")
        self.stats["write"] += 1
        return p
