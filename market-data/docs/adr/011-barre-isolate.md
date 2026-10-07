# ADR 011 — Barre isolate: una chiusura che va e torna si scarta; opzione esplicita `barre_isolate="scarta"`, default invariato

**Data:** 2026-10-06 · **Stato:** accettata il 2026-10-07 nella forma principale (solo sul prezzo), com'era scritta
prima di contare; le varianti con il volume restano solo nei conteggi · **Specchio:** `DECISIONS.md` di edge-lab,
ADR-058 (debito sugli studi chiusi)

> **Ordine di scrittura.** La sezione «La regola» qui sotto è stata scritta il 2026-10-06 alle 15:00, **prima di contare
> che cosa elimina**. Tutto ciò che viene dopo il primo conteggio sta nella sezione «Conteggi» e, se la regola fosse
> cambiata, in «Versioni della regola». Che cosa era già stato visto quando è stata scritta, e va detto: i risultati di
> un backtest pre-registrato poi invalidato proprio per questi errori (non registrati e non pubblicati), l'elenco dei
> rendimenti giornalieri estremi più grandi per lato, le cinque sedute attorno ai più grandi al rialzo, e il conteggio
> 825 = 306 + 519 con la sua divisione per classe di segnalazione.

## Contesto

In un backtest pre-registrato su un universo di circa 2.000 piccole società USA (2017-2026) un controllo sui rendimenti
giornalieri estremi ha trovato nei prezzi puliti barre palesemente sbagliate: una chiusura che passa da qualche decina
di centesimi a centinaia di dollari e torna al prezzo di prima il giorno dopo, con una manciata di titoli scambiati. La
barra passa i controlli di ADR 006 (un `salto_sospetto` richiede un rapporto vicino a uno split **senza ritorno** nelle
20 sedute dopo: una barra che torna non è un salto sospetto) e sta nei prezzi puliti con e senza `verifica_salti`. I
rendimenti giornalieri ≥ +100% o ≤ −50% di un titolo in portafoglio erano 825 in dieci anni, 701 senza nessuna
segnalazione. Gli errori cambiavano l'esito di un confronto pre-registrato: l'esecuzione è stata dichiarata non valida
e rifatta con regole scritte prima di contare che cosa tolgono, ma dopo aver visto i risultati invalidati (vedi «Ordine
di scrittura»). Questa è la prima: una regola per le barre isolate in market-data, **come opzione esplicita, non di
default**, con ADR e test, e i conteggi prima di qualunque riesecuzione.

## La regola (scritta prima dei conteggi)

Proposta di partenza: «barra scartata se la chiusura si discosta di oltre il 50% sia dalla chiusura precedente sia
dalla successiva, e la successiva torna entro il 10% dalla precedente; oppure volume sotto una soglia minima».

**Regola principale (R — solo prezzo).** Per un codice, sulla serie dei suoi prezzi puliti (quelli che
`prices(clean=True)` restituisce con le stesse opzioni, su tutte le date, non solo quelle chieste), una barra del
giorno G con chiusura x è **isolata**, e si scarta, se valgono tutte:

1. **Serie guardata: `adjusted_close`.** x, p, s sono le `adjusted_close` di G, della barra precedente e della barra
   successiva dello stesso codice, tutte finite e maggiori di zero. *Perché la rettificata e non la grezza*: è la serie
   da cui si calcolano i rendimenti; è continua attraverso split e dividendi, quindi uno split vero non vi compare
   come movimento (e comunque uno split non torna: nemmeno sulla grezza sarebbe preso); e prende anche l'errore della
   sola rettifica (fattore applicato un giorno prima o dopo). La variante sulla grezza `close` è contata a parte.
2. **Vicine nel tempo.** «Precedente» e «successiva» sono la barra prima e la barra dopo nella serie pulita del codice;
   devono distare da G **non più di 10 giorni di calendario** ciascuna. Dopo una sospensione più lunga un prezzo
   diverso non è una barra isolata: non valutabile, resta.
3. **Si discosta di oltre il 50% da entrambe, dalla stessa parte**: (x > 1,5·p **e** x > 1,5·s) oppure (x < 0,5·p **e**
   x < 0,5·s).
4. **La successiva torna entro il 10% dalla precedente**: |s / p − 1| ≤ 0,10.

Non valutabili, e quindi mai scartate: la prima e l'ultima barra della serie di un codice (**l'ultima barra disponibile
non è mai verificabile**: manca la successiva), una barra con una vicina oltre 10 giorni, una barra con la rettificata
mancante o non positiva (propria o di una vicina).

La regola è valutata **una volta sola sulla serie di partenza**: le barre scartate non diventano «vicine mancanti» per
un secondo giro (nessuna iterazione). Due barre isolate non possono essere adiacenti (la vicina di una barra isolata
sta entro il 10% dell'altra vicina, quindi non si discosta del 50% da entrambe le sue).

**Che cosa la regola non prende, per costruzione** (da contare):
- **due o più barre sbagliate consecutive** (p, x, x', s): ognuna ha una vicina sbagliata come lei;
- **le serie che alternano due livelli** quando un livello dura più di una barra; quando i livelli si alternano una
  barra sì e una no (A, B, A, B, A) ogni barra è «isolata» rispetto alle sue vicine: la regola le scarterebbe **tutte
  tranne le estreme**, che è sbagliato per metà di loro. È il caso da guardare nei conteggi;
- un movimento vero di oltre il 50% che torna entro il 10% il giorno dopo **verrebbe scartato**: è il rischio della
  regola a solo prezzo.

**Varianti con il volume** (contate accanto alla principale; soglia: **volume della barra < 1.000 titoli**, numero
assoluto scritto prima dei conteggi):
- **R-E (prezzo E volume)**: le condizioni 1-4 **e** volume < 1.000. Scarta meno: lascia gli errori con un volume
  normale, non scarta i movimenti veri molto scambiati.
- **R-O (prezzo O volume)**: le condizioni 1-3 **e** (la 4 **oppure** volume < 1.000). Scarta di più: prende anche la
  barra che va e torna solo in parte, se quasi nessuno ha scambiato.
- **R-grezza**: la principale con `close` al posto di `adjusted_close`.

**Estensione a 2-3 barre** (R2, **non adottata**): un gruppo di 2 o 3 barre consecutive,
tutte oltre il 50% dalla stessa parte rispetto sia alla barra prima del gruppo sia alla barra dopo, con la barra dopo
entro il 10% dalla barra prima, e tutto il gruppo dentro 10 giorni di calendario fra la barra prima e la barra dopo.
Si conta quante barre in più prenderebbe; si propone solo se i conteggi mostrano che serve.

## Informazione successiva

La regola usa la barra **successiva**: non è un filtro eseguibile in tempo reale. È una correzione a posteriori della
qualità del dato, come uno split che il fornitore registra dopo o come la verifica dei salti di ADR 010: risponde a
«questo prezzo c'è stato davvero?», non a «dove andrà il prezzo». In un backtest è lecita a una condizione: che la
barra scartata sparisca **per tutti gli usi** (valori, esecuzioni, qualunque regola che legga un prezzo) e non solo per
alcuni. Conseguenze da dichiarare da chi la usa: (a) l'ultima barra di ogni serie non è verificabile; (b) un valore che
si sarebbe letto su una barra isolata viene letto, con la regola, sulla barra prima (cioè come se quel prezzo non fosse
mai stato stampato).

## Implementazione

- `quality/barre_isolate.py`: funzione pura `isolate(giorni, valori, volumi=None, ...)` → maschera; costanti della regola.
- `api.prices(simboli, clean=True, barre_isolate="scarta")`: toglie le barre isolate dal risultato. Si combina con
  `verifica_salti`. Vale solo con `clean=True`. La serie su cui si valuta è quella intera del codice (le date chieste
  si applicano dopo), così una richiesta con `start`/`end` non cambia quali barre sono isolate.
- `api.barre_isolate(simboli)`: l'elenco delle barre che l'opzione scarta (`exchange`, `code`, `date`, le tre chiusure
  rettificate e grezze, le due date vicine, `volume`), per contarle e guardarle.
- **Default invariato**: senza l'argomento `prices()` esegue la stessa interrogazione di prima. Niente si scrive
  nell'archivio: nessuna segnalazione, nessuna riga nelle verifiche (stessa ragione di ADR 010, punto 4).
- Solo calcolo al volo, in memoria, sui prezzi letti; nessun file.

## Alternative scartate (prima dei conteggi)

- **Cambiare il default dei prezzi puliti**: cambierebbe in silenzio i numeri degli studi chiusi; resta un debito
  (verificarli con questa regola: `DECISIONS.md` di edge-lab, ADR-058).
- **Un controllo nuovo in `quality/checks.py` che scrive segnalazioni**: è la forma giusta se la regola resta a lungo;
  farlo ora cambierebbe `flags()` e, se `esclude`, il default. Rinviato.
- **Soglia relativa del volume** (rispetto alla mediana delle sedute prima): più adatta a titoli molto scambiati, ma
  introduce una finestra e un secondo parametro.

## Conteggi (scritti dopo; la regola non è cambiata)

Universo di circa 2.000 piccole società USA, titoli in portafoglio nel 2017-2026, prezzi puliti con
`verifica_salti="azioni"`; due lanci identici. **Solo conteggi: nessun rendimento di portafoglio.**

**Gli 825 rendimenti giornalieri estremi (≥ +100% o ≤ −50%).**

| regola | eliminati | restano | rialzi: eliminati / restano | ribassi: eliminati / restano |
|---|---:|---:|---:|---:|
| **R (principale, solo prezzo, rettificata)** | **114** | **711** | 57 / 249 | 57 / 462 |
| R-E (prezzo E volume < 1.000) | 91 | 734 | 46 / 260 | 45 / 474 |
| R-O (prezzo, e ritorno O volume < 1.000) | 116 | 709 | 58 / 248 | 58 / 461 |
| R-grezza | 115 | 710 | 57 / 249 | 58 / 461 |
| R più l'estensione a 2-3 barre (non adottata) | 140 | 685 | 71 / 235 | 69 / 450 |

Per classe (R): senza segnalazione 114 eliminati su 701; riammessi come «movimento vero» da ADR 010 0 su 107; a un
passaggio di codice 0 su 17. Per anno (R): la gran parte dei 114 sta in un solo anno e in un solo codice, che per
tutto l'anno alterna due livelli (48 barre scartate). Negli altri anni la regola elimina 0-6 rendimenti estremi l'anno.

**Quante barre scarta R.** Fra i circa 4,9 milioni di titoli-seduta dell'universo: **73 barre di 22 codici** (R-E 49 di
3 codici; R-O 74; R-grezza 74; l'estensione ne aggiungerebbe 89 di 8 codici). In tutti i 30.002 codici USA letti (di
borsa o con CIK, vivi dal 2015-12; 26,3 milioni di barre dal 2015-10-01): **circa 15.700 barre di 3.900 codici** (R-E
5.900; R-O 18.800; estensione 20.000 in più): sei barre su diecimila, in gran parte titoli OTC. Volume delle 73 barre
dell'universo: 49 sotto 1.000 titoli (mediana 0), 7 fra 1.000 e 99.999, **17 con 100.000 titoli o più**.

**Che cosa resta, ed è il punto.** Dei 711 che restano: rialzi da ×2 a ×5 211, da ×5 a ×10 18, ×10 o più 20; ribassi
da −50% a −80% 362, fino a −90% 49, oltre −90% 51. A occhio (dieci estratti a seme fisso, lettura dichiarata come
tale): sette sono movimenti veri con volumi di milioni di titoli, uno è un titolo in fallimento a un millesimo di
dollaro, uno ha un buco di due mesi fra le due barre, uno sembra una rettifica sbagliata che non torna. **Fra i 20
rialzi di ×10 o più, in 15 la chiusura di cinque sedute dopo è ancora sopra la metà: non sono barre isolate, sono
livelli che restano** (un codice che passa da pochi centesimi a decine di dollari e ci resta, senza split
registrato): azioni nuove sullo stesso codice dopo una riorganizzazione, raggruppamenti non rettificati, due titoli
sotto un codice. Non hanno un `salto_sospetto` a quella data (il controllo di ADR 006 cerca rapporti vicini a quelli
tipici di uno split) e **nessuna regola a barre isolate li prende**. È un problema diverso: ADR 012.

**Serie che alternano due livelli.** Dove i livelli si alternano una barra sì e una no la regola toglie le barre di un
livello **e anche dell'altro** (tutte tranne le estreme del tratto): in un codice 48 barre; in un altro 15 barre su 251
in un anno. Il risultato è una serie più corta e ancora mista, non una serie corretta. Un codice così andrebbe escluso
intero, non ripulito barra per barra.

**Rischio di scartare movimenti veri.** Delle 73 barre scartate nell'universo, 17 hanno 100.000 titoli o più. Fra i
dieci esempi estratti la sola con molto volume sta su un codice con otto salti segnalati, una serie sporca. **Le altre
16 non sono state guardate una per una**: non si può dire che nessuna sia un movimento vero. La variante R-E (volume <
1.000) non corre questo rischio e lascia 23 rendimenti estremi in più.

**Il default non cambia: prova sull'archivio vero.** 1.500 codici `Common Stock` USA estratti con
`random.Random(20261006)`, 1.900.151 righe: `prices()` del modulo com'era all'ultimo commit e `prices()` del modulo
modificato danno la stessa tabella (impronta `0465412d3168dd1d` in entrambi, e ancora la stessa dopo aver usato
l'opzione nello stesso processo); con l'opzione le righe in meno sono 414. Test: `tests/test_barre_isolate.py` (15).

## Versioni della regola

**Una sola.** La regola principale e le varianti sono quelle scritte prima dei conteggi; dopo i conteggi non sono
cambiate né soglie né condizioni. Due cose scritte dopo, che non toccano la regola: (1) i conteggi leggono R da
`api.barre_isolate` (serie intera) invece di rifarla sulle sole sedute del calendario — sulle sedute del calendario le
due coincidono; l'API ne trova altre in giorni che non sono sedute di borsa; (2) `api.regola_barre_isolate`, la
regola pura esposta dall'API perché chi conta le varianti non importi i moduli interni.

## Adozione (07-10-2026)

**Adottata la regola principale R, solo sul prezzo**, com'è scritta sopra. Le varianti con il volume (R-E, R-O), la
variante sulla grezza e l'estensione a 2-3 barre **restano solo nei conteggi**: l'opzione `barre_isolate="scarta"` fa
una cosa sola. Motivi: R toglie il caso che ha invalidato l'esecuzione; R-E era l'alternativa prudente per chi non
vuole rischiare movimenti veri; l'estensione a 2-3 barre prenderebbe 26 rendimenti estremi in più su 711, e 89 barre di
8 codici che sono serie a due livelli: non risolve il problema che resta. **La regola da sola non basta** a rendere
puliti i prezzi di un universo di piccole società: i livelli che restano sono fuori dalla sua portata (ADR 012).
