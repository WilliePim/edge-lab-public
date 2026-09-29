# Backfill — domande aperte

Questioni che richiedono una decisione tua. Per ciascuna ho preso la strada più
conservativa e sono andato avanti, come da istruzione. Nessuna è stata indovinata
in silenzio.

---

## Q1 — La Fase 1 come specificata richiede 128 ore di download

**DECISA DA ME, provvisoriamente. È la più importante.**

La specifica dice: *"Scarica i full-index trimestrali EDGAR dal 2015Q1 a oggi ed
estrai tutti i Form 4. Parsali con il parser esistente (parse.py)."*

Ho misurato il volume reale invece di stimarlo:

| | |
|---|---|
| Righe Form 4 in 2015Q1 | 135.156 |
| **Accession distinte** (dopo dedup per co-firmatari) | **65.957** |
| Media su 2015Q1, 2018Q1, 2021Q1, 2024Q1, 2026Q1 | ~129.000 righe / ~66.000 filing |
| Trimestri 2015Q1 → 2026Q3 | 47 |
| **Filing totali da scaricare** | **~3.100.000** |

A 6,7 req/s (il throttle di `EdgarClient`, 0,15s) sono **128 ore**. Al limite SEC
di 10 req/s sono **86 ore**. Il vincolo 5 vieta di aggirare il rate limit, e
giustamente.

Va peggio di così: `EdgarClient.ownership_xml()` fa **due** richieste per filing —
prima `index.json`, poi l'XML. Sono 6,2 milioni di richieste, non 3,1. Usando il
path `.txt` del full-index (che contiene l'XML inline) si torna a una richiesta
per filing, ma 128 ore restano 128 ore.

### La strada che ho preso

**SEC bulk insider-transaction datasets**, `{anno}q{n}_form345.zip`. Verificati
disponibili: **2015q1 → 2026q1, 45 trimestri**, 8-15 MB ciascuno, ~500 MB in
totale. **45 download invece di 3,1 milioni.**

Contengono esattamente i campi che la Fase 1 chiede, nelle tabelle `SUBMISSION`,
`REPORTINGOWNER`, `NONDERIV_TRANS`, `FOOTNOTES`.

Non è una scelta arbitraria: il repo **ha già** fixture da questi dataset
(`tests/fixtures/breadth/`) e ha già documentato le due divergenze rispetto al
percorso XML, in `GOLDEN_INPUTS_BREADTH.md`:

1. le tabelle bulk sono **normalizzate** — una riga per transazione — mentre il
   percorso XML emette una riga per (transazione × firmatario). Il conteggio
   ingenuo sul percorso XML moltiplica per il numero di co-firmatari.
2. `AFF10B5ONE` esiste in `SUBMISSION` **solo dai trimestri successivi agli
   emendamenti di dicembre 2022**. Che è esattamente ciò che la tua specifica
   prevede scrivendo *"is_10b5_1 (null se pre-2023)"* — la stessa proprietà vale
   sul percorso XML, dove `<aff10b5One>` non esiste prima.

**Mitigazione obbligatoria che eseguo comunque:** valido l'estrazione bulk contro
il percorso XML con `parse.py` + `open_market_buys()` su un campione, e riporto
la divergenza misurata. `parse.py` resta la semantica di riferimento; il bulk è
la fonte del corpus. Se la divergenza è grande lo scoprirai dal numero, non da
una mia rassicurazione.

### Cosa perdo

**2026Q2 e 2026Q3 non sono ancora pubblicati** — il bulk ha ritardo trimestrale.
Il corpus arriva a 2026Q1. Quei cinque mesi non contribuirebbero comunque alla
Fase 4: non hanno ancora un rendimento forward a 12 mesi.

### Se preferisci il percorso XML

È implementato e riprendibile per trimestre: si lancia e va avanti per giorni
ripartendo dal checkpoint. Dimmelo e lo faccio girare — ma occupa la macchina per
cinque giorni e produce, per quanto ho potuto misurare, gli stessi numeri.

---

## Q2 — "score_max_possible" somma i massimi dei due componenti mancanti

**DECISA: seguo la specifica alla lettera, ma il numero va letto con cautela.**

La specifica chiede `score_max_possible = score_partial + punti massimi dei 2
mancanti`. `coverage` vale al massimo 1, `specialist_overlap` vale 2, quindi il
limite superiore è sempre `score_partial + 3`.

Essendo una costante additiva, `score_max_possible` **ordina i nomi esattamente
come `score_partial`**: non aggiunge informazione discriminante, e per i bucket
della Fase 4 produrrebbe la stessa classifica traslata di 3. Lo calcolo e lo
scrivo perché me lo hai chiesto, e uso `score_partial` per i bucket.

Se volevi invece un'imputazione (per esempio la distribuzione storica di quei due
componenti sui nomi dove sono noti), è un'altra cosa e non l'ho fatta: sarebbe
inventare dati, che il vincolo 2 vieta.

---

## Q3 — Il benchmark IWM non copre l'intero universo

**DECISA: uso IWM come da specifica, e registro il problema.**

IWM è Russell 2000. Il tetto di capitalizzazione del scanner è 2e9 e il pavimento
5e7, quindi la sovrapposizione è buona ma non totale: i nomi sotto ~3e8 sono
micro-cap che il Russell 2000 rappresenta male, e alcuni non ne fanno parte.

Il rendimento in eccesso su IWM resta la misura richiesta. Registro per ogni
osservazione anche la capitalizzazione al momento, così puoi ripesare a posteriori
se vuoi.

---

## Q4 — Prezzi storici: quale fonte, e cosa fare dei delistati

**DECISA: yfinance, con registrazione esplicita di ogni assenza.**

La specifica nomina yfinance implicitamente ("i nomi delistati spariscono da
yfinance"). Non ho un'altra fonte di prezzi storici disponibile senza credenziali.

Il survivorship bias che segnali è reale e non ho modo di eliminarlo — solo di
misurarlo. Ogni ticker senza prezzi finisce in `state/backfill/missing_prices.jsonl`
con il motivo, e la Fase 4 riporta la loro distribuzione per bucket di score. Se
si concentrano su uno degli estremi, il dataset è distorto e il report lo dirà.

**Questo è un limite che nessuna quantità di lavoro rimuove.** Va letto come tale.

---

## Q5 — I prezzi sono presi per ticker, non per CIK

**DECISA: procedo, e lo dichiaro fra i limiti. Non ho modo di risolverlo da solo.**

Scoperto durante la Fase 3, non previsto nel piano. Le serie prezzi sono
scaricate per **simbolo**, ma su undici anni i simboli vengono riassegnati: se
una societa' viene delistata e il suo ticker passa a un'altra, un'osservazione
del 2016 riceve i prezzi della societa' sbagliata — e sembrano prezzi validi.

Non l'ho quantificato perche' servirebbe una mappa storica ticker→CIK che non
ho. Dopo il survivorship e' il difetto residuo piu' serio, e a differenza del
survivorship **agisce in direzione ignota**: non so se gonfi o sgonfi i
rendimenti, ne' se colpisca uniformemente i bucket.

Se vuoi chiuderlo servirebbe una fonte con identificativi permanenti (CRSP
PERMNO, o la mappa ticker-CIK storica di EDGAR ricostruita dai filing). E' un
lavoro a se'.

---

## Q6 — Le medie sono contaminate da errori di prezzo

**DECISA: riporto mediana e media trimmata, con la media grezza accanto.**

Le serie yfinance contengono discontinuita' non corrette su titoli OTC e
delistati. Un titolo OTC segna +3.949.900% su sei mesi: un reverse split non aggiustato.
Ottanta osservazioni superano il +1000%, e bastano a spostare una media di
decine di punti — il bucket 2-3 mostrava +53,55% di media contro −1,78% di
mediana.

Ho aggiunto una media trimmata a +/-500% e la colonna dei valori scartati, e ho
lasciato la media grezza accanto perche' la differenza fra le due e' essa stessa
un'informazione sulla qualita' dei dati. Le mediane non sono state toccate.

Il taglio a 500% e' una scelta mia. Se preferisci un'altra soglia, e' un
parametro in `backfill_analyse.py` (`ARTEFACT`).
