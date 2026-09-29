"""Livello grezzo: risposte API così come arrivano, compresse, mai modificate. Una cartella per giorno di download.

    <archivio>/eodhd/raw/<AAAA-MM-GG>/<endpoint>__<impronta dei parametri>.<json|csv>.gz
    <archivio>/eodhd/manifest/grezzo.jsonl     una riga per file

Riga del manifest: file (relativo all'archivio), endpoint, parametri (senza chiave), scaricato (UTC), stato HTTP, byte,
sha256 del corpo non compresso, righe (lunghezza della lista JSON, o righe CSV senza intestazione; None se non si sa).
**Ripartenza**: `gia_scaricato()` guarda il manifest per endpoint + parametri con stato 200; un file già presente non
si riscarica; uno scaricamento ripetuto nello stesso giorno crea un file nuovo (`__2`, `__3`), mai una
sovrascrittura. Scrittura atomica (file temporaneo, poi `os.replace`).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from market_data import registri
from market_data.eodhd.client import oscura


def _chiave(endpoint: str, params: dict) -> str:
    p = {k: v for k, v in params.items() if k != "api_token"}
    return endpoint.strip("/") + "?" + urllib.parse.urlencode(sorted(p.items()))


def _righe(corpo: bytes, fmt: str) -> int | None:
    """Righe di dati: elementi della lista JSON, della lista `data` di una busta JSON, righe CSV non vuote senza intestazione."""
    try:
        if fmt == "json":
            dati = json.loads(corpo)
            if isinstance(dati, list):
                return len(dati)
            if isinstance(dati, dict) and isinstance(dati.get("data"), list):
                return len(dati["data"])
            return 1 if dati else 0
        return max(0, sum(1 for riga in corpo.split(b"\n") if riga.strip()) - 1)
    except ValueError:
        return None


class Grezzo:
    def __init__(self, archivio: Path):
        self.archivio = archivio
        self.manifest = archivio / "eodhd" / "manifest" / "grezzo.jsonl"
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        self._ok: dict[str, dict] = {}
        self._storia: dict[str, list[dict]] = {}
        righe, self.righe_illeggibili = registri.leggi(self.manifest)   # righe troncate: saltate e contate
        for r in righe:
            if r.get("stato") == 200:
                self._ok[r["chiave"]] = r
                self._storia.setdefault(r["chiave"], []).append(r)

    def gia_scaricato(self, endpoint: str, params: dict) -> dict | None:
        return self._ok.get(_chiave(endpoint, params))

    def storia(self, voce: dict) -> list[dict]:
        """Tutte le versioni con stato 200 della stessa chiave, dalla più vecchia alla più recente."""
        return list(self._storia.get(voce["chiave"], [voce]))

    def leggi(self, voce: dict) -> bytes:
        return gzip.decompress((self.archivio / voce["file"]).read_bytes())

    def salva(self, endpoint: str, params: dict, stato: int, corpo: bytes, adesso: datetime | None = None) -> dict:
        adesso = adesso or datetime.now(timezone.utc)
        fmt = params.get("fmt", "json")
        chiave = _chiave(endpoint, params)
        impronta = hashlib.sha256(chiave.encode()).hexdigest()[:16]
        nome = re.sub(r"[^A-Za-z0-9._-]+", "_", endpoint.strip("/"))[:120]
        cartella = Path("eodhd") / "raw" / adesso.date().isoformat()
        rel = cartella / "{}__{}.{}.gz".format(nome, impronta, fmt)
        n = 2
        while (self.archivio / rel).exists():            # mai sovrascrivere: un nuovo scaricamento è un file nuovo
            rel = cartella / "{}__{}__{}.{}.gz".format(nome, impronta, n, fmt)
            n += 1
        dest = self.archivio / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(gzip.compress(corpo))
        os.replace(tmp, dest)
        voce = {"chiave": oscura(chiave), "file": rel.as_posix(), "endpoint": endpoint,
                "parametri": {k: v for k, v in params.items() if k != "api_token"},
                "scaricato": adesso.isoformat(timespec="seconds"), "stato": stato, "byte": len(corpo),
                "sha256": hashlib.sha256(corpo).hexdigest(), "righe": _righe(corpo, fmt) if stato == 200 else None}
        registri.appendi(self.manifest, voce)
        if stato == 200:
            self._ok[chiave] = voce
            self._storia.setdefault(chiave, []).append(voce)
        return voce
