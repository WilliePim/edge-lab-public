"""Massimo e minimo del titolo dichiarati dalla societa' nel suo 10-K (Item 5), per decidere se un salto e' vero.

Serve a una cosa sola: un salto sospetto puo' essere un movimento di mercato vero (Apple il 29 settembre 2000, da
53,50 a 25,75) oppure una serie grezza fuori scala (Iconix a 63,00 il 16 dicembre 2015, quando il titolo stava sotto
i 17). Dall'interno dei dati i due casi sono identici: `adjusted_close` e' il grezzo per una costante e salta uguale,
il gap e' overnight in entrambi, la barra del giorno e' coerente in entrambi. Dal bilancio no.

Fino all'esercizio 2018 l'Item 5 del 10-K doveva riportare massimo e minimo per trimestre (voce 201(c) del
Regulation S-K, tolta dalla SEC con le modifiche FAST Act del 2018). Per i salti precedenti quei numeri sono una
fonte indipendente, depositata dalla societa' stessa e citabile.

**Il test.** Chiusura del giorno prima del salto e chiusura del giorno del salto, confrontate con l'intervallo
dichiarato per il periodo che le contiene:

- tutte e due dentro  -> il salto e' un movimento vero, il periodo prima non si esclude;
- quella prima fuori sopra, quella dopo dentro -> la serie prima del salto e' fuori scala, si esclude;
- ogni altro esito (bilancio assente, Item 5 illeggibile, tutte e due fuori) -> non verificabile, si esclude come
  prima e si conta il motivo.

Il confronto usa tutti e due gli estremi. Una chiusura sta sempre dentro il massimo e il minimo del suo periodo:
fuori da li' e' impossibile, da qualunque lato. Guardare solo il massimo lascerebbe passare per «vere» le serie
scalate verso il basso -- e' un limite inferiore di zero -- come Affiliated Computer Services, che il 02-01-2009 va
da 13,15 a 1,27 mentre il suo bilancio dichiara 34,84-58,70.

`TOLLERANZA` copre l'arrotondamento dei bilanci vecchi in ottavi e i disallineamenti di un giorno fra esercizio
fiscale e trimestre solare. Non e' una soglia di merito: allargandola il test diventa piu' prudente, cioe' dichiara
"fuori scala" meno spesso e lascia piu' salti fra i non verificabili, che restano esclusi.
"""
from __future__ import annotations

import datetime as dt
import re

TOLLERANZA = 0.10
PREZZO_MASSIMO_PLAUSIBILE = 100_000.0
PREZZO_MINIMO_PLAUSIBILE = 0.01

#  L'ancora dell'Item 5. Nell'indice del bilancio compare la stessa frase: si sceglie l'occorrenza seguita dalla
#  tabella, non quella seguita dal numero di pagina.
ANCORA = re.compile(r"Market\s+for\s+(the\s+)?Registrant", re.I)
FINE = re.compile(r"Item\s*6[\.\s]|Selected\s+Financial\s+Data|Item\s*7[\.\s]", re.I)
SEGNI_TABELLA = re.compile(r"\bHigh\b|\bLow\b|First\s+Quarter|Fourth\s+Quarter|\bQuarter\s+Ended\b", re.I)

#  I prezzi si trovano dall'etichetta della riga, non dalla sezione: l'Item 5 dei bilanci vecchi rimanda spesso
#  altrove («set forth in Part II, Item 8 ... incorporated by reference», 10-K Apple 1996) e la sezione di arrivo
#  contiene anche ricavi, utili e dividendi. L'etichetta invece sta attaccata ai numeri giusti.
#
#  Due forme, entrambe in uso dagli anni Novanta a oggi:
#    «Price range per common share $25.00 -$16.00 $28.88 -$19.63 ...»   (Apple, 1994-2000)
#    «High Low ... Fourth Quarter $ 10.08 $ 6.76 ...»                    (Iconix, 2016)
ETICHETTE_PREZZO = (
    re.compile(r"[Pp]rice\s+range[^.$]{0,60}?share", re.I),
    re.compile(r"\bHigh\b[\s\S]{0,120}?\bLow\b", re.I),
    re.compile(r"\bLow\b[\s\S]{0,120}?\bHigh\b", re.I),
    re.compile(r"high\s+and\s+low[^.]{0,80}?price", re.I),
)
FINESTRA_ETICHETTA = 400        # i numeri stanno subito dopo l'etichetta; oltre comincia un'altra riga di tabella
FINESTRA_PRIMA = 200            # l'anno a volte precede l'etichetta: «Fiscal 2000 price range per common share»

#  L'anno che etichetta i prezzi. Una tabella dell'Item 5 ne riporta quasi sempre due, l'esercizio e quello prima:
#  presi insieme darebbero una fascia larga il doppio, dentro la quale ci sta anche una rottura di scala.
ANNO = re.compile(r"\b(19[6-9]\d|20[0-4]\d)\b")

#  Prezzi come li scrivono i bilanci: decimali ($64.13, 64.13) e frazioni ottali dei depositi prima del 2001
#  (53 1/2, 53-1/2, 5/8). La frazione da sola vale meno di 1 dollaro ed e' un prezzo valido per i titoli piccoli.
DECIMALE = re.compile(r"\$?\s*(\d{1,5}\.\d{2})\b")
FRAZIONE = re.compile(r"\$?\s*(\d{1,5})[\s-](\d{1,2})/(\d{1,2})\b")
SOLO_FRAZIONE = re.compile(r"(?<![\d/.])(\d{1,2})/(\d{1,2})\b")


def item5(testo: str) -> str | None:
    """La sezione Item 5 del deposito, o None se non si trova."""
    for inizio in reversed([m.start() for m in ANCORA.finditer(testo)]):   # l'ultima e' la sezione, non l'indice
        coda = testo[inizio:inizio + 12000]
        fine = FINE.search(coda, 200)
        regione = coda[:fine.start()] if fine else coda[:6000]
        if SEGNI_TABELLA.search(regione):
            return regione
    return None


def _finestre(testo: str) -> list[tuple[str, int | None]]:
    """I pezzi che seguono ogni etichetta di prezzo, ciascuno con l'anno che sta scritto *prima* dell'etichetta.

    I prezzi si leggono solo dopo l'etichetta: prima ci sono ricavi, utili e dividendi, e leggerli falserebbe il
    minimo. L'anno invece a volte sta li' -- «Fiscal 2000 price range per common share» -- e serve, perche' una
    tabella dell'Item 5 riporta quasi sempre due esercizi e presi insieme darebbero una fascia larga il doppio,
    dentro la quale ci sta anche una rottura di scala. Le finestre che si accavallano si fondono, cosi' ogni numero
    si legge una volta sola."""
    tratti = []
    for etichetta in ETICHETTE_PREZZO:
        for m in etichetta.finditer(testo):
            prima = testo[max(0, m.start() - FINESTRA_PRIMA):m.start()]
            anni = ANNO.findall(prima)
            tratti.append([m.end(), min(m.end() + FINESTRA_ETICHETTA, len(testo)), int(anni[-1]) if anni else None])
    fusi: list[list] = []
    for da, a, anno in sorted(tratti):
        if fusi and da <= fusi[-1][1]:
            fusi[-1][1] = max(fusi[-1][1], a)
        else:
            fusi.append([da, a, anno])
    return [(testo[da:a], anno) for da, a, anno in fusi]


def _valori_con_anno(regione: str, anno_prima: int | None) -> list[tuple[int | None, float]]:
    """I prezzi della regione, ciascuno con l'anno che lo etichetta: l'ultimo anno scritto prima di lui dentro la
    regione, oppure quello che precedeva l'etichetta."""
    anni = [(m.start(), int(m.group(1))) for m in ANNO.finditer(regione)]
    fuori = []
    for posizione, valore in _valori_posizionati(regione):
        precedenti = [a for p, a in anni if p < posizione]
        fuori.append((precedenti[-1] if precedenti else anno_prima, valore))
    return fuori


def _valori_posizionati(regione: str) -> list[tuple[int, float]]:
    """I prezzi di una regione con la loro posizione: decimali e frazioni, in ordine di lettura."""
    valori = []
    for m in FRAZIONE.finditer(regione):
        intero, num, den = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if den and num < den:
            valori.append((m.start(), intero + num / den))
    senza_frazioni = FRAZIONE.sub(lambda m: " " * len(m.group(0)), regione)
    valori += [(m.start(), float(m.group(1))) for m in DECIMALE.finditer(senza_frazioni)]
    senza_prezzi = DECIMALE.sub(lambda m: " " * len(m.group(0)), senza_frazioni)
    for m in SOLO_FRAZIONE.finditer(senza_prezzi):
        num, den = int(m.group(1)), int(m.group(2))
        if den and num < den:
            valori.append((m.start(), num / den))
    return sorted((p, v) for p, v in valori if PREZZO_MINIMO_PLAUSIBILE <= v <= PREZZO_MASSIMO_PLAUSIBILE)


def _valori(regione: str) -> list[float]:
    """I prezzi di una regione, decimali e frazioni."""
    return [v for _p, v in _valori_posizionati(regione)]


VALORI_MINIMI = 4                        # due trimestri, massimo e minimo: sotto non e' una tabella di prezzi


def prezzi_dichiarati(testo: str) -> list[tuple[int | None, float]]:
    """I prezzi dichiarati nel deposito, con l'anno di ciascuno: prima quelli etichettati dentro l'Item 5, che sono
    i piu' sicuri; se l'Item 5 rimanda altrove, quelli etichettati nel resto del documento."""
    sezione = item5(testo)
    if sezione:
        valori = [x for regione, anno in _finestre(sezione) for x in _valori_con_anno(regione, anno)]
        if len(valori) >= VALORI_MINIMI:
            return valori
    return [x for regione, anno in _finestre(testo) for x in _valori_con_anno(regione, anno)]


def intervallo(testo: str, anno: int | None = None) -> tuple[float, float, int] | None:
    """(massimo, minimo, quanti valori) dichiarati nel bilancio, o None se non si legge.

    Con `anno`, solo i prezzi che quell'anno etichetta: e' la fascia che serve, perche' quella di due esercizi messi
    insieme e' larga il doppio e ci passa dentro una rottura di scala. Continental Resources il 20-12-2010 va da
    28,58 a 57,64 -- la serie prima sta a meta' della scala vera -- e sta dentro l'intervallo 13,84-59,98 dei due
    esercizi 2009 e 2010 presi insieme."""
    valori = prezzi_dichiarati(testo)
    if anno is not None:
        valori = [(a, v) for a, v in valori if a == anno]
    soli = [v for _a, v in valori]
    if len(soli) < VALORI_MINIMI:
        return None
    return max(soli), min(soli), len(soli)


def esamina(pre: float, post: float, massimo: float, minimo: float,
            tolleranza: float = TOLLERANZA) -> tuple[str, float | None]:
    """Confronta le due chiusure del salto con l'intervallo che la societa' dichiara.

    ("vero", None) | ("fuori scala", fattore) | ("incerto", None). Il fattore e' pre/post: di quanto la serie
    precedente e' scalata rispetto a quella che il bilancio conferma.

    **Servono tutti e due gli estremi.** Il minimo letto e' spesso piu' basso del vero, perche' nei bilanci la riga
    dei prezzi sta accanto a dividendi, valore nominale e utili per azione (sul 10-K Apple del 1996 si legge 0,12,
    che e' il dividendo). Un minimo troppo basso allarga la fascia e rende il test **piu' permissivo**, mai piu'
    severo: e' un difetto tollerabile. Non usarlo affatto invece equivale a un minimo di zero, cioe' al test piu'
    permissivo possibile, e lascia passare per «vere» serie che non sono di quella societa': Affiliated Computer
    Services il 02-01-2009 va da 13,15 a 1,27 mentre il suo bilancio dichiara un intervallo di 34,84-58,70.

    Con tutti e due gli estremi il verso del salto non conta piu': una serie scalata verso il basso sfonda il
    minimo come una scalata verso l'alto sfonda il massimo."""
    tetto, pavimento = massimo * (1.0 + tolleranza), minimo * (1.0 - tolleranza)
    pre_dentro = pavimento <= pre <= tetto
    post_dentro = pavimento <= post <= tetto
    if pre_dentro and post_dentro:
        return "vero", None
    if not pre_dentro and post_dentro:
        return "fuori scala", pre / post if post else None
    return "incerto", None


def testo_pulito(corpo: bytes) -> str:
    """Il deposito senza marcatura, con gli spazi normalizzati."""
    testo = corpo.decode("utf-8", "replace")
    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = re.sub(r"&nbsp;|&#160;", " ", testo)
    testo = re.sub(r"&#8217;|&#8216;|&rsquo;", "'", testo)
    return re.sub(r"\s+", " ", testo)


def annuale_per(annuali: list[tuple], giorno: dt.date) -> tuple | None:
    """Il 10-K il cui esercizio contiene `giorno`: il primo con data di chiusura dell'esercizio non precedente al
    giorno e non oltre un anno dopo. Il bilancio dell'anno dopo riporta anche i trimestri dell'anno prima, quindi
    va bene anche quello, ma il proprio e' piu' stretto."""
    g = giorno.isoformat()
    candidati = [x for x in annuali if x[2] and g <= x[2] <= (giorno + dt.timedelta(days=370)).isoformat()]
    return min(candidati, key=lambda x: x[2]) if candidati else None
