"""Test F (segnali precoci), fermata 2: segnali, composito, misure e verdetto come pre-registrati
(`2026-09-30_preregistrazione_test_f.md`, ADR-060..067). Nessun parametro scelto qui.

Dati solo da `market_data.api`. Point-in-time: a ogni fine mese t si usano solo dati pubblicati entro t — versioni
ALFRED per PERMIT (dal 1999-08-31) e ICSA (dal 2009-05-31), ritardi dichiarati altrove (ADR-063, ADR-066).

    python backtest/drawdown_alpha/test_f.py            # stampa il materiale del referto (markdown)
"""
from __future__ import annotations

import datetime as dt
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from market_data import api

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import eventi_f as E  # noqa: E402

SEME = 20261001                       # seme fisso dei falsi eventi, scritto nella pre-registrazione
N_FALSI = 1000
INIZIO_MESI = dt.date(1967, 1, 31)    # robustezza a 4 segnali dal 1967
FINE_MESI = dt.date(2025, 12, 31)
PRIMA_VERSIONE = {"PERMIT": dt.date(1999, 8, 17), "ICSA": dt.date(2009, 5, 28)}
RITARDO_GSW = 11                      # giorni (ADR-063)
MAX_GIORNI_CURVA = 7                  # riga GSW mancante (NA nei festivi): ultimo giorno valido precedente, non più vecchio di così (ADR-071)
RITARDO_ICSA = 5                      # giorni: giovedì per la settimana chiusa il sabato prima
GIORNI_BILL = 91                      # buono a 13 settimane
SEGNALI = ("ebp", "ntfs", "permit", "icsa", "wti")


# ------------------------------------------------------------------ calendario e aritmetica delle date

def fine_mese(d: dt.date) -> dt.date:
    return E.fine_mese(d)


def mesi_prima(d: dt.date, mesi: int) -> dt.date:
    return E.mesi_prima(d, mesi)


def primo_del_mese(d: dt.date) -> dt.date:
    return d.replace(day=1)


def fini_mese(da: dt.date, a: dt.date) -> list[dt.date]:
    out, d = [], fine_mese(da)
    while d <= a:
        out.append(d)
        d = fine_mese(d + dt.timedelta(days=1))
    return out


def mesi_fra(a: dt.date, b: dt.date) -> int:
    """Mesi di calendario da a a b (b − a), positivi se b viene dopo."""
    return (b.year - a.year) * 12 + (b.month - a.month)


def indice_mese(fm: dt.date) -> int:
    return fm.year * 12 + fm.month - 1


# ------------------------------------------------------------------ curva GSW e tasso a 3 mesi

def svensson_y(n: float, b0, b1, b2, b3, t1, t2) -> float:
    a = (1 - math.exp(-n / t1)) / (n / t1)
    v = b0 + b1 * a + b2 * (a - math.exp(-n / t1))
    if b3 and t2:
        c = (1 - math.exp(-n / t2)) / (n / t2)
        v += b3 * (c - math.exp(-n / t2))
    return v


def forward_3m_fra_18m(riga) -> float:
    p = [riga[k] for k in ("BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2")]
    p = [0.0 if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v) for v in p]
    return (1.75 * svensson_y(1.75, *p) - 1.5 * svensson_y(1.5, *p)) / 0.25


def y_gsw(riga, n: float) -> float:
    p = [riga[k] for k in ("BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2")]
    p = [0.0 if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v) for v in p]
    return svensson_y(n, *p)


def dtb3_continuo(sconto_pct: float, giorni: int = GIORNI_BILL) -> float:
    """Tasso di sconto (per cento, base 360) → rendimento zero-coupon a capitalizzazione continua (per cento, base 365):
    prezzo P = 1 − d·giorni/360 (TreasuryDirect); y = (365/giorni)·ln(1/P)."""
    p = 1.0 - sconto_pct / 100.0 * giorni / 360.0
    return 100.0 * (365.0 / giorni) * math.log(1.0 / p)


# ------------------------------------------------------------------ serie

class Dati:
    def __init__(self):
        self.righe = E.chiusure()                                     # [(data, chiusura)] GSPC.INDX
        self.date_sedute = [d for d, _ in self.righe]
        self.ebp = {d.date(): v for d, v in zip(*(lambda df: (df["date"], df["ebp"]))(api.ebp()))}
        g = api.gsw()
        self.gsw = [r for r in g.to_dict("records")]
        for r in self.gsw:
            r["date"] = r["date"].date()
        self.dtb3 = self._serie("DTB3")
        self.permit_oggi = self._serie("PERMIT")
        self.icsa_oggi = self._serie("ICSA")
        self.wti = self._serie("WTISPLC")
        self.gs10 = self._serie("GS10")
        self.tb3ms = self._serie("TB3MS")
        self._vintage: dict[tuple[str, dt.date], list[tuple[dt.date, float]]] = {}

    @staticmethod
    def _serie(nome: str) -> list[tuple[dt.date, float]]:
        df = api.fred(nome)
        return [(d.date(), float(v)) for d, v in zip(df["date"], df["value"])]

    def vintage(self, serie: str, fm: dt.date) -> list[tuple[dt.date, float]]:
        k = (serie, fm)
        if k not in self._vintage:
            df = api.fred(serie, al_giorno=fm)
            self._vintage[k] = [(d.date(), float(v)) for d, v in zip(df["date"], df["value"])]
        return self._vintage[k]

    def chiusura_mensile(self, fm: dt.date) -> float | None:
        i = self._ultima_seduta(fm)
        return self.righe[i][1] if i is not None else None

    def _ultima_seduta(self, giorno: dt.date) -> int | None:
        import bisect
        i = bisect.bisect_right(self.date_sedute, giorno) - 1
        return i if i >= 0 else None


def ultimo_prima(serie: list[tuple[dt.date, float]], giorno: dt.date) -> tuple[dt.date, float] | None:
    import bisect
    date = [d for d, _ in serie]
    i = bisect.bisect_right(date, giorno) - 1
    return serie[i] if i >= 0 else None


# ------------------------------------------------------------------ segnali a fine mese

@dataclass
class Lettura:
    acceso: bool | None           # None = segnale non disponibile a quella data
    valore: float | None = None   # per le tabelle descrittive
    dati: str = ""                # quali dati (e di quando) ha usato la lettura


def segnale_ebp(D: Dati, fm: dt.date) -> Lettura:
    mese = primo_del_mese(mesi_prima(fm, 1))
    v = D.ebp.get(mese)
    if v is None or math.isnan(v):
        prima = [d for d in D.ebp if d < mese]
        if not prima:
            return Lettura(None, None, "EBP non ancora esistente")
        ultimo = max(prima)
        return Lettura(None, None, "EBP di {} non pubblicato (ultimo nel file: {} = {:+.3f})".format(
            mese.strftime("%Y-%m"), ultimo.strftime("%Y-%m"), D.ebp[ultimo]))
    return Lettura(v > 0, v, "EBP di {}".format(mese.strftime("%Y-%m")))


def _riga_valida(r) -> bool:
    b = r.get("BETA0")
    return b is not None and not (isinstance(b, float) and math.isnan(b))


def riga_gsw(gsw: list[dict], limite: dt.date, max_giorni: int = MAX_GIORNI_CURVA) -> dict | None:
    """L'ultima riga **valida** della curva GSW con data <= `limite`. Il file della Fed ha una riga anche nei giorni
    festivi, con `NA` al posto dei parametri: in quel caso vale l'ultimo giorno valido precedente, mai uno successivo,
    e non più vecchio di `max_giorni` giorni rispetto a `limite` (altrimenti None: il segnale resta mancante).
    Correzione di un errore di lettura, ADR-071: prima si prendeva la riga del giorno anche se era `NA`."""
    riga = None
    for r in gsw:                                                     # ordinato per data
        if r["date"] > limite:
            break
        if _riga_valida(r):
            riga = r
    if riga is None or (limite - riga["date"]).days > max_giorni:
        return None
    return riga


def segnale_ntfs(D: Dati, fm: dt.date, tasso: str = "dtb3") -> Lettura:
    limite = fm - dt.timedelta(days=RITARDO_GSW)
    riga = riga_gsw(D.gsw, limite)
    if riga is None:
        return Lettura(None)
    f = forward_3m_fra_18m(riga)
    if tasso == "gsw":
        y3 = y_gsw(riga, 0.25)
        dati = "curva GSW del {}: forward {:.3f}, y(0,25) {:.3f}".format(riga["date"], f, y3)
    else:
        b = ultimo_prima(D.dtb3, riga["date"])
        if b is None or b[0] < riga["date"] - dt.timedelta(days=7):
            return Lettura(None)
        y3 = dtb3_continuo(b[1])
        dati = "curva GSW del {}: forward {:.3f}; DTB3 del {}: {:.2f} sconto → {:.3f} continuo".format(
            riga["date"], f, b[0], b[1], y3)
    s = f - y3
    return Lettura(s < 0, s, dati)


def _osservazioni_permit(D: Dati, fm: dt.date) -> list[tuple[dt.date, float]]:
    ultimo = primo_del_mese(mesi_prima(fm, 1))                       # il mese t esce il 12° giorno lavorativo di t+1
    serie = D.vintage("PERMIT", fm) if fm >= PRIMA_VERSIONE["PERMIT"] else D.permit_oggi
    return [(d, v) for d, v in serie if d <= ultimo]


def segnale_permit(D: Dati, fm: dt.date) -> Lettura:
    oss = _osservazioni_permit(D, fm)
    if len(oss) < 12:
        return Lettura(None)
    v = [x for _, x in oss]
    m3, m12 = statistics.fmean(v[-3:]), statistics.fmean(v[-12:])
    versione = "versione ALFRED al {}".format(fm) if fm >= PRIMA_VERSIONE["PERMIT"] else "serie di oggi"
    return Lettura(m3 < m12, m3 / m12 - 1, "PERMIT fino a {} ({}): media 3 mesi {:.0f}, 12 mesi {:.0f}".format(
        oss[-1][0].strftime("%Y-%m"), versione, m3, m12))


def _osservazioni_icsa(D: Dati, fm: dt.date) -> list[tuple[dt.date, float]]:
    ultimo = fm - dt.timedelta(days=RITARDO_ICSA)
    serie = D.vintage("ICSA", fm) if fm >= PRIMA_VERSIONE["ICSA"] else D.icsa_oggi
    return [(d, v) for d, v in serie if d <= ultimo]


def segnale_icsa(D: Dati, fm: dt.date) -> Lettura:
    oss = _osservazioni_icsa(D, fm)
    if len(oss) < 52:
        return Lettura(None)
    v = [x for _, x in oss]
    m4, m52 = statistics.fmean(v[-4:]), statistics.fmean(v[-52:])
    versione = "versione ALFRED al {}".format(fm) if fm >= PRIMA_VERSIONE["ICSA"] else "serie di oggi"
    return Lettura(m4 > m52, m4 / m52 - 1, "ICSA fino alla settimana del {} ({}): media 4 sett. {:.0f}, 52 sett. {:.0f}".format(
        oss[-1][0], versione, m4, m52))


def segnale_wti(D: Dati, fm: dt.date) -> Lettura:
    per_mese = getattr(D, "_wti_mese", None)
    if per_mese is None:
        per_mese = D._wti_mese = {d: v for d, v in D.wti}
    mese = primo_del_mese(mesi_prima(fm, 1))
    v = per_mese.get(mese)
    if v is None:
        return Lettura(None)
    prima = [per_mese.get(primo_del_mese(mesi_prima(mese, k))) for k in range(1, 37)]
    if any(x is None for x in prima):
        return Lettura(None)
    massimo = max(prima)
    return Lettura(v > massimo, v / massimo - 1, "WTISPLC di {}: {:.2f}; massimo dei 36 mesi precedenti {:.2f}".format(
        mese.strftime("%Y-%m"), v, massimo))


def segnale_curva_10a_3m(D: Dati, fm: dt.date) -> Lettura:
    """Confronto descrittivo con il Test A: GS10 − TB3MS (medie mensili H.15) del mese t−1, acceso se < 0."""
    mese = primo_del_mese(mesi_prima(fm, 1))
    a = dict(D.gs10).get(mese)
    b = dict(D.tb3ms).get(mese)
    if a is None or b is None:
        return Lettura(None)
    return Lettura(a - b < 0, a - b)


def faber(D: Dati, fm: dt.date, chiusure_mensili: dict[dt.date, float]) -> Lettura:
    mesi = [fine_mese(mesi_prima(fm, k)) for k in range(0, 10)]
    v = [chiusure_mensili.get(m) for m in mesi]
    if any(x is None for x in v):
        return Lettura(None)
    media = statistics.fmean(v)
    return Lettura(v[0] < media, v[0] / media - 1)


@dataclass
class Mese:
    fm: dt.date
    letture: dict                 # nome → Lettura
    composito5: int | None
    composito4: int | None
    composito5_gsw: int | None
    faber: bool | None
    curva: bool | None
    chiusura: float | None


def calcola_mesi(D: Dati, da: dt.date = INIZIO_MESI, a: dt.date = FINE_MESI, log=print) -> list[Mese]:
    chiusure_mensili = {fm: D.chiusura_mensile(fm) for fm in fini_mese(dt.date(1960, 1, 31), dt.date(2026, 9, 30))}
    out = []
    for fm in fini_mese(da, a):
        letture = {"ebp": segnale_ebp(D, fm), "ntfs": segnale_ntfs(D, fm), "permit": segnale_permit(D, fm),
                   "icsa": segnale_icsa(D, fm), "wti": segnale_wti(D, fm), "ntfs_gsw": segnale_ntfs(D, fm, "gsw")}
        cinque = [letture[s].acceso for s in SEGNALI]
        quattro = [letture[s].acceso for s in SEGNALI if s != "ebp"]
        gsw5 = [letture[s].acceso for s in ("ebp", "ntfs_gsw", "permit", "icsa", "wti")]
        c5 = sum(cinque) if all(x is not None for x in cinque) else None
        c4 = sum(quattro) if all(x is not None for x in quattro) else None
        c5g = sum(gsw5) if all(x is not None for x in gsw5) else None
        fb = faber(D, fm, chiusure_mensili)
        cv = segnale_curva_10a_3m(D, fm)
        out.append(Mese(fm, letture, c5, c4, c5g, fb.acceso, cv.acceso, chiusure_mensili.get(fm)))
        if fm.month == 12 and fm.year % 10 == 0:
            log("  calcolato fino al", fm)
    return out


# ------------------------------------------------------------------ eventi e finestre

@dataclass
class EventoF:
    nome: str
    massimo_data: dt.date
    massimo: float
    soglia_data: dt.date          # −15%
    dieci_data: dt.date           # −10%
    fondo_data: dt.date
    profondita: float
    recessione: tuple | None
    inizio_finestra: dt.date      # massimo − 24 mesi
    fine_finestra: dt.date        # −10%


def data_dieci(righe, massimo_data: dt.date, massimo: float) -> dt.date:
    i = next(i for i, (d, _) in enumerate(righe) if d == massimo_data)
    return next(d for d, v in righe[i + 1:] if v <= 0.90 * massimo)


def eventi_test(righe, rec, mese_dopo_il_picco=False, fondi_1980=False, senza_ebp=False) -> list[EventoF]:
    out = []
    for ev in E.eventi_12_mesi(righe):
        r = E.recessione_associata(ev, rec, mese_dopo_il_picco=mese_dopo_il_picco)
        if E.stato(ev, r, senza_ebp=senza_ebp) != "verdetto":
            continue
        out.append(EventoF(ev.massimo_data.isoformat(), ev.massimo_data, ev.massimo, ev.soglia_data,
                           data_dieci(righe, ev.massimo_data, ev.massimo), ev.fondo_data, ev.profondita, r,
                           mesi_prima(ev.massimo_data, 24), data_dieci(righe, ev.massimo_data, ev.massimo)))
    if fondi_1980:
        a = [e for e in out if e.massimo_data.year == 1980]
        if len(a) == 2:
            primo, secondo = a
            fuso = EventoF("1980 fusi (" + primo.nome + " + " + secondo.nome + ")", primo.massimo_data, primo.massimo,
                           primo.soglia_data, secondo.dieci_data, secondo.fondo_data, min(primo.profondita, secondo.profondita),
                           primo.recessione, primo.inizio_finestra, secondo.fine_finestra)
            out = [e for e in out if e.massimo_data.year != 1980] + [fuso]
            out.sort(key=lambda e: e.massimo_data)
    return out


def mesi_in_finestra(mesi: list[Mese], ev: EventoF) -> list[Mese]:
    return [m for m in mesi if ev.inizio_finestra <= m.fm <= ev.fine_finestra]


def prima_accensione(mesi_f: list[Mese], chiave) -> dt.date | None:
    for m in mesi_f:
        if chiave(m):
            return m.fm
    return None


def colpito(mesi_f: list[Mese], composito: str, soglia: int) -> dt.date | None:
    return prima_accensione(mesi_f, lambda m: getattr(m, composito) is not None and getattr(m, composito) >= soglia)


# ------------------------------------------------------------------ episodi e falsi allarmi

@dataclass
class Episodio:
    inizio: dt.date
    fine: dt.date
    mesi_accesi: int
    esito: str                    # "evento <nome>" | "FALSO ALLARME" | "non giudicabile"


def episodi(mesi: list[Mese], composito: str, soglia: int, separazione: int = 3) -> list[tuple[dt.date, dt.date, int]]:
    accesi = [m.fm for m in mesi if getattr(m, composito) is not None and getattr(m, composito) >= soglia]
    out = []
    for fm in accesi:
        if out and mesi_fra(out[-1][1], fm) < separazione:
            out[-1] = (out[-1][0], fm, out[-1][2] + 1)
        else:
            out.append((fm, fm, 1))
    return out


def classifica_episodi_severa(eps, eventi_tutti: list[E.Evento], ultima_seduta: dt.date, inizio: str = "soglia") -> list[Episodio]:
    """Lettura severa (aggiunta dell'utente del 01-10, descrittiva): l'episodio che inizia al mese s è un falso allarme se nei
    24 mesi dopo s non **parte** un ribasso ≥ 15 %. Partenza = seduta T del −15 % (`inizio="soglia"`, la data di inizio
    dell'evento di ADR-060) oppure massimo P (`inizio="massimo"`). Un ribasso già partito a s (data di partenza ≤ s) non conta."""
    out = []
    for s, fine, n in eps:
        limite = fine_mese(mesi_prima(s, -24))
        esito = "FALSO ALLARME"
        for ev in eventi_tutti:
            partenza = ev.soglia_data if inizio == "soglia" else ev.massimo_data
            if s < partenza <= limite:
                esito = "evento {} (−15 % il {})".format(ev.massimo_data, ev.soglia_data)
                break
        if esito == "FALSO ALLARME" and mesi_fra(s, ultima_seduta) < 24:
            esito = "non giudicabile (meno di 24 mesi di dati dopo)"
        out.append(Episodio(s, fine, n, esito))
    return out


def classifica_episodi(eps, eventi_tutti: list[E.Evento], ultima_seduta: dt.date) -> list[Episodio]:
    out = []
    for inizio, fine, n in eps:
        esito = "FALSO ALLARME"
        for ev in eventi_tutti:
            if inizio <= ev.massimo_data <= fine_mese(mesi_prima(inizio, -24)) or ev.massimo_data <= inizio <= ev.fondo_data:
                esito = "evento " + ev.massimo_data.isoformat()
                break
        if esito == "FALSO ALLARME" and mesi_fra(inizio, ultima_seduta) < 24:
            esito = "non giudicabile (meno di 24 mesi di dati dopo)"
        out.append(Episodio(inizio, fine, n, esito))
    return out


# ------------------------------------------------------------------ rendimenti, sovrapposizione, falsi eventi

def rendimenti(mesi: list[Mese], chiusure: dict[dt.date, float], scelti) -> dict:
    out = {}
    for h in (3, 6, 12):
        r = []
        for m in mesi:
            if not scelti(m) or m.chiusura is None:
                continue
            dopo = chiusure.get(fine_mese(mesi_prima(m.fm, -h)))
            if dopo is not None:
                r.append(dopo / m.chiusura - 1)
        out[h] = (len(r), statistics.fmean(r) if r else float("nan"), statistics.median(r) if r else float("nan"),
                  sum(1 for x in r if x < 0) / len(r) if r else float("nan"))
    return out


def sovrapposizione(mesi: list[Mese]) -> dict:
    nomi = list(SEGNALI)
    out = {}
    for a in nomi:
        for b in nomi:
            if a == b:
                continue
            on_a = [m for m in mesi if m.letture[a].acceso is True and m.letture[b].acceso is not None]
            insieme = sum(1 for m in on_a if m.letture[b].acceso is True)
            out[(a, b)] = (insieme / len(on_a) if on_a else float("nan"), len(on_a))
    return out


def falsi_eventi(mesi: list[Mese], eventi: list[EventoF], composito: str, soglia: int, seme: int = SEME,
                 n: int = N_FALSI) -> list[float]:
    rng = random.Random(seme)
    candidati = [m.fm for m in mesi if dt.date(1975, 1, 1) <= m.fm <= FINE_MESI]
    lunghezze = [max(0, mesi_fra(e.massimo_data, e.fine_finestra)) for e in eventi]   # mesi dal massimo al −10%
    on = {m.fm for m in mesi if getattr(m, composito) is not None and getattr(m, composito) >= soglia}
    tassi = []
    for _ in range(n):
        finestre = []
        for lung in lunghezze:
            for _tent in range(10_000):
                p = rng.choice(candidati)
                a, b = fine_mese(mesi_prima(p, 24)), fine_mese(mesi_prima(p, -lung))
                if b > FINE_MESI or any(not (b < x or a > y) for x, y in finestre):
                    continue
                finestre.append((a, b))
                break
            else:
                raise RuntimeError("falsi eventi: impossibile piazzare una finestra senza sovrapposizioni")
        colpiti = sum(1 for a, b in finestre if any(a <= fm <= b for fm in on))
        tassi.append(colpiti / len(finestre))
    return tassi


def percentile_di(valore: float, campione: list[float]) -> tuple[float, float]:
    """(quota dei falsi strettamente sotto il valore, quota non sopra)."""
    return (sum(1 for x in campione if x < valore) / len(campione), sum(1 for x in campione if x <= valore) / len(campione))


# ------------------------------------------------------------------ referto

def _d(x) -> str:
    return x.isoformat() if x else "—"


def _m(fm: dt.date | None, riferimento: dt.date) -> str:
    """Anticipo in mesi rispetto a `riferimento` (positivo = prima)."""
    return "—" if fm is None else str(mesi_fra(fm, riferimento))


def tabella_eventi(mesi: list[Mese], eventi: list[EventoF], composito: str = "composito5") -> str:
    righe = ["| evento | finestra | −15% | EBP | NTFS | PERMIT | ICSA | WTI | comp ≥3 (anticipo mesi sul massimo / sul −15%) | ≥2 | ≥4 | Faber (anticipo sul massimo) | 10a−3m |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for ev in eventi:
        f = mesi_in_finestra(mesi, ev)
        acc = {s: prima_accensione(f, lambda m, s=s: m.letture[s].acceso is True) for s in SEGNALI}
        c3, c2, c4 = colpito(f, composito, 3), colpito(f, composito, 2), colpito(f, composito, 4)
        fb = prima_accensione(f, lambda m: m.faber is True)
        cv = prima_accensione(f, lambda m: m.curva is True)
        righe.append("| {} ({:.1%}) | {} → {} | {} | {} | {} | {} | {} | {} | {} ({} / {}) | {} | {} | {} ({}) | {} |".format(
            ev.nome, ev.profondita, ev.inizio_finestra, ev.fine_finestra, ev.soglia_data,
            _d(acc["ebp"]), _d(acc["ntfs"]), _d(acc["permit"]), _d(acc["icsa"]), _d(acc["wti"]),
            _d(c3) if c3 else "**NON COLPITO**", _m(c3, ev.massimo_data), _m(c3, ev.soglia_data), _d(c2), _d(c4),
            _d(fb), _m(fb, ev.massimo_data), _d(cv)))
    return "\n".join(righe)


def riassunto_cella(mesi, eventi, composito, soglia, eps_classificati) -> dict:
    colpiti = sum(1 for ev in eventi if colpito(mesi_in_finestra(mesi, ev), composito, soglia))
    falsi = sum(1 for e in eps_classificati if e.esito == "FALSO ALLARME")
    return {"eventi": len(eventi), "colpiti": colpiti, "falsi": falsi,
            "non_giudicabili": sum(1 for e in eps_classificati if e.esito.startswith("non giudicabile"))}


def verdetto(colpiti: int, eventi: int, falsi: int, pct_sotto: float) -> tuple[str, dict]:
    a = colpiti >= math.ceil(2 * eventi / 3)
    b = falsi <= colpiti
    c = pct_sotto > 0.90
    if not a:
        return "NON REGGE", {"a": a, "b": b, "c": c}
    return ("REGGE" if (b and c) else "INCONCLUSIVO"), {"a": a, "b": b, "c": c}


def da_quando(serie: list[tuple[dt.date, bool | None]], fm: dt.date) -> str:
    """Il primo mese della sequenza corrente (acceso o spento) che arriva a `fm`, saltando i mesi non disponibili."""
    attuale = next((v for d, v in serie if d == fm), None)
    if attuale is None:
        return "—"
    inizio = fm
    for d, v in reversed(serie):
        if d > fm or v is None:
            continue
        if v != attuale:
            break
        inizio = d
    return "{} dal {}".format("acceso" if attuale else "spento", inizio.strftime("%Y-%m"))


def stato_attuale(D: Dati, fm: dt.date, log=print) -> str:
    """Stato di ogni segnale e del composito alla fine del mese `fm`, con i dati usati e da quando è acceso o spento."""
    recenti = calcola_mesi(D, dt.date(fm.year - 8, 1, 31), fm, log=lambda *_: None)
    m = recenti[-1]
    assert m.fm == fm
    soglie = {"ebp": "> 0", "ntfs": "< 0", "permit": "media 3 mesi < media 12 mesi", "icsa": "media 4 sett. > media 52 sett.",
              "wti": "> massimo dei 36 mesi precedenti", "ntfs_gsw": "< 0"}
    righe = ["| segnale | dati usati (point-in-time al {}) | valore | soglia | stato | da quando |".format(fm), "|---|---|---|---|---|---|"]
    for s in SEGNALI + ("ntfs_gsw",):
        l = m.letture[s]
        serie = [(x.fm, x.letture[s].acceso) for x in recenti]
        stato = "non disponibile" if l.acceso is None else ("ACCESO" if l.acceso else "spento")
        righe.append("| {} | {} | {} | {} | {} | {} |".format(
            s, l.dati, "—" if l.valore is None else "{:+.3f}".format(l.valore), soglie[s], stato, da_quando(serie, fm)))
    c5 = [(x.fm, None if x.composito5 is None else x.composito5 >= 3) for x in recenti]
    ultimo_c5 = next((x for x in reversed(recenti) if x.composito5 is not None), None)
    accesi_disponibili = sum(1 for s in SEGNALI if m.letture[s].acceso is True)
    non_disp = [s for s in SEGNALI if m.letture[s].acceso is None]
    righe.append("| **composito ≥ 3** | {} | {} | ≥ 3 | {} | {} |".format(
        "regola stretta: {}".format("tutti e cinque i segnali" if not non_disp else "non calcolabile, manca " + ", ".join(non_disp)),
        "—" if m.composito5 is None else m.composito5, "—" if m.composito5 is None else ("ACCESO" if m.composito5 >= 3 else "spento"),
        da_quando(c5, fm) if m.composito5 is not None else "ultimo calcolabile: {} = {} ({})".format(
            ultimo_c5.fm, ultimo_c5.composito5, da_quando(c5, ultimo_c5.fm))))
    if non_disp:
        ultimo_ebp = max(d for d in D.ebp)
        extra = accesi_disponibili + (1 if D.ebp[ultimo_ebp] > 0 else 0)
        righe.append("| composito con l'ultimo EBP pubblicato ({} = {:+.3f}) | i 4 segnali disponibili + EBP di {} | {} | ≥ 3 | {} | — |".format(
            ultimo_ebp.strftime("%Y-%m"), D.ebp[ultimo_ebp], ultimo_ebp.strftime("%Y-%m"), extra, "ACCESO" if extra >= 3 else "spento"))
    return "\n".join(righe)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    D = Dati()
    print("# Materiale del referto — Test F, fermata 2 ({})\n".format(dt.date.today()))
    print("GSPC.INDX: {} sedute, {} → {}".format(len(D.righe), D.righe[0][0], D.righe[-1][0]))
    ultima = D.righe[-1][0]
    rec = E.recessioni()
    mesi = calcola_mesi(D)
    chiusure = {m.fm: m.chiusura for m in mesi}
    for fm in fini_mese(dt.date(2026, 1, 31), dt.date(2026, 9, 30)):
        chiusure[fm] = D.chiusura_mensile(fm)
    tutti_eventi = E.eventi_12_mesi(D.righe)

    disp5 = [m for m in mesi if m.composito5 is not None]
    print("Composito a 5 disponibile: {} mesi, {} → {}".format(len(disp5), disp5[0].fm, disp5[-1].fm))
    for s in SEGNALI + ("ntfs_gsw",):
        d = [m for m in mesi if m.letture[s].acceso is not None]
        print("  segnale {}: disponibile {} → {}, acceso {:.1%} del tempo".format(
            s, d[0].fm, d[-1].fm, sum(1 for m in d if m.letture[s].acceso) / len(d)))
    for soglia in (2, 3, 4):
        print("Quota del tempo con composito ≥{}: {:.1%}".format(
            soglia, sum(1 for m in disp5 if m.composito5 >= soglia) / len(disp5)))

    # ---- cella del verdetto
    eventi = eventi_test(D.righe, rec)
    eps = classifica_episodi(episodi(mesi, "composito5", 3), tutti_eventi, ultima)
    cella = riassunto_cella(mesi, eventi, "composito5", 3, eps)
    tassi = falsi_eventi(mesi, eventi, "composito5", 3)
    reale = cella["colpiti"] / cella["eventi"]
    sotto, non_sopra = percentile_di(reale, tassi)
    v, crit = verdetto(cella["colpiti"], cella["eventi"], cella["falsi"], sotto)
    print("\n## Cella del verdetto — composito ≥3, {} ribassi da recessione (inizio = mese del picco NBER)\n".format(cella["eventi"]))
    print("colpiti {}/{} (servono {}), falsi allarmi {} (+{} non giudicabili), tasso reale {:.3f}; falsi eventi (seme {}): "
          "mediana {:.3f}, 90° percentile {:.3f}, quota sotto il reale {:.3f} (non sopra {:.3f})".format(
              cella["colpiti"], cella["eventi"], math.ceil(2 * cella["eventi"] / 3), cella["falsi"], cella["non_giudicabili"],
              reale, SEME, statistics.median(tassi), sorted(tassi)[int(0.9 * len(tassi))], sotto, non_sopra))
    print("**VERDETTO: {}** — a) {} b) {} c) {}\n".format(v, crit["a"], crit["b"], crit["c"]))
    print(tabella_eventi(mesi, eventi))
    print("\n### Episodi del composito ≥3 (separazione < 3 mesi = uno)\n")
    print("| inizio | fine | mesi accesi | esito |\n|---|---|---:|---|")
    for e in eps:
        print("| {} | {} | {} | {} |".format(e.inizio, e.fine, e.mesi_accesi, e.esito))

    # ---- falsi allarmi, lettura severa (aggiunta dell'utente del 01-10, descrittiva)
    print("\n### Falsi allarmi, lettura severa (parte un nuovo ribasso ≥ 15 % nei 24 mesi dopo l'accensione; ribasso già partito non conta)\n")
    for inizio, nome in (("soglia", "partenza = seduta T del −15 % (inizio dell'evento, ADR-060)"), ("massimo", "partenza = massimo P dell'evento")):
        sev = classifica_episodi_severa(episodi(mesi, "composito5", 3), tutti_eventi, ultima, inizio=inizio)
        falsi = [e for e in sev if e.esito == "FALSO ALLARME"]
        ng = sum(1 for e in sev if e.esito.startswith("non giudicabile"))
        print("- **{}**: {} falsi allarmi su {} episodi (+{} non giudicabili): {} — criterio b) falsi ≤ colpiti ({}): {}".format(
            nome, len(falsi), len(sev), ng, ", ".join("{}→{}".format(e.inizio.strftime("%Y-%m"), e.fine.strftime("%Y-%m")) for e in falsi),
            cella["colpiti"], "regge" if len(falsi) <= cella["colpiti"] else "NON regge"))
    print("\n| inizio | fine | mesi | esito (partenza = −15 %) | esito (partenza = massimo) |\n|---|---|---:|---|---|")
    sev_t = classifica_episodi_severa(episodi(mesi, "composito5", 3), tutti_eventi, ultima, "soglia")
    sev_p = classifica_episodi_severa(episodi(mesi, "composito5", 3), tutti_eventi, ultima, "massimo")
    for a, b in zip(sev_t, sev_p):
        print("| {} | {} | {} | {} | {} |".format(a.inizio, a.fine, a.mesi_accesi, a.esito, b.esito))

    # ---- stato attuale
    print("\n## Stato al 2026-09-30\n")
    print(stato_attuale(D, dt.date(2026, 9, 30)))

    # ---- soglie descrittive
    for soglia in (2, 4):
        eps_s = classifica_episodi(episodi(mesi, "composito5", soglia), tutti_eventi, ultima)
        c = riassunto_cella(mesi, eventi, "composito5", soglia, eps_s)
        t = falsi_eventi(mesi, eventi, "composito5", soglia)
        s_, _ = percentile_di(c["colpiti"] / c["eventi"], t)
        print("\nDescrittiva ≥{}: colpiti {}/{}, falsi allarmi {} (+{} non giudicabili), quota falsi eventi sotto il reale {:.3f}, episodi {}".format(
            soglia, c["colpiti"], c["eventi"], c["falsi"], c["non_giudicabili"], s_, len(eps_s)))

    # ---- rendimenti
    print("\n## Rendimenti dell'S&P 500 dopo l'accensione (composito ≥3) contro tutti i mesi\n")
    print("| campione | orizzonte | n | media | mediana | quota negativi |\n|---|---|---:|---:|---:|---:|")
    inizi = {e.inizio for e in eps}
    campioni = (("mesi accesi (≥3)", lambda m: m.composito5 is not None and m.composito5 >= 3),
                ("prima accensione di ogni episodio", lambda m: m.fm in inizi),
                ("tutti i mesi con composito", lambda m: m.composito5 is not None))
    for nome, scelta in campioni:
        for h, (n, media, med, neg) in rendimenti(mesi, chiusure, scelta).items():
            print("| {} | {} mesi | {} | {:+.1%} | {:+.1%} | {:.0%} |".format(nome, h, n, media, med, neg))

    # ---- sovrapposizione
    print("\n## Sovrapposizione: quota dei mesi con A acceso in cui anche B è acceso (coppie > 80% in grassetto)\n")
    sov = sovrapposizione(disp5)
    print("| A \\ B | " + " | ".join(SEGNALI) + " |\n|---|" + "---|" * len(SEGNALI))
    for a in SEGNALI:
        celle = []
        for b in SEGNALI:
            if a == b:
                celle.append("—")
            else:
                q, n = sov[(a, b)]
                celle.append(("**{:.0%}**" if q > 0.8 else "{:.0%}").format(q))
        print("| {} | ".format(a) + " | ".join(celle) + " |")

    # ---- robustezze descrittive
    print("\n## Robustezze descrittive\n")
    def riga_rob(nome, ev_, composito, soglia, mesi_=mesi):
        eps_ = classifica_episodi(episodi(mesi_, composito, soglia), tutti_eventi, ultima)
        c = riassunto_cella(mesi_, ev_, composito, soglia, eps_)
        t = falsi_eventi(mesi_, ev_, composito, soglia)
        s_, _ = percentile_di(c["colpiti"] / c["eventi"], t)
        print("- **{}**: colpiti {}/{}, falsi allarmi {} (+{} non giudicabili), quota falsi eventi sotto il reale {:.3f} — {}".format(
            nome, c["colpiti"], c["eventi"], c["falsi"], c["non_giudicabili"], s_,
            ", ".join("{}: {}".format(e.nome, _d(colpito(mesi_in_finestra(mesi_, e), composito, soglia)) or "**no**") for e in ev_)))
    riga_rob("recessione dal mese dopo il picco (USREC)", eventi_test(D.righe, rec, mese_dopo_il_picco=True), "composito5", 3)
    riga_rob("1980 fusi in un evento (massimo 1980-02-13, finestra dal 1978-02 al −10% del secondo)", eventi_test(D.righe, rec, fondi_1980=True), "composito5", 3)
    riga_rob("composito a 4 senza EBP dal 1967, cella ≥3 su 4", eventi_test(D.righe, rec, senza_ebp=True), "composito4", 3)
    riga_rob("composito a 4 senza EBP dal 1967, cella ≥2 su 4", eventi_test(D.righe, rec, senza_ebp=True), "composito4", 2)
    riga_rob("tasso a 3 mesi tutto GSW (y(0,25)) nel composito a 5", eventi, "composito5_gsw", 3)
    print("\nTabella con il composito a 4 (senza EBP), eventi dal 1970:\n")
    print(tabella_eventi(mesi, eventi_test(D.righe, rec, senza_ebp=True), "composito4"))

    # ---- curva a breve: trimestri negativi (confronto con il paper, 1972-2018)
    print("\n## Near-term forward spread (DTB3): medie trimestrali negative 1972-2018, e versione tutto GSW\n")
    for chiave in ("ntfs", "ntfs_gsw"):
        trimestri = {}
        for m in mesi:
            v = m.letture[chiave].valore
            if v is not None and 1972 <= m.fm.year <= 2018:
                trimestri.setdefault((m.fm.year, (m.fm.month - 1) // 3 + 1), []).append(v)
        neg = [k for k, v in sorted(trimestri.items()) if statistics.fmean(v) < 0]
        print("- {}: {} trimestri negativi su {}: {}".format(chiave, len(neg), len(trimestri),
              ", ".join("{}Q{}".format(a, q) for a, q in neg)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
