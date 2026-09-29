"""Il client SEC: cache su disco, formato compresso, e quello che NON chiede alla rete.

Questo modulo non aveva test. Non li aveva perche' ogni suite gli sostituisce un
finto: comodo per il resto, ma vuol dire che la cache -- l'unica ragione per cui un
secondo giro nello stesso giorno dura minuti invece di un'ora -- non era coperta da
niente. Qui non si tocca la rete: la sessione e' finta e conta le chiamate.
"""
import gzip
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.edgar import EdgarClient


class Risposta:
    def __init__(self, status_code=200, text="corpo"):
        self.status_code = status_code
        self.text = text


class Sessione:
    """Sessione finta: registra gli URL chiesti e risponde come le si dice."""

    def __init__(self, risposte=None):
        self.chiesti = []
        self.risposte = risposte or {}

    def get(self, url, timeout=None):
        self.chiesti.append(url)
        return self.risposte.get(url, Risposta())


def client(tmp, risposte=None):
    c = EdgarClient("Nome Cognome nome@example.com", cache_dir=tmp)
    c.session = Sessione(risposte)
    c.min_interval = 0.0          # i test non aspettano la SEC
    return c


with tempfile.TemporaryDirectory() as tmp:
    print("[edgar] una risposta scaricata si rilegge dal disco, non dalla rete")
    c = client(tmp)
    primo = c.get("https://www.sec.gov/uno")
    secondo = c.get("https://www.sec.gov/uno")
    check("il corpo torna identico", (primo, secondo) == ("corpo", "corpo"),
          str((primo, secondo)))
    check("la rete e' stata toccata una volta sola", len(c.session.chiesti) == 1,
          str(c.session.chiesti))
    check("il secondo giro e' contato come cache",
          (c.stats["network"], c.stats["cache"]) == (1, 1), str(dict(c.stats)))

    print("[edgar] la cache si scrive compressa")
    p = c._cache_path("https://www.sec.gov/uno")
    check("il file in chiaro non esiste", not p.exists(), str(p))
    gz = p.with_suffix(".cache.gz")
    check("il file compresso esiste", gz.exists(), str(gz))
    check("...e contiene proprio quel corpo",
          gzip.decompress(gz.read_bytes()).decode() == "corpo")
    #  Misurato sulla cache vera: 19,5 GB in chiaro, circa 1,7 compressi. Su un
    #  disco che si e' gia' riempito due volte questo mese non e' un dettaglio.
    check("comprimere serve: un corpo ripetitivo diventa piu' piccolo dell'originale",
          len(gzip.compress(b"ownershipDocument" * 500)) < 500 * len("ownershipDocument"))

with tempfile.TemporaryDirectory() as tmp:
    print("[edgar] i file in chiaro gia' sul disco continuano a valere")
    c = client(tmp)
    vecchio = c._cache_path("https://www.sec.gov/vecchio")
    vecchio.write_text("scaricato prima della compressione", encoding="utf-8")
    check("una voce vecchia si legge ancora",
          c.get("https://www.sec.gov/vecchio") == "scaricato prima della compressione")
    check("...senza chiedere niente alla rete", c.session.chiesti == [],
          str(c.session.chiesti))

    print("[edgar] una cache troncata si riscarica invece di rompere il giro")
    rotto = c._cache_path("https://www.sec.gov/rotto")
    rotto.with_suffix(".cache.gz").write_bytes(b"non e' gzip")
    check("il corpo arriva dalla rete", c.get("https://www.sec.gov/rotto") == "corpo")
    check("...e la rete e' stata chiamata", c.session.chiesti == ["https://www.sec.gov/rotto"],
          str(c.session.chiesti))

with tempfile.TemporaryDirectory() as tmp:
    print("[edgar] un 404 e' una risposta, non un errore da ripetere")
    url = "https://www.sec.gov/manca"
    c = client(tmp, {url: Risposta(404, "")})
    check("404 -> None", c.get(url) is None)
    check("...chiesto una volta sola, senza ritentare", len(c.session.chiesti) == 1,
          str(c.session.chiesti))
    check("...e non finisce in cache", not c._cache_path(url).with_suffix(".cache.gz").exists())

    print("[edgar] l'indice di oggi non si mette in cache")
    #  Il file della SEC si riempie durante la giornata: metterlo in cache
    #  congelerebbe un indice a meta'.
    c2 = client(tmp)
    c2.get("https://www.sec.gov/di-oggi", use_cache=False)
    check("niente file scritto", not c2._cache_path("https://www.sec.gov/di-oggi")
          .with_suffix(".cache.gz").exists())
    c2.get("https://www.sec.gov/di-oggi", use_cache=False)
    check("...e ogni giro rilegge davvero", len(c2.session.chiesti) == 2,
          str(c2.session.chiesti))

sys.exit(report("ALL EDGAR TESTS PASSED"))
