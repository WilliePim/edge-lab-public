# ADR 012 — Salto di livello non spiegato: una chiusura che sale di cinque volte e resta; elenco esplicito `api.salti_di_livello()`, prezzi e default invariati

**Data:** 2026-10-07 · **Stato:** accettata **nella versione 2**, decisa dopo aver visto i conteggi della versione 1
(e dichiarata come tale): solo i rialzi, con l'esenzione dei «movimento vero» · **Specchio:** `DECISIONS.md` di
edge-lab, ADR-058 (debito sugli studi chiusi)

## Regola adottata (versione 2) — leggere questa

La barra del giorno G di un codice è un **salto di livello non spiegato** se valgono tutte: (1) chiusura grezza c e
chiusura p della barra precedente valide, a non più di 10 giorni di calendario; (2) **c / p ≥ 5** (solo rialzi); (3)
nessuno split registrato con la data di G lo spiega (tabella `split` con fattore f tale che 1/1,25 ≤ (c/p)·f ≤ 1,25, o
nota `split_del_fornitore`); (4) le 5 barre successive esistono e stanno entro il 50% da c; (5) **G non è il giorno di
un `salto_sospetto` che la verifica con le azioni di ADR 010 classifica «movimento vero»**. I ribassi restano nei dati
come sono.

`api.salti_di_livello(simboli, verifica_salti=None, barre_isolate=None, direzione="rialzi",
esenta_movimento_vero=True)`: **i valori di default sono la regola adottata.** La prima versione, simmetrica («alla
lettera»), resta disponibile come variante esplicita con `direzione="entrambe", esenta_movimento_vero=False`: serve a
chi vuole misurare quanto un risultato dipende dalla scelta. Con l'esenzione attiva la funzione legge i file SEC (come
`salti_classificati`).

## Storia delle versioni

| versione | quando | che cosa | perché |
|---|---|---|---|
| **1 — simmetrica** | 2026-10-07, ore 09:15, **prima di contare** | rapporto ≥ 5 **oppure** ≤ 0,2, nessuna esenzione | — |
| **2 — adottata** | 2026-10-07, verso mezzogiorno, **decisa dopo aver visto i conteggi della versione 1** (80 salti: 18 rialzi e 62 ribassi; riparto per classe e volume; dieci esempi presi e dieci non presi) | solo rialzi (≥ 5); esenzione dei «movimento vero» di ADR 010; il resto invariato | **la versione simmetrica toglieva crolli veri** |

È ciò che mostrano i conteggi della versione 1: nel riparto per volume e per verifica con le azioni (più sotto) fra
i ribassi presi il crollo vero è il caso frequente, fra i rialzi lo è l'errore di dati.

Nessuna soglia è cambiata fra le due versioni: 5, 5 barre, 50%, 10 giorni e ±25% sono quelli scritti alle 09:15. La
modifica è **successiva ai conteggi** e va letta così: non è una regola scritta alla cieca, è una correzione motivata e
registrata. Per questo la variante «alla lettera» resta disponibile: chi usa l'elenco in uno studio può riportare
accanto il risultato con la versione simmetrica e dire se cambia.

## Conteggi della versione adottata

Universo di circa 2.000 piccole società USA, titoli in portafoglio nel 2017-2026. **Solo conteggi:
nessun rendimento di portafoglio.**

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | totale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **regola adottata** (tutti rialzi) | 0 | 1 | 5 | 3 | 1 | 2 | 3 | 1 | 0 | 2 | **18** |
| variante «alla lettera» | 6 | 8 | 9 | 8 | 10 | 6 | 11 | 9 | 5 | 8 | 80 |

- 18 salti di 18 titoli. **L'esenzione non toglie nessuno dei 18** (nessun rialzo era un «movimento vero» di ADR 010:
  i dieci «movimento vero» presi dalla versione 1 erano tutti ribassi).
- Dei 20 rialzi di dieci volte o più rimasti dopo le barre isolate (ADR 011) ne prende **7**, gli stessi della
  versione 1; i motivi dei non presi sono elencati più sotto.
- Volume del giorno dei 18: 8 oltre il milione, 5 fra 100.000 e 999.999, 5 sotto 100.000.

**Limite trovato contando la versione adottata, non corretto: 9 dei 18 salti presi sono raggruppamenti registrati
proprio in quella data.** La grezza sale di 7-125 volte, **la rettificata quel giorno si muove fra −38% e +45%**, cioè
il titolo ha perso (o guadagnato) più del 25% nel giorno stesso del raggruppamento, e il prodotto rapporto × fattore
esce dalla tolleranza di ±25% scritta alle 09:15. Per questi nove la serie viene segnalata senza che ci sia un errore
di dati. Gli altri nove hanno il salto anche nella rettificata; almeno uno, con decine di milioni di titoli scambiati,
è a occhio un rialzo vero. *Correzioni possibili, non adottate: tolleranza più larga sul fattore dello split (per
esempio rapporto × fattore fra 0,5 e 2), oppure valutare il salto sulla rettificata (10 rialzi invece di 18).*
Verificato con `api.prices` e `api.splits` sui 18 codici.

**Limiti della regola adottata.** (1) Usa le 5 barre dopo il salto: spezzare una serie all'ultima chiusura prima del
salto non è eseguibile in tempo reale. (2) Un rialzo vero di cinque volte che resta è preso, salvo che sia un
`salto_sospetto` verificato come «movimento vero». (3) Non prende i codici che finiscono entro 5 barre dal salto, i
livelli che oscillano, gli errori della sola rettifica: 11 rialzi di dieci volte o più restano. (4) I ribassi non sono
toccati: gli errori verso il basso (società comprate il cui codice prosegue a centesimi) restano nei dati. (5) I nove
raggruppamenti presi per la tolleranza stretta.

---

# Versione 1 (simmetrica) — com'era stata scritta prima di contare, e i suoi conteggi

*Da qui in giù la regola è quella della prima versione. Dove dice «la regola» intende la versione simmetrica.*

> **Ordine di scrittura.** Le sezioni «La regola» e «Letture» sono state scritte il **2026-10-07 alle 09:15, prima di
> contare che cosa la regola trova**. Ciò che viene dopo i conteggi sta in «Conteggi». Che cosa era già stato visto, e
> va detto: i risultati di un backtest pre-registrato poi invalidato per errori nei prezzi (non registrati e non
> pubblicati); i conteggi di ADR 011, con l'elenco dei venti rialzi più grandi rimasti dopo la regola delle barre
> isolate e le loro chiusure; dieci esempi di rendimenti estremi rimasti; la tabella degli split di cinque codici.

## Contesto

Dopo la regola delle barre isolate (ADR 011), nello stesso universo di piccole società restano 711 rendimenti
giornalieri estremi. Fra i 20 rialzi di dieci volte o più, in 15 il nuovo livello resta: non sono barre che vanno e
tornano, sono serie che cambiano livello — azioni nuove sullo stesso codice dopo una riorganizzazione (un codice che
passa da pochi centesimi a decine di dollari e ci resta), raggruppamenti che il fornitore non ha rettificato, due
titoli sotto un codice. Il controllo `salto_sospetto` di ADR 006 non li segnala (cerca rapporti vicini a quelli tipici
di uno split). Di qui una terza regola, **esplicita, non di default, con ADR e test**.

## La regola (scritta prima dei conteggi)

Per un codice, sulla serie dei suoi prezzi puliti (quelli che `prices(clean=True, …)` restituisce con le opzioni
chieste, su tutte le date), la barra del giorno G è un **salto di livello non spiegato** se valgono tutte:

1. **Serie guardata: la chiusura grezza `close`.** c è la chiusura di G, p quella della barra precedente dello stesso
   codice; entrambe finite e maggiori di zero.
2. **Consecutive e vicine**: la barra precedente dista da G **non più di 10 giorni di calendario** (come in ADR 011).
   Oltre: non valutato (dopo una sospensione lunga un altro prezzo non è «due chiusure consecutive»).
3. **Rapporto**: r = c / p **≥ 5 oppure ≤ 0,2**, estremi compresi.
4. **Senza uno split registrato in quella data con un fattore compatibile.** Il salto è **spiegato**, e non è preso,
   se l'archivio ha per quel codice, **con la data di G**: (a) una riga della tabella `split` con fattore f (azioni
   nuove / vecchie) tale che r·f stia fra 1/1,25 e 1,25 (uno split 1 a 10 ha f = 0,1 e porta la grezza a dieci volte:
   r·f = 1); oppure (b) una nota `split_del_fornitore` (ADR 006: il fornitore ha applicato lo split alla rettificata
   senza metterlo in tabella — è uno split che l'archivio conosce; il suo fattore è per costruzione quello del salto).
5. **Il nuovo livello persiste**: le **5 barre successive** a G nella serie del codice esistono tutte e ciascuna ha
   |c₊ₖ / c − 1| ≤ 0,5 (k = 1…5), con chiusure valide. Se dopo G ci sono meno di 5 barre: **non valutabile, non
   preso**.

Vale in entrambe le direzioni. Ogni barra si valuta da sola, una volta, sulla serie di partenza.

## Letture (scritte prima dei conteggi; alternative accanto)

- **Grezza e non rettificata.** Gli split registrati si vedono nella grezza. Conseguenza: uno split vero che
  l'archivio non conosce affatto (né tabella né nota) e che il fornitore non ha rettificato è preso — ed è giusto,
  perché anche la rettificata salta. Uno split che il fornitore ha rettificato e annotato è spiegato dal punto 4b.
  *Variante contata: la stessa regola sulla `adjusted_close`, senza il punto 4 (sulla rettificata uno split noto non
  compare).*
- **«In quella data» alla lettera**: la data dello split deve essere quella di G.
- **Compatibile = entro ±25%** (1/1,25 ≤ r·f ≤ 1,25), la stessa tolleranza di ADR 010.
- **Persistenza misurata sulle 5 barre successive, qualunque distanza abbiano**; rispetto al nuovo livello c, non alla
  media. *Variante contata: entro il 25%.*
- **Ordine con le altre regole**: `clean=True` → `verifica_salti` → `barre_isolate` → salti di livello. **Le barre
  isolate si tolgono prima**: una barra che va e torna è fatta di due salti, e il secondo (il ritorno) «persiste» —
  senza toglierla prima, ogni barra isolata di cinque volte diventerebbe un salto di livello al suo ritorno.
  `api.salti_di_livello(simboli, verifica_salti=…, barre_isolate=…)` valuta la serie che quelle opzioni
  restituiscono.
- **Un salto che ADR 010 ha classificato «movimento vero» è preso lo stesso** (in questa versione).
  **Questo vuol dire che la regola prende anche crolli e rialzi veri di cinque volte**: una società che perde l'80% in
  una seduta e resta lì è, per questa regola, un salto di livello. Quanti sono si vede nei conteggi (riparto per
  classe della verifica con le azioni e per volume del giorno), e va deciso guardandoli.
- **Due salti a meno di 5 barre l'uno dall'altro**: il primo non persiste (il secondo lo porta fuori dal 50%) e non è
  preso; il secondo sì, se persiste. Alla lettera.
- *Variante contata: soglie 3 e 1/3 al posto di 5 e 0,2.*

## Forma in market-data

- `quality/salti_livello.py`: regola pura, senza archivio.
- **`api.salti_di_livello(simboli, verifica_salti=None, barre_isolate=None, …)`**: l'elenco dei salti, una riga per
  salto: `exchange`, `code`, `date` (il giorno del salto), `date_prima`, `close_prima`, `close`, `rapporto`,
  `direzione` (`rialzo` o `ribasso`), `volume`.
- **`prices()` non cambia e non ha un'opzione nuova.** La regola non toglie barre: i prezzi dopo il salto sono veri
  prezzi (di un altro titolo, o dello stesso su un'altra scala). Che cosa fare della serie è una decisione di chi usa
  l'elenco, sta nel suo programma e va scritta nella sua pre-registrazione. **Default invariato per costruzione**;
  niente si scrive nell'archivio.

## Informazione successiva

La regola usa le 5 barre **dopo** il salto: l'elenco è una correzione a posteriori del dato, come ADR 010 e ADR 011. Ma
un uso possibile dell'elenco va detto com'è: **interrompere una serie «all'ultima chiusura prima del salto» usa
informazione successiva**. Non è eseguibile in tempo reale. Se il salto è un errore di dati l'interruzione è neutra
(toglie un rendimento che non c'è stato). Se è un movimento vero, **toglie dai dati un crollo o un rialzo reale**: è
il motivo per cui il riparto fra errori e movimenti veri va contato prima di usare la regola, ed è ciò che ha portato
alla versione 2.

## Conteggi (scritti dopo; la regola della versione 1 non è cambiata)

Stesso universo, titoli in portafoglio nel 2017-2026, prezzi puliti con `verifica_salti="azioni"` e
senza le barre isolate; due lanci identici. **Solo conteggi: nessun rendimento di portafoglio.**

**Salti trovati: 80, di 71 titoli — 18 rialzi e 62 ribassi.**

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | totale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| salti | 6 | 8 | 9 | 8 | 10 | 6 | 11 | 9 | 5 | 8 | 80 |
| rialzi (≥ 5) | 0 | 1 | 5 | 3 | 1 | 2 | 3 | 1 | 0 | 2 | 18 |
| ribassi (≤ 0,2) | 6 | 7 | 4 | 5 | 9 | 4 | 8 | 8 | 5 | 6 | 62 |

Barre con rapporto ≥ 5 o ≤ 0,2: 271; 140 spiegate da uno split in quella data, **80 prese**, 35 non
persistono, 9 con la barra precedente oltre 10 giorni, 7 con meno di 5 barre dopo.

**Quanti sono movimenti veri — il riparto.**

| | rialzi | ribassi | totale |
|---|---:|---:|---:|
| senza nessuna segnalazione di market-data a quella data | 18 | 52 | 70 |
| `salto_sospetto` classificato **movimento vero** da ADR 010 | 0 | 10 | 10 |
| volume del giorno ≥ 1.000.000 | 8 | 38 | **46** |
| volume da 100.000 a 999.999 | 5 | 11 | 16 |
| volume sotto 100.000 (di cui sotto 1.000) | 5 (2) | 13 (4) | 18 (6) |

**Più della metà dei salti presi (46 su 80) ha oltre un milione di titoli scambiati quel giorno, e 38 di questi sono
ribassi**: è il profilo di un crollo vero (un farmaco bocciato, un fallimento annunciato) più che di un errore di dati
— **un indizio, non una prova**: almeno un caso che a occhio è un errore ha 3 milioni di titoli scambiati.
Dieci sono proprio i salti che ADR 010 aveva verificato come movimenti veri con le azioni in circolazione. A occhio,
sui dieci estratti a seme fisso (lettura dichiarata come tale): tre movimenti veri, cinque errori di dati (quattro
società comprate a un prezzo, il cui codice prosegue poi a centesimi; un raggruppamento non registrato), due dubbi.
**La regola, così com'è scritta, prende insieme errori e crolli veri, e la soglia di cinque volte non li distingue.**

**I 20 rialzi di dieci volte o più rimasti dopo le barre isolate: presi 7.** Non presi: 2 sono passaggi di codice
(fuori dalla portata di questa regola); 3 hanno meno di 5 barre dopo il salto (il codice finisce subito dopo); 6 non
persistono; 1 ha la barra precedente oltre 10 giorni; 1 ha uno split registrato e compatibile in quella data, **ma la
rettificata salta lo stesso** (errore della rettifica, che una regola sulla grezza non può vedere). Ribassi a un decimo
o meno: presi 28 su 51 (6 con la barra precedente lontana, 3 passaggi di codice, 2 senza 5 barre dopo, 2 che non
persistono, 10 in cui salta la sola rettificata e la grezza no).

**Varianti (solo conteggi).**

| variante | rialzi | ribassi | totale |
|---|---:|---:|---:|
| **regola della versione 1** (soglia 5, persistenza 50%, grezza) | 18 | 62 | **80** |
| soglia 3 e 1/3 | 52 | 131 | 183 |
| persistenza entro il 25% | 12 | 49 | 61 |
| sulla rettificata, senza la condizione dello split | 10 | 67 | 77 |
| soglia 3 e 1/3, sulla rettificata | 42 | 136 | 178 |

Dieci casi con rapporto fra 3 e 5 (o fra 0,2 e 1/3), non presi (167 in tutto), a occhio: sei crolli veri con decine di
milioni di titoli; due frazionamenti o raggruppamenti che la grezza mostra; due dubbi. Abbassare la soglia a 3
porterebbe dentro soprattutto movimenti veri.

**Tutto l'archivio letto** (30.002 codici USA di borsa o con CIK, vivi dal 2015-12; barre dal 2015-10-01, senza le
barre isolate): 5.402 salti di livello non spiegati (3.070 rialzi, 2.332 ribassi) in 3.167 codici. Nell'archivio intero
i rialzi sono più dei ribassi; fra le piccole società dell'universo contato il contrario.

**Prezzi e default invariati: prova sull'archivio vero.** 1.500 codici `Common Stock` USA estratti con
`random.Random(20261007)`, 1.761.705 righe: `prices()` del modulo all'ultimo commit e del modulo modificato danno la
stessa tabella (impronta `6b847611e4205ef6`), con e senza `barre_isolate`, prima e dopo aver chiesto l'elenco dei salti
(235 su quel campione). Test: `tests/test_salti_livello.py` (12, comprese la direzione e l'esenzione della versione 2).

## Che cosa si sapeva prima di adottarla (scritto per la versione 1)

1. **Prende crolli veri.** Fino a 38 dei 62 ribassi presi hanno il volume di un movimento vero (indizio, non prova);
   10 sono verificati come veri da ADR 010; sui dieci estratti a occhio i veri sono 3. Usata per interrompere le
   serie, la regola toglierebbe dai dati perdite che ci sono state davvero: una distorsione introdotta da una regola
   di pulizia, scritta sapendolo.
2. **Non prende tutto ciò per cui è nata**: 7 su 20 dei rialzi di dieci volte o più. I casi che sfuggono sono i codici
   che finiscono entro 5 barre dal salto, i livelli che oscillano, e gli errori della sola rettifica.
3. **Alternative che il riparto suggeriva**: (a) non prendere i salti che ADR 010 classifica «movimento vero» (10 su
   80); (b) non prendere i salti con volume sopra una soglia (46 su 80 sopra il milione); (c) prendere solo i rialzi
   (18), dove l'errore di dati è il caso normale, e lasciare i ribassi (62), dove il crollo vero è il caso normale.
   La versione 2 adotta (a) e (c).
