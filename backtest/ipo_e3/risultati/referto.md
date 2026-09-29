# E3 — IPO rotte e IPO forti (USA, 2012-2024): referto

**In breve: nessuna delle due idee regge.**

## 1. IPO rotte — INCONCLUSIVO, perché la popolazione è rara

*La domanda:* un'IPO sana, crollata sotto il prezzo di collocamento, recupera contro società simili se la compro
quando le vendite finiscono e la tengo un anno?

Le IPO rotte trovate sono 195, ma quelle sane secondo i filtri sono solo 17. Il motivo principale è il flusso di
cassa: al giorno d'ingresso solo 41 su 194 avevano un flusso operativo positivo. Il criterio chiede almeno 80 casi in
8 anni; con 17 casi in 7 anni non si conclude, né in un senso né nell'altro. **Non mancano dati: un'IPO crollata che
genera cassa è un caso raro.**

I 17 casi che ci sono non fanno pensare a un recupero: a un anno la mediana è −22% contro i simili, e solo 5 su 17
li battono.

## 2. IPO forti — NON REGGE

*La domanda:* un'IPO che fino alla scadenza del lock-up non ha mai chiuso sotto il prezzo di collocamento batte
società simili nell'anno dopo?

Su 331 casi in 13 anni, per l'IPO tipica la risposta è no:
- mediana −9,5% contro i simili;
- solo il 42% li batte.

La media delle medie annuali è positiva, +12,4%. La tirano su pochi grandi vincitori, e
cambia molto da un anno all'altro: t = 1,07, ne serve almeno 2. Le forti del 2020-2021 perdono il 40% contro i simili.

Per confronto, l'IPO media fa peggio dei simili nell'anno dopo il lock-up (mediana −17%): le forti vanno meno
peggio, ma non battono le società comparabili.

## Da sapere prima di usare questi numeri

- 204 IPO sono escluse perché l'archivio dei prezzi segnala un salto sospetto. Fra loro ci sarebbero 58 rotte,
  probabilmente fra le peggiori.
- Il giorno d'ingresso delle rotte cade a un estremo nel 52% dei casi: la regola «fine delle vendite» spesso non
  scatta.
- Per 11 IPO le azioni in XBRL sono sbagliate, e i peer scelti sono microsocietà. Tolte, nessun verdetto cambia.

---

# Appendice

Generata da `backtest/ipo_e3/analisi.py` e `referto.py` (codice al commit `c5effba`). Regole: `2026-09-22_preregistrazione.md` e `2026-09-22_addendum_fermata1.md`; decisioni ADR-046 … ADR-052. Conteggi e imbuto: `risultati/conteggi.md`.

## A. Verdetti

| domanda | cella | casi | anni | mediana | media delle medie annuali | t (gradi) | 2012-18 | 2019-24 | placebo: media, t | esito |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. IPO rotte | B × 252 | 17 | 7 | -22.0% | -4.8% | -0.42 (6) | -10.4% | +9.2% | -6.6%, t -0.53 | **INCONCLUSIVO** |
| 2. IPO forti | forte × 252 | 331 | 13 | -9.5% | +12.4% | 1.07 (12) | +13.8% | +10.7% | -0.9%, t -0.09 | **NON REGGE** |

**1. IPO rotte — INCONCLUSIVO.** Criteri, nell'ordine:

- **falso** — 1. almeno 80 casi e almeno 8 anni
- **falso** — 2. mediana > 0
- **falso** — 3. media delle medie annuali > 0 con t ≥ 2
- **falso** — 4. media > 0 in 2012-2018 e in 2019-2024
- vero — 5. placebo con |t| < 2 e media più bassa

**2. IPO forti — NON REGGE.** Criteri, nell'ordine:

- vero — 1. almeno 80 casi e almeno 8 anni
- **falso** — 2. mediana > 0
- **falso** — 3. media delle medie annuali > 0 con t ≥ 2
- vero — 4. media > 0 in 2012-2018 e in 2019-2024
- vero — 5. placebo con |t| < 2 e media più bassa

## B. Medie per anno di coorte, celle del verdetto e placebo

| anno | B × 252: casi | media | B × placebo: casi | media | forte × 252: casi | media | forte × placebo: casi | media | base × 252: casi | media |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2012 | 1 | — | 1 | — | 23 | +18.9% | 23 | +14.4% | 60 | +7.0% |
| 2013 | 0 | — | 0 | — | 63 | -5.1% | 63 | -3.3% | 104 | -214.6% |
| 2014 | 2 | — | 2 | — | 41 | -3.3% | 41 | -19.8% | 114 | -1.8% |
| 2015 | 2 | — | 2 | — | 18 | +0.6% | 18 | +11.2% | 70 | -7.5% |
| 2016 | 0 | — | 0 | — | 22 | +14.0% | 21 | +25.2% | 49 | +5.3% |
| 2017 | 2 | — | 2 | — | 30 | +30.7% | 30 | -0.7% | 66 | +8.0% |
| 2018 | 3 | -42.1% | 3 | -8.9% | 26 | +40.9% | 26 | +70.5% | 66 | +24.1% |
| 2019 | 1 | — | 1 | — | 25 | +62.2% | 25 | -17.0% | 58 | +46.2% |
| 2020 | 0 | — | 0 | — | 48 | -49.8% | 48 | -50.4% | 84 | -36.4% |
| 2021 | 6 | -14.6% | 6 | +3.0% | 25 | -22.4% | 25 | -1.7% | 160 | -25.3% |
| 2022 | 0 | — | 0 | — | 1 | — | 1 | — | 17 | -3.0% |
| 2023 | 0 | — | 0 | — | 2 | — | 2 | — | 23 | -15.9% |
| 2024 | 0 | — | 0 | — | 7 | +42.9% | 7 | +31.0% | 31 | +13.2% |

## C. I casi della cella del verdetto 1 (rotte, B × 252)

17 casi in 7 anni di coorte (2012 1, 2014 2, 2015 2, 2017 2, 2018 3, 2019 1, 2021 6), tutti con esito «completo».
Mediana −22,0%, 5 casi su 17 positivi. *(Copia pubblica: la tabella per titolo — nome, ingresso, rendimento extra —
è stata tolta; le medie per anno stanno nella sezione B.)*

## D. Tutte le celle (descrittive, tranne le due del verdetto)

| cella | casi | anni | media | mediana | positivi | media delle medie annuali | t |
|---|---:|---:|---:|---:|---:|---:|---:|
| A × 63 | 1 | 1 | — | — | — | — | — |
| A × 126 | 1 | 1 | — | — | — | — | — |
| A × 252 | 1 | 1 | — | — | — | — | — |
| A × placebo | 1 | 1 | — | — | — | — | — |
| B × 63 | 17 | 7 | +3.5% | -1.5% | 47% | +6.4% | 1.44 |
| B × 126 | 17 | 7 | +5.4% | -3.8% | 47% | +8.1% | 0.80 |
| B × 252 | 17 | 7 | -12.4% | -22.0% | 29% | -4.8% | -0.42 |
| B × placebo | 17 | 7 | -5.1% | -3.6% | 41% | -6.6% | -0.53 |
| C × 63 | 18 | 6 | +0.5% | +0.5% | 56% | +0.8% | 0.27 |
| C × 126 | 18 | 6 | -2.9% | -10.9% | 33% | -3.7% | -0.46 |
| C × 252 | 18 | 6 | -16.0% | -22.0% | 33% | -16.2% | -2.29 |
| C × placebo | 18 | 6 | -6.3% | -11.9% | 44% | -10.6% | -0.80 |
| forte × 63 | 333 | 13 | +0.9% | -0.6% | 49% | +3.6% | 0.80 |
| forte × 126 | 333 | 13 | +2.3% | -1.8% | 48% | +8.1% | 1.23 |
| forte × 252 | 331 | 13 | +4.0% | -9.5% | 42% | +12.4% | 1.07 |
| forte × placebo | 330 | 13 | -2.7% | -10.7% | 42% | -0.9% | -0.09 |
| base × 63 | 905 | 13 | -21.9% | -3.8% | 44% | -14.1% | -1.02 |
| base × 126 | 905 | 13 | -24.6% | -6.8% | 42% | -15.0% | -0.93 |
| base × 252 | 902 | 13 | -27.4% | -16.9% | 37% | -15.4% | -0.88 |
| B × 252, coorte 2020-2021 | 6 | 1 | -14.6% | -26.0% | 17% | -14.6% | — |
| forte × 252, coorte 2020-2021 | 73 | 2 | -40.4% | -40.9% | 12% | -36.1% | -2.63 |
| base × 252, coorte 2020-2021 | 244 | 2 | -29.1% | -39.5% | 19% | -30.9% | -5.56 |

## E. Chi entra, chi esce, e come sono trattati i delistati

| cella | completo | delistato: prezzo dell'offerta | delistato: ultimo prezzo | fuori: buco all'uscita | fuori: finestra oltre i dati | fuori: senza prezzo all'ingresso |
|---|---:|---:|---:|---:|---:|---:|
| C × 63 | 18 | 0 | 0 | 0 | 0 | 0 |
| C × 126 | 18 | 0 | 0 | 0 | 0 | 0 |
| C × 252 | 18 | 0 | 0 | 0 | 0 | 0 |
| C × placebo | 18 | 0 | 0 | 0 | 0 | 0 |
| B × 63 | 17 | 0 | 0 | 0 | 0 | 0 |
| B × 126 | 17 | 0 | 0 | 0 | 0 | 0 |
| B × 252 | 17 | 0 | 0 | 0 | 0 | 0 |
| B × placebo | 16 | 1 | 0 | 0 | 0 | 0 |
| A × 63 | 1 | 0 | 0 | 0 | 0 | 0 |
| A × 126 | 1 | 0 | 0 | 0 | 0 | 0 |
| A × 252 | 1 | 0 | 0 | 0 | 0 | 0 |
| A × placebo | 1 | 0 | 0 | 0 | 0 | 0 |
| forte × 63 | 333 | 0 | 0 | 0 | 0 | 0 |
| forte × 126 | 332 | 0 | 1 | 0 | 0 | 0 |
| forte × 252 | 320 | 6 | 5 | 1 | 1 | 0 |
| forte × placebo | 315 | 10 | 5 | 1 | 1 | 1 |
| base × 63 | 903 | 2 | 0 | 0 | 0 | 0 |
| base × 126 | 898 | 2 | 5 | 0 | 0 | 0 |
| base × 252 | 874 | 13 | 15 | 2 | 1 | 0 |

Prezzo dell'offerta in contanti trovato per 141 titoli delistati su 267 cercati. Esiti dei peer: A ok: 1; A rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia): 16; B ok: 17; C ok: 18; base capitalizzazione non calcolabile: 37; base ok: 905; base rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia): 34; forte capitalizzazione non calcolabile: 17; forte ok: 333; forte rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia): 11.

## F. Finestre descrittive delle rotte (rendimento del titolo, non extra)

| popolazione | finestra | casi | mediana | media |
|---|---:|---:|---:|---:|
| tutte le rotte con un ingresso B | collocamento → S − 10 | 194 | -42.8% | -42.7% |
| tutte le rotte con un ingresso B | S − 10 → S + 10 | 194 | -12.4% | -10.1% |
| tutte le rotte con un ingresso B | S + 10 → ingresso B | 193 | -5.7% | -6.8% |
| rotte della cella del verdetto | collocamento → S − 10 | 17 | -41.1% | -38.4% |
| rotte della cella del verdetto | S − 10 → S + 10 | 17 | -17.0% | -10.9% |
| rotte della cella del verdetto | S + 10 → ingresso B | 17 | -4.7% | -2.3% |

## G. Spaccato insider (cella B × 252, descrittivo)

Attesa registrata prima dei rendimenti: il gruppo con vendite di dirigenti o amministratori fra la scadenza del lock-up e l'ingresso fa peggio.

| gruppo | casi | mediana | media |
|---|---:|---:|---:|
| con vendite | 8 | +2.5% | +8.5% |
| senza vendite | 9 | -27.9% | -31.0% |

*(Copia pubblica: tolto l'elenco per titolo con nome, rendimento extra e numero di vendite.)*

## H. Sensibilità post hoc: capitalizzazioni XBRL assurde (non decide niente)

Trovata dopo i rendimenti, guardando i valori estremi (`sensibilita.py`). Per 11 IPO le azioni in XBRL danno una capitalizzazione sotto un decimo di quella del prospetto, a volte di poche migliaia di dollari, e i peer scelti sono microsocietà con serie rotte. Le celle rifatte senza quei casi:

| cella | casi | mediana | media delle medie annuali | t |
|---|---:|---:|---:|---:|
| B × 252 | 17 | -22.0% | -4.8% | -0.42 |
| B × placebo | 17 | -3.6% | -6.6% | -0.53 |
| forte × 252 | 329 | -9.5% | +11.8% | 1.04 |
| forte × placebo | 328 | -10.6% | -0.2% | -0.02 |
| base × 63 | 894 | -3.8% | -0.5% | -0.26 |
| base × 126 | 894 | -7.1% | -0.1% | -0.02 |
| base × 252 | 891 | -16.8% | +0.8% | 0.14 |

Verdetti con le stesse regole: 1. IPO rotte INCONCLUSIVO; 2. IPO forti NON REGGE. Casi tolti: 11 IPO (rapporto fra capitalizzazione XBRL e del prospetto fra 0,0000× e 0,0698×; elenco per nome tolto nella copia pubblica).

## I. Limiti dichiarati

- **IPO tolte per `salto_sospetto`** (addendum, punto 7): 204 IPO escono perché l'archivio toglie la loro storia fino a un salto non verificato. Sulle chiusure grezze sarebbero state 58 rotte e 31 forti: il campione delle rotte perde soprattutto le peggiori.
- **Giorno B degenere** (punto 8): oltre metà delle rotte entra al primo giorno possibile o all'ingresso forzato (`conteggi.md` §4).
- **Peer:** la coerenza della serie con un prezzo di riferimento (ADR-051) non si può controllare; il SIC usato per togliere banche e REIT è quello di oggi.
- **Capitalizzazioni XBRL** assurde per alcune IPO: sezione H.

## J. Chiamate EDGAR

2699 su 3000.

