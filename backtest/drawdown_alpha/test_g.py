"""Test G (scadenza delle put spread), fermata 2: simulazione, misure e i due verdetti come pre-registrati
(`2026-10-04_preregistrazione_test_g.md`, ADR-072..074; composito corretto da ADR-071). Nessun parametro scelto qui.

Due versioni di budget (A: premio 6% × mesi/12, massimo 3%, tetto 6% sui 360 giorni precedenti; B: 3% fisso, nessun
tetto) × 4 regole di ingresso × 4 scadenze = 32 combinazioni; più le sensibilità descrittive (inclinazione 0 e +10,
valore intrinseco, q = 0) su tutte le 32: 160 serie. Prezzi, strike, scadenza, buchi e parte coperta vengono da
`test_g_dati.py`; composito e Faber da `test_f.py`; lista A dei ribassi da `eventi_f.py`; definizione di ribasso da
`episodi.py`. Dati solo da `market_data.api`. Un dato che manca ferma il programma (`DatoMancante`), non si sostituisce.

    python backtest/drawdown_alpha/test_g.py            # stampa il materiale del referto (markdown), controlli compresi
    python backtest/drawdown_alpha/test_g.py --confronto-composito <file.py>
        # solo il confronto descrittivo: regole 2 e 3 con il composito calcolato da un'altra copia di test_f.py
        # (per esempio quella prima di ADR-071, estratta da git fuori dal repo). L'uscita predefinita non cambia.
"""
from __future__ import annotations

import bisect
import datetime as dt
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import eventi_f as E  # noqa: E402
import test_g_dati as G  # noqa: E402
from episodi import episodi_drawdown  # noqa: E402  (definizione comune del filone)

VERSIONI = ("A", "B")
REGOLE = (1, 2, 3, 4)
NOME_REGOLA = {1: "1 sempre accesa", 2: "2 composito ≥ 3", 3: "3 composito ≥ 3 e VIX sotto la mediana", 4: "4 Faber"}
CELLA_VERDETTO = {"A": (3, 12), "B": (3, 3)}          # (regola, mesi)
CAPITALE = 100.0
TETTO_BPS = 600                                       # versione A: 6% sui 360 giorni precedenti, nuova operazione compresa
GIORNI_TETTO = 360
LETTURE = (dt.date(1989, 12, 31), dt.date(2025, 11, 30))   # fini mese lette: ingresso alla prima seduta del mese dopo
SOGLIA_COMPOSITO = 3
RIDUZIONE_REGGE = 1.0 / 3.0
RIDUZIONE_NON_REGGE = 1.0 / 5.0
COSTO_REGGE = 1.5                                     # punti di rendimento annuo
COSTO_NON_REGGE = 3.0
#  (nome, inclinazione, q, valutazione dello spread aperto). La prima è la scelta principale; le altre cambiano una
#  cosa alla volta e sono descrittive (pre-registrazione, «Quante combinazioni si guardano»).
VARIANTI = (("principale", G.INCLINAZIONE, G.DIVIDENDO, "modello"),
            ("inclinazione 0", 0.0, G.DIVIDENDO, "modello"),
            ("inclinazione +10", 10.0, G.DIVIDENDO, "modello"),
            ("valore intrinseco", G.INCLINAZIONE, G.DIVIDENDO, "intrinseco"),
            ("q = 0", G.INCLINAZIONE, 0.0, "modello"))


# ------------------------------------------------------------------ il mercato visto dalla simulazione

@dataclass
class Mercato:
    """Quello che la simulazione legge: sedute del periodo, sedute di tutto l'archivio (per la data di scadenza),
    chiusura, VIX (punti) e tasso continuo (frazione) di ogni seduta del periodo, buchi già risolti."""
    sedute: list
    sedute_archivio: list
    chiusura: dict
    vix: dict
    tasso: dict


def serie_sulle_sedute(serie: G.Serie, chiusura: dict) -> G.Serie:
    """La serie con le sole osservazioni in giorni di seduta di GSPC (pre-registrazione, «Regola dei buchi»: le
    osservazioni in giorni che non sono sedute non si usano)."""
    return G.Serie(serie.nome, [(d, v) for d, v in serie.righe if d in chiusura])


def mercato_reale(D: G.Dati) -> Mercato:
    sedute = D.sedute_periodo()
    vix = serie_sulle_sedute(D.vix, D.chiusura)
    tb = serie_sulle_sedute(D.dtb3, D.chiusura)
    return Mercato(sedute, D.sedute, D.chiusura,
                   {d: vix.ultimo_noto(d)[1] for d in sedute},                       # DatoMancante oltre 7 giorni
                   {d: G.tasso_continuo(tb.ultimo_noto(d)[1]) for d in sedute})


def scadenza_operazione(ingresso: dt.date, mesi: int, sedute_archivio: list) -> dt.date:
    """`G.scadenza` (seduta precedente se la data non è una seduta); oltre l'ultima seduta dell'archivio la scadenza è
    la data di calendario, senza spostamento (pre-registrazione, «Valutazione giornaliera»)."""
    bersaglio = E.mesi_prima(ingresso, -mesi)
    if bersaglio > sedute_archivio[-1]:
        return bersaglio
    return G.scadenza(ingresso, mesi, sedute_archivio)


# ------------------------------------------------------------------ segnali mensili e calendario degli ingressi

def vix_sotto_mediana(vix: G.Serie, fm: dt.date, sedute_archivio: list) -> bool | None:
    """Ultimo VIX noto alla fine del mese `fm` strettamente sotto la mediana delle chiusure del VIX nei 12 mesi di
    calendario che finiscono in `fm` (fm compresa, fm − 1 anno escluso). None se la finestra non è intera (il VIX
    comincia dopo la prima seduta della finestra). Usa solo dati con data <= fm."""
    limite = E.un_anno_prima(fm)
    i = bisect.bisect_right(sedute_archivio, limite)
    if i >= len(sedute_archivio) or vix.date[0] > sedute_archivio[i]:
        return None
    finestra = [v for d, v in vix.righe if limite < d <= fm]
    if not finestra:
        return None
    _d, ultimo = vix.ultimo_noto(fm)
    return ultimo < statistics.median(finestra)


def letture_mensili(mesi_f: list, vix: G.Serie, sedute_archivio: list) -> dict:
    """{regola: {fine mese: True / False / None}} per le regole 2, 3 e 4. None = lettura non disponibile: la regola
    non entra (fail-closed), non si usa il mese prima. `mesi_f` è l'uscita di `test_f.calcola_mesi`."""
    per_fm = {m.fm: m for m in mesi_f}
    out = {2: {}, 3: {}, 4: {}}
    fm = E.fine_mese(LETTURE[0])
    while fm <= LETTURE[1]:
        m = per_fm.get(fm)
        if m is None:
            raise G.DatoMancante("fine mese {} non calcolata da test_f.calcola_mesi".format(fm))
        c = m.composito5
        acceso = None if c is None else c >= SOGLIA_COMPOSITO
        out[2][fm] = acceso
        if acceso is None or acceso is False:
            out[3][fm] = acceso
        else:
            sotto = vix_sotto_mediana(vix, fm, sedute_archivio)
            out[3][fm] = None if sotto is None else sotto
        out[4][fm] = m.faber
        fm = E.fine_mese(fm + dt.timedelta(days=1))
    return out


def calendario_ingressi(letture: dict, sedute: list) -> set:
    """Le sedute in cui il segnale permette l'ingresso: la prima seduta del mese dopo ogni fine mese con lettura accesa.
    Una lettura None o spenta non dà ingresso."""
    out = set()
    for fm, acceso in letture.items():
        if acceso is not True:
            continue
        i = bisect.bisect_right(sedute, fm)
        dopo = fm + dt.timedelta(days=1)
        if i >= len(sedute) or (sedute[i].year, sedute[i].month) != (dopo.year, dopo.month):
            raise G.DatoMancante("nessuna seduta nel mese dopo la lettura del {}".format(fm))
        out.add(sedute[i])
    return out


# ------------------------------------------------------------------ simulazione

@dataclass
class Operazione:
    ingresso: dt.date
    scadenza: dt.date
    s0: float                     # chiusura del giorno di ingresso
    k1: float
    k2: float
    vix: float
    tasso: float
    prezzo: float                 # prezzo dello spread all'ingresso, punti indice
    premio_pct: float             # frazione del portafoglio
    portafoglio: float            # valore del portafoglio alla chiusura dell'ingresso (dopo un eventuale incasso)
    premio: float                 # denaro pagato = premio_pct × portafoglio
    n: float                      # numero di spread = premio / prezzo
    coperta: float                # parte coperta = premio_pct / (prezzo / s0)
    s_scadenza: float | None = None
    valore_scadenza: float | None = None    # punti indice per spread
    incasso: float | None = None            # denaro = n × valore_scadenza


@dataclass
class Esito:
    valori: list                                  # valore del portafoglio a ogni seduta
    spread: list                                  # valore dello spread aperto a ogni seduta (dopo le operazioni del giorno)
    operazioni: list = field(default_factory=list)
    bloccati: list = field(default_factory=list)  # sedute in cui il tetto ha impedito un ingresso


def tetto_permette(ingressi_passati: list, giorno: dt.date, premio_bps: int) -> bool:
    """Versione A: premi degli ingressi con data > giorno − 360 giorni più il premio nuovo; oltre il 6% non si entra,
    il 6% esatto è ammesso. `ingressi_passati` = [(data, punti base)]; conti in punti base interi."""
    limite = giorno - dt.timedelta(days=GIORNI_TETTO)
    return sum(b for d, b in ingressi_passati if d > limite) + premio_bps <= TETTO_BPS


def simula(M: Mercato, mesi: int, premio_pct: float, tetto: bool, ingressi: set | None,
           inclinazione: float = G.INCLINAZIONE, q: float = G.DIVIDENDO, valutazione: str = "modello",
           limite_coperta: float | None = None) -> Esito:
    """Portafoglio con protezione. `ingressi` = sedute in cui il segnale permette di entrare (None = ogni seduta, regola
    1). A ogni seduta, nell'ordine: incasso dello spread che scade oggi (reinvestito nell'indice a questa chiusura);
    ingresso, se non c'è uno spread aperto, il segnale lo permette e il tetto pure; valutazione.

    `limite_coperta` (predefinito None = nessun limite, come pre-registrato): se dato, numero di spread =
    min(premio / prezzo, limite × portafoglio / chiusura); il premio speso è quello effettivo (numero × prezzo, minore
    della percentuale piena quando il limite morde) e il resto resta nell'indice. Descrittivo, fuori dalle 160 serie;
    il tetto della versione A conta comunque la percentuale piena."""
    if valutazione not in ("modello", "intrinseco"):
        raise ValueError(valutazione)
    premio_bps = round(premio_pct * 10000)
    quote = CAPITALE / M.chiusura[M.sedute[0]]
    aperta: Operazione | None = None
    passati: list = []
    out = Esito([], [])
    for d in M.sedute:
        S = M.chiusura[d]
        if aperta is not None and d > aperta.scadenza:
            raise RuntimeError("spread aperto oltre la scadenza: {} > {}".format(d, aperta.scadenza))
        if aperta is not None and d == aperta.scadenza:
            aperta.s_scadenza = S
            aperta.valore_scadenza = G.put_spread(S, aperta.k1, aperta.k2, 0.0, 0.0, M.vix[d], inclinazione, q)
            aperta.incasso = aperta.n * aperta.valore_scadenza
            quote += aperta.incasso / S
            aperta = None
        if aperta is None and (ingressi is None or d in ingressi):
            if tetto and not tetto_permette(passati, d, premio_bps):
                out.bloccati.append(d)
            else:
                fine = scadenza_operazione(d, mesi, M.sedute_archivio)
                k1, k2 = G.strike(S)
                prezzo = G.put_spread(S, k1, k2, G.anni(d, fine), M.tasso[d], M.vix[d], inclinazione, q)
                if not prezzo > 0:
                    raise RuntimeError("prezzo dello spread non positivo il {}: {!r}".format(d, prezzo))
                portafoglio = quote * S
                premio = premio_pct * portafoglio
                if limite_coperta is None or premio / prezzo <= limite_coperta * portafoglio / S:
                    aperta = Operazione(d, fine, S, k1, k2, M.vix[d], M.tasso[d], prezzo, premio_pct, portafoglio, premio,
                                        premio / prezzo, G.parte_coperta(premio_pct, prezzo / S))
                else:
                    n = limite_coperta * portafoglio / S
                    premio = n * prezzo
                    aperta = Operazione(d, fine, S, k1, k2, M.vix[d], M.tasso[d], prezzo, premio / portafoglio, portafoglio,
                                        premio, n, limite_coperta)
                quote -= premio / S
                passati.append((d, premio_bps))
                out.operazioni.append(aperta)
        if aperta is None:
            v = 0.0
        elif valutazione == "intrinseco":
            v = aperta.n * G.put_spread(S, aperta.k1, aperta.k2, 0.0, 0.0, M.vix[d], inclinazione, q)
        else:
            v = aperta.n * G.put_spread(S, aperta.k1, aperta.k2, G.anni(d, aperta.scadenza), M.tasso[d], M.vix[d],
                                        inclinazione, q)
        out.spread.append(v)
        out.valori.append(quote * S + v)
    return out


def senza_protezione(M: Mercato) -> list:
    quote = CAPITALE / M.chiusura[M.sedute[0]]
    return [quote * M.chiusura[d] for d in M.sedute]


# ------------------------------------------------------------------ misure

def giorni_periodo(sedute: list) -> int:
    return (sedute[-1] - sedute[0]).days


def rendimento_annuo(valore_finale: float, giorni: int) -> float:
    return (valore_finale / CAPITALE) ** (365.0 / giorni) - 1.0


def ribasso_massimo(valori: list, da: int = 0, a: int | None = None) -> tuple[float, int, int]:
    """(profondità negativa, indice del massimo, indice del minimo) del ribasso più profondo fra gli indici da e a."""
    a = len(valori) - 1 if a is None else a
    peggio, i_p, i_f = 0.0, da, da
    picco, i_picco = valori[da], da
    for i in range(da, a + 1):
        v = valori[i]
        if v > picco:
            picco, i_picco = v, i
        elif v / picco - 1.0 < peggio:
            peggio, i_p, i_f = v / picco - 1.0, i_picco, i
    return peggio, i_p, i_f


def tre_ribassi(sedute: list, base: list) -> list:
    """I tre episodi più profondi del portafoglio senza protezione (`episodi.episodi_drawdown`, massimo mobile dal primo
    giorno): [(data del picco, data del fondo, profondità negativa)], dal più profondo."""
    ep = episodi_drawdown([(d.isoformat(), v) for d, v in zip(sedute, base)])
    if len(ep) < 3:
        raise G.DatoMancante("meno di tre ribassi nel periodo: {}".format(len(ep)))
    tre = sorted(ep, key=lambda e: -e.drawdown)[:3]
    return [(dt.date.fromisoformat(e.picco_data), dt.date.fromisoformat(e.fondo_data), -e.drawdown) for e in tre]


def profondita_sulle_date(valori: list, pos: dict, picco: dt.date, fondo: dt.date) -> float:
    return valori[pos[fondo]] / valori[pos[picco]] - 1.0


def riduzioni(tre: list, valori: list, pos: dict) -> tuple[float, list, list]:
    """(media semplice delle tre riduzioni, le tre riduzioni, le tre profondità con protezione sulle stesse date)."""
    prof = [profondita_sulle_date(valori, pos, p, f) for p, f, _ in tre]
    rid = [1.0 - con / senza for con, (_p, _f, senza) in zip(prof, tre)]
    return statistics.fmean(rid), rid, prof


def verdetto(riduzione: float, costo_punti: float) -> str:
    """REGGE se riduzione >= 1/3 e costo <= 1,5 punti; NON REGGE se riduzione < 1/5 o costo > 3 punti; altrimenti
    INCONCLUSIVO. Numeri non arrotondati."""
    if riduzione < RIDUZIONE_NON_REGGE or costo_punti > COSTO_NON_REGGE:
        return "NON REGGE"
    if riduzione >= RIDUZIONE_REGGE and costo_punti <= COSTO_REGGE:
        return "REGGE"
    return "INCONCLUSIVO"


def guadagno_put(es: Esito, pos: dict, picco: dt.date, fondo: dt.date) -> float:
    """Incassi a scadenza in (P, F] + valore dello spread aperto in F − valore in P − premi pagati in (P, F], diviso per
    il valore del portafoglio protetto in P."""
    incassi = sum(o.incasso for o in es.operazioni if o.incasso is not None and picco < o.scadenza <= fondo)
    premi = sum(o.premio for o in es.operazioni if picco < o.ingresso <= fondo)
    return (incassi + es.spread[pos[fondo]] - es.spread[pos[picco]] - premi) / es.valori[pos[picco]]


@dataclass
class Misure:
    rendimento: float
    ribasso_max: float
    riduzione: float
    riduzioni: list
    profondita: list
    costo_punti: float
    premio_annuo: float
    operazioni: int
    oltre_100: int
    coperta_max: float


def misura(M: Mercato, es: Esito, base: list, tre: list, pos: dict) -> Misure:
    giorni = giorni_periodo(M.sedute)
    r0, r1 = rendimento_annuo(base[-1], giorni), rendimento_annuo(es.valori[-1], giorni)
    media, rid, prof = riduzioni(tre, es.valori, pos)
    coperte = [o.coperta for o in es.operazioni]
    return Misure(r1, ribasso_massimo(es.valori)[0], media, rid, prof, 100.0 * (r0 - r1),
                  sum(o.premio_pct for o in es.operazioni) / (giorni / 365.0), len(es.operazioni),
                  sum(1 for c in coperte if c > 1.0), max(coperte) if coperte else 0.0)


def slittamenti(bloccati: list, sedute: list) -> list:
    """Gruppi di sedute consecutive bloccate dal tetto: [(prima, ultima, numero di sedute)]."""
    pos = {d: i for i, d in enumerate(sedute)}
    out = []
    for d in bloccati:
        if out and pos[d] == pos[out[-1][1]] + 1:
            out[-1] = (out[-1][0], d, out[-1][2] + 1)
        else:
            out.append((d, d, 1))
    return out


def scostamento_contabile(M: Mercato, es: Esito, base: list) -> float:
    """Controllo: portafoglio protetto − non protetto alla fine = somma di (−premio, + incasso), ciascuno cresciuto con
    l'indice dal suo giorno alla fine, più il valore dello spread ancora aperto. Restituisce la differenza fra i due lati."""
    s_fin = M.chiusura[M.sedute[-1]]
    atteso = es.spread[-1]
    for o in es.operazioni:
        atteso -= o.premio * s_fin / o.s0
        if o.incasso is not None:
            atteso += o.incasso * s_fin / o.s_scadenza
    return (es.valori[-1] - base[-1]) - atteso


# ------------------------------------------------------------------ stampa

def it(x: float, fmt: str) -> str:
    """Numero con la virgola decimale; uno zero arrotondato non porta il segno meno."""
    s = format(x, fmt)
    if s.startswith("-") and not any(c in "123456789" for c in s):
        s = ("+" if fmt.startswith("+") else "") + s[1:]
    return s.replace(".", ",")


def p(x: float, n: int = 1) -> str:
    return it(x, ".{}%".format(n))


def cella(v: str, r: int, m: int) -> bool:
    return CELLA_VERDETTO[v] == (r, m)


def esegui(M: Mercato, ingressi: dict, variante: tuple) -> dict:
    """Le 32 combinazioni di una variante: {(versione, regola, mesi): Esito}."""
    _nome, incl, q, val = variante
    return {(v, r, m): simula(M, m, G.PREMIO[v][m], v == "A", ingressi[r], incl, q, val)
            for v in VERSIONI for r in REGOLE for m in G.SCADENZE_MESI}


def tetti_teorici(D: G.Dati, tre: list) -> dict:
    """{(versione, mesi): [riduzione massima teorica per ciascuno dei tre ribassi]}: 20% × premio / costo dello spread
    alla seduta del massimo, diviso per la profondità (stessa formula di `test_g_dati.tetto_teorico`)."""
    out = {}
    for picco, _fondo, prof in tre:
        S = D.chiusura[picco]
        vix, tb = D.vix.ultimo_noto(picco)[1], D.dtb3.ultimo_noto(picco)[1]
        for m in G.SCADENZE_MESI:
            costo = G.put_spread(S, *G.strike(S), G.anni(picco, G.scadenza(picco, m, D.sedute)), G.tasso_continuo(tb), vix) / S
            for v in VERSIONI:
                out.setdefault((v, m), []).append(G.guadagno_massimo(G.PREMIO[v][m], costo) / -prof)
    return out


def stampa_dati(D: G.Dati, M: Mercato, letture: dict, mesi_f: list) -> None:
    print("## Dati e segnali\n")
    print("- GSPC.INDX: {} sedute nell'archivio, {} → {}; nel periodo {} sedute, {} → {} ({} giorni di calendario).".format(
        len(D.sedute), D.sedute[0], D.sedute[-1], len(M.sedute), M.sedute[0], M.sedute[-1], giorni_periodo(M.sedute)))
    print("- VIXCLS: {} osservazioni, {} → {}; DTB3: {} osservazioni, {} → {}.".format(
        len(D.vix.righe), D.vix.date[0], D.vix.date[-1], len(D.dtb3.righe), D.dtb3.date[0], D.dtb3.date[-1]))
    for nome, serie in (("VIXCLS", D.vix), ("DTB3", D.dtb3)):
        filtrata = serie_sulle_sedute(serie, D.chiusura)
        diversi = sum(1 for d in M.sedute if serie.ultimo_noto(d) != filtrata.ultimo_noto(d))
        eta = max((d - filtrata.ultimo_noto(d)[0]).days for d in M.sedute)
        print("- {}: sedute del periodo senza il dato del giorno {}; età massima del valore usato {} giorni; sedute in cui "
              "il valore cambierebbe usando anche le osservazioni in giorni senza seduta: {}.".format(
                  nome, sum(1 for d in M.sedute if d not in serie.per_data), eta, diversi))
    n = len(letture[2])
    per_fm = {m.fm: m for m in mesi_f}
    print("- Letture mensili ({} → {}): {}; senza composito {}; senza Faber {}; regola 3 senza la mediana del VIX "
          "(finestra non intera) {}.".format(LETTURE[0], LETTURE[1], n,
                                             sum(1 for fm in letture[2] if per_fm[fm].composito5 is None),
                                             sum(1 for x in letture[4].values() if x is None),
                                             sum(1 for fm in letture[3] if letture[2][fm] is True and letture[3][fm] is None)))
    for r in (2, 3, 4):
        accese = sorted(fm for fm, x in letture[r].items() if x is True)
        print("- regola {}: letture accese {} su {}{}.".format(
            NOME_REGOLA[r], len(accese), n, "" if not accese else " (prima {}, ultima {})".format(accese[0], accese[-1])))
    tutte = D.vix
    filtrata = serie_sulle_sedute(D.vix, D.chiusura)
    diverse = 0
    for fm in letture[3]:
        if letture[2][fm] is True:
            if vix_sotto_mediana(tutte, fm, D.sedute) != vix_sotto_mediana(filtrata, fm, D.sedute):
                diverse += 1
    print("- regola 3: letture con composito ≥ 3 in cui il confronto VIX/mediana cambierebbe contando anche le "
          "osservazioni del VIX in giorni senza seduta di GSPC: {}.".format(diverse))


def stampa_tre(tre: list, base: list, M: Mercato) -> None:
    giorni = giorni_periodo(M.sedute)
    print("\n## Portafoglio senza protezione e i suoi tre ribassi peggiori\n")
    print("Valore finale {} (da 100); rendimento annuo {}; ribasso massimo {}.\n".format(
        it(base[-1], ".4f"), p(rendimento_annuo(base[-1], giorni), 4), p(ribasso_massimo(base)[0], 2)))
    print("| # | massimo | fondo | profondità senza protezione |\n|---|---|---|---:|")
    for i, (a, b, d) in enumerate(tre, 1):
        print("| {} | {} ({}) | {} ({}) | {} |".format(i, a, it(M.chiusura[a], ".2f"), b, it(M.chiusura[b], ".2f"), p(d, 2)))


def stampa_verdetti(mis: dict) -> None:
    print("\n## Verdetti — due, uno per versione\n")
    print("| versione | cella | riduzione media dei tre ribassi peggiori (non arrotondata) | soglie | costo in punti di "
          "rendimento annuo (non arrotondato) | soglie | verdetto |\n|---|---|---:|---|---:|---|---|")
    for v in VERSIONI:
        r, m = CELLA_VERDETTO[v]
        x = mis[(v, r, m)]
        print("| {} | regola 3 × {} mesi | {} | REGGE ≥ {} ; NON REGGE < {} | {} | REGGE ≤ 1,5 ; NON REGGE > 3 | **{}** |".format(
            v, m, it(x.riduzione, ".10f"), it(RIDUZIONE_REGGE, ".10f"), it(RIDUZIONE_NON_REGGE, ".10f"),
            it(x.costo_punti, ".10f"), verdetto(x.riduzione, x.costo_punti)))


def stampa_griglia(v: str, mis: dict) -> None:
    print("\n## Versione {} — 4 regole × 4 scadenze\n".format(v))
    print("| regola | scadenza | rendimento annuo | ribasso massimo | riduzione media dei tre ribassi peggiori | costo "
          "(punti) | premio annuo speso | operazioni |\n|---|---|---:|---:|---:|---:|---:|---:|")
    for r in REGOLE:
        for m in G.SCADENZE_MESI:
            x = mis[(v, r, m)]
            g = "**" if cella(v, r, m) else ""
            print("| {}{}{} | {}{} mesi{} | {} | {} | {} | {} | {} | {} |".format(
                g, NOME_REGOLA[r], g, g, m, " — verdetto" + g if g else "", p(x.rendimento, 2), p(x.ribasso_max, 1),
                p(x.riduzione, 1), it(x.costo_punti, "+.3f"), p(x.premio_annuo, 2), x.operazioni))


def stampa_ribassi(tre: list, esiti: dict, mis: dict, pos: dict) -> None:
    print("\n## I tre ribassi peggiori con protezione — celle del verdetto\n")
    print("| versione, cella | massimo → fondo | senza protezione | con protezione (stesse date) | riduzione | ribasso "
          "massimo del protetto nella finestra (descrittivo) |\n|---|---|---:|---:|---:|---:|")
    for v in VERSIONI:
        r, m = CELLA_VERDETTO[v]
        x, es = mis[(v, r, m)], esiti[(v, r, m)]
        for (a, b, d), con, rid in zip(tre, x.profondita, x.riduzioni):
            dentro = ribasso_massimo(es.valori, pos[a], pos[b])[0]
            print("| {}, regola 3 × {} mesi | {} → {} | {} | {} | {} | {} |".format(
                v, m, a, b, p(d, 2), p(con, 2), p(rid, 2), p(dentro, 2)))
        print("| {}, regola 3 × {} mesi | **media semplice delle tre riduzioni** | | | **{}** | |".format(v, m, p(x.riduzione, 2)))
    print("\n### Tutte le 32 celle: profondità con protezione sulle stesse date (riduzione)\n")
    print("| versione | regola | scadenza | " + " | ".join("{} → {}".format(a, b) for a, b, _ in tre) + " | media delle riduzioni |")
    print("|---|---|---|" + "---:|" * 4)
    for v in VERSIONI:
        for r in REGOLE:
            for m in G.SCADENZE_MESI:
                x = mis[(v, r, m)]
                print("| {} | {} | {} mesi | {} | {} |".format(v, r, m, " | ".join(
                    "{} ({})".format(p(c, 1), p(q, 1)) for c, q in zip(x.profondita, x.riduzioni)), p(x.riduzione, 1)))


def stampa_guadagni(eventi: list, esiti: dict, pos: dict) -> None:
    print("\n## Guadagno delle put nei ribassi della lista A del Test F (% del portafoglio protetto al massimo)\n")
    print("| # | massimo | fondo | profondità dell'indice | A, regola 3 × 12 mesi | B, regola 3 × 3 mesi |\n|---|---|---|---:|---:|---:|")
    for i, ev in enumerate(eventi, 1):
        print("| {} | {} | {} | {} | {} | {} |".format(
            i, ev.massimo_data, ev.fondo_data, p(ev.profondita, 1),
            *(it(100 * guadagno_put(esiti[(v,) + CELLA_VERDETTO[v]], pos, ev.massimo_data, ev.fondo_data), "+.2f") + "%"
              for v in VERSIONI)))
    print("\n### Tutte le 32 celle (colonne: anno del massimo dell'evento)\n")
    print("| versione | regola | scadenza | " + " | ".join(str(ev.massimo_data.year) for ev in eventi) + " |")
    print("|---|---|---|" + "---:|" * len(eventi))
    for v in VERSIONI:
        for r in REGOLE:
            for m in G.SCADENZE_MESI:
                print("| {} | {} | {} mesi | {} |".format(v, r, m, " | ".join(
                    it(100 * guadagno_put(esiti[(v, r, m)], pos, ev.massimo_data, ev.fondo_data), "+.1f") for ev in eventi)))


def stampa_coincidenze(esiti: dict, mis: dict) -> None:
    print("\n## Coincidenza fra versione A e versione B, cella per cella\n")
    print("| regola | scadenza | operazioni A / B | stesse date di ingresso | massima differenza del valore giornaliero | "
          "riduzione A / B | costo A / B | coincidono |\n|---|---|---|---|---:|---|---|---|")
    for m in G.SCADENZE_MESI:
        for r in REGOLE:
            a, b = esiti[("A", r, m)], esiti[("B", r, m)]
            date = [o.ingresso for o in a.operazioni] == [o.ingresso for o in b.operazioni]
            diff = max(abs(x - y) for x, y in zip(a.valori, b.valori))
            ma, mb = mis[("A", r, m)], mis[("B", r, m)]
            print("| {} | {} mesi | {} / {} | {} | {} | {} / {} | {} / {} | {} |".format(
                r, m, len(a.operazioni), len(b.operazioni), "sì" if date else "no", it(diff, ".3g"),
                p(ma.riduzione, 2), p(mb.riduzione, 2), it(ma.costo_punti, "+.3f"), it(mb.costo_punti, "+.3f"),
                "**sì**" if (date and diff == 0.0) else "no"))
    a, b = mis[("A", 3, 12)], mis[("B", 3, 12)]
    print("\nCella del verdetto A (regola 3 × 12 mesi) contro la cella regola 3 × 12 mesi di B: riduzione {} contro {}; "
          "costo {} contro {}; differenze {} e {}.".format(
              it(a.riduzione, ".10f"), it(b.riduzione, ".10f"), it(a.costo_punti, ".10f"), it(b.costo_punti, ".10f"),
              it(a.riduzione - b.riduzione, ".3g"), it(a.costo_punti - b.costo_punti, ".3g")))


def stampa_tetto_teorico(D: G.Dati, tre: list, mis: dict) -> None:
    tetti = tetti_teorici(D, tre)
    print("\n## Riduzione ottenuta contro il tetto teorico della pre-registrazione (regola 3; una sola operazione aperta al massimo)\n")
    print("| versione | scadenza | tetto teorico medio ({}) | riduzione ottenuta, regola 3 ({}) | ottenuta / tetto |".format(
        " ; ".join(str(a.year) for a, _b, _d in tre), " ; ".join(str(a.year) for a, _b, _d in tre)))
    print("|---|---|---:|---:|---:|")
    for v in VERSIONI:
        for m in G.SCADENZE_MESI:
            t, x = tetti[(v, m)], mis[(v, 3, m)]
            g = "**" if cella(v, 3, m) else ""
            print("| {}{}{} | {}{} mesi{} | {} ({}) | {} ({}) | {} |".format(
                g, v, g, g, m, g, p(statistics.fmean(t), 1), " ; ".join(p(y, 0) for y in t), p(x.riduzione, 1),
                " ; ".join(p(y, 0) for y in x.riduzioni), p(x.riduzione / statistics.fmean(t), 0)))


def stampa_coperta(esiti: dict, mis: dict) -> None:
    print("\n## Parte coperta oltre il 100% (nessun limite applicato)\n")
    print("| versione | regola | scadenza | operazioni | con parte coperta > 100% | massimo | quando |\n|---|---|---|---:|---:|---:|---|")
    for v in VERSIONI:
        tot, oltre, massimo = 0, 0, (0.0, None, None)
        for r in REGOLE:
            for m in G.SCADENZE_MESI:
                es, x = esiti[(v, r, m)], mis[(v, r, m)]
                top = max(es.operazioni, key=lambda o: o.coperta) if es.operazioni else None
                print("| {} | {} | {} mesi | {} | {} | {} | {} |".format(
                    v, r, m, x.operazioni, x.oltre_100, p(x.coperta_max, 0), top.ingresso if top else "—"))
                tot, oltre = tot + x.operazioni, oltre + x.oltre_100
                if top and top.coperta > massimo[0]:
                    massimo = (top.coperta, top.ingresso, (r, m))
        print("| **{} — totale delle 16 celle** | | | **{}** | **{}** | **{}** | {} (regola {}, {} mesi) |".format(
            v, tot, oltre, p(massimo[0], 0), massimo[1], massimo[2][0], massimo[2][1]))


def stampa_blocchi(esiti: dict, M: Mercato) -> None:
    print("\n## Tetto della versione A: ingressi bloccati o slittati\n")
    print("| regola | scadenza | sedute (regola 1) o letture mensili (regole 2-4) bloccate dal tetto | ingressi slittati | dettaglio |\n|---|---|---:|---:|---|")
    for r in REGOLE:
        for m in G.SCADENZE_MESI:
            es = esiti[("A", r, m)]
            gruppi = slittamenti(es.bloccati, M.sedute)
            print("| {} | {} mesi | {} | {} | {} |".format(r, m, len(es.bloccati), len(gruppi), "; ".join(
                "{}{}".format(a, "" if n == 1 else " → {} ({} sedute)".format(b, n)) for a, b, n in gruppi) or "—"))
    print("\nVersione B: nessun tetto; ingressi bloccati {}.".format(
        sum(len(es.bloccati) for (v, _r, _m), es in esiti.items() if v == "B")))


def stampa_sensibilita(sens: dict, mis: dict) -> None:
    print("\n## Sensibilità descrittive — celle del verdetto\n")
    print("| versione, cella | variante | riduzione media | costo (punti) | rendimento annuo | premio annuo speso | "
          "operazioni | verdetto con questa variante (descrittivo: non cambia il verdetto) |\n|---|---|---:|---:|---:|---:|---:|---|")
    for v in VERSIONI:
        r, m = CELLA_VERDETTO[v]
        for nome, _i, _q, _val in VARIANTI:
            x = mis[(v, r, m)] if nome == "principale" else sens[nome][(v, r, m)]
            print("| {}, regola 3 × {} mesi | {} | {} | {} | {} | {} | {} | {} |".format(
                v, m, nome, p(x.riduzione, 2), it(x.costo_punti, "+.3f"), p(x.rendimento, 2), p(x.premio_annuo, 2),
                x.operazioni, verdetto(x.riduzione, x.costo_punti)))
    print("\n### Tutte le 32 celle: riduzione media / costo in punti, per variante\n")
    print("| versione | regola | scadenza | " + " | ".join(n for n, *_ in VARIANTI) + " |")
    print("|---|---|---|" + "---:|" * len(VARIANTI))
    for v in VERSIONI:
        for r in REGOLE:
            for m in G.SCADENZE_MESI:
                celle = []
                for nome, *_ in VARIANTI:
                    x = mis[(v, r, m)] if nome == "principale" else sens[nome][(v, r, m)]
                    celle.append("{} / {}".format(p(x.riduzione, 1), it(x.costo_punti, "+.2f")))
                print("| {} | {} | {} mesi | {} |".format(v, r, m, " | ".join(celle)))


def stampa_operazioni(esiti: dict) -> None:
    print("\n## Operazioni delle due celle del verdetto\n")
    for v in VERSIONI:
        r, m = CELLA_VERDETTO[v]
        print("### Versione {}, regola 3 × {} mesi\n".format(v, m))
        print("| # | ingresso | scadenza | chiusura | VIX | prezzo dello spread (% indice) | premio | parte coperta | "
              "chiusura a scadenza | valore a scadenza (% della chiusura di ingresso) | incasso / premio |\n"
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for i, o in enumerate(esiti[(v, r, m)].operazioni, 1):
            chiusa = o.incasso is not None
            print("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                i, o.ingresso, o.scadenza, it(o.s0, ".2f"), it(o.vix, ".2f"), p(o.prezzo / o.s0, 3), p(o.premio_pct, 1),
                p(o.coperta, 0), it(o.s_scadenza, ".2f") if chiusa else "aperta a fine periodo",
                p(o.valore_scadenza / o.s0, 2) if chiusa else "—", it(o.incasso / o.premio, ".2f") if chiusa else "—"))
        print()


def stampa_faber_limite(M: Mercato, ingressi: dict, esiti: dict, mis: dict, base: list, tre: list, pos: dict) -> None:
    """Aggiunta del 04-10-2026, dopo aver visto i risultati: una cella (B, Faber × 3 mesi) con la parte coperta
    limitata al 100% del portafoglio. Descrittiva: una serie in più oltre le 160, nessun verdetto."""
    v, r, m = "B", 4, 3
    senza, x0 = esiti[(v, r, m)], mis[(v, r, m)]
    con = simula(M, m, G.PREMIO[v][m], False, ingressi[r], limite_coperta=1.0)
    x1 = misura(M, con, base, tre, pos)
    cop = [o.coperta for o in senza.operazioni]
    top = max(senza.operazioni, key=lambda o: o.coperta)
    print("\n## Faber × 3 mesi, versione B — copertura e limite al 100% (descrittiva, aggiunta dopo aver visto i risultati)\n")
    print("Serie guardate: {} pre-registrate + 1 aggiunta = {}.\n".format(32 * len(VARIANTI), 32 * len(VARIANTI) + 1))
    print("Parte coperta delle {} operazioni della cella senza limite: media {} ; mediana {} ; minima {} ; massima {} ({}) ; "
          "oltre il 100%: {} su {}.\n".format(len(cop), p(statistics.fmean(cop), 1), p(statistics.median(cop), 1), p(min(cop), 1),
                                              p(top.coperta, 1), top.ingresso, sum(1 for c in cop if c > 1.0), len(cop)))
    morde = [o for o in con.operazioni if o.premio_pct < G.PREMIO[v][m]]
    cop1 = [o.coperta for o in con.operazioni]
    print("Con il limite al 100%: il limite morde in {} operazioni su {}; parte coperta media {} ; massima {} ; premio "
          "effettivo per operazione: minimo {} ; medio {} ; massimo {}.\n".format(
              len(morde), len(con.operazioni), p(statistics.fmean(cop1), 1), p(max(cop1), 1),
              p(min(o.premio_pct for o in con.operazioni), 3), p(statistics.fmean(o.premio_pct for o in con.operazioni), 3),
              p(max(o.premio_pct for o in con.operazioni), 3)))
    print("| misura | senza limite (cella della griglia) | limite al 100% |\n|---|---:|---:|")
    print("| rendimento annuo | {} | {} |".format(p(x0.rendimento, 2), p(x1.rendimento, 2)))
    print("| ribasso massimo | {} | {} |".format(p(x0.ribasso_max, 1), p(x1.ribasso_max, 1)))
    for i, (a, b, d) in enumerate(tre):
        print("| {} → {} (senza protezione {}): profondità con protezione (riduzione) | {} ({}) | {} ({}) |".format(
            a, b, p(d, 2), p(x0.profondita[i], 2), p(x0.riduzioni[i], 2), p(x1.profondita[i], 2), p(x1.riduzioni[i], 2)))
    print("| riduzione media dei tre ribassi peggiori | {} | {} |".format(p(x0.riduzione, 2), p(x1.riduzione, 2)))
    print("| riduzione media, non arrotondata | {} | {} |".format(it(x0.riduzione, ".10f"), it(x1.riduzione, ".10f")))
    print("| costo (punti di rendimento annuo) | {} | {} |".format(it(x0.costo_punti, "+.3f"), it(x1.costo_punti, "+.3f")))
    print("| costo, non arrotondato | {} | {} |".format(it(x0.costo_punti, ".10f"), it(x1.costo_punti, ".10f")))
    print("| premio annuo effettivamente speso | {} | {} |".format(p(x0.premio_annuo, 2), p(x1.premio_annuo, 2)))
    print("| operazioni | {} | {} |".format(x0.operazioni, x1.operazioni))
    print("| riduzione ≥ 1/3 | {} | {} |".format(*("sì" if x.riduzione >= RIDUZIONE_REGGE else "no" for x in (x0, x1))))
    print("| costo ≤ 1,5 punti | {} | {} |".format(*("sì" if x.costo_punti <= COSTO_REGGE else "no" for x in (x0, x1))))
    print("| supererebbe le due soglie di REGGE (descrittivo: non è un verdetto) | {} | {} |".format(
        *("sì" if verdetto(x.riduzione, x.costo_punti) == "REGGE" else "no" for x in (x0, x1))))
    print("\nControllo contabile della serie con il limite (protetto − non protetto contro premi e incassi): scostamento {}.".format(
        it(scostamento_contabile(M, con, base), ".3g")))


# ------------------------------------------------------------------ controlli di buon senso

def controlli(D: G.Dati, M: Mercato, base: list, tre: list, esiti: dict) -> None:
    print("## Controlli di buon senso\n")
    # (a) nessuna operazione = indice
    vuoto = simula(M, 12, 0.03, True, set())
    giorni = giorni_periodo(M.sedute)
    s0, s1 = M.chiusura[M.sedute[0]], M.chiusura[M.sedute[-1]]
    diretto = [CAPITALE * M.chiusura[d] / s0 for d in M.sedute]
    r_indice = (s1 / s0) ** (365.0 / giorni) - 1.0
    dd_indice = ribasso_massimo([M.chiusura[d] for d in M.sedute])
    dd_vuoto = ribasso_massimo(vuoto.valori)
    print("**(a) Cella «nessuna operazione» = indice.** Simulazione con il segnale mai acceso: operazioni {}; massima "
          "differenza giornaliera dal portafoglio senza protezione {}; massima differenza da 100 × chiusura / chiusura "
          "del {} {}.".format(len(vuoto.operazioni), it(max(abs(x - y) for x, y in zip(vuoto.valori, base)), ".3g"),
                              M.sedute[0], it(max(abs(x - y) for x, y in zip(vuoto.valori, diretto)), ".3g")))
    print("Chiusure: {} ({}) → {} ({}). Rendimento annuo dell'indice dalle chiusure {} ; della cella vuota {} ; "
          "differenza {}. Ribasso massimo dell'indice {} ({} → {}); della cella vuota {} ({} → {}).".format(
              it(s0, ".2f"), M.sedute[0], it(s1, ".2f"), M.sedute[-1], p(r_indice, 6),
              p(rendimento_annuo(vuoto.valori[-1], giorni), 6), it(r_indice - rendimento_annuo(vuoto.valori[-1], giorni), ".3g"),
              p(dd_indice[0], 4), M.sedute[dd_indice[1]], M.sedute[dd_indice[2]],
              p(dd_vuoto[0], 4), M.sedute[dd_vuoto[1]], M.sedute[dd_vuoto[2]]))
    for a, b, prof in tre:
        print("  ribasso {} → {}: portafoglio {} ; indice dalle chiusure {} / {} − 1 = {}".format(
            a, b, p(prof, 4), it(M.chiusura[b], ".2f"), it(M.chiusura[a], ".2f"), p(M.chiusura[b] / M.chiusura[a] - 1, 4)))

    # (b) una operazione reale del 2008, ricalcolata passo per passo senza le funzioni di prezzo
    scelta = None
    for chiave in (("A", 3, 12), ("B", 3, 3), ("A", 2, 12), ("A", 1, 12)):
        for i, o in enumerate(esiti[chiave].operazioni):
            if o.ingresso.year == 2008 and o.incasso is not None:
                scelta = (chiave, i, o)
                break
        if scelta:
            break
    if scelta is None:
        raise RuntimeError("nessuna operazione del 2008 nelle celle guardate dal controllo (b)")
    (v, r, m), i, o = scelta
    es = esiti[(v, r, m)]
    pos = {d: j for j, d in enumerate(M.sedute)}
    print("\n**(b) Una operazione del 2008 ricalcolata a mano** — versione {}, regola {}, {} mesi, operazione n. {}.\n".format(v, r, m, i + 1))
    S = D.chiusura[o.ingresso]
    d_vix, vix = D.vix.ultimo_noto(o.ingresso)
    d_tb, tb = D.dtb3.ultimo_noto(o.ingresso)
    bersaglio = E.mesi_prima(o.ingresso, -m)
    fine = max(d for d in D.sedute if d <= bersaglio)
    T = (fine - o.ingresso).days / 365.0
    P = 1.0 - tb / 100.0 * 91 / 360.0
    rr = (365.0 / 91.0) * math.log(1.0 / P)
    q = G.DIVIDENDO
    prezzi = []
    print("    Dati letti: chiusura GSPC del {} = {:.2f} ; VIXCLS del {} = {:.2f} ; DTB3 del {} = {:.2f}".format(
        o.ingresso, S, d_vix, vix, d_tb, tb))
    print("    Scadenza: {} + {} mesi = {} → seduta {} ; {} giorni ; T = {:.6f}".format(
        o.ingresso, m, bersaglio, fine, (fine - o.ingresso).days, T))
    print("    Tasso: P = {:.8f} ; r = {:.8f}".format(P, rr))
    for nome, k, sigma in (("comprata", 0.95 * S, vix / 100.0), ("venduta", 0.75 * S, (vix + 5.0) / 100.0)):
        d1 = (math.log(S / k) + (rr - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        n1 = 0.5 * (1.0 + math.erf(-d1 / math.sqrt(2.0)))
        n2 = 0.5 * (1.0 + math.erf(-d2 / math.sqrt(2.0)))
        put = k * math.exp(-rr * T) * n2 - S * math.exp(-q * T) * n1
        prezzi.append(put)
        print("    put {}: K = {:.4f} ; σ = {:.4f} ; d1 = {:.6f} ; d2 = {:.6f} ; N(−d1) = {:.6f} ; N(−d2) = {:.6f} ; put = {:.4f}".format(
            nome, k, sigma, d1, d2, n1, n2, put))
    prezzo = prezzi[0] - prezzi[1]
    v_prima = es.valori[pos[o.ingresso]]
    premio = G.PREMIO[v][m] * v_prima
    n = premio / prezzo
    s_fin = D.chiusura[fine]
    payoff = max(0.95 * S - s_fin, 0.0) - max(0.75 * S - s_fin, 0.0)
    print("    Spread = {:.4f} − {:.4f} = {:.6f} punti ({:.4%} della chiusura)".format(prezzi[0], prezzi[1], prezzo, prezzo / S))
    print("    Portafoglio alla chiusura dell'ingresso (dalla serie del programma) = {:.6f} ; premio = {:.1%} × {:.6f} = {:.6f}".format(
        v_prima, G.PREMIO[v][m], v_prima, premio))
    print("    Numero di spread = {:.6f} / {:.6f} = {:.8f} ; parte coperta = {:.4%}".format(premio, prezzo, n, n * S / v_prima))
    print("    Chiusura del {} = {:.2f} ; valore a scadenza = max({:.4f} − {:.2f}, 0) − max({:.4f} − {:.2f}, 0) = {:.4f} punti ; "
          "incasso = {:.8f} × {:.4f} = {:.6f}".format(fine, s_fin, 0.95 * S, s_fin, 0.75 * S, s_fin, payoff, n, payoff, n * payoff))
    print("\n| voce | a mano | programma | differenza |\n|---|---:|---:|---:|")
    for nome, mano, prog in (("scadenza", fine, o.scadenza), ("prezzo dello spread", prezzo, o.prezzo), ("premio", premio, o.premio),
                             ("numero di spread", n, o.n), ("valore a scadenza (punti)", payoff, o.valore_scadenza),
                             ("incasso", n * payoff, o.incasso)):
        if isinstance(mano, dt.date):
            print("| {} | {} | {} | {} |".format(nome, mano, prog, "0" if mano == prog else "**DIVERSA**"))
        else:
            print("| {} | {} | {} | {} |".format(nome, it(mano, ".8f"), it(prog, ".8f"), it(mano - prog, ".3g")))

    # (c) premi e incassi contro la differenza fra protetto e non protetto
    print("\n**(c) Premi e incassi contro la differenza fra portafoglio protetto e non protetto.** Per ogni cella: valore "
          "finale protetto − non protetto, contro la somma di (− premio, + incasso), ciascuno cresciuto con l'indice dal "
          "suo giorno al {}, più lo spread ancora aperto.\n".format(M.sedute[-1]))
    print("| cella | operazioni | somma dei premi | somma degli incassi | spread aperto alla fine | protetto − non protetto "
          "| ricostruito da premi e incassi | differenza |\n|---|---:|---:|---:|---:|---:|---:|---:|")
    for vv in VERSIONI:
        chiave = (vv,) + CELLA_VERDETTO[vv]
        e2 = esiti[chiave]
        sc = scostamento_contabile(M, e2, base)
        print("| {}, regola 3 × {} mesi | {} | {} | {} | {} | {} | {} | {} |".format(
            vv, chiave[2], len(e2.operazioni), it(sum(o2.premio for o2 in e2.operazioni), ".4f"),
            it(sum(o2.incasso for o2 in e2.operazioni if o2.incasso is not None), ".4f"), it(e2.spread[-1], ".4f"),
            it(e2.valori[-1] - base[-1], ".6f"), it(e2.valori[-1] - base[-1] - sc, ".6f"), it(sc, ".3g")))
    print("\nMassimo scostamento assoluto sulle 32 celle: {}.".format(
        it(max(abs(scostamento_contabile(M, e2, base)) for e2 in esiti.values()), ".3g")))
    semplice = min((es2 for es2 in esiti.values() if es2.operazioni), key=lambda es2: len(es2.operazioni))
    o1 = semplice.operazioni[0]
    j = pos[o1.scadenza] if o1.incasso is not None else None
    if j is not None:
        quote0 = CAPITALE / M.chiusura[M.sedute[0]]
        atteso = quote0 * o1.s_scadenza - o1.premio * o1.s_scadenza / o1.s0 + o1.incasso
        print("Caso semplice, una sola operazione (la prima della cella con meno operazioni, ingresso {}, scadenza {}): "
              "non protetto alla scadenza {} ; − premio {} × {}/{} ; + incasso {} ; atteso {} ; programma {} ; differenza {}.".format(
                  o1.ingresso, o1.scadenza, it(quote0 * o1.s_scadenza, ".6f"), it(o1.premio, ".6f"), it(o1.s_scadenza, ".2f"),
                  it(o1.s0, ".2f"), it(o1.incasso, ".6f"), it(atteso, ".6f"), it(semplice.valori[j], ".6f"),
                  it(atteso - semplice.valori[j], ".3g")))


# ------------------------------------------------------------------ confronto con un'altra lettura del composito

MESI_IN_EVIDENZA = (dt.date(2007, 12, 31), dt.date(2008, 1, 31), dt.date(2008, 2, 29), dt.date(2008, 3, 31),
                    dt.date(2019, 11, 30), dt.date(2019, 12, 31), dt.date(2020, 1, 31), dt.date(2020, 2, 29))
FINESTRE_IN_EVIDENZA = ((dt.date(2007, 10, 1), dt.date(2008, 12, 31)), (dt.date(2019, 7, 1), dt.date(2020, 12, 31)))


def carica_modulo(percorso: str):
    """Una copia di `test_f.py` caricata da file con un altro nome di modulo; non tocca quella del repo."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_f_alternativo", percorso)
    if spec is None or spec.loader is None:
        raise G.DatoMancante("modulo del composito non caricabile: {}".format(Path(percorso).name))
    mod = importlib.util.module_from_spec(spec)
    prima = list(sys.path)
    sys.modules[spec.name] = mod               # le dataclass del modulo lo cercano in sys.modules
    spec.loader.exec_module(mod)
    sys.path[:] = prima                        # la copia aggiunge la sua cartella al path: si toglie
    return mod


def confronto_composito(percorso: str) -> int:
    """Descrittivo, fatto dopo aver visto i risultati: le celle delle regole 2 e 3 (le sole che leggono il composito)
    con il composito calcolato da `percorso`, accanto a quelle del referto (composito di `test_f.py` del repo). Non
    cambia nessun verdetto: quello valido è con il composito del repo (ADR-071, deciso prima dei risultati)."""
    import test_f as F
    alt = carica_modulo(percorso)
    D = G.Dati()
    M = mercato_reale(D)
    vix = serie_sulle_sedute(D.vix, D.chiusura)
    base = senza_protezione(M)
    pos = {d: i for i, d in enumerate(M.sedute)}
    tre = tre_ribassi(M.sedute, base)
    mesi = {"repo": F.calcola_mesi(F.Dati(), log=lambda *_: None), "alt": alt.calcola_mesi(alt.Dati(), log=lambda *_: None)}
    letture = {k: letture_mensili(v, vix, D.sedute) for k, v in mesi.items()}
    ingressi = {k: {r: calendario_ingressi(letture[k][r], M.sedute) for r in (2, 3)} for k in mesi}
    per_fm = {k: {m.fm: m for m in v} for k, v in mesi.items()}

    print("## Effetto della correzione di lettura del composito (ADR-071) — confronto descrittivo\n")
    print("Composito «corretto» = `test_f.py` del repo; «vecchia lettura» = `{}`, caricato da fuori dal repo. "
          "`riga_gsw` nel modulo del repo: {}; nel modulo alternativo: {}.\n".format(
              Path(percorso).name, "presente" if hasattr(F, "riga_gsw") else "ASSENTE",
              "presente" if hasattr(alt, "riga_gsw") else "assente"))
    for k, nome in (("repo", "corretto"), ("alt", "vecchia lettura")):
        senza = sorted(fm for fm in letture[k][2] if per_fm[k][fm].composito5 is None)
        lungo = [m.fm for m in mesi[k] if dt.date(1973, 2, 28) <= m.fm <= dt.date(2025, 12, 31)]
        senza_lungo = [fm for fm in lungo if per_fm[k][fm].composito5 is None]
        print("- {}: letture del Test G senza composito {} su {}{}; fini mese 1973-02 → 2025-12 senza composito {} su {}; "
              "letture accese regola 2: {} ; regola 3: {}.".format(
                  nome, len(senza), len(letture[k][2]),
                  "" if not senza else " (" + ", ".join(fm.strftime("%Y-%m") for fm in senza) + ")",
                  len(senza_lungo), len(lungo), sum(1 for x in letture[k][2].values() if x is True),
                  sum(1 for x in letture[k][3].values() if x is True)))

    def stato(x):
        return "mancante" if x is None else ("accesa" if x else "spenta")

    print("\n### Letture intorno a 2008-02 e 2020-01\n")
    print("| fine mese letta | ingresso possibile | composito corretto | composito vecchia lettura | regola 2 corretto / vecchia | "
          "regola 3 corretto / vecchia |\n|---|---|---:|---:|---|---|")
    for fm in MESI_IN_EVIDENZA:
        c = {k: per_fm[k][fm].composito5 for k in mesi}
        print("| {} | {} | {} | {} | {} / {} | {} / {} |".format(
            fm, M.sedute[bisect.bisect_right(M.sedute, fm)], "mancante" if c["repo"] is None else c["repo"],
            "**mancante**" if c["alt"] is None else c["alt"], stato(letture["repo"][2][fm]), stato(letture["alt"][2][fm]),
            stato(letture["repo"][3][fm]), stato(letture["alt"][3][fm])))

    esiti = {k: {(v, r, m): simula(M, m, G.PREMIO[v][m], v == "A", ingressi[k][r])
                 for v in VERSIONI for r in (2, 3) for m in G.SCADENZE_MESI} for k in mesi}
    mis = {k: {c: misura(M, es, base, tre, pos) for c, es in esiti[k].items()} for k in mesi}

    print("\n### Le 16 celle delle regole 2 e 3: composito corretto (a referto) contro vecchia lettura\n")
    print("Serie guardate in più: {} (regole 2 e 3 × 4 scadenze × 2 versioni, scelta principale).\n".format(len(esiti["alt"])))
    print("| versione | regola | scadenza | operazioni corretto / vecchia | ingressi solo con il composito corretto | ingressi solo "
          "con la vecchia lettura | riduzione media corretto / vecchia | costo (punti) corretto / vecchia |\n|---|---|---|---|---|---|---|---|")
    for v in VERSIONI:
        for r in (2, 3):
            for m in G.SCADENZE_MESI:
                a, b = esiti["repo"][(v, r, m)], esiti["alt"][(v, r, m)]
                da, db = [o.ingresso for o in a.operazioni], [o.ingresso for o in b.operazioni]
                xa, xb = mis["repo"][(v, r, m)], mis["alt"][(v, r, m)]
                g = "**" if cella(v, r, m) else ""
                print("| {}{}{} | {}{}{} | {}{} mesi{} | {} / {} | {} | {} | {} / {} | {} / {} |".format(
                    g, v, g, g, r, g, g, m, " — verdetto" + g if g else "", len(da), len(db),
                    ", ".join(str(d) for d in da if d not in db) or "—", ", ".join(str(d) for d in db if d not in da) or "—",
                    p(xa.riduzione, 2), p(xb.riduzione, 2), it(xa.costo_punti, "+.3f"), it(xb.costo_punti, "+.3f")))

    print("\n### Ingressi delle regole 2 e 3 nelle due finestre in evidenza (versione B; nella A le date sono le stesse)\n")
    print("| regola | scadenza | finestra | ingressi con il composito corretto | ingressi con la vecchia lettura |\n|---|---|---|---|---|")
    for r in (2, 3):
        for m in G.SCADENZE_MESI:
            for da_, a_ in FINESTRE_IN_EVIDENZA:
                righe = [", ".join(str(o.ingresso) for o in esiti[k][("B", r, m)].operazioni if da_ <= o.ingresso <= a_) or "—"
                         for k in ("repo", "alt")]
                print("| {} | {} mesi | {} → {} | {} | {} |".format(r, m, da_, a_, righe[0], righe[1]))

    print("\n### I due verdetti con la vecchia lettura (descrittivo: il verdetto valido è quello con il composito corretto)\n")
    print("| versione | cella | riduzione corretto (a referto) | costo corretto | verdetto valido | riduzione vecchia lettura | "
          "costo vecchia lettura | cosa darebbe la vecchia lettura |\n|---|---|---:|---:|---|---:|---:|---|")
    for v in VERSIONI:
        r, m = CELLA_VERDETTO[v]
        xa, xb = mis["repo"][(v, r, m)], mis["alt"][(v, r, m)]
        print("| {} | regola 3 × {} mesi | {} | {} | **{}** | {} | {} | {} |".format(
            v, m, it(xa.riduzione, ".10f"), it(xa.costo_punti, ".10f"), verdetto(xa.riduzione, xa.costo_punti),
            it(xb.riduzione, ".10f"), it(xb.costo_punti, ".10f"), verdetto(xb.riduzione, xb.costo_punti)))
    return 0


# ------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if "--confronto-composito" in argv:
        i = argv.index("--confronto-composito")
        if i + 1 >= len(argv):
            raise SystemExit("--confronto-composito vuole il percorso di una copia di test_f.py")
        return confronto_composito(argv[i + 1])
    import test_f as F
    D = G.Dati()
    M = mercato_reale(D)
    mesi_f = F.calcola_mesi(F.Dati(), log=lambda *_: None)
    letture = letture_mensili(mesi_f, serie_sulle_sedute(D.vix, D.chiusura), D.sedute)
    ingressi = {1: None}
    ingressi.update({r: calendario_ingressi(letture[r], M.sedute) for r in (2, 3, 4)})
    base = senza_protezione(M)
    pos = {d: i for i, d in enumerate(M.sedute)}
    tre = tre_ribassi(M.sedute, base)
    eventi = [ev for ev in E.eventi_12_mesi(D.gspc) if ev.massimo_data >= G.PERIODO[0] and ev.soglia_data <= G.PERIODO[1]]
    for ev in eventi:
        if ev.fondo_data > M.sedute[-1]:
            raise G.DatoMancante("il fondo dell'evento {} cade dopo la fine del periodo".format(ev.massimo_data))

    esiti = esegui(M, ingressi, VARIANTI[0])
    mis = {k: misura(M, es, base, tre, pos) for k, es in esiti.items()}
    sens = {}
    for variante in VARIANTI[1:]:
        sens[variante[0]] = {k: misura(M, es, base, tre, pos) for k, es in esegui(M, ingressi, variante).items()}

    print("# Materiale del referto — Test G, fermata 2\n")
    print("Combinazioni guardate: {} (2 con verdetto, {} descrittive); serie guardate con le sensibilità: {}.\n".format(
        len(esiti), len(esiti) - 2, len(esiti) * len(VARIANTI)))
    stampa_dati(D, M, letture, mesi_f)
    stampa_tre(tre, base, M)
    stampa_verdetti(mis)
    for v in VERSIONI:
        stampa_griglia(v, mis)
    stampa_ribassi(tre, esiti, mis, pos)
    stampa_guadagni(eventi, esiti, pos)
    stampa_coincidenze(esiti, mis)
    stampa_tetto_teorico(D, tre, mis)
    stampa_coperta(esiti, mis)
    stampa_blocchi(esiti, M)
    stampa_sensibilita(sens, mis)
    stampa_operazioni(esiti)
    controlli(D, M, base, tre, esiti)
    stampa_faber_limite(M, ingressi, esiti, mis, base, tre, pos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
