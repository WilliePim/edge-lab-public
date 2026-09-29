# Pre-registrazione — addendum 4: la capitalizzazione senza lookahead da split (§15.4)

Scritto il **2026-09-15, dopo i passi 2 e 4 e prima di calcolare un solo rendimento con la
correzione.** Autorizzazione dell'utente: «La correzione §15.4 rientra nel budget sopravvivenza
residuo». Integra la pre-registrazione `130b0fe` e gli addenda 1–3; dove tace, valgono quelli.
Decisione: ADR-032.

---

## 1. Lo stato di questo addendum, prima di tutto

**La correzione nasce guardando i risultati del passo 2**: il rendimento del peer contro IWM
scende con la fascia (circa +8,6% nella <50M, +1,2% nella P, −3,7% nella >300M). Un'ipotesi
formulata sui risultati non si pre-registra all'indietro.

- **Il verdetto di registro resta R1 — INCONCLUSIVO** (`82754b8`).
- Il ricalcolo corretto usa la stessa tabella R0′–R6 e si riporta marcato **POST-HOC**.
- **Se il risultato corretto sostituisce R1 lo decide l'utente**, non questo addendum.

---

## 2. Il difetto, misurato prima di scrivere

§15.4 della pre-registrazione: le azioni XBRL sono as-reported, il prezzo del panel è `Adj Close`,
rettificato all'indietro per gli split successivi. Un reverse split 1:k dopo D moltiplica per k
il prezzo storico, e con esso la cap a D; uno split in avanti la divide.

**Misura descrittiva, zero rete** (`backtest/rematch_50_300m/diagnostica_1504/misura_1504.py`):
f = prezzo d'esecuzione del Form 4 / `Adj Close` alla stessa sessione. Senza split né dividendi
successivi f ≈ 1; f < 0,67 indica un reverse split successivo.

| fascia | peer M_size con f < 0,67 | peer − IWM di quei peer | eventi con f < 0,67 | evento − IWM di quegli eventi |
|---|---:|---:|---:|---:|
| <50M | 22,3% | +3,56% | 7,7% | −18,17% |
| **50–300M** | **14,8%** | **−13,86%** | **6,8%** | −6,41% |
| >300M | 15,0% | −18,56% | 13,1% | −12,36% |

Per i peer f è preso alla transazione insider più vicina a D (distanza mediana 552 giorni nella
cella P); per gli eventi alla data dell'acquisto. Nella cella P i peer con un reverse split
successivo sono il doppio degli eventi, e quei peer rendono 14 punti sotto IWM.

---

## 3. La correzione

**cap_corretta(D) = azioni XBRL con `filed` ≤ D × `Adj Close`(D) × F(D)**, con

**F(D) = prodotto dei rapporti degli split accettati (§4) interamente successivi a D.**

Il rapporto è quello delle azioni riesposte su quelle originali: 0,1 per un reverse 1:10, 2 per
uno split 2:1. Tre casi per ciascuno split, con finestra (lo, hi]:

| D rispetto alla finestra | effetto |
|---|---|
| D ≤ lo | lo split è dopo D: entra in F(D) |
| D ≥ hi | lo split è prima di D: non entra |
| lo < D < hi | **ambiguo**: la cap a D non si calcola |

Dove si applica:

- **Peer**: cap del candidato = cap_corretta. Ambiguo → il candidato esce dal pool **a quella D**, contato.
- **Eventi, fascia e distanza**: cap_corretta con la D della riga che decideva la fascia. Se è
  ambigua o non calcolabile, vale la cap dal prezzo insider dell'addendum 3 §3 (prezzo grezzo,
  nessun lookahead), con flag `CAP_DA_PREZZO_INSIDER`.
- **Popolazione**: si ricostruisce con le fasce corrette, stessa regola (cancello → fascia → un
  evento per emittente ogni 365 giorni sull'unione). Gli eventi che cambiano cella si contano.
- **Rendimenti**: invariati. I rendimenti da `Adj Close` sono già corretti per gli split; il
  difetto sta solo nei livelli.
- **r12 di M_mom**: invariato, per la stessa ragione.

**Residuo dichiarato.** `Adj Close` rettifica anche i dividendi, e questa correzione non li tocca:
per un emittente che distribuisce, la cap storica resta un po' sottostimata. Split non rilevati
restano sbagliati come prima.

---

## 4. Quali split si accettano

**Rilevatore** (`diagnostica_1504/split_cumulato.py`, zero rete), sulle `companyfacts` XBRL in
cache (399 CIK su 400 nel campione controllato):

- concetti `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` (per periodo start–end) e
  `us-gaap:CommonStockSharesOutstanding` (per data);
- per ogni periodo, i valori in ordine di deposito. Fra due depositi consecutivi, rapporto =
  nuovo / vecchio. È candidato se ≤ 0,55 o ≥ 1,8; se è sotto 1/50 o sopra 50 si scarta come
  errore d'unità. Finestra (deposito vecchio, deposito nuovo];
- candidati concordi entro il 10% e con finestre sovrapposte si fondono nella finestra più
  stretta.

**Rapporto pulito**: il rapporto, o il suo inverso, entro il 3% di 1,5, 2, 2,5, 3, 4, 5, 6, 7,
8, 10, 12, 15, 20, 25, 30, 35, 40 o 50.

**Verifica col prezzo insider**, quando possibile:
- transazione dello stesso CIK ≤ lo ed entro 365 giorni, e transazione > hi ed entro 365 giorni;
- atteso = prodotto degli split rilevati fra le due transazioni;
- **confermato** se f_prima / f_dopo sta entro un fattore 1,5 dall'atteso; **piatto** se sta
  entro 1,25 da 1; **discorde** altrimenti.

**Regola d'accettazione:**

| categoria | verificabile | non verificabile |
|---|---|---|
| reverse o in avanti, rapporto pulito | accettato se confermato; scartato se discorde o piatto | **accettato** |
| reverse, rapporto non pulito | accettato se confermato; scartato altrimenti | scartato |
| in avanti, rapporto non pulito | scartato | scartato |

**Misura su eventi e peer M_size del passo 2** (3.763 CIK):

| categoria | confermati | discordi | piatti | non verificabili |
|---|---:|---:|---:|---:|
| reverse, pulito | 115 | 31 | 6 | 1.090 |
| in avanti, pulito | 36 | 5 | 7 | 360 |
| reverse, non pulito | 15 | 8 | 7 | 317 |

Gli split in avanti non puliti si scartano perché sulla verifica semplice ne è stato confermato
1 su 58 verificabili (`split_puliti.py`). Sono con ogni probabilità fusioni inverse: lo storico
viene riesposto col rapporto di cambio, che non è uno split del titolo quotato.

Nella cella P, dei 344 peer con f < 0,67 il rilevatore trova un reverse split dopo D per 204,
nessuno split per 113, e una finestra a cavallo di D per 25.

---

## 5. Validazione del rilevatore, prima di usarlo

Stessa logica del classificatore d'uscita (addendum 3 §5).

- **Campione**: 40 split accettati, estratti con **seme 20260915** fra quelli che entrano in almeno
  una F(D) di un evento o di un peer della cella P.
- **Documenti**: per ciascuno, una ricerca full-text EDGAR sul CIK, forme 8-K, 10-Q e 10-K, frase
  `stock split`, finestra [lo − 30, hi + 30] (1 chiamata); poi il primo documento restituito
  (1 chiamata).
- **Etichetta vera**: letta sui documenti, **senza vedere il rapporto del rilevatore**, che sta in
  un file separato (`_rilevatore.json`). Tipi: `SPLIT r` (col rapporto letto nel testo, per
  esempio «1-for-10 reverse stock split» → 0,1), `NESSUNO_SPLIT`, `NON_DETERMINABILE`. Ogni
  etichetta porta accession e citazione.
- **Concordanza**: split letto con rapporto entro il 10% da quello del rilevatore.
  NON_DETERMINABILE conta come discordante.
- **Sotto il 90% — meno di 36 su 40 — la correzione non si applica**, il ricalcolo non si fa, e
  si riporta che §15.4 non è correggibile con i dati in cache.

---

## 6. Budget

- **EDGAR: le 97 chiamate residue** del tetto di 200 dell'addendum 3, stesso contatore
  (`step2_prep/edgar_calls.json`) e stesso tetto nel codice. Circa 80 per la validazione; le
  restanti per i prezzi dei deal dei terminati in finestra che entrano nella cella P con le fasce
  corrette. Senza chiamate disponibili, quegli eventi vanno a S_zero con flag `NON_SCARICATO`.
- **yfinance**: nessuna chiamata. **Modelli linguistici**: 0.

---

## 7. Cosa si calcola, se la validazione passa

Tutto il passo 2 e il passo 4 sulla popolazione e sui peer corretti, in `step2c/` e `step4c/`,
con intestazione **POST-HOC**:
- le celle P, <50M, >300M, cluster e 4/4 × {vs IWM, M_size, M_mom};
- i placebo P1 e P2 e la tabella R0′–R6;
- la scomposizione per anno, gli scenari di sopravvivenza e il limite k;
- il closed period a W = 5, 10, 20.

**In più, come diagnostica:**
- eventi che cambiano fascia;
- peer cambiati per ciascun matching;
- candidati usciti dal pool per finestra ambigua;
- quota di eventi con `CAP_DA_PREZZO_INSIDER`;
- la stessa tabella del §2 ricalcolata con le cap corrette.

---

## 8. Ordine di esecuzione

1. commit di questo file e degli script di `diagnostica_1504/`;
2. rilevatore → `step2c_prep/split.json`, zero rete;
3. campione di validazione e documenti (EDGAR) → estratti, e `_rilevatore.json` separato;
4. etichette in `_verita_split.json`, committate prima di aprire `_rilevatore.json`;
5. concordanza;
6. **ci si ferma e si riporta all'utente**: esito della validazione, e decisione sullo stato del
   ricalcolo (§1);
7. solo dopo: popolazione corretta, deal dei nuovi terminati, passo 2 e passo 4 corretti.
