"""Le finestre su file, per poterle leggere in un editor invece che nel terminale.

Una finestra e' venti-quaranta mila caratteri: dieci-venti pagine. In una
console non si torna indietro, non si cerca, non si tiene il segno. Chi
etichetta cento documenti leggendo a scorrimento non sta leggendo: sta
scremando, e le etichette che ne escono misurano la sua pazienza.

Quindi il testo esce su file, uno per documento, e la CLI stampa il percorso
prima di chiedere. Si legge di la', si risponde di qua.

IL FILE CONTIENE ESATTAMENTE CIO' CHE RICEVE IL MODELLO, delimitatori
compresi: e' la stessa stringa, non una sua resa. Se divergessero, chi
etichetta risponderebbe a un testo diverso da quello estratto, e l'attribuzione
dentro/fuori finestra delle evals -- che confronta il valore vero con le
finestre inviate -- misurerebbe la differenza fra due tagli invece che la
qualita' di uno. `finestre_da_file` rilegge il file e `test_sessione.py`
verifica l'uguaglianza carattere per carattere.

DOVE FINISCONO. Fuori dal package, in una directory di stato: contengono il
testo di depositi SEC e non hanno niente da fare in un mirror pubblico. Il
percorso predefinito e' `<sopra il package>/state/edgar_llm/sessioni/<data>/`,
sovrascrivibile con `--out-dir`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

#  Sopra il package, mai dentro: `edgar_llm/` e' cio' che viene pubblicato.
BASE = Path(__file__).resolve().parents[1] / "state" / "edgar_llm" / "sessioni"

INIZIO = "<!-- INIZIO FINESTRE -->"
FINE = "<!-- FINE FINESTRE -->"
INDICE = "INDICE.md"

DA_FARE = "da fare"
ETICHETTATO = "etichettato"
SALTATO = "saltato"
ILLEGGIBILE = "illeggibile"

_NON_NOME = re.compile(r"[^A-Za-z0-9._-]+")


class FinestreNonEsportabili(RuntimeError):
    """Il testo contiene i delimitatori, e il file non sarebbe rileggibile."""


def dir_sessione(base=None, giorno=None) -> Path:
    giorno = giorno or date.today()
    return Path(base or BASE) / giorno.isoformat()


def ticker_di(client, cik: str) -> str:
    """Il primo ticker dalle submissions, o il CIK. Serve solo al nome del file."""
    try:
        d = client.submissions(cik) or {}
    except Exception:                                          # noqa: BLE001
        return str(cik)
    t = (d.get("tickers") or [None])[0]
    return _NON_NOME.sub("", str(t)) if t else str(cik)


def nome_file(n: int, filing, ticker: str) -> str:
    """Un nome che si legge in un elenco di file e che nessun filesystem rifiuta.

    OGNI pezzo si sanifica, ticker compreso. `ticker_di` lo ripulisce gia', ma
    questa funzione accetta una stringa da chiunque: un `/` non sanificato non
    darebbe un nome brutto, darebbe una sottodirectory -- o un errore, a
    seconda del sistema.
    """
    forma = "8-K-2.01" if getattr(filing, "is_ma_8k", False) else filing.form
    return "{:02d}_{}_{}_{}.md".format(
        n, _NON_NOME.sub("-", forma), _NON_NOME.sub("-", ticker or filing.cik),
        _NON_NOME.sub("-", filing.accession))


def esporta(n: int, filing, ticker: str, nome_emittente: str,
            testo: str, finestre: str, out_dir) -> Path:
    """Scrive il file del documento. Restituisce il percorso."""
    if INIZIO in finestre or FINE in finestre:
        #  Non e' mai successo su un filing vero, e se succedesse il file non
        #  sarebbe piu' rileggibile: meglio fermarsi che scrivere qualcosa che
        #  si rileggera' troncato senza dirlo.
        raise FinestreNonEsportabili(
            "il testo contiene un delimitatore: {}".format(filing.accession))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / nome_file(n, filing, ticker)

    resa = len(finestre) / len(testo) if testo else 0.0
    intestazione = [
        "# {} · {} · {}".format(
            "8-K item 2.01" if getattr(filing, "is_ma_8k", False)
            else filing.form, ticker or "—", filing.filed),
        "",
        "| | |",
        "|---|---|",
        "| emittente | {} |".format(nome_emittente or "—"),
        "| ticker | {} |".format(ticker or "—"),
        "| CIK | {} |".format(filing.cik),
        "| accession | `{}` |".format(filing.accession),
        "| forma | {} |".format(filing.form),
        "| depositato | {} |".format(filed_o_trattino(filing)),
        "| documento | {} |".format(filing.primary_document or "—"),
        "| su EDGAR | {} |".format(filing.url),
        "",
        "Documento **{:,} caratteri**, finestre **{:,}** ({:.1%}).".format(
            len(testo), len(finestre), resa),
        "",
        "Sotto i delimitatori c'e' **esattamente** il testo mandato al modello, "
        "tagli compresi. I salti sono segnati in chiaro: dove compare "
        "`[... testo omesso ...]` manca del documento, e una risposta che si "
        "puo' dare solo leggendo la parte mancante e' un `null`, non una "
        "deduzione.",
        "",
        INIZIO,
    ]
    p.write_text("\n".join(intestazione) + "\n" + finestre + "\n" + FINE + "\n",
                 encoding="utf-8")
    return p


def filed_o_trattino(filing) -> str:
    return filing.filed or "—"


def finestre_da_file(p) -> str:
    """Il testo fra i delimitatori: esattamente cio' che e' stato esportato."""
    s = Path(p).read_text(encoding="utf-8")
    i = s.index(INIZIO) + len(INIZIO) + 1        # +1: il ritorno a capo dopo
    j = s.index(FINE) - 1                        # -1: il ritorno a capo prima
    return s[i:j]


def scrivi_indice(out_dir, voci) -> Path:
    """`voci` = [(n, filing, ticker, nome_file, stato, note)]. Riscritto ogni volta."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fatti = sum(1 for v in voci if v[4] == ETICHETTATO)

    L = ["# Sessione di etichettatura — {}".format(out_dir.name), "",
         "**{} etichettati** su {}. ".format(fatti, len(voci)),
         "", "Si legge il file, si risponde nella CLI. Invio vuoto = «il "
         "documento non lo dice», che e' una risposta.", "",
         "| # | stato | forma | ticker | file | note |",
         "|---:|---|---|---|---|---|"]
    for n, filing, ticker, nome, stato, note in voci:
        forma = "8-K/2.01" if getattr(filing, "is_ma_8k", False) else filing.form
        L.append("| {} | {} | {} | {} | [{}]({}) | {} |".format(
            n, stato, forma, ticker or "—", nome, nome, note or ""))
    L += ["", "I file contengono testo di depositi SEC. Vivono sotto `state/`, "
          "che e' ignorato da git: non entrano in nessun repository.", ""]

    p = out_dir / INDICE
    p.write_text("\n".join(L), encoding="utf-8")
    return p
