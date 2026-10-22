# Referto — Test G, scadenza delle put spread (fermata 2) — BOZZA per la revisione dell'utente

**4 ottobre 2026.** Calcolato come pre-registrato in `backtest/drawdown_alpha/2026-10-04_preregistrazione_test_g.md`
(ADR-072..074; composito corretto da ADR-071), approvata e congelata prima di qualunque rendimento. Script:
`backtest/drawdown_alpha/test_g.py` (simulazione, misure, verdetti, controlli), che riusa `test_g_dati.py` (prezzo
Black-Scholes con q = 2%, strike, scadenza, buchi, parte coperta), `test_f.py` (composito, Faber), `eventi_f.py` (lista
A dei ribassi) ed `episodi.py` (definizione di ribasso). Le tabelle qui sotto sono l'uscita del programma, riportata
com'è; nessun numero scritto a mano. Dati solo da `market_data.api`. **Nessun risultato va tradotto in regola di
portafoglio senza una decisione dell'utente.** Il registro dei verdetti (`data/verdicts.jsonl`) non è stato toccato.

## I due verdetti

**I verdetti sono due, indipendenti, uno per versione di budget. Le combinazioni guardate sono 32 (2 con verdetto, 30
descrittive); con le sensibilità le serie guardate sono 160.** Dopo aver visto i risultati, su richiesta dell'utente,
ne sono state guardate altre **17, tutte descrittive e dichiarate nelle loro sezioni**: 1 (Faber × 3 mesi della versione B
con la copertura limitata al 100%) e 16 (regole 2 e 3 con la vecchia lettura del composito). **Totale guardato: 177
serie.** Nessuna delle 17 entra in un verdetto.

| versione | cella | riduzione media dei tre ribassi peggiori (non arrotondata) | soglie | costo in punti di rendimento annuo (non arrotondato) | soglie | verdetto |
|---|---|---:|---|---:|---|---|
| A | regola 3 × 12 mesi | 0,1241753648 | REGGE ≥ 0,3333333333 ; NON REGGE < 0,2000000000 | -0,0025802633 | REGGE ≤ 1,5 ; NON REGGE > 3 | **NON REGGE** |
| B | regola 3 × 3 mesi | 0,0820774173 | REGGE ≥ 0,3333333333 ; NON REGGE < 0,2000000000 | 0,3335297873 | REGGE ≤ 1,5 ; NON REGGE > 3 | **NON REGGE** |

- **Versione A (regola 3 × 12 mesi): NON REGGE.** Riduzione media dei tre ribassi peggiori **0,1241753648**: sotto 1/5
  (0,2), quindi è vera la prima condizione di NON REGGE; sotto anche 1/3. Costo **−0,0025802633** punti di rendimento
  annuo (il portafoglio protetto rende 0,0026 punti *più* di quello senza protezione): sotto 1,5 e sotto 3, la seconda
  condizione di NON REGGE non è vera. Basta la prima.
- **Versione B (regola 3 × 3 mesi): NON REGGE.** Riduzione media **0,0820774173**: sotto 1/5. Costo **0,3335297873**
  punti: sotto 1,5 e sotto 3. Basta la prima condizione.

In entrambe le celle il verdetto viene dalla riduzione, non dal costo. Le soglie sono confrontate sui numeri non
arrotondati (regola: REGGE se riduzione ≥ 1/3 e costo ≤ 1,5; NON REGGE se riduzione < 1/5 o costo > 3; INCONCLUSIVO
altrimenti).

## Dati letti

- GSPC.INDX: 24806 sedute nell'archivio, 1927-12-30 → 2026-10-02; nel periodo 9067 sedute, 1990-01-02 → 2025-12-31 (13147 giorni di calendario).
- VIXCLS: 9286 osservazioni, 1990-01-02 → 2026-10-01; DTB3: 18179 osservazioni, 1954-01-04 → 2026-10-01.
- VIXCLS: sedute del periodo senza il dato del giorno 3; età massima del valore usato 1 giorni; sedute in cui il valore cambierebbe usando anche le osservazioni in giorni senza seduta: 0.
- DTB3: sedute del periodo senza il dato del giorno 75; età massima del valore usato 3 giorni; sedute in cui il valore cambierebbe usando anche le osservazioni in giorni senza seduta: 0.
- Letture mensili (1989-12-31 → 2025-11-30): 432; senza composito 0; senza Faber 0; regola 3 senza la mediana del VIX (finestra non intera) 9.
- regola 2 composito ≥ 3: letture accese 96 su 432 (prima 1989-12-31, ultima 2025-10-31).
- regola 3 composito ≥ 3 e VIX sotto la mediana: letture accese 42 su 432 (prima 1991-01-31, ultima 2025-09-30).
- regola 4 Faber: letture accese 103 su 432 (prima 1990-01-31, ultima 2025-04-30).
- regola 3: letture con composito ≥ 3 in cui il confronto VIX/mediana cambierebbe contando anche le osservazioni del VIX in giorni senza seduta di GSPC: 0.

## Il portafoglio senza protezione e i suoi tre ribassi peggiori

Valore finale 1903,1666 (da 100); rendimento annuo 8,5231%; ribasso massimo -56,78%.

| # | massimo | fondo | profondità senza protezione |
|---|---|---|---:|
| 1 | 2007-10-09 (1565,15) | 2009-03-09 (676,53) | -56,78% |
| 2 | 2000-03-24 (1527,46) | 2002-10-09 (776,76) | -49,15% |
| 3 | 2020-02-19 (3386,15) | 2020-03-23 (2237,40) | -33,92% |

Sono gli stessi tre episodi indicati nella pre-registrazione (massimi 2007-10-09, 2000-03-24, 2020-02-19), ricalcolati
con `episodi.episodi_drawdown` sul portafoglio senza protezione dal 1990-01-02 e non assunti.

### Con protezione, ribasso per ribasso, nelle due celle del verdetto

Profondità con protezione = valore al fondo / valore al massimo − 1 del portafoglio protetto, sulle **stesse due date**
del portafoglio senza protezione. Riduzione = 1 − profondità con / profondità senza. L'ultima colonna è descrittiva.

| versione, cella | massimo → fondo | senza protezione | con protezione (stesse date) | riduzione | ribasso massimo del protetto nella finestra (descrittivo) |
|---|---|---:|---:|---:|---:|
| A, regola 3 × 12 mesi | 2007-10-09 → 2009-03-09 | -56,78% | -44,77% | 21,14% | -44,77% |
| A, regola 3 × 12 mesi | 2000-03-24 → 2002-10-09 | -49,15% | -41,23% | 16,12% | -41,23% |
| A, regola 3 × 12 mesi | 2020-02-19 → 2020-03-23 | -33,92% | -33,92% | 0,00% | -33,92% |
| A, regola 3 × 12 mesi | **media semplice delle tre riduzioni** | | | **12,42%** | |
| B, regola 3 × 3 mesi | 2007-10-09 → 2009-03-09 | -56,78% | -40,17% | 29,24% | -40,17% |
| B, regola 3 × 3 mesi | 2000-03-24 → 2002-10-09 | -49,15% | -51,42% | -4,62% | -51,42% |
| B, regola 3 × 3 mesi | 2020-02-19 → 2020-03-23 | -33,92% | -33,92% | 0,00% | -33,92% |
| B, regola 3 × 3 mesi | **media semplice delle tre riduzioni** | | | **8,21%** | |

Cosa c'era aperto (dalla tabella delle operazioni in fondo):

- **A, 2007-09**: l'operazione n. 6 (2008-05-01 → 2009-05-01, parte coperta 74%) è aperta al fondo del 2009-03-09 e a
  scadenza vale il massimo (20% della chiusura di ingresso, incasso 4,94 volte il premio).
- **A, 2000-02**: l'operazione n. 2 (2000-03-01 → 2001-03-01) scade con l'indice fra i due strike (5,00% della chiusura
  di ingresso, incasso 1,47 volte il premio); la n. 3 (2001-12-03 → 2002-12-03) è aperta al fondo del 2002-10-09. Fra il
  2001-03-01 e il 2001-12-03 non c'è nessuna operazione aperta.
- **A, 2020**: l'operazione n. 9 (2019-03-01 → 2020-02-28) è aperta al massimo del 2020-02-19 ma scade il 2020-02-28
  con l'indice a 2.954,22, sopra lo strike comprato: vale zero. Al fondo del 2020-03-23 non c'è nessuno spread aperto.
- **B, 2007-09**: le operazioni n. 10 e n. 11 (2008-05-01 → 2008-08-01 → 2008-10-31) incassano 3,25 e 8,01 volte il
  premio; dal 2008-10-31 al 2009-05-01 non c'è nessuna operazione aperta, fondo del 2009-03-09 compreso.
- **B, 2000-02**: quattro operazioni (la n. 3 già aperta al massimo, le n. 4-6 aperte dopo); tre scadono a zero e una
  (n. 5) incassa 1,51 volte il premio; dal 2002-03-01 al fondo del 2002-10-09 non c'è nessuna operazione aperta. Il
  portafoglio protetto scende più di quello senza protezione (−51,42% contro −49,15%): riduzione negativa.
- **B, 2020**: nessuna operazione aperta fra il 2019-10-01 e il 2022-08-01.

Per le altre celle, in forma compatta — profondità con protezione sulle stesse date, e fra parentesi la riduzione:

| versione | regola | scadenza | 2007-10-09 → 2009-03-09 | 2000-03-24 → 2002-10-09 | 2020-02-19 → 2020-03-23 | media delle riduzioni |
|---|---|---|---:|---:|---:|---:|
| A | 1 | 3 mesi | -47,1% (17,1%) | -31,8% (35,2%) | -29,9% (11,9%) | 21,4% |
| A | 1 | 6 mesi | -44,5% (21,7%) | -43,0% (12,5%) | -5,9% (82,5%) | 38,9% |
| A | 1 | 9 mesi | -45,7% (19,5%) | -33,0% (32,9%) | -15,7% (53,6%) | 35,3% |
| A | 1 | 12 mesi | -47,1% (17,1%) | -39,0% (20,7%) | -19,7% (42,1%) | 26,6% |
| A | 2 | 3 mesi | -48,8% (14,0%) | -51,0% (-3,8%) | -33,9% (0,0%) | 3,4% |
| A | 2 | 6 mesi | -44,1% (22,4%) | -40,0% (18,7%) | -33,9% (0,0%) | 13,7% |
| A | 2 | 9 mesi | -50,1% (11,8%) | -47,9% (2,6%) | -33,9% (0,0%) | 4,8% |
| A | 2 | 12 mesi | -48,1% (15,3%) | -47,6% (3,2%) | -33,9% (0,0%) | 6,2% |
| A | 3 | 3 mesi | -48,7% (14,2%) | -50,3% (-2,3%) | -33,9% (0,0%) | 4,0% |
| A | 3 | 6 mesi | -44,9% (20,9%) | -38,6% (21,6%) | -33,9% (0,0%) | 14,2% |
| A | 3 | 9 mesi | -45,7% (19,5%) | -35,7% (27,4%) | -33,9% (0,0%) | 15,6% |
| A | 3 | 12 mesi | -44,8% (21,1%) | -41,2% (16,1%) | -33,9% (0,0%) | 12,4% |
| A | 4 | 3 mesi | -50,6% (10,9%) | -35,8% (27,2%) | -29,8% (12,3%) | 16,8% |
| A | 4 | 6 mesi | -45,4% (20,0%) | -29,0% (41,0%) | -28,8% (15,1%) | 25,4% |
| A | 4 | 9 mesi | -50,1% (11,8%) | -37,8% (23,1%) | -29,8% (12,2%) | 15,7% |
| A | 4 | 12 mesi | -45,9% (19,1%) | -32,0% (34,8%) | -30,3% (10,8%) | 21,6% |
| B | 1 | 3 mesi | -36,3% (36,0%) | -11,5% (76,6%) | -25,7% (24,2%) | 45,6% |
| B | 1 | 6 mesi | -44,5% (21,7%) | -43,0% (12,5%) | -5,9% (82,5%) | 38,9% |
| B | 1 | 9 mesi | -45,7% (19,5%) | -33,0% (32,9%) | -15,7% (53,6%) | 35,3% |
| B | 1 | 12 mesi | -47,1% (17,1%) | -39,0% (20,7%) | -19,7% (42,1%) | 26,6% |
| B | 2 | 3 mesi | -40,4% (28,8%) | -52,9% (-7,6%) | -33,9% (0,0%) | 7,1% |
| B | 2 | 6 mesi | -44,1% (22,4%) | -40,0% (18,7%) | -33,9% (0,0%) | 13,7% |
| B | 2 | 9 mesi | -50,1% (11,8%) | -47,9% (2,6%) | -33,9% (0,0%) | 4,8% |
| B | 2 | 12 mesi | -48,1% (15,3%) | -47,6% (3,2%) | -33,9% (0,0%) | 6,2% |
| B | 3 | 3 mesi | -40,2% (29,2%) | -51,4% (-4,6%) | -33,9% (0,0%) | 8,2% |
| B | 3 | 6 mesi | -44,9% (20,9%) | -38,6% (21,6%) | -33,9% (0,0%) | 14,2% |
| B | 3 | 9 mesi | -45,7% (19,5%) | -35,7% (27,4%) | -33,9% (0,0%) | 15,6% |
| B | 3 | 12 mesi | -44,8% (21,1%) | -41,2% (16,1%) | -33,9% (0,0%) | 12,4% |
| B | 4 | 3 mesi | -43,9% (22,6%) | -20,6% (58,0%) | -25,6% (24,5%) | 35,1% |
| B | 4 | 6 mesi | -45,4% (20,0%) | -29,0% (41,0%) | -28,8% (15,1%) | 25,4% |
| B | 4 | 9 mesi | -50,1% (11,8%) | -37,8% (23,1%) | -29,8% (12,2%) | 15,7% |
| B | 4 | 12 mesi | -45,9% (19,1%) | -32,0% (34,8%) | -30,3% (10,8%) | 21,6% |

## Le due griglie 4 × 4

Rendimento annuo = (valore finale / 100)^(365 / 13.147 giorni) − 1; ribasso massimo sulla serie propria di ciascun
portafoglio; costo = rendimento annuo senza protezione − rendimento annuo con protezione, in punti (negativo = il
portafoglio protetto ha reso di più); premio annuo speso = somma dei premi in percentuale del portafoglio nel giorno di
ingresso, divisa per gli anni del periodo. Solo le due celle in grassetto hanno un verdetto; le altre 30 sono
descrittive e non ricevono etichette.

### Versione A — budget annuo uguale (premio 1,5% a 3 mesi, 3% a 6, 9 e 12; tetto 6% sui 360 giorni precedenti)

| regola | scadenza | rendimento annuo | ribasso massimo | riduzione media dei tre ribassi peggiori | costo (punti) | premio annuo speso | operazioni |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 sempre accesa | 3 mesi | 4,95% | -47,8% | 21,4% | +3,576 | 6,04% | 145 |
| 1 sempre accesa | 6 mesi | 3,85% | -56,1% | 38,9% | +4,677 | 6,08% | 73 |
| 1 sempre accesa | 9 mesi | 6,42% | -45,7% | 35,3% | +2,107 | 4,08% | 49 |
| 1 sempre accesa | 12 mesi | 6,87% | -47,6% | 26,6% | +1,658 | 3,08% | 37 |
| 2 composito ≥ 3 | 3 mesi | 8,12% | -53,8% | 3,4% | +0,399 | 1,54% | 37 |
| 2 composito ≥ 3 | 6 mesi | 8,31% | -45,0% | 13,7% | +0,209 | 2,00% | 24 |
| 2 composito ≥ 3 | 9 mesi | 7,93% | -52,2% | 4,8% | +0,597 | 1,58% | 19 |
| 2 composito ≥ 3 | 12 mesi | 7,93% | -49,3% | 6,2% | +0,595 | 1,33% | 16 |
| 3 composito ≥ 3 e VIX sotto la mediana | 3 mesi | 8,39% | -50,9% | 4,0% | +0,133 | 0,92% | 22 |
| 3 composito ≥ 3 e VIX sotto la mediana | 6 mesi | 8,84% | -44,9% | 14,2% | -0,321 | 1,17% | 14 |
| 3 composito ≥ 3 e VIX sotto la mediana | 9 mesi | 8,95% | -45,7% | 15,6% | -0,427 | 1,17% | 14 |
| **3 composito ≥ 3 e VIX sotto la mediana** | **12 mesi — verdetto** | 8,53% | -44,8% | 12,4% | -0,003 | 1,00% | 12 |
| 4 Faber | 3 mesi | 8,00% | -50,6% | 16,8% | +0,520 | 1,79% | 43 |
| 4 Faber | 6 mesi | 7,89% | -45,4% | 25,4% | +0,632 | 2,25% | 27 |
| 4 Faber | 9 mesi | 7,91% | -50,1% | 15,7% | +0,613 | 1,83% | 22 |
| 4 Faber | 12 mesi | 8,38% | -45,9% | 21,6% | +0,144 | 1,58% | 19 |

### Versione B — premio fisso (3% per ogni operazione, nessun tetto)

| regola | scadenza | rendimento annuo | ribasso massimo | riduzione media dei tre ribassi peggiori | costo (punti) | premio annuo speso | operazioni |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 sempre accesa | 3 mesi | 1,23% | -45,4% | 45,6% | +7,290 | 12,08% | 145 |
| 1 sempre accesa | 6 mesi | 3,85% | -56,1% | 38,9% | +4,677 | 6,08% | 73 |
| 1 sempre accesa | 9 mesi | 6,42% | -45,7% | 35,3% | +2,107 | 4,08% | 49 |
| 1 sempre accesa | 12 mesi | 6,87% | -47,6% | 26,6% | +1,658 | 3,08% | 37 |
| 2 composito ≥ 3 | 3 mesi | 7,63% | -52,9% | 7,1% | +0,890 | 3,08% | 37 |
| 2 composito ≥ 3 | 6 mesi | 8,31% | -45,0% | 13,7% | +0,209 | 2,00% | 24 |
| 2 composito ≥ 3 | 9 mesi | 7,93% | -52,2% | 4,8% | +0,597 | 1,58% | 19 |
| 2 composito ≥ 3 | 12 mesi | 7,93% | -49,3% | 6,2% | +0,595 | 1,33% | 16 |
| **3 composito ≥ 3 e VIX sotto la mediana** | **3 mesi — verdetto** | 8,19% | -51,4% | 8,2% | +0,334 | 1,83% | 22 |
| 3 composito ≥ 3 e VIX sotto la mediana | 6 mesi | 8,84% | -44,9% | 14,2% | -0,321 | 1,17% | 14 |
| 3 composito ≥ 3 e VIX sotto la mediana | 9 mesi | 8,95% | -45,7% | 15,6% | -0,427 | 1,17% | 14 |
| 3 composito ≥ 3 e VIX sotto la mediana | 12 mesi | 8,53% | -44,8% | 12,4% | -0,003 | 1,00% | 12 |
| 4 Faber | 3 mesi | 7,39% | -43,9% | 35,1% | +1,136 | 3,58% | 43 |
| 4 Faber | 6 mesi | 7,89% | -45,4% | 25,4% | +0,632 | 2,25% | 27 |
| 4 Faber | 9 mesi | 7,91% | -50,1% | 15,7% | +0,613 | 1,83% | 22 |
| 4 Faber | 12 mesi | 8,38% | -45,9% | 21,6% | +0,144 | 1,58% | 19 |

## Coincidenza fra A e B — verificata con i numeri

La pre-registrazione prevedeva che a 9 e a 12 mesi le celle di A e di B coincidessero, e che a 6 mesi differissero
solo se il tetto bloccava. Verifica cella per cella: stesse date di ingresso e massima differenza fra i due valori
giornalieri del portafoglio su tutte le 9.067 sedute.

| regola | scadenza | operazioni A / B | stesse date di ingresso | massima differenza del valore giornaliero | riduzione A / B | costo A / B | coincidono |
|---|---|---|---|---:|---|---|---|
| 1 | 3 mesi | 145 / 145 | sì | 420 | 21,42% / 45,57% | +3,576 / +7,290 | no |
| 2 | 3 mesi | 37 / 37 | sì | 255 | 3,40% / 7,08% | +0,399 / +0,890 | no |
| 3 | 3 mesi | 22 / 22 | sì | 119 | 3,96% / 8,21% | +0,133 / +0,334 | no |
| 4 | 3 mesi | 43 / 43 | sì | 302 | 16,79% / 35,06% | +0,520 / +1,136 | no |
| 1 | 6 mesi | 73 / 73 | sì | 0 | 38,88% / 38,88% | +4,677 / +4,677 | **sì** |
| 2 | 6 mesi | 24 / 24 | sì | 0 | 13,69% / 13,69% | +0,209 / +0,209 | **sì** |
| 3 | 6 mesi | 14 / 14 | sì | 0 | 14,15% / 14,15% | -0,321 / -0,321 | **sì** |
| 4 | 6 mesi | 27 / 27 | sì | 0 | 25,36% / 25,36% | +0,632 / +0,632 | **sì** |
| 1 | 9 mesi | 49 / 49 | sì | 0 | 35,33% / 35,33% | +2,107 / +2,107 | **sì** |
| 2 | 9 mesi | 19 / 19 | sì | 0 | 4,78% / 4,78% | +0,597 / +0,597 | **sì** |
| 3 | 9 mesi | 14 / 14 | sì | 0 | 15,63% / 15,63% | -0,427 / -0,427 | **sì** |
| 4 | 9 mesi | 22 / 22 | sì | 0 | 15,68% / 15,68% | +0,613 / +0,613 | **sì** |
| 1 | 12 mesi | 37 / 37 | sì | 0 | 26,64% / 26,64% | +1,658 / +1,658 | **sì** |
| 2 | 12 mesi | 16 / 16 | sì | 0 | 6,18% / 6,18% | +0,595 / +0,595 | **sì** |
| 3 | 12 mesi | 12 / 12 | sì | 0 | 12,42% / 12,42% | -0,003 / -0,003 | **sì** |
| 4 | 12 mesi | 19 / 19 | sì | 0 | 21,58% / 21,58% | +0,144 / +0,144 | **sì** |

Cella del verdetto A (regola 3 × 12 mesi) contro la cella regola 3 × 12 mesi di B: riduzione 0,1241753648 contro 0,1241753648; costo -0,0025802633 contro -0,0025802633; differenze 0 e 0.

- **La cella del verdetto di A (regola 3 × 12 mesi) coincide con la cella descrittiva regola 3 × 12 mesi di B**: 12
  operazioni con le stesse date, differenza massima del valore giornaliero 0, stessa riduzione e stesso costo fino
  all'ultima cifra. **Perché**: a 12 mesi il premio è 3% in entrambe le versioni e il tetto della versione A non ha
  mai bloccato un ingresso (tabella sotto), quindi le due simulazioni fanno le stesse operazioni.
- **Coincidono tutte le 12 celle a 6, 9 e 12 mesi**, per la stessa ragione: stesso premio (3%), nessun blocco del tetto.
- **Non coincidono le 4 celle a 3 mesi**: stesse date di ingresso, ma il premio è 1,5% in A e 3% in B.
- Le celle che coincidono restano contate: 32 combinazioni e 160 serie guardate, come pre-registrato (più le 17
  aggiunte dopo, dichiarate in testa). Le serie
  *diverse* fra loro sono 20 su 32 (16 di A più le 4 a 3 mesi di B).

### Quante volte il tetto della versione A ha bloccato o fatto slittare un ingresso

| regola | scadenza | sedute (regola 1) o letture mensili (regole 2-4) bloccate dal tetto | ingressi slittati | dettaglio |
|---|---|---:|---:|---|
| 1 | 3 mesi | 0 | 0 | — |
| 1 | 6 mesi | 0 | 0 | — |
| 1 | 9 mesi | 0 | 0 | — |
| 1 | 12 mesi | 0 | 0 | — |
| 2 | 3 mesi | 0 | 0 | — |
| 2 | 6 mesi | 0 | 0 | — |
| 2 | 9 mesi | 0 | 0 | — |
| 2 | 12 mesi | 0 | 0 | — |
| 3 | 3 mesi | 0 | 0 | — |
| 3 | 6 mesi | 0 | 0 | — |
| 3 | 9 mesi | 0 | 0 | — |
| 3 | 12 mesi | 0 | 0 | — |
| 4 | 3 mesi | 0 | 0 | — |
| 4 | 6 mesi | 0 | 0 | — |
| 4 | 9 mesi | 0 | 0 | — |
| 4 | 12 mesi | 0 | 0 | — |

Versione B: nessun tetto; ingressi bloccati 0.

**Mai**, in nessuna delle 16 celle. Nella regola 1 a 3 mesi lo scarto minimo fra un ingresso e il quarto successivo è
di 361 giorni e a 6 mesi lo scarto minimo fra un ingresso e il secondo successivo è di 363 giorni (calcolo di controllo
sulle date di ingresso del programma): sopra i 360, quindi il caso previsto come possibile nella pre-registrazione
(«può slittare di qualche seduta») non si è presentato.

## Guadagno delle put nei ribassi della lista A del Test F

Per ogni evento: incassi a scadenza ricevuti dopo il massimo P ed entro il fondo F, più il valore di modello dello
spread aperto in F, meno il valore di modello dello spread aperto in P, meno i premi pagati dopo P ed entro F; diviso
per il valore del portafoglio protetto in P. La lista (10 eventi con massimo dal 1990) è riletta da
`eventi_f.eventi_12_mesi`.

| # | massimo | fondo | profondità dell'indice | A, regola 3 × 12 mesi | B, regola 3 × 3 mesi |
|---|---|---|---:|---:|---:|
| 1 | 1990-07-16 | 1990-10-11 | -19,9% | +0,00% | +0,00% |
| 2 | 1998-07-17 | 1998-08-31 | -19,3% | +0,00% | +0,00% |
| 3 | 2000-03-24 | 2002-10-09 | -49,1% | +7,97% | -4,10% |
| 4 | 2007-10-09 | 2009-03-09 | -56,8% | +10,60% | +24,35% |
| 5 | 2010-04-23 | 2010-07-02 | -16,0% | +0,00% | +0,00% |
| 6 | 2011-04-29 | 2011-10-03 | -19,4% | +0,00% | +0,00% |
| 7 | 2018-09-20 | 2018-12-24 | -19,8% | +0,00% | +0,00% |
| 8 | 2020-02-19 | 2020-03-23 | -33,9% | +0,00% | +0,00% |
| 9 | 2022-01-03 | 2022-10-12 | -25,4% | +2,43% | +6,97% |
| 10 | 2025-02-19 | 2025-04-08 | -18,9% | +0,00% | +0,00% |

Nelle due celle del verdetto la regola 3 ha uno spread aperto, o ne apre uno, in tre eventi su dieci (2000, 2007,
2022); negli altri sette il guadagno è zero (arrotondato a due decimali): fra massimo e fondo non c'è nessuna
operazione oppure, nella cella A nel 2010 e nel 2020, quella aperta al massimo scade a zero pochi giorni dopo (n. 7 il
2010-04-30, n. 9 il 2020-02-28). Nel 2000 la cella B ha un guadagno negativo (premi pagati più degli incassi).

Tutte le 32 celle, in punti percentuali del portafoglio protetto al massimo:

| versione | regola | scadenza | 1990 | 1998 | 2000 | 2007 | 2010 | 2011 | 2018 | 2020 | 2022 | 2025 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1 | 3 mesi | +12,6 | +9,5 | +20,0 | +11,9 | +0,8 | +2,3 | +7,2 | +4,0 | +4,0 | +10,3 |
| A | 1 | 6 mesi | +19,2 | +11,0 | +4,8 | +13,1 | +1,1 | +5,9 | +7,9 | +27,9 | +5,5 | +18,2 |
| A | 1 | 9 mesi | +12,3 | +6,6 | +18,4 | +11,5 | +5,4 | +1,9 | +11,7 | +17,9 | +3,0 | +6,6 |
| A | 1 | 12 mesi | +13,7 | +2,4 | +10,6 | +10,6 | +3,4 | +5,3 | +4,6 | +13,9 | +5,7 | +10,7 |
| A | 2 | 3 mesi | +10,1 | +0,0 | -3,4 | +11,0 | +0,0 | +0,0 | +10,6 | +0,0 | +3,5 | -0,1 |
| A | 2 | 6 mesi | +19,2 | +0,0 | +14,0 | +15,9 | +0,0 | +0,0 | +10,0 | +0,0 | +4,0 | +12,4 |
| A | 2 | 9 mesi | +10,6 | +0,0 | +1,0 | +6,9 | +0,0 | +0,0 | +7,1 | +0,0 | +3,0 | +0,0 |
| A | 2 | 12 mesi | +13,7 | +0,0 | +2,0 | +11,0 | +0,0 | +0,0 | +5,7 | +0,0 | +2,4 | +7,4 |
| A | 3 | 3 mesi | +0,0 | +0,0 | -2,0 | +11,8 | +0,0 | +0,0 | +0,0 | +0,0 | +3,5 | +0,0 |
| A | 3 | 6 mesi | +0,0 | +0,0 | +16,1 | +16,1 | +0,0 | +0,0 | +0,0 | +0,0 | +4,0 | +0,0 |
| A | 3 | 9 mesi | +0,0 | +0,0 | +15,6 | +12,4 | +0,0 | +0,0 | +0,0 | +0,0 | +3,0 | +0,0 |
| A | 3 | 12 mesi | +0,0 | +0,0 | +8,0 | +10,6 | +0,0 | +0,0 | +0,0 | +0,0 | +2,4 | +0,0 |
| A | 4 | 3 mesi | +1,4 | +0,0 | +16,0 | +6,9 | +0,0 | +1,3 | +6,2 | +3,8 | -0,7 | +4,9 |
| A | 4 | 6 mesi | +2,0 | +0,0 | +22,4 | +12,0 | +0,2 | +1,7 | +6,7 | +4,4 | +1,2 | +5,7 |
| A | 4 | 9 mesi | +4,9 | +0,0 | +12,3 | +6,9 | +0,1 | +1,3 | +4,8 | +3,4 | +2,2 | +4,5 |
| A | 4 | 12 mesi | +5,4 | +0,0 | +19,5 | +11,6 | +0,1 | +1,2 | +4,0 | +2,9 | +1,5 | +3,9 |
| B | 1 | 3 mesi | +25,7 | +19,2 | +43,1 | +24,8 | +1,7 | +4,6 | +14,3 | +8,1 | +7,8 | +20,6 |
| B | 1 | 6 mesi | +19,2 | +11,0 | +4,8 | +13,1 | +1,1 | +5,9 | +7,9 | +27,9 | +5,5 | +18,2 |
| B | 1 | 9 mesi | +12,3 | +6,6 | +18,4 | +11,5 | +5,4 | +1,9 | +11,7 | +17,9 | +3,0 | +6,6 |
| B | 1 | 12 mesi | +13,7 | +2,4 | +10,6 | +10,6 | +3,4 | +5,3 | +4,6 | +13,9 | +5,7 | +10,7 |
| B | 2 | 3 mesi | +20,7 | +0,0 | -6,8 | +22,5 | +0,0 | +0,0 | +21,3 | +0,0 | +7,0 | -0,1 |
| B | 2 | 6 mesi | +19,2 | +0,0 | +14,0 | +15,9 | +0,0 | +0,0 | +10,0 | +0,0 | +4,0 | +12,4 |
| B | 2 | 9 mesi | +10,6 | +0,0 | +1,0 | +6,9 | +0,0 | +0,0 | +7,1 | +0,0 | +3,0 | +0,0 |
| B | 2 | 12 mesi | +13,7 | +0,0 | +2,0 | +11,0 | +0,0 | +0,0 | +5,7 | +0,0 | +2,4 | +7,4 |
| B | 3 | 3 mesi | +0,0 | +0,0 | -4,1 | +24,4 | +0,0 | +0,0 | +0,0 | +0,0 | +7,0 | +0,0 |
| B | 3 | 6 mesi | +0,0 | +0,0 | +16,1 | +16,1 | +0,0 | +0,0 | +0,0 | +0,0 | +4,0 | +0,0 |
| B | 3 | 9 mesi | +0,0 | +0,0 | +15,6 | +12,4 | +0,0 | +0,0 | +0,0 | +0,0 | +3,0 | +0,0 |
| B | 3 | 12 mesi | +0,0 | +0,0 | +8,0 | +10,6 | +0,0 | +0,0 | +0,0 | +0,0 | +2,4 | +0,0 |
| B | 4 | 3 mesi | +2,8 | +0,0 | +33,7 | +14,2 | +0,1 | +2,6 | +12,5 | +7,6 | -1,5 | +9,7 |
| B | 4 | 6 mesi | +2,0 | +0,0 | +22,4 | +12,0 | +0,2 | +1,7 | +6,7 | +4,4 | +1,2 | +5,7 |
| B | 4 | 9 mesi | +4,9 | +0,0 | +12,3 | +6,9 | +0,1 | +1,3 | +4,8 | +3,4 | +2,2 | +4,5 |
| B | 4 | 12 mesi | +5,4 | +0,0 | +19,5 | +11,6 | +0,1 | +1,2 | +4,0 | +2,9 | +1,5 | +3,9 |

## Riduzione ottenuta contro il tetto teorico della pre-registrazione

Il tetto teorico (una sola operazione aperta esattamente al massimo, che paga tutto al fondo, senza togliere il premio)
è ricalcolato con la stessa formula e dà gli stessi valori scritti nella pre-registrazione (43,7% per la cella A,
111,5% per la cella B). Qui accanto alla riduzione ottenuta dalla regola 3.

| versione | scadenza | tetto teorico medio (2007 ; 2000 ; 2020) | riduzione ottenuta, regola 3 (2007 ; 2000 ; 2020) | ottenuta / tetto |
|---|---|---:|---:|---:|
| A | 3 mesi | 55,7% (47% ; 30% ; 90%) | 4,0% (14% ; -2% ; 0%) | 7% |
| A | 6 mesi | 62,7% (55% ; 41% ; 93%) | 14,2% (21% ; 22% ; 0%) | 23% |
| A | 9 mesi | 49,5% (44% ; 35% ; 69%) | 15,6% (20% ; 27% ; 0%) | 32% |
| **A** | **12 mesi** | 43,7% (39% ; 33% ; 59%) | 12,4% (21% ; 16% ; 0%) | 28% |
| **B** | **3 mesi** | 111,5% (95% ; 59% ; 180%) | 8,2% (29% ; -5% ; 0%) | 7% |
| B | 6 mesi | 62,7% (55% ; 41% ; 93%) | 14,2% (21% ; 22% ; 0%) | 23% |
| B | 9 mesi | 49,5% (44% ; 35% ; 69%) | 15,6% (20% ; 27% ; 0%) | 32% |
| B | 12 mesi | 43,7% (39% ; 33% ; 59%) | 12,4% (21% ; 16% ; 0%) | 28% |

La cella A ottiene 12,4% contro un tetto di 43,7% (il 28% del tetto); la cella B 8,2% contro 111,5% (il 7%). La
pre-registrazione scriveva che per arrivare a un terzo la cella A avrebbe dovuto ottenere circa il 76% del tetto.

## Parte coperta oltre il 100%

Numero di spread = premio / prezzo dello spread, senza nessun limite (è nella pre-registrazione). Parte coperta = premio
in % del portafoglio / costo dello spread in % dell'indice, per ogni operazione.

| versione | regola | scadenza | operazioni | con parte coperta > 100% | massimo | quando |
|---|---|---|---:|---:|---:|---|
| A | 1 | 3 mesi | 145 | 73 | 522% | 2006-12-15 |
| A | 1 | 6 mesi | 73 | 51 | 465% | 2006-12-15 |
| A | 1 | 9 mesi | 49 | 25 | 229% | 1995-03-30 |
| A | 1 | 12 mesi | 37 | 13 | 283% | 2006-12-15 |
| A | 2 | 3 mesi | 37 | 16 | 331% | 2006-12-01 |
| A | 2 | 6 mesi | 24 | 13 | 325% | 2006-12-01 |
| A | 2 | 9 mesi | 19 | 8 | 201% | 2024-06-03 |
| A | 2 | 12 mesi | 16 | 5 | 160% | 2023-08-01 |
| A | 3 | 3 mesi | 22 | 11 | 331% | 2006-12-01 |
| A | 3 | 6 mesi | 14 | 10 | 307% | 2006-09-01 |
| A | 3 | 9 mesi | 14 | 7 | 231% | 2006-09-01 |
| A | 3 | 12 mesi | 12 | 4 | 201% | 2006-09-01 |
| A | 4 | 3 mesi | 43 | 6 | 179% | 1994-07-01 |
| A | 4 | 6 mesi | 27 | 10 | 165% | 1994-12-01 |
| A | 4 | 9 mesi | 22 | 2 | 130% | 2023-11-01 |
| A | 4 | 12 mesi | 19 | 1 | 119% | 2023-11-01 |
| **A — totale delle 16 celle** | | | **573** | **255** | **522%** | 2006-12-15 (regola 1, 3 mesi) |
| B | 1 | 3 mesi | 145 | 127 | 1044% | 2006-12-15 |
| B | 1 | 6 mesi | 73 | 51 | 465% | 2006-12-15 |
| B | 1 | 9 mesi | 49 | 25 | 229% | 1995-03-30 |
| B | 1 | 12 mesi | 37 | 13 | 283% | 2006-12-15 |
| B | 2 | 3 mesi | 37 | 33 | 661% | 2006-12-01 |
| B | 2 | 6 mesi | 24 | 13 | 325% | 2006-12-01 |
| B | 2 | 9 mesi | 19 | 8 | 201% | 2024-06-03 |
| B | 2 | 12 mesi | 16 | 5 | 160% | 2023-08-01 |
| B | 3 | 3 mesi | 22 | 20 | 661% | 2006-12-01 |
| B | 3 | 6 mesi | 14 | 10 | 307% | 2006-09-01 |
| B | 3 | 9 mesi | 14 | 7 | 231% | 2006-09-01 |
| B | 3 | 12 mesi | 12 | 4 | 201% | 2006-09-01 |
| B | 4 | 3 mesi | 43 | 27 | 358% | 1994-07-01 |
| B | 4 | 6 mesi | 27 | 10 | 165% | 1994-12-01 |
| B | 4 | 9 mesi | 22 | 2 | 130% | 2023-11-01 |
| B | 4 | 12 mesi | 19 | 1 | 119% | 2023-11-01 |
| **B — totale delle 16 celle** | | | **573** | **356** | **1044%** | 2006-12-15 (regola 1, 3 mesi) |

- **Versione A**: 255 operazioni su 573 con parte coperta oltre il 100%; massimo 522% (2006-12-15, regola 1, 3 mesi).
  Nella cella del verdetto (regola 3 × 12 mesi): 4 su 12, massimo 201% (2006-09-01).
- **Versione B**: 356 su 573; massimo **1.044%** (2006-12-15, regola 1, 3 mesi). Nella cella del verdetto (regola 3 × 3
  mesi): 20 su 22, massimo 661% (2006-12-01).
- La pre-registrazione citava come esempio il 306% (versione B a 3 mesi, 2020-02-19): con il VIX intorno a 10-12 del
  2006 lo spread a 3 mesi costa meno dello 0,5% dell'indice e il premio del 3% compra un nozionale da sei a dieci volte
  il portafoglio. I 573 sono operazioni contate cella per cella: le 12 celle che coincidono fra A e B contano due volte.

## Sensibilità descrittive

Una variazione alla volta rispetto alla scelta principale (inclinazione +5, q = 2%, valutazione a modello), su tutte le
32 combinazioni. Inclinazione e dividendo cambiano il prezzo all'ingresso (quindi il numero di spread) e la valutazione
giornaliera; il valore intrinseco cambia solo la valutazione giornaliera dello spread aperto. **Nessuna di queste
cambia il verdetto**: l'ultima colonna dice cosa darebbe la stessa regola con quella variante.

| versione, cella | variante | riduzione media | costo (punti) | rendimento annuo | premio annuo speso | operazioni | verdetto con questa variante (descrittivo: non cambia il verdetto) |
|---|---|---:|---:|---:|---:|---:|---|
| A, regola 3 × 12 mesi | principale | 12,42% | -0,003 | 8,53% | 1,00% | 12 | NON REGGE |
| A, regola 3 × 12 mesi | inclinazione 0 | 10,23% | +0,156 | 8,37% | 1,00% | 12 | NON REGGE |
| A, regola 3 × 12 mesi | inclinazione +10 | 16,84% | -0,307 | 8,83% | 1,00% | 12 | NON REGGE |
| A, regola 3 × 12 mesi | valore intrinseco | 13,85% | +0,006 | 8,52% | 1,00% | 12 | NON REGGE |
| A, regola 3 × 12 mesi | q = 0 | 14,30% | -0,132 | 8,66% | 1,00% | 12 | NON REGGE |
| B, regola 3 × 3 mesi | principale | 8,21% | +0,334 | 8,19% | 1,83% | 22 | NON REGGE |
| B, regola 3 × 3 mesi | inclinazione 0 | 7,89% | +0,364 | 8,16% | 1,83% | 22 | NON REGGE |
| B, regola 3 × 3 mesi | inclinazione +10 | 9,04% | +0,249 | 8,27% | 1,83% | 22 | NON REGGE |
| B, regola 3 × 3 mesi | valore intrinseco | 8,33% | +0,334 | 8,19% | 1,83% | 22 | NON REGGE |
| B, regola 3 × 3 mesi | q = 0 | 9,20% | +0,204 | 8,32% | 1,83% | 22 | NON REGGE |

**In nessuna delle quattro varianti il verdetto di una delle due celle cambierebbe**: la riduzione resta sotto 1/5 in
tutte (al più 16,84% nella cella A con inclinazione +10; al più 9,20% nella cella B con q = 0) e il costo resta sotto
1,5 punti.

Tutte le 32 celle, riduzione media / costo in punti:

| versione | regola | scadenza | principale | inclinazione 0 | inclinazione +10 | valore intrinseco | q = 0 |
|---|---|---|---:|---:|---:|---:|---:|
| A | 1 | 3 mesi | 21,4% / +3,58 | 20,5% / +3,64 | 23,5% / +3,41 | 23,4% / +3,58 | 23,6% / +3,36 |
| A | 1 | 6 mesi | 38,9% / +4,68 | 37,8% / +4,81 | 43,8% / +4,41 | 51,0% / +4,70 | 45,6% / +4,51 |
| A | 1 | 9 mesi | 35,3% / +2,11 | 32,4% / +2,37 | 43,6% / +1,59 | 43,2% / +2,18 | 41,6% / +1,88 |
| A | 1 | 12 mesi | 26,6% / +1,66 | 23,8% / +1,91 | 34,7% / +1,17 | 37,5% / +1,69 | 32,0% / +1,47 |
| A | 2 | 3 mesi | 3,4% / +0,40 | 3,2% / +0,42 | 3,9% / +0,33 | 3,0% / +0,40 | 3,9% / +0,29 |
| A | 2 | 6 mesi | 13,7% / +0,21 | 12,1% / +0,35 | 16,9% / -0,08 | 14,3% / +0,21 | 15,6% / +0,02 |
| A | 2 | 9 mesi | 4,8% / +0,60 | 3,6% / +0,73 | 6,8% / +0,33 | 5,6% / +0,60 | 5,4% / +0,48 |
| A | 2 | 12 mesi | 6,2% / +0,60 | 4,8% / +0,73 | 8,8% / +0,32 | 7,7% / +0,62 | 7,1% / +0,49 |
| A | 3 | 3 mesi | 4,0% / +0,13 | 3,8% / +0,15 | 4,4% / +0,09 | 4,0% / +0,13 | 4,4% / +0,06 |
| A | 3 | 6 mesi | 14,2% / -0,32 | 13,1% / -0,23 | 16,9% / -0,54 | 14,6% / -0,32 | 16,2% / -0,49 |
| A | 3 | 9 mesi | 15,6% / -0,43 | 13,2% / -0,24 | 20,5% / -0,79 | 16,2% / -0,43 | 17,8% / -0,60 |
| A | 3 | 12 mesi | 12,4% / +0,00 | 10,2% / +0,16 | 16,8% / -0,31 | 13,9% / +0,01 | 14,3% / -0,13 |
| A | 4 | 3 mesi | 16,8% / +0,52 | 16,1% / +0,56 | 18,4% / +0,43 | 18,9% / +0,52 | 18,3% / +0,43 |
| A | 4 | 6 mesi | 25,4% / +0,63 | 22,9% / +0,77 | 30,4% / +0,36 | 30,9% / +0,63 | 28,2% / +0,48 |
| A | 4 | 9 mesi | 15,7% / +0,61 | 13,5% / +0,78 | 20,0% / +0,30 | 21,3% / +0,61 | 17,7% / +0,48 |
| A | 4 | 12 mesi | 21,6% / +0,14 | 17,7% / +0,38 | 29,3% / -0,31 | 26,4% / +0,14 | 24,3% / -0,02 |
| B | 1 | 3 mesi | 45,6% / +7,29 | 43,5% / +7,41 | 50,3% / +7,00 | 49,6% / +7,29 | 50,6% / +6,90 |
| B | 1 | 6 mesi | 38,9% / +4,68 | 37,8% / +4,81 | 43,8% / +4,41 | 51,0% / +4,70 | 45,6% / +4,51 |
| B | 1 | 9 mesi | 35,3% / +2,11 | 32,4% / +2,37 | 43,6% / +1,59 | 43,2% / +2,18 | 41,6% / +1,88 |
| B | 1 | 12 mesi | 26,6% / +1,66 | 23,8% / +1,91 | 34,7% / +1,17 | 37,5% / +1,69 | 32,0% / +1,47 |
| B | 2 | 3 mesi | 7,1% / +0,89 | 6,6% / +0,94 | 8,1% / +0,77 | 6,1% / +0,89 | 8,1% / +0,70 |
| B | 2 | 6 mesi | 13,7% / +0,21 | 12,1% / +0,35 | 16,9% / -0,08 | 14,3% / +0,21 | 15,6% / +0,02 |
| B | 2 | 9 mesi | 4,8% / +0,60 | 3,6% / +0,73 | 6,8% / +0,33 | 5,6% / +0,60 | 5,4% / +0,48 |
| B | 2 | 12 mesi | 6,2% / +0,60 | 4,8% / +0,73 | 8,8% / +0,32 | 7,7% / +0,62 | 7,1% / +0,49 |
| B | 3 | 3 mesi | 8,2% / +0,33 | 7,9% / +0,36 | 9,0% / +0,25 | 8,3% / +0,33 | 9,2% / +0,20 |
| B | 3 | 6 mesi | 14,2% / -0,32 | 13,1% / -0,23 | 16,9% / -0,54 | 14,6% / -0,32 | 16,2% / -0,49 |
| B | 3 | 9 mesi | 15,6% / -0,43 | 13,2% / -0,24 | 20,5% / -0,79 | 16,2% / -0,43 | 17,8% / -0,60 |
| B | 3 | 12 mesi | 12,4% / +0,00 | 10,2% / +0,16 | 16,8% / -0,31 | 13,9% / +0,01 | 14,3% / -0,13 |
| B | 4 | 3 mesi | 35,1% / +1,14 | 33,4% / +1,22 | 38,6% / +0,96 | 39,2% / +1,14 | 38,4% / +0,97 |
| B | 4 | 6 mesi | 25,4% / +0,63 | 22,9% / +0,77 | 30,4% / +0,36 | 30,9% / +0,63 | 28,2% / +0,48 |
| B | 4 | 9 mesi | 15,7% / +0,61 | 13,5% / +0,78 | 20,0% / +0,30 | 21,3% / +0,61 | 17,7% / +0,48 |
| B | 4 | 12 mesi | 21,6% / +0,14 | 17,7% / +0,38 | 29,3% / -0,31 | 26,4% / +0,14 | 24,3% / -0,02 |

## Operazioni delle due celle del verdetto

### Versione A, regola 3 × 12 mesi

| # | ingresso | scadenza | chiusura | VIX | prezzo dello spread (% indice) | premio | parte coperta | chiusura a scadenza | valore a scadenza (% della chiusura di ingresso) | incasso / premio |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1991-02-01 | 1992-01-31 | 343,05 | 21,04 | 3,199% | 3,0% | 94% | 408,78 | 0,00% | 0,00 |
| 2 | 2000-03-01 | 2001-03-01 | 1379,19 | 21,64 | 3,413% | 3,0% | 88% | 1241,23 | 5,00% | 1,47 |
| 3 | 2001-12-03 | 2002-12-03 | 1129,90 | 25,77 | 5,161% | 3,0% | 58% | 920,75 | 13,51% | 2,62 |
| 4 | 2003-04-01 | 2004-04-01 | 858,48 | 28,36 | 5,728% | 3,0% | 52% | 1132,17 | 0,00% | 0,00 |
| 5 | 2006-09-01 | 2007-08-31 | 1311,01 | 11,96 | 1,496% | 3,0% | 201% | 1473,99 | 0,00% | 0,00 |
| 6 | 2008-05-01 | 2009-05-01 | 1409,34 | 18,88 | 4,048% | 3,0% | 74% | 877,52 | 20,00% | 4,94 |
| 7 | 2009-05-01 | 2010-04-30 | 877,52 | 35,30 | 6,834% | 3,0% | 44% | 1186,69 | 0,00% | 0,00 |
| 8 | 2016-06-01 | 2017-06-01 | 2099,33 | 14,20 | 3,371% | 3,0% | 89% | 2430,06 | 0,00% | 0,00 |
| 9 | 2019-03-01 | 2020-02-28 | 2803,69 | 13,57 | 2,542% | 3,0% | 118% | 2954,22 | 0,00% | 0,00 |
| 10 | 2022-08-01 | 2023-08-01 | 4118,63 | 22,84 | 4,471% | 3,0% | 67% | 4576,73 | 0,00% | 0,00 |
| 11 | 2023-08-01 | 2024-08-01 | 4576,73 | 13,93 | 1,878% | 3,0% | 160% | 5446,68 | 0,00% | 0,00 |
| 12 | 2025-07-01 | 2026-07-01 | 6198,01 | 16,83 | 2,794% | 3,0% | 107% | aperta a fine periodo | — | — |

### Versione B, regola 3 × 3 mesi

| # | ingresso | scadenza | chiusura | VIX | prezzo dello spread (% indice) | premio | parte coperta | chiusura a scadenza | valore a scadenza (% della chiusura di ingresso) | incasso / premio |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1991-02-01 | 1991-05-01 | 343,05 | 21,04 | 1,677% | 3,0% | 179% | 380,29 | 0,00% | 0,00 |
| 2 | 1991-05-01 | 1991-08-01 | 380,29 | 17,77 | 1,261% | 3,0% | 238% | 387,12 | 0,00% | 0,00 |
| 3 | 2000-03-01 | 2000-06-01 | 1379,19 | 21,64 | 1,837% | 3,0% | 163% | 1448,81 | 0,00% | 0,00 |
| 4 | 2000-07-03 | 2000-10-03 | 1469,54 | 19,83 | 1,555% | 3,0% | 193% | 1426,46 | 0,00% | 0,00 |
| 5 | 2001-02-01 | 2001-05-01 | 1373,47 | 21,66 | 1,847% | 3,0% | 162% | 1266,44 | 2,79% | 1,51 |
| 6 | 2001-12-03 | 2002-03-01 | 1129,90 | 25,77 | 2,678% | 3,0% | 112% | 1131,78 | 0,00% | 0,00 |
| 7 | 2003-04-01 | 2003-07-01 | 858,48 | 28,36 | 3,171% | 3,0% | 95% | 982,32 | 0,00% | 0,00 |
| 8 | 2006-09-01 | 2006-12-01 | 1311,01 | 11,96 | 0,495% | 3,0% | 606% | 1396,71 | 0,00% | 0,00 |
| 9 | 2006-12-01 | 2007-03-01 | 1396,71 | 11,66 | 0,454% | 3,0% | 661% | 1403,17 | 0,00% | 0,00 |
| 10 | 2008-05-01 | 2008-08-01 | 1409,34 | 18,88 | 1,716% | 3,0% | 175% | 1260,31 | 5,57% | 3,25 |
| 11 | 2008-08-01 | 2008-10-31 | 1260,31 | 22,57 | 2,263% | 3,0% | 133% | 968,75 | 18,13% | 8,01 |
| 12 | 2009-05-01 | 2009-07-31 | 877,52 | 35,30 | 4,171% | 3,0% | 72% | 987,48 | 0,00% | 0,00 |
| 13 | 2016-06-01 | 2016-09-01 | 2099,33 | 14,20 | 1,055% | 3,0% | 284% | 2170,86 | 0,00% | 0,00 |
| 14 | 2019-03-01 | 2019-05-31 | 2803,69 | 13,57 | 0,826% | 3,0% | 363% | 2752,06 | 0,00% | 0,00 |
| 15 | 2019-07-01 | 2019-10-01 | 2964,33 | 14,06 | 0,920% | 3,0% | 326% | 2940,25 | 0,00% | 0,00 |
| 16 | 2022-08-01 | 2022-11-01 | 4118,63 | 22,84 | 2,256% | 3,0% | 133% | 3856,10 | 1,37% | 0,61 |
| 17 | 2022-12-01 | 2023-03-01 | 4076,57 | 19,84 | 1,633% | 3,0% | 184% | 3951,39 | 0,00% | 0,00 |
| 18 | 2023-05-01 | 2023-08-01 | 4167,87 | 16,08 | 1,041% | 3,0% | 288% | 4576,73 | 0,00% | 0,00 |
| 19 | 2023-08-01 | 2023-11-01 | 4576,73 | 13,93 | 0,733% | 3,0% | 409% | 4237,86 | 2,40% | 3,28 |
| 20 | 2024-06-03 | 2024-09-03 | 5283,40 | 13,11 | 0,627% | 3,0% | 478% | 5528,93 | 0,00% | 0,00 |
| 21 | 2025-07-01 | 2025-10-01 | 6198,01 | 16,83 | 1,204% | 3,0% | 249% | 6711,20 | 0,00% | 0,00 |
| 22 | 2025-10-01 | 2025-12-31 | 6711,20 | 16,29 | 1,136% | 3,0% | 264% | 6845,50 | 0,00% | 0,00 |

La regola 3 non entra nel 1990 (mediana del VIX non disponibile: 9 letture con il composito acceso e la finestra non
intera); il primo ingresso è il 1991-02-01.

## Controlli di buon senso

**(a) Cella «nessuna operazione» = indice.** Simulazione con il segnale mai acceso: operazioni 0; massima differenza giornaliera dal portafoglio senza protezione 0; massima differenza da 100 × chiusura / chiusura del 1990-01-02 4,55e-13.
Chiusure: 359,69 (1990-01-02) → 6845,50 (2025-12-31). Rendimento annuo dell'indice dalle chiusure 8,523077% ; della cella vuota 8,523077% ; differenza 0. Ribasso massimo dell'indice -56,7754% (2007-10-09 → 2009-03-09); della cella vuota -56,7754% (2007-10-09 → 2009-03-09).
  ribasso 2007-10-09 → 2009-03-09: portafoglio -56,7754% ; indice dalle chiusure 676,53 / 1565,15 − 1 = -56,7754%
  ribasso 2000-03-24 → 2002-10-09: portafoglio -49,1469% ; indice dalle chiusure 776,76 / 1527,46 − 1 = -49,1469%
  ribasso 2020-02-19 → 2020-03-23: portafoglio -33,9250% ; indice dalle chiusure 2237,40 / 3386,15 − 1 = -33,9250%

**(b) Una operazione del 2008 ricalcolata a mano** — versione A, regola 3, 12 mesi, operazione n. 6.

    Dati letti: chiusura GSPC del 2008-05-01 = 1409.34 ; VIXCLS del 2008-05-01 = 18.88 ; DTB3 del 2008-05-01 = 1.42
    Scadenza: 2008-05-01 + 12 mesi = 2009-05-01 → seduta 2009-05-01 ; 365 giorni ; T = 1.000000
    Tasso: P = 0.99641056 ; r = 0.01442312
    put comprata: K = 1338.8730 ; σ = 0.1888 ; d1 = 0.336542 ; d2 = 0.147742 ; N(−d1) = 0.368231 ; N(−d2) = 0.441273 ; put = 73.6620
    put venduta: K = 1057.0050 ; σ = 0.2388 ; d1 = 1.300745 ; d2 = 1.061945 ; N(−d1) = 0.096673 ; N(−d2) = 0.144130 ; put = 16.6178
    Spread = 73.6620 − 16.6178 = 57.044143 punti (4.0476% della chiusura)
    Portafoglio alla chiusura dell'ingresso (dalla serie del programma) = 388.537079 ; premio = 3.0% × 388.537079 = 11.656112
    Numero di spread = 11.656112 / 57.044143 = 0.20433495 ; parte coperta = 74.1184%
    Chiusura del 2009-05-01 = 877.52 ; valore a scadenza = max(1338.8730 − 877.52, 0) − max(1057.0050 − 877.52, 0) = 281.8680 punti ; incasso = 0.20433495 × 281.8680 = 57.595485

| voce | a mano | programma | differenza |
|---|---:|---:|---:|
| scadenza | 2009-05-01 | 2009-05-01 | 0 |
| prezzo dello spread | 57,04414316 | 57,04414316 | 0 |
| premio | 11,65611238 | 11,65611238 | -1,78e-15 |
| numero di spread | 0,20433495 | 0,20433495 | -2,78e-17 |
| valore a scadenza (punti) | 281,86800000 | 281,86800000 | 0 |
| incasso | 57,59548486 | 57,59548486 | -7,11e-15 |

**(c) Premi e incassi contro la differenza fra portafoglio protetto e non protetto.** Per ogni cella: valore finale protetto − non protetto, contro la somma di (− premio, + incasso), ciascuno cresciuto con l'indice dal suo giorno al 2025-12-31, più lo spread ancora aperto.

| cella | operazioni | somma dei premi | somma degli incassi | spread aperto alla fine | protetto − non protetto | ricostruito da premi e incassi | differenza |
|---|---:|---:|---:|---:|---:|---:|---:|
| A, regola 3 × 12 mesi | 12 | 240,4053 | 98,3364 | 5,7036 | 1,630547 | 1,630547 | 1,99e-13 |
| B, regola 3 × 3 mesi | 22 | 444,3581 | 252,9404 | 0,0000 | -199,727852 | -199,727852 | -5,68e-14 |

Massimo scostamento assoluto sulle 32 celle: 1,88e-12.
Caso semplice, una sola operazione (la prima della cella con meno operazioni, ingresso 1991-02-01, scadenza 1992-01-31): non protetto alla scadenza 113,647863 ; − premio 2,861214 × 408,78/343,05 ; + incasso 0,000000 ; atteso 110,238428 ; programma 110,238428 ; differenza 0.

Letture dei tre controlli:

- **(a)** La cella senza operazioni è il portafoglio senza protezione (differenza 0 su ogni seduta) e questo è
  l'indice: stesso rendimento annuo (8,523077%), stesso ribasso massimo (−56,7754%, 2007-10-09 → 2009-03-09), stesse
  profondità dei tre ribassi ricalcolate dalle chiusure. La differenza di 4,55e-13 è l'arrotondamento fra
  (100 / chiusura iniziale) × chiusura e 100 × chiusura / chiusura iniziale.
- **(b)** Operazione del 2008-05-01 della cella A: prezzo, premio, numero di spread, scadenza, valore a scadenza e
  incasso ricalcolati con le formule scritte per esteso (senza `put_spread`) coincidono con il programma (differenze
  dell'ordine di 1e-15). Il valore del portafoglio nel giorno di ingresso è preso dalla serie del programma.
- **(c)** In entrambe le celle del verdetto e in tutte le 32 la differenza fra portafoglio protetto e non protetto alla
  fine è ricostruita da premi, incassi e spread aperto con uno scostamento massimo di 1,88e-12; il caso con una sola
  operazione torna a 0.

Test: `tests/test_g_simulazione.py`, 165 controlli, 0 falliti (ALL TEST-G SIMULATION TESTS PASSED, exit 0). Suite completa del repo (`bash test.sh`): ALL SUITES PASSED, exit 0 (27 suite piatte, edgar_llm 173 passed, market-data 146 passed).
Determinismo: due esecuzioni consecutive di `test_g.py` danno la stessa uscita byte per byte (`cmp`).

## Faber × 3 mesi, versione B — copertura e limite al 100% (descrittiva, aggiunta il 04-10-2026 dopo aver visto i risultati)

**Non è un verdetto.** Questa sezione è stata chiesta dall'utente il 04-10-2026 **dopo aver visto la griglia**: riguarda
una sola cella su 32 (versione B, regola 4 Faber × 3 mesi), scelta a risultati noti, e non era nella pre-registrazione.
I due verdetti restano quelli in testa (celle della regola 3). È una serie in più oltre le 160 pre-registrate.

**Lettura del limite** (dichiarata): con il limite al 100%, numero di spread = min(premio / prezzo dello spread,
1 × valore del portafoglio / chiusura dell'indice), cioè il nozionale degli spread non supera il portafoglio. Quando il
limite morde il **premio speso è quello effettivo** (numero di spread × prezzo, meno del 3%) e il resto resta investito
nell'indice. Tutto il resto è identico alla cella della griglia: stesse date, stessi strike, stesso prezzo. Nel
programma è un parametro opzionale (`limite_coperta`, predefinito: nessun limite); le 32 celle e i due verdetti non
cambiano (uscita identica byte per byte a quella di prima dell'aggiunta, verificato con `cmp`).

Serie guardate: 160 pre-registrate + 1 aggiunta = 161.

Parte coperta delle 43 operazioni della cella senza limite: media 137,6% ; mediana 121,2% ; minima 64,7% ; massima 357,9% (1994-07-01) ; oltre il 100%: 27 su 43.

Con il limite al 100%: il limite morde in 27 operazioni su 43; parte coperta media 92,6% ; massima 100,0% ; premio effettivo per operazione: minimo 0,838% ; medio 2,339% ; massimo 3,000%.

| misura | senza limite (cella della griglia) | limite al 100% |
|---|---:|---:|
| rendimento annuo | 7,39% | 7,49% |
| ribasso massimo | -43,9% | -44,6% |
| 2007-10-09 → 2009-03-09 (senza protezione -56,78%): profondità con protezione (riduzione) | -43,92% (22,64%) | -44,61% (21,43%) |
| 2000-03-24 → 2002-10-09 (senza protezione -49,15%): profondità con protezione (riduzione) | -20,63% (58,02%) | -33,64% (31,56%) |
| 2020-02-19 → 2020-03-23 (senza protezione -33,92%): profondità con protezione (riduzione) | -25,61% (24,52%) | -25,61% (24,52%) |
| riduzione media dei tre ribassi peggiori | 35,06% | 25,84% |
| riduzione media, non arrotondata | 0,3506036655 | 0,2583611882 |
| costo (punti di rendimento annuo) | +1,136 | +1,030 |
| costo, non arrotondato | 1,1356460762 | 1,0300613899 |
| premio annuo effettivamente speso | 3,58% | 2,79% |
| operazioni | 43 | 43 |
| riduzione ≥ 1/3 | sì | no |
| costo ≤ 1,5 punti | sì | sì |
| supererebbe le due soglie di REGGE (descrittivo: non è un verdetto) | sì | no |

Controllo contabile della serie con il limite (protetto − non protetto contro premi e incassi): scostamento -2,27e-13.

- **Copertura della cella senza limite**: media 137,6%, mediana 121,2%, massima 357,9% (1994-07-01); 27 operazioni su
  43 oltre il 100%.
- **Senza limite** (la cella della griglia): riduzione media 0,3506036655 e costo 1,1356460762 punti; sono sopra 1/3 e
  sotto 1,5, cioè i numeri supererebbero le due soglie di REGGE.
- **Con il limite al 100%**: riduzione media 0,2583611882 (sotto 1/3, sopra 1/5) e costo 1,0300613899 punti; la soglia
  della riduzione non sarebbe superata. La differenza è quasi tutta nel ribasso 2000-02 (riduzione da 58,02% a 31,56%);
  nel 2007-09 passa da 22,64% a 21,43% e nel 2020 resta 24,52%. Il premio annuo effettivamente speso scende da 3,58% a
  2,79%.
- Le soglie sono citate solo per confronto: la cella non aveva un verdetto pre-registrato e non ne riceve uno qui.

## Effetto della correzione di lettura del composito (ADR-071) — confronto descrittivo

**Il verdetto valido è quello con la correzione**, decisa il 04-10-2026 prima di qualunque risultato (ADR-071, commit
`fe2da3f`, precedente all'esistenza di `test_g.py`). **L'esecuzione a referto era già quella corretta**: una
esecuzione del Test G con l'errore di lettura non c'è mai stata. Quella qui sotto con la **vecchia lettura** è stata
fatta **dopo**, su richiesta dell'utente, solo per mostrare la differenza: il composito è calcolato da una copia di
`test_f.py` com'era al commit `7a5a91e` (prima di ADR-071), estratta con `git show` in una cartella temporanea fuori
dal repo e passata al programma con `--confronto-composito`; il codice del repo non è stato toccato. Riguarda solo le
regole 2 e 3 (le uniche che leggono il composito): 16 serie in più, descrittive.

Composito «corretto» = `test_f.py` del repo; «vecchia lettura» = `test_f_7a5a91e.py`, caricato da fuori dal repo. `riga_gsw` nel modulo del repo: presente; nel modulo alternativo: assente.

- corretto: letture del Test G senza composito 0 su 432; fini mese 1973-02 → 2025-12 senza composito 0 su 635; letture accese regola 2: 96 ; regola 3: 42.
- vecchia lettura: letture del Test G senza composito 23 su 432 (1992-01, 1992-04, 1992-12, 1993-01, 1993-04, 1995-03, 1997-01, 1997-02, 2003-01, 2003-02, 2003-04, 2008-02, 2014-01, 2014-02, 2014-04, 2019-04, 2020-01, 2023-06, 2024-06, 2025-01, 2025-02, 2025-04, 2025-06); fini mese 1973-02 → 2025-12 senza composito 30 su 635; letture accese regola 2: 92 ; regola 3: 39.

### Letture intorno a 2008-02 e 2020-01

| fine mese letta | ingresso possibile | composito corretto | composito vecchia lettura | regola 2 corretto / vecchia | regola 3 corretto / vecchia |
|---|---|---:|---:|---|---|
| 2007-12-31 | 2008-01-02 | 4 | 4 | accesa / accesa | spenta / spenta |
| 2008-01-31 | 2008-02-01 | 4 | 4 | accesa / accesa | spenta / spenta |
| 2008-02-29 | 2008-03-03 | 4 | **mancante** | accesa / mancante | spenta / mancante |
| 2008-03-31 | 2008-04-01 | 4 | 4 | accesa / accesa | spenta / spenta |
| 2019-11-30 | 2019-12-02 | 1 | 1 | spenta / spenta | spenta / spenta |
| 2019-12-31 | 2020-01-02 | 1 | 1 | spenta / spenta | spenta / spenta |
| 2020-01-31 | 2020-02-03 | 0 | **mancante** | spenta / mancante | spenta / mancante |
| 2020-02-29 | 2020-03-02 | 1 | 1 | spenta / spenta | spenta / spenta |

### Le 16 celle delle regole 2 e 3: composito corretto (a referto) contro vecchia lettura

Serie guardate in più: 16 (regole 2 e 3 × 4 scadenze × 2 versioni, scelta principale).

| versione | regola | scadenza | operazioni corretto / vecchia | ingressi solo con il composito corretto | ingressi solo con la vecchia lettura | riduzione media corretto / vecchia | costo (punti) corretto / vecchia |
|---|---|---|---|---|---|---|---|
| A | 2 | 3 mesi | 37 / 37 | — | — | 3,40% / 3,40% | +0,399 / +0,399 |
| A | 2 | 6 mesi | 24 / 24 | — | — | 13,69% / 13,69% | +0,209 / +0,209 |
| A | 2 | 9 mesi | 19 / 19 | — | — | 4,78% / 4,78% | +0,597 / +0,597 |
| A | 2 | 12 mesi | 16 / 16 | — | — | 6,18% / 6,18% | +0,595 / +0,595 |
| A | 3 | 3 mesi | 22 / 21 | 2025-07-01, 2025-10-01 | 2025-09-02 | 3,96% / 3,96% | +0,133 / +0,088 |
| A | 3 | 6 mesi | 14 / 14 | 2025-07-01 | 2025-09-02 | 14,15% / 14,15% | -0,321 / -0,324 |
| A | 3 | 9 mesi | 14 / 14 | 2025-07-01 | 2025-09-02 | 15,63% / 15,63% | -0,427 / -0,441 |
| **A** | **3** | **12 mesi — verdetto** | 12 / 12 | 2025-07-01 | 2025-09-02 | 12,42% / 12,42% | -0,003 / -0,019 |
| B | 2 | 3 mesi | 37 / 37 | — | — | 7,08% / 7,08% | +0,890 / +0,890 |
| B | 2 | 6 mesi | 24 / 24 | — | — | 13,69% / 13,69% | +0,209 / +0,209 |
| B | 2 | 9 mesi | 19 / 19 | — | — | 4,78% / 4,78% | +0,597 / +0,597 |
| B | 2 | 12 mesi | 16 / 16 | — | — | 6,18% / 6,18% | +0,595 / +0,595 |
| **B** | **3** | **3 mesi — verdetto** | 22 / 21 | 2025-07-01, 2025-10-01 | 2025-09-02 | 8,21% / 8,21% | +0,334 / +0,242 |
| B | 3 | 6 mesi | 14 / 14 | 2025-07-01 | 2025-09-02 | 14,15% / 14,15% | -0,321 / -0,324 |
| B | 3 | 9 mesi | 14 / 14 | 2025-07-01 | 2025-09-02 | 15,63% / 15,63% | -0,427 / -0,441 |
| B | 3 | 12 mesi | 12 / 12 | 2025-07-01 | 2025-09-02 | 12,42% / 12,42% | -0,003 / -0,019 |

### Ingressi delle regole 2 e 3 nelle due finestre in evidenza (versione B; nella A le date sono le stesse)

| regola | scadenza | finestra | ingressi con il composito corretto | ingressi con la vecchia lettura |
|---|---|---|---|---|
| 2 | 3 mesi | 2007-10-01 → 2008-12-31 | 2008-01-02, 2008-05-01, 2008-08-01, 2008-11-03 | 2008-01-02, 2008-05-01, 2008-08-01, 2008-11-03 |
| 2 | 3 mesi | 2019-07-01 → 2020-12-31 | 2020-06-01 | 2020-06-01 |
| 2 | 6 mesi | 2007-10-01 → 2008-12-31 | 2008-04-01, 2008-10-01 | 2008-04-01, 2008-10-01 |
| 2 | 6 mesi | 2019-07-01 → 2020-12-31 | 2020-06-01 | 2020-06-01 |
| 2 | 9 mesi | 2007-10-01 → 2008-12-31 | 2007-12-03, 2008-10-01 | 2007-12-03, 2008-10-01 |
| 2 | 9 mesi | 2019-07-01 → 2020-12-31 | 2020-06-01 | 2020-06-01 |
| 2 | 12 mesi | 2007-10-01 → 2008-12-31 | 2008-10-01 | 2008-10-01 |
| 2 | 12 mesi | 2019-07-01 → 2020-12-31 | 2020-06-01 | 2020-06-01 |
| 3 | 3 mesi | 2007-10-01 → 2008-12-31 | 2008-05-01, 2008-08-01 | 2008-05-01, 2008-08-01 |
| 3 | 3 mesi | 2019-07-01 → 2020-12-31 | 2019-07-01 | 2019-07-01 |
| 3 | 6 mesi | 2007-10-01 → 2008-12-31 | 2008-05-01 | 2008-05-01 |
| 3 | 6 mesi | 2019-07-01 → 2020-12-31 | — | — |
| 3 | 9 mesi | 2007-10-01 → 2008-12-31 | 2008-05-01 | 2008-05-01 |
| 3 | 9 mesi | 2019-07-01 → 2020-12-31 | — | — |
| 3 | 12 mesi | 2007-10-01 → 2008-12-31 | 2008-05-01 | 2008-05-01 |
| 3 | 12 mesi | 2019-07-01 → 2020-12-31 | — | — |

### I due verdetti con la vecchia lettura (descrittivo: il verdetto valido è quello con il composito corretto)

| versione | cella | riduzione corretto (a referto) | costo corretto | verdetto valido | riduzione vecchia lettura | costo vecchia lettura | cosa darebbe la vecchia lettura |
|---|---|---:|---:|---|---:|---:|---|
| A | regola 3 × 12 mesi | 0,1241753648 | -0,0025802633 | **NON REGGE** | 0,1241753648 | -0,0194879873 | NON REGGE |
| B | regola 3 × 3 mesi | 0,0820774173 | 0,3335297873 | **NON REGGE** | 0,0820774173 | 0,2420018352 | NON REGGE |

- **Con il codice attuale non manca nessun composito**: 0 letture su 432 e 0 fini mese su 635 (1973-02 → 2025-12). Con
  la vecchia lettura ne mancavano 23 su 432 (30 su 635), fra cui 2008-02 e 2020-01.
- **Intorno a 2008-02 e 2020-01 non cambia nessuna operazione.** La lettura del 2008-02-29 con la correzione vale 4
  (regola 2 accesa, regola 3 spenta perché il VIX non è sotto la mediana); con la vecchia lettura mancava, ma in nessuna
  delle scadenze la regola 2 aveva un ingresso possibile il 2008-03-03 (c'era già uno spread aperto). La lettura del
  2020-01-31 con la correzione vale 0: nessuna regola accesa, nessun ingresso né con l'una né con l'altra.
- **Regola 2: le 8 celle sono identiche** con le due letture (stesse operazioni, stesse riduzioni, stessi costi).
- **Regola 3: cambia una sola lettura che conta, quella del 2025-06-30** (mancante con la vecchia lettura). Con la
  correzione l'ingresso è il 2025-07-01; con la vecchia lettura slitta al 2025-09-02 (a 3 mesi, 22 operazioni contro
  21). È dopo i tre ribassi peggiori: **le riduzioni non cambiano** (0,1241753648 nella cella A, 0,0820774173 nella
  cella B, con entrambe le letture); cambiano i costi (cella A −0,0025802633 contro −0,0194879873 punti; cella B
  0,3335297873 contro 0,2420018352).
- **I due verdetti sarebbero stati NON REGGE anche con la vecchia lettura.** La colonna «corretto» di questa tabella
  coincide cifra per cifra con i numeri in testa al referto: è la stessa esecuzione.

## Limiti

- **I prezzi sono stimati, non prezzi di mercato. Le put vere sotto stress costano di più** (limite dell'utente). Ogni
  premio, ogni numero di spread e ogni valore intermedio è un numero di Black-Scholes: non c'è nessuna quotazione di
  opzioni.
- **VIX a 30 giorni usato per ogni scadenza** (3, 6, 9 e 12 mesi). La volatilità implicita a scadenze lunghe non è il
  VIX; il test non la osserva.
- **Dividendo fisso al 2% nel prezzo delle put e portafoglio senza dividendi.** q = 2% è una media di comodo (q = 0 è
  fra le sensibilità); l'indice simulato è l'indice di prezzo, con e senza protezione, quindi i rendimenti annui dei due
  portafogli sono sotto il rendimento totale.
- **Pochi ribassi indipendenti.** Dietro i due verdetti e le 32 combinazioni ci sono **tre** ribassi (2000-02, 2007-09,
  2020) e una sola storia di 36 anni. Le celle non sono prove indipendenti, e 12 su 32 sono identiche a due a due. Nelle
  due celle del verdetto la riduzione nel 2020 è zero (nessuna operazione aperta al fondo) e pesa per un terzo nella
  media.
- **Inclinazione fissa** (+5 punti, attaccata allo strike) e **tasso a 3 mesi** per scadenze fino a 12 mesi.
- **Valore intermedio a modello**: la profondità con protezione al fondo dipende dal valore stimato dello spread
  aperto quel giorno (con il valore intrinseco la riduzione della cella A passa da 12,42% a 13,85%).
- **Nessun costo di transazione**, nessuna forbice, quantità frazionarie, regolamento sulla chiusura.
- **Parte coperta oltre il 100%, senza limite**: fino al 522% (A) e al 1.044% (B). Con il VIX basso il premio fisso
  compra un nozionale più grande del portafoglio; nessun limite è stato messo.
- **Tetto della versione A a 360 giorni**: non sono 12 mesi di calendario. Nel periodo non ha mai bloccato.
- **Il tetto teorico non è un limite matematico della strategia**: vale per una sola operazione aperta al massimo.
- **Composito**: eredita i limiti del Test F (EBP ristimato, serie di oggi prima delle versioni ALFRED). Le soglie del
  composito sono state fissate nel Test F sugli stessi anni: la regola 3 non è provata su dati nuovi.
- **VIX prima del 2003**: `VIXCLS` è la serie ricalcolata con il metodo attuale; nel 1990 la regola 3 non ha la mediana.
- **Due verdetti sugli stessi dati**: la cella A e la cella B rispondono a due domande diverse con le stesse soglie e
  non si fondono in un verdetto unico.

## Difformità e scelte fatte in esecuzione

Nessuna regola, soglia o definizione della pre-registrazione è stata cambiata. `test_g_dati.py` e `test_f.py` non sono
stati modificati. Dove la pre-registrazione lasciava un dettaglio aperto si è presa la lettura più letterale, senza
guardare quale convenisse; ogni punto è qui.

1. **Osservazioni del VIX e di DTB3 in giorni senza seduta di GSPC: non usate in nessun punto**, compresa la mediana a
   12 mesi della regola 3 e l'«ultimo VIX noto» di fine mese. È la frase della regola dei buchi («le osservazioni … in
   giorni che non sono sedute di GSPC non si usano») applicata anche alla regola 3, che parla di «chiusure giornaliere
   del VIX» senza precisare. **Effetto misurato: nessuno** — 0 sedute in cui il valore usato cambierebbe, 0 letture
   della regola 3 che cambierebbero (righe in «Dati letti»).
2. **Guadagno delle put: intervallo (P, F]**. Incassi con scadenza dopo P ed entro F, premi con ingresso dopo P ed
   entro F, valore dello spread alla chiusura di P e di F dopo le operazioni del giorno. La pre-registrazione dice «fra
   il massimo P e il fondo F» e «premi pagati dopo P» senza fissare gli estremi.
3. **Tre ribassi peggiori**: i tre più profondi fra gli episodi di `episodi.episodi_drawdown` con la sua soglia del 15%
   (definizione comune del filone, non modificata), elencati dal più profondo: 2007, 2000, 2020.
4. **Ribasso massimo del protetto dentro la finestra** (descrittivo): massimo mobile a partire da P, minimo entro F.
5. **Scadenza dopo il 2025-12-31**: per le operazioni aperte a fine periodo la data di scadenza si calcola con le sedute
   dell'archivio (fino al 2026-10-02) e, oltre, è la data di calendario, come pre-registrato; del 2026 si usa solo il
   calendario, nessun prezzo. Nella cella A l'operazione n. 12 (2025-07-01 → 2026-07-01) è aperta a fine periodo e vale
   5,70 a modello; nella cella B non resta nulla di aperto.
6. **Sensibilità di inclinazione e di q**: cambiano il prezzo sia all'ingresso (numero di spread) sia nella valutazione
   giornaliera. **Valore intrinseco**: premio e numero di spread restano quelli del prezzo a modello; cambia solo il
   valore dello spread aperto, quindi nel giorno di ingresso il portafoglio scende del premio.
7. **Tetto della versione A contato in punti base interi** (150, 300, limite 600), perché il 6% esatto sia ammesso senza
   dipendere dall'arrotondamento dei decimali.
8. **Regola 3, letture del 1990 con il composito acceso**: 9 letture senza la mediana (finestra non intera) → nessun
   ingresso, come pre-registrato. Alla lettura del 1990-12-31 la finestra è intera e la regola non è accesa; il primo
   ingresso è il 1991-02-01.
9. **Composito**: `test_f.calcola_mesi` chiamata con i suoi valori di default (1967-01 → 2025-12) e letta sulle 432
   fini mese 1989-12 → 2025-11; nessuna lettura mancante, nessun segnale ricalcolato qui.
10. **Controllo (b) «a mano»**: è un ricalcolo scritto per esteso dentro `test_g.py` (rieseguibile), non un calcolo su
    carta; usa gli stessi dati letti dall'archivio.
11. **Coincidenze A/B**: verificate come uguaglianza esatta (stesse date, differenza massima 0), non entro una tolleranza.
12. **`docs/HANDOFF.md` non aggiornato** in questa esecuzione (fuori dal perimetro assegnato): resta da fare.
13. **Due aggiunte dopo i risultati, su richiesta dell'utente (04-10-2026), entrambe descrittive**: la cella Faber × 3
    mesi della versione B con la copertura limitata al 100% (1 serie) e il confronto con la vecchia lettura del
    composito (16 serie). Sono fuori dalla pre-registrazione, hanno ciascuna la sua sezione e non toccano i verdetti.
    Il conto delle serie guardate sale da 160 a 177.
14. **Limite di copertura, lettura adottata**: numero di spread = min(premio / prezzo, portafoglio / chiusura); premio
    speso = quello effettivo; il resto resta nell'indice. Il parametro è spento per impostazione predefinita.
15. **Confronto con la vecchia lettura**: è un controfattuale costruito dopo, non una prima esecuzione. La copia di
    `test_f.py` del commit `7a5a91e` sta fuori dal repo e non è versionata: per rifare il confronto va riestratta.

## Cosa non c'è

Nessuna regola di portafoglio, nessuna ottimizzazione di soglie, strike o scadenze, nessuna etichetta sulle 30 celle
descrittive, nessun test di significatività, nessuna serie oltre le 177 dichiarate (160 pre-registrate, 17 aggiunte dopo i risultati su richiesta dell'utente).

## Come rifare tutto

    python backtest/drawdown_alpha/test_g.py          # con l'interprete del venv del repo: tutte le tabelle di questo referto
    git show 7a5a91e:backtest/drawdown_alpha/test_f.py > <cartella temporanea>/test_f_7a5a91e.py
    python backtest/drawdown_alpha/test_g.py --confronto-composito <cartella temporanea>/test_f_7a5a91e.py
                                                      # solo la sezione «Effetto della correzione di lettura del composito»
    python tests/test_g_simulazione.py                # prove sulla simulazione, senza rete
    bash test.sh                                      # suite completa
