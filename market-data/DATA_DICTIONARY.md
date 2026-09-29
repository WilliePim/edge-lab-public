# Dizionario dei dati

Ogni tabella dell'archivio, colonna per colonna, in italiano semplice. Le tabelle stanno in
`<MARKET_DATA_DIR>/eodhd/parquet/<tabella>/exchange=<BORSA>/` e si leggono **solo** con `market_data.api` (o con le viste
di `catalog.duckdb`). Ogni tabella ha anche la colonna **`exchange`**: il codice di borsa EODHD (`US`, `LSE`, `XETRA`, …;
`INDX` per gli indici, `FOREX` per i cambi).

## Come si riconosce un titolo

- **Simbolo** = `codice.borsa` (`AAPL.US`, `P_old.US`, `SAP.XETRA`). Un codice è **un periodo di vita** di un titolo.
- Quando un ticker viene riusato, EODHD dà alla società vecchia un codice nuovo (`P_old`, `FRSH_old1`, `FRSH1`) e lascia
  il ticker alla società di oggi. Stesso **ticker di base**, codici e ISIN diversi: sono due società.
- Mai riconoscere un titolo dal ticker o dal nome (il nome può essere il ticker stesso). Usare codice + borsa, con l'ISIN
  come conferma, e le date della prima e dell'ultima barra.

## Tabelle

### `prezzi`

Una riga per titolo e seduta.

| colonna | significato |
|---|---|
| `code` | codice EODHD del titolo (o dell'indice, in `INDX`) |
| `date` | giorno della seduta |
| `open`, `high`, `low`, `close` | apertura, massimo, minimo, chiusura: prezzi **grezzi**, come scambiati quel giorno |
| `adjusted_close` | chiusura **rettificata** per split e dividendi, con i rapporti noti il giorno del download. Vedi l'avvertenza sotto |
| `volume` | azioni scambiate (rettificate per split dal fornitore); vuoto se il fornitore non lo dà |
| `currency` | valuta della lista dei titoli della borsa (vuota se il codice non è nelle liste, per esempio gli indici) |

Sono già tolte le barre copiate dal gemello (vedi `barre_tolte`). Per i backtest: `prices()` restituisce i **prezzi puliti**,
senza i periodi segnalati (regole sotto).

**La chiusura rettificata non è confrontabile con quella di altri fornitori.** EODHD e Yahoo rettificano i dividendi in
modo diverso e lo scarto si accumula andando indietro nel tempo: nel campione della fase 4, il 22,7% delle chiusure
rettificate USA e il 39,3% di quelle europee differisce da Yahoo di oltre l'1%, mentre le stesse chiusure rettificate
solo per gli split coincidono (3,5% e 14,1% di date diverse, quasi tutte prima del 2015 in Europa). Per i **rendimenti
totali** conviene partire da `close` e dalla tabella `dividendi`, non da `adjusted_close`. In alcuni titoli
`adjusted_close` è perfino negativa (2.291 barre in 17 titoli USA): quelle barre non escono più dai prezzi puliti,
vedi «Chiusure a zero».

**Da dove vengono le righe.** Dalla serie per titolo scaricata per intero; dopo la sua ultima barra, dai dati in blocco per
seduta dell'aggiornamento. Un titolo che compare solo nei dati in blocco non entra. Se una serie è stata scaricata più
volte vale la versione più recente, purché abbia almeno metà delle righe della più lunga (una risposta troncata non
cancella la storia); dopo un ticker riusato vale comunque la versione nuova, anche se più corta.

### `dividendi`

| colonna | significato |
|---|---|
| `code`, `date` | titolo e data di stacco (primo giorno senza diritto al dividendo) |
| `declaration_date`, `record_date`, `payment_date` | annuncio, data di registrazione, pagamento (vuote se mancano) |
| `period` | frequenza dichiarata («Quarterly», …) |
| `value` | importo per azione **rettificato per gli split successivi** |
| `unadjusted_value` | importo per azione come pagato allora |
| `currency` | valuta del dividendo |
| `currency_from_listing` | vero se il fornitore non dava la valuta e si è usata quella della lista dei titoli: da controllare per i titoli che pagano in una valuta diversa da quella di quotazione |

### `split`

| colonna | significato |
|---|---|
| `code`, `date` | titolo e primo giorno con il nuovo numero di azioni |
| `ratio` | testo del fornitore, azioni nuove / vecchie («2.000000/1.000000») |
| `new_shares`, `old_shares` | le due parti del rapporto |
| `factor` | nuove / vecchie: 2 per un frazionamento 2:1, 0,1 per un raggruppamento 1:10 |

### `cambi`

Come `prezzi`, con `pair` al posto di `code` (`EURUSD` = dollari per un euro). Borsa `FOREX`. Volume di solito zero.

### `tesoro`

Tassi del Tesoro USA (borsa `US`), una riga per curva, giorno e scadenza.

| colonna | significato |
|---|---|
| `curve` | `yield-rates` (curva dei rendimenti), `bill-rates` (buoni), `long-term-rates`, `real-yield-rates` |
| `date`, `tenor` | giorno e scadenza («10Y», «13WK», …) |
| `rate` | rendimento in percentuale |
| `discount`, `coupon`, `avg_discount`, `avg_coupon`, `maturity_date`, `cusip` | solo per i buoni |
| `rate_type`, `extrapolation_factor` | solo per i tassi a lungo termine |

### `identificativi`

Mappatura del fornitore (solo borsa USA): `symbol`, `code`, `isin`, `figi`, `lei`, `cusip`, `cik` (codice SEC, con zeri
iniziali). Copre anche codici delistati (`FRSH_old.US` → CIK 1592379).

### `anagrafica`

Un record per codice, cioè per titolo e periodo di vita. Solo azioni ordinarie ed ETF delle liste più recenti, più i
codici che hanno prezzi nell'archivio ma non compaiono più nelle liste.

| colonna | significato |
|---|---|
| `code`, `symbol` | codice e simbolo `codice.borsa` |
| `ticker` | ticker di base: `P` per `P` e per `P_old` |
| `name`, `venue`, `country` | nome, mercato (NYSE, NASDAQ, PINK…), paese, dalle liste del fornitore |
| `isin`, `type`, `currency` | ISIN (vuoto per circa il 70% dei delistati USA), tipo, valuta |
| `status` | `attivo` o `delistato` nelle liste più recenti; `non nelle liste` per un codice con prezzi che il fornitore non elenca più (codice cambiato, tipo cambiato): nome, ISIN e tipo vengono dall'ultima versione delle liste che lo conteneva |
| `listed_in` | in quali liste compare (attivi, delistati) |
| `downloaded` | vero se l'archivio ha prezzi per il codice |
| `excluded_reason` | per Francoforte: perché non scaricato (senza ISIN, ISIN non tedesco, già su Xetra) |
| `first_date`, `last_date`, `bars` | prima e ultima barra e numero di barre nei `prezzi` |
| `removed_bars` | barre tolte perché copiate da un gemello |
| `cik`, `cusip`, `figi` | dalla tabella `identificativi` |
| `twins` | altri codici con lo stesso ticker di base nella stessa borsa. Ticker di base: `X_old` e `X_oldN` → `X` in ogni borsa; `X` più una cifra → `X` solo negli USA, solo per un codice delistato e solo se `X` esiste (altrove la cifra fa parte del ticker) |
| `same_isin` | altri codici con lo stesso ISIN nella stessa borsa (per esempio `SMRT_old` e `SMRTQ`) |
| `superseded_by` | solo per `non nelle liste`: codici delle liste attuali con lo stesso ISIN, cioè il probabile codice nuovo dello stesso titolo |

### `calendario`

`date`: una riga per seduta della borsa, dalla libreria `exchange_calendars`, dal 1960 (o dal primo anno che la libreria
accetta) a un anno avanti. TSX Venture usa il calendario di Toronto. Prima del 1985 non è verificato (vedi le regole).

### `barre_tolte`

`code`, `twin`, `removed`, `first_date`, `last_date`: barre tolte dai `prezzi` di un codice perché uguali a quelle di un
gemello con lo stesso ticker di base: la storia della società che usava prima il ticker. Uguali vuol dire stessa data,
stessa chiusura e volume entro lo 0,5% (il fornitore arrotonda i volumi della copia), in sequenze di almeno 20 sedute di
fila: coincidenze più brevi restano.

### `doppioni`

`code`, `duplicates`, `first_date`: date ripetute nella serie grezza del fornitore; nei `prezzi` resta la prima riga.

### `segnalazioni`

Periodi da escludere nei backtest, scritti dai controlli della fase 4.

| colonna | significato |
|---|---|
| `code` | titolo |
| `controllo` | che cosa ha trovato il controllo (elenco sotto) |
| `from_date`, `to_date` | periodo (estremi compresi) |
| `esclude` | il periodo esce dai prezzi puliti (vero) oppure è solo annotato (falso) |
| `detail` | perché: rapporto del salto e fascia di prezzo, sedute a volume zero, date EDGAR, numeri del bilancio |

I controlli che **escludono**: `salto_sospetto`, `volume_zero`, `prima_della_quotazione`.

I controlli che **annotano e basta**, perché il salto è spiegato e i dati vanno bene:
- `split_del_fornitore` — la chiusura rettificata attraversa il salto senza saltare: il fornitore conosce lo split,
  la serie grezza salta solo perché non è rettificata;
- `salto_confermato` — il 10-K della società dichiara un massimo di periodo compatibile con le due chiusure del salto:
  è un movimento di mercato vero.

Le due note coprono il solo giorno del salto, non il periodo prima.

`flags()` aggiunge `verified`: vero se una riga di `verifiche` copre il periodo (e allora il periodo torna nei prezzi
puliti).

### `liquidita`

Vista: una riga per titolo con la quota di barre senza prezzo. Descritta sotto, con la regola che la motiva.

### `verifiche` (file scritto a mano)

`<MARKET_DATA_DIR>/eodhd/verifiche.jsonl`, una riga JSON per periodo segnalato ma verificato con un'altra fonte:
`code`, `exchange`, `controllo`, `from_date`, `to_date`, `source` (la fonte, per esempio «IWM 2015-09-30»), `note`. Un
periodo coperto da una verifica torna nei prezzi puliti.

## Regole d'uso nei backtest (valgono per ogni tabella dei prezzi)

### Titoli con un salto sospetto (split mancante)

Un titolo è **segnalato** quando il controllo degli split mancanti (`market_data/quality/checks.py`) trova un salto
giornaliero che somiglia a uno split non registrato: rapporto fra le due chiusure entro ±5% da 2, 3, 4, 5, 8, 10, 15,
20, 25, 50, 100 o dagli inversi; nessun ritorno al livello di prima nelle 20 sedute dopo; nessuno split registrato in
quella data. Per ogni salto si riporta anche se il volume si muove in senso opposto al prezzo, come in uno split vero, e
la fascia di prezzo (sotto 0,05; fra 0,05 e 1; sopra 1: il più basso fra le due chiusure).

**Regola, in tre casi, nell'ordine** (decisione dell'utente alla fermata 3):

1. **La chiusura rettificata attraversa il salto** senza saltare (`rettificata_continua`): il fornitore conosce lo
   split e l'ha applicato. Il salto diventa una nota `split_del_fornitore` e **non si esclude niente**.
2. **Saltano tutte e due**, e il salto è nell'ambito verificabile: si confronta con il **massimo che la società
   dichiara nell'Item 5 del suo 10-K** (`market_data/quality/bilanci.py`). Se tutte e due le chiusure stanno sotto
   quel massimo e il salto è in discesa, è un movimento vero: nota `salto_confermato`, **niente esclusione**. Se la
   chiusura di prima supera il massimo dichiarato e quella dopo no, la serie precedente è **fuori scala**: si esclude.
3. **Tutto il resto si esclude**, come prima: dalla prima barra al giorno prima del salto.

**L'ambito della verifica sui bilanci**, e perché è quello: NASDAQ, NYSE e NYSE ARCA, fascia sopra 1 dollaro, salto
prima del 2019, CIK noto. Sono 1.911 salti su 1.273 titoli. Fuori da lì la verifica **non è stata fatta, per scelta**,
e il salto resta escluso:

| fuori ambito | perché |
|---|---|
| OTC (PINK, OTCQB, OTCGREY, …), TSX Venture, borse estere | quei titoli spesso non depositano alla SEC, e dove depositano il prezzo dichiarato è di un altro mercato |
| salti dal 2019 in poi | la SEC ha tolto l'obbligo di riportare massimo e minimo trimestrali (voce 201(c) del Regulation S-K, modifiche FAST Act del 2018): dopo, nel 10-K non ci sono più |
| fascia sotto 1 dollaro | il confronto con un massimo dichiarato al centesimo non distingue niente |
| CIK ignoto | non c'è un depositante da cercare |

**Quando la verifica non conclude, il salto resta escluso** e il motivo è scritto in `detail`: nessun 10-K che copra
l'esercizio del salto, il 10-K non dichiara i prezzi di quell'anno, Item 5 senza tabella dei prezzi, oppure nessuna
delle due chiusure sta nell'intervallo dichiarato.

**Due strade non percorse, e perché.**

*Dal 2019 in poi la tabella dei prezzi non esiste più.* Verificato aprendo tre bilanci di tre società diverse: Apple
(esercizio 2021), U.S. Bancorp (2020) e UPS (2022). In tutti e tre l'Item 5 contiene il mercato di quotazione, il
numero di azionisti iscritti, la politica dei dividendi e la tabella dei riacquisti — e nessun massimo o minimo di
periodo. L'unico prezzo rimasto è il «prezzo medio pagato per azione» dei riacquisti, mensile, solo per il quarto
trimestre e solo per le società che riacquistano: non è un ancoraggio utilizzabile. La strada è **chiusa**: per i
salti dal 2019 in poi non c'è un bilancio con cui confrontarli. Per i titoli del backtest Russell l'ancoraggio resta
il prezzo implicito nelle posizioni di IWM e IWC depositate alla SEC (valore / azioni a fine trimestre).

*Emittenti esteri: 278 salti non verificati, per scelta.* Le società che depositano 20-F o 40-F invece del 10-K non
sono state controllate, perché sono fuori da tutti i backtest in coda. I loro salti restano esclusi come gli altri
non verificabili.

Resta possibile, come prima, verificare un periodo con **un'altra fonte** e rimetterlo nei prezzi puliti scrivendo una
riga in `verifiche.jsonl` (per esempio il prezzo implicito nelle partecipazioni di IWM o IWB depositate alla SEC:
valore / azioni a fine trimestre). La verifica va scritta nel backtest: fonte, date confrontate, scarto.

### Chiusure a zero: barre mancanti, mai rendimenti

Il fornitore scrive `0` la chiusura di una seduta senza scambi. Sono **548.359 barre in 4.164 titoli USA**, quasi
tutte su PINK, OTCCE e OTCGREY, più 3.139 su Xetra e 3.044 in Australia. Uno zero non è un prezzo: in un backtest
varrebbe un rendimento del −100% il giorno che arriva e del +∞ il giorno che finisce.

**Regola** (decisione dell'utente alla fermata 3): nei prezzi puliti quelle barre **non esistono**. `prices()` le
salta, come salta i periodi esclusi; non diventano zeri e non diventano valori riempiti. Con `clean=False` ci sono
tutte, zeri compresi. Vale anche per `adjusted_close` ≤ 0 (2.291 barre in 17 titoli USA, che erano negative).

Un titolo a cui mancano molte sedute non è un titolo che si può mettere in un backtest, anche se le barre rimaste
sono buone: la tabella `liquidita` lo dice titolo per titolo.

### `liquidita`

Una riga per titolo (vista, si ricalcola sola).

| colonna | significato |
|---|---|
| `barre` | sedute nella serie grezza |
| `barre_senza_prezzo` | quante hanno chiusura zero o negativa |
| `quota_senza_prezzo` | la frazione, arrotondata a quattro cifre |
| `liquidita_insufficiente` | vero **oltre il 20%**: il titolo non ha abbastanza sedute quotate per starci dentro un backtest |

La soglia del 20% è una **segnalazione, non un filtro**: la vista marca, non toglie. Sta in un posto solo,
`catalog.QUOTA_LIQUIDITA_INSUFFICIENTE`. Si legge con `api.liquidity()`.

### Sequenze a volume zero con prezzo fermo

Una **sequenza sospetta** è fatta di almeno **20 sedute consecutive con volume zero e chiusura identica**
(`market_data/quality/checks.py`, `sequenze_volume_zero`): sono prezzi riportati, non scambi. Esempio: BHP in Australia,
1988-1998, dati mensili ripetuti ogni giorno. Un volume mancante interrompe la sequenza.

**Regola:** nei backtest **quei periodi si escludono**, come i periodi prima di un salto sospetto.

### Calendario delle sedute

Le sedute vengono dalla libreria `exchange_calendars` (EODHD non vende le festività in questo piano). Confronto con un
titolo liquido per borsa: fatto nella fase 1 (resoconto non pubblicato: misure per titolo su dati EODHD).

**Parigi e Xetra: il calendario prima del 1999 non è affidabile.** Parigi: circa 90 giorni fra il 1985 e il 1998 che la
libreria dà come sedute ma erano festivi, o il contrario. Xetra: 20 festività tedesche mancanti nella libreria. Per quelle
borse, prima del 1999, un giorno senza prezzo non è per forza un buco nei dati.

**Tutte le borse: prima del 1985 il calendario non è verificato.** La tabella parte dal 1960 perché i prezzi USA partono
dal 1962; la libreria conosce le chiusure storiche di New York (1963, 1968, 1977) ma dà come sedute i Capodanni del 1960
e del 1962.

### Barre prima della quotazione della società attuale

Un codice attivo **non deve avere barre prima della data di quotazione della società che oggi lo usa**, quando quella
data si ricava da EDGAR o dai file delle partecipazioni iShares. Le barre precedenti sono segnalate: di solito sono la
storia della società che usava prima lo stesso ticker (esempio: `P` di Everpure con 1.083 barre di Pandora). Si
tolgono le barre identiche a quelle del gemello `_old`; le altre restano segnalate e fuori dai backtest.

## Registri (esistono già)

### `eodhd/manifest/chiamate.jsonl`

Una riga per ogni richiesta partita verso EODHD, anche le ripetizioni.

| campo | significato |
|---|---|
| `quando` | istante della richiesta, UTC |
| `giorno` | giorno UTC a cui la chiamata è conteggiata |
| `endpoint` | percorso chiamato, per esempio `eod/AAPL.US` |
| `parametri` | parametri della richiesta, senza la chiave |
| `costo` | chiamate che EODHD addebita per questa richiesta |
| `stato` | codice HTTP della risposta (0 = nessuna risposta, errore di rete) |
| `tentativo` | 1 per la prima richiesta, 2-3 per le ripetizioni |
| `byte` | dimensione della risposta |

### `eodhd/manifest/grezzo.jsonl`

Una riga per ogni file salvato nel livello grezzo.

| campo | significato |
|---|---|
| `file` | percorso del file compresso, relativo all'archivio |
| `endpoint`, `parametri` | da dove viene la risposta (senza la chiave) |
| `scaricato` | quando, UTC |
| `stato` | codice HTTP |
| `byte` | dimensione della risposta non compressa |
| `sha256` | impronta della risposta non compressa: se cambia, il dato è cambiato |
| `righe` | elementi della lista JSON o righe del CSV; vuoto se la risposta non è una lista |

### `eodhd/manifest/aggiornamenti.jsonl`

Scritto dall'aggiornamento incrementale, una riga per fatto. Campo `tipo`:

| `tipo` | campi | significato |
|---|---|---|
| `inizio` | `borsa`, `data` | giorno da cui parte la copertura della borsa (il giorno prima del primo download per titolo); scritto una volta |
| `seduta` | `borsa`, `data`, `esito`, `stati`, `righe`, `righe_nostre`, `riferimento` | una seduta scaricata in blocco. `stati`: per `prezzi`, `split`, `dividendi` il codice HTTP, o `non lista` se la risposta 200 non era una lista JSON. `righe_nostre`: titoli con serie che hanno una riga con la data della seduta. `esito`: `ok`, `fallito` (un blocco non valido), `corto` (righe dei nostri titoli sotto metà del riferimento), `corto accettato` (corto in 3 giorni diversi). Coperte: `ok` e `corto accettato` |
| `lavoro` | `borsa`, `codice`, `motivo`, `data`, `tabelle` | serie da scaricare, scritta prima di scaricare. `motivo`: `nuovo` o `delistato nuovo` (`data` = giorno in cui è entrato in coda), `riuso` (`data` = ISIN o nome nuovi), `split` o `dividendo` (`data` = giorno dell'evento) |
| `fatto` | `borsa`, `codice`, `motivo`, `data`, `esito` | lavoro chiuso: `ok`; `non disponibile` (404 in almeno 5 giorni diversi da quando è in coda); `uscito dalle liste` |
| `non trovato` | `borsa`, `codice`, `tabella` | una risposta 404 a un lavoro in coda (non salvata nel grezzo) |
| `riuso` | `borsa`, `codice`, `identita`, `dal` | ticker riusato: la normalizzazione ignora le versioni della serie scaricate prima di `dal` |
| `identificativi` | `stato` o `file` | `stato: salvataggio` prima di salvare le pagine, poi `file` con le pagine salvate: la normalizzazione usa solo l'ultima mappatura con `file` (o, se il primo salvataggio si è interrotto, le pagine di prima) |

Ogni riga ha anche `quando` (UTC).
