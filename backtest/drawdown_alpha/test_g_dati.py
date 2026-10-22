"""Test G (scadenza delle put spread), fermata 1: lettura dei dati, prezzo Black-Scholes e controlli. Nient'altro.

Qui **non** c'è nessuna simulazione di portafoglio: nessun rendimento, nessun ribasso con protezione, nessun costo dei
premi, nessun guadagno delle put. Le regole sono in `2026-10-04_preregistrazione_test_g.md`; la simulazione si scrive
solo dopo l'approvazione dell'utente (fermata 2).

Dati solo da `market_data.api`: chiusure di `GSPC.INDX` (come `eventi_f.chiusure()`), `VIXCLS` e `DTB3` con `api.fred()`.
Un dato che manca non si sostituisce: nelle sedute senza VIX o senza DTB3 vale l'ultimo valore noto **prima** della
seduta (mai uno successivo) e, se è più vecchio di `MAX_GIORNI_VECCHIO` giorni, `DatoMancante`.

    python backtest/drawdown_alpha/test_g_dati.py             # controlli sui dati + prezzo di prova (markdown)
    python backtest/drawdown_alpha/test_g_dati.py --segnali   # in più: da quando esistono composito del Test F e Faber
    python backtest/drawdown_alpha/test_g_dati.py --tetto     # in più: riduzione massima teorica (solo prezzi di apertura)
"""
from __future__ import annotations

import bisect
import datetime as dt
import math
import statistics
import sys
from pathlib import Path

from market_data import api

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import eventi_f as E  # noqa: E402
from test_f import dtb3_continuo  # noqa: E402  (sconto bancario → rendimento continuo, base 365; ADR-067)

PERIODO = (dt.date(1990, 1, 1), dt.date(2025, 12, 31))
STRIKE_COMPRATA = 0.95                # put comprata 5% sotto il prezzo
STRIKE_VENDUTA = 0.75                 # put venduta 25% sotto
INCLINAZIONE = 5.0                    # punti di volatilità in più sulla put venduta (sensibilità descrittiva: 0 e 10)
SCADENZE_MESI = (3, 6, 9, 12)
BASE_GIORNI = 365.0                   # tempo = giorni di calendario / 365
MAX_GIORNI_VECCHIO = 7                # un valore «ultimo noto» più vecchio di così non si usa: ci si ferma
DIVIDENDO = 0.02                      # q continuo nel prezzo delle put (scelta principale, ADR-072); 0 = sensibilità descrittiva.
                                      # Il portafoglio simulato resta senza dividendi: GSPC è un indice di prezzo.
LARGHEZZA = STRIKE_COMPRATA - STRIKE_VENDUTA   # guadagno massimo dello spread: 20% del prezzo di ingresso
PREMIO = {"A": {3: 0.015, 6: 0.03, 9: 0.03, 12: 0.03},     # versione A: 6% × mesi/12, massimo 3%
          "B": {3: 0.03, 6: 0.03, 9: 0.03, 12: 0.03}}      # versione B: 3% fisso


class DatoMancante(RuntimeError):
    pass


# ------------------------------------------------------------------ Black-Scholes

def N(x: float) -> float:
    """Funzione di ripartizione della normale standard."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = DIVIDENDO) -> tuple[float, float]:
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def bs_put(S: float, K: float, T: float, r: float, sigma: float, q: float = DIVIDENDO) -> float:
    """Put europea. S, K in punti indice; T in anni; r, q tassi continui (frazione); sigma volatilità annua (frazione).
    A T = 0 il valore intrinseco. Volatilità o prezzi non positivi, T negativo: ValueError, mai un numero di ripiego."""
    if not (S > 0 and K > 0):
        raise ValueError("prezzo e strike devono essere positivi: S={!r} K={!r}".format(S, K))
    if T < 0:
        raise ValueError("tempo alla scadenza negativo: {!r}".format(T))
    if T == 0:
        return max(K - S, 0.0)
    if not sigma > 0:
        raise ValueError("volatilità non positiva: {!r}".format(sigma))
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    return K * math.exp(-r * T) * N(-d2) - S * math.exp(-q * T) * N(-d1)


def bs_call(S: float, K: float, T: float, r: float, sigma: float, q: float = DIVIDENDO) -> float:
    """Call europea: serve solo al controllo di parità put-call nei test."""
    if T == 0:
        return max(S - K, 0.0)
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * N(d1) - K * math.exp(-r * T) * N(d2)


def strike(S0: float) -> tuple[float, float]:
    """(strike della put comprata, strike della put venduta) dalla chiusura del giorno di ingresso; non arrotondati."""
    return STRIKE_COMPRATA * S0, STRIKE_VENDUTA * S0


def put_spread(S: float, k_comprata: float, k_venduta: float, T: float, r: float, vix: float,
               inclinazione: float = INCLINAZIONE, q: float = DIVIDENDO) -> float:
    """Valore di uno spread (put comprata − put venduta) in punti indice. `vix` in punti (20 = 20%): volatilità VIX per
    la comprata, VIX + `inclinazione` per la venduta. A T = 0 è il valore a scadenza."""
    if not k_comprata > k_venduta:
        raise ValueError("lo strike comprato deve stare sopra quello venduto")
    return (bs_put(S, k_comprata, T, r, vix / 100.0, q)
            - bs_put(S, k_venduta, T, r, (vix + inclinazione) / 100.0, q))


def tasso_continuo(dtb3_pct: float) -> float:
    """DTB3 (sconto bancario, per cento) → tasso continuo in frazione, con `test_f.dtb3_continuo` (91 giorni, base 365)."""
    return dtb3_continuo(dtb3_pct) / 100.0


# ------------------------------------------------------------------ date

def scadenza(ingresso: dt.date, mesi: int, sedute: list[dt.date]) -> dt.date:
    """`mesi` mesi di calendario dopo l'ingresso (stesso giorno del mese, o l'ultimo se non esiste); se non è una seduta,
    la seduta precedente. Oltre l'ultima seduta dell'archivio: DatoMancante."""
    bersaglio = E.mesi_prima(ingresso, -mesi)
    if bersaglio > sedute[-1]:
        raise DatoMancante("scadenza {} oltre l'ultima seduta dell'archivio ({})".format(bersaglio, sedute[-1]))
    i = bisect.bisect_right(sedute, bersaglio) - 1
    if i < 0 or sedute[i] <= ingresso:
        raise DatoMancante("nessuna seduta fra l'ingresso {} e la scadenza {}".format(ingresso, bersaglio))
    return sedute[i]


def anni(da: dt.date, a: dt.date) -> float:
    return (a - da).days / BASE_GIORNI


# ------------------------------------------------------------------ serie

class Serie:
    """Serie giornaliera di FRED con la regola dei buchi: ultimo valore noto, mai in avanti, mai più vecchio del limite."""

    def __init__(self, nome: str, righe: list[tuple[dt.date, float]]):
        self.nome = nome
        self.righe = righe
        self.date = [d for d, _ in righe]
        self.per_data = dict(righe)

    def ultimo_noto(self, giorno: dt.date, max_giorni: int = MAX_GIORNI_VECCHIO) -> tuple[dt.date, float]:
        i = bisect.bisect_right(self.date, giorno) - 1
        if i < 0:
            raise DatoMancante("{}: nessun valore entro il {}".format(self.nome, giorno))
        d, v = self.righe[i]
        if (giorno - d).days > max_giorni:
            raise DatoMancante("{}: l'ultimo valore prima del {} è del {} (più di {} giorni)".format(
                self.nome, giorno, d, max_giorni))
        return d, v


def leggi_fred(nome: str) -> Serie:
    df = api.fred(nome)                # se la serie non è nel grezzo di oggi il lettore la scarica (CSV pubblico, senza chiave)
    if len(df) == 0:
        raise DatoMancante("{}: serie vuota -- fermarsi, non sostituire dati".format(nome))
    return Serie(nome, [(d.date(), float(v)) for d, v in zip(df["date"], df["value"])])


class Dati:
    def __init__(self):
        self.gspc = E.chiusure()                                      # [(data, chiusura)] GSPC.INDX, prezzi puliti
        self.sedute = [d for d, _ in self.gspc]
        self.chiusura = dict(self.gspc)
        self.vix = leggi_fred("VIXCLS")
        self.dtb3 = leggi_fred("DTB3")

    def sedute_periodo(self) -> list[dt.date]:
        return [d for d in self.sedute if PERIODO[0] <= d <= PERIODO[1]]


# ------------------------------------------------------------------ controlli (fermata 1)

def _nel_periodo(righe):
    return [(d, v) for d, v in righe if PERIODO[0] <= d <= PERIODO[1]]


def _buchi(sedute: list[dt.date], presenti: set) -> list[tuple[dt.date, dt.date, int]]:
    """Serie di sedute consecutive senza il dato: (prima, ultima, numero di sedute)."""
    out, inizio, n, ultima = [], None, 0, None
    for d in sedute:
        if d in presenti:
            if inizio is not None:
                out.append((inizio, ultima, n))
                inizio, n = None, 0
        else:
            if inizio is None:
                inizio = d
            n += 1
            ultima = d
    if inizio is not None:
        out.append((inizio, ultima, n))
    return out


def controlli(D: Dati) -> None:
    sedute = D.sedute_periodo()
    print("## Controlli sui dati — periodo {} → {}\n".format(*PERIODO))
    print("| serie | prima data (valore) | ultima data | osservazioni totali | prima nel periodo | ultima nel periodo | osservazioni 1990-2025 |")
    print("|---|---|---|---:|---|---|---:|")
    for nome, righe in (("GSPC.INDX (chiusura)", D.gspc), ("VIXCLS", D.vix.righe), ("DTB3", D.dtb3.righe)):
        p = _nel_periodo(righe)
        print("| {} | {} ({:,.2f}) | {} | {} | {} | {} | {} |".format(
            nome, righe[0][0], righe[0][1], righe[-1][0], len(righe), p[0][0], p[-1][0], len(p)))

    print("\n### Buchi: sedute di GSPC senza VIX e senza DTB3 nello stesso giorno\n")
    buchi = {"VIXCLS": _buchi(sedute, set(D.vix.date)), "DTB3": _buchi(sedute, set(D.dtb3.date))}
    per_anno = {}
    for nome, lista in buchi.items():
        for a, b, _n in lista:
            for d in sedute[sedute.index(a):sedute.index(b) + 1]:
                per_anno.setdefault(d.year, {"VIXCLS": 0, "DTB3": 0})[nome] += 1
    sedute_anno = {}
    for d in sedute:
        sedute_anno[d.year] = sedute_anno.get(d.year, 0) + 1
    print("| anno | sedute | senza VIX | senza DTB3 |\n|---|---:|---:|---:|")
    for anno in sorted(sedute_anno):
        c = per_anno.get(anno, {"VIXCLS": 0, "DTB3": 0})
        print("| {} | {} | {} | {} |".format(anno, sedute_anno[anno], c["VIXCLS"], c["DTB3"]))
    print("| **totale** | {} | {} | {} |".format(len(sedute), sum(n for *_x, n in buchi["VIXCLS"]),
                                                 sum(n for *_x, n in buchi["DTB3"])))
    for nome, lista in buchi.items():
        lunghi = sorted(lista, key=lambda x: (-x[2], x[0]))[:5]
        print("\n{}: {} buchi; i più lunghi: {}".format(nome, len(lista), "; ".join(
            "{}{} ({} sedut{})".format(a, "" if a == b else " → " + b.isoformat(), n, "a" if n == 1 else "e")
            for a, b, n in lunghi) or "nessuno"))
    for nome, serie in (("VIXCLS", D.vix), ("DTB3", D.dtb3)):
        fuori = [d for d in serie.date if PERIODO[0] <= d <= PERIODO[1] and d not in D.chiusura]
        print("{}: {} osservazioni nel periodo in giorni che non sono sedute di GSPC{}".format(
            nome, len(fuori), "" if not fuori else " (prima {}, ultima {})".format(fuori[0], fuori[-1])))

    print("\n### Regola dei buchi alla prova: ultimo valore noto, mai in avanti\n")
    for serie in (D.vix, D.dtb3):
        peggio, quando, falliti = 0, None, []
        for d in sedute:
            try:
                dd, _v = serie.ultimo_noto(d)
            except DatoMancante:
                falliti.append(d)
                continue
            if (d - dd).days > peggio:
                peggio, quando = (d - dd).days, (d, dd)
        print("- {}: {} sedute su {} con un valore utilizzabile; età massima del valore usato {} giorni di calendario{}; "
              "sedute senza valore entro {} giorni: {}{}".format(
                  serie.nome, len(sedute) - len(falliti), len(sedute), peggio,
                  "" if quando is None else " (seduta {}, valore del {})".format(*quando), MAX_GIORNI_VECCHIO,
                  len(falliti), "" if not falliti else " — " + ", ".join(x.isoformat() for x in falliti[:10])))

    print("\n### Valori non positivi o anomali (1990-2025)\n")
    g = _nel_periodo(D.gspc)
    v = _nel_periodo(D.vix.righe)
    t = _nel_periodo(D.dtb3.righe)
    var = [(g[i][0], g[i][1] / g[i - 1][1] - 1) for i in range(1, len(g))]
    su, giu = max(var, key=lambda x: x[1]), min(var, key=lambda x: x[1])
    print("- GSPC: chiusure ≤ 0: {}; minimo {:,.2f} ({}), massimo {:,.2f} ({}); variazione giornaliera più ampia "
          "{:+.2%} ({}) e {:+.2%} ({}); giorni con |variazione| > 15%: {}".format(
              sum(1 for _d, x in g if not x > 0), min(g, key=lambda x: x[1])[1], min(g, key=lambda x: x[1])[0],
              max(g, key=lambda x: x[1])[1], max(g, key=lambda x: x[1])[0], su[1], su[0], giu[1], giu[0],
              sum(1 for _d, x in var if abs(x) > 0.15)))
    print("- VIXCLS: valori ≤ 0: {}; non finiti: {}; minimo {:.2f} ({}), massimo {:.2f} ({}); fuori da [5, 100]: {}".format(
        sum(1 for _d, x in v if not x > 0), sum(1 for _d, x in v if not math.isfinite(x)),
        min(v, key=lambda x: x[1])[1], min(v, key=lambda x: x[1])[0], max(v, key=lambda x: x[1])[1],
        max(v, key=lambda x: x[1])[0], sum(1 for _d, x in v if not 5 <= x <= 100)))
    zero = [d for d, x in t if x == 0]
    neg = [(d, x) for d, x in t if x < 0]
    print("- DTB3: valori = 0: {}{}; valori < 0: {}{}; non finiti: {}; minimo {:.2f} ({}), massimo {:.2f} ({}); "
          "fuori da [−1, 20]: {}".format(
              len(zero), "" if not zero else " (dal {} al {})".format(zero[0], zero[-1]),
              len(neg), "" if not neg else " (dal {} al {}, il più basso {:.2f})".format(neg[0][0], neg[-1][0], min(x for _d, x in neg)),
              sum(1 for _d, x in t if not math.isfinite(x)), min(t, key=lambda x: x[1])[1], min(t, key=lambda x: x[1])[0],
              max(t, key=lambda x: x[1])[1], max(t, key=lambda x: x[1])[0], sum(1 for _d, x in t if not -1 <= x <= 20)))
    print("  Un tasso ≤ 0 non è un errore (2011-2015, 2020): Black-Scholes lo accetta e si usa così com'è.")

    print("\n### Mediana a 12 mesi del VIX: da quando la finestra è intera\n")
    prima_vix = D.vix.date[0]
    for fm in _fini_mese(dt.date(1990, 1, 31), dt.date(1991, 12, 31)):
        limite = E.un_anno_prima(fm)
        prima_seduta = next(d for d in D.sedute if d > limite)
        if prima_vix <= prima_seduta:
            n = sum(1 for d in D.vix.date if limite < d <= fm)
            print("Prima fine mese con la finestra (t − 1 anno, t] coperta dal VIX: **{}** ({} osservazioni; primo VIX "
                  "{}, prima seduta della finestra {}). Primo ingresso possibile della regola 3: {}.".format(
                      fm, n, prima_vix, prima_seduta, next(d for d in D.sedute if d > fm)))
            break

    print("\n### Scadenze oltre la fine dei dati\n")
    print("Ultima seduta dell'archivio: {}. Uno spread a 12 mesi aperto dopo il {} scade oltre l'archivio; "
          "uno aperto nel 2025 scade comunque dopo il {} (fine del periodo).".format(
              D.sedute[-1], E.mesi_prima(D.sedute[-1], 12), PERIODO[1]))


def _fini_mese(da: dt.date, a: dt.date) -> list[dt.date]:
    out, d = [], E.fine_mese(da)
    while d <= a:
        out.append(d)
        d = E.fine_mese(d + dt.timedelta(days=1))
    return out


def controllo_segnali() -> None:
    """Da quando esistono il composito del Test F e Faber, letto dal codice del Test F (nessun valore acceso/spento stampato)."""
    import test_f as F
    D = F.Dati()
    mesi = F.calcola_mesi(D, log=lambda *_: None)
    print("\n## Composito del Test F e regola di Faber: disponibilità (da `test_f.calcola_mesi`)\n")
    c5 = [m for m in mesi if m.composito5 is not None]
    fb = [m for m in mesi if m.faber is not None]
    print("- composito a 5 segnali: prima fine mese {}, ultima {}, {} fini mese (calcolo dal {} al {})".format(
        c5[0].fm, c5[-1].fm, len(c5), mesi[0].fm, mesi[-1].fm))
    print("- Faber (10 chiusure mensili): prima fine mese calcolata {}, ultima {}, {} fini mese; la serie GSPC parte dal {}".format(
        fb[0].fm, fb[-1].fm, len(fb), D.righe[0][0]))
    letture = [m for m in mesi if dt.date(1989, 12, 31) <= m.fm <= dt.date(2025, 11, 30)]
    senza_c = [m for m in letture if m.composito5 is None]
    senza_f = [m for m in letture if m.faber is None]
    print("- letture usate dal Test G (fine mese 1989-12 → 2025-11, ingresso alla prima seduta del mese dopo): {}; "
          "senza composito: {}{}; senza Faber: {}".format(
              len(letture), len(senza_c), "" if not senza_c else " (" + ", ".join(
                  "{}: manca {}".format(m.fm, "/".join(s for s in F.SEGNALI if m.letture[s].acceso is None)) for m in senza_c) + ")",
              len(senza_f)))


# ------------------------------------------------------------------ prezzo di prova, passo per passo

def prezzo_di_prova(D: Dati, anno: int = 2008, mese: int = 9, mesi: int = 12) -> None:
    """Uno spread a `mesi` mesi aperto alla prima seduta del mese: tutti i passaggi con q = `DIVIDENDO`, poi il confronto
    con `put_spread`. Solo il prezzo all'apertura: né valore a scadenza né esito."""
    ingresso = next(d for d in D.sedute if d >= dt.date(anno, mese, 1))
    S = D.chiusura[ingresso]
    d_vix, vix = D.vix.ultimo_noto(ingresso)
    d_tb, tb = D.dtb3.ultimo_noto(ingresso)
    fine = scadenza(ingresso, mesi, D.sedute)
    giorni = (fine - ingresso).days
    T = giorni / BASE_GIORNI
    P = 1.0 - tb / 100.0 * 91 / 360.0
    r = (365.0 / 91.0) * math.log(1.0 / P)
    q = DIVIDENDO
    k1, k2 = STRIKE_COMPRATA * S, STRIKE_VENDUTA * S
    sq = S * math.exp(-q * T)
    print("\n## Prezzo di prova, passo per passo — spread a {} mesi aperto il {}, q = {:.2%}\n".format(mesi, ingresso, q))
    print("Dati letti: chiusura GSPC del {} = {:.2f}; VIXCLS del {} = {:.2f}; DTB3 del {} = {:.2f} (sconto, %).".format(
        ingresso, S, d_vix, vix, d_tb, tb))
    print("Scadenza: {} + {} mesi = {} → seduta {} ; giorni di calendario {} ; T = {}/365 = {:.6f}".format(
        ingresso, mesi, E.mesi_prima(ingresso, -mesi), fine, giorni, giorni, T))
    print("Tasso: P = 1 − {:.4f}·91/360 = {:.8f} ; r = (365/91)·ln(1/P) = {:.8f} ({:.4f}%)".format(tb / 100.0, P, r, 100 * r))
    print("Dividendo: q = {:.4f} ; S·e^(−qT) = {:.2f} × {:.8f} = {:.4f}".format(q, S, math.exp(-q * T), sq))
    print("Strike: comprata K1 = 0,95 × {:.2f} = {:.4f} ; venduta K2 = 0,75 × {:.2f} = {:.4f}\n".format(S, k1, S, k2))
    prezzi = []
    for nome, K, sigma in (("put comprata", k1, vix / 100.0), ("put venduta", k2, (vix + INCLINAZIONE) / 100.0)):
        a = math.log(S / K)
        b = (r - q + 0.5 * sigma * sigma) * T
        c = sigma * math.sqrt(T)
        d1 = (a + b) / c
        d2 = d1 - c
        sconto = K * math.exp(-r * T)
        p = sconto * N(-d2) - sq * N(-d1)
        prezzi.append(p)
        print("**{}** — K = {:.4f}, σ = {:.4f}".format(nome, K, sigma))
        print("  ln(S/K) = {:.8f} ; (r − q + σ²/2)·T = {:.8f} ; σ·√T = {:.8f}".format(a, b, c))
        print("  d1 = ({:.8f} + {:.8f}) / {:.8f} = {:.6f} ; d2 = d1 − σ·√T = {:.6f}".format(a, b, c, d1, d2))
        print("  N(d1) = {:.6f} ; N(d2) = {:.6f} ; N(−d1) = {:.6f} ; N(−d2) = {:.6f}".format(N(d1), N(d2), N(-d1), N(-d2)))
        print("  K·e^(−rT) = {:.4f} ; put = {:.4f} × {:.6f} − {:.4f} × {:.6f} = **{:.4f}** punti indice ({:.3%} di S)\n".format(
            sconto, sconto, N(-d2), sq, N(-d1), p, p / S))
    a_mano = prezzi[0] - prezzi[1]
    print("Spread a mano = {:.4f} − {:.4f} = **{:.4f} punti indice = {:.4%} della chiusura**".format(
        prezzi[0], prezzi[1], a_mano, a_mano / S))
    codice = put_spread(S, *strike(S), anni(ingresso, fine), tasso_continuo(tb), vix)
    print("Funzione del codice `put_spread(S, *strike(S), anni(ingresso, scadenza), tasso_continuo(DTB3), VIX)` = "
          "**{:.4f}** ; differenza {:.2e}".format(codice, codice - a_mano))
    for incl in (0.0, 10.0):
        v = put_spread(S, k1, k2, T, r, vix, inclinazione=incl)
        print("  (sensibilità descrittiva, inclinazione {:+.0f} punti: {:.4f} punti indice = {:.4%})".format(incl, v, v / S))
    v0 = put_spread(S, k1, k2, T, r, vix, q=0.0)
    print("  (sensibilità descrittiva, q = 0: {:.4f} punti indice = {:.4%}; comprata {:.4f}, venduta {:.4f})".format(
        v0, v0 / S, bs_put(S, k1, T, r, vix / 100.0, 0.0), bs_put(S, k2, T, r, (vix + INCLINAZIONE) / 100.0, 0.0)))
    if abs(codice - a_mano) > 1e-9:
        raise RuntimeError("il prezzo della funzione non coincide con il calcolo passo per passo")


# ------------------------------------------------------------------ riduzione massima teorica (solo prezzi di apertura)

def parte_coperta(premio: float, costo_spread: float) -> float:
    """Quota del portafoglio coperta da un'operazione: premio (frazione del portafoglio) / costo dello spread (frazione
    dell'indice). Può superare 1: nessun limite."""
    if not costo_spread > 0:
        raise ValueError("costo dello spread non positivo: {!r}".format(costo_spread))
    return premio / costo_spread


def guadagno_massimo(premio: float, costo_spread: float) -> float:
    """Guadagno massimo di un'operazione in frazione del portafoglio: 20% × parte coperta (indice a −25% o peggio a scadenza)."""
    return LARGHEZZA * parte_coperta(premio, costo_spread)


def tetto_teorico(D: Dati) -> None:
    """Per i tre ribassi più profondi dell'indice dal 1990 (lista A del Test F, già pubblicata): prezzo di APERTURA dello
    spread alla seduta del massimo, parte coperta, guadagno massimo e riduzione massima teorica = guadagno massimo /
    profondità. Nessun valore a scadenza, nessuna simulazione: è il tetto di una singola operazione, non un risultato."""
    eventi = [ev for ev in E.eventi_12_mesi(D.gspc) if ev.massimo_data >= PERIODO[0] and ev.soglia_data <= PERIODO[1]]
    tre = sorted(sorted(eventi, key=lambda ev: ev.profondita)[:3], key=lambda ev: ev.massimo_data)
    print("\n## Riduzione massima teorica dei tre ribassi peggiori — solo prezzi di apertura, q = {:.0%}\n".format(DIVIDENDO))
    print("Tre ribassi più profondi dell'indice dal 1990 (`eventi_f.eventi_12_mesi`): " + "; ".join(
        "massimo {} ({:,.2f}), fondo {}, profondità {:.1%}".format(ev.massimo_data, ev.massimo, ev.fondo_data, ev.profondita)
        for ev in tre) + "\n")
    print("| massimo | VIX | DTB3 | scadenza | data di scadenza | costo dello spread (% indice) | A: premio | A: parte coperta | "
          "A: guadagno massimo | A: riduzione massima | B: premio | B: parte coperta | B: guadagno massimo | B: riduzione massima |")
    print("|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    rid = {(v, m): [] for v in PREMIO for m in SCADENZE_MESI}
    for ev in tre:
        g = ev.massimo_data
        S = D.chiusura[g]
        _dv, vix = D.vix.ultimo_noto(g)
        _dt, tb = D.dtb3.ultimo_noto(g)
        for m in SCADENZE_MESI:
            fine = scadenza(g, m, D.sedute)
            costo = put_spread(S, *strike(S), anni(g, fine), tasso_continuo(tb), vix) / S
            celle = []
            for v in ("A", "B"):
                pr = PREMIO[v][m]
                c, gm = parte_coperta(pr, costo), guadagno_massimo(pr, costo)
                r = gm / -ev.profondita
                rid[(v, m)].append(r)
                celle.append("{:.1%} | {:.0%} | {:.1%} | {:.0%}".format(pr, c, gm, r))
            print("| {} | {:.2f} | {:.2f} | {} mesi | {} | {:.3%} | {} | {} |".format(g, vix, tb, m, fine, costo, celle[0], celle[1]))
    print("\n| versione | scadenza | riduzione massima teorica media dei tre | contro 1/3 | contro 1/5 |\n|---|---|---:|---|---|")
    for v in ("A", "B"):
        for m in SCADENZE_MESI:
            media = statistics.fmean(rid[(v, m)])
            print("| {} | {} mesi | {:.1%} ({}) | {} | {} |".format(
                v, m, media, " ; ".join("{:.0%}".format(x) for x in rid[(v, m)]),
                "sopra" if media >= 1 / 3 else "**sotto**", "sopra" if media >= 1 / 5 else "**sotto**"))


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    D = Dati()
    print("# Test G, fermata 1 — controlli sui dati ({}). Nessuna simulazione, nessun risultato.\n".format(dt.date.today()))
    controlli(D)
    if "--segnali" in argv:
        controllo_segnali()
    prezzo_di_prova(D)
    if "--tetto" in argv:
        tetto_teorico(D)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
