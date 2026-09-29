"""Client EODHD: una chiamata alla volta, limiti al minuto e al giorno con margine, ripetizioni, conteggio persistente.

- **Chiave**: aggiunta all'URL solo nel momento della richiesta. Tutto ciò che viene registrato (registro delle chiamate,
  manifest, eccezioni) usa `oscura()`, che la sostituisce con `***`.
- **Limiti**: il 90% di quelli del piano (`config.Limiti`). Al minuto: finestra mobile di 60 secondi, si aspetta. Al
  giorno: se la chiamata supererebbe il tetto, `BudgetEsaurito` e nessuna richiesta parte.
- **Conteggio**: registro append-only `<archivio>/eodhd/manifest/chiamate.jsonl`, una riga per richiesta HTTP partita
  (anche le ripetizioni: il fornitore le conta), con giorno UTC, endpoint, costo, stato HTTP. Le risposte 401, 403
  (endpoint fuori dal piano) e 404 (borsa o titolo inesistente) si registrano con costo 0: il fornitore non le addebita
  (misurato il 17-09-2026 col contatore di `user`, contro la documentazione che dà le 404 come addebitate). Il consumo **reale** si legge dal fornitore (`user`, costo 0) e si confronta con il registro.
- **Ripetizioni**: 429 e 5xx, tre tentativi con attesa crescente; 401, 402, 403, 404 tornano subito (sono risposte, non
  guasti: servono a classificare gli endpoint).

Solo libreria standard. Il trasporto è iniettabile per i test (nessuna chiamata reale nei test).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from market_data import registri
from market_data.config import Limiti

BASE = "https://eodhd.com/api/"
RIPETIBILI = frozenset({429, 500, 502, 503, 504})
NON_ADDEBITATI = frozenset({401, 403, 404})
TENTATIVI = 3
ATTESA_BASE = 2.0
TIMEOUT = 60


class BudgetEsaurito(RuntimeError):
    pass


@dataclass(frozen=True)
class Risposta:
    stato: int
    corpo: bytes
    url_oscurato: str


def oscura(testo: str) -> str:
    return re.sub(r"(api_token=)[^&\s]+", r"\1***", testo)


def trasporto_urllib(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "market-data/0.1 (uso personale)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""


class Registro:
    """Registro append-only delle chiamate partite; ricostruisce il consumo del giorno UTC alla partenza."""

    def __init__(self, percorso: Path):
        self.percorso = percorso
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        self._per_giorno: dict[str, int] = {}
        righe, _ = registri.leggi(percorso)                  # righe troncate da un'interruzione: saltate
        for r in righe:
            costo = 0 if r.get("stato") in NON_ADDEBITATI else int(r.get("costo") or 0)
            self._per_giorno[r["giorno"]] = self._per_giorno.get(r["giorno"], 0) + costo

    def usate(self, giorno: str) -> int:
        return self._per_giorno.get(giorno, 0)

    def scrivi(self, voce: dict) -> None:
        registri.appendi(self.percorso, voce)
        self._per_giorno[voce["giorno"]] = self.usate(voce["giorno"]) + int(voce["costo"])

    def allinea(self, giorno: str, usate_fornitore: int, quando: str) -> int:
        """Se il fornitore conta più chiamate del registro per il giorno, aggiunge una riga di rettifica (costo = differenza):
        il tetto locale segue il consumo reale. Restituisce la rettifica (0 se non serve)."""
        differenza = usate_fornitore - self.usate(giorno)
        if differenza > 0:
            self.scrivi({"quando": quando, "giorno": giorno, "endpoint": "rettifica-contatore-fornitore", "parametri": "",
                         "costo": differenza, "stato": 200, "tentativo": 0, "byte": 0})
        return max(0, differenza)


class Client:
    def __init__(self, chiave: str, archivio: Path, limiti: Limiti,
                 trasporto: Callable[[str], tuple[int, bytes]] = trasporto_urllib,
                 orologio: Callable[[], float] = time.monotonic, dormi: Callable[[float], None] = time.sleep,
                 adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        if not chiave:
            raise ValueError("chiave mancante")
        self._chiave = chiave
        self.limiti = limiti
        self.registro = Registro(archivio / "eodhd" / "manifest" / "chiamate.jsonl")
        self._trasporto, self._orologio, self._dormi, self._adesso = trasporto, orologio, dormi, adesso
        self._finestra: deque[float] = deque()

    def __repr__(self) -> str:                       # mai la chiave, nemmeno nei traceback
        return "Client(limiti={})".format(self.limiti)

    def usate_oggi(self) -> int:
        return self.registro.usate(self._adesso().date().isoformat())

    def _attendi_minuto(self) -> None:
        while True:
            t = self._orologio()
            while self._finestra and t - self._finestra[0] >= 60.0:
                self._finestra.popleft()
            if len(self._finestra) < self.limiti.minuto_utile:
                self._finestra.append(t)
                return
            self._dormi(60.0 - (t - self._finestra[0]) + 0.05)

    def get(self, endpoint: str, params: dict | None = None, costo: int = 1) -> Risposta:
        """GET di `BASE + endpoint`. `costo` = chiamate che il fornitore addebita per questa richiesta."""
        p = dict(params or {})
        p.setdefault("fmt", "json")
        percorso = urllib.parse.quote(endpoint.lstrip("/"), safe="/._-~%")
        url_pubblico = BASE + percorso + "?" + urllib.parse.urlencode(sorted(p.items()))
        url = url_pubblico + "&" + urllib.parse.urlencode({"api_token": self._chiave})
        for tentativo in range(1, TENTATIVI + 1):
            self._attendi_minuto()
            giorno = self._adesso().date().isoformat()          # dopo l'attesa: il giorno è quello dell'invio
            if self.registro.usate(giorno) + costo > self.limiti.giorno_utile:
                raise BudgetEsaurito("tetto del giorno {} raggiunto: {} + {} > {}".format(
                    giorno, self.registro.usate(giorno), costo, self.limiti.giorno_utile))
            try:
                stato, corpo = self._trasporto(url)
            except Exception as e:                              # anche IncompleteRead e InvalidURL; mai la chiave
                stato, corpo = 0, oscura("{}: {}".format(type(e).__name__, e)).encode()
            self.registro.scrivi({"quando": self._adesso().isoformat(timespec="seconds"), "giorno": giorno,
                                  "endpoint": endpoint, "parametri": oscura(urllib.parse.urlencode(sorted(p.items()))),
                                  "costo": 0 if stato in NON_ADDEBITATI else costo, "stato": stato,
                                  "tentativo": tentativo, "byte": len(corpo)})
            if stato not in RIPETIBILI and stato != 0:
                return Risposta(stato, corpo, url_pubblico)
            if tentativo < TENTATIVI:
                self._dormi(ATTESA_BASE * 2 ** (tentativo - 1))
        return Risposta(stato, corpo, url_pubblico)
