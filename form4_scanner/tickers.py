"""Il simbolo di borsa di un emittente, risolto sul CIK e non sul simbolo.

IL PROBLEMA. Il ticker di un Form 4 lo scrive il DEPOSITANTE, nel campo
`issuerTradingSymbol` dell'XML, e non c'e' niente che lo obblighi a essere
aggiornato. Il CIK 0001844971 deposita ancora come `GREE` -- Greenidge
Generation -- mentre EDGAR quel CIK lo elenca come `VIP`, Vulcan Infrastructure
& Power. Il nome nel report era quello nuovo e il simbolo quello vecchio, presi
dallo stesso file.

Non e' cosmetica: i prezzi si cercano in `prices/{ticker}.csv`. Un simbolo
stantio interroga una serie morta, e la societa' risulta senza prezzi -- cioe'
finisce fra i delistati presunti, che e' la variabile che domina ogni misura di
questo corpus.

Il CIK invece non cambia mai. E' l'identita', e il simbolo e' un attributo.

PERCHE' NON SI SOSTITUISCE ALLA CIECA. Su 7.998 CIK quotati, **1.455 hanno piu
di un simbolo**: GOOGL/GOOG/GOOGN/GOOGM, BRK-A/BRK-B, e JPM che ne ha nove fra
azioni e privilegiate. Prendere «il» ticker del CIK scambierebbe una classe per
l'altra, o un'ordinaria per una privilegiata. Quindi:

    il simbolo del deposito e' fra quelli attuali  -> si tiene, e' la classe giusta
    non c'e' piu', e il CIK ne ha UNO             -> si corregge
    non c'e' piu', e il CIK ne ha PIU DI UNO      -> NON si indovina, si dichiara
    il CIK non e' quotato                          -> non esiste un simbolo, e va bene

L'ultimo caso e' il piu' numeroso e il meno ovvio: 60 dei 506 emittenti visti in
dodici giorni sono fondi di credito privato e BDC non quotate. Per loro `NONE`
non e' un difetto, e' il fatto.

I SEPARATORI NON SONO DIFFERENZE. EDGAR scrive `BRK-B`, i depositi scrivono
`BRK.B`. Confrontarli alla lettera classificherebbe Berkshire come stantia e la
«correggerebbe» verso l'altra classe. Si normalizza il punto in trattino prima
di confrontare, mai dopo.

MISURATO sulle observations live, 506 coppie (CIK, simbolo) distinte in dodici
giorni: 439 valide, 60 CIK non quotati, 4 correzioni sicure -- fra cui `CYBN` ->
`HELP` su un emittente con 8,3 milioni di acquisti nel report di oggi -- e 3
ambigue, che restano dichiarate e non toccate.

SE LA MAPPA NON SI CARICA non succede niente: `resolve` restituisce il simbolo
del deposito con stato `sconosciuto`. Il giro gira identico a prima.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"

#  Cio' che un depositante scrive quando non c'e' un simbolo. Non sono ticker e
#  non vanno trattati come tali: se EDGAR per quel CIK ne conosce uno, e' un
#  guadagno secco -- due dei quattro casi corretti nascono qui.
PLACEHOLDERS = frozenset({
    "", "-", "--", "NONE", "NONE.", "N/A", "NA", "N.A.", "NULL", "TBD",
})

#  Gli stati. Sono fatti, non giudizi: dicono da dove viene il simbolo.
VALIDO = "valido"
CORRETTO = "corretto"
AMBIGUO = "ambiguo"
NON_QUOTATO = "cik non quotato"
SCONOSCIUTO = "sconosciuto"


@dataclass(frozen=True, slots=True)
class Resolved:
    """Il simbolo da usare, quello che il deposito dichiarava, e perche'."""

    ticker: str
    reported: str
    status: str
    candidates: tuple = ()

    @property
    def changed(self) -> bool:
        return self.status == CORRETTO

    def note(self) -> str:
        """Una riga per il report. Vuota se non c'e' niente da dire."""
        if self.status == CORRETTO:
            return "simbolo aggiornato: il deposito dichiara {}, EDGAR {}".format(
                self.reported or "(vuoto)", self.ticker)
        if self.status == AMBIGUO:
            return ("simbolo {} non piu' quotato; il CIK ne ha {}: {} -- "
                    "non risolto".format(self.reported or "(vuoto)",
                                         len(self.candidates),
                                         ", ".join(self.candidates)))
        return ""


def normalize(t) -> str:
    """Maiuscolo, senza spazi, e il punto diventa trattino.

    `BRK.B` e `BRK-B` sono lo stesso titolo scritto da due fonti diverse.
    """
    return (t or "").strip().upper().replace(".", "-")


def is_placeholder(t) -> bool:
    return (t or "").strip().upper() in PLACEHOLDERS


def load_map(client) -> dict:
    """{CIK a dieci cifre: frozenset di simboli attuali}.

    Una sola richiesta, servita dalla cache su disco dopo la prima volta. Se
    fallisce si restituisce una mappa vuota, e `resolve` lascia tutto com'e'.
    """
    try:
        doc = client.get_json(COMPANY_TICKERS)
    except Exception as exc:                              # noqa: BLE001
        log.warning("tickers: mappa non caricata (%s)", exc)
        return {}
    if not doc:
        log.warning("tickers: mappa vuota")
        return {}

    per_cik: dict = {}
    rows = doc.values() if isinstance(doc, dict) else doc
    for row in rows:
        try:
            cik = str(row["cik_str"]).zfill(10)
            tick = str(row["ticker"]).strip().upper()
        except (KeyError, TypeError, ValueError):
            continue
        if not tick:
            continue
        per_cik.setdefault(cik, set()).add(tick)
    return {k: frozenset(v) for k, v in per_cik.items()}


def resolve(reported, cik, tmap) -> Resolved:
    """Il simbolo da usare per questo CIK. Vedi il docstring del modulo."""
    rep = (reported or "").strip()
    if not tmap:
        return Resolved(rep, rep, SCONOSCIUTO)

    current = tmap.get(str(cik or "").zfill(10))
    if not current:
        #  Non quotato: un simbolo non esiste. Si tiene cio' che il deposito
        #  dichiara, che per questi e' quasi sempre un segnaposto, e va bene.
        return Resolved(rep, rep, NON_QUOTATO)

    ordered = tuple(sorted(current))

    if not is_placeholder(rep):
        if normalize(rep) in {normalize(x) for x in current}:
            return Resolved(rep, rep, VALIDO, ordered)

    #  Il simbolo dichiarato non e' fra gli attuali -- o non c'era affatto.
    if len(current) == 1:
        return Resolved(ordered[0], rep, CORRETTO, ordered)
    return Resolved(rep, rep, AMBIGUO, ordered)


def apply_to_clusters(clusters, client) -> dict:
    """Corregge il simbolo dei cluster. Ritorna il conteggio per stato.

    Un solo punto di applicazione: il simbolo entra nel percorso live da
    `cluster.py`, quindi si sistema qui e tutto cio' che viene dopo -- prezzi,
    report, archivio -- vede quello giusto.
    """
    tmap = load_map(client)
    counts: dict = {}
    for c in clusters:
        r = resolve(c.ticker, c.issuer_cik, tmap)
        counts[r.status] = counts.get(r.status, 0) + 1
        if r.changed:
            log.info("%s: simbolo %s -> %s", c.issuer_cik,
                     r.reported or "(vuoto)", r.ticker)
            c.ticker = r.ticker
    return counts
