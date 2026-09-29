"""Configurazione di market-data: percorso dell'archivio, chiave API e limiti del piano, solo da variabili d'ambiente.

Precedenza: variabile già impostata nell'ambiente, poi `.env` alla radice di edge-lab, il repo che contiene market-data/
(che non la sovrascrive mai).

| variabile | obbligatoria | significato |
|---|---|---|
| `MARKET_DATA_DIR` | sì | radice dell'archivio; **deve stare fuori da qualsiasi repo git** |
| `EODHD_API_KEY` | per scaricare | chiave EOD Historical Data; non compare mai in messaggi, log o manifest |
| `EODHD_DAILY_LIMIT` | no | chiamate al giorno del piano (100.000) |
| `EODHD_MINUTE_LIMIT` | no | chiamate al minuto del piano (1.000) |
| `MARKET_DATA_MEMORIA_QUOTA` | no | quota della RAM che DuckDB puo' usare (0,65) |
| `MARKET_DATA_MEMORIA_GB` | no | tetto assoluto, se si preferisce ai punti percentuali |
| `MARKET_DATA_THREADS` | no | thread di DuckDB (meta' dei processori, almeno 2) |

Il client usa il 90% di ciascun limite (margine del 10% chiesto dall'utente).

**Il tetto di memoria non e' un dettaglio di prestazioni.** Senza, DuckDB si prende l'80% della RAM della
macchina: su 16 GB sono quasi 13, e una scansione dell'archivio intero lascia il computer senza memoria mentre
lavora. La quota predefinita e' il 65%, scelta dall'utente il 21-09-2026 perche' il computer serve anche ad altro.
Le connessioni si aprono tutte con `applica_limiti`.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARGINE = 0.10
MEMORIA_QUOTA = 0.65            # quota della RAM per DuckDB; il resto serve al resto del computer
MEMORIA_GB_SENZA_MISURA = 4     # se la RAM della macchina non si ricava, un tetto prudente e basta


class ConfigError(RuntimeError):
    pass


def leggi_env(percorso: Path) -> dict[str, str]:
    """Coppie NOME=valore di un file `.env` (commenti e righe vuote ignorati, virgolette tolte)."""
    out: dict[str, str] = {}
    if not percorso.is_file():
        return out
    for riga in percorso.read_text(encoding="utf-8", errors="replace").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        nome, valore = riga.split("=", 1)
        out[nome.strip()] = valore.strip().strip("'\"")
    return out


def get(nome: str, default: str | None = None, env_file: Path | None = None) -> str | None:
    valore = os.environ.get(nome)
    if valore:
        return valore
    valore = leggi_env(env_file or REPO_ROOT / ".env").get(nome)
    return valore if valore else default


def repo_git_che_contiene(percorso: Path) -> Path | None:
    """La cartella di lavoro git che contiene `percorso` (anche se il percorso non esiste ancora), o None."""
    for p in (percorso, *percorso.parents):
        if (p / ".git").exists():
            return p
    return None


def archivio(valore: str | None = None, env_file: Path | None = None) -> Path:
    """Radice dell'archivio. Rifiuta un percorso mancante, relativo, o dentro un repo git (questo o un altro)."""
    grezzo = valore if valore is not None else get("MARKET_DATA_DIR", env_file=env_file)
    if not grezzo:
        raise ConfigError("MARKET_DATA_DIR non impostata: indica una cartella fuori dal repo (vedi .env.example)")
    p = Path(os.path.expandvars(grezzo)).expanduser()
    if not p.is_absolute():
        raise ConfigError("MARKET_DATA_DIR deve essere un percorso assoluto")
    p = p.resolve()
    if p == REPO_ROOT or REPO_ROOT in p.parents:
        raise ConfigError("MARKET_DATA_DIR sta dentro il repo: i dati non devono poter finire su git")
    repo = repo_git_che_contiene(p)
    if repo is not None:
        raise ConfigError("MARKET_DATA_DIR sta dentro un repo git ({}): scegli una cartella fuori".format(repo))
    return p


def chiave_eodhd(env_file: Path | None = None) -> str:
    k = get("EODHD_API_KEY", env_file=env_file)
    if not k:
        raise ConfigError("EODHD_API_KEY non impostata (vedi .env.example)")
    return k


@dataclass(frozen=True)
class Limiti:
    al_giorno: int
    al_minuto: int
    margine: float = MARGINE

    @property
    def giorno_utile(self) -> int:
        return int(self.al_giorno * (1 - self.margine))

    @property
    def minuto_utile(self) -> int:
        return max(1, int(self.al_minuto * (1 - self.margine)))


def limiti(env_file: Path | None = None) -> Limiti:
    def intero(nome, default):
        v = get(nome, env_file=env_file)
        try:
            return int(v) if v else default
        except ValueError as e:
            raise ConfigError("{} non è un intero".format(nome)) from e
    return Limiti(intero("EODHD_DAILY_LIMIT", 100_000), intero("EODHD_MINUTE_LIMIT", 1_000))


def memoria_totale_gb() -> float | None:
    """La RAM fisica della macchina, o None se non si ricava (allora vale un tetto fisso e prudente)."""
    try:
        if sys.platform == "win32":
            import ctypes

            class Stato(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            stato = Stato()
            stato.dwLength = ctypes.sizeof(Stato)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stato)):
                return None
            return stato.ullTotalPhys / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (AttributeError, OSError, ValueError):
        return None


def tetto_memoria_gb() -> float:
    """Quanti GB puo' usare DuckDB: la quota della RAM, o il tetto assoluto se l'ambiente lo impone."""
    assoluto = get("MARKET_DATA_MEMORIA_GB")
    if assoluto:
        try:
            return float(assoluto)
        except ValueError:
            pass
    quota = MEMORIA_QUOTA
    try:
        quota = float(get("MARKET_DATA_MEMORIA_QUOTA") or quota)
    except ValueError:
        pass
    totale = memoria_totale_gb()
    return round(totale * quota, 1) if totale else MEMORIA_GB_SENZA_MISURA


def threads() -> int:
    """Quanti thread: meta' dei processori, almeno due. Ogni thread ha i suoi buffer, quindi conta anche per la RAM."""
    try:
        return max(1, int(get("MARKET_DATA_THREADS")))
    except (TypeError, ValueError):
        return max(2, (os.cpu_count() or 4) // 2)


def applica_limiti(con, memoria_gb: float | None = None, n_threads: int | None = None):
    """Mette a una connessione DuckDB il tetto di memoria, i thread e la cartella temporanea dell'archivio.

    Senza tetto DuckDB prende l'80% della RAM e una scansione dell'archivio intero (227 milioni di barre) lascia il
    computer senza memoria. Con il tetto, quello che non ci sta va su disco: piu' lento, ma la macchina resta
    usabile mentre lavora. La cartella temporanea sta nell'archivio e non accanto al catalogo, cosi' lo spazio non
    dipende da come DuckDB lo calcola su un file aperto in sola lettura."""
    memoria = tetto_memoria_gb() if memoria_gb is None else memoria_gb
    n = threads() if n_threads is None else n_threads
    con.execute("SET memory_limit = '{:g}GB'".format(memoria))
    con.execute("SET threads = {:d}".format(n))
    con.execute("SET preserve_insertion_order = false")
    try:
        tmp = archivio() / "duckdb_tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        con.execute("SET temp_directory = '{}'".format(str(tmp).replace("'", "''")))
        libero = shutil.disk_usage(tmp).free / 1024 ** 3
        #  Meta' dello spazio libero, e comunque non piu' del doppio della memoria: quello che DuckDB non tiene in
        #  RAM finisce qui, e su un disco stretto riempirlo fermerebbe ben altro che questa scansione.
        con.execute("SET max_temp_directory_size = '{:g}GB'".format(max(1.0, min(memoria * 2, libero / 2))))
    except (ConfigError, OSError):
        pass                                              # senza archivio configurato resta la temporanea di default
    return con
