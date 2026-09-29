"""Un errore per colpa di chi: del modello, o del taglio del documento.

Sono due guasti diversi e si correggono in modi opposti. Se l'informazione era
DENTRO le finestre e il modello non l'ha vista, si lavora sul prompt. Se era
FUORI, il prompt non c'entra: nessuna istruzione fa leggere una frase che non
e' stata mandata, e va allargato il taglio.

Senza questa distinzione un'accuracy bassa sui 424B3 -- che entrano nel prompt
all'1% del loro testo -- si legge come «il modello sbaglia sui prospetti di
fusione», che e' una conclusione plausibile, comoda e forse falsa.

COME SI DECIDE. Si cerca la forma superficiale del valore VERO (quello che ha
scritto una persona) prima nelle finestre, poi nel documento intero. Funziona
solo per i campi che nel testo hanno una forma scritta: un importo, una data,
un nome. `tipo` non ce l'ha -- e' una classificazione, non una citazione -- e
`condizioni` e' una sintesi. Per quei due si risponde `n.d.`, che e' un esito
onesto e non una lacuna da riempire con un'euristica.
"""

from __future__ import annotations

import re

DENTRO = "dentro"
FUORI = "fuori"
ASSENTE = "assente"
NON_DETERMINABILE = "n.d."

MESI = ("January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December")

_WS = re.compile(r"\s+")


def _norm(s) -> str:
    return _WS.sub(" ", str(s or "")).strip().lower()


def _varianti_importo(v: float) -> list:
    """Le forme con cui un importo compare davvero in un prospetto.

    «$0.7 billion», «$700,000,000», «700.0 million» sono lo stesso numero, e un
    documento ne usa una sola. Cercare solo le cifre direbbe «fuori finestra»
    su un documento che lo scriveva in lettere due righe sopra.
    """
    fuori = []
    intero = int(round(v))
    fuori.append(str(intero))
    fuori.append("{:,}".format(intero))
    for divisore, parola in ((1e9, "billion"), (1e6, "million"),
                             (1e3, "thousand")):
        scalato = v / divisore
        if 0.01 <= scalato < 10000:
            for testo in ("{:g}".format(round(scalato, 2)),
                          "{:.1f}".format(scalato),
                          "{:,.1f}".format(scalato)):
                fuori.append("{} {}".format(testo, parola))
    return fuori


def _varianti_data(iso: str) -> list:
    """ISO piu' le forme americane, che sono quelle che i filing usano."""
    try:
        anno, mese, giorno = (int(x) for x in iso.split("-"))
    except (ValueError, AttributeError):
        return [str(iso)]
    nome = MESI[mese - 1]
    return [
        iso,
        "{} {}, {}".format(nome, giorno, anno),
        "{} {:02d}, {}".format(nome, giorno, anno),
        "{}/{}/{}".format(mese, giorno, anno),
        "{:02d}/{:02d}/{}".format(mese, giorno, anno),
    ]


def _varianti_testo(v: str) -> list:
    """Il nome intero, e la sua parte distintiva.

    «LSF11 Redwood Parent, L.P. (Seller)» compare nel documento senza la glossa
    fra parentesi, e spesso senza il suffisso societario. Se si cercasse solo
    la stringa intera si concluderebbe «fuori finestra» su un documento che la
    nomina in ogni pagina.
    """
    v = str(v).strip()
    fuori = [v]
    senza_parentesi = re.sub(r"\s*\([^)]*\)", "", v).strip(" ,.")
    if senza_parentesi and senza_parentesi != v:
        fuori.append(senza_parentesi)
    parole = senza_parentesi.split()
    if len(parole) >= 2:
        fuori.append(" ".join(parole[:2]))
    if parole:
        #  Una parola sola solo se e' lunga: «The» non prova niente.
        if len(parole[0]) >= 6:
            fuori.append(parole[0])
    return fuori


def varianti(campo: str, valore) -> list:
    if valore is None:
        return []
    if campo == "importo_usd":
        try:
            return _varianti_importo(float(valore))
        except (TypeError, ValueError):
            return []
    if campo == "data_efficacia":
        return _varianti_data(valore)
    if campo == "controparte":
        return _varianti_testo(valore)
    return []


def dove_sta(campo: str, valore, finestre: str, testo: str) -> str:
    """DENTRO, FUORI, ASSENTE o NON_DETERMINABILE.

    `finestre` e' cio' che ha ricevuto il modello; `testo` il documento intero.
    """
    v = varianti(campo, valore)
    if not v:
        return NON_DETERMINABILE
    nf, nt = _norm(finestre), _norm(testo)
    for x in v:
        if _norm(x) and _norm(x) in nf:
            return DENTRO
    for x in v:
        if _norm(x) and _norm(x) in nt:
            return FUORI
    #  Ne' nell'uno ne' nell'altro: l'etichetta non e' una citazione. Un
    #  importo scritto in una tabella che la conversione ha smontato finisce
    #  qui, e va contato a parte invece che addossato al taglio.
    return ASSENTE
