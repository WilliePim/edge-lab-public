"""Quando EDGAR accetta depositi, e perche' un indice puo' non esserci.

Il problema che questo modulo risolve. Il giro segnalava «giorno NON osservato»
per ogni giorno lavorativo il cui indice non si leggeva, e le tre ragioni per
cui un indice manca sono diversissime fra loro:

    FESTIVO       la SEC e' chiusa e non c'e' NIENTE da leggere. Un giorno
                  senza depositi, non un giorno ignoto.
    NON ANCORA    l'indice del giorno esce la sera; il giro delle 8:00 lo cerca
                  quando ancora non esiste. Sara' letto domani.
    ILLEGGIBILE   c'erano depositi e non li abbiamo visti. QUESTO e' il buco,
                  e solo questo va segnalato.

Contarli insieme sporca la conta dei buchi di festivi, e un contatore che
segnala sempre qualcosa si smette di guardare.

LA REGOLA, E QUANTO COPRE. Le undici feste federali si calcolano
aritmeticamente, con lo spostamento al venerdi' se cadono di sabato e al lunedi'
se cadono di domenica. Verificato contro il corpus, 2015-01 -> 2026-03:

    giorni lavorativi                                  2.934
    mediana dei depositi in un giorno lavorativo          67
    festivi calcolati che cadono in settimana            118
      di cui con ZERO depositi nel corpus                118   <- nessun falso positivo
    giorni lavorativi con zero depositi                  126
      spiegati dalla regola                              118   (93,7%)
      NON spiegati                                         8

GLI OTTO NON SPIEGATI SONO IL PUNTO INTERESSANTE, e non si risolvono con una
regola migliore: sono chiusure per ordine esecutivo, decise caso per caso.
Due sono giorni di lutto nazionale, gli altri sei sono vigilie di Natale e un
26 dicembre concessi ad hoc.

Per queste NON si indovina. `CLOSURES` le elenca con la data, ed e' una lista
che nasce dall'osservazione e non da un calcolo: e' destinata a restare
indietro. Una chiusura nuova, non ancora nella lista, finisce fra gli
ILLEGGIBILI -- cioe' viene segnalata come buco. E' voluto: senza
un'informazione esterna una chiusura non annunciata e' indistinguibile da un
guasto, e il vincolo di questo repository dice che il dato mancante resta
UNKNOWN e non diventa un «verificato vuoto».
"""

from __future__ import annotations

from datetime import date, timedelta

#  I tre esiti, piu' l'assenza di esito.
FESTIVO = "festivo"
CHIUSURA = "chiusura"          # per ordine esecutivo, osservata non calcolata
NON_ANCORA = "non ancora pubblicato"
ILLEGGIBILE = "illeggibile"
WEEKEND = "weekend"

#  Le chiusure che la regola federale non prende. Ricavate contando i depositi
#  del corpus: giorni lavorativi con ZERO depositi e non spiegati da una festa.
#  La ragione accanto a ciascuna e' conoscenza esterna, non un fatto dedotto da
#  questi dati: serve a chi legge, non al codice, che guarda solo la data.
CLOSURES = {
    "2018-12-05": "lutto nazionale",
    "2018-12-24": "vigilia di Natale concessa",
    "2019-12-24": "vigilia di Natale concessa",
    "2020-12-24": "vigilia di Natale concessa",
    "2024-12-24": "vigilia di Natale concessa",
    "2025-01-09": "lutto nazionale",
    "2025-12-24": "vigilia di Natale concessa",
    "2025-12-26": "giorno dopo Natale concesso",
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """L'n-esimo `weekday` del mese. Lunedi' = 0."""
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """L'ultimo `weekday` del mese."""
    if month == 12:
        d = date(year, 12, 31)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    """Sabato -> venerdi' prima; domenica -> lunedi' dopo."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def federal_holidays(year: int) -> dict:
    """Le feste federali dell'anno: data -> nome."""
    out = {
        _observed(date(year, 1, 1)): "Capodanno",
        _nth_weekday(year, 1, 0, 3): "Martin Luther King",
        _nth_weekday(year, 2, 0, 3): "Washington's Birthday",
        _last_weekday(year, 5, 0): "Memorial Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 10, 0, 2): "Columbus Day",
        _observed(date(year, 11, 11)): "Veterans Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving",
        _observed(date(year, 12, 25)): "Natale",
    }
    #  Juneteenth e' festa federale dal 2021. Prima di allora non lo era, e
    #  metterla comunque marcherebbe come chiusi sei giorni che erano aperti.
    if year >= 2021:
        out[_observed(date(year, 6, 19))] = "Juneteenth"
    return out


def holiday_name(day: date) -> str | None:
    """Il nome della festa federale, oppure None.

    Guarda l'anno DEL GIORNO e quello successivo: se Capodanno cade di sabato
    l'osservanza slitta al 31 dicembre PRECEDENTE, quindi un 31 dicembre e' una
    festa che appartiene all'anno dopo. E' accaduto nel nostro intervallo --
    Capodanno 2022 era un sabato, e il 31 dicembre 2021 fu chiuso.
    """
    return (
        federal_holidays(day.year).get(day)
        or federal_holidays(day.year + 1).get(day)
    )


def is_filing_day(day: date) -> bool:
    """EDGAR accetta depositi in questo giorno?"""
    if day.weekday() >= 5:
        return False
    if holiday_name(day):
        return False
    return day.isoformat() not in CLOSURES


def reason(day: date, name: str | None = None) -> str:
    """Il nome del festivo o della chiusura, per il report."""
    hol = holiday_name(day)
    if hol:
        return hol
    return CLOSURES.get(day.isoformat(), name or "")


def why_missing(day: date, today: date) -> tuple:
    """Perche' l'indice di `day` non c'e'. Ritorna (esito, spiegazione).

    Va chiamato SOLO dopo che la lettura e' fallita: dice come classificare il
    fallimento, non se ci sara'.

    Il caso `NON_ANCORA` e' approssimato al giorno, non all'ora: l'indice di un
    giorno esce la sera ora di New York, quindi il giro del mattino non lo
    trova. Un giro lanciato prima delle quattro del mattino ora italiana
    vedrebbe come illeggibile anche l'indice di ieri, che a New York non e'
    ancora uscito. L'attivita' pianificata gira alle 8:00 e il caso non si
    presenta; se si presentasse, il giorno finirebbe fra i buchi -- cioe'
    dalla parte prudente.
    """
    if day.weekday() >= 5:
        return (WEEKEND, "")
    hol = holiday_name(day)
    if hol:
        return (FESTIVO, hol)
    closure = CLOSURES.get(day.isoformat())
    if closure:
        return (CHIUSURA, closure)
    if day >= today:
        return (NON_ANCORA, "l'indice del giorno esce la sera")
    return (ILLEGGIBILE, "")


def classify(days, today: date) -> dict:
    """Raggruppa per esito le date il cui indice non si e' letto.

    `days` sono stringhe ISO o date. Il risultato ha una chiave per esito, con
    la lista delle date e, quando c'e', la spiegazione.
    """
    out = {FESTIVO: [], CHIUSURA: [], NON_ANCORA: [], ILLEGGIBILE: [], WEEKEND: []}
    for d in days:
        day = date.fromisoformat(d) if isinstance(d, str) else d
        kind, why = why_missing(day, today)
        out[kind].append((day.isoformat(), why))
    return out
