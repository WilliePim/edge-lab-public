"""Fonti esterne per i controlli della fase 4: EDGAR (SEC) e Yahoo. Nessuna dipende dall'archivio EODHD per funzionare.

**EDGAR**: User-Agent obbligatorio da `EDGAR_USER_AGENT` (nome ed email); 0,15 s fra le richieste; risposte in cache fuori
dal repo (`<archivio>/eodhd/edgar_cache/`), compresse con gzip (gli elenchi dei depositi di 10.000 società sarebbero
4-6 GB in chiaro). I documenti depositati non cambiano e restano in cache; gli elenchi dei depositi (`submissions`)
cambiano e la loro cache vale 7 giorni (per i controlli bastano: date di quotazione, split e cancellazioni passati).
- `depositi(cik)`: tutti i depositi (anche le pagine vecchie) come (data, modulo, voci, accession, documento). **Se una
  richiesta fallisce, anche una sola pagina, restituisce `None`**: un elenco incompleto non è «nessun deposito».
- `fine_quotazione(depositi)`: data del Form 25 o del Form 15 più recente, se c'è;
- `ultimo_periodico(depositi)`: data dell'ultimo bilancio periodico (10-K, 10-Q, 20-F, 40-F e varianti);
- `data_ipo(depositi)`: primo prospetto d'offerta 424B1 o 424B4 preceduto da un S-1 o F-1 nei due anni prima, senza bilanci
  periodici né depositi di società successora (8-K12B, 8-K12G3, S-4) prima di quel S-1/F-1: la quotazione di una società
  che prima non era pubblica. Altrimenti `None` (data non ricavabile);
- `prove_split(cik, giorno, rapporto)`: 8-K dal 60° giorno prima al 30° dopo il salto con un rapporto scritto («1-for-10»,
  «one-for-ten», «2-for-1») coerente con il salto (±5%). Una menzione senza rapporto coerente non basta; un 8-K che non si
  riesce a leggere rende la verifica «non verificabile».

**Yahoo** (`yfinance`, già usato in edge-lab): chiusura rettificata per il confronto con EODHD.
"""
from __future__ import annotations

import datetime as dt
import difflib
import gzip
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from market_data import config as C

SEC = "https://data.sec.gov/submissions/CIK{:010d}.json"
ARCHIVIO_SEC = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
DEPOSITO_INTERO = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{num}.txt"
PAUSA = 0.15
GIORNI_CACHE_ELENCHI = 7
FORME_FINE = ("25", "25-NSE", "15-12B", "15-12G", "15-15D")
PERIODICI = ("10-K", "10-Q", "20-F", "40-F", "10-KSB", "10-QSB", "10-K405", "10-KT", "10-QT", "10-12G", "10-12B")
SUCCESSORE = ("8-K12B", "8-K12G3", "S-4", "S-4/A", "F-4")
REGISTRAZIONE = ("S-1", "S-1/A", "F-1", "F-1/A", "SB-2", "SB-2/A")
PROSPETTO_IPO = ("424B1", "424B4")
NUMERI = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "twelve": 12, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
          "one hundred": 100, "hundred": 100, "two hundred": 200, "two hundred fifty": 250, "one thousand": 1000}
_NUM = r"(\d+(?:\.\d+)?|one hundred|two hundred fifty|two hundred|one thousand|twenty-five|" + "|".join(
    sorted((k for k in NUMERI if " " not in k and k != "twenty-five"), key=len, reverse=True)) + ")"
RAPPORTO_TESTO = re.compile(_NUM + r"\s*[-‐-― ]\s*for\s*[-‐-― ]\s*" + _NUM, re.IGNORECASE)
PAROLE_SPLIT = re.compile(r"reverse\s+(stock\s+)?split|stock\s+split|share\s+consolidation|forward\s+split|"
                          r"split\s+of\s+(our|the)\s+(outstanding\s+)?(common\s+)?(stock|shares)", re.IGNORECASE)
SUFFISSI_YAHOO = {"US": "", "LSE": ".L", "XETRA": ".DE", "F": ".F", "PA": ".PA", "AS": ".AS", "BR": ".BR", "LS": ".LS",
                  "SW": ".SW", "MC": ".MC", "VI": ".VI", "ST": ".ST", "HE": ".HE", "CO": ".CO", "OL": ".OL",
                  "TO": ".TO", "V": ".V", "AU": ".AX", "HK": ".HK"}


def numero(testo: str) -> float | None:
    t = testo.lower().strip()
    try:
        return float(t)
    except ValueError:
        return NUMERI.get(t)


def rapporti_nel_testo(testo: str) -> list[float]:
    """Rapporti «A-for-B» vicini a una parola di split, come fattore sul prezzo B / A (1-for-10 → 10; 2-for-1 → 0,5)."""
    out = []
    for m in RAPPORTO_TESTO.finditer(testo):
        intorno = testo[max(0, m.start() - 300):m.end() + 300]
        if not PAROLE_SPLIT.search(intorno):
            continue
        a, b = numero(m.group(1)), numero(m.group(2))
        if a and b and a != b:
            out.append(b / a)
    return out


class Edgar:
    def __init__(self, archivio: Path, user_agent: str | None = None, trasporto=None, dormi=time.sleep,
                 oggi=lambda: dt.date.today()):
        self.ua = user_agent or C.get("EDGAR_USER_AGENT")
        if not self.ua or "@" not in self.ua:
            raise C.ConfigError("EDGAR_USER_AGENT mancante (nome ed email, richiesti dalla SEC)")
        self.cache = archivio / "eodhd" / "edgar_cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self._trasporto = trasporto or self._urllib
        self._dormi, self._oggi = dormi, oggi
        self._ultimo = 0.0
        self.chiamate = 0
        self.fallite = 0
        self.byte_scritti = 0            # quanto e' cresciuta la cache in questa esecuzione

    def _urllib(self, url: str) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception:                                        # rete: nessuna risposta
            return 0, b""

    def get(self, url: str, un_giorno: bool = False) -> bytes | None:
        """Corpo della risposta, o None se la richiesta fallisce dopo 3 tentativi (o se la SEC risponde 404). Con
        `un_giorno` (elenchi che cambiano) la cache vale `GIORNI_CACHE_ELENCHI` giorni."""
        f = self.cache / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".bin.gz")
        if f.exists():
            eta = (self._oggi() - dt.date.fromtimestamp(f.stat().st_mtime)).days
            if not un_giorno or eta < GIORNI_CACHE_ELENCHI:
                try:
                    return gzip.decompress(f.read_bytes())
                except (OSError, EOFError):                       # file troncato: si riscarica
                    pass
        for tentativo in range(3):
            attesa = PAUSA - (time.monotonic() - self._ultimo)
            if attesa > 0:
                self._dormi(attesa)
            self._ultimo = time.monotonic()
            stato, corpo = self._trasporto(url)
            self.chiamate += 1
            if stato == 200:
                tmp = f.with_suffix(".tmp")
                compresso = gzip.compress(corpo)
                tmp.write_bytes(compresso)
                tmp.replace(f)
                self.byte_scritti += len(compresso)
                return corpo
            if stato in (403, 429, 503, 0):
                self._dormi(2.0 * (tentativo + 1))
                continue
            break
        self.fallite += 1
        return None

    def submissions(self, cik: str | int) -> dict | None:
        if not str(cik).strip().isdigit():                  # CIK vuoto o non numerico: nessuna richiesta
            return None
        corpo = self.get(SEC.format(int(cik)), un_giorno=True)
        try:
            return json.loads(corpo) if corpo else None
        except ValueError:
            return None

    def depositi(self, cik: str | int) -> tuple[dict | None, list[tuple] | None]:
        """(submissions, depositi ordinati) o (None, None) se una qualsiasi richiesta fallisce: elenco incompleto = ignoto."""
        d = self.submissions(cik)
        if not d:
            return None, None
        blocchi = [d.get("filings", {}).get("recent", {})]
        for extra in d.get("filings", {}).get("files", []) or []:
            corpo = self.get("https://data.sec.gov/submissions/" + extra["name"], un_giorno=True)
            try:
                blocchi.append(json.loads(corpo))
            except (TypeError, ValueError):
                return d, None
        out = []
        for b in blocchi:
            n = len(b.get("form", []))
            col = lambda k: (b.get(k) or [""] * n) if len(b.get(k) or []) == n else [""] * n  # noqa: E731
            out += list(zip(col("filingDate"), col("form"), col("items"), col("accessionNumber"), col("primaryDocument")))
        return d, sorted(out)

    def annuali(self, cik: str | int) -> list[tuple] | None:
        """I 10-K con la data di chiusura dell'esercizio: [(deposito, forma, esercizio, accession, documento)].

        `depositi()` non porta `reportDate`, che qui serve per scegliere il bilancio il cui esercizio contiene il
        salto. None se le submissions non si leggono: elenco incompleto = ignoto, come in `depositi()`."""
        d = self.submissions(cik)
        if not d:
            return None
        blocchi = [d.get("filings", {}).get("recent", {})]
        for extra in d.get("filings", {}).get("files", []) or []:
            corpo = self.get("https://data.sec.gov/submissions/" + extra["name"], un_giorno=True)
            try:
                blocchi.append(json.loads(corpo))
            except (TypeError, ValueError):
                return None
        out = []
        for b in blocchi:
            n = len(b.get("form", []))
            col = lambda k: (b.get(k) or [""] * n) if len(b.get(k) or []) == n else [""] * n  # noqa: E731
            for deposito, forma, esercizio, acc, doc in zip(col("filingDate"), col("form"), col("reportDate"),
                                                            col("accessionNumber"), col("primaryDocument")):
                if forma in ("10-K", "10-K405", "10-KSB", "10-K/A"):
                    out.append((deposito, forma, esercizio, acc, doc))
        return sorted(out)

    def documento(self, cik: str | int, acc: str, doc: str) -> bytes | None:
        """Il documento principale del deposito; per i depositi vecchi, che non ne dichiarano uno, il file
        completo `<accession>.txt`."""
        if doc:
            return self.get(ARCHIVIO_SEC.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc))
        return self.get(DEPOSITO_INTERO.format(cik=int(cik), acc=acc.replace("-", ""), num=acc))

    def prove_split(self, cik: str | int, giorno: dt.date, rapporto_tipico: float, depositi: list[tuple] | None = None) -> dict:
        if depositi is None:
            _d, depositi = self.depositi(cik)
            if depositi is None:
                return {"esito": "non verificabile: EDGAR non leggibile"}
        da, a = (giorno - dt.timedelta(days=60)).isoformat(), (giorno + dt.timedelta(days=30)).isoformat()
        otto_k = [x for x in depositi if x[1].startswith("8-K") and da <= x[0] <= a]
        illeggibili, menzioni = 0, []
        for data, forma, voci, acc, doc in otto_k:
            corpo = self.get(ARCHIVIO_SEC.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc)) if doc else None
            if corpo is None:
                illeggibili += 1
                continue
            testo = " ".join(re.sub(r"<[^>]+>", " ", corpo.decode("utf-8", "replace")).split())
            for k_testo in rapporti_nel_testo(testo):
                menzioni.append(k_testo)
                if abs(math.log(k_testo) - math.log(rapporto_tipico)) <= math.log(1.05):
                    m = RAPPORTO_TESTO.search(testo)
                    return {"esito": "split trovato", "data": data, "modulo": forma, "voci": voci, "accession": acc,
                            "rapporto_nel_testo": round(k_testo, 4),
                            "estratto": testo[max(0, m.start() - 120):m.end() + 120] if m else ""}
        if illeggibili:
            return {"esito": "non verificabile: {} 8-K non leggibili".format(illeggibili), "8k_nella_finestra": len(otto_k)}
        if menzioni:
            return {"esito": "rapporto nel testo diverso dal salto", "rapporti_nel_testo": [round(x, 4) for x in menzioni],
                    "8k_nella_finestra": len(otto_k)}
        return {"esito": "nessun 8-K con split" if otto_k else "nessun 8-K nella finestra", "8k_nella_finestra": len(otto_k)}


def fine_quotazione(depositi: list[tuple]) -> str | None:
    date = [x[0] for x in depositi if x[1] in FORME_FINE]
    return max(date) if date else None


def ultimo_periodico(depositi: list[tuple]) -> str | None:
    date = [x[0] for x in depositi if x[1] in PERIODICI]
    return max(date) if date else None


def data_ipo(depositi: list[tuple]) -> str | None:
    for data, forma, *_ in depositi:
        if forma not in PROSPETTO_IPO:
            continue
        inizio = (dt.date.fromisoformat(data) - dt.timedelta(days=730)).isoformat()
        registrazioni = [x[0] for x in depositi if x[1] in REGISTRAZIONE and inizio <= x[0] <= data]
        if not registrazioni:
            return None                                   # il primo prospetto non segue una registrazione: non è un'IPO
        prima_reg = min(registrazioni)
        if any(x[1] in PERIODICI + SUCCESSORE and x[0] < prima_reg for x in depositi):
            return None                                   # società già pubblica o successora: non è una prima quotazione
        return data
    return None


def nomi_simili(a: str, b: str) -> float:
    def norm(s):
        s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
        s = re.sub(r"\b(inc|corp|corporation|co|ltd|plc|holdings?|group|the|company|llc|lp|sa|ag|nv)\b", " ", s)
        return " ".join(s.split())
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def simbolo_yahoo(codice: str, borsa: str) -> str | None:
    if borsa not in SUFFISSI_YAHOO:
        return None
    base = codice.replace(".", "-") if borsa == "US" else codice
    return base + SUFFISSI_YAHOO[borsa]


def chiusure_yahoo(simboli: list[str], inizio: str) -> dict[str, dict]:
    """{simbolo yahoo: {data ISO: {"close": chiusura rettificata solo per gli split, "adj": rettificata anche per i
    dividendi}}}; simboli senza dati assenti."""
    import yfinance as yf
    out = {}
    for i in range(0, len(simboli), 25):
        gruppo = simboli[i:i + 25]
        df = yf.download(gruppo, start=inizio, auto_adjust=False, actions=False, progress=False, group_by="ticker", threads=False)
        for s in gruppo:
            try:
                sub = df[s] if len(gruppo) > 1 or getattr(df.columns, "nlevels", 1) > 1 else df
                chiuse, rett = sub["Close"], sub["Adj Close"]
            except (KeyError, TypeError):
                continue
            righe = {d.strftime("%Y-%m-%d"): {"close": float(c), "adj": float(a)} for d, c, a in zip(sub.index, chiuse, rett)
                     if c == c and a == a}                                    # c == c: non NaN
            if righe:
                out[s] = righe
    return out
