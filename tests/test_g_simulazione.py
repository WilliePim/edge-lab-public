"""Prove sulla simulazione del Test G (`backtest/drawdown_alpha/test_g.py`).

Nessuna rete e nessun archivio: i lettori dei dati sono sostituiti da una funzione che fallisce, e ogni serie e'
costruita a mano qui dentro. Si verifica cio' che la pre-registrazione fissa: la contabilita' (il premio esce vendendo
quote, l'incasso a scadenza si reinveste, la percentuale del premio non raddoppia mai), una sola operazione aperta, il
tetto a 360 giorni della versione A (il 6% esatto e' ammesso, oltre no), l'ingresso alla prima seduta dopo la lettura
mensile senza sguardo in avanti, il valore a scadenza nei tre casi, la misura dei ribassi sulle stesse date e il
verdetto sui casi limite delle soglie.
"""
import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest" / "drawdown_alpha"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, near, raises, report, section

import test_g as T
import test_g_dati as G


def _niente_rete(*_a, **_k):
    raise AssertionError("questa suite non deve leggere dati")


G.api.fred = _niente_rete
G.api.prices = _niente_rete


def feriali(da: dt.date, a: dt.date) -> list:
    out, d = [], da
    while d <= a:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def mercato(da: dt.date, a: dt.date, prezzo, vix: float = 20.0, tasso: float = 0.0, archivio_fino: dt.date | None = None):
    """Mercato finto: sedute = giorni feriali, `prezzo` = numero fisso o funzione della data."""
    sedute = feriali(da, a)
    f = prezzo if callable(prezzo) else (lambda _d: prezzo)
    archivio = feriali(da, archivio_fino or a + dt.timedelta(days=800))
    return T.Mercato(sedute, archivio, {d: float(f(d)) for d in archivio}, {d: vix for d in sedute}, {d: tasso for d in sedute})


INIZIO, FINE = dt.date(2020, 1, 2), dt.date(2021, 12, 31)


# ------------------------------------------------------------- contabilita'

def test_contabilita():
    section("contabilita': premio vendendo quote, incasso reinvestito, nessun raddoppio")
    M = mercato(INIZIO, FINE, 100.0)
    es = T.simula(M, 3, 0.03, False, {INIZIO})
    pos = {d: i for i, d in enumerate(M.sedute)}
    check("una operazione", len(es.operazioni) == 1, str(len(es.operazioni)))
    o = es.operazioni[0]
    atteso = G.put_spread(100.0, 95.0, 75.0, G.anni(INIZIO, dt.date(2020, 4, 2)), 0.0, 20.0)
    check("scadenza: 3 mesi di calendario", o.scadenza == dt.date(2020, 4, 2), str(o.scadenza))
    check("strike 95 e 75 sulla chiusura di ingresso", near(o.k1, 95.0, 1e-12) and near(o.k2, 75.0, 1e-12))
    check("prezzo = put_spread all'ingresso", near(o.prezzo, atteso, 1e-12), "{} {}".format(o.prezzo, atteso))
    check("premio = 3% del portafoglio (100) = 3", near(o.premio, 3.0, 1e-12), str(o.premio))
    check("numero di spread = premio / prezzo", near(o.n, 3.0 / atteso, 1e-12), str(o.n))
    check("parte coperta = premio % / costo dello spread in % dell'indice", near(o.coperta, 0.03 / (atteso / 100.0), 1e-12))
    check("l'acquisto non muove il valore del portafoglio (valutazione a modello)", near(es.valori[0], 100.0, 1e-12), str(es.valori[0]))
    check("lo spread aperto vale il premio nel giorno di ingresso", near(es.spread[0], 3.0, 1e-12), str(es.spread[0]))
    j = pos[o.scadenza]
    check("indice fermo: a scadenza lo spread vale zero e il portafoglio 97", near(es.valori[j], 97.0, 1e-12), str(es.valori[j]))
    check("...e resta 97: le quote vendute per il premio non tornano", near(es.valori[-1], 97.0, 1e-12), str(es.valori[-1]))
    check("prima della scadenza il portafoglio e' quote x chiusura + spread a modello",
          near(es.valori[10], 97.0 + es.spread[10], 1e-12) and 0.0 < es.spread[10] < 3.0, "{} {}".format(es.valori[10], es.spread[10]))

    section("incasso a scadenza reinvestito nell'indice")
    scad = dt.date(2020, 4, 2)
    M2 = mercato(INIZIO, FINE, lambda d: 100.0 if d < scad else 80.0)
    e2 = T.simula(M2, 3, 0.03, False, {INIZIO})
    o2 = e2.operazioni[0]
    j = pos[scad]
    check("valore a scadenza fra i due strike: 95 - 80 = 15 punti", near(o2.valore_scadenza, 15.0, 1e-12), str(o2.valore_scadenza))
    check("incasso = numero di spread x 15", near(o2.incasso, o2.n * 15.0, 1e-12))
    check("portafoglio a scadenza = 0,97 quote x 80 + incasso", near(e2.valori[j], 0.97 * 80.0 + o2.incasso, 1e-10), str(e2.valori[j]))
    check("dopo la scadenza non c'e' piu' spread", e2.spread[j] == 0.0 and e2.spread[-1] == 0.0)
    M3 = mercato(INIZIO, FINE, lambda d: 100.0 if d < scad else (80.0 if d == scad else 160.0))
    e3 = T.simula(M3, 3, 0.03, False, {INIZIO})
    check("l'incasso e' in quote: se l'indice raddoppia dopo la scadenza, raddoppia tutto il portafoglio",
          near(e3.valori[-1], 2.0 * e3.valori[j], 1e-10), "{} {}".format(e3.valori[-1], e3.valori[j]))
    base = T.senza_protezione(M2)
    check("premi e incassi spiegano la differenza dal portafoglio senza protezione",
          near(T.scostamento_contabile(M2, e2, base), 0.0, 1e-10), str(T.scostamento_contabile(M2, e2, base)))
    check("...con l'indice fermo dopo l'incasso: protetto - non protetto = incasso - premio x 80/100",
          near(e2.valori[-1] - base[-1], o2.incasso - 3.0 * 0.8, 1e-10))

    section("nessun raddoppio: la percentuale del premio non cambia dopo un premio perso")
    e4 = T.simula(M, 3, 0.03, False, None)                               # regola 1, indice fermo: ogni premio e' perso
    check("piu' operazioni in fila", len(e4.operazioni) >= 7, str(len(e4.operazioni)))
    check("la percentuale e' sempre 3%", all(o.premio_pct == 0.03 for o in e4.operazioni))
    check("il premio e' 3% del portafoglio corrente: 3, poi 2,91, poi 2,8227",
          near(e4.operazioni[0].premio, 3.0, 1e-12) and near(e4.operazioni[1].premio, 2.91, 1e-12)
          and near(e4.operazioni[2].premio, 2.8227, 1e-12), str([o.premio for o in e4.operazioni[:3]]))
    check("ogni premio e' piu' piccolo del precedente, mai piu' grande",
          all(b.premio < a.premio for a, b in zip(e4.operazioni, e4.operazioni[1:])))
    check("indice fermo: protetto - non protetto = - somma dei premi + spread aperto",
          near(e4.valori[-1] - 100.0, -sum(o.premio for o in e4.operazioni) + e4.spread[-1], 1e-10))

    section("valutazione al valore intrinseco (robustezza descrittiva)")
    e5 = T.simula(M, 3, 0.03, False, {INIZIO}, valutazione="intrinseco")
    check("nel giorno di ingresso il portafoglio scende del premio", near(e5.valori[0], 97.0, 1e-12), str(e5.valori[0]))
    check("stesso numero di spread e stesso premio della valutazione a modello",
          e5.operazioni[0].n == es.operazioni[0].n and e5.operazioni[0].premio == es.operazioni[0].premio)
    check("valutazione sconosciuta: errore", raises(lambda: T.simula(M, 3, 0.03, False, None, valutazione="boh"), ValueError))

    section("nessuna operazione = indice")
    Mi = mercato(INIZIO, FINE, lambda d: 100.0 + (d - INIZIO).days % 37)
    vuoto = T.simula(Mi, 12, 0.03, True, set())
    check("segnale mai acceso: nessuna operazione", vuoto.operazioni == [] and vuoto.bloccati == [])
    check("...e il portafoglio e' esattamente quello senza protezione", vuoto.valori == T.senza_protezione(Mi))
    check("che parte da 100", T.senza_protezione(Mi)[0] == 100.0)


# ------------------------------------------------------------- una sola operazione, scadenze

def test_una_alla_volta():
    section("una sola operazione aperta alla volta")
    M = mercato(INIZIO, FINE, lambda d: 100.0 + 0.01 * (d - INIZIO).days)
    for mesi in (3, 6, 9, 12):
        es = T.simula(M, mesi, 0.03, False, None)
        ops = es.operazioni
        check("{} mesi: nessuna operazione comincia prima che scada la precedente".format(mesi),
              all(b.ingresso >= a.scadenza for a, b in zip(ops, ops[1:])))
        check("{} mesi, regola 1 senza tetto: rinnovo nella seduta di scadenza".format(mesi),
              all(b.ingresso == a.scadenza for a, b in zip(ops, ops[1:])) and ops[0].ingresso == INIZIO)
    tutti = set(M.sedute)
    es = T.simula(M, 12, 0.03, False, tutti)
    check("segnale acceso in ogni seduta ma spread aperto: si aspetta la scadenza",
          [o.ingresso for o in es.operazioni] == [INIZIO, dt.date(2021, 1, 1), dt.date(2021, 12, 31)],
          str([o.ingresso for o in es.operazioni]))
    check("2021-01-02 e' sabato: la scadenza a 12 mesi dal 2020-01-02 e' la seduta PRIMA (2021-01-01), mai dopo",
          T.simula(M, 12, 0.03, False, {INIZIO}).operazioni[0].scadenza == dt.date(2021, 1, 1),
          str(T.simula(M, 12, 0.03, False, {INIZIO}).operazioni[0].scadenza))

    section("scadenza oltre l'archivio e spread aperto a fine periodo")
    Mc = mercato(INIZIO, FINE, 100.0, archivio_fino=dt.date(2022, 3, 31))
    ingresso = dt.date(2021, 9, 1)
    ec = T.simula(Mc, 12, 0.03, False, {ingresso})
    oc = ec.operazioni[0]
    check("scadenza oltre l'ultima seduta dell'archivio: la data di calendario", oc.scadenza == dt.date(2022, 9, 1), str(oc.scadenza))
    check("lo spread resta aperto: nessun incasso", oc.incasso is None and oc.valore_scadenza is None)
    check("...e alla fine vale il valore di modello di quel giorno",
          near(ec.spread[-1], oc.n * G.put_spread(100.0, 95.0, 75.0, G.anni(FINE, oc.scadenza), 0.0, 20.0), 1e-12)
          and ec.spread[-1] > 0)
    check("scadenza dentro l'archivio ma dopo il periodo: seduta precedente come sempre (2022-01-01 sabato -> 2021-12-31)",
          T.scadenza_operazione(dt.date(2021, 7, 1), 6, Mc.sedute_archivio) == dt.date(2021, 12, 31))


# ------------------------------------------------------------- tetto a 360 giorni

def test_tetto():
    section("tetto della versione A: 6% sui 360 giorni precedenti, nuova operazione compresa")
    D = dt.date(2021, 6, 1)
    g = lambda n: D - dt.timedelta(days=n)
    check("3% + 3% nuovo = 6% esatto: ammesso", T.tetto_permette([(g(200), 300)], D, 300))
    check("3% + 3% + 3% nuovo = 9%: bloccato", not T.tetto_permette([(g(300), 300), (g(100), 300)], D, 300))
    check("4 x 1,5% = 6% esatto: ammesso", T.tetto_permette([(g(270), 150), (g(180), 150), (g(90), 150)], D, 150))
    check("5 x 1,5% = 7,5%: bloccato", not T.tetto_permette([(g(359), 150), (g(270), 150), (g(180), 150), (g(90), 150)], D, 150))
    check("un ingresso a 359 giorni conta", not T.tetto_permette([(g(359), 300), (g(100), 300)], D, 300))
    check("un ingresso a 360 giorni esatti non conta (date > D - 360)", T.tetto_permette([(g(360), 300), (g(100), 300)], D, 300))
    check("un ingresso a 365 giorni non conta", T.tetto_permette([(g(365), 150), (g(270), 150), (g(180), 150), (g(90), 150)], D, 150))
    check("nessun ingresso passato: ammesso", T.tetto_permette([], D, 300))
    check("conti in punti base: 6% = 600", T.TETTO_BPS == 600 and T.GIORNI_TETTO == 360)

    section("tetto dentro la simulazione")
    M = mercato(INIZIO, dt.date(2022, 12, 30), 100.0)
    e1 = dt.date(2020, 1, 2)
    permessi = {e1, dt.date(2020, 6, 1), dt.date(2020, 9, 1), dt.date(2020, 12, 1), dt.date(2021, 1, 4)}
    es = T.simula(M, 3, 0.03, True, permessi)
    check("secondo ingresso (3% + 3% = 6% esatto): ammesso",
          [o.ingresso for o in es.operazioni][:2] == [e1, dt.date(2020, 6, 1)], str([o.ingresso for o in es.operazioni]))
    check("terzo e quarto tentativo (9%): bloccati", es.bloccati == [dt.date(2020, 9, 1), dt.date(2020, 12, 1)], str(es.bloccati))
    check("...e non recuperati con un premio piu' piccolo: il premio resta 3%", all(o.premio_pct == 0.03 for o in es.operazioni))
    check("quando il primo ingresso esce dalla finestra si rientra (2021-01-04: 368 giorni dopo)",
          [o.ingresso for o in es.operazioni] == [e1, dt.date(2020, 6, 1), dt.date(2021, 1, 4)], str([o.ingresso for o in es.operazioni]))
    senza = T.simula(M, 3, 0.03, False, permessi)
    check("versione B, stesso calendario, nessun tetto: quattro ingressi, nessuno bloccato",
          [o.ingresso for o in senza.operazioni] == [e1, dt.date(2020, 6, 1), dt.date(2020, 9, 1), dt.date(2020, 12, 1)]
          and senza.bloccati == [], str([o.ingresso for o in senza.operazioni]))

    r1 = T.simula(M, 3, 0.03, True, None)                                  # regola 1 con un premio che il tetto non regge
    date = [o.ingresso for o in r1.operazioni]
    soglia = e1 + dt.timedelta(days=360)
    atteso = next(d for d in M.sedute if d >= soglia)
    check("regola 1: dopo due ingressi il terzo slitta alla prima seduta in cui il tetto non blocca piu'",
          date[:3] == [e1, dt.date(2020, 4, 2), atteso], str(date[:3]))
    check("...riprovando a ogni seduta: tutte le sedute fra la scadenza e il rientro sono bloccate",
          [d for d in r1.bloccati if d < atteso] == [d for d in M.sedute if dt.date(2020, 7, 2) <= d < atteso])
    gruppi = T.slittamenti(r1.bloccati, M.sedute)
    check("le sedute bloccate consecutive contano come un solo ingresso slittato",
          gruppi[0][0] == dt.date(2020, 7, 2) and gruppi[0][2] == len([d for d in M.sedute if dt.date(2020, 7, 2) <= d < atteso]))
    a3 = T.simula(M, 3, G.PREMIO["A"][3], True, None)
    check("versione A a 3 mesi (1,5%): quattro rinnovi l'anno stanno nel 6%, nessun blocco su questo calendario",
          a3.bloccati == [] and [o.ingresso for o in a3.operazioni][:5] ==
          [e1, dt.date(2020, 4, 2), dt.date(2020, 7, 2), dt.date(2020, 10, 2), dt.date(2021, 1, 1)],
          str([o.ingresso for o in a3.operazioni][:5]))
    a12 = T.simula(M, 12, G.PREMIO["A"][12], True, None)
    check("versione A a 12 mesi (3%): un rinnovo l'anno, il tetto non blocca mai",
          a12.bloccati == [] and [o.ingresso for o in a12.operazioni] ==
          [e1, dt.date(2021, 1, 1), dt.date(2021, 12, 31), dt.date(2022, 12, 30)], str([o.ingresso for o in a12.operazioni]))


# ------------------------------------------------------------- ingressi mensili, nessuno sguardo in avanti

def test_ingressi():
    section("ingresso alla prima seduta dopo la lettura mensile")
    sedute = feriali(dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    letture = {dt.date(2020, 1, 31): True, dt.date(2020, 2, 29): False, dt.date(2020, 3, 31): None,
               dt.date(2020, 4, 30): True, dt.date(2020, 5, 31): True}
    cal = T.calendario_ingressi(letture, sedute)
    check("lettura accesa a fine gennaio (venerdi' 31): ingresso lunedi' 3 febbraio, non il 31",
          dt.date(2020, 2, 3) in cal and dt.date(2020, 1, 31) not in cal, str(sorted(cal)))
    check("lettura spenta: nessun ingresso a marzo", not any(d.month == 3 for d in cal))
    check("lettura mancante (None): nessun ingresso ad aprile, fail-closed", not any(d.month == 4 for d in cal))
    check("solo le prime sedute dei mesi dopo le letture accese", cal == {dt.date(2020, 2, 3), dt.date(2020, 5, 1), dt.date(2020, 6, 1)}, str(sorted(cal)))
    senza_primo = [d for d in sedute if d != dt.date(2020, 5, 1)]
    check("se il primo giorno feriale non e' una seduta: la seduta successiva",
          dt.date(2020, 5, 4) in T.calendario_ingressi(letture, senza_primo))
    check("nessuna seduta nel mese dopo la lettura: DatoMancante",
          raises(lambda: T.calendario_ingressi({dt.date(2020, 12, 31): True}, sedute), G.DatoMancante))
    check("...anche se il mese dopo manca e ce n'e' una piu' avanti",
          raises(lambda: T.calendario_ingressi({dt.date(2020, 1, 31): True}, [d for d in sedute if d.month != 2]), G.DatoMancante))

    M = mercato(INIZIO, FINE, 100.0)
    es = T.simula(M, 3, 0.03, False, T.calendario_ingressi({dt.date(2020, 1, 31): True}, M.sedute))
    check("nella simulazione: fino al 31 gennaio il portafoglio e' l'indice, l'operazione parte il 3 febbraio",
          es.operazioni[0].ingresso == dt.date(2020, 2, 3) and all(s == 0.0 for d, s in zip(M.sedute, es.spread) if d < dt.date(2020, 2, 3)))

    section("VIX sotto la mediana a 12 mesi: solo dati fino alla fine del mese")
    archivio = feriali(dt.date(2019, 1, 1), dt.date(2021, 12, 31))
    fm = dt.date(2020, 6, 30)

    def vix(valori_dopo: float, ultimo: float = 15.0, inizio: dt.date = dt.date(2019, 1, 1)) -> G.Serie:
        righe = []
        for d in archivio:
            if d < inizio:
                continue
            righe.append((d, ultimo if d == fm else (20.0 if d < fm else valori_dopo)))
        return G.Serie("VIX", righe)

    check("ultimo VIX 15 contro mediana 20: acceso", T.vix_sotto_mediana(vix(20.0), fm, archivio) is True)
    check("NESSUNO SGUARDO IN AVANTI: valori altissimi dopo la fine del mese non cambiano la lettura",
          T.vix_sotto_mediana(vix(90.0), fm, archivio) is True)
    check("...e nemmeno valori bassissimi", T.vix_sotto_mediana(vix(1.0), fm, archivio) is True)
    check("ultimo VIX 25 contro mediana 20: spento", T.vix_sotto_mediana(vix(1.0, ultimo=25.0), fm, archivio) is False)
    check("ultimo VIX uguale alla mediana: spento (confronto stretto)", T.vix_sotto_mediana(vix(1.0, ultimo=20.0), fm, archivio) is False)
    check("finestra non intera (il VIX comincia dopo la prima seduta della finestra): None",
          T.vix_sotto_mediana(vix(20.0, inizio=dt.date(2019, 7, 2)), fm, archivio) is None)
    check("finestra intera se il VIX comincia alla prima seduta dopo t - 1 anno (2019-07-01)",
          T.vix_sotto_mediana(vix(20.0, inizio=dt.date(2019, 7, 1)), fm, archivio) is True)
    salto = G.Serie("VIX", [(d, 10.0 if d <= dt.date(2019, 6, 28) else (30.0 if d < fm else 29.0)) for d in archivio])
    check("la finestra esclude t - 1 anno e quel che viene prima: 29 contro mediana 30, non contro i 10 di prima",
          T.vix_sotto_mediana(salto, fm, archivio) is True)
    vecchio = G.Serie("VIX", [(d, 20.0) for d in archivio if d <= dt.date(2020, 6, 19)])
    check("ultimo VIX piu' vecchio di 7 giorni: DatoMancante, non un valore di ripiego",
          raises(lambda: T.vix_sotto_mediana(vecchio, fm, archivio), G.DatoMancante))

    section("letture mensili delle regole 2, 3, 4")
    sed = feriali(dt.date(1989, 1, 2), dt.date(2026, 1, 30))
    piatto = G.Serie("VIX", [(d, 20.0) for d in sed if d >= dt.date(1990, 1, 2)])
    basso = G.Serie("VIX", [(d, 12.0 if (d.year, d.month) == (2000, 6) else 20.0) for d in sed if d >= dt.date(1990, 1, 2)])

    def mesi(composito: dict, faber: dict, salta=None) -> list:
        out, fm_ = [], dt.date(1989, 12, 31)
        while fm_ <= dt.date(2025, 12, 31):
            if fm_ != salta:
                out.append(SimpleNamespace(fm=fm_, composito5=composito.get(fm_, 0), faber=faber.get(fm_, False)))
            fm_ = T.E.fine_mese(fm_ + dt.timedelta(days=1))
        return out

    g00, l00, d90 = dt.date(2000, 6, 30), dt.date(2000, 7, 31), dt.date(1990, 6, 30)
    L = T.letture_mensili(mesi({g00: 3, l00: 4, d90: 5, dt.date(2001, 1, 31): None, dt.date(2001, 2, 28): 2},
                               {g00: True, dt.date(2001, 1, 31): None}), basso, sed)
    check("432 letture per regola, dal 1989-12-31 al 2025-11-30",
          all(len(L[r]) == 432 and min(L[r]) == dt.date(1989, 12, 31) and max(L[r]) == dt.date(2025, 11, 30) for r in (2, 3, 4)))
    check("regola 2: composito 3 acceso, 4 acceso, 2 spento", L[2][g00] is True and L[2][l00] is True and L[2][dt.date(2001, 2, 28)] is False)
    check("regola 3: composito 3 e VIX sotto la mediana: accesa", L[3][g00] is True)
    check("regola 3: composito 4 ma VIX non sotto la mediana: spenta", L[3][l00] is False)
    check("regola 3 nel 1990: composito acceso ma finestra del VIX non intera: None, nessun ingresso", L[2][d90] is True and L[3][d90] is None)
    check("composito mancante: regole 2 e 3 None (fail-closed), non il mese prima",
          L[2][dt.date(2001, 1, 31)] is None and L[3][dt.date(2001, 1, 31)] is None)
    check("Faber: acceso, spento, mancante", L[4][g00] is True and L[4][l00] is False and L[4][dt.date(2001, 1, 31)] is None)
    check("VIX piatto: regola 3 mai accesa (confronto stretto)",
          not any(x is True for x in T.letture_mensili(mesi({g00: 5}, {}), piatto, sed)[3].values()))
    check("una fine mese non calcolata dal Test F: DatoMancante",
          raises(lambda: T.letture_mensili(mesi({}, {}, salta=dt.date(2010, 3, 31)), piatto, sed), G.DatoMancante))


# ------------------------------------------------------------- valore a scadenza

def test_valore_a_scadenza():
    section("valore a scadenza dello spread: sopra K1, fra K1 e K2, sotto K2")
    scad = dt.date(2020, 4, 2)
    for nome, finale, atteso in (("sopra K1 (100): zero", 100.0, 0.0), ("esattamente K1 (95): zero", 95.0, 0.0),
                                 ("fra K1 e K2 (85): K1 - S = 10", 85.0, 10.0), ("esattamente K2 (75): 20", 75.0, 20.0),
                                 ("sotto K2 (60): K1 - K2 = 20, non di piu'", 60.0, 20.0)):
        M = mercato(INIZIO, FINE, lambda d, f=finale: 100.0 if d < scad else f)
        o = T.simula(M, 3, 0.03, False, {INIZIO}).operazioni[0]
        check(nome, near(o.valore_scadenza, atteso, 1e-12) and near(o.incasso, o.n * atteso, 1e-12) and o.s_scadenza == finale,
              str(o.valore_scadenza))
    M = mercato(INIZIO, FINE, lambda d: 100.0 if d < scad else 60.0)
    o = T.simula(M, 3, 0.03, False, {INIZIO}).operazioni[0]
    check("guadagno massimo = 20% x parte coperta del portafoglio di ingresso", near(o.incasso / o.portafoglio, 0.20 * o.coperta, 1e-12))
    for incl, q in ((0.0, 0.02), (10.0, 0.02), (5.0, 0.0)):
        ov = T.simula(M, 3, 0.03, False, {INIZIO}, inclinazione=incl, q=q).operazioni[0]
        check("inclinazione {} e q = {}: cambia il prezzo, non il valore a scadenza".format(incl, q),
              near(ov.valore_scadenza, 20.0, 1e-12) and ov.prezzo != o.prezzo)
    piu, meno = (T.simula(M, 3, 0.03, False, {INIZIO}, inclinazione=i).operazioni[0].prezzo for i in (0.0, 10.0))
    check("piu' inclinazione = spread meno caro = piu' spread con lo stesso premio", piu > o.prezzo > meno)


# ------------------------------------------------------------- limite alla parte coperta (descrittivo)

def test_limite_coperta():
    section("limite alla parte coperta: predefinito nessuno; al 100% il premio speso e' quello effettivo")
    scad = dt.date(2020, 4, 2)
    Mb = mercato(INIZIO, FINE, lambda d: 100.0 if d < scad else 60.0, vix=10.0)      # VIX basso: lo spread costa poco
    libero = T.simula(Mb, 3, 0.03, False, {INIZIO})
    nessuno = T.simula(Mb, 3, 0.03, False, {INIZIO}, limite_coperta=None)
    lim = T.simula(Mb, 3, 0.03, False, {INIZIO}, limite_coperta=1.0)
    o, ol = libero.operazioni[0], lim.operazioni[0]
    check("senza parametro e con None: stessa serie", libero.valori == nessuno.valori)
    check("senza limite la parte coperta supera il 100%", o.coperta > 1.0, str(o.coperta))
    check("IL LIMITE MORDE: numero di spread = portafoglio / chiusura = 1", near(ol.n, 1.0, 1e-12) and ol.n < o.n, str(ol.n))
    check("...parte coperta esattamente 100%", ol.coperta == 1.0 and near(ol.n * ol.s0 / ol.portafoglio, 1.0, 1e-12))
    check("...premio effettivo = numero x prezzo, minore del 3%",
          near(ol.premio, ol.n * ol.prezzo, 1e-12) and ol.premio < 3.0 and near(ol.premio_pct, ol.prezzo / 100.0, 1e-12)
          and ol.premio_pct < 0.03, "{} {}".format(ol.premio, ol.premio_pct))
    check("...stesso prezzo e stessi strike della cella senza limite", ol.prezzo == o.prezzo and (ol.k1, ol.k2) == (o.k1, o.k2))
    check("...il resto resta nell'indice: nel giorno di ingresso il portafoglio vale 100", near(lim.valori[0], 100.0, 1e-12))
    check("...a scadenza sotto K2 incassa 20 punti per uno spread: 20% del portafoglio di ingresso",
          near(ol.incasso, 20.0, 1e-12) and near(ol.incasso / ol.portafoglio, 0.20, 1e-12), str(ol.incasso))
    j = Mb.sedute.index(scad)
    check("...portafoglio a scadenza = quote rimaste x 60 + 20", near(lim.valori[j], (1.0 - ol.premio / 100.0) * 60.0 + 20.0, 1e-10))
    check("...contabilita' coerente con premi e incassi", near(T.scostamento_contabile(Mb, lim, T.senza_protezione(Mb)), 0.0, 1e-10))
    Ma = mercato(INIZIO, FINE, 100.0, vix=40.0)                                      # VIX alto: lo spread costa piu' del 3%
    a, b = T.simula(Ma, 3, 0.03, False, None), T.simula(Ma, 3, 0.03, False, None, limite_coperta=1.0)
    check("IL LIMITE NON MORDE: parte coperta sotto il 100%, serie identica a quella senza limite",
          all(o_.coperta < 1.0 for o_ in a.operazioni) and a.valori == b.valori
          and [o_.n for o_ in a.operazioni] == [o_.n for o_ in b.operazioni])
    check("...e il premio resta il 3% pieno", all(o_.premio_pct == 0.03 for o_ in b.operazioni))
    mezzo = T.simula(Mb, 3, 0.03, False, {INIZIO}, limite_coperta=0.5).operazioni[0]
    check("limite al 50%: mezzo spread, meta' premio", near(mezzo.n, 0.5, 1e-12) and near(mezzo.premio, 0.5 * ol.premio, 1e-12))


# ------------------------------------------------------------- misure

def test_misure():
    section("ribassi: i tre peggiori del portafoglio senza protezione, misurati sulle stesse date")
    sedute = feriali(dt.date(2020, 1, 1), dt.date(2020, 1, 14))
    base = [100.0, 120.0, 60.0, 130.0, 78.0, 140.0, 98.0, 150.0, 140.0, 151.0]
    prot = [100.0, 120.0, 90.0, 130.0, 91.0, 140.0, 98.0, 150.0, 100.0, 151.0]
    pos = {d: i for i, d in enumerate(sedute)}
    tre = T.tre_ribassi(sedute, base)
    check("tre episodi, dal piu' profondo: -50%, -40%, -30%",
          [(pos[a], pos[b]) for a, b, _ in tre] == [(1, 2), (3, 4), (5, 6)] and
          all(near(d, x, 1e-12) for (_a, _b, d), x in zip(tre, (-0.5, -0.4, -0.3))), str(tre))
    check("un ribasso sotto il 15% non entra (150 -> 140)", all(pos[a] != 7 for a, _b, _d in tre))
    media, rid, prof = T.riduzioni(tre, prot, pos)
    check("profondita' con protezione = valore al fondo / valore al picco - 1, sulle date del non protetto",
          near(prof[0], -0.25, 1e-12) and near(prof[1], -0.30, 1e-12) and near(prof[2], -0.30, 1e-12), str(prof))
    check("riduzioni: 1 - 25/50 = 50%, 1 - 30/40 = 25%, 1 - 30/30 = 0",
          near(rid[0], 0.5, 1e-12) and near(rid[1], 0.25, 1e-12) and near(rid[2], 0.0, 1e-12), str(rid))
    check("media semplice delle tre riduzioni = 25%", near(media, 0.25, 1e-12), str(media))
    check("...che non e' il rapporto fra le medie (1 - 28,33/40 = 29,2%)", abs(media - (1 - (0.25 + 0.30 + 0.30) / (0.5 + 0.4 + 0.3))) > 0.03)
    check("il ribasso proprio del protetto in altre date (150 -> 100) non entra nella riduzione",
          near(T.ribasso_massimo(prot)[0], 100.0 / 150.0 - 1.0, 1e-12) and near(media, 0.25, 1e-12))
    peggio = [100.0, 120.0, 54.0, 130.0, 78.0, 140.0, 98.0, 150.0, 140.0, 151.0]
    check("una protezione che peggiora il ribasso da' una riduzione negativa (1 - 55/50 = -10%)",
          near(T.riduzioni(tre, peggio, pos)[1][0], -0.1, 1e-12))
    check("portafoglio identico: riduzione zero", near(T.riduzioni(tre, base, pos)[0], 0.0, 1e-12))
    check("meno di tre ribassi: DatoMancante", raises(lambda: T.tre_ribassi(sedute[:5], base[:5]), G.DatoMancante))

    section("ribasso massimo, rendimento annuo, costo")
    dd = T.ribasso_massimo(base)
    check("ribasso massimo: 120 -> 60 = -50%", near(dd[0], -0.5, 1e-12) and (dd[1], dd[2]) == (1, 2), str(dd))
    check("ribasso massimo dentro una finestra", near(T.ribasso_massimo(base, 3, 6)[0], -0.4, 1e-12))
    check("serie sempre crescente: zero", T.ribasso_massimo([1.0, 2.0, 3.0])[0] == 0.0)
    check("da 100 a 200 in 365 giorni: +100% l'anno", near(T.rendimento_annuo(200.0, 365), 1.0, 1e-12))
    check("da 100 a 200 in 730 giorni: radice di 2 - 1", near(T.rendimento_annuo(200.0, 730), 2 ** 0.5 - 1, 1e-12))
    check("giorni del periodo: di calendario fra prima e ultima seduta", T.giorni_periodo([dt.date(1990, 1, 2), dt.date(2025, 12, 31)]) == 13147)

    section("misura completa su un caso a mano")
    M = mercato(INIZIO, FINE, 100.0)
    M.sedute = M.sedute[:10]
    M.chiusura = dict(M.chiusura)
    for d, v in zip(M.sedute, base):
        M.chiusura[d] = v
    es = T.Esito(prot, [0.0] * 10, [], [])
    x = T.misura(M, es, base, T.tre_ribassi(M.sedute, base), {d: i for i, d in enumerate(M.sedute)})
    check("costo = rendimento senza - rendimento con, in punti: zero se i valori finali coincidono", near(x.costo_punti, 0.0, 1e-12))
    es2 = T.Esito([v * 0.9 if i == 9 else v for i, v in enumerate(prot)], [0.0] * 10, [], [])
    x2 = T.misura(M, es2, base, T.tre_ribassi(M.sedute, base), {d: i for i, d in enumerate(M.sedute)})
    g = T.giorni_periodo(M.sedute)
    check("costo positivo se il protetto finisce sotto, uguale alla differenza dei rendimenti annui x 100",
          x2.costo_punti > 0 and near(x2.costo_punti, 100 * (T.rendimento_annuo(151.0, g) - T.rendimento_annuo(135.9, g)), 1e-9))
    check("nessuna operazione: premio annuo zero, zero operazioni", x.premio_annuo == 0.0 and x.operazioni == 0 and x.oltre_100 == 0)

    section("premio annuo speso e parte coperta")
    M = mercato(INIZIO, FINE, 100.0, vix=10.0)
    es = T.simula(M, 3, 0.03, False, None)
    base = T.senza_protezione(M)
    tre_finti = [(M.sedute[1], M.sedute[2], -0.5)] * 3
    x = T.misura(M, es, base, tre_finti, {d: i for i, d in enumerate(M.sedute)})
    anni = T.giorni_periodo(M.sedute) / 365.0
    check("premio annuo = somma delle percentuali / anni del periodo", near(x.premio_annuo, 0.03 * len(es.operazioni) / anni, 1e-12))
    check("VIX basso: parte coperta oltre il 100%, contata e senza limite",
          x.oltre_100 == len(es.operazioni) and x.coperta_max > 1.0 and near(x.coperta_max, max(o.coperta for o in es.operazioni), 1e-12))
    check("numero di spread x chiusura / portafoglio = parte coperta",
          all(near(o.n * o.s0 / o.portafoglio, o.coperta, 1e-12) for o in es.operazioni))

    section("guadagno delle put fra un massimo e un fondo")
    scad = dt.date(2020, 4, 2)
    M = mercato(INIZIO, FINE, lambda d: 100.0 if d < scad else 60.0)
    es = T.simula(M, 3, 0.03, False, {INIZIO, scad})
    pos = {d: i for i, d in enumerate(M.sedute)}
    o1, o2 = es.operazioni
    P, F = dt.date(2020, 1, 10), dt.date(2020, 5, 1)
    atteso = (o1.incasso + es.spread[pos[F]] - es.spread[pos[P]] - o2.premio) / es.valori[pos[P]]
    check("incasso della prima + valore della seconda in F - valore della prima in P - premio della seconda, sul portafoglio in P",
          near(T.guadagno_put(es, pos, P, F), atteso, 1e-12) and T.guadagno_put(es, pos, P, F) > 0)
    check("il premio pagato prima del massimo non entra", near(
        T.guadagno_put(es, pos, P, dt.date(2020, 3, 2)), (es.spread[pos[dt.date(2020, 3, 2)]] - es.spread[pos[P]]) / es.valori[pos[P]], 1e-12))
    check("nessuna operazione: guadagno zero", T.guadagno_put(T.simula(M, 3, 0.03, False, set()), pos, P, F) == 0.0)


# ------------------------------------------------------------- verdetto

def test_verdetto():
    section("verdetto: casi limite delle soglie (numeri non arrotondati)")
    terzo, quinto = 1.0 / 3.0, 1.0 / 5.0
    check("riduzione esattamente 1/3 e costo esattamente 1,5: REGGE", T.verdetto(terzo, 1.5) == "REGGE")
    check("riduzione appena sotto 1/3: INCONCLUSIVO", T.verdetto(terzo - 1e-12, 1.5) == "INCONCLUSIVO")
    check("0,3333 non e' un terzo: INCONCLUSIVO", T.verdetto(0.3333, 0.0) == "INCONCLUSIVO")
    check("costo appena sopra 1,5 con riduzione 1/3: INCONCLUSIVO", T.verdetto(terzo, 1.5 + 1e-12) == "INCONCLUSIVO")
    check("riduzione esattamente 1/5: non e' «meno di un quinto», INCONCLUSIVO", T.verdetto(quinto, 1.5) == "INCONCLUSIVO")
    check("riduzione appena sotto 1/5: NON REGGE", T.verdetto(quinto - 1e-12, 0.0) == "NON REGGE")
    check("costo esattamente 3: non e' «piu' di 3», INCONCLUSIVO", T.verdetto(terzo, 3.0) == "INCONCLUSIVO")
    check("costo appena sopra 3: NON REGGE anche con una riduzione alta", T.verdetto(0.9, 3.0 + 1e-12) == "NON REGGE")
    check("riduzione 1/5 e costo 3 esatti: INCONCLUSIVO", T.verdetto(quinto, 3.0) == "INCONCLUSIVO")
    check("NON REGGE basta una condizione: riduzione bassa con costo negativo", T.verdetto(0.1, -1.0) == "NON REGGE")
    check("costo negativo e riduzione alta: REGGE", T.verdetto(0.5, -0.2) == "REGGE")
    check("riduzione negativa: NON REGGE", T.verdetto(-0.05, 0.3) == "NON REGGE")
    check("riduzione alta, costo fra 1,5 e 3: INCONCLUSIVO", T.verdetto(0.6, 2.0) == "INCONCLUSIVO")
    check("soglie della pre-registrazione", (T.RIDUZIONE_REGGE, T.RIDUZIONE_NON_REGGE, T.COSTO_REGGE, T.COSTO_NON_REGGE) == (terzo, quinto, 1.5, 3.0))


def test_modulo_alternativo():
    section("confronto con un'altra copia del composito: caricata da file, senza toccare quella del repo")
    import tempfile
    with tempfile.TemporaryDirectory() as cartella:
        f = Path(cartella) / "copia.py"
        f.write_text("\n".join(["import sys", "from dataclasses import dataclass", "sys.path.insert(0, 'cartella-della-copia')",
                                "", "@dataclass", "class Mese:", "    fm: int", "", "def calcola_mesi():",
                                "    return [Mese(1)]", ""]), encoding="utf-8")
        prima = list(sys.path)
        mod = T.carica_modulo(str(f))
        check("il modulo si carica e le sue dataclass funzionano", mod.calcola_mesi()[0].fm == 1)
        check("ha un nome suo: non sostituisce test_f", mod.__name__ == "test_f_alternativo" and sys.modules.get("test_f") is not mod)
        check("il path che la copia aggiunge viene tolto", sys.path == prima)
    check("opzione senza percorso: errore, non l'esecuzione predefinita", raises(lambda: T.main(["--confronto-composito"]), SystemExit))
    check("le due finestre in evidenza: intorno a 2008-02 e a 2020-01",
          dt.date(2008, 2, 29) in T.MESI_IN_EVIDENZA and dt.date(2020, 1, 31) in T.MESI_IN_EVIDENZA)


def test_costanti():
    section("griglie e conto delle serie")
    check("celle del verdetto: A regola 3 x 12 mesi, B regola 3 x 3 mesi", T.CELLA_VERDETTO == {"A": (3, 12), "B": (3, 3)})
    check("32 combinazioni", len(T.VERSIONI) * len(T.REGOLE) * len(G.SCADENZE_MESI) == 32)
    check("cinque varianti (principale + 4 sensibilita'): 160 serie", len(T.VARIANTI) == 5 and 32 * len(T.VARIANTI) == 160)
    check("la principale: inclinazione +5, q = 2%, valutazione a modello", T.VARIANTI[0][1:] == (5.0, 0.02, "modello"))
    check("le sensibilita' cambiano una cosa alla volta",
          [v[1:] for v in T.VARIANTI[1:]] == [(0.0, 0.02, "modello"), (10.0, 0.02, "modello"), (5.0, 0.02, "intrinseco"), (5.0, 0.0, "modello")])
    check("letture dal 1989-12-31 al 2025-11-30", T.LETTURE == (dt.date(1989, 12, 31), dt.date(2025, 11, 30)))
    M = mercato(INIZIO, FINE, 100.0)
    tutte = T.esegui(M, {1: None, 2: set(), 3: set(), 4: set()}, T.VARIANTI[0])
    check("esegui: 32 celle, il tetto solo nella versione A, i premi della pre-registrazione",
          len(tutte) == 32 and tutte[("A", 1, 3)].operazioni[0].premio_pct == 0.015 and tutte[("B", 1, 3)].operazioni[0].premio_pct == 0.03
          and all(tutte[(v, 1, m)].operazioni[0].premio_pct == 0.03 for v in "AB" for m in (6, 9, 12)))
    check("a 12 mesi A e B danno la stessa serie", tutte[("A", 1, 12)].valori == tutte[("B", 1, 12)].valori)
    check("numeri con la virgola, zero senza segno meno", T.it(-0.0001, "+.2f") == "+0,00" and T.it(-1.234, "+.2f") == "-1,23" and T.p(0.1234, 1) == "12,3%")


test_contabilita()
test_una_alla_volta()
test_tetto()
test_ingressi()
test_valore_a_scadenza()
test_limite_coperta()
test_misure()
test_verdetto()
test_modulo_alternativo()
test_costanti()

if __name__ == "__main__":
    sys.exit(report("ALL TEST-G SIMULATION TESTS PASSED"))
