"""Aggiornamento incrementale (fase 5): per ogni borsa, solo il mancante dalla copertura registrata, con gli endpoint in blocco.

Tutto lo stato sta nel registro `manifest/aggiornamenti.jsonl` (campi in DATA_DICTIONARY.md). Un'esecuzione interrotta
(file STOP, errore, spegnimento) non perde nulla: le decisioni si scrivono **prima** di agire, e un lavoro si chiude solo
quando è fatto.

**Copertura** di una borsa = giorno prima del primo download per titolo della borsa (fissato nel registro alla prima
esecuzione), spostato in avanti seduta per seduta finché le sedute successive risultano coperte nel registro.

**Serie valida** di un codice = l'ultima serie di prezzi per titolo in CSV, se scaricata dopo l'ultimo segno di riuso del
codice. Solo le serie valide contano come «già scaricate», ricevono eventi e righe dai blocchi.

Per ogni borsa (Xetra prima di Francoforte, che si filtra con le liste di Xetra appena arrivate):
1. **liste dei titoli** di nuovo (attivi e delistati). Si confrontano con le precedenti solo se arrivano tutte e due come
   liste JSON e nessuna ha meno di metà delle righe di prima (una lista vuota o troncata non diventa il termine di
   confronto). Le decisioni vanno nella **coda dei lavori** prima che le liste nuove si salvino:
   - **titolo attivo senza serie valida** → lavoro «nuovo» (prezzi, dividendi, split), con i filtri del download;
   - **delistato mai visto** (come `X_old` dopo un riuso) → lavoro «delistato nuovo»;
   - **ticker riusato**: un codice con serie valida che fra gli attivi ha ISIN diverso da prima (o nome molto diverso
     quando manca un ISIN; il record attivo di prima vince su quello delistato) → **segno di riuso** con l'istante, poi
     lavoro «riuso» se il tipo è fra quelli tenuti. Dal segno in poi le versioni precedenti non valgono più, anche se
     più lunghe: finché il lavoro non è fatto il codice resta senza dati;
2. **in blocco per seduta** dopo la copertura: prezzi, split e dividendi (100 chiamate ciascuno). Un blocco vale solo se
   la risposta è 200 **e** una lista JSON. Esiti: **ok** (tre blocchi validi, e i titoli con serie valida che hanno una
   riga con la data della seduta sono almeno metà del riferimento: mediana delle ultime 5 sedute coperte, o i titoli
   attivi con serie valida); **fallito** o **corto** (la seduta non è coperta; la volta dopo si riscaricano solo i blocchi
   non validi, e i prezzi se era corta); **corto accettato** (corto in 3 giorni diversi). Dopo una seduta fallita le
   sedute seguenti della borsa si lasciano alla volta dopo (la copertura non passerebbe comunque);
3. **eventi** dai blocchi validi di split e dividendi, per i codici con serie valida → lavoro «split» (prezzi, dividendi,
   split) o «dividendo» (prezzi, dividendi), mai se la serie è stata scaricata dopo quel giorno;
4. **coda**: i lavori aperti della borsa, anche quelli rimasti da prima, raggruppati per titolo. Una tabella è fatta
   quando la sua versione più recente è stata scaricata dopo l'ingresso in coda del lavoro. Chiusure: `ok` (tutte fatte);
   `non disponibile` (le tabelle mancanti hanno risposto 404 in almeno 5 giorni diversi); `uscito dalle liste` (un
   «nuovo» non più fra gli attivi, un «delistato nuovo» o un «riuso» non più in nessuna lista). Un «nuovo» o
   «delistato nuovo» chiuso senza `ok` si può rimettere in coda dopo 30 giorni. Le risposte 404 non si salvano nel
   grezzo (si contano nel registro). Dopo un errore di rete o del fornitore su un titolo, le sue altre tabelle aspettano
   la volta dopo;
5. alla fine: **cambi e indici già nell'archivio, Tesoro USA (anno corrente e precedente)** di nuovo; **mappatura
   identificativi** di nuovo, salvata solo se tutte le pagine arrivano, fra due righe del registro (inizio e file).

Chiamate: rete, 429 e 5xx riprovati fino a 5 volte a un minuto di distanza per liste, blocchi e dati finali; una volta
sola per i lavori in coda (restano in coda). Dopo 10 chiamate di fila fallite così si chiede al fornitore se risponde
(`user`, non si paga): se no l'aggiornamento si ferma, se sì continua.

Poi: normalizzazione, Tesoro, identificativi, anagrafica, calendario, controlli senza fonti esterne, catalogo. Stesso
client, stesso tetto giornaliero, stesso file STOP e stesso chiavistello del download: i due non girano mai insieme.

    .venv/Scripts/python.exe -m market_data.eodhd.update [--borse US,LSE] [--fino-a AAAA-MM-GG] [--prova] [--senza-identificativi]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

from market_data import config as C
from market_data import registri
from market_data.eodhd import download as D
from market_data.eodhd.client import Client
from market_data.quality import calendario as K
from market_data.quality.esterni import nomi_simili
from market_data.store.raw import Grezzo

COSTO_BLOCCO = 100
TIPI_BLOCCO = {"prezzi": None, "split": "splits", "dividendi": "dividends"}
QUOTA_SEDUTA_CORTA = 0.5
QUOTA_LISTA_CORTA = 0.5
SEDUTE_DI_RIFERIMENTO = 5
MINIMO_SEDUTE_DI_RIFERIMENTO = 3
GIORNI_PRIMA_DI_ACCETTARE = 3
GIORNI_404_PRIMA_DI_CHIUDERE = 5
GIORNI_PRIMA_DI_RIMETTERE = 30
SOGLIA_NOME_RIUSO = 0.5
COPERTE = ("ok", "corto accettato")
TABELLE = ("prezzi", "dividendi", "split")
TABELLE_LAVORO = {"nuovo": TABELLE, "delistato nuovo": TABELLE, "riuso": TABELLE, "split": TABELLE,
                  "dividendo": ("prezzi", "dividendi")}
RIMETTIBILI = ("nuovo", "delistato nuovo")
SENZA_CALENDARIO_GIORNI = 10
MAX_TRANSITORI_DI_FILA = 10


def sedute_mancanti(coperto: dt.date | None, sedute: list[str], fino_a: dt.date) -> list[str]:
    return [s for s in sedute if (coperto is None or s > coperto.isoformat()) and s <= fino_a.isoformat()]


def ticker_riusati(prima_attivi: list[dict], prima_delistati: list[dict], dopo_attivi: list[dict]) -> list[dict]:
    """Record attivi nuovi il cui codice aveva prima un ISIN diverso (se ci sono tutti e due) o, senza uno dei due ISIN,
    un nome molto diverso. Il record di prima è quello attivo se c'è, altrimenti quello delistato: un codice che sta in
    tutte e due le liste con ISIN diversi non è un riuso a ogni esecuzione."""
    vecchi = {r["Code"]: r for r in prima_delistati if r.get("Code")}
    vecchi.update({r["Code"]: r for r in prima_attivi if r.get("Code")})
    out = {}
    for r in dopo_attivi:
        v = vecchi.get(r.get("Code"))
        if not v:
            continue
        i1, i2 = (v.get("Isin") or "").upper(), (r.get("Isin") or "").upper()
        if i1 and i2:
            riusato = i1 != i2
        else:
            riusato = bool(v.get("Name") and r.get("Name")) and nomi_simili(v["Name"], r["Name"]) < SOGLIA_NOME_RIUSO
        if riusato:
            out[r["Code"]] = r
    return [out[c] for c in sorted(out)]


def esito_seduta(validi: bool, righe_nostre: int, riferimento: float | None, giorni_corti_prima: int) -> str:
    """ok, fallito, corto o corto accettato (corto in `GIORNI_PRIMA_DI_ACCETTARE` giorni diversi, compreso questo)."""
    if not validi:
        return "fallito"
    if righe_nostre == 0 or (riferimento is not None and righe_nostre < QUOTA_SEDUTA_CORTA * riferimento):
        return "corto accettato" if giorni_corti_prima + 1 >= GIORNI_PRIMA_DI_ACCETTARE else "corto"
    return "ok"


def lista_json(corpo: bytes) -> list | None:
    """La risposta come lista JSON, o None se non lo è (errore del fornitore in un oggetto, testo, JSON rotto)."""
    try:
        dati = json.loads(corpo)
    except ValueError:
        return None
    return dati if isinstance(dati, list) else None


def chiave_lavoro(v: dict) -> tuple:
    return v.get("borsa"), v.get("codice"), v.get("motivo"), v.get("data")


def transitorio(stato: int) -> bool:
    return stato == 0 or stato == 429 or stato >= 500


class Registro:
    """`manifest/aggiornamenti.jsonl` con gli indici in memoria: nessuna scansione dell'intero file per decisione."""

    def __init__(self, percorso: Path):
        self.percorso = percorso
        self.inizi: dict[str, str] = {}
        self.sedute: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        self.lavori: dict[tuple, dict] = {}
        self.lavori_per_titolo: dict[tuple, list[dict]] = defaultdict(list)
        self.fatti: dict[tuple, dict] = {}
        self.riusi: dict[tuple[str, str], str] = {}
        self.segni: set[tuple] = set()
        self.giorni_404: dict[tuple, set[str]] = defaultdict(set)
        self.identificativi: list[dict] = []
        for voce in registri.leggi(percorso)[0]:
            self._indicizza(voce)

    def _indicizza(self, v: dict) -> None:
        tipo = v.get("tipo")
        if tipo == "inizio" and v.get("borsa") and v.get("data"):
            self.inizi.setdefault(v["borsa"], v["data"])
        elif tipo == "seduta" and v.get("borsa") and v.get("data"):
            self.sedute[v["borsa"]][v["data"]].append(v)
        elif tipo == "lavoro":
            self.lavori.setdefault(chiave_lavoro(v), v)
            self.lavori_per_titolo[(v.get("borsa"), v.get("codice"), v.get("motivo"))].append(v)
        elif tipo == "fatto":
            self.fatti.setdefault(chiave_lavoro(v), v)
        elif tipo == "riuso" and v.get("borsa") and v.get("codice") and v.get("dal"):
            chiave = (v["borsa"], v["codice"])
            self.riusi[chiave] = max(self.riusi.get(chiave, ""), v["dal"])
            self.segni.add((v["borsa"], v["codice"], v.get("identita")))
        elif tipo == "non trovato" and v.get("quando"):
            self.giorni_404[(v.get("borsa"), v.get("codice"), v.get("tabella"))].add(v["quando"][:10])
        elif tipo == "identificativi":
            self.identificativi.append(v)

    def aggiungi(self, voce: dict) -> dict:
        registri.appendi(self.percorso, voce)
        self._indicizza(voce)
        return voce

    def aperti(self, borsa: str) -> list[dict]:
        return [v for k, v in self.lavori.items() if k[0] == borsa and k not in self.fatti]


class Aggiornamento:
    def __init__(self, archivio: Path, client: Client, grezzo: Grezzo, log=print,
                 adesso=lambda: dt.datetime.now(dt.timezone.utc), dormi=time.sleep):
        self.archivio, self.client, self.grezzo = archivio, client, grezzo
        self.dl = D.Download(archivio, client, grezzo, log=log, adesso=adesso, dormi=dormi)
        self.log = self.dl.log
        self._adesso, self._dormi = adesso, dormi
        self.reg = Registro(archivio / "eodhd" / "manifest" / "aggiornamenti.jsonl")
        self.transitori_di_fila = 0
        self.esiti_in_questa_esecuzione: dict[tuple, str] = {}      # (borsa, codice, tabella) -> esito non riuscito

    # ---- registro
    def istante(self) -> str:
        return self._adesso().isoformat(timespec="seconds")

    def annota(self, voce: dict) -> dict:
        return self.reg.aggiungi(dict(voce, quando=self.istante()))

    def in_coda(self, voce: dict) -> bool:
        """Mette un lavoro in coda se non c'è già. Un «nuovo» o «delistato nuovo» chiuso senza `ok` da più di 30 giorni
        si rimette (con la data di oggi nella chiave). Vero se l'ha aggiunto."""
        motivo = voce["motivo"]
        if motivo in RIMETTIBILI:
            oggi = self._adesso().date()
            for p in self.reg.lavori_per_titolo[(voce["borsa"], voce["codice"], motivo)]:
                f = self.reg.fatti.get(chiave_lavoro(p))
                if f is None or f.get("esito") == "ok":
                    return False
                if (oggi - dt.date.fromisoformat(f["quando"][:10])).days < GIORNI_PRIMA_DI_RIMETTERE:
                    return False
            voce = dict(voce, data=oggi.isoformat())
        elif chiave_lavoro(voce) in self.reg.lavori:
            return False
        self.annota(dict(voce, tipo="lavoro", tabelle=list(TABELLE_LAVORO[motivo])))
        return True

    def chiudi(self, v: dict, esito: str, e: dict) -> None:
        self.annota({"tipo": "fatto", **{k: v[k] for k in ("borsa", "codice", "motivo", "data")}, "esito": esito})
        e["lavori_chiusi"] += 1

    # ---- grezzo
    def _serie_per_titolo(self, borsa: str, anche_prima_dei_riusi: bool = False) -> dict[str, dict]:
        """codice -> ultima voce 200 dei prezzi per titolo in CSV (il formato del download in massa; i campioni JSON delle
        fasi 0 e 1 non contano). Senza `anche_prima_dei_riusi`, solo le serie valide (scaricate dopo il segno di riuso)."""
        out = {}
        for voce in self.grezzo._ok.values():
            ep = voce["endpoint"]
            if ep.startswith("eod/") and ep.endswith("." + borsa) and voce["parametri"] == {"fmt": "csv"}:
                codice = urllib.parse.unquote(ep[4:-len(borsa) - 1])
                dal = self.reg.riusi.get((borsa, codice))
                if anche_prima_dei_riusi or not dal or voce["scaricato"] >= dal:
                    out[codice] = voce
        return out

    def borse(self) -> list[str]:
        out = set()
        for voce in self.grezzo._ok.values():
            if voce["endpoint"].startswith("eod/") and set(voce["parametri"]) == {"fmt"}:
                borsa = voce["endpoint"].rsplit(".", 1)[-1]
                if borsa not in ("INDX", "FOREX"):
                    out.add(borsa)
        return sorted(out)

    def copertura_iniziale(self, borsa: str) -> dt.date | None:
        """Fissata nel registro alla prima esecuzione; prima di allora, giorno prima della **prima** versione della serie
        per titolo scaricata per prima (le versioni riscaricate dopo non la spostano)."""
        if borsa in self.reg.inizi:
            return dt.date.fromisoformat(self.reg.inizi[borsa])
        date = [self.grezzo.storia(v)[0]["scaricato"][:10] for v in self._serie_per_titolo(borsa, anche_prima_dei_riusi=True).values()]
        return dt.date.fromisoformat(min(date)) - dt.timedelta(days=1) if date else None

    def coperto_fino_a(self, borsa: str, sedute: list[str]) -> dt.date | None:
        coperto = self.copertura_iniziale(borsa)
        registrate = self.reg.sedute[borsa]
        for s in sedute:
            if coperto is not None and s <= coperto.isoformat():
                continue
            if any(v.get("esito") in COPERTE for v in registrate.get(s, [])):
                coperto = dt.date.fromisoformat(s)
            else:
                break
        return coperto

    def piano(self, borse: list[str], fino_a: dt.date) -> dict:
        out = {}
        for b in borse:
            iniziale = self.copertura_iniziale(b)
            aperti = len(self.reg.aperti(b))
            if b not in K.CALENDARI:
                self.log("aggiornamento {}: nessun calendario, niente sedute in blocco".format(b))
                out[b] = {"coperto_fino_a": str(iniziale) if iniziale else None, "sedute": [], "chiamate_in_blocco": 0,
                          "chiamate_liste": 2, "lavori_aperti": aperti, "senza_calendario": True}
                continue
            base = iniziale or (fino_a - dt.timedelta(days=SENZA_CALENDARIO_GIORNI))
            tutte = K.sessioni(b, base.isoformat(), fino_a.isoformat())
            coperto = self.coperto_fino_a(b, tutte)
            registrate = self.reg.sedute[b]
            sedute = [s for s in sedute_mancanti(coperto, tutte, fino_a)
                      if not any(v.get("esito") in COPERTE for v in registrate.get(s, []))]
            out[b] = {"coperto_fino_a": str(coperto) if coperto else None, "sedute": sedute,
                      "chiamate_in_blocco": COSTO_BLOCCO * len(TIPI_BLOCCO) * len(sedute), "chiamate_liste": 2,
                      "lavori_aperti": aperti}
        return out

    # ---- chiamate
    def fornitore_risponde(self) -> bool:
        try:
            return self.client.get("user", {}, costo=0).stato == 200
        except Exception:                                    # noqa: BLE001 — qualsiasi errore vale «non risponde»
            return False

    def chiama(self, endpoint: str, params: dict, costo: int, pazienza: bool = True):
        """Una chiamata; con `pazienza` rete, 429 e 5xx si riprovano fino a 5 volte a un minuto di distanza. Non salva."""
        prove = D.RIPROVE_RETE if pazienza else 0
        for prova in range(prove + 1):
            r = self.dl._chiama(endpoint, params, costo)
            if not transitorio(r.stato) or prova == prove:
                break
            self.log("{}: HTTP {} dopo i tentativi del client, nuova prova fra un minuto ({}/{})".format(
                endpoint, r.stato, prova + 1, prove))
            self._dormi(D.PAUSA_RETE)
        if not transitorio(r.stato):
            self.transitori_di_fila = 0
            return r
        self.transitori_di_fila += 1
        if self.transitori_di_fila >= MAX_TRANSITORI_DI_FILA:
            if not self.fornitore_risponde():
                raise D.Fermo("{} chiamate di fila fallite e il fornitore non risponde (ultima: {} HTTP {}): i lavori restano "
                              "in coda".format(self.transitori_di_fila, endpoint, r.stato))
            self.log("{} chiamate di fila fallite ma il fornitore risponde: si continua".format(self.transitori_di_fila))
            self.transitori_di_fila = 0
        return r

    def scarica(self, endpoint: str, params: dict, costo: int):
        """Nuovo scaricamento anche se la chiave è già nel grezzo: un file nuovo, mai sovrascritto."""
        r = self.chiama(endpoint, params, costo)
        self.grezzo.salva(endpoint, params, r.stato, r.corpo, adesso=self._adesso())
        return r

    # ---- 1. liste
    def liste_nuove(self, b: str, e: dict, xetra_cache: dict) -> dict:
        """Liste nuove contro le precedenti: decisioni nella coda, poi liste salvate. Restituisce i codici ammessi
        (`attivi`, `tutti`) delle liste usate, e `nuove` vero se sono quelle appena arrivate."""
        parametri = ({"fmt": "json"}, {"delisted": "1", "fmt": "json"})
        prima = []
        for params in parametri:
            voce = self.grezzo.gia_scaricato("exchange-symbol-list/" + b, params)
            prima.append((lista_json(self.grezzo.leggi(voce)) or []) if voce else [])
        risposte = [self.chiama("exchange-symbol-list/" + b, params, 1) for params in parametri]
        dopo = []
        for r, p in zip(risposte, prima):
            d = lista_json(r.corpo) if r.stato == 200 else None
            if d is not None and p and len(d) < QUOTA_LISTA_CORTA * len(p):
                self.log("aggiornamento {}: lista di {} righe contro {} di prima, non usata".format(b, len(d), len(p)))
                d = None
            dopo.append(d)
        nuove = all(d is not None for d in dopo)
        if not nuove:
            e["falliti"] += sum(d is None for d in dopo)
            self.log("aggiornamento {}: liste non disponibili, nessun confronto (i lavori in coda proseguono)".format(b))
            dopo = [d if d is not None else p for d, p in zip(dopo, prima)]
        titoli = D.titoli_da_liste(b, dopo[0], dopo[1])
        if b == "XETRA" and nuove:
            xetra_cache["xetra"] = D.isin_xetra(dopo[0], dopo[1])
        if b == "F":
            if "xetra" not in xetra_cache:
                xetra_cache["xetra"] = D.isin_xetra(self.dl.lista("XETRA", False), self.dl.lista("XETRA", True))
            titoli, _ = D.filtro_francoforte(titoli, *xetra_cache["xetra"])
        ammessi = {"attivi": {t.codice for t in titoli if t.stato == "attivo"}, "tutti": {t.codice for t in titoli},
                   "nuove": nuove}
        if not nuove:
            return ammessi
        con_serie = set(self._serie_per_titolo(b))
        gia_viste = {r.get("Code") for r in prima[0] + prima[1]}
        for t in titoli:
            if t.codice in con_serie:
                continue
            if t.stato == "attivo":
                e["titoli_nuovi"] += self.in_coda({"borsa": b, "codice": t.codice, "motivo": "nuovo", "data": None})
            elif t.codice not in gia_viste:
                e["delistati_nuovi"] += self.in_coda({"borsa": b, "codice": t.codice, "motivo": "delistato nuovo", "data": None})
        for r in ticker_riusati(prima[0], prima[1], dopo[0]):
            codice = r["Code"]
            if codice not in con_serie:
                continue
            identita = (r.get("Isin") or "").upper() or (r.get("Name") or "")
            if (b, codice, identita) not in self.reg.segni:
                self.annota({"tipo": "riuso", "borsa": b, "codice": codice, "identita": identita, "dal": self.istante()})
            if codice in ammessi["tutti"]:
                self.log("aggiornamento {}: {} sembra riusato ({}), serie di nuovo per intero".format(b, codice, identita))
                e["riusati"] += self.in_coda({"borsa": b, "codice": codice, "motivo": "riuso", "data": identita})
            else:
                self.log("aggiornamento {}: {} riusato da un titolo di tipo non tenuto ({}): la serie vecchia esce".format(
                    b, codice, r.get("Type")))
                e["riusati_non_tenuti"] += 1
        for params, r in zip(parametri, risposte):                     # solo ora: il confronto è già nel registro
            self.grezzo.salva("exchange-symbol-list/" + b, params, r.stato, r.corpo, adesso=self._adesso())
        return ammessi

    # ---- 2-3. sedute
    def seduta(self, borsa: str, giorno: str, con_serie: set[str], attivi_con_serie: int) -> dict:
        """Scarica i blocchi della seduta che mancano o l'ultima volta non erano validi. Non registra nulla."""
        registrate = self.reg.sedute[borsa].get(giorno, [])
        ultima = registrate[-1] if registrate else None
        dati, stati = {}, {}
        for nome, tipo in TIPI_BLOCCO.items():
            params = {"date": giorno, "fmt": "json", **({"type": tipo} if tipo else {})}
            voce = self.grezzo.gia_scaricato("eod-bulk-last-day/" + borsa, params)
            rifare = voce is None or (ultima is not None and (
                (ultima.get("stati") or {}).get(nome) != 200 or (nome == "prezzi" and ultima.get("esito") == "corto")))
            if rifare:
                r = self.scarica("eod-bulk-last-day/" + borsa, params, COSTO_BLOCCO)
                corpo, stato = r.corpo, r.stato
            else:
                corpo, stato = self.grezzo.leggi(voce), 200
            lista = lista_json(corpo) if stato == 200 else None
            stati[nome] = 200 if lista is not None else (stato if stato != 200 else "non lista")
            dati[nome] = lista or []
        validi = all(s == 200 for s in stati.values())
        codici = lambda nome, solo_giorno=False: {  # noqa: E731
            x.get("code") for x in dati[nome]
            if isinstance(x, dict) and x.get("code") and (not solo_giorno or str(x.get("date", ""))[:10] == giorno)}
        nostri = codici("prezzi", solo_giorno=True) & con_serie
        coperte = sorted((d, v["righe_nostre"]) for d, vv in self.reg.sedute[borsa].items() for v in vv
                         if d < giorno and v.get("esito") in COPERTE and "righe_nostre" in v)
        recenti = [n for _d, n in coperte[-SEDUTE_DI_RIFERIMENTO:]]
        riferimento = statistics.median(recenti) if len(recenti) >= MINIMO_SEDUTE_DI_RIFERIMENTO else attivi_con_serie
        giorni_corti = {v["quando"][:10] for v in registrate if v.get("esito") == "corto"} - {self._adesso().date().isoformat()}
        return {"esito": esito_seduta(validi, len(nostri), riferimento, len(giorni_corti)), "stati": stati,
                "righe": len(dati["prezzi"]), "righe_nostre": len(nostri), "riferimento": riferimento,
                "split": codici("split") if stati["split"] == 200 else set(),
                "dividendi": codici("dividendi") if stati["dividendi"] == 200 else set()}

    # ---- 4. coda
    def esegui_coda(self, b: str, e: dict, ammessi: dict) -> None:
        per_codice: dict[str, list[dict]] = defaultdict(list)
        for v in self.reg.aperti(b):
            per_codice[v["codice"]].append(v)
        for codice, lavori in sorted(per_codice.items()):
            restano = []
            for v in lavori:
                fuori = (v["motivo"] == "nuovo" and codice not in ammessi["attivi"]) or (
                    v["motivo"] in ("delistato nuovo", "riuso") and codice not in ammessi["tutti"])
                if fuori and ammessi["nuove"]:
                    self.chiudi(v, "uscito dalle liste", e)
                else:
                    restano.append(v)
            if not restano:
                continue
            compiti = {c.tabella: c for c in D.compiti_titolo(D.Titolo(b, codice, "", "", "", "", ""))}
            esiti = {}
            for tabella in TABELLE:
                chi = [v for v in restano if tabella in v.get("tabelle", ())]
                if not chi:
                    continue
                c = compiti[tabella]
                voce = self.grezzo.gia_scaricato(c.endpoint, c.parametri())
                if voce is not None and voce["scaricato"] >= max(v["quando"] for v in chi):
                    esiti[tabella] = "fatta"
                    continue
                gia = self.esiti_in_questa_esecuzione.get((b, codice, tabella))
                if gia is not None or "fallita" in esiti.values():   # provata poco fa, o il titolo ha appena fallito
                    esiti[tabella] = gia or "fallita"
                    continue
                r = self.chiama(c.endpoint, c.parametri(), c.costo, pazienza=False)
                if r.stato == 200:
                    self.grezzo.salva(c.endpoint, c.parametri(), r.stato, r.corpo, adesso=self._adesso())
                    esiti[tabella] = "fatta"
                elif r.stato in D.DEFINITIVI:
                    self.annota({"tipo": "non trovato", "borsa": b, "codice": codice, "tabella": tabella})
                    esiti[tabella] = "non trovata"
                else:
                    self.grezzo.salva(c.endpoint, c.parametri(), r.stato, r.corpo, adesso=self._adesso())
                    esiti[tabella] = "fallita"
                    e["falliti"] += 1
                if esiti[tabella] != "fatta":
                    self.esiti_in_questa_esecuzione[(b, codice, tabella)] = esiti[tabella]
            for v in restano:
                propri = {t: esiti[t] for t in v["tabelle"]}
                if all(x == "fatta" for x in propri.values()):
                    self.chiudi(v, "ok", e)
                elif all(x == "fatta" or (x == "non trovata" and len(
                        [g for g in self.reg.giorni_404[(b, codice, t)] if g >= v["quando"][:10]]) >= GIORNI_404_PRIMA_DI_CHIUDERE)
                         for t, x in propri.items()):                       # solo i giorni da quando il lavoro è in coda
                    self.chiudi(v, "non disponibile", e)
        e["lavori_aperti"] = len(self.reg.aperti(b))

    # ---- esecuzione
    def esegui(self, borse: list[str], fino_a: dt.date, identificativi: bool = True) -> dict:
        esito, xetra_cache = {}, {}
        ordine = sorted(borse, key=lambda b: b == "F")          # Francoforte in fondo, dopo Xetra; le altre nel loro ordine
        for b in ordine:
            e = {"sedute": 0, "sedute_coperte": 0, "sedute_non_coperte": [], "sedute_rimandate": 0, "titoli_nuovi": 0,
                 "delistati_nuovi": 0, "riusati": 0, "riusati_non_tenuti": 0, "eventi": 0, "lavori_chiusi": 0,
                 "lavori_aperti": 0, "falliti": 0}
            iniziale = self.copertura_iniziale(b)
            if iniziale and b not in self.reg.inizi:
                self.annota({"tipo": "inizio", "borsa": b, "data": iniziale.isoformat()})
            ammessi = self.liste_nuove(b, e, xetra_cache)
            self.esegui_coda(b, e, ammessi)
            p = self.piano([b], fino_a)[b]
            e["sedute"] = len(p["sedute"])
            serie = self._serie_per_titolo(b)
            attivi_con_serie = len(ammessi["attivi"] & set(serie))
            for i, giorno in enumerate(p["sedute"]):
                s = self.seduta(b, giorno, set(serie), attivi_con_serie)
                for codice in sorted((s["split"] | s["dividendi"]) & set(serie)):
                    if serie[codice]["scaricato"][:10] > giorno:          # serie già scaricata dopo l'evento
                        continue
                    motivo = "split" if codice in s["split"] else "dividendo"
                    e["eventi"] += self.in_coda({"borsa": b, "codice": codice, "motivo": motivo, "data": giorno})
                if s["esito"] in ("fallito", "corto"):
                    e["sedute_non_coperte"].append(giorno)
                else:
                    e["sedute_coperte"] += 1
                if s["esito"] == "corto accettato":
                    self.log("aggiornamento {}: seduta {} corta in {} giorni diversi ({} righe dei nostri titoli, riferimento {}), "
                             "accettata".format(b, giorno, GIORNI_PRIMA_DI_ACCETTARE, s["righe_nostre"], s["riferimento"]))
                self.annota({"tipo": "seduta", "borsa": b, "data": giorno, "esito": s["esito"], "stati": s["stati"],
                             "righe": s["righe"], "righe_nostre": s["righe_nostre"], "riferimento": s["riferimento"]})
                if s["esito"] == "fallito" and i + 1 < len(p["sedute"]):
                    e["sedute_rimandate"] = len(p["sedute"]) - i - 1
                    self.log("aggiornamento {}: seduta {} fallita, le {} seguenti alla volta dopo".format(b, giorno, e["sedute_rimandate"]))
                    break
            self.esegui_coda(b, e, ammessi)
            esito[b] = e
            self.log("aggiornamento {}: {}".format(b, e))
        esito["extra"] = self.extra(fino_a, identificativi)
        return esito

    def extra(self, fino_a: dt.date, identificativi: bool) -> dict:
        """Cambi e indici già nell'archivio, Tesoro USA dell'anno corrente e precedente, mappatura identificativi."""
        conti = {"cambi_indici": 0, "tesoro": 0, "pagine_identificativi": 0, "identificativi_salvati": False, "falliti": 0}
        serie = sorted({v["endpoint"] for v in self.grezzo._ok.values()
                        if v["endpoint"].startswith("eod/") and v["endpoint"].endswith((".INDX", ".FOREX"))
                        and set(v["parametri"]) == {"fmt"}})
        for ep in serie:
            conti["falliti"] += self.scarica(ep, {"fmt": "csv"}, 1).stato != 200
            conti["cambi_indici"] += 1
        if any(v["endpoint"].startswith("ust/") for v in self.grezzo._ok.values()):
            for curva in D.CURVE_TESORO:
                for anno in (fino_a.year - 1, fino_a.year):
                    conti["falliti"] += self.scarica("ust/" + curva, {"filter[year]": str(anno), "fmt": "json"}, 1).stato != 200
                    conti["tesoro"] += 1
        if identificativi and any(v["endpoint"] == "id-mapping" for v in self.grezzo._ok.values()):
            pagine, completa = [], False
            for pagina in range(D.TETTO_PAGINE_ID):
                c = D.compito_identificativi(pagina)
                r = self.chiama(c.endpoint, c.parametri(), c.costo)
                conti["pagine_identificativi"] += 1
                try:
                    corpo = json.loads(r.corpo) if r.stato == 200 else None
                except ValueError:
                    corpo = None
                if not isinstance(corpo, dict) or not isinstance(corpo.get("data"), list):
                    conti["falliti"] += 1
                    break
                pagine.append((c, r))
                if not (corpo.get("links") or {}).get("next") or not corpo["data"]:
                    completa = True
                    break
            if completa:
                self.annota({"tipo": "identificativi", "stato": "salvataggio"})       # un'interruzione qui si riconosce
                file = [self.grezzo.salva(c.endpoint, c.parametri(), 200, r.corpo, adesso=self._adesso())["file"] for c, r in pagine]
                self.annota({"tipo": "identificativi", "file": file})
                conti["identificativi_salvati"] = True
            else:
                self.log("mappatura identificativi incompleta dopo {} pagine: non salvata, resta la precedente".format(len(pagine)))
        return conti


def ricostruisci(archivio: Path, borse: list[str], log=print, controlli: bool = True) -> None:
    from market_data.quality.esegui import Controlli
    from market_data.store import catalog, identity
    from market_data.store import normalize as N
    n = N.Normalizzatore(archivio, log=log)
    n.per_titolo({"prezzi", "dividendi", "split", "cambi"}, set(borse) | {"INDX", "FOREX"})
    n.tesoro()
    n.identificativi()
    identity.Anagrafica(archivio, log=log).costruisci(borse)
    K.scrivi_calendario(archivio, [b for b in borse if b in K.CALENDARI])
    if controlli:
        Controlli(archivio, log=log).esegui(borse, esterni=False)          # riscrive anche il catalogo
    else:
        catalog.costruisci_catalogo(archivio, log=log)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Aggiornamento incrementale dalla copertura registrata per borsa")
    ap.add_argument("--borse", default="")
    ap.add_argument("--fino-a", default="")
    ap.add_argument("--prova", action="store_true", help="stampa il piano senza chiamare il fornitore")
    ap.add_argument("--senza-identificativi", action="store_true")
    a = ap.parse_args(argv)
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    archivio = C.archivio()
    fino_a = dt.date.fromisoformat(a.fino_a) if a.fino_a else dt.date.today() - dt.timedelta(days=1)
    client = Client(C.chiave_eodhd(), archivio, C.limiti())
    agg = Aggiornamento(archivio, client, Grezzo(archivio))
    agg.dl._contatore = D.contatore_fornitore(client)
    borse = [b.strip() for b in a.borse.split(",") if b.strip()] or agg.borse()
    piano = agg.piano(borse, fino_a)
    print(json.dumps({"fino_a": str(fino_a),
                      "chiamate_stimate": sum(p["chiamate_in_blocco"] + p["chiamate_liste"] for p in piano.values()),
                      "non_comprese": "lavori in coda e nuovi (2 o 3 chiamate per titolo); cambi e indici (una ciascuno); "
                                      "Tesoro (8); identificativi (una per 1.000 righe)",
                      "borse": {b: dict(p, sedute=len(p["sedute"])) for b, p in piano.items()}}, indent=1))
    if a.prova:
        return 0
    with D.Chiavistello(archivio / "eodhd" / "manifest"):             # mai insieme al download
        try:
            agg.dl.controlla_contatore()
            esito = agg.esegui(borse, fino_a, identificativi=not a.senza_identificativi)
        except D.Fermo as e:
            print("FERMO: {}".format(e))
            return 2
        ricostruisci(archivio, borse)
    print(json.dumps(esito, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
