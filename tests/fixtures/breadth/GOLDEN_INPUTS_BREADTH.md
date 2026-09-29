# Breadth — conteggi grezzi, quattro settimane (Fase 1)

Estratti dalle fixture in questa cartella, ritagliate dal dataset bulk SEC
`2022q2_form345.zip`. **Nessuna percentuale, nessun destagionalizzato, nessuno
z-score**: quelli li calcoli tu a mano, e il codice della Fase 2 verrà scritto
contro i tuoi valori. Mai verificare il codice contro se stesso.

Le quattro settimane sono consecutive e attraversano il selloff del maggio 2022.
Sono state scelte perché **il denominatore si muove molto** — da 704 a 1.491 —
che è il caso in cui una misura basata sui soli conteggi assoluti si romperebbe
senza farsi notare.

---

## I conteggi

| settimana (lunedì) | emittenti con acquisto aperto | emittenti totali | transazioni | mediana $ per acquisto |
|---|---:|---:|---:|---:|
| 2022-04-25 | 108 | 704 | 246 | 202.750 |
| 2022-05-02 | 157 | 1.221 | 408 | 152.250 |
| 2022-05-09 | 300 | 1.146 | 804 | 125.370 |
| 2022-05-16 | 287 | 1.491 | 629 | 97.960 |

Per contesto, il resto del trimestre (non incluso nelle fixture, non golden —
serve solo a farti vedere dove cadono le quattro settimane):

| settimana | con acquisto | totali |
|---|---:|---:|
| 2022-04-04 | 58 | 1.403 |
| 2022-04-11 | 63 | 708 |
| 2022-04-18 | 64 | 784 |
| *2022-04-25* | *108* | *704* |
| *2022-05-02* | *157* | *1.221* |
| *2022-05-09* | *300* | *1.146* |
| *2022-05-16* | *287* | *1.491* |
| 2022-05-23 | 199 | 1.266 |
| 2022-05-30 | 128 | 1.336 |
| 2022-06-06 | 132 | 1.181 |
| 2022-06-13 | 230 | 1.339 |
| 2022-06-20 | 77 | 770 |

---

## Come sono stati prodotti — le decisioni che cambiano i numeri

**Numeratore.** Emittenti distinti (`ISSUERCIK`) con almeno una riga in
`NONDERIV_TRANS` che soddisfa: `TRANS_CODE == "P"`,
`TRANS_ACQUIRED_DISP_CD == "A"`, valore `TRANS_SHARES × TRANS_PRICEPERSHARE`
≥ 25.000, e la cui comunicazione non è esclusa come 10b5-1. Solo tabella non
derivata. Corrisponde a `open_market_buys` in `parse.py:221-231`.

**Denominatore.** Emittenti distinti che hanno depositato almeno un Form 4
(`DOCUMENT_TYPE == "4"`) in quella settimana.

**Il 10b5-1 nel 2022 non ha un checkbox.** Il campo `AFF10B5ONE` compare in
`SUBMISSION.tsv` **solo dai trimestri successivi agli emendamenti di dicembre
2022** — verificato: assente in 2022q2, presente in 2025q2. Per entrambi i
blocchi storici richiesti (2006‑2011 e 2018‑2022) esiste solo il fallback, ed è
lo **stesso** che usa il percorso live: il regex `_PLAN_RE` di `parse.py:32`
applicato a `FOOTNOTES.FOOTNOTE_TXT` e a `SUBMISSION.REMARKS`. Sul trimestre
pieno intercetta 3.465 Form 4 su 50.481 dai footnote e 99 dai remarks.

**Settimane diverse per numeratore e denominatore, di proposito.** Il numeratore
è per **data di transazione** (`TRANS_DATE`): misura quando gli insider hanno
comprato. Il denominatore è per **data di deposito** (`FILING_DATE`): misura
quanti emittenti erano attivi nel processo di comunicazione in quella settimana.

> **Conseguenza da tenere presente prima di calcolare.** La settimana più recente
> di una serie live è sempre **incompleta**: il Form 4 ha due giorni lavorativi
> di scadenza e i depositi tardivi esistono, quindi il numeratore di una
> settimana continua a crescere per giorni dopo la sua chiusura. È il motivo per
> cui lo schema prevede `supersedes`. Su queste quattro settimane il problema non
> si pone — sono chiuse da anni.

**Nessuna deduplica per co-firmatari è servita.** A differenza del percorso XML,
dove `parse.py:71-74` emette un `Transaction` per ogni firmatario e il conteggio
ingenuo moltiplica, i bulk SEC tengono le tabelle normalizzate:
`NONDERIV_TRANS` ha una riga per transazione, `REPORTINGOWNER` una per persona.
Il conteggio `transazioni` qui sopra è quindi già **economico**.

> Questa è una divergenza reale fra i due percorsi, e va misurata prima di
> giuntare le serie: il "1.375" del run live è il conteggio (riga × firmatario),
> non quello economico.

---

## Fedeltà delle fixture

Le fixture sono potate ma **riproducono esattamente** i conteggi del trimestre
pieno sulle quattro settimane — verificato riga per riga.

- `SUBMISSION.tsv`, `NONDERIV_TRANS.tsv`, `REPORTINGOWNER.tsv` — solo le
  accession con deposito o transazione nella finestra, e solo le colonne che la
  misura legge. Una fixture con 28 colonne dove il codice ne tocca 5 invita un
  test che dipende in silenzio da una delle altre 23.
- `FOOTNOTES.tsv` — **tutte** le righe che il regex intercetta (1.138), più un
  campione deterministico di quelle che non matchano (963, una ogni 40). Tenere
  tutti i match significa che l'insieme delle comunicazioni 10b5-1 è identico a
  quello del trimestre pieno: i conteggi non possono muoversi. Il campione serve
  a tenere esercitato anche il ramo negativo del regex.

Totale 4,7 MB invece di 14,5 nell'originale.

**Copia pubblica (2026-09-28): fully synthetic identifiers.** Ogni identificativo
è sintetico, in tutte le righe allo stesso modo, assegnato in ordine alfabetico
del valore originale: accession (`0999999999-YY-nnnnnn`, coerenti fra i quattro
file), CIK di emittenti e reporting owner (`09nnnnnnnn`, una sola mappa per i
due ruoli), simboli (`SYNnnnn`), nomi di emittente (`ISSUER nnnn`), nomi dei
reporting owner (`OWNER nnnnn`), `NONDERIV_TRANS_SK` (progressivo). Le
sostituzioni sono biunivoche. Il testo libero è neutro: `FOOTNOTE_TXT` e
`REMARKS` diventano «Rule 10b5-1 plan (text omitted).» dove il regex `_PLAN_RE`
scattava e «Text omitted.» altrove (vuoto resta vuoto), così l'insieme delle
comunicazioni 10b5-1 è lo stesso; `RPTOWNER_TITLE` diventa «Title omitted.»
(conteneva nomi di società). Date, form type, codici, quantità, prezzi, ruoli
e `FOOTNOTE_ID` sono invariati. I conteggi qui sopra sono stati ricontati
sulle fixture sintetiche: identici.

---

## Cosa manca ancora, e non è stato indovinato

`REPORTINGOWNER.tsv` è nelle fixture ma non entra in nessuno di questi conteggi:
serve alla Fase 3, per la tabella `insider_history` e per la variante filtrata
CMP della serie storica.
