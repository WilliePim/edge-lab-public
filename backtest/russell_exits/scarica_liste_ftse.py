"""Russell 2000, uscite verso il basso — scarica le liste ufficiali FTSE Russell delle cancellazioni.

Serve al controllo dei falsi positivi anno per anno (addendum del 21-09-2026). Una lista vale solo se è la
**finale** della ricostituzione di giugno di quell'anno: non le preliminari di maggio, non gli aggiornamenti di
metà giugno, non le aggiunte.

## Come si riconosce la finale

Non dal nome del file, e nemmeno dal titolo. Nel 2025 sono usciti tre file di cancellazioni (23 maggio, 30 maggio,
27 giugno) distinti solo dalla data nel nome; nel 2016 la preliminare e la finale hanno **lo stesso indirizzo**,
perché FTSE ha sovrascritto il file, e si distinguono solo perché l'archivio del web ne conserva due copie. Il
titolo dichiarato è inutile: nel 2023 il file delle cancellazioni e quello delle aggiunte si chiamano tutti e due
«Reconstitution».

Quello che distingue è la **data di creazione nei metadati del PDF**, che in ogni anno controllato coincide con il
giorno della ricostituzione:

| anno | fonte | creato il | ricostituzione |
|---|---|---|---|
| 2016 | archivio del web, copia del 30-06 | 2016-06-24 | 2016-06-24 |
| 2016 | archivio del web, copia del 21-06 | 2016-06-17 | *(preliminare, scartata)* |
| 2017 | archivio del web | 2017-06-23 | 2017-06-23 |
| 2021 | archivio del web | 2021-06-25 | 2021-06-25 |
| 2022 | archivio del web | 2022-06-24 | 2022-06-24 |
| 2023 | lseg.com | 2023-06-23 | 2023-06-23 |
| 2024 | lseg.com | 2024-06-28 | 2024-06-28 |
| 2025 | lseg.com (già nel repo) | 2025-06-27 | 2025-06-27 |

In più si controlla che la lista sia **disgiunta** da quella delle aggiunte dello stesso giorno, quando le aggiunte
si scaricano: è l'unico modo di essere sicuri di non aver preso il file sbagliato, visto che i titoli non aiutano.

## Anni senza lista finale

**2018 e 2019**: non esistono nell'archivio del web né su lseg.com. **2020**: esiste solo l'aggiornamento del
19 giugno (`ru3000_deletions_20200619.pdf`), e la ricostituzione era il 26. Quegli anni restano **non
controllati**, e questo va detto: non sono anni senza falsi positivi.

## Come sono stati trovati gli indirizzi

Gli anni recenti su lseg.com hanno un nome prevedibile (`ru3000-deletions[-final]-AAAAMMGG.pdf`) e si provano.
Gli anni vecchi stavano su `ftserussell.com`, con nomi cambiati due volte, e si sono trovati interrogando
l'indice dell'archivio del web (`web.archive.org/cdx`) sul dominio. Gli indirizzi verificati sono scritti qui
sotto invece di essere indovinati ogni volta.

    python backtest/russell_exits/scarica_liste_ftse.py            # scarica quello che manca
    python backtest/russell_exits/scarica_liste_ftse.py --elenco   # dice solo che cosa c'è e che cosa manca
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CARTELLA = ROOT / "state" / "backfill" / "russell" / "liste"
DATE = HERE / "date_ricostituzione.csv"

sys.path.insert(0, str(HERE))
import lista_ftse_pdf as L  # noqa: E402

AGENTE = "edge-lab ricerca accademica"
LSEG = "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/"
ARCHIVIO = "https://web.archive.org/web/{istante}id_/{url}"
PAUSA = 1.5
GIORNI_DI_SCARTO = 2            # la data di creazione deve coincidere con la ricostituzione, o quasi
RIGHE_MINIME = 50
SOVRAPPOSIZIONE_MASSIMA = 0.02  # cancellazioni e aggiunte dello stesso giorno non si somigliano

#  anno -> (indirizzo delle cancellazioni, indirizzo delle aggiunte per il controllo incrociato o None)
FONTI = {
    2016: (ARCHIVIO.format(istante="20160630015402",
                           url="http://www.ftserussell.com/files/support-documents/russell-3000-index-2016-deletions"),
           ARCHIVIO.format(istante="20160621133709",
                           url="http://www.ftserussell.com/files/support-documents/russell-3000-index-2016-additions")),
    2017: (ARCHIVIO.format(istante="20180201202107",
                           url="http://www.ftserussell.com/files/support-documents/final-r3000-deletions-2017"),
           ARCHIVIO.format(istante="20180201200920",
                           url="http://www.ftserussell.com/files/support-documents/final-r3000-additions-2017")),
    2021: (ARCHIVIO.format(istante="20210626025026",
                           url="https://content.ftserussell.com/sites/default/files/ru3000_deletions_20210625.pdf"),
           ARCHIVIO.format(istante="20210625230319",
                           url="https://content.ftserussell.com/sites/default/files/ru3000_additions_20210625.pdf")),
    2022: (ARCHIVIO.format(istante="20220625012025",
                           url="https://content.ftserussell.com/sites/default/files/ru3000_deletions_20220624.pdf"),
           ARCHIVIO.format(istante="20220627135943",
                           url="https://content.ftserussell.com/sites/default/files/ru3000_additions_20220624.pdf")),
    2023: (LSEG + "ru3000-deletions-final-20230623.pdf", LSEG + "ru3000-additions-final-20230623.pdf"),
    2024: (LSEG + "ru3000-deletions-final-20240628.pdf", LSEG + "ru3000-additions-final-20240628.pdf"),
}
#  Il 2025 sta già nel repo da prima, con un altro nome.
GIA_NEL_REPO = {2025: ROOT / "state" / "backfill" / "russell" / "ru3000-deletions-20250627.pdf"}
SENZA_LISTA = {
    2018: "nessuna lista nell'archivio del web né su lseg.com",
    2019: "nessuna lista nell'archivio del web né su lseg.com (esiste l'elenco dei membri al 1° luglio)",
    2020: "esiste solo l'aggiornamento del 19 giugno, la ricostituzione era il 26",
}


def ricostituzioni() -> dict[int, dt.date]:
    fuori = {}
    with DATE.open(encoding="utf-8") as f:
        for riga in csv.DictReader(f):
            try:
                fuori[int(riga["anno"])] = dt.date.fromisoformat(riga["ricostituzione"])
            except ValueError:
                continue                                  # la riga «2026-12» non è un anno solare
    return fuori


def scarica(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    for tentativo in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read() if r.status == 200 else None
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(5 * (tentativo + 1))
                continue
            return None
        except (urllib.error.URLError, OSError):
            time.sleep(3 * (tentativo + 1))
    return None


def verifica(pdf: Path, ricostituzione: dt.date, aggiunte: set[str] | None) -> tuple[bool, str]:
    """(va bene, perché). Data di creazione dai metadati, righe leggibili, e disgiunzione dalle aggiunte."""
    _titoli, data = L.titolo_e_data(pdf)
    if not data:
        return False, "senza data di creazione nei metadati"
    creato = dt.date(int(data[:4]), int(data[4:6]), int(data[6:8]))
    scarto = (creato - ricostituzione).days
    if abs(scarto) > GIORNI_DI_SCARTO:
        return False, "creato il {} ({:+d} giorni dalla ricostituzione): non è la lista finale".format(creato, scarto)
    righe = L.righe(pdf)
    if len(righe) < RIGHE_MINIME:
        return False, "solo {} righe lette: il formato non è quello atteso".format(len(righe))
    simboli = {r["simbolo"] for r in righe}
    nota = ""
    if aggiunte:
        comuni = simboli & aggiunte
        quota = len(comuni) / len(simboli)
        if quota > SOVRAPPOSIZIONE_MASSIMA:
            return False, "{} simboli su {} stanno anche fra le aggiunte: è la lista sbagliata".format(
                len(comuni), len(simboli))
        nota = ", disgiunta dalle aggiunte ({} in comune su {})".format(len(comuni), len(simboli))
    return True, "creato il {}, {} società{}".format(creato, len(righe), nota)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--elenco", action="store_true", help="dice solo che cosa c'è e che cosa manca")
    a = ap.parse_args(argv)
    CARTELLA.mkdir(parents=True, exist_ok=True)
    date = ricostituzioni()
    uscita = 0

    for anno, percorso in sorted(GIA_NEL_REPO.items()):
        ok, perche = verifica(percorso, date[anno], None) if percorso.exists() else (False, "il file non c'è")
        print("{}  {} {}".format(anno, "già nel repo:" if ok else "PROBLEMA:", perche))
        uscita |= 0 if ok else 1

    for anno in sorted(FONTI):
        atteso = CARTELLA / "ru3000-deletions-{}.pdf".format(anno)
        url_canc, url_agg = FONTI[anno]
        if atteso.exists():
            ok, perche = verifica(atteso, date[anno], None)
            print("{}  {} {}".format(anno, "già scaricata:" if ok else "SCARTATA:", perche))
            uscita |= 0 if ok else 1
            continue
        if a.elenco:
            print("{}  manca".format(anno))
            continue
        aggiunte = None
        if url_agg:
            corpo = scarica(url_agg)
            time.sleep(PAUSA)
            if corpo and corpo.startswith(b"%PDF"):
                tmp = CARTELLA / "aggiunte-{}.pdf".format(anno)
                tmp.write_bytes(corpo)
                aggiunte = {r["simbolo"] for r in L.righe(tmp)}
                tmp.unlink()
        corpo = scarica(url_canc)
        time.sleep(PAUSA)
        if not corpo or not corpo.startswith(b"%PDF"):
            uscita |= 1
            print("{}  NON SCARICATA da {}".format(anno, url_canc[:90]))
            continue
        atteso.write_bytes(corpo)
        ok, perche = verifica(atteso, date[anno], aggiunte)
        if not ok:
            atteso.unlink()
            uscita |= 1
        print("{}  {} {}".format(anno, "scaricata:" if ok else "SCARTATA:", perche))

    for anno, perche in sorted(SENZA_LISTA.items()):
        print("{}  non controllabile: {}".format(anno, perche))
    return uscita


if __name__ == "__main__":
    raise SystemExit(main())
