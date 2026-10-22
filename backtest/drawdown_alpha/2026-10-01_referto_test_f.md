# Referto — Test F, segnali precoci (fermata 2) — BOZZA per la revisione dell'utente

**1 ottobre 2026.** Calcolato come pre-registrato in `backtest/drawdown_alpha/2026-09-30_preregistrazione_test_f.md`
(aggiornata il 01-10 con ADR-066 e ADR-067, prima di qualunque calcolo). Script: `backtest/drawdown_alpha/test_f.py`
(uscita integrale riprodotta qui, nessun numero scritto a mano). Dati solo da `market_data.api`: chiusure di `GSPC.INDX`
(24.794 sedute, 1927-12-30 → 2026-09-16), EBP (file Fed del 2026-08-06), curva GSW (al 2026-09-25), DTB3, PERMIT e ICSA
con le versioni ALFRED a ogni fine mese (PERMIT dal 1999-08-31, ICSA dal 2009-05-31: 517 versioni scaricate il 01-10,
0 errori), WTISPLC, GS10, TB3MS, USRECM. **Nessun risultato va tradotto in regola di portafoglio.** Il registro dei verdetti
non è stato toccato.

## Verdetto della cella pre-registrata — composito ≥ 3, 6 ribassi da recessione 1973-2025

| criterio | regola | misurato | esito |
|---|---|---|---|
| (a) colpiti | ≥ 2/3 dei ribassi da recessione (≥ 4 su 6) | **6 su 6** | regge |
| (b) falsi allarmi | ≤ colpiti | **4** falsi allarmi (+ 2 episodi del 2025 non giudicabili) ≤ 6 | regge |
| (c) falsi eventi | tasso di colpiti > 90° percentile di 1000 serie casuali (seme 20261001) | tasso reale 1,000; 90° percentile dei casuali **1,000**; quota dei casuali strettamente sotto il reale **0,885**; mediana dei casuali 0,833 | **non regge** |

**VERDETTO: INCONCLUSIVO** — (a) regge, (b) regge, (c) fallisce. Il composito ≥ 3 è acceso il **26,4 % del tempo**
(1973-02 → 2025-12, 605 fini mese) e la finestra del colpito è lunga 24 mesi più i mesi dal massimo al −10 %: in queste
condizioni anche sei finestre piazzate a caso vengono colpite tutte nell'11,5 % delle serie casuali, e in mediana 5 su 6.
Il segnale colpisce tutto, ma non più di quanto colpirebbe il caso con la stessa quota di tempo acceso.

### Evento per evento (prima fine mese di accensione dentro la finestra; anticipo in mesi)

| evento (profondità) | finestra del colpito | −15 % | EBP | NTFS | PERMIT | ICSA | WTI | composito ≥ 3 (anticipo sul massimo / sul −15 %) | ≥ 2 | ≥ 4 | Faber (anticipo sul massimo) | 10a−3m (GS10−TB3MS) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1980-02-13 (−17,1 %) | 1978-02-13 → 1980-03-10 | 1980-03-24 | 1979-12-31 | 1978-09-30 | 1978-10-31 | 1978-02-28 | 1979-03-31 | **1978-12-31** (14 / 15) | 1978-12-31 | 1979-03-31 | 1978-02-28 (24) | 1979-01-31 |
| 1980-11-28 (−27,1 %) | 1978-11-28 → 1981-08-24 | 1981-09-08 | 1979-12-31 | 1978-12-31 | 1978-11-30 | 1978-12-31 | 1979-03-31 | **1978-12-31** (23 / 33) | 1978-12-31 | 1979-03-31 | 1978-11-30 (24) | 1979-01-31 |
| 1990-07-16 (−19,9 %) | 1988-07-16 → 1990-08-17 | 1990-08-23 | 1988-07-31 | 1989-06-30 | 1989-03-31 | 1988-07-31 | 1990-02-28 | **1989-03-31** (16 / 17) | 1988-07-31 | 1989-06-30 | 1990-01-31 (6) | — |
| 2000-03-24 (−49,1 %) | 1998-03-24 → 2000-04-14 | 2000-12-20 | 1998-09-30 | 1998-09-30 | 1999-06-30 | 1998-06-30 | 2000-01-31 | **2000-02-29** (1 / 10) | 1998-09-30 | — | 1998-08-31 (19) | — |
| 2007-10-09 (−56,8 %) | 2005-10-09 → 2007-11-26 | 2008-01-18 | 2007-08-31 | 2006-01-31 | 2006-01-31 | 2005-10-31 | 2005-10-31 | **2006-05-31** (17 / 20) | 2005-10-31 | 2006-07-31 | — | 2006-09-30 |
| 2020-02-19 (−33,9 %) | 2018-02-19 → 2020-02-27 | 2020-03-09 | 2018-07-31 | 2019-03-31 | 2018-08-31 | 2018-11-30 | 2018-02-28 | **2018-11-30** (15 / 16) | 2018-08-31 | — | 2018-10-31 (16) | 2019-07-31 |

Letture: l'anticipo del composito sul massimo va da 1 mese (2000) a 23 (1980-11); i due eventi del 1980 sono colpiti dalla
stessa accensione del 1978-12-31 (dichiarato in pre-registrazione). La regola di Faber (chiusura mensile sotto la media
delle ultime 10) è «accesa» già alla prima fine mese della finestra nel 1980 (il mercato era sotto media nel 1978) e
non lo è mai nella finestra del 2007: non è un confronto fra pari — Faber segue il prezzo, non lo anticipa — e qui si
riporta come la pre-registrazione chiedeva, senza altra lettura. La curva 10a−3m del Test A si accende in 4 eventi su 6,
mai nel 1990 e nel 2000 (medie mensili, soglia zero).

### Episodi del composito ≥ 3 (fini mese consecutive, uniti se separati da meno di 3 mesi) e falsi allarmi

| inizio | fine | mesi accesi | esito |
|---|---|---:|---|
| 1973-07-31 | 1975-06-30 | 23 | evento 1973-01-11 (descrittivo; l'allarme arriva durante la discesa) |
| 1978-12-31 | 1980-08-31 | 19 | evento 1980-02-13 |
| 1981-05-31 | 1982-05-31 | 13 | evento 1980-11-28 (durante la discesa) |
| 1984-09-30 | 1984-09-30 | 1 | **FALSO ALLARME** |
| 1986-08-31 | 1986-10-31 | 3 | evento 1987-08-25 (senza recessione) |
| 1989-03-31 | 1990-02-28 | 11 | evento 1990-07-16 |
| 1990-05-31 | 1991-05-31 | 13 | evento 1990-07-16 |
| 2000-02-29 | 2000-02-29 | 1 | evento 2000-03-24 |
| 2000-06-30 | 2001-03-31 | 10 | evento 2000-03-24 (durante la discesa) |
| 2001-08-31 | 2001-11-30 | 4 | evento 2000-03-24 (durante la discesa) |
| 2003-03-31 | 2003-05-31 | 2 | **FALSO ALLARME** |
| 2006-05-31 | 2007-04-30 | 9 | evento 2007-10-09 |
| 2007-08-31 | 2009-06-30 | 22 | evento 2007-10-09 |
| 2010-08-31 | 2010-08-31 | 1 | evento 2011-04-29 (senza recessione, massimo 8 mesi dopo) |
| 2016-05-31 | 2016-05-31 | 1 | **FALSO ALLARME** |
| 2018-11-30 | 2019-02-28 | 3 | evento 2018-09-20 (durante la discesa) |
| 2019-05-31 | 2019-07-31 | 3 | evento 2020-02-19 |
| 2020-05-31 | 2020-07-31 | 3 | evento 2022-01-03 (senza recessione, massimo 20 mesi dopo: al limite dei 24) |
| 2022-07-31 | 2022-08-31 | 2 | evento 2022-01-03 (durante la discesa) |
| 2022-11-30 | 2022-12-31 | 2 | **FALSO ALLARME** |
| 2023-04-30 | 2023-08-31 | 4 | evento 2025-02-19 (senza recessione, massimo 22 mesi dopo: al limite dei 24) |
| 2024-05-31 | 2024-12-31 | 6 | evento 2025-02-19 (senza recessione) |
| 2025-05-31 | 2025-05-31 | 1 | non giudicabile (meno di 24 mesi di dati dopo) |
| 2025-08-31 | 2025-10-31 | 3 | non giudicabile |

24 episodi; **4 falsi allarmi** (1984-09, 2003-03/05, 2016-05, 2022-11/12), tutti brevi (1-2 mesi); 2 non giudicabili.
**Da dichiarare**: la definizione pre-registrata di falso allarme è generosa — un ribasso ≥ 15 % *senza recessione* che
parte fino a 24 mesi dopo «salva» l'episodio (2020-05 → 2022-01, 2023-04 → 2025-02), e un allarme durante una discesa già
iniziata non è «falso» anche se arriva dopo il −15 % (1973-07, 1981-05, 2000-06, 2001-08, 2018-11, 2022-07). Con una
lettura più stretta (solo ribassi da recessione, solo massimi futuri) i falsi allarmi sarebbero di più; non si è cambiata
la regola dopo aver visto i dati.

### Quota del tempo acceso (1973-02 → 2025-12, 605 fini mese)

composito ≥ 2: 46,0 % · **≥ 3: 26,4 %** · ≥ 4: 8,9 %. Singoli (dalla loro prima data): EBP > 0 45,5 %, NTFS < 0 19,9 %
(versione tutto GSW 26,0 %), PERMIT 41,4 %, ICSA 37,5 %, WTI 10,9 %.

### Soglie descrittive

- **≥ 2**: colpiti 6/6, **15 falsi allarmi** (+1 non giudicabile) su 42 episodi; quota dei casuali sotto il reale 0,037.
- **≥ 4**: colpiti **4/6** (mancano 2000 e 2020), 2 falsi allarmi su 13 episodi; quota dei casuali sotto il reale 0,849.

### Rendimenti dell'S&P 500 dopo l'accensione, contro tutti i mesi (chiusure di fine mese)

| campione | 3 mesi (media / mediana / negativi) | 6 mesi | 12 mesi | n |
|---|---|---|---|---|
| fini mese con composito ≥ 3 | +0,6 % / +1,2 % / 44 % | +2,4 % / +4,4 % / 40 % | +6,3 % / +11,0 % / 31 % | 160 (159 a 12 mesi) |
| prima fine mese di ogni episodio | +3,2 % / +3,1 % / 25 % | +5,8 % / +6,8 % / 33 % | +9,4 % / +12,2 % / 25 % | 24 |
| tutti i mesi con composito | +2,2 % / +2,5 % / 34 % | +4,5 % / +4,9 % / 30 % | +9,4 % / +11,3 % / 24 % | 605 (602) |

Nei mesi accesi il rendimento medio è più basso e la quota di esiti negativi più alta che nell'insieme; alla prima
accensione di un episodio no. Descrittivo, 24 episodi: nessun test di significatività pre-registrato, nessuno fatto.

### Sovrapposizione fra segnali (quota delle fini mese con A acceso in cui anche B è acceso)

| A \ B | EBP | NTFS | PERMIT | ICSA | WTI |
|---|---|---|---|---|---|
| EBP | — | 20 % | 53 % | 50 % | 8 % |
| NTFS | 45 % | — | **79 %** | 62 % | 17 % |
| PERMIT | 55 % | 36 % | — | 61 % | 15 % |
| ICSA | 60 % | 33 % | 70 % | — | 17 % |
| WTI | 31 % | 28 % | 58 % | 54 % | — |

**Nessuna coppia supera l'80 %**; la più vicina è NTFS → PERMIT (79 %): quando la curva a breve è invertita i permessi
sono quasi sempre in calo, non viceversa (36 %).

## Robustezze descrittive (nessuna entra nel verdetto)

- **Recessione dal mese dopo il picco (USREC, 5 eventi, il 2000 esce)**: colpiti 5/5, falsi allarmi 4 (+2), quota dei
  casuali sotto il reale 0,804 — stesso quadro, (c) non reggerebbe nemmeno qui.
- **1980 fusi** (massimo 1980-02-13, finestra 1978-02-13 → 1981-08-24, 5 eventi): colpiti 5/5, falsi allarmi 4 (+2),
  quota dei casuali sotto il reale 0,792.
- **Composito a 4 senza EBP dal 1967, cella ≥ 3 su 4** (eventi da recessione con massimo ≥ 1970-01-01, 7 compreso il
  1973): colpiti **5/7** — **non colpiti 1973-01-11** (nella finestra 1971-01 → 1973-04 si accendono solo ICSA 1971-08 e
  WTI 1971-01; la curva si inverte dal 1973Q2, dopo il −10 %) **e 2000-03-24** (senza EBP il composito arriva a 2 e non
  a 3); 1 falso allarme (+2 non giudicabili); quota dei casuali sotto il reale 0,862.
- **Composito a 4, cella ≥ 2 su 4**: colpiti 6/7 (manca il 1973), 10 falsi allarmi, quota dei casuali sotto il reale 0,055.
- **Tasso a 3 mesi tutto GSW (y(0,25) al posto di DTB3)**: colpiti 6/6, falsi allarmi 5 (+2), quota dei casuali sotto il
  reale 0,796; stesse date di accensione del composito nei 6 eventi.
- **Curva 10a−3m del Test A** (GS10 − TB3MS < 0): accesa in finestra in 4 eventi su 6 (1979-01, 1979-01, 2006-09, 2019-07),
  mai nel 1990 e nel 2000 (colonna nella tabella sopra).
- **Near-term forward spread, medie trimestrali 1972-2018, confronto con i grafici del paper (qualitativo: i valori del
  paper non sono disponibili come dati)**: con DTB3 **28 trimestri negativi su 188**: 1973Q2-1974Q4, 1979Q1-1980Q2,
  1980Q4-1981Q3, 1989Q3-Q4, 2000Q3-2001Q1, 2006Q1 e 2006Q3-2007Q2, 2007Q4 — cioè prima o all'inizio di ciascuna delle sei
  recessioni del periodo e **nessun trimestre negativo nel 1995, nel 1998 e nel 2008-2018**, coerente con la descrizione
  del Note 2018 (la serie «ha anticipato ogni recessione» e, a differenza dei differenziali lunghi, «has not been trending
  down in recent years»). La versione tutto GSW ha 36 trimestri negativi, con in più 1978Q4, 1989Q2, **1998Q1 e
  1998Q3-Q4** (falso segnale nel 1998), 2007Q3, 2008Q1 e 2008Q4: l'estrapolazione della curva sotto l'anno abbassa il
  tasso a 3 mesi e rende lo spread più spesso negativo. La scelta DTB3 (ADR-067) è la più vicina al paper.

### Robustezza aggiunta dall'utente (01-10, descrittiva): falsi allarmi con la lettura severa

Un episodio del composito ≥ 3 (stessa fusione sotto i 3 mesi) è un falso allarme se **nei 24 mesi successivi
all'accensione non parte un nuovo ribasso ≥ 15 %**; un ribasso già partito al momento dell'accensione non conta.
Partenza = **seduta T del −15 %**, cioè la data di inizio dell'evento di ADR-060 (lettura principale); in seconda riga
la lettura con partenza = massimo P dell'evento.

- **Partenza = −15 % (T)**: **7 falsi allarmi** su 24 episodi (+2 non giudicabili): 1973-07→1975-06, 1984-09, 2001-08→11,
  2003-03→05, 2016-05, 2022-07→08, 2022-11→12. **Criterio b) (falsi ≤ colpiti = 6): NON reggerebbe** (7 > 6).
- **Partenza = massimo (P)**: **9 falsi allarmi**: i sette sopra più 1981-05→1982-05 e 2000-06→2001-03 (massimo già alle
  spalle, −15 % ancora davanti). **b) NON reggerebbe** (9 > 6).

| inizio | fine | mesi | esito (partenza = −15 %) | esito (partenza = massimo) |
|---|---|---:|---|---|
| 1973-07-31 | 1975-06-30 | 23 | FALSO ALLARME | FALSO ALLARME |
| 1978-12-31 | 1980-08-31 | 19 | evento 1980-02-13 (−15 % il 1980-03-24) | idem |
| 1981-05-31 | 1982-05-31 | 13 | evento 1980-11-28 (−15 % il 1981-09-08) | FALSO ALLARME |
| 1984-09-30 | 1984-09-30 | 1 | FALSO ALLARME | FALSO ALLARME |
| 1986-08-31 | 1986-10-31 | 3 | evento 1987-08-25 (−15 % il 1987-10-16) | idem |
| 1989-03-31 | 1990-02-28 | 11 | evento 1990-07-16 (−15 % il 1990-08-23) | idem |
| 1990-05-31 | 1991-05-31 | 13 | evento 1990-07-16 | idem |
| 2000-02-29 | 2000-02-29 | 1 | evento 2000-03-24 (−15 % il 2000-12-20) | idem |
| 2000-06-30 | 2001-03-31 | 10 | evento 2000-03-24 (−15 % il 2000-12-20) | FALSO ALLARME |
| 2001-08-31 | 2001-11-30 | 4 | FALSO ALLARME | FALSO ALLARME |
| 2003-03-31 | 2003-05-31 | 2 | FALSO ALLARME | FALSO ALLARME |
| 2006-05-31 | 2007-04-30 | 9 | evento 2007-10-09 (−15 % il 2008-01-18) | idem |
| 2007-08-31 | 2009-06-30 | 22 | evento 2007-10-09 | idem |
| 2010-08-31 | 2010-08-31 | 1 | evento 2011-04-29 (−15 % il 2011-08-08) | idem |
| 2016-05-31 | 2016-05-31 | 1 | FALSO ALLARME | FALSO ALLARME |
| 2018-11-30 | 2019-02-28 | 3 | evento 2018-09-20 (−15 % il 2018-12-20) | evento 2020-02-19 |
| 2019-05-31 | 2019-07-31 | 3 | evento 2020-02-19 (−15 % il 2020-03-09) | idem |
| 2020-05-31 | 2020-07-31 | 3 | evento 2022-01-03 (−15 % il 2022-05-09) | idem |
| 2022-07-31 | 2022-08-31 | 2 | FALSO ALLARME | FALSO ALLARME |
| 2022-11-30 | 2022-12-31 | 2 | FALSO ALLARME | FALSO ALLARME |
| 2023-04-30 | 2023-08-31 | 4 | evento 2025-02-19 (−15 % il 2025-04-04) | idem |
| 2024-05-31 | 2024-12-31 | 6 | evento 2025-02-19 | idem |
| 2025-05-31 | 2025-05-31 | 1 | non giudicabile | non giudicabile |
| 2025-08-31 | 2025-10-31 | 3 | non giudicabile | non giudicabile |

Il verdetto resta quello pre-registrato (INCONCLUSIVO, con la lettura pre-registrata del falso allarme): questa è una
lettura descrittiva. Nota: il 1973-07 e il 2001-08 sono accensioni *dentro* un ribasso già partito (non contano, e dopo
non ne parte un altro entro 24 mesi); il 2022-07 e il 2022-11 arrivano dopo il −15 % del 2022-05-09.

## Stato al 30-09-2026 (point-in-time: regole e ritardi pre-registrati, versioni ALFRED al 2026-09-30)

| segnale | dati usati | valore | soglia | stato | da quando |
|---|---|---|---|---|---|
| 1 credito (EBP) | **EBP di agosto 2026 non pubblicato**: il file della Fed è fermo a luglio 2026 (`Last-Modified` 2026-08-06, riletto il 01-10); ultimo valore luglio 2026 = −0,319 | — (luglio −0,319) | > 0 | **non disponibile per la regola**; con l'ultimo pubblicato: spento | spento dal dato di luglio 2024 (fine mese 2024-08); l'unico mese sopra zero dal 2024 è giugno 2024 (+0,001) |
| 2 tassi (NTFS) | curva GSW del 2026-09-18 (≤ 30-09 − 11 gg): forward 3 m fra 18 m 4,999 %; DTB3 del 2026-09-18: 3,99 % sconto → 4,066 % continuo | **+0,933** | < 0 | spento | spento dal 2026-05 |
| 3 casa (PERMIT) | PERMIT fino ad agosto 2026, versione ALFRED al 2026-09-30: media 3 mesi 1.403, media 12 mesi 1.425 | −1,5 % (3 m / 12 m − 1) | media 3 m < media 12 m | **ACCESO** | acceso dal 2026-06 |
| 4 lavoro (ICSA) | ICSA fino alla settimana del 2026-09-19 (versione ALFRED al 2026-09-30): media 4 settimane 202.250, media 52 settimane 213.442 | −5,2 % | media 4 s > media 52 s | spento | spento dal 2026-07 |
| 5 petrolio (WTI) | WTISPLC di agosto 2026: 83,90; massimo dei 36 mesi precedenti 102,13 | −17,8 % | > massimo 36 mesi | spento | spento dal 2026-07 |
| (confronto) NTFS tutto GSW | curva GSW del 2026-09-18: forward 4,999, y(0,25) 4,036 | +0,963 | < 0 | spento | spento dal 2026-05 |
| **composito ≥ 3** | regola stretta: **non calcolabile al 30-09** (manca l'EBP di agosto); ultimo calcolabile 2026-08-31 (EBP di luglio) = **1** | 1 | ≥ 3 | spento | spento dal 2025-11 (ultima accensione: episodio 2025-08→10) |
| composito con l'ultimo EBP pubblicato (luglio, −0,319) | 4 segnali disponibili + EBP di luglio | **1** (solo PERMIT) | ≥ 3 | spento | — |

Nessun segnale di protezione acceso al 30-09-2026 tranne i permessi; il composito è a 1 su 5. Nessuna regola di
portafoglio ne discende (fase «prepararsi», verdetto INCONCLUSIVO).

## Scelte fatte al posto dell'utente e deviazioni imposte dai dati (dichiarate)

1. **Lettura operativa del falso allarme** (scritta nella pre-registrazione del 01-10 prima di calcolare): episodio non
   falso se un evento della lista A — qualunque stato — ha il massimo fra s e s + 24 mesi, o se s cade fra massimo e
   fondo; episodi che iniziano a meno di 24 mesi dall'ultima seduta: «non giudicabili». È una lettura, non la sola
   possibile; l'effetto è detto sopra.
2. **Lettura del criterio (c)**: «quota dei 1000 tassi casuali strettamente sotto il reale > 0,90». Con il reale a 1,000
   qualunque lettura dà lo stesso esito: il 90° percentile dei casuali è 1,000, non superabile.
3. **Finestre dei falsi eventi** lunghe come quelle reali (24 mesi più i mesi dal massimo al −10 %, cioè 0-1 mese nel
   1980-02, 1990, 2020; 1 nel 2000; 1 nel 2007; 9 nel 1980-11), non sovrapposte, con il −10 % entro il 2025-12.
4. **Rendimenti**: tre campioni (tutte le fini mese accese; prime accensioni; tutti i mesi), chiusura dell'ultima seduta
   del mese.
5. **Sovrapposizione**: quota condizionata per coppia ordinata; soglia 80 % su questa misura.
6. **Curva 10a−3m del Test A**: per coprire il 1973 si è usata GS10 − TB3MS (medie mensili H.15, FRED) del mese t−1,
   non DGS10 − DGS3MO giornaliere del Test A (dal 1981): confronto descrittivo, dichiarato in pre-registrazione.
7. **Un difetto trovato eseguendo**: `eventi_f.mesi_prima` falliva spostando una fine mese del 31 in un mese di 30
   giorni (`ValueError` al primo calcolo delle finestre di fine mese). Corretto limitando il giorno all'ultimo del mese
   (`eventi_f.py`, modifica non ancora committata); la lista degli eventi della fermata 1 non cambia: l'uscita di
   `eventi_f.py` prima e dopo la correzione è identica (`diff` vuoto).
8. **Composito a 5 dal 1973-02** (l'EBP di gennaio 1973 è noto a febbraio): il 1973-01-11 resta descrittivo come
   pre-registrato; nel composito a 4 è un evento del verdetto descrittivo e non è colpito.
9. **EBP della versione del 2026-08-06**: ristimato, non point-in-time; limite dichiarato, nessuna alternativa.
10. **Versioni ALFRED**: PERMIT dal 1999-08-31 e ICSA dal 2009-05-31 (517 fini mese); prima, serie di oggi con i ritardi
    dichiarati (revisioni non riprodotte).

## Verifica (cosa è stato letto, e da dove)

- L'uscita di `python backtest/drawdown_alpha/test_f.py` (exit 0, 10 s), riprodotta qui integralmente.
- Il log del download delle versioni (`fatto: ok 517 errori 0`) e il manifest `fred/manifest/grezzo.jsonl` (endpoint
  `alfred/PERMIT` e `alfred/ICSA`, nessuna chiave).
- La conversione DTB3: al 2026-09-25 DTB3 4,10 % → 4,18 % continuo, contro y(0,25) GSW 4,17 % (stessa grandezza).
- `bash test.sh` dopo la correzione di `mesi_prima`: ALL SUITES PASSED, exit 0, 56 s (letto dal log).
- Le tre sezioni aggiunte il 01-10 (falsi allarmi severi, stato al 30-09, limite del disegno) vengono dalla seconda
  esecuzione di `test_f.py` (exit 0); il resto dell'uscita è identico alla prima (`diff` vuoto sulle altre sezioni).
  Stato dell'EBP: file `fred/raw/2026-10-01/ebp__*.csv.gz` riletto, ultima riga `7/1/2026`; `Last-Modified` del file
  della Fed 2026-08-06 (intestazione HTTP riletta il 01-10).

## Cosa non c'è

Nessuna regola di portafoglio, nessun costo delle put, nessuna ottimizzazione di soglie, nessun test di
significatività sui rendimenti. Il verdetto è INCONCLUSIVO per la regola pre-registrata, non per un giudizio.

## Limite del disegno

Il criterio «colpito sì/no» con una finestra di 24 mesi prima del massimo si satura quando il segnale è acceso spesso.
Qui il composito ≥ 3 è acceso il **26,4 %** delle fini mese (1973-02 → 2025-12) e le finestre degli eventi durano da 24 a
33 mesi: la probabilità che una finestra qualunque contenga almeno una fine mese accesa è alta per costruzione, e
infatti le 1000 serie casuali di sei finestre vengono colpite in mediana 5 volte su 6 e tutte e sei nell'11,5 % dei
casi — il **90° percentile dei tassi casuali è 1,000**, lo stesso valore del tasso reale, e la **quota dei casuali sotto
il reale è 0,885**. In queste condizioni il criterio (c) non può distinguere un segnale che anticipa da uno che è
semplicemente acceso spesso, e il criterio (a) non può fallire: 6 su 6 è il risultato atteso anche per il caso. È una
constatazione sul disegno pre-registrato, misurata sui suoi stessi numeri; non si propone qui nessun altro test.

## Nota del 04-10-2026 — Correzione di lettura della curva

Il referto qui sopra è chiuso e non è stato riscritto. Questa nota registra un errore di lettura trovato preparando il
Test G, la sua correzione (ADR-071) e il confronto prima/dopo. **Il verdetto non cambia: INCONCLUSIVO, con gli stessi
criteri (a) vero, (b) vero, (c) falso.** Il registro dei verdetti non è stato toccato.

**L'errore.** `segnale_ntfs` leggeva la riga della curva GSW del giorno t − 11. Il file della Fed ha una riga anche nei
giorni festivi, con `NA` al posto dei parametri: quando t − 11 (o l'ultima riga prima) era un festivo, il segnale dei
tassi risultava mancante e con lui il composito. Succedeva in **30 fini mese su 635** fra il 1973-02 e il 2025-12 (per
questo il referto parla di 605 fini mese), più il 2026-06-30 nello stato attuale. **La correzione**: l'ultimo giorno
valido precedente, mai uno successivo, non più vecchio di 7 giorni rispetto a t − 11 (`test_f.riga_gsw`,
`MAX_GIORNI_CURVA`); oltre, il segnale resta mancante. Nei 31 casi la riga usata è più vecchia di 1-4 giorni. La
versione tutta GSW passa per la stessa lettura ed è corretta insieme; la curva 10 anni − 3 mesi (GS10 − TB3MS mensili
da FRED) non legge il file GSW e non è toccata.

I 31 mesi: 1975-02, 1978-01, 1980-02, 1981-04, 1986-01, 1986-02, 1987-04, 1992-01, 1992-04, 1992-12, 1993-01, 1993-04,
1995-03, 1997-01, 1997-02, 2003-01, 2003-02, 2003-04, 2008-02, 2014-01, 2014-02, 2014-04, 2019-04, 2020-01, 2023-06,
2024-06, 2025-01, 2025-02, 2025-04, 2025-06 e, fuori dal periodo, 2026-06.

**Prima e dopo** (uscita completa di `python backtest/drawdown_alpha/test_f.py` prima e dopo la modifica, confrontata
con `diff`; stessi dati del 04-10-2026):

| voce | prima | dopo |
|---|---|---|
| fini mese con il composito a 5 (1973-02 → 2025-12) | 605 | **635** (nessuna mancante) |
| eventi colpiti (composito ≥ 3, 6 ribassi da recessione) | 6/6 | 6/6 — stesse date di prima accensione per tutti e sei |
| falsi allarmi (lettura pre-registrata) | 4 (+2 non giudicabili) | 4 (+**1** non giudicabile) |
| episodi del composito ≥ 3 | 24 | **23** |
| falsi allarmi severi, partenza = −15 % | 7 su 24 | 7 su **23** (gli stessi sette) |
| falsi allarmi severi, partenza = massimo | 9 su 24 | 9 su **23** (gli stessi nove; uno inizia 1981-04 invece di 1981-05) |
| tasso reale / quota dei falsi eventi sotto il reale | 1,000 / 0,885 | 1,000 / 0,885 |
| mediana e 90° percentile dei falsi eventi | 0,833 / 1,000 | 0,833 / 1,000 |
| criteri (a) / (b) / (c) | vero / vero / falso | vero / vero / falso |
| **verdetto** | INCONCLUSIVO | **INCONCLUSIVO** |
| quota del tempo con composito ≥ 2 / ≥ 3 / ≥ 4 | 46,0 % / 26,4 % / 8,9 % | 45,8 % / 26,3 % / 8,8 % |
| segnale dei tassi acceso (DTB3 / tutto GSW) | 19,9 % / 26,0 % | 20,3 % / 26,3 % |
| descrittiva ≥ 2 | 6/6, 15 falsi allarmi, 42 episodi, quota 0,037 | 6/6, **14** falsi allarmi, **40** episodi, quota 0,037 |
| descrittiva ≥ 4 | 4/6, 2 falsi allarmi, 13 episodi, quota 0,849 | invariata |
| robustezze (mese dopo il picco, 1980 fusi, 4 segnali ≥ 3, tutto GSW) | 5/5, 5/5, 5/7, 6/6; falsi allarmi 4, 4, 1, 5; quote 0,804, 0,792, 0,862, 0,796 | colpiti, falsi allarmi e quote invariati; non giudicabili da 2 a 1 |
| robustezza 4 segnali ≥ 2 su 4 | 6/7, 10 falsi allarmi, quota 0,055 | 6/7, 10 falsi allarmi, quota **0,054** |
| stato al 2026-09-30: composito | non calcolabile (manca l'EBP di agosto); ultimo calcolabile 2026-08-31 = 1, «spento dal 2025-11» | non calcolabile (manca l'EBP di agosto); ultimo calcolabile 2026-08-31 = 1, **«spento dal 2026-07»** |
| stato al 2026-09-30: i cinque segnali | — | invariati |

**Cosa cambia negli episodi.** I mesi recuperati allungano di un mese cinque episodi (1973-07 → 1975-06: 24 mesi
accesi; 1978-12 → 1980-08: 20; 2007-08 → 2009-06: 23; 2023-04 → 2023-08: 5; 2024-05 → 2024-12: 7), anticipano di un
mese l'inizio di uno (1981-04 invece di 1981-05, 14 mesi) e **fondono in uno i due episodi del 2025** (2025-05 e
2025-08 → 2025-10 diventano 2025-05 → 2025-10, 5 mesi, non giudicabile): giugno 2025 era uno dei mesi mancanti. Da qui
un episodio e un «non giudicabile» in meno.

**Cosa cambia nello stato attuale.** La fine mese **2026-06-30** era fra i mesi mancanti (il 19 giugno è festivo). Con
la correzione il composito di quel mese è **3** (casa, lavoro e petrolio accesi; credito e tassi spenti): acceso per un
solo mese, poi 1 a luglio e ad agosto. Il referto scriveva «spento dal 2025-11»; la lettura corretta è «spento dal
2026-07, acceso nel solo giugno 2026». Il 2026 è fuori dal periodo del test (1973-2025) e non entra in nessuna misura.

**Rendimenti dopo l'accensione e sovrapposizione** (descrittivi): i mesi accesi passano da 160 a 167 e i mesi con
composito da 605 a 635; medie e mediane si muovono al più di 0,5 punti e le quote di sovrapposizione di 1-2 punti (uscita
completa nel `diff`). Il «Limite del disegno» resta com'è: la quota dei casuali sotto il reale è sempre 0,885.

**Verifica.** Uscite prima e dopo lette dai due file salvati; mesi mancanti dopo la correzione contati su
`test_f.calcola_mesi` (635 su 635); test `tests/test_f_curva.py` (riga `NA` → giorno valido precedente, mai in avanti,
limite di età).
