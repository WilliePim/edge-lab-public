# Pre-registrazione — Test F, segnali precoci (fermata 1)

**30 settembre 2026.** Filone drawdown_alpha, metodo standard del progetto: due fermate, nessuna misura guardata prima
della fermata 2, dato mancante dichiarato e mai sostituito, nessuna spesa LLM — regole deterministiche. Branch
`feat/early-signals`. Decisioni in `DECISIONS.md` ADR-059 (il Test E è superato da questo test) e ADR-060..067; il
lettore delle serie della Fed in `market-data/docs/adr/008-fred-alfred-ebp-gsw.md`. **Aggiornata il 01-10-2026 con le
decisioni dell'utente sulla fermata 1 (ADR-066, ADR-067)**: le sezioni toccate lo dicono. Script della fermata 2:
`backtest/drawdown_alpha/test_f.py`.

**In questa fermata non è stato calcolato nessun segnale acceso/spento, nessun colpito, nessun rendimento, nessun falso
allarme.** Sono stati costruiti solo gli eventi (le due liste sotto) e verificate le fonti con una chiamata reale ciascuna.

## Filosofia e scopo

Capire quali segnali macro anticipano i ribassi della Borsa USA legati a una recessione, di quanto, e con quanti falsi
allarmi. È la fase «prepararsi» — comprare put spread lunghi quando la protezione costa poco — non la fase «agire».
Diverso dai Test A e B (`risultati_ab.md`): lì la posizione restava aperta dal segnale al fondo e il rally intermedio
pesava più della discesa; qui si misura solo se il segnale c'è, quanto prima, e quanto spesso a vuoto. **Nessun risultato
di questa fermata, né della prossima, va tradotto in regola di portafoglio.**

## I cinque segnali e il composito — regole fissate dall'utente, nessuna ottimizzazione

Frequenza mensile: ogni segnale si valuta all'ultimo giorno di calendario di ogni mese t, con i soli dati pubblicati
entro t (ritardi nella sezione dedicata). Nessun parametro è scelto sui dati.

| # | segnale | serie | regola «acceso» |
|---|---|---|---|
| 1 | credito | excess bond premium (EBP, Gilchrist-Zakrajšek), `api.ebp()` | EBP del mese disponibile > 0 |
| 2 | tassi | near-term forward spread (Engstrom-Sharpe 2018): forward dalla curva GSW, `api.gsw()`; tasso a 3 mesi dal buono a 13 settimane DTB3, `api.fred("DTB3")` (decisione del 01-10, ADR-067) | forward a 3 mesi fra 18 mesi − tasso a 3 mesi < 0 |
| 3 | casa | permessi edilizi PERMIT, `api.fred("PERMIT", al_giorno=…)` | media degli ultimi 3 mesi < media degli ultimi 12 |
| 4 | lavoro | richieste iniziali di sussidio ICSA, `api.fred("ICSA", al_giorno=…)` | media delle ultime 4 settimane > media delle ultime 52 |
| 5 | petrolio | WTISPLC mensile, `api.fred("WTISPLC")` | prezzo del mese disponibile > massimo dei 36 mesi precedenti (Hamilton 2003) |

«Ultimi 3/12 mesi» e «ultime 4/52 settimane» sono le osservazioni disponibili alla fine del mese t, cioè quelle già
pubblicate (per PERMIT: i mesi t−3..t−1 contro t−12..t−1; per ICSA: le ultime 4 settimane pubblicate contro le ultime 52).
Per il petrolio: il valore del mese t−1 contro i 36 mesi da t−37 a t−2.

**Composito** = numero di segnali accesi, da 0 a 5. **Cella del verdetto: composito ≥ 3.** Le soglie ≥ 2 e ≥ 4 sono solo
descrittive. **Robustezza descrittiva**: composito a 4 segnali senza EBP, dal 1967 (in pratica dal gennaio 1968 per la
media a 52 settimane di ICSA; eventi con 24 mesi interi di dati dal 1970-01-01).

## Fonti — verificate con una chiamata reale il 30-09-2026, tramite il lettore nuovo

| serie | fonte e URL | prima data letta | ultima | frequenza | versioni storiche |
|---|---|---|---|---|---|
| S&P 500, chiusure | archivio EODHD, `api.prices("GSPC.INDX")` | **1927-12-30** (17,66) | 2026-09-16 | giornaliera, 24.794 sedute | — (chiusure, non riviste) |
| EBP | Fed, `federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv` (pagina «Updating the Recession Risk and the Excess Bond Premium») | **1973-01-01** (ebp −0,047) | 2026-07-01 | mensile, 643 | **no**: ristimato a ogni aggiornamento; ogni download resta con la sua data |
| curva GSW | Fed, `federalreserve.gov/data/yield-curve-tables/feds200628.csv` | **1961-06-14** | 2026-09-25 | giornaliera, 17.033 | no |
| PERMIT | FRED, `fred.stlouisfed.org/graph/fredgraph.csv?id=PERMIT` | **1960-01-01** (1.092) | 2026-08-01 | mensile, 800 | **ALFRED dal 1999-08-17** |
| ICSA | FRED, `…?id=ICSA` | **1967-01-07** (208.000) | 2026-09-19 | settimanale (sabato), 3.116 | **ALFRED dal 2009-05-28** |
| WTISPLC | FRED, `…?id=WTISPLC` (OILPRICE fino a luglio 2013, poi MCOILWTICO) | **1946-01-01** (1,17) | 2026-08-01 | mensile, 968 | ALFRED dal 2016-10-13 (non usate: media di prezzi spot, non rivista) |
| USRECM (recessioni NBER) | FRED, `…?id=USRECM` | 1854-12-01 | 2026-08-01 | mensile | — |
| DTB3 (confronto per il tasso a 3 mesi) | FRED, `…?id=DTB3` | 1954-01-04 (1,33) | 2026-09-28 | giornaliera | — |
| DGS3MO, DGS10 (Test A, confronto descrittivo) | FRED | 1981-09-01; 1962-01-02 | 2026-09-28 | giornaliera | — |
| ALFRED (versioni storiche) | `api.stlouisfed.org/fred/series/observations` | — | — | — | il 30-09 la chiave mancava (`ConfigError` prima della richiesta; senza chiave l'API risponde 400); **dal 01-10 la chiave è nel `.env`** e una chiamata reale su PERMIT al 2010-06-15 ha restituito la versione storica (ultima osservazione 2010-04 = 610 contro 637 di oggi; chiave assente dal grezzo) — ADR-064 |

Le versioni ALFRED sono lette dal campo «Release Dates» delle pagine `alfred.stlouisfed.org/series?seid=…`. Date NBER
dalla tabella `nber.org/research/data/us-business-cycle-expansions-and-contractions` (picco → minimo): 1969-12→1970-11,
1973-11→1975-03, 1980-01→1980-07, 1981-07→1982-11, 1990-07→1991-03, 2001-03→2001-11, 2007-12→2009-06, 2020-02→2020-04;
`USRECM` vale 1 esattamente in quei mesi (verificato riga per riga).

**Shiller non serve e non si usa**: l'archivio copre dal 1927 con chiusure giornaliere. **Il calendario dei backtest
parte dal 2011, ma l'archivio degli indici ha la storia intera** (ADR-061).

## Il near-term forward spread — come si calcola (ADR-062)

Engstrom e Sharpe, FEDS Notes 2018-06-28 «(Don't Fear) The Yield Curve»: «the difference between the current implied
forward rate (on Treasury bills) six quarters from now and the current yield on a three-month Treasury bill»; il forward
«is inferred from the yields to maturity on Treasury notes maturing 6 quarters from now and 7 quarters from now»; dati
trimestrali 1972:Q1-2018:Q1; fonte «Federal Reserve Bank of New York; Federal Reserve Board staff estimates». FEDS Notes
2022-03-25 «Reprise»: ntfs_t = fwd^6_t − y^1_t, «All Treasury yield data are constructed from smoothed zero-coupon yield
curves following the procedure of Gurkaynak, Sack, and Wright (2007)». Il working paper FEDS 2018-055 (PDF) non è stato
letto: nessuna libreria PDF nel venv e nessuna dipendenza nuova.

**Formula usata** (decisione dell'utente del 01-10, ADR-067: forward dalla curva GSW, tasso di oggi dal buono DTB3):

    curva GSW, parametri di Svensson del giorno (zero-coupon, capitalizzazione continua, per cento — riga
    «Zero-coupon yield, Continuously Compounded, SVENYXX» dell'intestazione del file):
    y(n) = β0 + β1·(1−e^{−n/τ1})/(n/τ1) + β2·[(1−e^{−n/τ1})/(n/τ1) − e^{−n/τ1}] + β3·[(1−e^{−n/τ2})/(n/τ2) − e^{−n/τ2}]
    forward a 3 mesi fra 18 mesi (6 → 7 trimestri):  f = [1,75·y(1,75) − 1,5·y(1,5)] / 0,25
    tasso a 3 mesi di oggi: DTB3 (H.15, «3-Month Treasury Bill Secondary Market Rate, Discount Basis») convertito
    nella stessa convenzione della curva: prezzo P = 1 − d·91/360 (TreasuryDirect, «Price = Face value (1 – (discount
    rate x time)/360)»; buono a 13 settimane = 91 giorni), poi y3m = (365/91)·ln(1/P), in per cento
    ntfs = f − y3m        acceso se ntfs < 0

Il tasso DTB3 è quello del giorno dell'osservazione GSW usata (ultimo disponibile entro 7 giorni prima, altrimenti il
segnale non è disponibile). β3 = 0 e τ2 assente prima del 1980-01-02 (Nelson-Siegel). La y(n) riproduce le colonne
`SVENY01/02` e la forward istantanea `SVENF01/02` del file su 16.286 giorni con scarto massimo 6·10⁻⁵ e 2,3·10⁻⁴ punti
(verificato prima di scriverla qui). Le scadenze 1,5 e 1,75 anni stanno dentro la parte stimata della curva dal 1961.

**Dove replica il paper**: fonte del forward (GSW), scadenza (6 → 7 trimestri), forma (forward meno «current yield on a
three-month Treasury bill»). **Dove no, dichiarato**: (a) il tasso a breve del paper viene dalla curva lisciata (Reprise
2022); qui è il buono quotato, convertito; (b) valore di fine mese (ultima osservazione con il ritardo di 11 giorni), non
media trimestrale; (c) le stime «Board staff» possono differire dal file pubblico. **Confronto descrittivo**: la versione
tutta GSW, con y(0,25) dalla stessa curva al posto di DTB3. Il confronto con i grafici del paper (1972-2018) si fa alla
fermata 2 sulle medie trimestrali della serie calcolata. **La curva 10 anni − 3 mesi del Test A resta solo come
confronto descrittivo**: qui, per coprire il 1973, GS10 − TB3MS (medie mensili H.15, FRED) del mese t−1, acceso se < 0.

## Ritardi di pubblicazione (ADR-063)

Regola: alla fine del mese t solo dati pubblicati entro t. ALFRED dove esiste; altrove serie di oggi con ritardo prudente
e revisioni non riprodotte, dichiarato.

| serie | alla fine del mese t si usa | fonte del calendario |
|---|---|---|
| EBP | il mese t−1: esce «after 10:00 a.m. on the fourth business day of each month» (luglio 2026 nel file del 2026-08-06; il file di settembre non era ancora uscito il 30-09: «subject to delay») | pagina Fed dell'EBP; `Last-Modified` del file |
| curva GSW | l'ultima osservazione con data ≤ t − 11 giorni **(deciso il 01-10: 11 giorni fissi)**: il file esce «on Tuesday for the period up to the Friday of the previous week», caso peggiore 11 giorni | pagina Fed `data/nominal-yield-curve.htm` |
| DTB3 | il valore del giorno dell'osservazione GSW (≤ t − 11): l'H.15 «is posted daily Monday through Friday at 4:15pm» con i dati del giorno lavorativo prima, FRED lo aggiorna lo stesso giorno (DTB3 «Last Updated: Sep 30, 2026 3:16 PM CDT») — ritardo di 1-2 giorni lavorativi, coperto dagli 11 | pagina Fed H.15 `releases/h15/`; pagina FRED di DTB3 |
| PERMIT | il mese t−1: il mese t esce il «12th Workday» di t+1 alle 8:30 (agosto 2026 → 17-09-2026); **con ALFRED dal 1999-08-17 la versione nota il giorno t**; prima, serie di oggi | Census `census.gov/construction/soc/schedule.html`; ALFRED |
| ICSA | le settimane con sabato ≤ t − 5 giorni (giovedì della settimana dopo: ultima osservazione 2026-09-19, versione ALFRED 2026-09-24); **con ALFRED dal 2009-05-28 la versione nota il giorno t**; prima, serie di oggi | versioni ALFRED |
| WTISPLC | il mese t−1 (agosto 2026 aggiornato su FRED il 2026-09-02); serie di oggi, media di prezzi spot non rivista | pagina FRED |
| S&P 500 | chiusura del giorno | — |
| NBER | solo per classificare gli eventi a posteriori (annunci con mesi di ritardo, nessun segnale li usa) | — |

## Regola degli eventi — proposta (ADR-060)

Chiusure giornaliere di `GSPC.INDX`. **M_t** = massimo delle chiusure nei 12 mesi di calendario che finiscono in t (t
compresa, t − 1 anno escluso; circa 252 sedute).

1. **Inizio.** Un evento parte alla prima seduta T con chiusura ≤ 0,85 × M_T mentre nessun evento è aperto. Il **massimo
   dell'evento** è la seduta P della chiusura M_T (la prima, a parità), fissato a T. Nessuna chiusura fra P e T può stare
   sotto 0,85 × M_T (avrebbe fatto partire l'evento prima), quindi il fondo si cerca da T in poi.
2. **Chiusura.** L'evento resta aperto finché l'indice non segna un **nuovo massimo a 12 mesi**: la prima seduta R > T con
   chiusura strettamente superiore a tutte le chiusure dei 12 mesi precedenti. **Fondo** = chiusura minima fra P e R. Se R
   non arriva entro la fine della serie, l'evento è aperto e il fondo è provvisorio.
3. **Niente doppi conteggi.** Mentre un evento è aperto non ne parte un altro. A R la chiusura supera tutto l'anno prima,
   quindi nessuna seduta prima di R può essere il massimo a 12 mesi di una seduta dopo R: **il massimo del nuovo evento è
   sempre ≥ R del precedente**.
4. **Ribasso da recessione.** Il mese del massimo P è fra il mese di inizio della recessione − 12 mesi (compreso) e il mese
   del minimo (compreso). **Inizio = mese del picco NBER** (USRECM) — **deciso dall'utente il 01-10 (ADR-066): il 2000
   è dentro, 6 eventi per il verdetto, servono almeno 4 colpiti (2/3)**. La convenzione «la recessione inizia il mese
   dopo il picco» (USREC, 5 eventi) resta come robustezza descrittiva.
4b. **1980 fusi (robustezza descrittiva, ADR-066).** I due eventi da recessione del 1980 (massimi 1980-02-13 e
   1980-11-28) si fondono in uno: massimo = il primo (1980-02-13, 118,44), finestra del colpito unica dal 1978-02-13
   (24 mesi prima del primo massimo) alla data del −10% del secondo evento (unione delle due finestre), fondo = il
   minimo dei due. Nel verdetto i due eventi restano distinti e lo stesso segnale può contare per entrambi.
5. **Periodo 1973-2025**: massimo ≥ 1973-01-01 e data del −15% ≤ 2025-12-31.
6. **Stato.** *Verdetto*: da recessione e massimo ≥ 1975-01-01 (24 mesi interi di tutti e cinque i segnali: l'EBP parte
   dal gennaio 1973). *Descrittivo*: senza recessione, o con meno di 24 mesi di dati. *Non incluso*: fuori dal periodo
   (mostrati per contesto).

**Esempi sui casi reali.** 1980: massimo a 12 mesi 1980-02-13 (118,44), −15% il 1980-03-24 dopo 27 sedute, fondo
1980-03-27 (98,22, −17,1%), chiuso il 1980-07-14 quando la chiusura supera tutte quelle dell'anno prima; con il massimo
storico (120,24 del 1973-01-11, superato solo il 1980-07-17) questo evento non esiste. 1980-81: il 1980-11-28 (140,52) è
già un nuovo massimo, e la discesa fino al 1982-08-12 (−27,1%) è un secondo evento distinto in tutte e due le liste.
2000-02: −15% il 2000-12-20 dopo 188 sedute dal massimo del 2000-03-24; fondo 2002-10-09 (−49,1%); chiuso il 2003-09-02
(nuovo massimo a 12 mesi) contro il 2007-05-30 (nuovo massimo storico). 2020: −15% dopo 13 sedute.

## Le due liste di eventi affiancate

Colonne: massimo (data, chiusura), data del −15%, sedute da P al −15%, fondo, profondità, chiusura dell'evento (R),
recessione NBER associata (picco → minimo), stato. Uscita di `python backtest/drawdown_alpha/eventi_f.py` del 30-09-2026.

### A — massimo delle chiusure degli ultimi 12 mesi (regola del Test F)

| # | massimo | data −15% | sedute | fondo | profondità | chiusura evento | recessione NBER | stato |
|---|---|---|---:|---|---:|---|---|---|
| 1 | 1966-02-09 (94,06) | 1966-08-19 | 133 | 1966-10-07 (73,20) | −22,2% | 1967-04-21 | no | non incluso (prima del 1973) |
| 2 | 1968-11-29 (108,37) | 1969-07-25 | 158 | 1970-05-26 (69,29) | −36,1% | 1971-01-12 | no **(al limite: 12 mesi + 2 giorni prima del picco NBER 1969-12)** | non incluso (prima del 1973) |
| 3 | 1973-01-11 (120,24) | 1973-07-03 | 119 | 1974-10-03 (62,28) | −48,2% | **1975-06-23** | 1973-11 → 1975-03 | **descrittivo (meno di 24 mesi di EBP)** |
| 4 | **1976-12-31 (107,46)** | 1977-10-25 | 206 | 1978-03-06 (86,90) | −19,1% | 1978-07-31 | no | descrittivo (senza recessione) — **solo in A** |
| 5 | **1980-02-13 (118,44)** | 1980-03-24 | 27 | 1980-03-27 (98,22) | −17,1% | 1980-07-14 | 1980-01 → 1980-07 (massimo dentro la recessione) | **verdetto — solo in A** |
| 6 | 1980-11-28 (140,52) | 1981-09-08 | 195 | 1982-08-12 (102,42) | −27,1% | **1982-10-07** | 1981-07 → 1982-11 | verdetto |
| 7 | 1987-08-25 (336,77) | 1987-10-16 | 37 | 1987-12-04 (223,92) | −33,5% | **1988-10-18** | no | descrittivo (senza recessione) |
| 8 | 1990-07-16 (368,95) | 1990-08-23 | 28 | 1990-10-11 (295,46) | −19,9% | 1991-02-13 | 1990-07 → 1991-03 | verdetto |
| 9 | 1998-07-17 (1.186,75) | 1998-08-31 | 31 | 1998-08-31 (957,28) | −19,3% | 1998-11-23 | no | descrittivo (senza recessione) |
| 10 | 2000-03-24 (1.527,46) | 2000-12-20 | 188 | 2002-10-09 (776,76) | −49,1% | **2003-09-02** | 2001-03 → 2001-11 **(al limite: fuori se l'inizio è il mese dopo il picco)** | verdetto |
| 11 | 2007-10-09 (1.565,15) | 2008-01-18 | 70 | 2009-03-09 (676,53) | −56,8% | **2009-10-12** | 2007-12 → 2009-06 | verdetto |
| 12 | **2010-04-23 (1.217,28)** | 2010-06-30 | 47 | 2010-07-02 (1.022,58) | −16,0% | 2010-11-04 | no | descrittivo (senza recessione) — **solo in A** |
| 13 | **2011-04-29 (1.363,61)** | 2011-08-08 | 69 | 2011-10-03 (1.099,23) | −19,4% | 2012-02-24 | no | descrittivo (senza recessione) — **solo in A** |
| 14 | 2018-09-20 (2.930,75) | 2018-12-20 | 63 | 2018-12-24 (2.351,10) | −19,8% | 2019-04-23 | no | descrittivo (senza recessione) |
| 15 | 2020-02-19 (3.386,15) | 2020-03-09 | 13 | 2020-03-23 (2.237,40) | −33,9% | 2020-08-18 | 2020-02 → 2020-04 | verdetto |
| 16 | 2022-01-03 (4.796,56) | 2022-05-09 | 87 | 2022-10-12 (3.577,03) | −25,4% | **2023-06-12** | no | descrittivo (senza recessione) |
| 17 | 2025-02-19 (6.144,15) | 2025-04-04 | 32 | 2025-04-08 (4.982,77) | −18,9% | 2025-06-27 | no | descrittivo (senza recessione) |

### B — massimo storico (definizione comune del filone, `episodi.py`)

| # | massimo | data −15% | sedute | fondo | profondità | chiusura evento | recessione NBER | stato |
|---|---|---|---:|---|---:|---|---|---|
| 1 | 1966-02-09 (94,06) | 1966-08-19 | 133 | 1966-10-07 (73,20) | −22,2% | 1967-05-04 | no | non incluso |
| 2 | 1968-11-29 (108,37) | 1969-07-25 | 158 | 1970-05-26 (69,29) | −36,1% | 1972-03-06 | no (al limite, come sopra) | non incluso |
| 3 | 1973-01-11 (120,24) | 1973-07-03 | 119 | 1974-10-03 (62,28) | −48,2% | **1980-07-17** | 1973-11 → 1975-03 | descrittivo (meno di 24 mesi) |
| 4 | 1980-11-28 (140,52) | 1981-09-08 | 195 | 1982-08-12 (102,42) | −27,1% | **1982-11-03** | 1981-07 → 1982-11 | verdetto |
| 5 | 1987-08-25 (336,77) | 1987-10-16 | 37 | 1987-12-04 (223,92) | −33,5% | **1989-07-26** | no | descrittivo |
| 6 | 1990-07-16 (368,95) | 1990-08-23 | 28 | 1990-10-11 (295,46) | −19,9% | 1991-02-13 | 1990-07 → 1991-03 | verdetto |
| 7 | 1998-07-17 (1.186,75) | 1998-08-31 | 31 | 1998-08-31 (957,28) | −19,3% | 1998-11-23 | no | descrittivo |
| 8 | 2000-03-24 (1.527,46) | 2000-12-20 | 188 | 2002-10-09 (776,76) | −49,1% | **2007-05-30** | 2001-03 → 2001-11 (al limite) | verdetto |
| 9 | 2007-10-09 (1.565,15) | 2008-01-18 | 70 | 2009-03-09 (676,53) | −56,8% | **2013-03-28** | 2007-12 → 2009-06 | verdetto |
| 10 | 2018-09-20 (2.930,75) | 2018-12-20 | 63 | 2018-12-24 (2.351,10) | −19,8% | 2019-04-23 | no | descrittivo |
| 11 | 2020-02-19 (3.386,15) | 2020-03-09 | 13 | 2020-03-23 (2.237,40) | −33,9% | 2020-08-18 | 2020-02 → 2020-04 | verdetto |
| 12 | 2022-01-03 (4.796,56) | 2022-05-09 | 87 | 2022-10-12 (3.577,03) | −25,4% | **2024-01-19** | no | descrittivo |
| 13 | 2025-02-19 (6.144,15) | 2025-04-04 | 32 | 2025-04-08 (4.982,77) | −18,9% | 2025-06-27 | no | descrittivo |

**Differenze (in grassetto sopra).** A ha 17 eventi, B 13: A aggiunge **1976-12-31**, **1980-02-13** (il caso che ha
motivato la regola: con il massimo storico il 1980 non è un evento nuovo, perché il 120,24 del 1973 fu superato solo il
1980-07-17), **2010-04-23** e **2011-04-29**. Massimo, data del −15%, fondo e profondità coincidono per gli eventi in
comune; cambia la data di chiusura (nuovo massimo a 12 mesi in A, nuovo massimo storico in B: per il 1973 quasi cinque
anni di differenza, per il 2000 quattro, per il 2007 tre e mezzo). **Eventi per il verdetto: 6 in A** (1980-02, 1980-11,
1990-07, 2000-03 al limite, 2007-10, 2020-02) **e 5 in B**.

## Casi al limite, segnalati ora

1. **2000**: massimo 2000-03-24, picco NBER marzo 2001. Con «inizio = mese del picco» il mese del massimo (2000-03) è
   esattamente il dodicesimo prima e **rientra**; con «inizio = mese dopo il picco» (USREC, la lettera della definizione
   NBER «recessions start in the month after a peak») **esce per otto giorni**. **Deciso il 01-10: mese del picco, il
   2000 è dentro**; l'altra convenzione è una robustezza descrittiva.
2. **1968-11-29** (fuori periodo, ma dentro la robustezza a 4 segnali): 12 mesi e 2 giorni prima del picco NBER
   1969-12 → «senza recessione» per la regola. Se l'utente vuole contarlo, la regola diventa «13 mesi» e va detto ora.
3. **1973-01-11**: massimo 11 giorni dopo l'inizio del periodo; l'EBP parte dal gennaio 1973, quindi i 24 mesi prima del
   massimo non ci sono → descrittivo nel composito a 5; nel composito a 4 senza EBP i 24 mesi ci sono (dal 1970-01-01).
4. **1980-02-13 e 1980-11-28**: due eventi da recessione con massimi a nove mesi di distanza; le finestre «24 mesi prima
   del massimo» si sovrappongono (1978-02 → 1980-03 e 1978-11 → 1981-09), quindi **lo stesso episodio acceso può contare
   come colpito per tutti e due**. **Deciso il 01-10: nel verdetto restano due eventi; robustezza descrittiva con i due
   fusi** (regola 4b sopra).
5. **1980-02-13**: il massimo è dentro la recessione (gennaio-luglio 1980), l'evento dura 27 sedute fino al −15% e il
   −10% arriva ancora prima: la finestra del colpito si chiude presto.
6. **1990-07-16 e 2020-02-19**: il massimo cade nel mese stesso del picco NBER.
7. **2022-01-03** e **2025-02-19**: ribassi ≥ 15% senza recessione NBER: descrittivi e, per la definizione di falso
   allarme sotto, un'accensione che li precede **non** è un falso allarme (ribasso ≥ 15% con o senza recessione).
8. **Evento aperto**: nessuno alla fine della serie (2026-09-16).

## Misure e verdetto — copiati dal testo dell'utente, da calcolare solo alla fermata 2

- **Colpito** = composito acceso (≥ 3) in almeno una fine mese fra 24 mesi prima del massimo e il momento in cui l'indice
  perde il 10% dal massimo (prima chiusura ≤ 0,90 × massimo).
- **Anticipo in mesi** (dalla prima accensione nella finestra al massimo) e **confronto con la regola di Faber**:
  chiusura mensile sotto la media delle ultime 10 chiusure mensili (Faber 2007, «A Quantitative Approach to Tactical
  Asset Allocation»), sulla stessa serie `GSPC.INDX`.
- **Falso allarme** = episodio di accensione senza ribasso ≥ 15% (con o senza recessione) che parte entro 24 mesi;
  episodi separati da meno di 3 mesi contano come uno. *Lettura operativa (scritta il 01-10, prima di calcolare)*:
  episodio = fini mese consecutive con composito ≥ 3, uniti se fra l'ultimo mese acceso dell'uno e il primo dell'altro
  passano meno di 3 mesi; l'episodio che inizia al mese s **non** è un falso allarme se esiste un evento della lista A
  (qualunque stato) con massimo fra s e s + 24 mesi, oppure con s fra il massimo e il fondo (l'allarme arriva durante
  una discesa già in corso); un episodio che inizia a meno di 24 mesi dall'ultima seduta disponibile è «non
  giudicabile» e si conta a parte. Gli episodi si contano da quando il composito a 5 esiste (1973-02).
- **Quota del tempo acceso**: quota delle fini mese con composito ≥ 3 fra quelle in cui tutti e cinque i segnali
  esistono (1973-02 → 2025-12); anche per ≥ 2 e ≥ 4 e per ogni singolo segnale.
- **Rendimento dell'S&P a 3/6/12 mesi dopo l'accensione del composito, contro tutti i mesi**: chiusura dell'ultima seduta
  del mese; media, mediana e quota di rendimenti negativi, su (i) tutte le fini mese con composito ≥ 3, (ii) la prima
  fine mese di ogni episodio, (iii) tutte le fini mese con composito disponibile.
- **Matrice di sovrapposizione**: per ogni coppia ordinata (A, B), quota delle fini mese con A acceso in cui anche B è
  acceso; le coppie oltre l'80% si segnalano.
- **Falsi eventi (deciso il 01-10, ADR-066)**: 1000 serie casuali; ogni serie ha tanti eventi quanti quelli del verdetto
  (6), con **date di inizio uniformi** fra le fini mese del 1975-01 → 2025-12 e **episodi non sovrapposti**; la finestra
  di ogni falso evento ha la stessa lunghezza di quella del corrispondente evento reale (24 mesi prima del massimo più i
  mesi dal massimo al −10%) e deve finire entro il 2025-12; un falso evento è «colpito» con la stessa regola dei veri.
  **Seme fisso: 20261001** (`random.Random(20261001)`, `test_f.py`). Il tasso di colpiti reale si confronta con la
  distribuzione dei 1000 tassi casuali (quota dei casuali strettamente sotto il reale).
- **Verdetto pre-registrato** (solo ribassi da recessione, composito ≥ 3):
  **REGGE** se (a) colpiti ≥ 2/3 dei ribassi da recessione, (b) falsi allarmi ≤ colpiti, (c) tasso di colpiti > 90°
  percentile dei falsi eventi; **NON REGGE** se fallisce (a); **INCONCLUSIVO** se (a) regge ma fallisce (b) o (c).
  **6 eventi, servono almeno 4 colpiti** (deciso il 01-10). (c) si legge come: la quota dei 1000 tassi casuali
  strettamente sotto il tasso reale supera 0,90.
- **Robustezze descrittive** (nessuna entra nel verdetto): recessione dal mese dopo il picco (5 eventi); 1980 fusi; composito
  a 4 senza EBP dal 1967 (cella ≥ 3 su 4 e ≥ 2 su 4, eventi da recessione con massimo ≥ 1970-01-01, 1973 compreso);
  10 anni − 3 mesi del Test A (GS10 − TB3MS) come confronto; versione tutta GSW del segnale 2; medie trimestrali del
  near-term forward spread 1972-2018 confrontate con i grafici del paper, se possibile.

## Limiti dichiarati

- **EBP ristimato**: il file di oggi riscrive tutta la storia a ogni aggiornamento; il segnale 1 usa la versione del
  30-09-2026 (file del 2026-08-06) e non quella nota all'epoca. Non esiste un'alternativa con versioni.
- **Chiave ALFRED** (ADR-064): mancava il 30-09 (bloccante); **dal 01-10 è nel `.env`** e la chiamata reale è verificata:
  non più bloccante. Prima del 1999-08-17 (PERMIT) e del 2009-05-28 (ICSA) le versioni non esistono comunque: serie di
  oggi con i ritardi dichiarati, revisioni non riprodotte.
- **Curva GSW**: ritardo fisso di 11 giorni; valore di fine mese invece di media trimestrale; nella versione di
  confronto y(0,25) è un'estrapolazione sotto l'anno.
- **DTB3**: la conversione da sconto a rendimento continuo assume 91 giorni alla scadenza (buono a 13 settimane) e la
  quotazione denaro del mercato secondario dell'H.15.
- **Shiller**: non usato.
- **Russell 2000**: tolto dal Test F (decisione del 01-10, ADR-066).
- **Working paper FEDS 2018-055** non letto (PDF; solo i due FEDS Notes in HTML).
- **NBER a posteriori**: la classificazione degli eventi usa date annunciate mesi dopo; nessun segnale le usa.

## Cosa resta fissato dopo questa fermata

I cinque segnali e il composito con le loro regole; le fonti e la prima data di ciascuna; la formula del near-term forward
spread e le sue deviazioni dal paper; i ritardi di pubblicazione; la regola degli eventi con le due liste; i casi al
limite; le misure e il verdetto. **Decisioni prese dall'utente il 01-10-2026 (ADR-066, ADR-067), prima di qualunque
calcolo**: inizio della recessione = mese del picco NBER (6 eventi, almeno 4 colpiti; il mese dopo come robustezza);
regola degli eventi come proposta, 1980 distinti nel verdetto e fusi in una robustezza; Russell 2000 tolto; tasso a 3 mesi
da DTB3 convertito, forward dalla curva GSW, versione tutta GSW come confronto; ritardo GSW 11 giorni fissi; falsi eventi
con episodi non sovrapposti, inizi uniformi, seme 20261001. Da qui le regole non cambiano più.
