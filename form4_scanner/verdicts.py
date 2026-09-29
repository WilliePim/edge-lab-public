"""Il registro dei verdetti: giudizio dell'operatore, registrato, mai prodotto.

ESTENDE IL CONFINE DI `CLAUDE.md`. Lo scanner calcola fatti e non produce
giudizi. Un verdetto E' un giudizio, quindi non puo' nascere qui: e' un **campo
di input umano**, un'annotazione dell'operatore. Lo scanner ha esattamente due
diritti su questo file:

  1. **scriverlo quando glielo si detta**, dalla CLI, campo per campo;
  2. **misurarlo**, nel report mensile.

Non lo scrive mai da solo, non lo aggiorna, non lo interpreta. Nessuna
esecuzione dello scan tocca questo file.

APPEND-ONLY, E MAI UNA MODIFICA. Un cambio di verdetto e' una riga nuova con
`supersedes` che punta all'id della precedente sullo stesso CIK. Il verdetto
corrente di un emittente e' quello che nessun altro supersede. La storia dei
ripensamenti e' meta' del valore del registro: sapere che un HOLD e' diventato
SELL il 12 novembre, e perche', vale piu' del SELL.

VIVE IN `data/`, NON IN `state/`. `state/` e' cache, corpus, panel, e si puo'
azzerare. Questo no: non si puo' ricostruire da EDGAR, perche' non viene da
EDGAR. Il file non fa parte del repository (e' in `.gitignore`): ogni operatore
ha il suo, e senza file `load` restituisce una lista vuota.

NESSUN DEFAULT SU `verdict`, `thesis`, `invalidation`. Un verdetto senza tesi e
senza condizione di invalidazione non e' un giudizio, e' un'opinione: se
mancano, la CLI rifiuta invece di inventare.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "data" / "verdicts.jsonl"

CLASSES = ("SELL", "HOLD", "BUY", "STRONG_BUY")


def _id(rec: dict) -> str:
    """Identita' stabile della riga: data + cik + tesi, in dodici esadecimali."""
    raw = "{}|{}|{}".format(rec.get("date"), rec.get("cik"), rec.get("thesis"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def load(path=None) -> list:
    """Ogni evento, in ordine di scrittura. [] se il registro non esiste."""
    p = Path(path or LEDGER)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue                       # una riga rotta non ne nasconde 50
    return out


def current(path=None) -> dict:
    """{cik senza zeri: verdetto in vigore}. Superato = non in vigore."""
    rows = load(path)
    superseded = {r.get("supersedes") for r in rows if r.get("supersedes")}
    out = {}
    for r in rows:
        if r.get("id") in superseded:
            continue
        cik = str(r.get("cik", "")).lstrip("0")
        if not cik:
            continue
        #  L'ultima riga vince a parita' di CIK: due verdetti nello stesso
        #  giorno senza supersedes sono un errore di inserimento, non due
        #  verdetti, e mostrarne uno solo e' meglio che mostrarli entrambi.
        prev = out.get(cik)
        if prev is None or str(r.get("date", "")) >= str(prev.get("date", "")):
            out[cik] = r
    return out


def add(cik, ticker, verdict, thesis, invalidation, *,
        price_at_verdict=None, cap_bucket=None, terreno=None, score_v3=None,
        upgrade_triggers=None, review_date=None, source_report=None,
        has_13d=None, expected_return_pct=None, expected_horizon_months=None,
        on=None, path=None) -> dict:
    """Aggiunge un evento. Solleva ValueError su cio' che non si puo' dedurre."""
    verdict = (verdict or "").strip().upper()
    if verdict not in CLASSES:
        raise ValueError("verdict deve essere uno di {}, ricevuto {!r}".format(
            ", ".join(CLASSES), verdict))
    if not (thesis or "").strip():
        raise ValueError("thesis mancante: un verdetto senza tesi non e' un "
                         "giudizio, e lo scanner non ne inventa una")
    inval = [s for s in (invalidation or []) if str(s).strip()]
    if not inval:
        raise ValueError("invalidation mancante: serve almeno una condizione "
                         "che, se si avvera, dice che il verdetto era sbagliato")

    on = on or date.today()
    cik = str(cik).lstrip("0")
    prev = current(path).get(cik)
    rec = {
        "date": on.isoformat() if hasattr(on, "isoformat") else str(on),
        "ticker": (ticker or "").upper() or None,
        "cik": cik,
        "verdict": verdict,
        "price_at_verdict": float(price_at_verdict) if price_at_verdict else None,
        "cap_bucket": cap_bucket,
        "terreno": terreno,
        "score_v3": int(score_v3) if score_v3 is not None else None,
        "thesis": thesis.strip(),
        "invalidation": inval,
        "upgrade_triggers": [s for s in (upgrade_triggers or []) if str(s).strip()],
        "review_date": (review_date.isoformat()
                        if hasattr(review_date, "isoformat")
                        else (review_date or None)),
        "source_report": source_report or None,
        "has_13d": has_13d,
        #  L'attesa dell'operatore, in percentuale e su quale orizzonte. Sta qui e
        #  non in una tabella a parte perche' e' una previsione come le altre e
        #  va confrontata come le altre: nel mensile finisce accanto al
        #  rendimento realizzato.
        "expected_return_pct": (float(expected_return_pct)
                                if expected_return_pct is not None else None),
        "expected_horizon_months": expected_horizon_months,
        "supersedes": (prev or {}).get("id"),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    rec["id"] = _id(rec)

    p = Path(path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
    return rec


# ------------------------------------------------------------ invalidazioni --
#  Una condizione di invalidazione e' scritta in italiano o in inglese da un
#  essere umano. Lo scanner NON la interpreta: leggerebbe un'intenzione, che e'
#  esattamente cio' che il confine gli vieta.
#
#  Quello che puo' fare senza interpretare e' confrontare un prezzo con un
#  numero, quando la condizione e' scritta in una forma che contiene un numero e
#  una direzione. Tutto il resto viene riportato alla lettera e marcato NON
#  VERIFICABILE, perche' "senza notizie" o "crescita di un segmento < 7%" non sono
#  domande che un file di prezzi possa chiudere.
import re as _re

_PRICE_RULE = _re.compile(
    r"\b(?:close|chiusura|chiude|prezzo|price)\b[^0-9]{0,24}"
    r"\b(below|under|sotto|above|over|sopra)\b[^0-9]{0,12}"
    r"([0-9]+(?:[.,][0-9]+)?)", _re.I)


FILLER = {"a", "the", "il", "lo", "la", "di", "da", "in", "su", "and", "e",
          "or", "o", "of", "for", "per", "usd", "eur", "$", "-", "--"}


def check_invalidation(text: str, price):
    """(esito, spiegazione). esito True/False/None -- None = non verificabile.

    Verifica SOLO le condizioni che sono per intero un confronto fra un prezzo e
    un numero. «close below 18.50» si', «close below 18.50 without news» NO:
    quella e' una congiunzione, e chiudere la prima meta' ignorando la seconda
    sarebbe lo scanner che decide al posto dell'operatore che «senza notizie» vale.
    Restituisce comunque il fatto sul prezzo nella spiegazione, cosi' chi legge
    ha il numero senza avere un verdetto.
    """
    m = _PRICE_RULE.search(text or "")
    if not m or price is None:
        return None, "non verificabile automaticamente"
    direction = m.group(1).lower()
    try:
        level = float(m.group(2).replace(",", "."))
    except ValueError:
        return None, "non verificabile automaticamente"
    below = direction in ("below", "under", "sotto")
    met = price < level if below else price > level
    if met:
        fact = "prezzo {:.2f} {} {:.2f}".format(
            price, "<" if below else ">", level)
    else:
        fact = "prezzo {:.2f} {} {:.2f}".format(
            price, ">=" if below else "<=", level)

    #  Cosa resta della frase, tolto il confronto sul prezzo.
    rest = (text[:m.start()] + " " + text[m.end():]).lower()
    words = [w for w in _re.findall(r"[a-z0-9%]+", rest) if w not in FILLER]
    if words:
        return None, "{} — resta da verificare a mano: «{}»".format(
            fact, " ".join(words))
    return met, fact
