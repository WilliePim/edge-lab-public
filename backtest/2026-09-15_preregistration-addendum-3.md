# Pre-registrazione — addendum 3: sopravvivenza

Scritto il **2026-09-15, prima di qualunque rendimento del passo 2**, dopo la revisione
dell'utente. Sostituisce l'addendum 1 §5 e la riga R0 della tabella dell'addendum 1 §4; per il
resto integra. Decisioni: [`DECISIONS.md`](../DECISIONS.md), ADR-022 … ADR-029. Codice:
[`rematch_50_300m/survival.py`](rematch_50_300m/survival.py), committato con questo file.

I numeri di questo file segnati *esplorativi* vengono da misure sulla sola cache, senza
rendimenti, fatte per scrivere le regole. Quelli definitivi escono da `survival.py
popolazione` dopo il commit.

---

## 1. Cosa cambia

| | addendum 1 | addendum 3 |
|---|---|---|
| popolazione della cella | osservati, un evento per emittente ogni 365 giorni | osservati **e** non osservati con fascia dal prezzo insider, stessa regola sull'unione (§3) |
| su cosa si legge il verdetto | osservati | **osservati + risolti** (§2) |
| sopravvivenza | S0 e S1 su tutti i non osservati attesi | prima la mappatura dei ticker; poi classi d'uscita **solo** per chi termina dentro la finestra (§4, §6) |
| R0 | segno fra S0 e S1 | **R0′**: segno fra S_zero e S0 sui soli terminati in finestra senza classe — **non vincola** (§7) |
| vivi non osservati | — | fuori dal verdetto; copertura e limite k (§8) |
| S1 (+15%) | scenario | **abolito** |

---

## 2. Prima la mappatura dei ticker

Un evento senza serie in `prices/` il cui CIK ha **oggi** almeno un ticker nelle submissions
EDGAR (campo `tickers`) non è un delisting: è un guasto di mappatura.

- La serie si cerca, per i ticker di oggi, in `state/backfill/prices/` e poi in
  `state/backfill/prices_resolved/`. Quest'ultima è stata scaricata il 2026-09-15 con yfinance
  (Adj Close, dal 2013-01-01) per i 115 ticker degli 84 emittenti che ne erano privi: 70 serie
  scritte, 45 ticker senza dati dopo due passate. `prices/` non cambia e la sua impronta nella
  pre-registrazione resta valida; l'impronta di `prices_resolved/` va nel report di popolazione.
- **`RISOLTO`**: la serie ha una barra entro 5 sessioni dalla prima sessione dopo il deposito.
  Entra nel campione con quella serie; rendimenti come per gli osservati (addendum 2).
- **`VIVO_SENZA_STORIA`**: la serie comincia dopo l'ingresso — il ticker è cambiato e la storia
  vecchia non c'è più (FNTE → IMXI). Vivo non osservato (§8).
- **`GUASTO_FONTE`**: il ticker di oggi non ha serie in nessuna fonte. Vivo non osservato.

**Seconda fonte: non esiste nel repo.** Verificato il 2026-09-15: l'unico fornitore di prezzi
nel codice è yfinance (5 import); nessun'altra directory di prezzi su disco; gli strumenti
rimossi con la potatura che toccavano i prezzi (`backfill_prices.py`, `backtest_v1.py`,
`price_source_gap.py`) usavano la stessa fonte e la stessa `prices/`; nessuno dei ticker in
guasto esiste in un altro file.

**Osservati con serie finita prima dell'uscita** (`ENDED_IN_WINDOW`, addendum 2): se il CIK ha un
ticker di oggi con una serie che riprende entro 5 sessioni dall'ultima barra, le due serie si
**giuntano a rapporto 1** — stesso CIK, stesso registrante — con flag `GIUNTURA`. Altrimenti
ultimo prezzo piatto. Nessuna soglia di continuità: il giorno di una fusione può avere un salto
vero.

---

## 3. Fascia dei non osservati, e popolazione

**Cap** = azioni XBRL con `filed` ≤ D (regola di `marketcap_build.py` al commit `ef0ff29`) ×
prezzo medio ponderato delle righe insider dell'evento, con D = data dell'ultima transazione
≤ deposito. È l'unico prezzo che esiste per tutti gli emittenti senza serie.

**Validato sugli osservati** (esplorativo): su 31.501 eventi con entrambe le cap, **stessa fascia
nell'88,9%**; rapporto con la cap del backfill mediano 1,033, p10 0,50, p90 1,51. Delle vere
50–300M, 773 finiscono in >300M e 337 in <50M. La coda larga è con ogni probabilità il difetto
documentato in `marketcap_build.py` — azioni as-reported per `Adj Close`, rettificato per split
e dividendi — mentre il prezzo insider è grezzo. Non verificato evento per evento.

Gli **osservati** tengono la fascia originale (`marketcap_rows.jsonl`). Gli eventi senza serie e
senza azioni XBRL non hanno fascia, stanno fuori da tutte le celle e si contano (esplorativo:
5.441 in variante (a), tutte le bande).

**Popolazione**, per ciascuna fascia: cancello → fascia → un evento per emittente ogni 365 giorni,
**sull'unione** di osservati e non osservati. L'insieme osservato cambia di poco rispetto
all'addendum 1 (esplorativo: 2.329 contro 2.340), perché il filtro ora vede anche gli eventi non
osservati dello stesso CIK.

---

## 4. Il classificatore d'uscita

Per gli emittenti senza ticker oggi, dalle submissions in cache, zero chiamate.

- **T_end** = ultima data di un Form 25, 25-NSE, 15-12B, 15-12G o 15-15D; se non ce ne sono,
  ultimo deposito di qualunque tipo.
- **W** = [T_end − 365 giorni, T_end + 30 giorni].
- Classe, con questa precedenza:

| # | classe | regola |
|---|---|---|
| 1 | `FALLIMENTO` | 8-K con item **1.03** in W |
| 2 | `LIQUIDAZIONE` | «LIQUIDAT» nel nome attuale o in un nome precedente |
| 3 | `ACQUISIZIONE` | DEFM14A, DEFM14C, SC TO-T, SC 13E3, SC 13E-3, SC TO-C o **SC 14D9** in W, oppure 8-K con item **5.01** in W |
| 4 | `VOLONTARIO_OTC` | un Form 25 o 15 in W, oppure 8-K con item 3.01 in W |
| 5 | `NON_RISOLTO` | altrimenti |

La regola 3 estende la regola di acquisizione di uno strumento precedente (le forme di acquisizione DEFM14A, DEFM14C, SC TO-T, SC 13E3, SC 13E-3, SC TO-C; strumento non incluso nella copia
pubblica), che non poteva leggere gli item degli 8-K da `form.idx`: le submissions li portano, e con l'item 1.03 il fallimento diventa separabile.

**Posizione rispetto alla finestra dell'evento** (ingresso s0 = prima sessione dopo il deposito,
uscita = s0 + 126):

| stato | regola | trattamento |
|---|---|---|
| `USCITO_PRIMA` | T_end < deposito | **non è un evento: fuori dal campione** |
| `TERMINATO_IN_FINESTRA` | T_end ≤ data di uscita | scenari del §6 |
| `USCITO_DOPO` | T_end > data di uscita | vivo durante la finestra, non osservato (§8) |
| `TOO_RECENT` | uscita oltre la cache | escluso, come per gli osservati |

---

## 5. Validazione del classificatore — prima di usarlo

- **Campione**: tutti gli emittenti `TERMINATO_IN_FINESTRA` della cella P. Se sono meno di 40,
  si integrano fino a 40 con un'estrazione a **seme 20260915** fra gli emittenti
  `TERMINATO_IN_FINESTRA` delle celle <50M e >300M; se sono più di 40, se ne estraggono 40 con
  lo stesso seme.
- **Documenti letti** per emittente: l'ultimo Form 25 o 25-NSE in W, e l'8-K in W con l'item
  preferito 1.03 > 5.01 > 2.01 > 3.01 (il più recente); se nessuno, l'ultimo 8-K in W.
- **Etichetta vera**: assegnata leggendo quei documenti in questa sessione, **prima di aprire la
  classe del classificatore**, che `survival.py` scrive in un file separato
  (`_classificatore.json`). Ogni etichetta porta accession e citazione, così si verifica. Tipi:
  ACQUISIZIONE, FALLIMENTO, LIQUIDAZIONE, VOLONTARIO_OTC, NON_DETERMINABILE.
- **Concordanza** = concordanti ÷ 40. NON_DETERMINABILE conta come discordante, salvo quando il
  classificatore dice NON_RISOLTO.
- **Se la concordanza è sotto il 90% — meno di 36 su 40 — il classificatore non si usa**, e tutti
  i terminati in finestra vanno a S_zero con flag `CLASSIFICATORE_NON_VALIDATO`. Il verdetto non
  può dipendere da un classificatore non validato.

---

## 6. Valori degli scenari (terminati in finestra, classificatore validato)

| classe | scenario | eccesso dell'evento |
|---|---|---|
| ACQUISIZIONE, deal **in contanti** leggibile | **S_acq** | r_deal − r_peer |
| ACQUISIZIONE, deal in azioni, misto, ambiguo, non trovato o non scaricato | S_zero, flag | 0 |
| FALLIMENTO | **S0** | −100% − r_peer |
| LIQUIDAZIONE, distribuzione per azione leggibile | **S_acq** | come sopra, con la distribuzione al posto del deal |
| LIQUIDAZIONE senza distribuzione leggibile | S_zero, flag | 0 |
| VOLONTARIO_OTC | S_zero, flag `OTC_SENZA_PREZZO` | 0 |
| NON_RISOLTO | S_zero (e S0 nel test del §7) | 0 |

**S_acq nel dettaglio.**

- **Prezzo del deal**: dal più recente fra l'8-K in W con item 5.01, 2.01 o 8.01, poi DEFM14A o
  DEFM14C, poi SC TO-T; ci si ferma al primo documento con esito CONTANTI o MISTO.
- **Regex dichiarate** (`survival.py`, `CONTANTI` e `MISTO`), su testo a spazi compressi:
  - `right to receive (an amount in cash equal to)? $X (per share)? in cash`
  - `$X per share (of …)? in cash` oppure `… net to the seller(s)/holder(s) in cash`
  - `(merger|offer|per share) (consideration|price) of $X (per share)? in cash`
  - `liquidating distribution(s) of|totaling|aggregating (approximately)? $X per share`
- **MISTO** se entro ±300 caratteri dall'importo compare `exchange ratio`, `stock
  consideration`, `fraction of a share`, `shares of common stock of`, `in stock`, o `and 0.x
  share`. **AMBIGUO** se lo stesso documento dà importi in contanti diversi: si passa al
  documento successivo.
- **Ingresso** al prezzo d'esecuzione dell'insider, media ponderata delle righe dell'evento, con
  flag `INGRESSO_NON_ALLA_DATA_DI_DEPOSITO`, contati (esplorativo: 32 eventi nella cella P).
  L'incoerenza con gli osservati è nota e limitata.
- **Uscita** al prezzo del deal, con il cambio EUR alla sessione s0 + 126: il contante resta fermo
  fino alla fine della finestra.
- **Guardia sui dati**: un rapporto deal / prezzo insider fuori da [0,05; 20] segnala un errore di
  unità o di documento, non un deal; l'evento va a S_zero con flag `IMPLAUSIBILE`.
- Gambe del peer e di IWM alle sessioni s0 e s0 + 126, come nell'addendum 2; il peer si sceglie
  con la cap insider dell'evento.

---

## 7. Verdetto: cosa cambia nella tabella dell'addendum 1

- Le righe **R1–R6** si calcolano su **osservati + risolti**.
- **R0 è sostituita da R0′.** Si calcola la media degli scenari su osservati + risolti +
  terminati in finestra, con i valori del §6. Se il segno di quella media cambia quando i soli
  terminati in finestra con classe **NON_RISOLTO** passano da S_zero a S0, il verdetto è
  INCONCLUSIVO (sopravvivenza).
- **R0′ non vincola il verdetto.** Nella misura esplorativa la cella P ha **1** evento
  terminato in finestra con classe NON_RISOLTO: nessun risultato plausibile cambia segno per un
  evento. La regola resta scritta, e si riporta.
- Accanto al verdetto, la **tabella degli scenari**: media di osservati + risolti; con i
  terminati in finestra ai valori del §6; con i NON_RISOLTO in finestra a S0.

---

## 8. I vivi non osservati: fuori dal verdetto, con un limite

`USCITO_DOPO`, `VIVO_SENZA_STORIA` e `GUASTO_FONTE` stanno **fuori dal verdetto**, dichiarati come
copertura:

copertura = (osservati + risolti) ÷ (osservati + risolti + terminati in finestra + vivi non
osservati)

Esplorativo: circa **64%** (2.362 su 3.705, esclusi i 4 `USCITO_PRIMA`).

**L'esclusione non è neutra.** Chi esce dal mercato dopo la finestra ha in media fatto peggio,
nei 126 giorni, di chi resta. Senza prezzi non si corregge; si limita, come misura
**descrittiva e non di verdetto**:

- per k ∈ {0, 5, 10, 20} punti: **media_k = m − k · n_u / (n_v + n_u)**, cioè la media della cella
  se gli `USCITO_DOPO` avessero avuto eccesso m − k;
- **k\* = m · (n_v + n_u) / n_u**, il k a cui la media va a zero, riportato accanto al verdetto.
  Se m ≤ 0, k\* non si calcola.

Con m = media del matching di riferimento, n_v = coppie nella media del verdetto, n_u = eventi
`USCITO_DOPO` della cella P (esplorativo 1.264). Il limite considera solo gli usciti dopo:
`VIVO_SENZA_STORIA` e `GUASTO_FONTE` sono sopravvissuti, non usciti. Si riporta anche per l'altro
matching e contro IWM.

---

## 9. Budget

- **EDGAR: tetto di 200 chiamate di rete** per validazione e prezzi dei deal insieme. Contatore
  su disco (`step2_prep/edgar_calls.json`) che somma tutte le esecuzioni; richieste sequenziali a
  0,15 s l'una dall'altra (al massimo ~6,7 al secondo), User-Agent dichiarato. Una chiamata oltre
  il tetto non parte, e il documento mancante porta l'evento a S_zero con flag `NON_SCARICATO`.
  Stima: ~40 emittenti × 2 documenti, più ~32 emittenti × fino a 2 documenti, in parte già letti
  per la validazione.
- **yfinance**: usato una volta il 2026-09-15 per `prices_resolved/`. Nessun'altra chiamata.
- **API di modelli linguistici: 0.**

---

## 10. Limiti dichiarati

1. **5.441 eventi** senza azioni XBRL: nessuna fascia, fuori dalle celle.
2. **Ingresso di S_acq al prezzo insider**, non alla prima sessione dopo il deposito.
3. **Il classificatore legge forme e item, non testi.** Esempio noto di errore d'ancoraggio: DISH
   Network, classificata VOLONTARIO_OTC, era stata fusa in EchoStar; continuando a depositare
   come emittente di debito, il suo ultimo Form 15 cade anni dopo.
4. **Le etichette vere le assegna chi ha scritto il classificatore**, a classe nascosta: non è
   una doppia cieca. Per questo ogni etichetta porta la citazione.
5. **La fascia originale usa l'`Adj Close`** (§3).

---

## 11. Ordine di esecuzione

1. commit di questo file e di `survival.py`;
2. `survival.py popolazione` — cache;
3. `survival.py campione` — EDGAR;
4. etichette vere in `step2_prep/validazione/_verita.json`;
5. `survival.py concordanza`;
6. `survival.py deal` — EDGAR, solo con classificatore valido;
7. passo 2.
