"""Dal deposito al testo, e dal testo alle finestre che si mandano al modello.

Un 424B5 e' un documento HTML: tabelle di copertina, decine di pagine di
fattori di rischio, e in fondo la sottoscrizione. Mandarlo intero costa e non
serve: cio' che si estrae -- tipo, controparte, importo, condizioni, data --
sta nella copertina e in due o tre sezioni con un titolo prevedibile.

Quindi due tagli, non uno:

  * la TESTA, che porta copertina e riassunto dell'offerta;
  * una FINESTRA per ciascuna ancora trovata (`Use of Proceeds`,
    `Plan of Distribution`, `Item 2.01`...).

Le finestre che si sovrappongono si fondono, e ogni salto e' segnato in chiaro
nel testo inviato: il modello deve poter vedere che manca qualcosa, altrimenti
cita con sicurezza attraverso un buco.

Le costanti qui sotto NON sono scelte a occhio: vengono dalla misura in
docs/costs.md, rieseguibile con `python -m edgar_llm.tools.measure_docs`.
"""

from __future__ import annotations

import logging
import re

from lxml import html as lxml_html

log = logging.getLogger(__name__)


class UnreadableDocument(RuntimeError):
    """Il documento c'e' ma non si e' potuto convertire in testo.

    Ha un tipo suo perche' la prima versione di `to_text` restituiva stringa
    vuota su errore, e una stringa vuota e' indistinguibile da un documento
    senza testo. Il risultato: gli 8-K in inline XBRL -- che aprono con
    `<?xml version='1.0' encoding='ASCII'?>`, e che lxml rifiuta se glieli si
    passa come `str` invece che come `bytes` -- misuravano zero caratteri
    tutti e cinque su cinque, e la tabella dei costi lo leggeva come "8-K:
    nessun testo". Un fallimento totale di una classe di documenti travestito
    da dato. Adesso alza, e chi chiama decide: mai PASS, mai zero muto.
    """

#  Fissate dalla misura del Passo 0 -- vedi docs/costs.md.
HEAD_CHARS = 12_000
WINDOW_CHARS = 8_000
ELISION = "\n\n[... testo omesso ...]\n\n"

#  Titoli di sezione, non parole qualunque: `re.M` piu' un contesto corto per
#  evitare che un rimando nell'indice apra una finestra sull'indice.
ANCHORS = (
    r"Use\s+of\s+Proceeds",
    r"Plan\s+of\s+Distribution",
    r"The\s+Offering",
    r"Underwrit(?:ing|ers?)",
    r"Item\s+2\.01",
    r"Item\s+1\.01",
    r"Securities\s+Purchase\s+Agreement",
    r"At[- ]the[- ]Market",
)
_ANCHOR_RE = re.compile("|".join(ANCHORS), re.I)
_WS = re.compile(r"[ \t\r\f\v]+")
_NL = re.compile(r"\n{3,}")

#  `text_content()` concatena senza separatori: `<p>Prima</p><p>Use of
#  Proceeds</p>` diventa `PrimaUse of Proceeds`. Su un filing generato da un
#  editor il guaio si vede poco -- l'HTML ha gia' spazi fra i tag -- e proprio
#  per questo passava inosservato: incolla le parole solo dove il markup e'
#  compatto, cioe' nelle tabelle di copertina, che sono il posto dove stanno
#  importi e date. Un ritorno a capo dopo ogni blocco rimette la struttura su
#  cui lavorano le ancore.
BLOCK_TAGS = frozenset({
    "p", "div", "br", "tr", "td", "th", "table", "li", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "hr", "blockquote",
})


def to_text(raw: str) -> str:
    """HTML (o iXBRL, o testo nudo) -> testo leggibile.

    Gli spazi si collassano ma i ritorni a capo no: la struttura a righe e' cio'
    che rende riconoscibile un titolo di sezione, e le ancore lavorano su quella.
    """
    if not raw:
        return ""
    stripped = raw.lstrip()[:2000].lower()
    if "<" not in stripped:
        text = raw
    else:
        #  BYTES, non str: meta' dei depositi recenti sono inline XBRL e aprono
        #  con una dichiarazione di encoding, che lxml rifiuta su una stringa
        #  gia' decodificata. Vedi UnreadableDocument.
        try:
            #  L'encoding va DICHIARATO al parser. Passando byte nudi, lxml
            #  ricade sul default latin-1 e un \xa0 torna come mojibake, che
            #  nessuna sostituzione a valle recupera piu'.
            doc = lxml_html.fromstring(
                raw.encode("utf-8", "replace"),
                parser=lxml_html.HTMLParser(encoding="utf-8"))
        except Exception as e:                                 # noqa: BLE001
            log.error("documento illeggibile: %s: %s", type(e).__name__, e)
            raise UnreadableDocument(str(e)) from e
        for bad in doc.xpath("//script|//style|//head"):
            bad.getparent().remove(bad)
        for el in doc.iter():
            if isinstance(el.tag, str) and el.tag.lower() in BLOCK_TAGS:
                el.tail = "\n" + (el.tail or "")
        text = doc.text_content()
    text = text.replace("\xa0", " ")
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _NL.sub("\n\n", text).strip()


def _merge(spans, limit):
    spans = sorted(spans)
    out = []
    for a, b in spans:
        a, b = max(0, a), min(limit, b)
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def windows(text: str, head_chars: int = HEAD_CHARS,
            window_chars: int = WINDOW_CHARS, max_anchors: int = 6) -> str:
    """Il testo che finisce nel prompt. Vuoto se il documento e' vuoto."""
    if not text:
        return ""
    if len(text) <= head_chars:
        return text

    spans = [(0, head_chars)]
    half = window_chars // 2
    seen = 0
    for m in _ANCHOR_RE.finditer(text, head_chars):
        spans.append((m.start() - half, m.start() + half))
        seen += 1
        if seen >= max_anchors:
            break

    merged = _merge(spans, len(text))
    parts, prev_end = [], 0
    for a, b in merged:
        if a > prev_end:
            parts.append(ELISION)
        parts.append(text[a:b])
        prev_end = b
    if prev_end < len(text):
        parts.append(ELISION)
    return "".join(parts)


def document_text(client, filing) -> str:
    """Testo del documento primario. '' se EDGAR non l'ha dato.

    Non ingoia `UnreadableDocument`: "non l'ho scaricato" e "l'ho scaricato e
    non l'ho capito" sono due esiti diversi e chi chiama deve poterli separare.
    """
    return to_text(client.get(filing.url) or "")
