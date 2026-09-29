"""Russell 2000, uscite verso il basso — rendimenti extra, statistica e verdetto (fermata del verdetto).

Tutto quello che c'è qui è scritto nella pre-registrazione del 16 settembre prima di guardare qualunque rendimento. I
paragrafi citati sono di quel documento; le decisioni che li precisano stanno in ADR-043 (peer) e ADR-045 (placebo).

**Rendimento extra** (§7) = rendimento del titolo sulla chiusura rettificata − media dei rendimenti dei peer **sulle
stesse date** (§5). Sulla chiusura rettificata per frazionamenti e dividendi, `adjusted_close` di EODHD.

**Finestre incomplete e delistati**, alla lettera:
- una finestra che finisce dopo l'ultima seduta del calendario (2026-08-28) esclude il caso da quella cella, e si
  conta (§7);
- un titolo senza prezzo all'ingresso non entra: il caso esce dalla cella, il peer esce dalla media; servono almeno 3
  peer (§5);
- un titolo — caso o peer — **delistato dentro la finestra** usa l'ultimo prezzo disponibile, oppure il prezzo in
  contanti dell'offerta **se il documento dell'offerta è già in cache** (§5): nessuno scaricamento nuovo. Il prezzo
  dell'offerta è un prezzo grezzo, quindi si applica come ultimo passo sopra il rendimento rettificato fino all'ultima
  barra: rettificata dell'ultima barra × offerta / chiusura dell'ultima barra;
- una barra mancante all'uscita di un titolo ancora quotato (un buco dei prezzi puliti) vale l'ultima chiusura entro
  5 sedute, come per gli altri prezzi di `analisi.py`; oltre, il titolo esce da quella cella e si conta.

**Statistica** (§8): per cella casi, media, mediana, quota positivi; medie per anno; t sulle medie annuali = media delle
medie / (deviazione standard delle medie / √anni), gradi di libertà anni − 1; tutto anche per 2015-2019 e 2020-2025.

**Verdetto** (§1), nell'ordine fissato: REGGE se valgono tutti e cinque i criteri; altrimenti INCONCLUSIVO se la
mediana e la media delle medie annuali sono positive e il t per anno è fra 1 e 2, oppure il criterio 1 non è
raggiunto; altrimenti NON REGGE. «Media» nei criteri 4 e 5 = media delle medie annuali, come il §1 precisa per il 5.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", HERE):
    sys.path.insert(0, str(p))

STALE = 5                           # sedute di tolleranza per una barra mancante, come in analisi.py
MIN_PEER = 3                        # §5
ORIZZONTI = (63, 126, 252)          # §7
SOTTOPERIODI = (("2015-2019", 2015, 2019), ("2020-2025", 2020, 2025))
SOGLIA_T = 2.0                      # §1, criterio 3
SOGLIA_T_BASSA = 1.0                # §1, INCONCLUSIVO
MIN_CASI, MIN_ANNI = 100, 9         # §1, criterio 1
FORME_OFFERTA = ("DEFM14A", "DEFM14C", "SC TO-T")
GIORNI_OFFERTA_PRIMA, GIORNI_OFFERTA_DOPO = 180, 60


def _c(x) -> bool:
    return x is not None and x == x


def ultimo_prima(xs, s: int, stale: int = STALE):
    """L'ultimo valore presente fra le sedute s − stale e s, o None."""
    for i in range(s, max(-1, s - stale - 1), -1):
        if 0 <= i < len(xs) and _c(xs[i]):
            return xs[i]
    return None


def ultima_barra(xs) -> int | None:
    """Indice dell'ultima seduta con un valore, o None."""
    for i in range(len(xs) - 1, -1, -1):
        if _c(xs[i]):
            return i
    return None


# ------------------------------------------------------------------------------------------------ rendimento ---
def rendimento(adj, close, s: int, e: int, last: int, offerta: float | None = None) -> tuple[float | None, str]:
    """(rendimento sulla chiusura rettificata da s a e, esito). `last` = ultima seduta del calendario.

    Esiti: "completo", "delistato: ultimo prezzo", "delistato: prezzo dell'offerta", e i motivi di esclusione
    "finestra oltre i dati", "senza prezzo all'ingresso", "buco all'uscita"."""
    if e > last:
        return None, "finestra oltre i dati"
    p0 = ultimo_prima(adj, s)
    if p0 is None or p0 <= 0:
        return None, "senza prezzo all'ingresso"
    fine = ultima_barra(adj)
    if fine is None or fine < s:
        return None, "senza prezzo all'ingresso"
    if fine >= e:
        p1 = ultimo_prima(adj, e)
        if p1 is None:
            return None, "buco all'uscita"
        return p1 / p0 - 1.0, "completo"
    #  Delistato dentro la finestra: ultimo prezzo, o l'offerta in contanti applicata sopra l'ultima barra.
    p1 = adj[fine]
    if offerta and _c(close[fine]) and close[fine] > 0:
        return (p1 * offerta / close[fine]) / p0 - 1.0, "delistato: prezzo dell'offerta"
    return p1 / p0 - 1.0, "delistato: ultimo prezzo"


def rendimento_extra(caso: dict, peer: list[dict], s: int, e: int, last: int, serie, offerta_di=None):
    """(extra, esito del caso, peer usati). `serie(codice)` dà la tupla di serie_eodhd; `offerta_di(titolo, e)` il
    prezzo in contanti dell'offerta o None. Extra None se il caso non entra o se i peer con prezzo sono meno di 3."""
    def uno(t):
        ser = serie(t.get("codice"))
        if ser is None:
            return None, "senza prezzo all'ingresso"
        close, adj = ser[0], ser[1]
        fine = ultima_barra(adj)
        off = offerta_di(t, fine) if (offerta_di and fine is not None and fine < e) else None
        return rendimento(adj, close, s, e, last, off)

    r_caso, esito = uno(caso)
    if r_caso is None:
        return None, esito, 0
    r_peer = [r for r, _ in (uno(p) for p in peer) if r is not None]
    if len(r_peer) < MIN_PEER:
        return None, "meno di {} peer con prezzo".format(MIN_PEER), len(r_peer)
    return r_caso - sum(r_peer) / len(r_peer), esito, len(r_peer)


# ----------------------------------------------------------------------------------------- cambi di ticker ---
#  Aggiunto il 22-09-2026, DOPO il verdetto Russell e senza toccarlo (`2026-09-22_addendum_verdetto.md`): il referto
#  di quel terreno è stato calcolato senza questa parte e non si rifà. Serve ai backtest futuri.
#
#  Quando una società cambia ticker, EODHD chiude il codice vecchio e ne apre uno nuovo sotto lo stesso CIK. Senza
#  seguirlo, `rendimento` vede la fine della serie e tratta il titolo come delistato. Si segue un codice nuovo solo se:
#  - riprende entro STALE sedute dall'ultima barra del vecchio (una riquotazione mesi dopo, come le azioni nuove dopo
#    un fallimento, è un altro titolo);
#  - dove le due serie si sovrappongono nelle STALE sedute fino all'ultima barra del vecchio, le chiusure stanno in un
#    rapporto costante entro STESSA_SERIE, o MEZZO_CENTESIMO per le quotazioni arrotondate al centesimo. Con due o più
#    sedute in comune il rapporto è la loro mediana (per esempio 1,5, la conversione delle azioni in una fusione); con
#    una sola deve essere 1. I rinomi di EODHD ricopiano la storia; un'altra classe dello stesso emittente, o una
#    quotazione ferma (un codice fermo a un prezzo fisso contro il gemello fuori borsa che scambia), no;
#  - è l'unico candidato così: con due o più, non si segue niente.
#  Provato sui dati veri dei nove cambi di ticker dell'addendum (ne segue otto) e di un caso a due classi; i test in
#  `test_rendimenti.py` riproducono le stesse forme con dati sintetici (ticker AAA/BBB/CCC, prezzi inventati).
STESSA_SERIE = 0.01
MEZZO_CENTESIMO = 0.005


def aggancio(vecchia, nuova, stale: int = STALE) -> int | None:
    """La seduta in cui la serie `nuova` prende il posto di `vecchia`, o None se non è un successore.

    `vecchia`, `nuova`: (close, adj, ...) di serie_eodhd. Per i test sopra, `close` è la chiusura rettificata per i
    frazionamenti, che per un rinomo coincide seduta per seduta."""
    fine = ultima_barra(vecchia[1])
    if fine is None:
        return None
    fine_nuova = ultima_barra(nuova[1])
    if fine_nuova is None or fine_nuova <= fine:
        return None
    comuni = [(vecchia[0][i], nuova[0][i]) for i in range(max(0, fine - stale), fine + 1)
              if _c(vecchia[0][i]) and _c(nuova[0][i]) and vecchia[0][i] > 0 and nuova[0][i] > 0]
    rapporto = statistics.median(b / a for a, b in comuni) if len(comuni) >= 2 else 1.0
    if any(abs(b - rapporto * a) > max(STESSA_SERIE * b, MEZZO_CENTESIMO) for a, b in comuni):
        return None
    for i in range(fine, min(len(nuova[1]), fine + stale + 1)):
        if _c(nuova[1][i]) and nuova[1][i] > 0:
            return i
    return None


def segui(vecchia, candidati) -> tuple[tuple, str | None]:
    """(serie seguita, codice seguito o None). `candidati`: {codice: serie} degli altri codici dello stesso CIK.

    La serie seguita è quella vecchia fino alla sua ultima barra; da lì la `adj` prosegue con i rendimenti del codice
    nuovo, incatenata all'ultima rettificata del vecchio, mentre `close` e `vol` sono quelli veri del codice nuovo (il
    prezzo dell'offerta di `rendimento` si confronta con una chiusura vera). Si segue una catena di rinomi, un anello
    alla volta, finché c'è un successore unico."""
    seguiti = []
    while True:
        buoni = [(k, s, j) for k, s in candidati.items() if k not in seguiti
                 for j in [aggancio(vecchia, s)] if j is not None]
        if len(buoni) != 1:
            return vecchia, ("→".join(seguiti) or None)
        codice, nuova, j = buoni[0]
        fine = ultima_barra(vecchia[1])
        base = vecchia[1][fine] / nuova[1][j]
        close, adj, vol = vecchia[0][:], vecchia[1][:], vecchia[2][:]
        for i in range(fine + 1, len(adj)):
            close[i], vol[i] = nuova[0][i], nuova[2][i]
            adj[i] = nuova[1][i] * base if _c(nuova[1][i]) else nuova[1][i]
        vecchia = (close, adj, vol) + tuple(vecchia[3:])
        seguiti.append(codice)


# -------------------------------------------------------------------------------------------------- offerta ---
def offerta_in_cache(cik: str, ultima_data: str) -> float | None:
    """Il prezzo in contanti dell'offerta, dai documenti **già in cache** intorno all'ultima barra, o None.

    Candidati, in quest'ordine: l'8-K del completamento (voci 2.01, 5.01, 8.01), il DEFM14A/C, l'SC TO-T, fra 180
    giorni prima e 60 dopo l'ultima barra. Vale solo un esito CONTANTI di `survival.leggi_deal`: un'offerta mista o
    ambigua non dà un prezzo."""
    if not cik:
        return None
    import survival as SV
    _d, dep = SV.submissions(cik)
    if not dep:
        return None
    fine = dt.date.fromisoformat(ultima_data)
    lo = (fine - dt.timedelta(days=GIORNI_OFFERTA_PRIMA)).isoformat()
    hi = (fine + dt.timedelta(days=GIORNI_OFFERTA_DOPO)).isoformat()
    finestra = [x for x in dep if lo <= x[0] <= hi]
    candidati = []
    otto = SV.scegli_8k(finestra, ("2.01", "5.01", "8.01"))
    if otto:
        candidati.append(otto)
    for forma in FORME_OFFERTA:
        candidati += [x for x in reversed(finestra) if x[1] == forma][:1]
    for _data, _forma, _voci, acc, doc in candidati:
        if not doc:
            continue
        url = SV.url_documento(cik, acc, doc)
        if not SV.in_cache(url):
            continue                                      # §5: solo se il documento è già in cache
        esito, prezzo, _citazione = SV.leggi_deal(SV.testo(SV.leggi_cache(url)))
        if esito == "CONTANTI" and prezzo:
            return prezzo
    return None


# ----------------------------------------------------------------------------------------------- statistica ---
def statistiche(per_anno: dict[int, list[float]]) -> dict:
    """Le statistiche di una cella (§8). `per_anno`: anno -> rendimenti extra dei casi di quell'anno."""
    per_anno = {a: v for a, v in per_anno.items() if v}
    tutti = [x for v in per_anno.values() for x in v]
    medie = {a: statistics.fmean(v) for a, v in sorted(per_anno.items())}
    fuori = {"casi": len(tutti), "anni": len(medie),
             "media": statistics.fmean(tutti) if tutti else None,
             "mediana": statistics.median(tutti) if tutti else None,
             "quota_positivi": sum(1 for x in tutti if x > 0) / len(tutti) if tutti else None,
             "medie_per_anno": medie, "casi_per_anno": {a: len(v) for a, v in sorted(per_anno.items())},
             "media_delle_medie": statistics.fmean(medie.values()) if medie else None, "t": None, "gradi": None}
    if len(medie) >= 2:
        ds = statistics.stdev(medie.values())
        if ds > 0:
            fuori["t"] = fuori["media_delle_medie"] / (ds / math.sqrt(len(medie)))
            fuori["gradi"] = len(medie) - 1
    fuori["sottoperiodi"] = {}
    for nome, da, a in SOTTOPERIODI:
        parte = {y: v for y, v in per_anno.items() if da <= y <= a}
        if parte:
            sub = statistiche_senza_sottoperiodi(parte)
            fuori["sottoperiodi"][nome] = sub
    return fuori


def statistiche_senza_sottoperiodi(per_anno):
    tutti = [x for v in per_anno.values() for x in v]
    medie = [statistics.fmean(v) for v in per_anno.values() if v]
    t = None
    if len(medie) >= 2 and statistics.stdev(medie) > 0:
        t = statistics.fmean(medie) / (statistics.stdev(medie) / math.sqrt(len(medie)))
    return {"casi": len(tutti), "anni": len(medie), "media": statistics.fmean(tutti) if tutti else None,
            "mediana": statistics.median(tutti) if tutti else None,
            "media_delle_medie": statistics.fmean(medie) if medie else None, "t": t}


# -------------------------------------------------------------------------------------------------- verdetto ---
def verdetto(cella: dict, placebo: dict) -> tuple[str, dict]:
    """(esito, criteri) secondo il §1, nell'ordine fissato. Un criterio che non si può calcolare è falso."""
    mom, t = cella["media_delle_medie"], cella["t"]
    sub = cella.get("sottoperiodi", {})
    criteri = {
        "1. almeno 100 casi e almeno 9 anni": cella["casi"] >= MIN_CASI and cella["anni"] >= MIN_ANNI,
        "2. mediana > 0": cella["mediana"] is not None and cella["mediana"] > 0,
        "3. media delle medie annuali > 0 con t ≥ 2": mom is not None and mom > 0 and t is not None and t >= SOGLIA_T,
        "4. media > 0 in 2015-2019 e in 2020-2025": all(
            (sub.get(n) or {}).get("media_delle_medie") is not None and sub[n]["media_delle_medie"] > 0
            for n, _a, _b in SOTTOPERIODI),
        "5. placebo con |t| < 2 e media più bassa": (
            placebo["t"] is not None and abs(placebo["t"]) < SOGLIA_T and placebo["media_delle_medie"] is not None
            and mom is not None and placebo["media_delle_medie"] < mom),
    }
    if all(criteri.values()):
        return "REGGE", criteri
    c1, c2 = criteri["1. almeno 100 casi e almeno 9 anni"], criteri["2. mediana > 0"]
    if c2 and mom is not None and mom > 0 and ((t is not None and SOGLIA_T_BASSA <= t < SOGLIA_T) or not c1):
        return "INCONCLUSIVO", criteri
    return "NON REGGE", criteri


# ------------------------------------------------------------------------------------ dicembre, descrittivo ---
def secondo_venerdi_di_dicembre(anno: int) -> str:
    d = dt.date(anno, 12, 1)
    primo = d + dt.timedelta(days=(4 - d.weekday()) % 7)
    return (primo + dt.timedelta(days=7)).isoformat()


def ultima_seduta_entro(ids: list[str], giorno: str) -> int | None:
    import bisect
    i = bisect.bisect_right(ids, giorno) - 1
    return i if i >= 0 else None


def prima_seduta_da(ids: list[str], giorno: str) -> int | None:
    import bisect
    i = bisect.bisect_left(ids, giorno)
    return i if i < len(ids) else None
