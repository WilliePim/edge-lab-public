"""E3, fase 0 punto 2 — dal prospetto dell'IPO, con regole deterministiche: prezzo, data, lock-up, azioni.

Nessun modello linguistico (regola 4 della direttiva): espressioni regolari sul testo del documento principale del
424B4/424B1, convertito da HTML a testo con lo stesso convertitore del repo (`survival.testo`). Ogni campo porta la
citazione da cui viene, per la verifica a mano dei 30 prospetti.

Campi:
- **prezzo di collocamento**: «initial public offering price» / «public offering price» con un importo per azione,
  cercato nella copertina (primi 15.000 caratteri); se c'è un intervallo «between $X and $Y» e nessun prezzo, il
  prospetto non è definitivo e il campo resta vuoto;
- **data**: la data della copertina («The date of this prospectus is …»); se manca, la data di deposito;
- **lock-up**: il numero di giorni nelle frasi di lock-up («lock-up», «not to sell … for a period of N days after the
  date of this prospectus»). Si prende il valore **più frequente** fra le frasi che parlano di amministratori,
  dirigenti o azionisti; le altre durate si registrano come eccezioni;
- **azioni offerte**: «We are offering N shares» o «N shares of common stock» in copertina;
- **azioni in circolazione dopo l'offerta**: «common stock to be outstanding after this offering … N shares»;
- esclusioni che richiedono il testo: **unit** in offerta, **trust** di una SPAC, **REIT** dichiarato, **prezzo sotto
  $5**, **nessun prezzo di collocamento** (non è un'offerta iniziale di azioni: rivendita, debito, quotazione diretta).
"""
from __future__ import annotations

import collections
import json
import re

import comune as C

ARCH = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
COPERTINA = 15000
NUMERI = {"thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90, "one hundred twenty": 120,
          "one hundred and twenty": 120, "one hundred fifty": 150, "one hundred eighty": 180,
          "one hundred and eighty": 180, "two hundred seventy": 270, "three hundred sixty-five": 365, "365": 365}

_IMPORTO = r"\$\s?(\d{1,4}(?:\.\d{1,4})?)"
#  Frasi della copertina, nell'ordine: «The initial public offering price [for our Class A common stock] is $17.00»,
#  «public offering price of $X per share», «PRICE $19.00 A SHARE» (Bats), «Price to public $19.00»; poi la riga
#  della tabella «Initial public offering price $ 17.00».
_OGGETTO = r"(?:\s+(?:for|of|per)\s+(?:each\s+|one\s+|a\s+)?(?:our\s+|the\s+)?[A-Za-z ,-]{0,40}?(?:stock|shares?))?"
PREZZO = [re.compile(r"initial\s+public\s+offering\s+price" + _OGGETTO + r"\s+(?:is|will\s+be|of)\s+" + _IMPORTO, re.I),
          re.compile(r"public\s+offering\s+price" + _OGGETTO + r"\s+(?:is|of)\s+" + _IMPORTO + r"\s+per\s+(?:share|unit)",
                     re.I),
          re.compile(r"\bPRICE\s+" + _IMPORTO + r"\s+(?:A|PER)\s+SHARE\b"),
          re.compile(r"price\s+to\s+(?:the\s+)?public\W{0,10}" + _IMPORTO, re.I),
          re.compile(r"offering\s+price\s+(?:of|is)\s+" + _IMPORTO + r"\s+per\s+share", re.I)]
TABELLA_PREZZO = re.compile(r"(?:initial\s+)?public\s+offering\s+price\s{0,3}\(?\d?\)?\s{0,3}" + _IMPORTO, re.I)
#  La tabella della copertina con le colonne in testa: «Price to Public Underwriting Discounts … Per Share $19.00 $1.33
#  $17.67» (Annie's, 2012). Il primo importo dopo «Per Share», entro 300 caratteri dalla testata, è il prezzo al pubblico.
TABELLA_COLONNE = re.compile(r"price\s+to\s+(?:the\s+)?public.{0,300}?per\s+share\s+" + _IMPORTO, re.I)
INTERVALLO = re.compile(r"between\s+" + _IMPORTO + r"\s+and\s+" + _IMPORTO, re.I)
DATA = re.compile(r"(?:the\s+date\s+of\s+this\s+prospectus\s+is|prospectus\s+dated|this\s+prospectus\s+is\s+dated)\s+"
                  r"([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})", re.I)
#  «180 days after the date of this prospectus», anche con la virgola prima di «from» («360 and 540 days, from the
#  date of this prospectus», Bats 2016).
LOCK = re.compile(r"(?:for\s+a\s+period\s+of\s+|during\s+the\s+|until\s+|ending\s+|through\s+)?"
                  r"(\d{2,3}|[a-z]+(?:[\s-](?:hundred|and|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|five)"
                  r"){0,4})\s*(?:\(\d{2,3}\)\s*)?(?:calendar\s+)?days?,?\s+(?:after|following|from)\s+the\s+date\s+of\s+"
                  r"(?:this|the\s+final)\s+prospectus", re.I)
#  «the 180-day lock-up period», «180-day restricted period».
LOCK_TRATTINO = re.compile(r"\b(\d{2,3})-day\s+(?:lock-?\s?up|restricted|market\s+stand-?off)\s+period", re.I)
#  Azioni offerte = l'offerta base della copertina (società più eventuali azionisti venditori, senza l'opzione dei
#  collocatori): prima la cifra del titolo («PROSPECTUS 5,580,000 Shares», «2,016,000 Shares of Common Stock»), con la
#  S maiuscola e nei primi 4.000 caratteri; poi le frasi.
TITOLO_OFFERTA = re.compile(r"\b(\d{1,3}(?:,\d{3}){1,3})\s+Shares\b")
TITOLO_CARATTERI = 4000
OFFERTE = [re.compile(r"(?:we\s+are|the\s+company\s+is|[A-Z][\w.,&' -]{2,60}\s+is)\s+(?:offering|selling)\s+"
                      r"(?:to\s+sell\s+)?([\d,]{5,})\s+shares", re.I),
           re.compile(r"(?:this\s+is\s+(?:an|the)\s+initial\s+public\s+offering\s+of\s+|offering\s+of\s+)([\d,]{5,})\s+"
                      r"shares", re.I)]
#  «Common stock to be outstanding after this offering 26,544,188 shares», anche con parole fra la frase e il numero
#  («Capital stock outstanding after this offering: Common stock 87,801,671 shares», Bats 2016): fino a 60 caratteri
#  senza cifre.
CIRCOLAZIONE = re.compile(r"outstanding\s+(?:immediately\s+)?(?:after|following)\s+(?:this|the)\s+offering"
                          r"(?:(?!includ|exclud|based|consist|represent|assum|reflect)[^\d]){0,60}?"
                          r"(\d{1,3}(?:,\d{3}){1,3})\s+shares", re.I)
#  Le frasi sulla Rule 144 («90 days after the date of this prospectus» nella tabella delle azioni vendibili) non
#  sono il lock-up: si scartano se una di queste parole sta nei 250 caratteri prima della durata.
NON_LOCKUP = re.compile(r"rule\s+144|rule\s+701|eligible\s+for\s+(?:sale|resale)|available\s+for\s+sale", re.I)
#  Società in accomandita e LLC che offrono «common units»: non sono azioni ordinarie. Si segnano e si contano, non si
#  escludono: è una decisione dell'utente alla fermata 1.
LP_UNITA = re.compile(r"common\s+units\s+representing\s+limited\s+(?:partner|liability\s+company)\s+interests|"
                      r"\blimited\s+partner\s+interests\b|\bcommon\s+units\b", re.I)
UNIT = re.compile(r"\b(?:we\s+are\s+offering|offering\s+of)\s+[\d,]+\s+units\b|\bper\s+unit\b", re.I)
TRUST = re.compile(r"\btrust\s+account\b", re.I)
REIT = re.compile(r"\bqualify\s+(?:to\s+be\s+taxed\s+)?as\s+a\s+(?:real\s+estate\s+investment\s+trust|REIT)\b", re.I)
MESI = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"])}


def url(cik: str, acc: str, doc: str) -> str:
    return ARCH.format(cik=int(cik), acc=acc.replace("-", ""), doc=doc)


def documento(cik: str, percorso_indice: str) -> tuple[str | None, str]:
    """(url del documento principale, accession) dal percorso dell'indice e dalle submissions in blocco."""
    import bulk
    acc = percorso_indice.rsplit("/", 1)[-1].replace(".txt", "")
    _t, dep = bulk.submissions(cik)
    for _d, _f, _v, a, doc in dep:
        if a == acc and doc:
            return url(cik, acc, doc), acc
    return None, acc


def _giorni(s: str) -> int | None:
    s = s.lower().replace("-", " ").strip()
    if s.isdigit():
        return int(s)
    s = re.sub(r"\s+", " ", s)
    for k, v in NUMERI.items():
        if s.endswith(k.replace("-", " ")):
            return v
    return None


def _numero(s: str) -> int:
    return int(s.replace(",", ""))


def estrai(testo: str) -> dict:
    """I campi del prospetto con le citazioni. Nessun campo inventato: dove la regola non trova, None."""
    t = re.sub(r"[\s\u00a0\u200b\ufeff]+", " ", testo)
    cop = t[:COPERTINA]
    f = {"prezzo": None, "prezzo_citazione": "", "intervallo": None, "data_copertina": None, "lockup_giorni": None,
         "lockup_citazione": "", "lockup_durate": {}, "azioni_offerte": None, "offerte_citazione": "",
         "azioni_dopo": None, "dopo_citazione": "", "unit": False, "trust": False, "reit": False, "lp_unita": False}
    for rx in PREZZO:
        m = rx.search(cop)
        if m:
            f["prezzo"], f["prezzo_citazione"] = float(m.group(1)), cop[max(0, m.start() - 60):m.end() + 20]
            break
    if f["prezzo"] is None:
        m = TABELLA_PREZZO.search(cop) or TABELLA_COLONNE.search(cop)
        if m:
            f["prezzo"], f["prezzo_citazione"] = float(m.group(1)), cop[max(0, m.start() - 60):m.end() + 20]
    m = INTERVALLO.search(cop)
    if m:
        f["intervallo"] = (float(m.group(1)), float(m.group(2)))
    m = DATA.search(t[:COPERTINA]) or DATA.search(t)
    if m:
        try:
            mese, giorno, anno = m.group(1).replace(",", "").split()
            f["data_copertina"] = "{}-{:02d}-{:02d}".format(int(anno), MESI[mese.lower()], int(giorno))
        except (KeyError, ValueError):
            pass
    durate = collections.Counter()
    esempi = {}
    for m in LOCK.finditer(t):
        g = _giorni(m.group(1))
        if not g or g < 30 or g > 730:
            continue
        intorno = t[max(0, m.start() - 600):m.end() + 100].lower()
        if not re.search(r"lock[\s-]?up|officers|directors|stockholders|shareholders|holders\s+of", intorno):
            continue
        frase = t[max(t.rfind(". ", 0, m.start()), m.start() - 400):m.end()].lower()
        if re.search(r"option|additional\s+shares|over-?allotment|stabiliz|directed\s+share", frase):
            continue                                    # l'opzione dei collocatori, non il lock-up
        if NON_LOCKUP.search(t[max(0, m.start() - 250):m.start()]):
            continue                                    # la tabella della Rule 144, non il lock-up
        durate[g] += 1
        esempi.setdefault(g, t[max(0, m.start() - 200):m.end() + 40])
    for m in LOCK_TRATTINO.finditer(t):
        g = int(m.group(1))
        if 30 <= g <= 730:
            durate[g] += 1
            esempi.setdefault(g, t[max(0, m.start() - 200):m.end() + 40])
    if durate:
        #  La durata più frequente; a parità, la più corta (la prima scadenza, quella da cui parte la vendita).
        massimo = max(durate.values())
        g = min(d for d, n in durate.items() if n == massimo)
        f["lockup_giorni"], f["lockup_citazione"] = g, esempi[g]
        f["lockup_durate"] = dict(durate)
    m = TITOLO_OFFERTA.search(cop[:TITOLO_CARATTERI])
    if m:
        f["azioni_offerte"], f["offerte_citazione"] = _numero(m.group(1)), cop[max(0, m.start() - 60):m.end() + 40]
    else:
        for rx in OFFERTE:
            m = rx.search(cop)
            if m:
                f["azioni_offerte"], f["offerte_citazione"] = (_numero(m.group(1)),
                                                               cop[max(0, m.start() - 60):m.end() + 20])
                break
    m = CIRCOLAZIONE.search(t)
    if m:
        f["azioni_dopo"], f["dopo_citazione"] = _numero(m.group(1)), t[max(0, m.start() - 40):m.end() + 20]
    f["unit"] = bool(UNIT.search(cop))
    f["trust"] = bool(TRUST.search(cop))
    f["reit"] = bool(REIT.search(t[:200000]))
    f["lp_unita"] = bool(LP_UNITA.search(cop[:TITOLO_CARATTERI]))
    return f


def motivo(f: dict) -> str:
    """Esclusione dal testo, nell'ordine; stringa vuota se l'IPO resta."""
    if f["trust"]:
        return "SPAC (trust account dichiarato)"
    if f["unit"]:
        return "unit"
    if f["reit"]:
        return "REIT dichiarato"
    if f["prezzo"] is None:
        return "nessun prezzo di collocamento nel prospetto"
    if f["prezzo"] < 5:
        return "prezzo di collocamento sotto $5"
    return ""


def leggi(cik: str, percorso_indice: str) -> tuple[dict | None, str]:
    """(campi, url) scaricando il documento se serve (una chiamata, contata nel tetto)."""
    import survival as SV
    u, _acc = documento(cik, percorso_indice)
    if not u:
        return None, ""
    raw = C.budget().get(u)
    if raw is None:
        return None, u
    return estrai(SV.testo(raw)), u


if __name__ == "__main__":
    import csv
    import sys
    righe = [r for r in csv.DictReader((C.STATO / "universo.csv").open(encoding="utf-8")) if not r["motivo"]]
    passo = max(1, len(righe) // int(sys.argv[1])) if len(sys.argv) > 1 else 1
    for r in righe[::passo]:
        f, u = leggi(r["cik"], r["percorso_indice"])
        print(json.dumps({"nome": r["nome"], "anno": r["anno"], "url": u,
                          **({k: f[k] for k in ("prezzo", "intervallo", "data_copertina", "lockup_giorni", "lockup_durate",
                                                "azioni_offerte", "azioni_dopo", "unit", "trust", "reit")} if f else {}),
                          "motivo": motivo(f) if f else "documento non letto"}, ensure_ascii=False))
