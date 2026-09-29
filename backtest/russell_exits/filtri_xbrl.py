"""Russell 2000, uscite verso il basso — filtri di qualità dai companyfacts EDGAR (piano B5). Funzioni pure.

Solo fatti con `filed` < data di riferimento (Rank Day). Ogni filtro risponde True (passa), False (non passa) o None (non
verificabile) con un motivo; il chiamante esclude i None e li conta a parte.

1. Flusso di cassa operativo 12 mesi > 0 (`NetCashProvidedByUsedInOperatingActivities` → `…ContinuingOperations`).
2. Cassa netta, oppure debito netto / EBITDA < 3; EBITDA ≤ 0 con debito netto > 0 = non passa. Tag di
   `tools/backfill_gates.py` (INSTANT, DURATION); aritmetica di `form4_scanner/xbrl.py` (`net_debt`, `ebitda`).
3. Azioni in circolazione +5% o meno in 12 mesi (`dei:EntityCommonStockSharesOutstanding` → `us-gaap:
   CommonStockSharesOutstanding`), corrette per i frazionamenti di Yahoo fra le due date.

12 mesi: ultimo anno fiscale + progressivo dell'anno in corso − progressivo dello stesso periodo dell'anno prima;
senza anno fiscale, quattro trimestri consecutivi. NON si usa `backfill_gates.four_quarters` (somma trimestri duplicati o
non consecutivi). Dati più vecchi di 270 giorni alla data = non verificabile.

STATO (23/09/2026, ADR-053): il fallback di `azioni_per_deposito` a `us-gaap:CommonStockSharesOutstanding`, quando
`dei:EntityCommonStockSharesOutstanding` non è ancora disponibile, è filtrato da `stato_plausibilita` — chiuso per
i gusci pre-riorganizzazione e per gli errori di scala grandi. **Limite noto, non risolto per costruzione:** una
società a classi multiple il cui valore di fallback implica un prezzo per azione ancora dentro una fascia plausibile
(decine-centinaia di dollari) passa come `ok` o `non_verificato` anche se sbagliata — nessun controllo sul solo
prezzo implicito può distinguerla da un titolo vero comparabile. Verificato su Houlihan Lokey, Aziyo, Nuvalent
(sbagliati per confronto col prospetto in E3, non intercettati). Chi riusa questo modulo su un nuovo universo
dovrebbe aspettarsi lo stesso falso negativo silenzioso e, dove possibile, incrociare con una fonte indipendente
specifica del proprio caso.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from form4_scanner.xbrl import ebitda, net_debt  # noqa: E402

INSTANT = {                                   # copia di tools/backfill_gates.py::INSTANT (import evitato: il modulo apre il client EDGAR)
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"],
    "st_debt": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "assets": ["Assets"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}
DURATION = {
    "ebit": ["OperatingIncomeLoss"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
}
AZIONI = (("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "CommonStockSharesOutstanding"))
DEI_AZIONI = AZIONI[0]
ETA_MAX = 270
SOGLIA_LEVA, SOGLIA_AZIONI = 3.0, 0.05

#  Il fallback a us-gaap:CommonStockSharesOutstanding (quando dei:EntityCommonStockSharesOutstanding non è ancora
#  disponibile alla data di riferimento) può restituire un numero non rappresentativo del totale azioni: il valore
#  nominale di un guscio pre-riorganizzazione (100, 1.000 azioni) o una sola classe di una società a classi multiple
#  (l'API companyfacts della SEC toglie l'informazione di dimensione/classe, quindi non è possibile distinguerle dal
#  tag). Tre controlli in ordine, il primo disponibile decide; ADR (E3, 22-23/09/2026):
#  1. un fatto dei futuro (filed dopo `rif`) esiste: rapporto valore attuale / valore futuro, sotto il 20% implausibile;
#  2. altrimenti, un fatto dei:EntityPublicFloat utile vicino a `rif`: prezzo implicito = flottante $ / azioni,
#     fuori da $0,01-$100.000/azione implausibile;
#  3. altrimenti, soglia assoluta di 100.000 azioni: sotto soglia scartato, sopra soglia accettato ma "non
#     verificato" (nessuna doppia conferma trovata, tracciabile con `stato_plausibilita`).
SOGLIA_RAPPORTO_DEI_FUTURO = 0.20
SOGLIA_AZIONI_MINIMA = 100_000
#  Tetto stretto il 23/09/2026, dopo aver trovato un caso reale (Associated Capital Group) che un tetto a
#  100.000 $/azione lasciava passare: sui peer con flottante disponibile, il massimo fra quelli senza motivo di
#  sospetto è $801,62 e il minimo fra i due casi noti sbagliati (Associated Capital Group, Houlihan Lokey come
#  peer) è $4.155,69 — un margine pulito. Non risolve tutto: il valore di Houlihan Lokey alla sua data di caso
#  E3 ($447) e quelli di Aziyo ($44) e Nuvalent ($76) restano sotto qualunque tetto sensato, perché il prezzo
#  implicito che ne risulta non è assurdo, è solo sbagliato — nessun tetto sul prezzo può prenderli senza
#  buttare via dati veri.
PREZZO_IMPLICITO_MIN, PREZZO_IMPLICITO_MAX = 0.01, 1_000


def _d(s):
    return date.fromisoformat(str(s)[:10])


def fatti(cf, tassonomia, tag, unita, rif):
    """Fatti depositati prima di `rif` (data ISO), senza doppioni: per (inizio, fine) vale il deposito più recente."""
    righe = (((cf or {}).get("facts") or {}).get(tassonomia) or {}).get(tag, {}).get("units", {}).get(unita, [])
    per = {}
    for f in righe:
        if not f.get("filed") or f["filed"] >= rif or f.get("val") is None or not f.get("end"):
            continue
        k = (f.get("start"), f["end"])
        if k not in per or f["filed"] > per[k]["filed"]:
            per[k] = f
    return list(per.values())


def _durata(f):
    return (_d(f["end"]) - _d(f["start"])).days + 1


def dodici_mesi(cf, tags, rif):
    """(valore, fine, metodo) o (None, None, motivo)."""
    for tag in tags:
        fs = [f for f in fatti(cf, "us-gaap", tag, "USD", rif) if f.get("start")]
        if fs:
            break
    else:
        return None, None, "tag assenti"
    annuali = [f for f in fs if 340 <= _durata(f) <= 380]
    if annuali:
        a = max(annuali, key=lambda f: f["end"])
        inizio_nuovo = _d(a["end"]) + timedelta(days=1)
        ytd = [f for f in fs if _durata(f) < 340 and f["end"] > a["end"]
               and abs((_d(f["start"]) - inizio_nuovo).days) <= 5]
        valore, fine, metodo = float(a["val"]), a["end"], "anno fiscale"
        if ytd:
            y = max(ytd, key=lambda f: f["end"])
            prec = [f for f in fs if abs((_d(f["start"]) - _d(a["start"])).days) <= 5
                    and abs((_d(f["end"]) - (_d(y["end"]) - timedelta(days=365))).days) <= 10
                    and abs(_durata(f) - _durata(y)) <= 10]
            if prec:
                p = max(prec, key=lambda f: f["filed"])
                valore, fine, metodo = float(a["val"]) + float(y["val"]) - float(p["val"]), y["end"], "anno + progressivo"
    else:
        trim = sorted((f for f in fs if 80 <= _durata(f) <= 100), key=lambda f: f["end"])
        catena = []
        for f in reversed(trim):
            if not catena or abs((_d(catena[-1]["start"]) - timedelta(days=1) - _d(f["end"])).days) <= 5:
                catena.append(f)
            if len(catena) == 4:
                break
        if len(catena) < 4:
            return None, None, "né anno fiscale né quattro trimestri consecutivi"
        valore, fine, metodo = sum(float(f["val"]) for f in catena), catena[0]["end"], "quattro trimestri"
    if (_d(rif) - _d(fine)).days > ETA_MAX:
        return None, None, "dati vecchi ({})".format(fine)
    return valore, fine, metodo


def istantaneo(cf, tags, rif, unita="USD", tassonomia="us-gaap"):
    for tag in tags:
        fs = [f for f in fatti(cf, tassonomia, tag, unita, rif) if not f.get("start")]
        if fs:
            f = max(fs, key=lambda f: (f["end"], f["filed"]))
            if (_d(rif) - _d(f["end"])).days > ETA_MAX:
                return None, None
            return float(f["val"]), f["end"]
    return None, None


# ---------------------------------------------------------------------- filtri --
def f1_flusso_cassa(cf, rif):
    v, fine, m = dodici_mesi(cf, DURATION["ocf"], rif)
    if v is None:
        return None, m
    return v > 0, "{:,.0f} al {} ({})".format(v, fine, m)


def f2_leva(cf, rif):
    lt, _ = istantaneo(cf, INSTANT["lt_debt"], rif)
    st, _ = istantaneo(cf, INSTANT["st_debt"], rif)
    cash, fine_c = istantaneo(cf, INSTANT["cash"], rif)
    att, fine_a = istantaneo(cf, INSTANT["assets"], rif)
    eq, fine_e = istantaneo(cf, INSTANT["equity"], rif)
    letto = (att is not None and fine_a == fine_c) or (eq is not None and fine_e == fine_c)
    nd = net_debt(lt, st, cash, balance_sheet_read=letto)
    if nd.value is None:
        return None, "debito netto: " + nd.reason
    if nd.value <= 0:
        return True, "cassa netta {:,.0f}".format(-nd.value)
    ebit, _f1, m1 = dodici_mesi(cf, DURATION["ebit"], rif)
    da, _f2, m2 = dodici_mesi(cf, DURATION["da"], rif)
    eb = ebitda(ebit, da)
    if eb.value is None:
        return None, "EBITDA: {} / {}".format(m1 if ebit is None else "ok", m2 if da is None else "ok")
    if eb.value <= 0:
        return False, "EBITDA {:,.0f} ≤ 0 con debito netto {:,.0f}".format(eb.value, nd.value)
    leva = nd.value / eb.value
    return leva < SOGLIA_LEVA, "debito netto / EBITDA {:.2f}".format(leva)


def _dei_futuro(cf, rif):
    """Primo fatto dei:EntityCommonStockSharesOutstanding depositato a partire da `rif` (incluso). None se assente."""
    tass, tag = DEI_AZIONI
    righe = (((cf or {}).get("facts") or {}).get(tass) or {}).get(tag, {}).get("units", {}).get("shares", [])
    dopo = [f for f in righe if f.get("filed") and f["filed"] >= rif and f.get("val") is not None and f.get("end")]
    return min(dopo, key=lambda f: f["filed"]) if dopo else None


def _flottante_vicino(cf, rif):
    """Fatto dei:EntityPublicFloat (val > 0) più vicino a `rif` per data di fine. None se assente."""
    righe = (((cf or {}).get("facts") or {}).get("dei") or {}).get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
    utili = [f for f in righe if f.get("val") and f.get("end")]
    if not utili:
        return None
    return min(utili, key=lambda f: abs((_d(f["end"]) - _d(rif)).days))


def stato_plausibilita(cf, rif, valore):
    """("ok"|"non_verificato"|"scartato", motivo) per un valore ottenuto dal fallback us-gaap. I tre controlli
    dell'ADR, il primo disponibile decide."""
    futuro = _dei_futuro(cf, rif)
    if futuro is not None:
        rapporto = valore / float(futuro["val"]) if futuro["val"] else 0.0
        esito = "scartato" if rapporto < SOGLIA_RAPPORTO_DEI_FUTURO else "ok"
        return esito, "rapporto {:.1%} vs dei futuro {} (depositato {})".format(rapporto, futuro["end"], futuro["filed"])
    fl = _flottante_vicino(cf, rif)
    if fl is not None:
        prezzo = float(fl["val"]) / valore if valore else float("inf")
        esito = "ok" if PREZZO_IMPLICITO_MIN <= prezzo <= PREZZO_IMPLICITO_MAX else "scartato"
        return esito, "prezzo implicito ${:,.4f} da flottante {} (${:,.0f})".format(prezzo, fl["end"], fl["val"])
    if valore < SOGLIA_AZIONI_MINIMA:
        return "scartato", "sotto soglia assoluta di {:,.0f}".format(SOGLIA_AZIONI_MINIMA)
    return "non_verificato", "sopra soglia assoluta, nessun dei futuro né flottante utilizzabile"


def azioni_per_deposito(cf, rif):
    """{(filed, accn): azioni} sommando le classi dello stesso deposito; prima fonte con dati.

    Se la fonte è il fallback us-gaap:CommonStockSharesOutstanding (dei:EntityCommonStockSharesOutstanding non
    disponibile a `rif`), ogni valore passa da `stato_plausibilita`: gli «scartati» sono tolti, come se il dato
    non ci fosse — nessuna sostituzione silenziosa."""
    for tass, tag in AZIONI:
        righe = (((cf or {}).get("facts") or {}).get(tass) or {}).get(tag, {}).get("units", {}).get("shares", [])
        per = {}
        for f in righe:
            if f.get("filed") and f["filed"] < rif and f.get("val") is not None:
                k = (f["filed"], f.get("accn", ""))
                d = per.setdefault(k, {})
                d[f["end"]] = d.get(f["end"], 0.0) + float(f["val"])
        if per:
            #  un deposito può riportare più date: vale la più recente, sommando le classi alla stessa data
            valori = {k: sum(v for e, v in d.items() if e == max(d)) for k, d in per.items()}
            if (tass, tag) == DEI_AZIONI:
                return valori, tag
            valori = {k: v for k, v in valori.items() if stato_plausibilita(cf, rif, v)[0] != "scartato"}
            if valori:
                return valori, tag
            #  tutti i valori del fallback erano implausibili: si prova comunque il prossimo tag, se c'è
    return {}, None


def f3_azioni(cf, rif, fattore_split=lambda a, b: 1.0):
    per, tag = azioni_per_deposito(cf, rif)
    if not per:
        return None, "azioni assenti"
    ult = max(per)
    if (_d(rif) - _d(ult[0])).days > ETA_MAX:
        return None, "azioni vecchie ({})".format(ult[0])
    obiettivo = _d(ult[0]) - timedelta(days=365)
    prima = [k for k in per if 270 <= (_d(ult[0]) - _d(k[0])).days <= 460]
    if not prima:
        return None, "nessun deposito 9-15 mesi prima"
    p = min(prima, key=lambda k: abs((_d(k[0]) - obiettivo).days))
    if per[p] <= 0:
        return None, "azioni non positive"
    fattore = fattore_split(p[0], ult[0])
    crescita = per[ult] / (per[p] * fattore) - 1.0
    nota = " (corretta per split x{:g})".format(fattore) if fattore != 1.0 else ""
    return crescita <= SOGLIA_AZIONI, "{} {:+.1%} da {} a {}{}".format(tag, crescita, p[0], ult[0], nota)
