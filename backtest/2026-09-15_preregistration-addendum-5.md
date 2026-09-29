# Pre-registrazione — addendum 5: correzione dello split lookahead con la tabella di Yahoo

Scritto il **2026-09-15, dopo il verdetto R1 del passo 2, dopo il fallimento dell'addendum 4 (33/40,
ADR-033) e prima di calcolare l'esito della validazione di questo addendum o un solo rendimento
corretto.** Decisione: ADR-034 e ADR-035.

---

## 1. Stato, deciso dall'utente prima di questo file

- **R1 del ri-test resta INCONCLUSIVO**, qualunque cosa dia il ricalcolo. Il ricalcolo è **POST-HOC** e
  descrittivo.
- La correzione dello split lookahead sulla market cap si fa **una volta sola** e **vale per ogni backtest
  che usa lo stesso panel**.
- **Metodo: la tabella degli split di Yahoo** (scelta dell'utente fra Yahoo, un nuovo addendum XBRL e
  nessuna correzione).
- Dopo questo ricalcolo **il filone insider è chiuso**: niente passo 4 corretto, niente passo 5.

---

## 2. La fonte

`state/backfill/splits.json`, scaricato il 2026-09-15 con yfinance (`actions=True`) per i 5.835 ticker
di `prices/` e `prices_resolved/`. Per i ticker il cui file porta il nome vecchio (recupero del panel,
`price_failures_classified.json`, campo `changed`) la tabella è chiesta al ticker corrente.

| | ticker |
|---|---:|
| tabella ottenuta (`OK`) | **4.058** |
| senza risposta (`SCONOSCIUTO`) | **1.777** |

**I 1.777 non sono un rate limit.** Verificato il 2026-09-15 sull'endpoint `chart` di Yahoo, quello dei
prezzi, con `range=max`, `range=10y`, `range=5y` e un intervallo esplicito: CRVN, CRWK e CMIIU rispondono
404 «No data found», CSBQ zero barre; un ticker di controllo (AAA nella copia pubblica) risponde. 1.752 di loro hanno una serie su disco
che arriva oltre il 2026-08-20: Yahoo li serviva al momento del download del panel e oggi no.

**Perché questa fonte.** È la tabella con cui Yahoo ha rettificato `adj_close`: annullarla non richiede di
indovinare una data né un rapporto.

### 2.1 Fonte integrativa: EDGAR, solo dove serve (scelta dell'utente)

Quando sono stati scaricati, anche i ticker `SCONOSCIUTO` avevano l'`adj_close` rettificato da Yahoo:
manca solo la tabella. Si cerca su EDGAR **solo per quelli che contano e che mostrano uno split**.

**Misura fatta prima di questa regola** (senza rete, soli acquisti `form4_raw/`, salto = rapporto insider
oltre 1,8× fra due transazioni entro circa un anno): fra i ticker usati, senza tabella e con un salto,
46 peer della cella P del ri-test; **154 nell'intero pool**; circa 160 non verificabili. *(Copia pubblica:
tolto il conteggio delle serie di un altro studio che usa lo stesso panel.)*

- **Insieme**: ticker `SCONOSCIUTO` delle serie del pool (regola di `step2_analysis.Pool`) e delle serie
  degli eventi del ri-test (più, nel repo d'origine, quelle di un catalogo di eventi non pubblicato:
  `backtest/splits.py` ora riceve la popolazione come argomento).
- **Salto**: transazioni insider (acquisti di `form4_raw/` e vendite di `sales.jsonl`, prezzo > 0, media
  ponderata per giorno) dei CIK di quel ticker; f come al §4; due transazioni consecutive a **non più di 365
  giorni** con **|ln(f_a / f_b)| > ln 1,8**. Finestra del salto = (d_a, d_b]; salti sovrapposti dello stesso
  ticker si fondono.
- **Ricerca**: full-text EDGAR, frase `"stock split"`, sul CIK, depositi fra d_a − 30 e d_b + 60 giorni; si
  leggono al più 2 documenti in ordine di deposito, prima gli 8-K.
- **Regex**: rapporto `(N|parola)[- ](for|to)[- ](M|parola) … (reverse )?(stock |share )?split`, r = N / M
  («1-for-10» → 0,1; «3-for-2» → 1,5); il più ricorrente nel documento. Data: la prima `effective … DATA`
  entro 300 caratteri dal rapporto; altrimenti la data di deposito del documento, flag `DATA_DA_DEPOSITO`.
- **Accettazione**: |ln((f_a / f_b) / r)| ≤ ln 1,5 **e** data in (d_a − 30, d_b]. Altrimenti il salto resta
  senza split, F = 1 con flag.
- **Tetto: 500 chiamate EDGAR**, contatore `backtest/split_edgar_calls.json`, nel codice.

Lo split accettato entra nel fattore del §3 come quelli di Yahoo, con stato `OK_EDGAR`.

---

## 3. La correzione

Con r_t = azioni nuove / azioni vecchie (2:1 → 2; 1:10 → 0,1) e `end` = data del record di azioni usato:

**cap(D) = azioni(end) × adj_close(D) × F**, **F = ∏ r_t per gli split con end < t ≤ ultima barra della serie**.

Uno split dopo l'ultima barra non è dentro `adj_close` e non entra. Ticker `SCONOSCIUTO` → **F = 1, flag
`SPLIT_SCONOSCIUTO`, contato**: non diventa «nessuno split» (fail-closed).

**Dove si applica nel ri-test** (`backtest/rematch_50_300m/split_fix.py`):
- fascia degli eventi osservati: `mcap` di `marketcap_rows.jsonl` × F, col record di azioni che
  `marketcap_build.py` @ `ef0ff29` ha usato (ultimo `filed` ≤ `trans`, `primary or fallback`) e il ticker
  della riga;
- cap dei candidati nel `Pool`: azioni `primary` × F per record;
- cap dell'evento per la distanza (ADR-006): azioni × F.

Non cambiano: la cap dei non osservati e dei terminati (prezzo insider, grezzo) e tutti i rendimenti
(`adj_close` è già corretto per gli split nei rapporti).

---

## 4. Validazione, prima di usarla — zero chiamate

**Split da validare**: tutti quelli della tabella con data fra il 2014-01-01 e il 2026-08-28, di un ticker
che ha transazioni insider verificabili.

**Verifica col prezzo insider** (la regola dell'addendum 4 §4, qui applicata alla tabella di Yahoo):
- ticker → CIK: gli `issuer_cik` del corpus che portano quel ticker;
- transazioni: righe con prezzo > 0 di `form4_raw/` (acquisti) e di `sales.jsonl` (vendite) di quei CIK;
- f = prezzo della transazione / `adj_close` alla sua sessione (ultimo close entro 5 sessioni);
- f_prima = ultima transazione nei 365 giorni prima della data dello split; f_dopo = prima transazione nei
  365 giorni dopo; **atteso** = prodotto degli split della tabella fra le due transazioni; **osservato** =
  f_prima / f_dopo;
- **CONFERMATO** se |ln(osservato/atteso)| ≤ ln 1,5 **e** |ln(osservato/atteso)| < |ln osservato|;
  altrimenti **PIATTO** se |ln osservato| ≤ ln 1,25; altrimenti **DISCORDE**.

**Soglia: CONFERMATI / (CONFERMATI + PIATTI + DISCORDI) ≥ 90%.** Sotto, la correzione **non si applica
da nessuna parte**, né qui né altrove, e lo si riporta. Si riportano anche i non verificabili e la quota di
cap dei peer toccata da `SPLIT_SCONOSCIUTO`.

---

## 5. Cosa si calcola, se la validazione passa

`survival.py popolazione` con le fasce corrette → `step2y_prep/`; `step2_analysis.py` con pool e distanze
corrette → `step2y/`, intestazione **POST-HOC**. Stesse celle, stessi placebo, stessa tabella R0′–R6.
Prezzi dei deal e validazione del classificatore si riusano; un CIK nuovo senza deal va a S_zero con flag
`DEAL_NON_CERCATO`. In più: eventi che cambiano fascia, peer cambiati.

**Nessuna chiamata EDGAR, nessun modello linguistico.**
