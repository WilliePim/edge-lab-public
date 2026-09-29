"""La guardia che sta fra questo package e un repo pubblico.

Tutto cio' che sta dentro `edgar_llm/` e' pubblico per definizione, e una
regola che dipende dalla disciplina di chi committa non e' una regola. Questo
script FA FALLIRE la pubblicazione: esce 1, e chi lo lancia non pubblica.

Tre famiglie di controlli.

STRUTTURALI, sempre attivi e senza configurazione: indirizzi email, path
assoluti di qualcuno, chiavi API, identificativi di spazio di lavoro, e pochi
termini generici di un uso operativo (watchlist, registro e classi dei
verdetti) che non hanno niente a che fare con l'estrazione da un filing.

COLLEGAMENTI: un link markdown relativo che risolve FUORI dalla radice del
package. Un mirror pubblica solo questa directory, quindi un link che esce
punta a un file che il lettore pubblico non ha -- e ne rivela l'esistenza.

DA LISTA, opzionali: i ticker e i termini privati che qualcuno non vuole veder
comparire -- nomi di progetti, termini del proprio processo di investimento.
La lista arriva da un file (`--deny-file`), mai dal codice: un termine privato
scritto qui dentro sarebbe esso stesso la cosa da non pubblicare. Il confronto
non distingue maiuscole e minuscole e rispetta il confine di parola.

    python -m edgar_llm.tools.perimeter_check
    python -m edgar_llm.tools.perimeter_check --deny-file lista.txt

CHI SORVEGLIA IL SORVEGLIANTE. Ogni controllo ha uno slug e una FIXTURE
POSITIVA: un file sintetico che DEVE farlo scattare. `self_check()` gira prima
di ogni scansione e rifiuta un pattern che non compili o che contenga un
carattere di controllo. Il perche' sta in
`docs/postmortems/PM-001-the-silent-guard.md`: un pattern rotto non fallisce,
tace, e una guardia muta ha lo stesso aspetto di una guardia che non trova
niente.

L'unico caso studio ammesso con nome e' ITT/SPX FLOW, che e' un esempio tecnico
di falso positivo e non una posizione: sta in AMMESSI.
"""

from __future__ import annotations

import argparse
import re
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#  Estensioni che una persona legge. I binari non si ispezionano: se ce n'e'
#  uno qui dentro e' gia' un problema suo, segnalato a parte.
TESTUALI = {".py", ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".ini",
            ".cfg", ".toml", ".sh", ".example", ""}

#  Nomi che possono comparire perche' sono il caso studio dichiarato.
AMMESSI = ("ITT", "SPX FLOW", "SPX")

#  (slug, pattern, perche'). Lo slug fa due cose che una descrizione in
#  italiano non puo' fare: lega un pattern alla sua fixture, e resta stabile
#  quando la descrizione cambia. Due pattern possono condividere il perche' --
#  i termini del processo lo fanno -- e non possono condividere lo slug.
STRUTTURALI = (
    ("email", r"[\w.+-]+@[\w-]+\.[\w.]+", "indirizzo email"),
    #  Tre forme, non una: il path come si scrive a mano, come finisce dentro
    #  un sorgente Python con i backslash raddoppiati, e con le barre girate.
    #  La prima versione cercava un backslash singolo e mancava proprio la
    #  forma che un path assoluto assume quando qualcuno lo incolla in codice.
    ("path-windows", r"[A-Za-z]:[\\/]+Users[\\/]", "path assoluto Windows"),
    ("path-posix", r"/(?:home|Users)/[a-z]", "path assoluto POSIX"),
    ("chiave-api", r"sk-ant-[A-Za-z0-9_-]{8}", "chiave API in chiaro"),
    #  Aggiunto dopo un quasi-incidente: un id reale di spazio di lavoro era
    #  finito dentro `.env.example`, file TRACCIATO e dentro il perimetro. Non
    #  era ancora stato committato. Non e' una credenziale, ma identifica
    #  un'organizzazione e non ha niente da fare in un modello.
    ("workspace-id", r"\bwrkspc_[A-Za-z0-9_-]{6,}", "id di spazio di lavoro"),
    #  I termini del proprio processo di investimento NON si scrivono qui: un
    #  pattern che li nomina li pubblica. Vanno nel --deny-file, come i ticker.
    ("watchlist", r"(?i)\bwatchlist\b", "riferimento alla watchlist"),
    ("registro-verdetti", r"verdicts\.jsonl", "registro dei verdetti"),
    ("classe-verdetto", r"\bSTRONG_BUY\b", "classe di verdetto"),
    #  Il perimetro non nomina il progetto che lo contiene, nemmeno quando ne
    #  parla: il package deve poter vivere da solo, e il nome dell'ospite non
    #  serve a chi lo legge. Nove occorrenze erano gia' entrate negli ADR e in
    #  edgar.py prima che questo controllo esistesse, e sono state riscritte in
    #  forma astratta. I nomi di altri progetti privati NON si scrivono qui:
    #  scritti in un pattern sarebbero essi stessi la fuga. Vanno nella lista
    #  (--deny-file), come i ticker.
    ("nome-repo-privato", r"(?i)\bform4[-_]scanner\b",
     "nome del package ospite che contiene questo package"),
    ("campo-punteggio", r"\bscore_v3\b", "campo della pipeline privata"),
)

#  Il controllo sui collegamenti NON e' una regex sul testo: risolve il
#  bersaglio contro la posizione del file e guarda dove finisce. Un `](../` a
#  occhio sembra una violazione e quasi sempre non lo e' -- `docs/evals/` che
#  rimanda a `docs/adr/` deve poterlo fare -- mentre `](../../altro-package/)`
#  e' la cosa vera da fermare. Cercare la stringa segnalerebbe i tre link
#  interni legittimi che questa documentazione ha gia', e un controllo che
#  segnala cio' che e' corretto viene disattivato dopo la seconda volta.
SLUG_LINK = "link-fuori-perimetro"
PERCHE_LINK = "collegamento fuori dal perimetro"
_LINK_MD = re.compile(r"\]\(([^)\s]+)")

#  Le fixture positive vivono qui e sono ESCLUSE dalla scansione: sono file il
#  cui scopo e' violare, e senza l'esclusione la pubblicazione fallirebbe
#  sempre. L'esclusione e' per percorso esatto, non per nome, ed e' sorvegliata
#  a sua volta: `test_perimeter.py` verifica che la directory contenga
#  ESATTAMENTE le fixture dichiarate, cosi' non ci si puo' nascondere dentro
#  nient'altro.
FIXTURES = ("tests", "fixtures", "perimetro")
FIXTURES_DIR = ROOT / Path(*FIXTURES)

#  I DUE FILE CHE DEVONO CONTENERE CIO' CHE VIETANO: la guardia, che elenca i
#  pattern, e la sua suite, che li prova uno per uno. Sono nominati per intero e
#  non per directory o estensione: "salta i test" sarebbe un buco largo quanto
#  la cartella dei test.
ESENTI = ("perimeter_check.py", "test_perimeter.py")

Riscontro = namedtuple("Riscontro", "file riga slug perche frammento")


class PatternRotto(RuntimeError):
    """Un pattern che non puo' funzionare. Vedi PM-001."""


def self_check() -> None:
    """Rifiuta i pattern che non possono trovare niente. Gira PRIMA di scandire.

    Sta qui e non solo nella suite perche' la pipeline del mirror lancia questa
    guardia, non pytest: un controllo che vale soltanto quando qualcuno si
    ricorda di far girare i test non protegge una pubblicazione.
    """
    visti = set()
    for slug, pat, _perche in STRUTTURALI:
        if slug in visti:
            raise PatternRotto("slug duplicato: {}".format(slug))
        visti.add(slug)
        #  La classe intera di guasti di PM-001: un livello di escape di
        #  troppo trasforma `\b` in un backspace letterale, invisibile nel
        #  sorgente, e il pattern smette di trovare qualsiasi cosa senza dirlo.
        ctrl = [(i, hex(ord(c))) for i, c in enumerate(pat) if ord(c) < 0x20]
        if ctrl:
            raise PatternRotto(
                "{}: carattere di controllo nel pattern {} -> {}".format(
                    slug, pat.encode("unicode_escape").decode(), ctrl))
        try:
            re.compile(pat)
        except re.error as e:
            raise PatternRotto("{}: regex non valida: {}".format(slug, e)) from e


def slugs() -> tuple:
    """Ogni controllo che deve avere una fixture positiva."""
    return tuple(s for s, _, _ in STRUTTURALI) + (SLUG_LINK,)


def _e_una_dichiarazione(path: Path) -> bool:
    return path.name in ESENTI


def _ammesso(frammento: str) -> bool:
    """Il caso studio dichiarato, e il segnaposto del file di esempio.

    NON esiste piu' un'esenzione generica per la parola «example»: esentava
    anche `sk-ant-EXAMPLEKEY`, cioe' esattamente la forma che avrebbe una
    chiave finta -- o una vera camuffata da finta.
    """
    if any(a.lower() in frammento.lower() for a in AMMESSI):
        return True
    return "tu@dominio" in frammento


def leggi_deny(path: str | None) -> list[str]:
    if not path:
        return []
    out = []
    for riga in Path(path).read_text(encoding="utf-8").splitlines():
        t = riga.strip().upper()
        if t and not t.startswith("#") and t not in AMMESSI:
            out.append(t)
    return out


def _e_una_fixture(f: Path, root: Path) -> bool:
    try:
        parti = f.relative_to(root).parts
    except ValueError:
        return False
    return parti[:len(FIXTURES)] == FIXTURES


def _link_fuori(f: Path, riga: str, radice: Path) -> str | None:
    """Il primo bersaglio che risolve fuori dalla radice, o None."""
    for m in _LINK_MD.finditer(riga):
        t = m.group(1)
        if t.startswith(("http://", "https://", "mailto:", "#")):
            continue
        try:
            dest = (f.parent / t).resolve()
        except (OSError, ValueError):
            continue
        if dest != radice and radice not in dest.parents:
            return t
    return None


def scan(root, deny: list[str], skip_fixtures: bool = True) -> list:
    """Ogni violazione trovata sotto `root`, come lista di `Riscontro`."""
    self_check()
    root = Path(root).resolve()
    trovati = []
    for f in sorted(root.rglob("*")):
        #  Le directory generate non sono sorgente e non si pubblicano.
        if not f.is_file() or any(
                part.startswith(("__pycache__", ".pytest_cache", ".git"))
                for part in f.parts):
            continue
        if skip_fixtures and _e_una_fixture(f, root):
            continue
        if f.suffix not in TESTUALI:
            trovati.append(Riscontro(f, 0, "binario", "file non testuale",
                                     f.suffix))
            continue
        if _e_una_dichiarazione(f):
            continue
        try:
            righe = f.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            trovati.append(Riscontro(f, 0, "illeggibile",
                                     "file non decodificabile", ""))
            continue

        for n, riga in enumerate(righe, 1):
            for slug, pat, perche in STRUTTURALI:
                m = re.search(pat, riga)
                if m and not _ammesso(m.group(0)):
                    trovati.append(Riscontro(f, n, slug, perche,
                                             m.group(0)[:60]))
            if f.suffix == ".md":
                fuori = _link_fuori(f, riga, root)
                if fuori:
                    trovati.append(Riscontro(f, n, SLUG_LINK, PERCHE_LINK,
                                             fuori[:60]))
            for t in deny:
                #  Confine di parola: "ADC" non deve scattare dentro "ADCs".
                #  Maiuscole indifferenti: un termine privato scritto in
                #  minuscolo nel testo e' la stessa fuga.
                if re.search(r"\b{}\b".format(re.escape(t)), riga, re.I):
                    trovati.append(Riscontro(f, n, "ticker",
                                             "ticker in lista di esclusione", t))
    return trovati


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--deny-file", default=None,
                    help="un termine per riga: ticker o termini privati da "
                         "non pubblicare (maiuscole indifferenti)")
    a = ap.parse_args(argv)

    try:
        self_check()
    except PatternRotto as e:
        print("GUARDIA ROTTA — {}\n\nUn pattern che non puo' trovare niente e' "
              "peggio di nessun pattern: tace invece di fallire. Vedi "
              "docs/postmortems/PM-001-the-silent-guard.md.".format(e))
        return 2

    deny = leggi_deny(a.deny_file)
    trovati = scan(a.root, deny)

    if not trovati:
        print("perimetro pulito: {} ({} controlli, {} termini in lista)".format(
            a.root, len(slugs()), len(deny)))
        return 0

    print("PERIMETRO VIOLATO — {} riscontri, la pubblicazione si ferma\n"
          .format(len(trovati)))
    for r in trovati:
        try:
            rel = r.file.relative_to(Path(a.root).resolve())
        except ValueError:
            rel = r.file
        print("  {}:{}  [{}] {} -> {!r}".format(
            rel, r.riga, r.slug, r.perche, r.frammento))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
