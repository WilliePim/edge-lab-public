"""Russell 2000, uscite verso il basso — partecipazioni di IWM e IWB dai depositi SEC (piano B1).

Istantanee per anno 2015-2025: 31 marzo (N-PORT-P se esiste, altrimenti il prospetto completo del N-CSR, voce 6) e
30 giugno (N-PORT-P se esiste, altrimenti N-Q). Il 30 giugno 2019 non esiste (fase 0): l'istantanea resta assente.

- N-PORT-P: `primary_doc.xml`, righe `invstOrSec` con `assetCat` = EC (azioni ordinarie): nome, titolo, CUSIP, ISIN,
  azioni, valore in dollari.
- N-Q / N-CSR: HTML con tutti i fondi della famiglia; si prende solo il prospetto COMPLETO del fondo esatto
  («Schedule of Investments … iSHARES ® RUSSELL 2000 ETF <data>», non «Summary», non Growth/Value), sezione COMMON STOCKS:
  nome, azioni, valore. Niente CUSIP.

Output `state/backfill/russell/holdings/{fondo}_{periodo}.csv` e manifesto con sha256 e conteggi. Chiamate EDGAR sul
tetto di `sec.py`. Nessuna dipendenza nuova.

    python backtest/russell_exits/partecipazioni_sec.py
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import sec  # noqa: E402

DEPOSITI = HERE / "risultati" / "fase0_depositi.json"
OUT = ROOT / "state" / "backfill" / "russell" / "holdings"
MANIFEST = OUT / "_manifest.json"
ANNI = range(2015, 2026)
#  Due anni hanno il 30 giugno di domenica con zero sedute dopo la ricostituzione del venerdi': l'istantanea non ha
#  ancora recepito il cambio di indice (nel 2024 si contano 17 entrate invece delle 190-285 degli altri anni, e il
#  2019 non ha proprio il file). Per quegli anni serve un'istantanea piu' in la' come file «dopo»: il 30 settembre,
#  deciso dall'utente il 17-09-2026. Tabella: risultati/controllo_date_giugno.md.
PERIODI_IN_PIU = {2019: ("2019-09-30",), 2024: ("2024-09-30",)}
NOME_FONDO = {"IWM": "RUSSELL 2000 ETF", "IWB": "RUSSELL 1000 ETF"}
ARCH = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{nome}"
MESI = "January|February|March|April|May|June|July|August|September|October|November|December"
TESTATA = re.compile(r"(Summary\s+)?Schedule\s+of\s+Investments(?:\s*\((?:Unaudited|Continued)\))*(?:\s*\((?:Unaudited|Continued)\))?"
                     r"\s+iSHARES\s*®?\s*(.+?)\s+ETF\s+(" + MESI + r")\s+(\d{1,2}),\s+(20\d\d)", re.I)
NUM = re.compile(r"^\(?\$?\s*[\d,]+(?:\.\d+)?\)?$")
NOTE = re.compile(r"(?:\s+(?:[a-z](?:,[a-z])*|(?:\([a-z]\))+))+$")
COLONNE = {"Security", "Shares", "Value", "% of Net Assets", "Shares or Principal", "Principal"}
TOTALI = re.compile(r"^(total|net assets|other assets|liabilities|see accompanying)", re.I)


# ------------------------------------------------------------------ N-PORT --
def righe_nport(xml_txt):
    root = ET.fromstring(xml_txt.encode("utf-8"))
    ns = {"n": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    q = (lambda t: "n:" + t) if ns else (lambda t: t)
    per = root.find(".//" + q("repPdDate"), ns)
    serie = root.find(".//" + q("seriesName"), ns)
    out = []
    for x in root.iter(("{%s}invstOrSec" % ns["n"]) if ns else "invstOrSec"):
        def v(tag):
            e = x.find(q(tag), ns)
            return (e.text or "").strip() if e is not None and e.text else ""
        isin = x.find(q("identifiers") + "/" + q("isin"), ns)
        out.append({"nome": v("name"), "titolo": v("title"), "cusip": v("cusip"),
                    "isin": isin.get("value", "") if isin is not None else "", "azioni": v("balance"),
                    "unita": v("units"), "valore": v("valUSD"), "categoria": v("assetCat")})
    return (per.text.strip() if per is not None else ""), (serie.text.strip() if serie is not None else ""), out


# --------------------------------------------------------------- N-Q / N-CSR --
def testo_a_righe(h):
    """HTML → righe di celle: </tr> chiude una riga, </td>/</th> separano le celle, i blocchi di testo sono righe."""
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)</t[dh]\s*>", "\t", h)
    h = re.sub(r"(?i)</tr\s*>|</p\s*>|<br\s*/?>|</div\s*>|</h\d\s*>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h).replace("\xa0", " ")
    for riga in h.split("\n"):
        celle = [re.sub(r"\s+", " ", c).strip() for c in riga.split("\t")]
        celle = [c for c in celle if c and c != "$"]
        if celle:
            yield celle


FONDO_RE = re.compile(r"iSHARES\s*®?\s*(RUSSELL[\w \-]*?)\s+ETF\b", re.I)
DATA_RE = re.compile(r"(" + MESI + r")\s+(\d{1,2}),?\s*(20\d\d)", re.I)
TRATTINO_PCT = re.compile(r"—\s*\(?[\d.]+\)?\s*%")
ALTRE = ("right", "warrant", "preferred", "short-term", "money market", "investment compan", "other interest",
         "futures", "master limited", "closed-end", "exchange-traded")
RUMORE = ("see accompanying", "see notes", "percentages shown", "table of contents")


def _categoria(testo, attuale):
    s = testo.lower()
    if "total" in s:
        return "FINE"
    if "common stock" in s:
        return "COMMON"
    if any(k in s for k in ALTRE):
        return "ALTRO"
    return attuale                                  # intestazione di settore: la categoria non cambia


def righe_html(h, fondo, periodo):
    """Righe delle azioni ordinarie del prospetto completo di `fondo` alla data `periodo` (AAAA-MM-GG).

    Tre formati iShares (2015-2017, 2018, 2019): ogni cella esce su una riga sua, quindi si legge un flusso di pezzi.
    Intestazione del fondo: nei pezzi intorno a «Schedule of Investments» (non «Summary»), in qualsiasi ordine.
    Settori e categorie: i pezzi si accumulano finche' un pezzo con «— x%» chiude l'intestazione; «Common Stocks»
    apre le azioni ordinarie, «Total …» o un'altra categoria le chiude. Una riga = nome accumulato + azioni + valore.
    """
    anno, mese, giorno = periodo.split("-")
    pezzi = [c for celle in testo_a_righe(h) for c in celle]
    out, dentro, cat, buf, azioni = [], False, "", [], None
    for i, tok in enumerate(pezzi):
        basso = tok.lower()
        if "schedule of investments" in basso:
            fin = " ".join(pezzi[max(0, i - 2):i + 5])
            mf, md = FONDO_RE.search(fin), DATA_RE.search(fin)
            giusto = (mf is not None and re.sub(r"\s+", " ", mf.group(1)).upper().strip() + " ETF" == fondo
                      and md is not None and md.group(1).lower() == MESI.split("|")[int(mese) - 1].lower()
                      and int(md.group(2)) == int(giorno) and md.group(3) == anno)
            dentro = giusto and "summary" not in basso
            if "continued" not in fin.lower():
                cat = ""
            buf, azioni = [], None
            continue
        if not dentro:
            continue
        if tok in COLONNE or any(basso.startswith(r) for r in RUMORE):
            buf, azioni = [], None
            continue
        if NUM.match(tok):
            if not buf:
                continue
            if azioni is None:
                azioni = tok
                continue
            nome = " ".join(buf).strip()
            if cat == "COMMON" and not TOTALI.match(nome) and "other securities" not in nome.lower():
                out.append({"nome": re.sub(r"^[—\-\s]+", "", NOTE.sub("", nome)).strip(), "titolo": "", "cusip": "", "isin": "",
                            "azioni": azioni.replace(",", "").replace("$", "").strip(), "unita": "NS",
                            "valore": tok.replace(",", "").replace("$", "").strip("() "), "categoria": "EC"})
            buf, azioni = [], None
            continue
        if azioni is not None:                      # testo fra azioni e valore: riga rotta, si riparte
            buf, azioni = [], None
        if TRATTINO_PCT.search(tok) or (re.match(r"^\(?[\d.]+\)?\s*%$", tok) and buf and buf[-1].rstrip().endswith("—")):
            cat = _categoria(" ".join(buf + [tok]), cat)
            buf = []
            continue
        if basso.rstrip().endswith("(continued)"):
            buf = []                                # settore ripetuto a inizio pagina
            continue
        ha_minuscole = bool(re.search(r"[a-z]", tok))
        if ha_minuscole and buf and not any(re.search(r"[a-z]", x) for x in buf) and len(" ".join(buf)) > 3:
            nuova = _categoria(" ".join(buf), cat)   # intestazione in maiuscolo senza percentuale
            if nuova != cat or any(k in " ".join(buf).lower() for k in ("common stock",)):
                cat = nuova
                buf = []
            elif not re.search(r"\d", " ".join(buf)) and len(buf) >= 1 and all(len(x) > 2 for x in buf) and \
                    " ".join(buf).isupper() and ("&" in " ".join(buf) or len(" ".join(buf).split()) >= 2):
                buf = []                            # settore in maiuscolo (es. «AEROSPACE & DEFENSE»)
        if re.match(r"^\s*common\s+stocks?\s*$", basso) or basso in ("common",) and i + 1 < len(pezzi) and \
                pezzi[i + 1].lower().startswith("stock"):
            cat, buf = "COMMON", []
            continue
        buf.append(tok)
    return out


# -------------------------------------------------------------------- main --
def scegli(depositi, periodo):
    cand = [d for d in depositi if d["periodo"] == periodo]
    for tipo in ("NPORT-P", "N-CSR", "N-Q"):
        for d in cand:
            if d["tipo"] == tipo:
                return d
    return None


def documento(b, cik, d):
    acc = d["accession"].replace("-", "")
    if d["tipo"] == "NPORT-P":
        return b.get(ARCH.format(cik=int(cik), acc=acc, nome="primary_doc.xml")), "primary_doc.xml"
    idx = b.get(ARCH.format(cik=int(cik), acc=acc, nome="index.json"))
    if not idx:
        return None, ""
    items = [i for i in json.loads(idx)["directory"]["item"] if i["name"].lower().endswith(".htm")
             and "ex99" not in i["name"].lower() and "index" not in i["name"].lower()]
    if not items:
        return None, ""
    nome = max(items, key=lambda i: int(i.get("size") or 0))["name"]
    return b.get(ARCH.format(cik=int(cik), acc=acc, nome=nome)), nome


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--periodi", help="solo questi periodi, separati da virgola (per esempio 2019-09-30,2024-09-30)")
    #  Il tetto e' cumulativo su tutto il lavoro del Russell (`edgar_calls.json`), non per esecuzione: un giro
    #  parziale che chiede quattro documenti va rifiutato se il contatore e' gia' oltre, a meno di alzarlo apposta.
    ap.add_argument("--tetto", type=int, default=sec.TETTO, help="tetto cumulativo delle chiamate EDGAR")
    a = ap.parse_args(argv)
    solo = set(a.periodi.split(",")) if a.periodi else None
    OUT.mkdir(parents=True, exist_ok=True)
    dep = json.loads(DEPOSITI.read_text(encoding="utf-8"))
    b = sec.Budget(tetto=a.tetto)
    man = {}
    for anno in ANNI:
        for sym, fondo in NOME_FONDO.items():
            cik = dep["fondi"][sym]["cik"]
            periodi = ("{}-03-31".format(anno), "{}-06-30".format(anno)) + PERIODI_IN_PIU.get(anno, ())
            for periodo in periodi:
                if solo and periodo not in solo:
                    continue
                chiave = "{}_{}".format(sym, periodo)
                d = scegli(dep["depositi"][sym], periodo)
                if d is None:
                    man[chiave] = {"esito": "DEPOSITO_ASSENTE"}
                    print(chiave, "DEPOSITO_ASSENTE", flush=True)
                    continue
                txt, nome_doc = documento(b, cik, d)
                if not txt:
                    man[chiave] = {"esito": "DOCUMENTO_NON_SCARICATO", "tipo": d["tipo"], "accession": d["accession"]}
                    print(chiave, "DOCUMENTO_NON_SCARICATO", flush=True)
                    continue
                if d["tipo"] == "NPORT-P":
                    per, serie, righe = righe_nport(txt)
                    controllo = "periodo {} serie {}".format(per, serie)
                    ok = per == periodo and fondo.lower() in serie.lower()
                    righe = [r for r in righe if r["categoria"] == "EC"]
                else:
                    righe = righe_html(txt, fondo, periodo)
                    controllo, ok = "prospetto completo", bool(righe)
                p = OUT / "{}.csv".format(chiave)
                with p.open("w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=["nome", "titolo", "cusip", "isin", "azioni", "unita", "valore", "categoria"])
                    w.writeheader()
                    w.writerows(righe)
                valore = sum(float(r["valore"] or 0) for r in righe)
                man[chiave] = {"esito": "OK" if ok else "CONTROLLO_FALLITO", "tipo": d["tipo"], "accession": d["accession"],
                               "documento": nome_doc, "controllo": controllo, "righe": len(righe),
                               "valore_totale": round(valore, 2), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                print(chiave, d["tipo"], man[chiave]["esito"], "righe", len(righe), "valore {:,.0f}".format(valore),
                      "chiamate", b.usate, flush=True)
    if solo and MANIFEST.exists():                 # un giro parziale aggiorna il manifesto, non lo sostituisce
        vecchio = json.loads(MANIFEST.read_text(encoding="utf-8"))
        vecchio.update(man)
        man = vecchio
    MANIFEST.write_text(json.dumps(man, indent=1, sort_keys=True), encoding="utf-8")
    print("chiamate di rete usate:", b.usate, "negate:", b.negate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
