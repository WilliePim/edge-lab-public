"""Popolazione del passo 2: chi e' osservato, chi e' risolto, chi e' uscito, e come.

Addendum 3. **Nessun rendimento**: questo script costruisce la popolazione delle celle,
classifica le uscite, sceglie il campione di validazione del classificatore e legge i
prezzi dei deal. I rendimenti sono del passo 2.

    python backtest/rematch_50_300m/survival.py popolazione
    python backtest/rematch_50_300m/survival.py campione
    python backtest/rematch_50_300m/survival.py concordanza
    python backtest/rematch_50_300m/survival.py deal

QUATTRO SOTTOCOMANDI, IN QUEST'ORDINE, PERCHE' L'ORDINE E' LA REGOLA.

  popolazione  cache soltanto, zero rete.
  campione     scarica i documenti del campione di validazione. Le etichette vere si
               scrivono a mano in step2_prep/validazione/_verita.json leggendo quei
               documenti, SENZA aprire _classificatore.json.
  concordanza  confronta, e decide se il classificatore si puo' usare (soglia 90%).
  deal         solo se il classificatore e' valido: prezzo per azione del deal, regex
               dichiarata, solo contanti.

Il tetto di 200 chiamate EDGAR vale per la somma di tutte le esecuzioni: il contatore sta
su disco, e una chiamata oltre il tetto non parte.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import gzip
import hashlib
import json
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import backtest_event_time as B  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "step2_prep"
VAL = OUT / "validazione"
S = B.STATE

#  Fonti di serie prezzi, in ordine di priorita'. `prices/` e' congelata con la sua impronta
#  nella pre-registrazione; `prices_resolved/` contiene solo le serie scaricate per la
#  mappatura dei ticker (addendum 3 §2) e non tocca quell'impronta.
FONTI = (S / "prices", S / "prices_resolved")

CACHE = ROOT / ".edgar_cache"
SUB = "https://data.sec.gov/submissions/"
ARCH = "https://www.sec.gov/Archives/edgar/data/"

TERM = frozenset({"25", "25-NSE", "15-12B", "15-12G", "15-15D"})
#  Le forme di acquisizione di uno strumento precedente (non incluso nella copia pubblica), piu' SC 14D9 (la risposta
#  del bersaglio a un'offerta).
ACQ = frozenset({"DEFM14A", "DEFM14C", "SC TO-T", "SC 13E3", "SC 13E-3", "SC TO-C", "SC 14D9"})

BANDE = (("<50M", 0.0, 50e6), ("50-300M", 50e6, 300e6), (">300M", 300e6, float("inf")))
COOLDOWN = 365
H = 126
MAX_STALE = 5
PRIMA_DI_TEND = 365
DOPO_TEND = 30

SEED = 20260915
N_CAMPIONE = 40
SOGLIA_CONCORDANZA = 0.90
TETTO_CHIAMATE = 200

TIPI_VERITA = ("ACQUISIZIONE", "FALLIMENTO", "LIQUIDAZIONE", "VOLONTARIO_OTC", "NON_DETERMINABILE")


# ------------------------------------------------------------------ comuni --
def banda(cap):
    if cap is None:
        return None
    for nome, lo, hi in BANDE:
        if lo <= cap < hi:
            return nome
    return None


def chiave(t):
    return (t or "").replace("/", "_").upper()


def cache_path(url):
    return CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".cache")


def file_in_cache(url):
    """Il file in cache per `url`, o None. Due formati con lo stesso nome: `.cache` in chiaro (i file vecchi) e
    `.cache.gz` (quello che `form4_scanner.edgar` scrive dalla revisione di settembre 2026). Guardare solo il primo
    rende invisibile tutto quello che si scarica dopo: il 22-09-2026 erano 999 file, e per quelle società
    `submissions` rispondeva «nessun deposito»."""
    p = cache_path(url)
    if p.exists():
        return p
    g = p.with_suffix(".cache.gz")
    return g if g.exists() else None


def in_cache(url):
    return file_in_cache(url) is not None


def leggi_cache(url):
    """Il corpo in cache per `url`, compresso o no, o None."""
    f = file_in_cache(url)
    if f is None:
        return None
    dati = f.read_bytes()
    if f.suffix == ".gz":
        dati = gzip.decompress(dati)
    return dati.decode("utf-8", errors="replace")


IDS, _IPX = B.load_series("IWM")
LAST = len(IDS) - 1


def sessione(d):
    return bisect.bisect_right(IDS, d) - 1


def eventi_con_veto():
    ver = {}
    for line in (S / "dilution.jsonl").open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        ver[(r["issuer_cik"], r["as_of"])] = r.get("verdict")
    return [e for e in B.load_events("2015-01-01") if ver.get((e["cik"], e["filed"])) != "BLOCKED"]


def righe_insider():
    """{(cik, deposito): [(data transazione, azioni, prezzo)]} dal corpus."""
    out = collections.defaultdict(list)
    for f in sorted(B.CORPUS.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                out[((r.get("issuer_cik") or "").lstrip("0"), r.get("filed_date"))].append(
                    (r.get("transaction_date") or "", float(r.get("shares") or 0),
                     float(r.get("price") or 0)))
    return out


class Azioni:
    """Azioni XBRL point-in-time: ultimo valore con `filed` <= D. Regola di marketcap_build.py @ ef0ff29."""

    def __init__(self):
        self._c = {}

    def at(self, cik, d):
        if cik not in self._c:
            p = S / "shares" / "{}.json".format(cik)
            by = {}
            if p.exists():
                for r in json.loads(p.read_text(encoding="utf-8")).get("primary") or []:
                    if r.get("filed") and r.get("val"):
                        by[r["filed"]] = float(r["val"])
            fd = sorted(by)
            self._c[cik] = (fd, [by[x] for x in fd])
        fd, v = self._c[cik]
        j = bisect.bisect_right(fd, d) - 1
        return v[j] if j >= 0 else None


def prezzo_insider(righe, e):
    """(data dell'ultima transazione, prezzo medio ponderato) delle righe dell'evento."""
    rs = [x for x in righe.get((e["cik"], e["filed"]), []) if x[1] > 0 and x[2] > 0 and x[0] <= e["filed"]]
    if not rs:
        return None, None
    return max(x[0] for x in rs), sum(x[1] * x[2] for x in rs) / sum(x[1] for x in rs)


def caps_backfill():
    caps = collections.defaultdict(list)
    for line in (S / "marketcap_rows.jsonl").open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("mcap"):
            caps[str(r["issuer"]).lstrip("0")].append((r["trans"], r["mcap"]))
    for k in caps:
        caps[k].sort()
    return caps


def cap_backfill(caps, e):
    xs = caps.get(e["cik"])
    if not xs:
        return None
    j = bisect.bisect_right([d for d, _ in xs], e["filed"]) - 1
    return xs[j][1] if j >= 0 else None


def indice_serie():
    idx = {}
    for d in FONTI:
        for p in sorted(d.glob("*.csv")):
            idx.setdefault(p.stem.upper(), p)
    return idx


def date_serie(path):
    ds = []
    with path.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d = line.split(",", 1)[0].strip()
            if len(d) == 10:
                ds.append(d)
    return ds


def submissions(cik):
    """(json, [(data, forma, item, accession, documento primario)]) dalla cache. Nessuna rete."""
    testo_sub = leggi_cache(SUB + "CIK{:010d}.json".format(int(cik)))
    if testo_sub is None:
        return None, []
    d = json.loads(testo_sub)
    blocchi = [d["filings"]["recent"]]
    for f in d["filings"].get("files") or []:
        pagina = leggi_cache(SUB + f["name"])
        if pagina is not None:
            blocchi.append(json.loads(pagina))
    dep = []
    for b in blocchi:
        n = len(b.get("form", []))

        def col(k):
            v = b.get(k) or []
            return v if len(v) == n else [""] * n

        for dt, fm, it, acc, doc in zip(col("filingDate"), col("form"), col("items"),
                                        col("accessionNumber"), col("primaryDocument")):
            dep.append((dt, fm, it or "", acc, doc))
    dep.sort()
    return d, dep


def finestra(dep, t_end):
    lo = (date.fromisoformat(t_end) - timedelta(days=PRIMA_DI_TEND)).isoformat()
    hi = (date.fromisoformat(t_end) + timedelta(days=DOPO_TEND)).isoformat()
    return [x for x in dep if lo <= x[0] <= hi]


def classifica(d, dep):
    """(classe, t_end). Addendum 3 §4. Precedenza: fallimento, liquidazione, acquisizione, volontario."""
    term = [x[0] for x in dep if x[1] in TERM]
    t_end = max(term) if term else (dep[-1][0] if dep else None)
    if not t_end:
        return "NON_RISOLTO", None
    w = finestra(dep, t_end)
    otto_k = [x for x in w if x[1].startswith("8-K")]
    nomi = [(d or {}).get("name") or ""] + [x.get("name") or "" for x in (d or {}).get("formerNames") or []]
    if any("1.03" in x[2] for x in otto_k):
        return "FALLIMENTO", t_end
    if any("LIQUIDAT" in n.upper() for n in nomi):
        return "LIQUIDAZIONE", t_end
    if any(x[1] in ACQ for x in w) or any("5.01" in x[2] for x in otto_k):
        return "ACQUISIZIONE", t_end
    if any(x[1] in TERM for x in w) or any("3.01" in x[2] for x in otto_k):
        return "VOLONTARIO_OTC", t_end
    return "NON_RISOLTO", t_end


# ------------------------------------------------------------- popolazione --
def popolazione(_a) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gated = eventi_con_veto()
    righe = righe_insider()
    azioni = Azioni()
    caps = caps_backfill()
    serie = indice_serie()
    base = {p.stem.upper() for p in FONTI[0].glob("*.csv")}

    per_banda = collections.defaultdict(list)
    for e in gated:
        oss = bool(e["ticker"]) and chiave(e["ticker"]) in base
        e = dict(e)
        e["osservato"] = oss
        if oss:
            e["cap"], e["cap_fonte"] = cap_backfill(caps, e), "marketcap_rows"
            e["data_insider"], e["prezzo_insider"] = prezzo_insider(righe, e)
        else:
            d_ins, px = prezzo_insider(righe, e)
            n = azioni.at(e["cik"], d_ins) if d_ins else None
            e["cap"] = n * px if (n and px) else None
            e["cap_fonte"] = "prezzo_insider_x_azioni_xbrl"
            e["data_insider"], e["prezzo_insider"] = d_ins, px
        b = banda(e["cap"])
        if b:
            per_banda[b].append(e)

    sub_cache = {}
    righe_out, tab = [], collections.defaultdict(collections.Counter)
    for nome, _lo, _hi in BANDE:
        for e in B.cooldown_filter(per_banda[nome], COOLDOWN):
            s0 = bisect.bisect_right(IDS, e["filed"])
            r = {"cik": e["cik"], "ticker": e["ticker"], "filed": e["filed"], "banda": nome,
                 "cap": e["cap"], "cap_fonte": e["cap_fonte"], "data_insider": e["data_insider"],
                 "prezzo_insider": e["prezzo_insider"], "stato": None, "classe": None,
                 "t_end": None, "serie": None}
            if s0 + H > LAST:
                r["stato"] = "TOO_RECENT"
            elif e["osservato"]:
                r["stato"], r["serie"] = "OSSERVATO", str(serie[chiave(e["ticker"])].relative_to(ROOT))
            else:
                if e["cik"] not in sub_cache:
                    sub_cache[e["cik"]] = submissions(e["cik"])
                d, dep = sub_cache[e["cik"]]
                oggi = (d or {}).get("tickers") or []
                if oggi:
                    trovata = next((serie[chiave(t)] for t in oggi if chiave(t) in serie), None)
                    if trovata is None:
                        r["stato"] = "GUASTO_FONTE"
                    else:
                        ds = date_serie(trovata)
                        j = bisect.bisect_left(ds, IDS[s0])
                        ok = j < len(ds) and sessione(ds[j]) - s0 <= MAX_STALE
                        r["stato"] = "RISOLTO" if ok else "VIVO_SENZA_STORIA"
                        r["serie"] = str(trovata.relative_to(ROOT))
                else:
                    classe, t_end = classifica(d, dep)
                    r["classe"], r["t_end"] = classe, t_end
                    if t_end and t_end < e["filed"]:
                        r["stato"] = "USCITO_PRIMA"
                    elif t_end and t_end <= IDS[s0 + H]:
                        r["stato"] = "TERMINATO_IN_FINESTRA"
                    else:
                        r["stato"] = "USCITO_DOPO"
            righe_out.append(r)
            tab[nome][(r["stato"], r["classe"] or "")] += 1

    with (OUT / "popolazione.jsonl").open("w", encoding="utf-8") as fh:
        for r in righe_out:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    L = ["# Popolazione del passo 2", "",
         "Generato da `python backtest/rematch_50_300m/survival.py popolazione`. Solo cache, "
         "nessuna chiamata di rete, nessun rendimento. Regole: addendum 3.", ""]
    for nome, _lo, _hi in BANDE:
        c = tab[nome]
        tot = sum(c.values())
        valutabili = tot - c[("TOO_RECENT", "")] - sum(v for (s, _k), v in c.items() if s == "USCITO_PRIMA")
        nucleo = c[("OSSERVATO", "")] + c[("RISOLTO", "")]
        L += ["## Cella {}".format(nome), "",
              "| stato | classe | eventi |", "|---|---|---:|"]
        for (s, k), v in sorted(c.items()):
            L.append("| `{}` | {} | {:,} |".format(s, k or "—", v))
        L += ["| **totale** | | **{:,}** |".format(tot), "",
              "Valutabili (senza `TOO_RECENT` e `USCITO_PRIMA`): **{:,}**. Osservati + risolti: "
              "**{:,}**, copertura **{:.1%}**.".format(valutabili, nucleo, nucleo / valutabili if valutabili else 0), ""]
    (OUT / "popolazione.md").write_text("\n".join(L), encoding="utf-8")
    print("scritto {} e {}".format(OUT / "popolazione.jsonl", OUT / "popolazione.md"))
    return 0


# --------------------------------------------------------- rete con tetto --
class Budget:
    """Il tetto di chiamate EDGAR, persistente fra le esecuzioni."""

    FILE = OUT / "edgar_calls.json"

    def __init__(self):
        from edgar_llm.config import get as env_get
        from form4_scanner.edgar import EdgarClient

        ua = env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")
        if not ua or "@" not in ua:
            raise SystemExit("serve EDGAR_USER_AGENT con nome ed email")
        #  0,15 s fra le richieste: al massimo ~6,7 al secondo, sotto il limite SEC di 10.
        self.client = EdgarClient(ua, cache_dir=CACHE, min_interval=0.15)
        self.usate = json.loads(self.FILE.read_text(encoding="utf-8"))["network"] if self.FILE.exists() else 0

    def get(self, url):
        """Testo, o None. None anche quando il tetto impedirebbe la chiamata."""
        if not in_cache(url) and self.usate >= TETTO_CHIAMATE:
            return None
        prima = self.client.stats["network"]
        txt = self.client.get(url)
        self.usate += self.client.stats["network"] - prima
        self.FILE.parent.mkdir(parents=True, exist_ok=True)
        self.FILE.write_text(json.dumps({"network": self.usate, "tetto": TETTO_CHIAMATE}), encoding="utf-8")
        return txt


def url_documento(cik, acc, doc):
    return "{}{}/{}/{}".format(ARCH, int(cik), acc.replace("-", ""), doc)


def testo(raw):
    from edgar_llm.fetch import UnreadableDocument, to_text
    try:
        return to_text(raw or "")
    except UnreadableDocument:
        return ""


def scegli_8k(w, preferenze):
    for item in preferenze:
        xs = [x for x in w if x[1].startswith("8-K") and item in x[2]]
        if xs:
            return xs[-1]
    xs = [x for x in w if x[1].startswith("8-K")]
    return xs[-1] if xs else None


# ---------------------------------------------------------------- campione --
def campione(_a) -> int:
    VAL.mkdir(parents=True, exist_ok=True)
    pop = [json.loads(l) for l in (OUT / "popolazione.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    in_p = sorted({r["cik"] for r in pop if r["banda"] == "50-300M" and r["stato"] == "TERMINATO_IN_FINESTRA"})
    altrove = sorted({r["cik"] for r in pop if r["banda"] != "50-300M" and r["stato"] == "TERMINATO_IN_FINESTRA"} - set(in_p))
    rng = random.Random(SEED)
    if len(in_p) >= N_CAMPIONE:
        scelti = sorted(rng.sample(in_p, N_CAMPIONE))
    else:
        scelti = in_p + sorted(rng.sample(altrove, min(N_CAMPIONE - len(in_p), len(altrove))))

    budget = Budget()
    classi, indice = {}, []
    for cik in scelti:
        d, dep = submissions(cik)
        classe, t_end = classifica(d, dep)
        classi[cik] = classe
        w = finestra(dep, t_end) if t_end else []
        docs = []
        f25 = [x for x in w if x[1] in ("25", "25-NSE")]
        if f25:
            docs.append(f25[-1])
        otto = scegli_8k(w, ("1.03", "5.01", "2.01", "3.01"))
        if otto:
            docs.append(otto)
        L = ["# CIK {} — {}".format(cik, (d or {}).get("name")), "",
             "Nomi precedenti: {}".format("; ".join("{} (fino al {})".format(x.get("name"), (x.get("to") or "")[:10])
                                                    for x in (d or {}).get("formerNames") or []) or "—"), "",
             "Depositi nella finestra di lettura ({} → +{} giorni dall'ultimo Form 25/15, o dall'ultimo deposito):".format(
                 PRIMA_DI_TEND, DOPO_TEND), ""]
        L += ["- {} `{}` item {}".format(dt, fm, it or "—") for dt, fm, it, _acc, _doc in w[-25:]]
        for dt, fm, it, acc, doc in docs:
            url = url_documento(cik, acc, doc)
            t = testo(budget.get(url))
            L += ["", "## {} `{}` del {} — {}".format(fm, acc, dt, url), ""]
            if not t:
                L.append("_documento non scaricato (tetto) o illeggibile_")
                continue
            t = re.sub(r"\s+", " ", t)
            pezzi = []
            for m in re.finditer(r"Item\s+(1\.03|2\.01|3\.01|5\.01|8\.01)", t, re.I):
                pezzi.append(t[m.start():m.start() + 2500])
                if len(pezzi) == 3:
                    break
            L += (pezzi or [t[:4000]])
        (VAL / "{}.md".format(cik)).write_text("\n".join(L), encoding="utf-8")
        indice.append({"cik": cik, "nome": (d or {}).get("name"), "documenti": [x[3] for x in docs]})
    #  La classe del classificatore sta in un file separato: le etichette vere si scrivono
    #  leggendo i documenti, senza guardarla.
    (VAL / "_classificatore.json").write_text(json.dumps(classi, indent=1, sort_keys=True), encoding="utf-8")
    (VAL / "_campione.json").write_text(json.dumps(
        {"seed": SEED, "cella_P": len(in_p), "integrati_da_altre_celle": len(scelti) - min(len(in_p), len(scelti)),
         "emittenti": indice}, indent=1), encoding="utf-8")
    print("campione di {} emittenti ({} dalla cella P); chiamate EDGAR usate in totale: {}".format(
        len(scelti), min(len(in_p), len(scelti)), budget.usate))
    return 0


# ------------------------------------------------------------- concordanza --
def concordanza(_a) -> int:
    verita = json.loads((VAL / "_verita.json").read_text(encoding="utf-8"))
    classi = json.loads((VAL / "_classificatore.json").read_text(encoding="utf-8"))
    righe, conc = [], 0
    for cik in sorted(classi):
        v = (verita.get(cik) or {}).get("tipo", "MANCANTE")
        if v not in TIPI_VERITA:
            raise SystemExit("tipo non ammesso per {}: {}".format(cik, v))
        c = classi[cik]
        ok = (c == v) or (c == "NON_RISOLTO" and v == "NON_DETERMINABILE")
        conc += ok
        righe.append((cik, c, v, ok, (verita.get(cik) or {}).get("citazione", "")))
    n = len(classi)
    p = conc / n if n else 0.0
    valido = p >= SOGLIA_CONCORDANZA
    L = ["# Validazione del classificatore d'uscita", "",
         "{} emittenti, seme {}. Concordanti: **{} su {} = {:.1%}**, soglia {:.0%}: **{}**.".format(
             n, SEED, conc, n, p, SOGLIA_CONCORDANZA,
             "classificatore VALIDO" if valido else "classificatore NON VALIDO — tutti i terminati in finestra a S_zero"), "",
         "| CIK | classificatore | lettura dei documenti | concorda | citazione |", "|---|---|---|---|---|"]
    for cik, c, v, ok, cit in righe:
        L.append("| {} | {} | {} | {} | {} |".format(cik, c, v, "sì" if ok else "**no**", cit.replace("|", "/")[:160]))
    (OUT / "validazione.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (OUT / "validazione_esito.json").write_text(json.dumps(
        {"n": n, "concordanti": conc, "concordanza": p, "soglia": SOGLIA_CONCORDANZA,
         "classificatore_valido": valido}, indent=1), encoding="utf-8")
    print("concordanza {:.1%} -> {}".format(p, "VALIDO" if valido else "NON VALIDO"))
    return 0


# -------------------------------------------------------------------- deal --
IMPORTO = r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,4})?)"
CONTANTI = (
    re.compile(r"right to receive\s+(?:an amount in cash equal to\s+)?" + IMPORTO
               + r"(?:\s+per\s+share)?,?\s+in\s+cash", re.I),
    re.compile(IMPORTO + r"\s+per\s+share(?:\s+of\s+[\w\s.,]{0,60}?)?,?\s+(?:in\s+cash|net\s+to\s+the\s+"
               r"(?:seller|holder)s?(?:\s+thereof)?\s+in\s+cash)", re.I),
    re.compile(r"(?:merger|offer|per\s+share)\s+(?:consideration|price)\s+of\s+" + IMPORTO
               + r"(?:\s+per\s+share)?,?\s+in\s+cash", re.I),
    re.compile(r"liquidating\s+distributions?\s+(?:of|totaling|aggregating)\s+(?:approximately\s+)?"
               + IMPORTO + r"\s+per\s+share", re.I),
)
MISTO = re.compile(r"exchange\s+ratio|stock\s+consideration|fraction\s+of\s+a\s+share|"
                   r"shares\s+of\s+common\s+stock\s+of|in\s+stock|and\s+0\.\d+\s+(?:of\s+a\s+)?shares?", re.I)


def leggi_deal(t):
    """(esito, prezzo, citazione) su un testo. Esiti: CONTANTI, MISTO, AMBIGUO, NON_TROVATO."""
    t = re.sub(r"\s+", " ", t or "")
    trovati = []
    for rx in CONTANTI:
        for m in rx.finditer(t):
            ctx = t[max(0, m.start() - 300):m.end() + 300]
            trovati.append((float(m.group(1).replace(",", "")), bool(MISTO.search(ctx)), ctx.strip()))
    if not trovati:
        return "NON_TROVATO", None, ""
    if any(misto for _, misto, _ in trovati):
        return "MISTO", None, next(ctx for _, misto, ctx in trovati if misto)[:400]
    importi = sorted({round(x, 4) for x, _, _ in trovati})
    if len(importi) > 1:
        return "AMBIGUO", None, "; ".join("${}".format(x) for x in importi)
    return "CONTANTI", importi[0], trovati[0][2][:400]


def deal(_a) -> int:
    esito_val = json.loads((OUT / "validazione_esito.json").read_text(encoding="utf-8"))
    pop = [json.loads(l) for l in (OUT / "popolazione.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    obiettivi = sorted({r["cik"] for r in pop if r["banda"] == "50-300M" and r["stato"] == "TERMINATO_IN_FINESTRA"
                        and r["classe"] in ("ACQUISIZIONE", "LIQUIDAZIONE")})
    righe = []
    if not esito_val["classificatore_valido"]:
        righe = [{"cik": c, "esito": "CLASSIFICATORE_NON_VALIDO"} for c in obiettivi]
    else:
        budget = Budget()
        for cik in obiettivi:
            d, dep = submissions(cik)
            _classe, t_end = classifica(d, dep)
            w = finestra(dep, t_end)
            candidati = []
            otto = scegli_8k(w, ("5.01", "2.01", "8.01"))
            if otto:
                candidati.append(otto)
            candidati += [x for x in reversed(w) if x[1] in ("DEFM14A", "DEFM14C")][:1]
            candidati += [x for x in reversed(w) if x[1] == "SC TO-T"][:1]
            r = {"cik": cik, "esito": "NON_TROVATO", "prezzo": None}
            for dt, fm, it, acc, doc in candidati:
                raw = budget.get(url_documento(cik, acc, doc))
                if raw is None:
                    r = {"cik": cik, "esito": "NON_SCARICATO", "prezzo": None}
                    break
                es, px, cit = leggi_deal(testo(raw))
                r = {"cik": cik, "esito": es, "prezzo": px, "forma": fm, "accession": acc, "data": dt, "citazione": cit}
                if es in ("CONTANTI", "MISTO"):
                    break
            righe.append(r)
        print("chiamate EDGAR usate in totale: {}".format(budget.usate))
    with (OUT / "deal.jsonl").open("w", encoding="utf-8") as fh:
        for r in righe:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print("deal:", dict(collections.Counter(r["esito"] for r in righe)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for nome, fn in (("popolazione", popolazione), ("campione", campione),
                     ("concordanza", concordanza), ("deal", deal)):
        sp.add_parser(nome).set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
