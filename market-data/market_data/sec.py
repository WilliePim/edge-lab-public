"""Bilanci e depositi della SEC dai due file in blocco già scaricati: `companyfacts.zip` e `submissions.zip`.

Le funzioni pubbliche stanno in `api.py` (`sec_azioni`, `sec_bilancio`, `sec_cik`, `sec_societa`, `sec_depositi`); qui
la lettura dentro lo zip, il parsing e la cache. **Nessuna rete**: i due file si leggono dove sono, e se mancano ci si
ferma con `FileMancante`. Nessun download implicito, nessun aggiornamento automatico. Decisioni in docs/adr/009.

**Dove stanno**: `<archivio>/sec_bulk/companyfacts.zip`, `<archivio>/sec_bulk/submissions.zip` e
`<archivio>/sec_bulk/manifest.json` (per file: URL, data UTC del download, byte, sha256, testate HTTP). Prima di aprire
uno zip si controlla che il manifest lo elenchi e che la dimensione sia quella scritta lì: un file troncato o
sostituito senza manifest non si legge.

**Che cosa c'è dentro.** `companyfacts.zip`: un file `CIK##########.json` per società, con tutti i fatti XBRL dei
suoi depositi, per tassonomia (`dei`, `us-gaap`, `ifrs-full`, …), voce e unità; ogni fatto ha `end`, `val`, `accn`,
`fy`, `fp`, `form`, `filed`, e `start` se è un periodo. `submissions.zip`: per società una testata (nome, SIC, tipo,
ticker di oggi) con i 1.000 depositi più recenti, e i più vecchi in file `CIK##########-submissions-NNN.json`.

**Che cosa NON c'è, e che cosa è sbagliato alla fonte** (il lettore non corregge niente):
- `companyfacts` non contiene i fatti riportati **con una dimensione**: le azioni per classe di una società con più
  classi mancano del tutto, e i ricavi per segmento pure;
- i valori sono quelli depositati, **errori compresi**: azioni in circolazione mille o un milione di volte più grandi
  del vero (un grande emittente riporta le azioni in migliaia in un deposito e in unità nel successivo);
- lo stesso periodo compare una volta per ogni deposito che lo riporta (comparativi, riesposizioni): scegliere quale
  vale a una data è compito di chi legge, con `depositato`;
- SIC, nome e ticker della testata sono **quelli di oggi**, non quelli di una data.

**Cache** (opzionale, `cache=True`): `<archivio>/sec_bulk/cache/`, dentro la cartella dei dati, mai nel repo. Per ogni
combinazione di file, impronta dello zip e voci (o moduli) chieste, una tabella Parquet con le società già lette e
l'elenco dei CIK già cercati. Si ricostruisce da sola; cancellarla non perde niente. Senza cache ogni chiamata rilegge
il file della società dentro lo zip (decine di millisecondi l'una).
"""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

CARTELLA = "sec_bulk"
FILE = {"companyfacts": "companyfacts.zip", "submissions": "submissions.zip"}
VOCI_AZIONI = ("dei:EntityCommonStockSharesOutstanding", "us-gaap:CommonStockSharesOutstanding",
               "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic")
TASSONOMIA_PREDEFINITA = "us-gaap"
COLONNE_FATTI = ("cik", "voce", "unita", "inizio", "fine", "valore", "depositato", "modulo", "esercizio", "periodo",
                 "accn", "frame")
COLONNE_SOCIETA = ("cik", "nome", "sic", "sic_descrizione", "tipo", "categoria", "stato", "chiusura_esercizio", "ticker",
                   "borse", "altri_file")
COLONNE_DEPOSITI = ("cik", "accn", "modulo", "depositato", "data_rapporto", "voci_8k")
VERSIONE_CACHE = "1"


class FileMancante(RuntimeError):
    """Uno dei file in blocco della SEC non c'è, non è nel manifest o non ha la dimensione scritta nel manifest."""


def cik_intero(cik) -> int:
    """CIK come intero: accetta 320193, "320193", "0000320193"."""
    try:
        n = int(str(cik).strip())
    except (TypeError, ValueError) as e:
        raise ValueError("CIK non valido: {!r}".format(cik)) from e
    if n <= 0:
        raise ValueError("CIK non valido: {!r}".format(cik))
    return n


def _lista_cik(cik) -> list[int]:
    if isinstance(cik, (str, int)) or not hasattr(cik, "__iter__"):
        cik = [cik]
    return sorted({cik_intero(c) for c in cik})


def voce_completa(voce: str) -> tuple[str, str]:
    """(tassonomia, voce): `Revenues` → (`us-gaap`, `Revenues`); `dei:EntityPublicFloat` → (`dei`, `EntityPublicFloat`)."""
    if not isinstance(voce, str) or not voce.strip():
        raise ValueError("voce non valida: {!r}".format(voce))
    t, _, v = voce.strip().rpartition(":")
    return (t or TASSONOMIA_PREDEFINITA), v


def leggi_fatti(dati: dict, cik: int, voci) -> list[tuple]:
    """Le righe (`COLONNE_FATTI`) delle voci chieste dentro il JSON di una società: tutte le unità, tutti i depositi,
    così come sono. Un fatto senza `val`, `end` o `filed` si salta."""
    fatti = (dati or {}).get("facts") or {}
    out = []
    for voce in voci:
        tass, nome = voce_completa(voce)
        corpo = (fatti.get(tass) or {}).get(nome) or {}
        for unita, righe in sorted((corpo.get("units") or {}).items()):
            for f in righe:
                if f.get("val") is None or not f.get("end") or not f.get("filed"):
                    continue
                try:
                    valore = float(f["val"])
                except (TypeError, ValueError):
                    continue
                out.append((cik, "{}:{}".format(tass, nome), unita, f.get("start") or None, f["end"], valore, f["filed"],
                            f.get("form") or "", f.get("fy"), f.get("fp") or "", f.get("accn") or "", f.get("frame") or ""))
    return out


def leggi_societa(dati: dict, cik: int) -> tuple:
    d = dati or {}
    return (cik, d.get("name") or "", str(d.get("sic") or ""), d.get("sicDescription") or "", d.get("entityType") or "",
            d.get("category") or "", d.get("stateOfIncorporation") or "", d.get("fiscalYearEnd") or "",
            ",".join(d.get("tickers") or []), ",".join(x or "" for x in (d.get("exchanges") or [])),
            len((d.get("filings") or {}).get("files") or []))


def leggi_depositi(blocco: dict, cik: int, moduli=None) -> list[tuple]:
    """Le righe (`COLONNE_DEPOSITI`) di un blocco di depositi (`filings.recent` o un file `-submissions-NNN`)."""
    b = blocco or {}
    forme, date = b.get("form") or [], b.get("filingDate") or []
    accn, rapporto, voci = b.get("accessionNumber") or [], b.get("reportDate") or [], b.get("items") or []
    out = []
    for i, modulo in enumerate(forme):
        if moduli is not None and modulo not in moduli:
            continue
        if i >= len(date) or not date[i]:
            continue
        out.append((cik, accn[i] if i < len(accn) else "", modulo, date[i], (rapporto[i] if i < len(rapporto) else "") or None,
                    (voci[i] if i < len(voci) else "") or ""))
    return out


def _tabella_fatti(righe: list[tuple]):
    import pandas as pd
    df = pd.DataFrame(righe, columns=list(COLONNE_FATTI))
    for c in ("inizio", "fine", "depositato"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["cik"] = df["cik"].astype("int64")
    df["valore"] = df["valore"].astype("float64")
    df["esercizio"] = pd.to_numeric(df["esercizio"], errors="coerce").astype("Int64")
    return df.sort_values(["cik", "voce", "unita", "depositato", "accn", "fine", "inizio"], kind="stable").reset_index(drop=True)


def _tabella_societa(righe: list[tuple]):
    import pandas as pd
    df = pd.DataFrame(righe, columns=list(COLONNE_SOCIETA))
    df["cik"] = df["cik"].astype("int64")
    df["altri_file"] = df["altri_file"].astype("int64")
    return df.sort_values("cik", kind="stable").reset_index(drop=True)


def _tabella_depositi(righe: list[tuple]):
    import pandas as pd
    df = pd.DataFrame(righe, columns=list(COLONNE_DEPOSITI))
    for c in ("depositato", "data_rapporto"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["cik"] = df["cik"].astype("int64")
    return df.sort_values(["cik", "depositato", "accn"], kind="stable").reset_index(drop=True)


class Lettore:
    """Un lettore per processo e per archivio: gli zip si aprono una volta, l'indice dei nomi resta in memoria."""

    def __init__(self, archivio: Path):
        self.cartella = Path(archivio) / CARTELLA
        self._zip: dict[str, zipfile.ZipFile] = {}
        self._nomi: dict[str, frozenset[str]] = {}
        self._manifest: dict | None = None
        self.letture = 0                         # file letti dentro gli zip (i test contano che la cache funzioni)

    # ------------------------------------------------------------------ file e manifest
    def manifest(self) -> dict:
        if self._manifest is None:
            f = self.cartella / "manifest.json"
            if not f.is_file():
                raise FileMancante("manca il manifest dei file SEC (sec_bulk/manifest.json): nessun download implicito, "
                                   "i file in blocco vanno messi a mano (docs/adr/009)")
            try:
                self._manifest = json.loads(f.read_text(encoding="utf-8"))
            except ValueError as e:
                raise FileMancante("il manifest dei file SEC non è JSON valido") from e
        return self._manifest

    def _apri(self, nome: str) -> zipfile.ZipFile:
        if nome not in self._zip:
            voce = self.manifest().get(nome)
            f = self.cartella / FILE[nome]
            if not voce:
                raise FileMancante("{} non è nel manifest dei file SEC".format(FILE[nome]))
            if not f.is_file():
                raise FileMancante("manca {} fra i file SEC in blocco: nessun download implicito (docs/adr/009)".format(FILE[nome]))
            if voce.get("byte") is not None and f.stat().st_size != int(voce["byte"]):
                raise FileMancante("{} ha {} byte, il manifest ne dichiara {}: file troncato o sostituito".format(
                    FILE[nome], f.stat().st_size, voce["byte"]))
            try:
                self._zip[nome] = zipfile.ZipFile(f)
            except zipfile.BadZipFile as e:
                raise FileMancante("{} non è uno zip leggibile".format(FILE[nome])) from e
            self._nomi[nome] = frozenset(self._zip[nome].namelist())
        return self._zip[nome]

    def _json(self, nome: str, membro: str):
        z = self._apri(nome)
        if membro not in self._nomi[nome]:
            return None
        self.letture += 1
        with z.open(membro) as fh:
            return json.load(fh)

    def cik_presenti(self, nome: str = "companyfacts") -> frozenset[int]:
        """I CIK che hanno un file nello zip (per `submissions`: la testata)."""
        if nome not in FILE:
            raise ValueError("file SEC sconosciuto: {!r} (companyfacts o submissions)".format(nome))
        self._apri(nome)
        return frozenset(int(n[3:13]) for n in self._nomi[nome] if n.startswith("CIK") and n[3:13].isdigit() and len(n) == 18)

    # ------------------------------------------------------------------ cache
    def _chiave(self, nome: str, parametri) -> str:
        sha = (self.manifest().get(nome) or {}).get("sha256") or ""
        return hashlib.sha256(json.dumps([VERSIONE_CACHE, nome, sha, parametri], sort_keys=True).encode()).hexdigest()[:20]

    def _con_cache(self, prefisso: str, chiave: str, cik: list[int], leggi, tabella):
        """Righe dei `cik` dalla cache, leggendo dallo zip solo quelli mai cercati. `leggi(cik)` → righe."""
        import pandas as pd
        d = self.cartella / "cache"
        f_dati, f_cik = d / "{}_{}.parquet".format(prefisso, chiave), d / "{}_{}.cik.json".format(prefisso, chiave)
        cercati: set[int] = set()
        df = None
        if f_dati.is_file() and f_cik.is_file():
            try:
                cercati = set(json.loads(f_cik.read_text(encoding="utf-8")))
                df = pd.read_parquet(f_dati)
            except (ValueError, OSError):
                cercati, df = set(), None
        nuovi = [c for c in cik if c not in cercati]
        if nuovi or df is None:
            righe = []
            for c in nuovi:
                righe += leggi(c)
            fresco = tabella(righe)
            df = fresco if df is None or not len(df) else (pd.concat([df, fresco], ignore_index=True) if len(fresco) else df)
            d.mkdir(parents=True, exist_ok=True)
            tmp_d, tmp_c = Path(str(f_dati) + ".tmp"), Path(str(f_cik) + ".tmp")
            df.to_parquet(tmp_d, index=False)
            tmp_c.write_text(json.dumps(sorted(cercati | set(nuovi))), encoding="utf-8")
            os.replace(tmp_d, f_dati)
            os.replace(tmp_c, f_cik)
        return df[df["cik"].isin(cik)].reset_index(drop=True)

    # ------------------------------------------------------------------ letture
    def bilancio(self, cik, voci, cache: bool = False):
        cik = _lista_cik(cik)
        voci = [voci] if isinstance(voci, str) else list(voci)
        if not voci:
            raise ValueError("nessuna voce chiesta")
        complete = sorted({"{}:{}".format(*voce_completa(v)) for v in voci})

        def leggi(c):
            return leggi_fatti(self._json("companyfacts", "CIK{:010d}.json".format(c)), c, complete)

        self._apri("companyfacts")
        if cache:
            df = self._con_cache("fatti", self._chiave("companyfacts", complete), cik, leggi, _tabella_fatti)
            return _tabella_fatti_ordinata(df)
        righe = []
        for c in cik:
            righe += leggi(c)
        return _tabella_fatti(righe)

    def _submissions(self, c: int, moduli, tutti: bool):
        dati = self._json("submissions", "CIK{:010d}.json".format(c))
        if dati is None:
            return None, []
        dep = leggi_depositi((dati.get("filings") or {}).get("recent"), c, moduli)
        if tutti:
            for altro in (dati.get("filings") or {}).get("files") or []:
                blocco = self._json("submissions", altro.get("name") or "")
                dep += leggi_depositi(blocco, c, moduli)
        return leggi_societa(dati, c), dep

    def societa(self, cik, cache: bool = False):
        cik = _lista_cik(cik)

        def leggi(c):
            testa, _ = self._submissions(c, (), False)
            return [testa] if testa else []

        self._apri("submissions")
        if cache:
            return self._con_cache("societa", self._chiave("submissions", "societa"), cik, leggi, _tabella_societa) \
                .sort_values("cik", kind="stable").reset_index(drop=True)
        righe = []
        for c in cik:
            righe += leggi(c)
        return _tabella_societa(righe)

    def depositi(self, cik, moduli=None, tutti: bool = False, cache: bool = False):
        cik = _lista_cik(cik)
        moduli = None if moduli is None else sorted({str(m) for m in ([moduli] if isinstance(moduli, str) else moduli)})

        def leggi(c):
            return self._submissions(c, moduli, tutti)[1]

        self._apri("submissions")
        if cache:
            df = self._con_cache("depositi", self._chiave("submissions", ["depositi", moduli, bool(tutti)]), cik, leggi,
                                 _tabella_depositi)
            return df.sort_values(["cik", "depositato", "accn"], kind="stable").reset_index(drop=True)
        righe = []
        for c in cik:
            righe += leggi(c)
        return _tabella_depositi(righe)


def _tabella_fatti_ordinata(df):
    return df.sort_values(["cik", "voce", "unita", "depositato", "accn", "fine", "inizio"], kind="stable").reset_index(drop=True)


_lettori: dict[str, Lettore] = {}


def lettore(archivio: Path) -> Lettore:
    """Il lettore dell'archivio, uno per processo (gli zip restano aperti)."""
    k = str(Path(archivio))
    if k not in _lettori:
        _lettori[k] = Lettore(Path(archivio))
    return _lettori[k]


def dimentica() -> None:
    """Chiude gli zip aperti (dopo aver sostituito i file, o nei test)."""
    for l_ in _lettori.values():
        for z in l_._zip.values():
            z.close()
    _lettori.clear()
