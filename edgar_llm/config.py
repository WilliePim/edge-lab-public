"""Da dove arrivano i segreti, e da dove non devono arrivare.

DUE POSTI, IN QUEST'ORDINE: l'ambiente del processo, e un file `.env` cercato
risalendo dalle directory sopra questo package. L'ambiente **vince sempre** sul
file: un segreto iniettato da uno scheduler o da una CI deve poter scavalcare un
`.env` vecchio rimasto su disco, e non il contrario. Un file dimenticato che
sovrascrive silenziosamente la chiave giusta e' il modo in cui si passa un
pomeriggio a debuggare un 401.

IL `.env` SI CERCA RISALENDO, e la ragione e' il perimetro. Questo package e'
pubblico; la chiave no. Tenendo il file **sopra** `edgar_llm/` -- alla radice
del repo che lo contiene -- il segreto non sta mai dentro la directory che viene
pubblicata, e non c'e' da fidarsi di un `.gitignore` perche' non c'e' niente da
ignorare. Un `.env` dentro `edgar_llm/` funziona lo stesso, e per un uso
autonomo del package va bene; qui dentro non e' il posto giusto.

Nessuna dipendenza: sono trenta righe e `python-dotenv` non vale un rigo in
requirements.

QUESTO MODULO NON STAMPA MAI UN VALORE. Le funzioni di diagnosi dicono se una
variabile c'e' e quanto e' lunga, mai cosa contiene.
"""

from __future__ import annotations

import os
from pathlib import Path

NOME = ".env"
#  Quante directory risalire prima di arrendersi. Cinque coprono
#  package -> repo -> eventuale cartella di lavoro, e non abbastanza da
#  raccogliere il `.env` di un progetto vicino per sbaglio.
RISALITA = 5

_caricato = False


def trova(start: Path | None = None) -> Path | None:
    """Il primo `.env` risalendo. None se non ce n'e'."""
    base = Path(start or Path(__file__).resolve().parent)
    for _ in range(RISALITA):
        p = base / NOME
        if p.is_file():
            return p
        if base.parent == base:
            break
        base = base.parent
    return None


def parse(testo: str) -> dict:
    """`CHIAVE=valore` per riga. Righe vuote e `#` ignorate."""
    out = {}
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, _, valore = riga.partition("=")
        chiave = chiave.strip()
        if chiave.startswith("export "):
            chiave = chiave[len("export "):].strip()
        valore = valore.strip()
        #  Gli apici sono di chi scrive il file, non parte del valore.
        if len(valore) >= 2 and valore[0] == valore[-1] and valore[0] in "\"'":
            valore = valore[1:-1]
        if chiave:
            out[chiave] = valore
    return out


def load(start: Path | None = None, force: bool = False) -> list:
    """Carica il `.env` nell'ambiente. Restituisce i nomi caricati.

    Idempotente: la seconda chiamata non fa niente, cosi' chiamarla da piu'
    punti d'ingresso non costa una lettura di disco per volta.
    """
    global _caricato
    if _caricato and not force:
        return []
    _caricato = True

    p = trova(start)
    if p is None:
        return []
    try:
        coppie = parse(p.read_text(encoding="utf-8"))
    except OSError:
        return []

    messi = []
    for chiave, valore in coppie.items():
        #  L'ambiente vince. Un valore gia' presente non si tocca.
        if chiave not in os.environ and valore:
            os.environ[chiave] = valore
            messi.append(chiave)
    return messi


def get(nome: str, default: str = "") -> str:
    load()
    return os.environ.get(nome) or default


def stato() -> list:
    """(nome, presente, lunghezza) per la diagnosi. MAI il valore."""
    load()
    out = []
    for nome in ("EDGAR_USER_AGENT", "FORM4_USER_AGENT", "ANTHROPIC_API_KEY",
                 "ANTHROPIC_WORKSPACE_ID", "EDGAR_LLM_MODE"):
        v = os.environ.get(nome) or ""
        out.append((nome, bool(v), len(v)))
    return out


def main(argv=None) -> int:
    """`python -m edgar_llm.config` — dice cosa c'e', senza dire cosa vale."""
    import argparse

    ap = argparse.ArgumentParser(description="cosa vede il codice")
    ap.add_argument("--prova", action="store_true",
                    help="fa UNA chiamata minima all'API per verificare che "
                         "le credenziali funzionino davvero")
    a = ap.parse_args(argv)
    p = trova()
    print("file .env: {}".format(p if p else "nessuno trovato"))
    print()
    for nome, presente, n in stato():
        print("  {:<20} {:<10} {}".format(
            nome, "presente" if presente else "ASSENTE",
            "{} caratteri".format(n) if presente else ""))
    print()
    ua = os.environ.get("EDGAR_USER_AGENT") or os.environ.get("FORM4_USER_AGENT")
    print("EDGAR:    {}".format(
        "pronto" if ua and "@" in ua else "manca un User-Agent con nome ed email"))
    print("modello:  {}".format(
        "pronto" if os.environ.get("ANTHROPIC_API_KEY")
        else "nessuna chiave — si puo' girare solo in EDGAR_LLM_MODE=replay"))

    if not a.prova:
        print()
        print("(`--prova` fa una chiamata vera: e' l'unico modo di sapere "
              "se la chiave funziona. Le altre righe qui sopra dicono solo "
              "che c'e' scritto qualcosa.)")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print()
        print("PROVA SALTATA: nessuna chiave da provare.")
        return 1

    from .client import LLMClient, ModelUnavailable

    print()
    print("chiamata di prova...")
    try:
        u = LLMClient().ping()
    except ModelUnavailable as e:
        print("  FALLITA — {}".format(e))
        return 1
    print("  OK: {} ha risposto ({} token in, {} out)".format(
        u["model"], u["input_tokens"], u["output_tokens"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
