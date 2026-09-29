"""Download in massa (fase 2 confermata dall'utente il 17-09-2026): piano per blocco, ripartenza, controlli.

## Blocchi e ordine

1. **USA**: azioni ordinarie ed ETF, attivi e delistati, compresi OTC; indici principali e VIX; Tesoro USA; mappatura degli
   identificativi (CUSIP, ISIN, CIK).
2. **Europa**: Stoccolma, Helsinki, Copenaghen, Oslo, Londra, Xetra, Francoforte, Parigi, Amsterdam, Bruxelles, Lisbona,
   Svizzera, Madrid, Vienna (Milano non disponibile); indici per paese; cambi contro euro e dollaro.
   **Francoforte**: solo titoli con ISIN tedesco (DE) il cui ISIN non è già su Xetra (per un titolo attivo: fra gli attivi
   di Xetra; per un delistato: in una delle due liste di Xetra); quelli senza ISIN si saltano e si contano.
3. **Altri**: Toronto, TSX Venture, Australia, Hong Kong (Tokyo non disponibile); indici principali.

Per titolo, 3 chiamate: prezzi giornalieri in **CSV**, dividendi e split in **JSON**. Risposte nel livello grezzo
compresso (`store/raw.py`), mai sovrascritte.

## Ripartenza

Il piano di un blocco si congela al primo avvio in `manifest/piano_<blocco>.json`. Ogni compito ha un esito in
`manifest/esiti_<blocco>.jsonl`: `ok`, `vuoto` (risposta 200 senza righe), `definitivo` (404: borsa o titolo inesistente,
non si ripete), `temporaneo` (rete, 429, 5xx dopo i tentativi; 401 e 403 isolati: si ripetono). Al riavvio l'esito di un
compito già nel livello grezzo si ricalcola dal grezzo, non da una riga vecchia. A fine blocco una ripassata dei temporanei.
Un solo download alla volta (`manifest/download.lock`).

## Fermate automatiche (decisione dell'utente)

- **Spazio**: prima di ogni gruppo di titoli, spazio libero < 1,2 × stima dello spazio ancora necessario (grezzo che manca
  più tutte le tabelle Parquet) + 5 GB → fermo.
- **Fallimenti**: in un blocco, compiti falliti (definitivi più temporanei) oltre il **2%** dei compiti eseguiti → fermo.
  Controllato dopo almeno 1.500 compiti e a fine blocco. Prima di contare un errore di rete o del fornitore come fallimento
  si riprova fino a 5 volte a un minuto di distanza.
- **Autorizzazione**: 20 risposte 401 o 403 di fila → fermo (chiave o abbonamento, non singoli titoli).
- **Contatore del fornitore non leggibile** 3 volte di fila → fermo (senza il consumo reale il tetto non si controlla).
- **File `manifest/STOP`**: se esiste, il download si ferma al compito successivo.
- **Tetto giornaliero**: non è una fermata; al tetto locale, alla risposta 402 del fornitore o al contatore del fornitore
  sopra il tetto si aspetta la mezzanotte UTC e si riprende. Il contatore del fornitore si legge all'inizio di ogni blocco e
  ogni 1.000 chiamate partite; se conta più del registro, il registro si allinea.

Stato leggibile in `manifest/stato_download.json`; registro in `manifest/download.log`.

    .venv/Scripts/python.exe -m market_data.eodhd.download --blocchi 1,2,3
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from market_data import config as C
from market_data import registri
from market_data.eodhd.client import BudgetEsaurito, Client
from market_data.store.raw import Grezzo

TIPI = ("Common Stock", "ETF")
BLOCCHI = {
    "1": {"nome": "USA", "borse": ("US",)},
    "2": {"nome": "Europa", "borse": ("ST", "HE", "CO", "OL", "LSE", "XETRA", "F", "PA", "AS", "BR", "LS", "SW", "MC", "VI")},
    "3": {"nome": "Altri", "borse": ("TO", "V", "AU", "HK")},
}
#  Stima della fase 2 (verificata): GB di grezzo e di Parquet per blocco, e titoli su cui è fatta.
STIMA = {"1": (1.82, 2.04, 59_785), "2": (2.57, 2.90, 49_790), "3": (0.59, 0.65, 16_284)}
INDICI = {
    "1": ("GSPC", "DJI", "IXIC", "NDX", "VIX", "NYA", "MID", "SML", "RUT"),
    #  Regno Unito: il fornitore non ha il FTSE 100; si usano i Cboe UK 100 e UK 250 (versione di prezzo)
    "2": ("GDAXI", "FCHI", "AEX", "BFX", "PSI20", "IBEX", "ATX", "SSMI", "OMXS30", "OMXH25", "OMXC25", "OBX", "SX5E",
          "BUK100P", "BUK250P", "MDAXI", "SDAXI", "STOXX50E"),
    "3": ("GSPTSE", "AXJO", "AORD", "HSI", "N225", "TOPX"),
}
VALUTE = ("SEK", "NOK", "DKK", "GBP", "CHF", "CAD", "AUD", "HKD", "JPY")
ANNI_TESORO = range(1990, dt.date.today().year + 1)
CURVE_TESORO = ("yield-rates", "bill-rates", "long-term-rates", "real-yield-rates")
SOGLIA_FALLIMENTI = 0.02
MINIMO_COMPITI = 1_500
MARGINE_SPAZIO = 5 * 1024 ** 3
FATTORE_SPAZIO = 1.2
GRUPPO = 200
TETTO_PAGINE_ID = 500
DEFINITIVI = frozenset({404})
AUTORIZZAZIONE = frozenset({401, 403})
TETTO_FORNITORE = 402
MAX_AUTORIZZAZIONE_DI_FILA = 20
RIPROVE_RETE, PAUSA_RETE = 5, 60.0
MAX_CONTATORE_ILLEGGIBILE = 3
OGNI_CHIAMATE_CONTATORE = 1_000


@dataclass(frozen=True)
class Titolo:
    borsa: str
    codice: str
    tipo: str
    stato: str               # "attivo" o "delistato"
    isin: str
    nome: str
    valuta: str


@dataclass(frozen=True)
class Compito:
    endpoint: str
    params: tuple            # coppie ordinate, per poter stare in un insieme
    costo: int
    tabella: str             # prezzi, dividendi, split, indici, cambi, tesoro, identificativi

    def parametri(self) -> dict:
        return dict(self.params)


def q(codice: str) -> str:
    return urllib.parse.quote(codice, safe=".-_")


# ------------------------------------------------------------------ piano --
def titoli_da_liste(borsa: str, attivi: list[dict], delistati: list[dict], tipi=TIPI) -> list[Titolo]:
    """Titoli dei tipi scelti; un codice presente in tutte e due le liste vale una volta (come attivo)."""
    visti, out = set(), []
    for righe, stato in ((attivi, "attivo"), (delistati, "delistato")):
        for r in righe:
            if r.get("Type") not in tipi or not r.get("Code") or r["Code"] in visti:
                continue
            visti.add(r["Code"])
            out.append(Titolo(borsa, r["Code"], r["Type"], stato, r.get("Isin") or "", r.get("Name") or "", r.get("Currency") or ""))
    return out


def isin_xetra(lista_attivi: list[dict], lista_delistati: list[dict]) -> tuple[set[str], set[str]]:
    """(ISIN degli attivi di Xetra, ISIN di tutte e due le liste di Xetra)."""
    attivi = {(r.get("Isin") or "").upper() for r in lista_attivi if r.get("Isin")}
    return attivi, attivi | {(r.get("Isin") or "").upper() for r in lista_delistati if r.get("Isin")}


def motivo_esclusione_francoforte(isin: str, stato: str, xetra_attivi: set[str], xetra_tutti: set[str]) -> str | None:
    if not isin:
        return "senza ISIN"
    if not isin.upper().startswith("DE"):
        return "ISIN non tedesco"
    if isin.upper() in (xetra_attivi if stato == "attivo" else xetra_tutti):
        return "ISIN tedesco già su Xetra"
    return None


def filtro_francoforte(titoli: list[Titolo], xetra_attivi: set[str], xetra_tutti: set[str] | None = None) -> tuple[list[Titolo], dict]:
    """Solo ISIN tedeschi non già su Xetra (un titolo attivo di Francoforte si confronta con gli attivi di Xetra: se su Xetra
    è delistato, a Francoforte si continua a scambiare). Conteggi di ciò che si salta."""
    xetra_tutti = xetra_attivi if xetra_tutti is None else xetra_tutti
    conti = {"senza ISIN": 0, "ISIN non tedesco": 0, "ISIN tedesco già su Xetra": 0, "tenuti": 0}
    tenuti = []
    for t in titoli:
        motivo = motivo_esclusione_francoforte(t.isin, t.stato, xetra_attivi, xetra_tutti)
        conti[motivo or "tenuti"] += 1
        if motivo is None:
            tenuti.append(t)
    return tenuti, conti


def compiti_titolo(t: Titolo) -> list[Compito]:
    simbolo = "{}.{}".format(q(t.codice), t.borsa)
    return [Compito("eod/" + simbolo, (("fmt", "csv"),), 1, "prezzi"),
            Compito("div/" + simbolo, (("fmt", "json"),), 1, "dividendi"),
            Compito("splits/" + simbolo, (("fmt", "json"),), 1, "split")]


def compiti_extra(blocco: str, codici_indici: set[str], codici_cambi: set[str]) -> tuple[list[Compito], dict]:
    """Indici, cambi e tesoro del blocco; i codici che il fornitore non elenca si contano come mancanti."""
    out, mancanti = [], {"indici": [], "cambi": []}
    for c in INDICI[blocco]:
        if c in codici_indici:
            out.append(Compito("eod/{}.INDX".format(c), (("fmt", "csv"),), 1, "indici"))
        else:
            mancanti["indici"].append(c)
    if blocco == "1":
        for curva in CURVE_TESORO:
            for anno in ANNI_TESORO:
                out.append(Compito("ust/" + curva, (("filter[year]", str(anno)), ("fmt", "json")), 1, "tesoro"))
    if blocco == "2":
        coppie = ["EURUSD"] + ["EUR" + v for v in VALUTE] + ["USD" + v for v in VALUTE]
        for c in coppie:
            if c in codici_cambi:
                out.append(Compito("eod/{}.FOREX".format(c), (("fmt", "csv"),), 1, "cambi"))
            else:
                mancanti["cambi"].append(c)
    return out, mancanti


def compito_identificativi(pagina: int) -> Compito:
    return Compito("id-mapping", tuple(sorted({"filter[ex]": "US", "page[limit]": "1000",
                                               "page[offset]": str(pagina * 1000), "fmt": "json"}.items())), 1, "identificativi")


# ----------------------------------------------------------- controlli puri --
def troppi_fallimenti(falliti: int, eseguiti: int, minimo: int | None = None, soglia: float | None = None,
                      finale: bool = False) -> bool:
    minimo = MINIMO_COMPITI if minimo is None else minimo
    soglia = SOGLIA_FALLIMENTI if soglia is None else soglia
    if eseguiti == 0 or (eseguiti < minimo and not finale):
        return False
    return falliti / eseguiti > soglia


def spazio_necessario(frazioni_mancanti: dict[str, float], stima: dict | None = None) -> float:
    """Byte ancora necessari al download: grezzo che manca per blocco, per il fattore di sicurezza, più la riserva. Il
    Parquet si costruisce dopo, in un passo a parte con il suo controllo (`store.ricostruisci`), per scelta dell'utente
    del 18-09-2026 (ADR 006 punto 62)."""
    stima = STIMA if stima is None else stima
    gb = sum(stima[b][0] * f for b, f in frazioni_mancanti.items())
    return FATTORE_SPAZIO * gb * 1024 ** 3 + MARGINE_SPAZIO


def secondi_alla_mezzanotte_utc(adesso: dt.datetime) -> float:
    domani = (adesso + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (domani - adesso).total_seconds() + 120          # due minuti di margine sull'azzeramento


def esito_di(stato: int, corpo: bytes, tabella: str) -> str:
    if stato == 200:
        if tabella in ("prezzi", "indici", "cambi"):
            righe = [x for x in corpo.decode("utf-8", "replace").splitlines() if x.strip()]
            return "ok" if len(righe) > 1 else "vuoto"
        testo = corpo.strip()
        if testo in (b"", b"[]", b"{}"):
            return "vuoto"
        try:
            dati = json.loads(testo)
        except ValueError:
            return "ok"
        if isinstance(dati, dict) and isinstance(dati.get("data"), list) and not dati["data"]:
            return "vuoto"                                   # busta senza righe (tesoro, identificativi)
        return "ok"
    return "definitivo" if stato in DEFINITIVI else "temporaneo"


def processo_vivo(pid: str) -> bool:
    if not pid.strip().isdigit():
        return False
    if os.name == "nt":
        #  byte, non testo: il messaggio di tasklist per un PID inesistente è nella lingua e nella codifica del sistema
        #  («Nessuna attività…» in cp850) e con -X utf8 la decodifica falliva (stdout None)
        uscita = subprocess.run(["tasklist", "/FI", "PID eq {}".format(pid.strip()), "/NH", "/FO", "CSV"],
                                capture_output=True).stdout or b""
        return '"{}"'.format(pid.strip()).encode() in uscita
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


class Chiavistello:
    """Un solo download o aggiornamento alla volta sullo stesso archivio (`manifest/download.lock` con il PID)."""

    def __init__(self, man: Path, vivo: Callable[[str], bool] = processo_vivo):
        self.file = man / "download.lock"
        self._vivo = vivo

    def __enter__(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        if self.file.exists():
            pid = self.file.read_text(encoding="utf-8").strip()
            if pid and pid != str(os.getpid()) and self._vivo(pid):
                raise SystemExit("download o aggiornamento già in corso (PID {}): uno alla volta".format(pid))
        self.file.write_text(str(os.getpid()), encoding="utf-8")
        return self

    def __exit__(self, *_):
        try:
            if self.file.read_text(encoding="utf-8").strip() == str(os.getpid()):
                self.file.unlink()
        except OSError:
            pass


# --------------------------------------------------------------- download --
class Fermo(Exception):
    pass


class Download:
    def __init__(self, archivio: Path, client: Client, grezzo: Grezzo, log: Callable[[str], None] | None = None,
                 disco_libero: Callable[[], int] | None = None, dormi: Callable[[float], None] = time.sleep,
                 adesso: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
                 contatore: Callable[[], tuple[int, str] | None] | None = None):
        self.archivio, self.client, self.grezzo = archivio, client, grezzo
        self.man = archivio / "eodhd" / "manifest"
        self.man.mkdir(parents=True, exist_ok=True)
        self._log_file = self.man / "download.log"
        self._log = log
        self._disco = disco_libero or (lambda: shutil.disk_usage(archivio).free)
        self._dormi, self._adesso = dormi, adesso
        self._contatore = contatore
        self._contatore_illeggibile = 0
        self._autorizzazione_di_fila = 0
        self._chiamate = 0
        self.stato: dict = {}

    # ---- registro e stato
    def log(self, testo: str) -> None:
        riga = "{} {}".format(self._adesso().isoformat(timespec="seconds"), testo)
        with self._log_file.open("a", encoding="utf-8") as fh:
            fh.write(riga + "\n")
        if self._log:
            self._log(riga)

    def scrivi_stato(self) -> None:
        self.stato["aggiornato"] = self._adesso().isoformat(timespec="seconds")
        tmp = self.man / "stato_download.json.tmp"
        tmp.write_text(json.dumps(self.stato, indent=1), encoding="utf-8")
        for tentativo in range(5):
            try:
                tmp.replace(self.man / "stato_download.json")
                return
            except PermissionError:                    # file aperto da chi lo sta leggendo (Windows): si riprova
                self._dormi(0.2 * (tentativo + 1))
        self.log("stato_download.json occupato: stato non aggiornato questa volta")

    def controlla_stop(self) -> None:
        if (self.man / "STOP").exists():
            raise Fermo("file STOP presente")

    # ---- dati di partenza
    def json_grezzo(self, endpoint: str, params: dict):
        voce = self.grezzo.gia_scaricato(endpoint, params)
        if voce is None:
            r = self._chiama(endpoint, params, 1)
            voce = self.grezzo.salva(endpoint, params, r.stato, r.corpo)
            if r.stato != 200:
                raise Fermo("lista {} {} non disponibile: HTTP {}".format(endpoint, params, r.stato))
        return json.loads(self.grezzo.leggi(voce))

    def lista(self, borsa: str, delistati: bool) -> list[dict]:
        params = {"delisted": "1", "fmt": "json"} if delistati else {"fmt": "json"}
        return self.json_grezzo("exchange-symbol-list/" + borsa, params)

    def piano(self, blocco: str) -> dict:
        percorso = self.man / "piano_{}.json".format(blocco)
        if percorso.exists():
            return json.loads(percorso.read_text(encoding="utf-8"))
        titoli, esclusi = [], {}
        for borsa in BLOCCHI[blocco]["borse"]:
            tt = titoli_da_liste(borsa, self.lista(borsa, False), self.lista(borsa, True))
            if borsa == "F":
                xa, xt = isin_xetra(self.lista("XETRA", False), self.lista("XETRA", True))
                tt, conti = filtro_francoforte(tt, xa, xt)
                esclusi["F"] = conti
            titoli += tt
        codici_indici = {r["Code"] for r in self.json_grezzo("exchange-symbol-list/INDX", {"fmt": "json"})}
        codici_cambi = {r["Code"] for r in self.json_grezzo("exchange-symbol-list/FOREX", {"fmt": "json"})}
        extra, mancanti = compiti_extra(blocco, codici_indici, codici_cambi)
        p = {"blocco": blocco, "nome": BLOCCHI[blocco]["nome"], "creato": self._adesso().isoformat(timespec="seconds"),
             "titoli": [asdict(t) for t in titoli], "extra": [asdict(c) for c in extra], "esclusi": esclusi,
             "non_elencati_dal_fornitore": mancanti, "identificativi": blocco == "1",
             "conteggi": {"titoli": len(titoli), "compiti_titoli": 3 * len(titoli), "compiti_extra": len(extra)}}
        tmp = percorso.with_suffix(".tmp")
        tmp.write_text(json.dumps(p), encoding="utf-8")
        tmp.replace(percorso)
        self.log("piano del blocco {} congelato: {} titoli, {} compiti extra, esclusi {}, non elencati {}".format(
            blocco, len(titoli), len(extra), esclusi, mancanti))
        return p

    # ---- chiamate con attesa del tetto
    def _chiama(self, endpoint: str, params: dict, costo: int):
        """Una chiamata. Al tetto locale o alla risposta 402 del fornitore aspetta l'azzeramento e riprova; conta le
        risposte 401/403 di fila; ogni 1.000 chiamate rilegge il contatore del fornitore."""
        while True:
            self.controlla_stop()
            try:
                r = self.client.get(endpoint, params, costo=costo)
            except BudgetEsaurito as e:
                self.aspetta_azzeramento(str(e))
                continue
            self._chiamate += 1
            if self._chiamate % OGNI_CHIAMATE_CONTATORE == 0:
                self.controlla_contatore()
            if r.stato == TETTO_FORNITORE:
                self.aspetta_azzeramento("il fornitore risponde 402: tetto giornaliero raggiunto")
                continue
            if r.stato in AUTORIZZAZIONE:
                self._autorizzazione_di_fila += 1
                if self._autorizzazione_di_fila >= MAX_AUTORIZZAZIONE_DI_FILA:
                    raise Fermo("{} risposte 401/403 di fila (ultima: {}): chiave o abbonamento da controllare".format(
                        self._autorizzazione_di_fila, endpoint))
            else:
                self._autorizzazione_di_fila = 0
            return r

    def aspetta_azzeramento(self, motivo: str) -> None:
        attesa = secondi_alla_mezzanotte_utc(self._adesso())
        self.log("tetto giornaliero ({}): attesa di {:.0f} minuti fino all'azzeramento".format(motivo, attesa / 60))
        self.stato["in_attesa_del_tetto_fino_a"] = (self._adesso() + dt.timedelta(seconds=attesa)).isoformat(timespec="seconds")
        self.scrivi_stato()
        fine = self._adesso() + dt.timedelta(seconds=attesa)
        while self._adesso() < fine:
            self.controlla_stop()
            self._dormi(min(60.0, max(1.0, (fine - self._adesso()).total_seconds())))
        self.stato.pop("in_attesa_del_tetto_fino_a", None)

    # ---- esecuzione di un blocco
    def esiti(self, blocco: str) -> dict[tuple, dict]:
        righe, illeggibili = registri.leggi(self.man / "esiti_{}.jsonl".format(blocco))
        if illeggibili:
            self.log("esiti del blocco {}: {} righe illeggibili saltate (interruzione)".format(blocco, illeggibili))
        return {(e["endpoint"], tuple(sorted(e["parametri"].items()))): e for e in righe}

    def registra_esito(self, blocco: str, c: Compito, stato: int, esito: str, byte: int) -> dict:
        e = {"quando": self._adesso().isoformat(timespec="seconds"), "endpoint": c.endpoint, "parametri": c.parametri(),
             "tabella": c.tabella, "stato": stato, "esito": esito, "byte": byte}
        registri.appendi(self.man / "esiti_{}.jsonl".format(blocco), e)
        return e

    def esito_dal_grezzo(self, voce: dict, tabella: str) -> str:
        """Esito di un compito già nel grezzo (stato 200), dal numero di righe del manifest o, se manca, dal corpo."""
        if voce.get("righe") is not None:
            return "ok" if voce["righe"] > 0 else "vuoto"
        try:
            return esito_di(200, self.grezzo.leggi(voce), tabella)
        except OSError:
            return "ok"

    def esegui_compito(self, blocco: str, c: Compito, esiti: dict) -> str:
        chiave = (c.endpoint, c.params)
        voce = self.grezzo.gia_scaricato(c.endpoint, c.parametri())
        if voce is not None:
            return self.esito_dal_grezzo(voce, c.tabella)
        precedente = esiti.get(chiave)
        if precedente and precedente["esito"] == "definitivo":
            return "definitivo"
        for prova in range(RIPROVE_RETE + 1):
            r = self._chiama(c.endpoint, c.parametri(), c.costo)
            if r.stato == 200 or r.stato in DEFINITIVI or r.stato in AUTORIZZAZIONE or prova == RIPROVE_RETE:
                break
            self.log("{}: HTTP {} dopo i tentativi del client, nuova prova fra un minuto ({}/{})".format(
                c.endpoint, r.stato, prova + 1, RIPROVE_RETE))
            self._dormi(PAUSA_RETE)
        self.grezzo.salva(c.endpoint, c.parametri(), r.stato, r.corpo)
        esito = esito_di(r.stato, r.corpo, c.tabella)
        esiti[chiave] = self.registra_esito(blocco, c, r.stato, esito, len(r.corpo))
        return esito

    def frazioni_mancanti(self, blocco: str, fatti: int, totale: int, blocchi: list[str]) -> dict[str, float]:
        """Per ogni blocco la frazione di grezzo ancora da scaricare, nell'ordine in cui i blocchi vengono eseguiti."""
        out = {b: 0.0 for b in STIMA}
        posizione = blocchi.index(blocco) if blocco in blocchi else 0
        for i, b in enumerate(blocchi):
            if b not in STIMA:
                continue
            if i > posizione:
                out[b] = 1.0
            elif b == blocco:
                out[b] = max(0.0, 1 - fatti / totale) if totale else 0.0
        return out

    def controlla_spazio(self, blocco: str, fatti: int, totale: int, blocchi: list[str]) -> None:
        serve = spazio_necessario(self.frazioni_mancanti(blocco, fatti, totale, blocchi))
        libero = self._disco()
        self.stato["disco_libero_gb"] = round(libero / 1024 ** 3, 2)
        self.stato["disco_necessario_gb"] = round(serve / 1024 ** 3, 2)
        if libero < serve:
            raise Fermo("spazio insufficiente: liberi {:.1f} GB, necessari {:.1f} GB".format(libero / 1024 ** 3, serve / 1024 ** 3))

    def controlla_contatore(self) -> None:
        """Consumo reale del fornitore: allinea il registro se il fornitore conta di più, aspetta se è al tetto, si ferma se
        il contatore non si legge 3 volte di fila."""
        if not self._contatore:
            return
        letto = self._contatore()
        if letto is None:
            self._contatore_illeggibile += 1
            self.log("contatore del fornitore non leggibile ({} di fila)".format(self._contatore_illeggibile))
            if self._contatore_illeggibile >= MAX_CONTATORE_ILLEGGIBILE:
                raise Fermo("contatore del fornitore non leggibile {} volte di fila: consumo reale sconosciuto".format(
                    self._contatore_illeggibile))
            return
        self._contatore_illeggibile = 0
        usate, giorno_fornitore = letto
        oggi = self._adesso().date().isoformat()
        if giorno_fornitore != oggi:
            usate = 0                                   # il fornitore azzera alla prima chiamata del giorno
        rettifica = self.client.registro.allinea(oggi, usate, self._adesso().isoformat(timespec="seconds"))
        if rettifica:
            self.log("registro locale allineato al fornitore: +{} chiamate".format(rettifica))
        self.stato["contatore_fornitore"] = usate
        self.stato["registro_locale_oggi"] = self.client.usate_oggi()
        if usate >= self.client.limiti.giorno_utile:
            self.aspetta_azzeramento("contatore del fornitore a {}".format(usate))

    def identificativi(self, blocco: str, esiti: dict, conti: dict) -> list[Compito]:
        """Mappatura CUSIP/ISIN/CIK per la borsa USA, a pagine da 1.000 righe fino all'ultima o al tetto di pagine.
        Ogni pagina conta come compito; una pagina fallita si registra, si ripassa a fine blocco e ferma la mappatura."""
        fatte = []
        for pagina in range(TETTO_PAGINE_ID):
            c = compito_identificativi(pagina)
            fatte.append(c)
            esito = self.esegui_compito(blocco, c, esiti)
            conti[esito] += 1
            if esito != "ok":
                if esito != "vuoto":
                    self.log("mappatura identificativi: pagina {} con esito {}".format(pagina, esito))
                break
            try:
                corpo = json.loads(self.grezzo.leggi(self.grezzo.gia_scaricato(c.endpoint, c.parametri())))
            except (ValueError, TypeError):
                self.log("mappatura identificativi: pagina {} non è JSON, mappatura interrotta".format(pagina))
                break
            if not isinstance(corpo, dict) or not (corpo.get("links") or {}).get("next") or not corpo.get("data"):
                break
        else:
            self.log("mappatura identificativi: raggiunto il tetto di {} pagine".format(TETTO_PAGINE_ID))
        return fatte

    def esegui_blocco(self, blocco: str, blocchi: list[str]) -> dict:
        p = self.piano(blocco)
        compiti = [Compito(**dict(c, params=tuple(tuple(v) for v in c["params"]))) for c in p["extra"]]
        for t in p["titoli"]:
            compiti += compiti_titolo(Titolo(**t))
        esiti = self.esiti(blocco)
        conti = {"ok": 0, "vuoto": 0, "definitivo": 0, "temporaneo": 0}
        self.stato = {"blocco": blocco, "nome": p["nome"], "compiti": len(compiti), "fatti": 0, "conti": conti}
        self.log("blocco {} ({}): {} compiti".format(blocco, p["nome"], len(compiti)))
        self.controlla_contatore()
        for i, c in enumerate(compiti):
            if i % GRUPPO == 0:
                self.controlla_spazio(blocco, i, len(compiti), blocchi)
                self.scrivi_stato()
            conti[self.esegui_compito(blocco, c, esiti)] += 1
            self.stato["fatti"] = i + 1
            falliti = conti["definitivo"] + conti["temporaneo"]
            if troppi_fallimenti(falliti, i + 1):
                raise Fermo("blocco {}: {} compiti falliti su {} ({:.1%}), sopra il 2%".format(blocco, falliti, i + 1, falliti / (i + 1)))
        if p.get("identificativi"):
            compiti += self.identificativi(blocco, esiti, conti)
        #  una ripassata dei temporanei (compresa l'eventuale pagina fallita della mappatura)
        da_ripetere = [c for c in compiti if esiti.get((c.endpoint, c.params), {}).get("esito") == "temporaneo"
                       and self.grezzo.gia_scaricato(c.endpoint, c.parametri()) is None]
        if da_ripetere:
            self.log("blocco {}: ripasso {} compiti temporanei".format(blocco, len(da_ripetere)))
            self.controlla_contatore()
            for c in da_ripetere:
                conti["temporaneo"] -= 1
                conti[self.esegui_compito(blocco, c, esiti)] += 1
            if p.get("identificativi") and any(c.endpoint == "id-mapping" for c in da_ripetere):
                ultima = max(int(dict(c.params)["page[offset]"]) // 1000 for c in compiti if c.endpoint == "id-mapping")
                voce = self.grezzo.gia_scaricato("id-mapping", compito_identificativi(ultima).parametri())
                if voce is not None:                          # la pagina ora c'è: si prosegue la mappatura
                    self.log("mappatura identificativi: ripresa dopo la pagina {}".format(ultima))
                    compiti += self.identificativi(blocco, esiti, conti)
        falliti = conti["definitivo"] + conti["temporaneo"]
        self.stato["conti"] = conti
        self.stato["esito"] = "completato"
        self.scrivi_stato()
        self.log("blocco {} completato: {}".format(blocco, conti))
        if troppi_fallimenti(falliti, len(compiti), finale=True):
            raise Fermo("blocco {}: {} compiti falliti su {} ({:.1%}), sopra il 2%".format(blocco, falliti, len(compiti), falliti / len(compiti)))
        return conti


def contatore_fornitore(client: Client) -> Callable[[], tuple[int, str] | None]:
    def leggi() -> tuple[int, str] | None:
        r = client.get("user", {}, costo=0)
        if r.stato != 200:
            return None
        try:
            d = json.loads(r.corpo)
            return int(d["apiRequests"]), str(d.get("apiRequestsDate") or "")
        except (ValueError, KeyError, TypeError):
            return None
    return leggi


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--blocchi", default="1,2,3")
    a = ap.parse_args(argv)
    blocchi = [b.strip() for b in a.blocchi.split(",") if b.strip()]
    for flusso in (sys.stdout, sys.stderr):              # processo staccato su Windows: console non UTF-8
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    archivio = C.archivio()
    client = Client(C.chiave_eodhd(), archivio, C.limiti())
    d = Download(archivio, client, Grezzo(archivio), log=print, contatore=contatore_fornitore(client))
    with Chiavistello(d.man):
        (d.man / "download.pid").write_text(str(os.getpid()), encoding="utf-8")
        try:
            for b in blocchi:
                d.esegui_blocco(b, blocchi)
            d.stato["esito"] = "tutti i blocchi completati"
            d.scrivi_stato()
            d.log("download completato: blocchi {}".format(blocchi))
            return 0
        except Fermo as e:
            d.stato["esito"] = "fermo: {}".format(e)
            d.scrivi_stato()
            d.log("FERMO: {}".format(e))
            return 2
        except Exception as e:                       # qualsiasi altro errore: stato scritto, poi si rilancia
            d.stato["esito"] = "errore: {}: {}".format(type(e).__name__, e)
            d.scrivi_stato()
            d.log("ERRORE: {}: {}".format(type(e).__name__, e))
            raise


if __name__ == "__main__":
    sys.exit(main())
