# ADR 006 — Download in massa, archivio normalizzato, controlli, aggiornamento: scelte tecniche

**Data:** 2026-09-17 · **Stato:** accettata

## Contesto

Decisioni dell'utente alla fermata 2 (17 settembre): blocchi 1-2-3 per titolo; grezzo per tutto; prezzi grezzi in CSV
compresso, dividendi e split in JSON; Francoforte solo con ISIN tedesco non già su Xetra; split sospetti al ±5% con Iconix
come test di accettazione; volume zero ripetuto (20 sedute) escluso dai backtest; nessuna fermata prima della 3 salvo
spazio o fallimenti oltre il 2% di un blocco.

## Scelte e motivi

1. **Download come processo staccato** (`Start-Process`), con file di stato, registro, PID e file `STOP`: sopravvive
   alla sessione, si ferma in modo pulito, riparte senza riscaricare.
2. **Piano congelato per blocco** al primo avvio: liste, filtro di Francoforte e compiti extra non cambiano durante il
   download; i conteggi di ciò che si salta restano scritti.
3. **Fallimento** = compito finito con 401, 403, 404, errore di rete, 429 o 5xx dopo i tentativi. Una risposta 200
   vuota non è un fallimento (è un titolo senza dati), si conta a parte. Soglia controllata dopo 1.500 compiti e a fine
   blocco.
4. **Spazio**: fermo se il libero è sotto 1,2 × (grezzo mancante + tutto il Parquet stimato) + 5 GB. *Diviso in due dal punto 62.*
5. **Tetto giornaliero**: non si ferma, aspetta la mezzanotte UTC; il contatore del fornitore si rilegge ogni 1.000
   compiti.
6. **Compiti extra**: indici (S&P 500, Dow Jones, Nasdaq Composite e 100, VIX, NYSE Composite, S&P 400 e 600; per paese
   in Europa; Toronto, Australia, Hong Kong, Nikkei e TOPIX), Tesoro USA (4 curve per anno dal 1990), cambi contro euro e
   dollaro per SEK, NOK, DKK, GBP, CHF, CAD, AUD, HKD, JPY, mappatura identificativi USA a pagine da 1.000. I codici che
   il fornitore non elenca si contano (Russell 2000 manca).
7. **Normalizzazione a flusso** (gruppi da 500.000 righe, file da 2 milioni) con scambio atomico della partizione: 120
   milioni di righe USA non stanno in memoria.
8. **Barre copiate tolte**: da un codice si tolgono le barre identiche per data, chiusura e volume a quelle di un gemello
   (`X_old`, `X_oldN`, `X` più una cifra); le rimozioni sono registrate. *Ristretta dai punti 31 e 32.*
9. **Date ripetute**: resta la prima riga del fornitore, il conteggio va nella tabella `doppioni`.
10. **Controlli in SQL** (DuckDB) con le funzioni Python come riferimento: un test confronta i due su serie casuali.
11. **Coerenza degli split**: grezza divisa per il fattore e rettificata continua, entro metà del salto in logaritmo.
12. **Salti oltre il 90%**: rapporto fra chiusure sopra 1,9 o sotto 0,1, senza split registrato quel giorno.
13. **Barre prima della quotazione**: solo con EDGAR (primo 8-A12B, 8-A12G, 424B1 o 424B4), per società con primo deposito
    dal 1997 e quel modulo entro due anni (schema di un'IPO), barre oltre 30 giorni prima. I file iShares vivono nei
    backtest dello scanner e non si leggono da qui (il package resta indipendente).
14. **Campioni presi a caso** con seme fisso 20260917: controlli ripetibili.
15. **Aggiornamento**: in blocco per seduta in JSON (i campi del blocco CSV non sono documentati); barre del blocco
    aggiunte solo dopo l'ultima barra per titolo; titoli con split o dividendo nel periodo riscaricati per intero.
    *Rifatto nei punti 39-45.*
16. **Verifiche fatte a mano** in un file JSONL, non in Parquet: si scrivono con un editor.
17. **`market_data.api` restituisce `pandas.DataFrame`** da viste DuckDB create in memoria sul percorso della
    configurazione (l'archivio si può spostare); `catalog.duckdb` sul disco ha le stesse viste per l'uso in SQL.

## Correzioni dopo la revisione del download (17-09-2026, download fermato con STOP e ripartito)

18. **401 e 403 non sono più esiti definitivi**: sono problemi di chiave o di abbonamento, non del titolo. Si ripetono alla
    ripartenza; 20 di fila fermano il download. Solo la 404 (titolo o borsa inesistente) è definitiva.
19. **402 = tetto del fornitore**: si aspetta l'azzeramento e si riprova, non è un fallimento.
20. **Errori di rete e 5xx**: dopo i tentativi del client, fino a 5 nuove prove a un minuto di distanza prima di contare il
    compito come fallito (un'interruzione breve non deve fermare un download di giorni).
21. **Contatore del fornitore**: letto all'inizio di ogni blocco e ogni 1.000 chiamate partite (non compiti); se conta più
    del registro locale, il registro si allinea con una riga di rettifica; se la data del contatore non è oggi, vale zero;
    3 letture fallite di fila fermano il download.
22. **Un solo processo alla volta** (`manifest/download.lock`, anche per l'aggiornamento): due processi raddoppierebbero le
    chiamate e scriverebbero gli stessi file.
23. **Registri robusti alle interruzioni** (`market_data/registri.py`): le righe troncate si saltano in lettura e in
    scrittura si va a capo prima della riga nuova; l'esito di un compito già nel grezzo si ricalcola dal grezzo.
24. **Mappatura identificativi**: ogni pagina è un compito contato; una pagina fallita si registra e si ripassa.
25. **Francoforte**: un titolo attivo si esclude solo se il suo ISIN è fra gli **attivi** di Xetra (se su Xetra è
    delistato, a Francoforte si continua a scambiare); un titolo delistato si esclude se l'ISIN è in una delle due liste.
26. **Regno Unito**: il fornitore non ha il FTSE 100; indici Cboe UK 100 e UK 250 (versione di prezzo).
27. **Coerenza degli split**: giudicata solo per fattori ≥ 1,5 o ≤ 1/1,5 (con fattori vicini a 1 il controllo non
    distingue un movimento normale); gli altri si contano a parte.

## Correzioni dopo la revisione delle fasi 3-5 (17-09-2026, codice non ancora usato sui dati veri)

Controlli di qualità:

28. **EDGAR non leggibile = «non verificabile»**, mai «nessun deposito»: una pagina di depositi mancante o un 8-K non
    scaricabile non contano come prova contraria.
29. **Split veri su EDGAR**: l'8-K conta solo se il testo porta un rapporto (per esempio «1-for-10») entro il 5% di quello
    del salto, vicino a parole di frazionamento o raggruppamento. **IPO vere**: 424B1 o 424B4 preceduti entro due anni da
    S-1, F-1 o SB-2, senza rapporti periodici prima della registrazione.
30. **Segnalazioni EDGAR conservate** nei giri senza fonti esterne; le barre prima dell'inizio del calendario si contano a
    parte invece di finire fra i buchi; campione Yahoo scelto per borsa fra i titoli con barre recenti.

Normalizzazione e anagrafica:

31. **Gemelli ristretti**: `X_old` e `X_oldN` in ogni borsa; `X` più una cifra solo negli USA e solo se il codice è
    delistato e `X` esiste (altrove, e sugli attivi, la cifra fa parte del ticker: `TRS3`, `9801`).
32. **Barre copiate** tolte solo in sequenze di almeno 20 sedute uguali per data e chiusura, con volume entro lo 0,5% (il
    fornitore arrotonda i volumi della copia); coincidenze isolate restano.
33. **Una versione nuova più corta non sostituisce**: fra le versioni di una serie vale la più recente con almeno metà
    delle righe della più lunga; le sostituzioni mancate si registrano. Eccezione al punto 47 (riuso).
34. **Blocco integrato a flusso con DuckDB**, solo per i codici con una serie per titolo, solo dopo la loro ultima barra
    (o dal giorno prima del download): niente titoli nati solo dal blocco, niente righe in memoria.
35. **Valuta dei dividendi**: se il fornitore non la dà si usa quella della lista, segnata in `currency_from_listing`.
36. **Codici con prezzi non più nelle liste** entrano nell'anagrafica con stato «non nelle liste», i dati dell'ultima
    versione delle liste che li conteneva e `superseded_by` (codici attuali con lo stesso ISIN).

Viste, API, copia di sicurezza:

37. **Prezzi puliti filtrati per simbolo prima dell'esclusione** (una query su un titolo non legge tutta la borsa);
    verifiche scritte a mano lette con tolleranza (righe rotte contate in `verification_problems()`); `flags()` con la
    colonna `verified`; catalogo sul disco scritto a parte e sostituito, mai con viste congelate; `refresh()` vale per
    tutti i thread.
38. **Copia di sicurezza a specchio**, incrementale per dimensione e data (verifica completa a richiesta), errori per file
    registrati senza fermare la copia, temporanei esclusi; non parte se il download, un aggiornamento o una
    ricostruzione sono in corso.

Aggiornamento incrementale (sostituisce il punto 15):

39. **Copertura per borsa** dal giorno prima del primo download per titolo, fissata nel registro
    `manifest/aggiornamenti.jsonl` alla prima esecuzione, e avanzata solo dalle sedute registrate come coperte. Prima si
    partiva dall'ultima barra di un titolo qualsiasi: un titolo più aggiornato faceva saltare sedute a tutti gli altri.
40. **Seduta coperta** = tre blocchi (prezzi, split, dividendi) con risposta 200 e righe dei nostri titoli almeno metà del
    riferimento (mediana delle ultime 5 sedute coperte, o i titoli attivi con serie finché non ce ne sono 3). Una seduta
    fallita o corta si riscarica all'esecuzione successiva; corta in 3 giorni diversi si accetta e il registro lo dice
    (festività sconosciute alla libreria, borse poco scambiate): senza questa uscita la copertura resterebbe ferma.
41. *(Rifatto nei punti 46-47.)* **Liste confrontate**: attivi senza serie scaricati per intero; delistati mai visti prima (come `X_old` dopo un riuso)
    scaricati per intero.
42. *(Rifatto nei punti 46 e 48-49.)* **Eventi**: split → prezzi, dividendi e split di nuovo; dividendo → prezzi e dividendi. Una volta per evento
    (registro) e mai se la serie è stata scaricata dopo la data dell'evento. La seduta si registra dopo gli eventi, così
    un'interruzione li ripete invece di perderli.
43. **Cambi, indici, Tesoro (anno corrente e precedente) e mappatura identificativi** si riscaricano a ogni esecuzione;
    poi normalizzazione, anagrafica, calendario, controlli senza fonti esterne (le sezioni EDGAR e Yahoo di
    `qualita.json` restano, con la loro data) e catalogo.
44. *(Rifatto nel punto 47.)* **Ticker riusato**: stesso codice con ISIN diverso, o nome molto diverso quando manca un ISIN → serie completa di
    nuovo, e il registro annota i file nuovi; la normalizzazione sceglie solo fra le versioni da quei file in poi, anche
    se più corte (la società nuova ha meno storia di quella vecchia, e il punto 33 terrebbe la vecchia).
45. **Calendario dal 1960** (prima dal 1985): i prezzi USA partono dal 1962. La libreria conosce le chiusure storiche di
    New York (1963, 1968, 1977, 1985) ma non tutti i Capodanni (1960 e 1962 risultano sedute): prima del 1985 il
    calendario non è verificato.

## Correzioni dopo la revisione dell'aggiornamento (17-09-2026, 13 difetti confermati, prima di ogni uso sui dati veri)

Causa comune dei difetti gravi: il confronto delle liste partiva dalle liste appena salvate e un lavoro fallito si
dimenticava. Un'interruzione o qualche risposta sbagliata del fornitore diventavano perdite permanenti.

46. *(Chiusure rifatte nei punti 54-55.)* **Coda dei lavori nel registro.** Ogni serie da scaricare (titolo nuovo, delistato nuovo, riuso, split, dividendo) è un
    lavoro scritto nel registro **prima** di scaricare; le liste nuove si salvano solo dopo aver scritto le decisioni. Un
    lavoro si chiude quando ogni sua tabella ha una versione scaricata dopo l'ingresso in coda, o risponde 404; resta
    aperto altrimenti, e l'esecuzione successiva riprova solo le tabelle mancanti. Un «nuovo» con 404 resta aperto (la 404
    non si paga, i dati di una quotazione appena nata arrivano dopo). Dentro la stessa esecuzione una tabella fallita non
    si riprova (le pause di un minuto costerebbero tempo senza cambiare nulla).
47. **Riuso segnato con un istante, non con i file.** Il segno si scrive appena il riuso è deciso; la normalizzazione
    ignora tutte le versioni della serie scaricate prima, per ogni tabella. Finché la serie nuova non arriva il codice
    resta senza dati per quella tabella: niente società vecchia allungata con i prezzi della nuova, e niente dividendi
    della vecchia attaccati alla nuova. Il record di prima con cui si confronta è quello attivo se c'è (un codice nelle
    due liste con ISIN diversi non è un riuso a ogni esecuzione). Un codice riusato da un tipo che l'archivio non tiene
    (un fondo, un ISIN non tedesco a Francoforte) riceve solo il segno: la serie vecchia esce, la società vecchia resta
    col suo codice nuovo da delistato.
48. **Blocchi validi = risposta 200 e lista JSON.** Un oggetto (errore del fornitore) rende la seduta fallita; la
    normalizzazione usa solo i file che cominciano con una lista (prima DuckDB si fermava su ogni ricostruzione). Si
    riscaricano solo i blocchi non validi (e i prezzi di una seduta corta), non tutti e tre.
49. **Righe della seduta contate per data.** Contano solo le righe con la data della seduta: un blocco che restituisce il
    giorno prima non copre la seduta.
50. *(Rifatto nel punto 57.)* **Riprove come nel download**: rete, 429 e 5xx riprovati fino a 5 volte a un minuto di distanza; 10 chiamate di fila
    fallite così fermano l'aggiornamento, e la coda aspetta la volta dopo.
51. **Mappatura identificativi salvata solo se completa**, e registrata con i suoi file; la normalizzazione usa solo
    l'ultima mappatura completa (prima pagine vecchie oltre la fine della nuova restavano, con ISIN vecchi).
52. **Calendario**: una finestra senza sedute (un fine settimana) dà una lista vuota invece di un errore della libreria.
53. **Rapporto di qualità**: un giro su alcune borse conserva le sezioni delle altre, ciascuna con la data del suo
    controllo (`borse_controllate_il`).

Limite noto, non corretto: una seduta con almeno metà delle righe attese ma non tutte è «ok» e non si riscarica. La
soglia del 50% è documentata al punto 40; alzarla renderebbe corte le sedute delle borse poco scambiate.

## Correzioni dopo la seconda revisione dell'aggiornamento (17-09-2026: 11 dei 13 difetti chiusi, 2 in parte, 8 nuovi)

54. **Una 404 non chiude subito un lavoro**, di nessun tipo. Si chiude `non disponibile` quando le tabelle mancanti hanno
    risposto 404 in almeno 5 giorni diversi da quando il lavoro è in coda; `uscito dalle liste` quando un «nuovo» non è
    più fra gli attivi o un «delistato nuovo» o «riuso» non è più in nessuna lista (solo con liste appena arrivate). Prima
    un riuso con una 404 di un giorno lasciava il codice senza dati per sempre. Un «nuovo» o «delistato nuovo» chiuso
    senza `ok` torna in coda dopo 30 giorni, se serve ancora. Le 404 non si salvano nel grezzo, si contano nel registro.
55. **Serie valida** = scaricata dopo l'ultimo segno di riuso del codice. Solo le serie valide contano come «già
    scaricate» e ricevono eventi: un codice riusato da un tipo non tenuto non torna indietro con un dividendo, e un riuso
    chiuso `non disponibile` torna «nuovo».
56. **Dividendi e split dai blocchi solo dal giorno prima del download della serie per titolo** (come per i prezzi, dopo
    l'ultima barra), e per un codice riusato solo dal giorno del download (la serie nuova contiene già i suoi eventi):
    quelli della società vecchia, già nei blocchi prima del riuso, non passano alla nuova.
57. **Lavori in coda senza pause**: una sola chiamata, niente 5 prove a un minuto (restano in coda); dopo un errore su un
    titolo, le sue altre tabelle aspettano la volta dopo. Dopo 10 chiamate di fila fallite (rete, 429, 5xx) si chiede al
    fornitore se risponde (`user`, non si paga): se no l'aggiornamento si ferma, se sì continua. Prima pochi titoli
    sempre in errore, in testa alla coda, fermavano ogni esecuzione prima delle sedute. Dopo una seduta fallita le sedute
    seguenti della borsa si lasciano alla volta dopo (durante un guasto del blocco costerebbero 18 minuti l'una).
58. **Liste**: una lista con meno di metà delle righe di prima (anche vuota) non si usa e non si salva, come una lista
    fallita: non diventa il termine di confronto.
59. **Xetra prima di Francoforte** nella stessa esecuzione, e Francoforte si filtra con le liste di Xetra appena arrivate.
60. **Mappatura identificativi**: una riga del registro prima di salvare le pagine; se il primo salvataggio si interrompe,
    la normalizzazione usa le pagine scaricate prima di quella riga.
61. **Registro indicizzato in memoria** (lavori, chiusure, sedute, segni, 404) e segni di riuso letti una volta per
    normalizzazione: prima ogni decisione rileggeva tutto il registro (circa 250.000 righe in un anno, fino a 45 minuti in
    più per ricostruzione). Liste con lo stesso contenuto lette una volta.

## Spazio su disco, decisione dell'utente del 18-09-2026

62. **Controllo dello spazio diviso in due.** Il download si è fermato due volte per spazio (09:47 e 11:38 UTC) senza
    che l'archivio c'entrasse: il file di paging di Windows è cresciuto fino a 27,7 GB mentre girava Docker Desktop. La
    soglia chiedeva anche lo spazio di tutto il Parquet, che però si costruisce solo a download finito. L'utente ha
    scelto: durante il download conta solo il grezzo mancante (1,2 × grezzo mancante + 5 GB; 9,8 GB al momento della
    scelta, a 93.400 compiti del blocco 1); prima della ricostruzione `store.ricostruisci` controlla lo spazio del Parquet
    (1,2 × Parquet stimato − Parquet già presente + 5 GB; 11,7 GB con l'archivio senza Parquet) e, se manca, si ferma
    senza scrivere nulla: allora si chiede all'utente.
63. **Cache di EDGAR compressa, elenchi dei depositi validi 7 giorni.** Il controllo delle barre prima della quotazione
    legge gli elenchi dei depositi di circa 10.000 società USA: in chiaro sarebbero 4-6 GB su un disco già stretto, e
    con la cache valida un giorno una ripetizione il giorno dopo li riscaricherebbe tutti. Gzip riduce lo spazio a circa
    un decimo; 7 giorni bastano perché i controlli guardano date passate (quotazione, split, cancellazione).
64. **Confronto con Yahoo sulle chiusure rettificate solo per gli split.** Il primo giro sui dati veri dava il 22,7% di
    chiusure USA diverse di oltre l'1% (39% in Europa), ma confrontava le rettificate anche per i dividendi: sui sei
    titoli peggiori le chiusure divise per gli split EODHD successivi coincidono con la Close di Yahoo (0-0,6% di date
    diverse dal 2010), mentre le rettificate differiscono sul 90-100% delle date. Si misurava il diverso metodo di
    rettifica dei dividendi, non la qualità dei prezzi. Ora il confronto principale è sulle chiusure rettificate per gli
    split; le rettificate per i dividendi si riportano a parte (quota oltre l'1% e scarto mediano per titolo), perché
    contano per chi calcola rendimenti totali da `adjusted_close`.

## Prezzi puliti, decisioni dell'utente del 21-09-2026 (fermata 3)

65. **Il salto sospetto passa per tre casi, e il secondo non è una soglia ma una verifica.** L'ipotesi iniziale era:
    rettificata continua → nota; grezza e rettificata che saltano entrambe con volume oltre 3 volte la mediana delle 20
    sedute prima → crollo vero; il resto → esclusione. Misurata sui due casi di accettazione dell'utente, non li separa:
    Apple il 29-09-2000 ha un eccesso di volume di 22,4×, Iconix il 17-12-2015 di 8,8×, e a 3× sono tutti e due «crollo
    vero», mentre Iconix deve restare esclusa. Perché i due test passino la soglia dovrebbe stare fra 8,8 e 22,4: tarata
    su due punti, cioè quello che «nessuna soglia senza misura» vieta. Cercato un segnale interno che li distingua, non
    c'è: in tutti e due i casi `adjusted_close` è la grezza per una costante e salta identica, il gap è overnight, la
    barra del giorno è coerente. Quello che li ha separati è il bilancio della società. Decisione dell'utente: il
    secondo caso diventa il confronto con il massimo dichiarato nell'**Item 5 del 10-K**, e il volume esce dalla regola.
    Ordine: prima la rettificata continua, poi la verifica sui bilanci, poi l'esclusione.
66. **Chiusure a zero: barre mancanti, mai rendimenti.** 548.359 barre in 4.164 titoli USA (più 3.139 su Xetra e 3.044
    in Australia) hanno chiusura zero: sedute senza scambi che il fornitore scrive come prezzo. Nessuna regola le
    toglieva. In un backtest valgono −100% il giorno che arrivano. Decisione: spariscono dai prezzi puliti invece di
    diventare uno zero, insieme alle `adjusted_close` ≤ 0. Nuova vista `liquidita` con la quota per titolo e il segno
    `liquidita_insufficiente` **oltre il 20%**: segnala, non toglie.
67. **Ambito della verifica sui bilanci, dichiarato invece che nascosto.** NASDAQ, NYSE e NYSE ARCA, fascia sopra 1
    dollaro, salto prima del 2019, CIK noto: 1.911 salti su 1.273 titoli. Fuori da lì la verifica non si fa **per
    scelta** — l'OTC e le borse estere spesso non depositano alla SEC, e dal 2019 l'Item 5 non riporta più massimo e
    minimo trimestrali (la SEC ha tolto l'obbligo della voce 201(c) del Regulation S-K con le modifiche FAST Act del
    2018) — e il salto resta escluso come prima. Bilancio assente o Item 5 illeggibile: escluso, contato per motivo.
    Il dizionario dei dati scrive dove la verifica non è stata fatta e perché.
68. ~~**Il verdetto usa il solo massimo dichiarato, e solo per i salti in discesa.**~~ **Superato dal punto 71 lo
    stesso giorno**, prima di qualunque uso dei dati. Restava scritto così: Il minimo letto nei bilanci non è
    affidabile: la riga dei prezzi sta accanto a dividendi e utili per azione, e sul 10-K Apple del 1996 il minimo
    letto è 0,12, che è il dividendo. Col solo massimo si riconosce una serie scalata verso l'alto — la chiusura di
    prima supera un massimo che la società dichiara, quindi è impossibile — ma non una scalata verso il basso. Per
    questo un salto verso l'alto non può essere dichiarato vero e resta escluso: Southern Union il 22-12-1994 passa da
    1,83 a 14,50 sotto un massimo dichiarato di 21,88, indistinguibile da una serie divisa per otto.
69. **`api.prices(clean=True)` non usava la vista `prezzi_puliti`.** Per filtrare prima sui simboli si riscrive la
    query, e le due definizioni erano già divergenti prima di questa modifica. La condizione sui prezzi validi sta ora
    in una costante sola (`catalog.PREZZO_VALIDO`) e un test confronta le due strade titolo per titolo.
70. **`esclude` mancante vale «esclude».** Le partizioni scritte prima di oggi non hanno la colonna. La vista
    `segnalazioni` la aggiunge come TRUE dove manca ed è nulla: il comportamento di prima, quando ogni periodo
    segnalato usciva dai prezzi puliti. Un dato mancante non diventa un permesso.

71. **Il verdetto usa tutti e due gli estremi dichiarati** (sostituisce il punto 68). Il punto 68 diceva di ignorare
    il minimo perché contaminato da dividendi e utili per azione. È il ragionamento sbagliato: ignorarlo equivale a
    un minimo di zero, cioè al test più permissivo possibile. Un minimo letto troppo basso allarga la fascia e rende
    il test più permissivo, mai più severo — un difetto tollerabile; l'assenza no. Trovato leggendo il campione che
    l'utente aveva chiesto di riportare: Affiliated Computer Services il 02-01-2009 va da 13,15 a 1,27 mentre il suo
    10-K dichiara 34,84-58,70, e veniva promosso a «movimento vero». Con tutti e due gli estremi il verso del salto
    non conta più, e cade la restrizione ai soli salti in discesa.
72. **I prezzi dichiarati si legano all'anno che li etichetta.** Una tabella dell'Item 5 riporta quasi sempre due
    esercizi, e presi insieme danno una fascia larga il doppio, dentro la quale ci sta anche una rottura di scala:
    Continental Resources il 20-12-2010 passa da 28,58 a 57,64 — la serie prima sta a metà della scala vera — e
    l'intervallo 13,84-59,98 dei due esercizi 2009 e 2010 se lo beve. Ogni prezzo letto porta ora l'ultimo anno
    scritto prima di lui, o quello che precede l'etichetta nella forma «Fiscal 2000 price range per common share», e
    il confronto usa solo l'anno del salto. I prezzi si continuano a leggere **solo dopo** l'etichetta, dove non ci
    sono ricavi né dividendi. Effetto: i promossi scendono da 402 a 281 sui 1.855 salti dell'ambito.
73. **Tetto di memoria al 65% della RAM e controlli a blocchi di codici.** Una scansione dell'archivio saturava la
    macchina dell'utente (0,12 GB liberi su 15,9): nessuna connessione DuckDB aveva un tetto, e senza tetto DuckDB
    prende l'80% della memoria. `config.applica_limiti` mette ora tetto, thread e cartella temporanea a tutte e sei
    le connessioni del package; la quota è scelta dell'utente perché il computer serve anche ad altro, e la
    temporanea non può superare metà dello spazio libero su un disco che ne ha poco. I due controlli a finestra
    mobile girano a blocchi da 15 milioni di barre **divisi per codice**: ogni serie sta tutta dentro un blocco,
    quindi il risultato è identico al giro unico — dividere per data spezzerebbe le finestre. Costa quasi niente,
    perché rileggere le 113 milioni di barre americane richiede 0,3 secondi. Il giro USA completo: 6 minuti e 37
    secondi, con la macchina libera.
