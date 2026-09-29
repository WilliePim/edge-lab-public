# RULES.md — le regole che lo scanner ha il diritto di applicare

Questo file esiste per la regola di controllo in [CLAUDE.md](CLAUDE.md): *se una
frase di un report non può essere ricondotta a un campo di un filing o a una
regola qui dentro, non ci sta.*

Ogni voce è un **fatto**: una regola dichiarata, riproducibile, che si calcola
per join o conteggio da EDGAR. Nessuna esprime merito. Dove c'è una soglia
numerica, la soglia è o presa dalla letteratura (e detto da dove) o validata su
una misura del corpus (e detto quale) — mai scelta a intuito. Eccezione
dichiarata: le soglie del predicato diluizione (§7), che vengono da osservazioni
dal vivo e sono marcate come non validate.

Ogni riga cita il punto del codice che la implementa. Se il codice cambia e
questo file no, questo file è sbagliato.

---

## 1. Che cosa conta come acquisto

**`open_market_buys`** — [parse.py:217](form4_scanner/parse.py#L217)

Una transazione entra se e solo se, tutte insieme:

| condizione | campo Form 4 |
|---|---|
| codice `P` | `transactionCode` |
| acquisizione | `transactionAcquiredDisposedCode == "A"` |
| non derivata | tabella non-derivative |
| non sotto piano 10b5-1 | `aff10b5One`, oppure `10b5-1` nelle footnote |
| valore ≥ soglia | `shares × pricePerShare` |

**Provenienza della soglia da $25.000.** Non è nata in una misura di oggi: è
config dello scanner dal primo commit — `DEFAULT_MIN_VALUE = 25_000.0`,
[scan.py:37](form4_scanner/scan.py#L37), commit `525bfd7` del 14 agosto 2026 —
e il corpus storico è stato costruito con la stessa soglia: lo script del backfill
di allora, `backfill_fetch.py`, non è più nel repo, ma la soglia che usava è
riportata in [cmp_calendar_time_long.md:19](reports/cmp_calendar_time_long.md).

Quello che se ne sa per misura: toglierla **cambia la conclusione**. In
`cmp_calendar_time_long.md` il test con la soglia non aveva la potenza di vedere
l'effetto Cohen-Malloy-Pomorski — serviva 1,01% al mese e il paper ne riporta
0,8 — e poteva solo dire «non riesco a misurarlo». Ogni misura sul corpus
riporta perciò le due popolazioni, con e senza soglia.

## 2. Classificazione del compratore (Cohen-Malloy-Pomorski)

**`classify_insider`** — [classify.py:51](form4_scanner/classify.py#L51)

Su tre blocchi mobili di 365 giorni ancorati alla data di valutazione — non anni
solari, perché i bucket solari perderebbero il marzo più vecchio di un
compratore di marzo valutato in agosto.

| etichetta | regola |
|---|---|
| `unseasoned` | nessun acquisto nei 3 anni **e** il CIK esiste da < 365 giorni |
| `novel` | nessun acquisto nei 3 anni, con storia osservabile |
| `sparse` | acquisti in < 3 dei 3 blocchi |
| `routine` | un mese solare ricorre in **tutti e tre** i blocchi |
| `opportunistic` | acquisti in tutti e tre i blocchi, nessun mese ricorrente |

`unseasoned` esiste perché una storia vuota e una storia non osservabile sono
fatti diversi. Senza `cik_first_filing` la distinzione non si può fare e
l'etichetta è `novel`: in assenza di prova non si inventa un declassamento.

## 3. Gruppi di compratori

**`buyer_groups`** — [cluster.py:34](form4_scanner/cluster.py#L34)

Union-find sui CIK dei proprietari che **condividono un'accession**. Chi
co-deposita è una decisione sola, non quattro: la società di gestione di un
fondo, il suo GP e i suoi feeder firmano lo stesso Form 4 per lo stesso scambio.
La fusione è transitiva.

**`max_window_buyers(window_days)`** — [cluster.py:105](form4_scanner/cluster.py#L105)
conta i **gruppi** distinti, non le teste, dentro la più densa finestra mobile
di `window_days`.

> **Limite noto, non corretto**: affiliati che depositano Form 4 *separati* non
> condividono accession e restano gruppi distinti. Caso reale: John Hancock GA
> Mortgage Trust, CIK 1742952, quattro controllate Manulife, quattro accession.

## 4. I quattro booleani di `score_v3`

**`score_v3`** — [flags.py:190](form4_scanner/flags.py#L190). Peso 1 ciascuno,
nessuna soglia sulla somma.

| booleano | regola |
|---|---|
| `cluster` | ≥2 gruppi con almeno un compratore `opportunistic` **e** `max_window_buyers(30) >= 2` |
| `director` | esiste una transazione con `isDirector` vero, `isOfficer` falso, `isTenPercentOwner` falso |
| `no_10pct` | nessuna transazione con `isTenPercentOwner` vero |
| `terreno` | il primo acquisto del cluster cade in `[D, D+90]` per una figlia dell'indice spin-off |

`terreno` è `None`, non `False`, se `data/spinoffs_index.json` non esiste: la
domanda non fatta e la risposta negativa sono fatti diversi.

**L'ordinamento dell'output** è `score_v3` decrescente, poi numero di compratori
nella finestra decrescente — [scan.py:354](form4_scanner/scan.py#L354). Non
esiste altro ordinamento.

## 5. Terreno spin-off

**`tools/spinoffs.py`**, indice in `data/spinoffs_index.json`. L'indice non fa
parte del repository: lo costruisce lo strumento da EDGAR, insieme al funnel
che ne misura la resa. Senza indice `terreno` vale `None` (§4).

### La rete — solo metadati

| passo | regola |
|---|---|
| candidati | CIK con un **Form 10-12B** (o `/A`) dal 2015, dai `form.idx` trimestrali |
| rete | **EX-99.1 presente** fra gli exhibit del 10-12B o di una qualsiasi delle sue `/A` |

Il 10-12G è **fuori per default**: gli spin-off quotati si registrano sotto la
Section 12(b), e il 12(g) lo usano anche shell, banche e graduati dalla Reg A.

> **Perché la rete non legge la descrizione degli exhibit.** La regola naturale
> sarebbe «EX-99.1 descritto come *Information Statement*» più «un exhibit
> descritto come *Separation and Distribution Agreement*». **Quella descrizione
> non esiste nei metadati EDGAR.** Campionata su sei spin-off certi, sia nella
> tabella `-index.htm` sia nell'intestazione SGML, il campo ripete il numero:
>
> ```
> TYPE=EX-99.1     DESCRIPTION=EX-99.1
> TYPE=EX-10.2     DESCRIPTION=EX-10.2
> ```
>
> Le due frasi vivono solo nell'indice degli exhibit **dentro il corpo** del
> Form 10. La pipeline non legge corpi: si ferma al numero dell'exhibit, e le
> due frasi sono misurate una volta sola da
> [`tools/audit_spinoff_net.py`](tools/audit_spinoff_net.py), che **non decide
> niente** — misura la precisione della rete e basta.

### L'ancora

| | |
|---|---|
| `date_distribution` | **primo giorno con prezzo regular-way** per il ticker della figlia |
| condizione | **nessun prezzo per quel ticker nei 365 giorni prima** del deposito del Form 10 |
| se c'è | la figlia cade con motivo **`pre-existing price history`** |

Un prezzo prima della registrazione significa che quel CIK era già quotato —
OTC, uplisting, reverse merger — e non è una figlia appena distribuita.

> **Limite dichiarato e accettato**: si perdono gli spin-off di società già
> parzialmente quotate (carve-out IPO seguito da distribuzione). Non sono
> *orphan stock* e non sono il terreno che questa feature cerca.

**Il burst di Form 3 NON è più l'ancora.** È `date_imminent`: il segnale che una
distribuzione sta arrivando. La Section 16 obbliga gli insider a depositare il
Form 3 all'efficacia della registrazione, e **l'efficacia precede la
distribuzione di 2-4 settimane** — misurato: mediana +10 giorni fra burst e
primo prezzo, p25 +5, p75 +20, su 101 figlie. Le figlie fra burst e
distribuzione compaiono in `_watch.md` nella sezione «in arrivo».

*(Correzione: una versione precedente di questo file diceva che
`date_distribution` poteva **ritardare** fino a 10 giorni sulla distribuzione,
per via del termine di 10 giorni del Form 3. Il verso era sbagliato — il Form 3
arriva prima, non dopo — e comunque l'ancora adesso è il prezzo, non il burst.)*

### La capitalizzazione alla distribuzione

| | |
|---|---|
| `cap_at_distribution` | azioni dalla **copertina del primo 10-Q o 10-K** della figlia (`dei:EntityCommonStockSharesOutstanding`, primo deposito successivo alla distribuzione) **×** prezzo del giorno di distribuzione |
| fascia | `cap_bucket(cap_at_distribution)` — vedi §6 |
| `universe` | `True` se `cap_at_distribution < 2e9` |

Le figlie sopra i 2 miliardi **restano nell'indice** con `universe: False`: il
terreno è un fatto su di loro, e il tetto è una scelta sulla lista generale. Le
due domande restano separabili.

> **Il tetto non taglia il terreno.** L'incrocio Form 4 × figlie in finestra gira
> su **tutte** le figlie dell'indice, senza tetto di capitalizzazione: il tetto
> vive solo sulla lista generale. Una figlia di fascia `mid` era tagliata da
> `scan.py` prima del join, e `_watch.md` diceva «no» su un acquisto che stava
> dentro entrambe le finestre.

### Provenienza delle soglie

I **90 giorni** vengono dalla letteratura, non da qui:
Allen (2001) e uno studio del 2019 sul tono del prospetto (nessuno dei due è in
`docs/bibliography.md`), che colloca l'85,5% delle operazioni open-market nei primi
tre mesi. I **365 giorni** del test sul prezzo preesistente sono una regola di forma
dichiarata: un anno di quotazione prima della registrazione non è un residuo di
when-issued trading.

## 6. Fasce di capitalizzazione — una definizione, ovunque

**`cap_bucket(cap)`** — [flags.py](form4_scanner/flags.py). È **l'unico punto
del codice che confronta una capitalizzazione con un numero.**

| fascia | da | a |
|---|---:|---:|
| `nano` | 0 | 50e6 |
| `micro` | 50e6 | 300e6 |
| `small` | 300e6 | 2e9 |
| `mid` | 2e9 | 10e9 |
| `large` | 10e9 | 200e9 |
| `mega` | 200e9 | ∞ |
| `unknown` | — | capitalizzazione assente, `NaN`, o negativa |

**Confini inclusivi a sinistra**: 300e6 è `small`, non `micro`. `unknown` non è
zero e non è una fascia bassa: è l'assenza del dato, e resta distinguibile da
una capitalizzazione verificata.

Dove si usa:

| | |
|---|---|
| figlie spin-off | `cap_bucket(cap_at_distribution)`, sostituisce `stratum`; in `_watch.md` la colonna si chiama «fascia» |
| observations | su ogni emittente valutato, accanto alla capitalizzazione grezza |
| lista giornaliera | l'universo è espresso come insieme di fasce, derivato da `bands_for_range(min_cap, max_cap)` |
| funnel spin-off | conteggio per fascia |

> **Una discrepanza dichiarata.** L'universo giornaliero è stato descritto come
> `{nano, micro, small}`, ma il filtro in vigore è `min_cap = 50e6`, che
> **esclude** `nano`: le fasce effettive sono `{micro, small}`. Il report le
> deriva da `min_cap`/`max_cap` invece di nominarle, quindi dice il vero
> qualunque cosa sia in vigore. Abbassare `min_cap` a 0 farebbe entrare `nano`
> ed è una decisione, non un rinominamento.

## 7. Predicato diluizione — implementato, disattivato finché non è validato

**`dilution.py`**. Predicato, non validato. **Il veto è spento per default:** il verdetto si
calcola sempre e compare come flag («veto off»), ma `Card.blocked` è vero, e il nome fermato,
solo con `EDGE_LAB_DILUTION_VETO=1` nell'ambiente (`dilution.veto_attivo`). È l'unico predicato
che può impostare `blocked`. Le soglie qui sotto vengono da
osservazioni dal vivo e dalla forma dei depositi (sotto), non da una misura sul
corpus. Verdetto `BLOCKED` se una qualsiasi:

| condizione | soglia |
|---|---|
| un 424B/S-3 takedown depositato **dopo** l'ultimo acquisto | entro **75 giorni** |
| un takedown prezzato **prima** dell'acquisto | entro **5 giorni** |
| crescita delle azioni in circolazione su 1 anno | **≥ 25%** |

`CAUTION` sopra il **10%** di crescita. **`UNKNOWN` quando il dato manca, mai
`CLEAR`**: un pass silenzioso qui è il modo di sbagliare che costa di più.

Le due finestre asimmetriche non sono simmetria mancata: dopo l'acquisto è la
trappola (l'acquisto fa da marketing al collocamento), prima è partecipazione al
collocamento stesso — stesso form, stesso lato, significato opposto, e solo il
ritardo li separa. Osservato dal vivo su BRVE e ATTO, 424B4 il giorno prima,
ogni compratore riempito allo stesso identico prezzo.

## 8. Predicati di segno — NON in pipeline, non validati

**`tools/sign_gates_count.py`**. Predicati, non validati. Non girano nella pipeline dello scanner: sono uno strumento di
conteggio, e il replay storico di `tools/backfill_gates.py` è descrittivo (niente
pre-registrazione, niente controllo appaiato).

| predicato | regola | stato |
|---|---|---|
| `NO_EBITDA_WITH_NET_DEBT` | net debt > 0 **e** EBITDA ≤ 0 | conteggiato, non in pipeline |
| `NEGATIVE_EQUITY_LEVERED` | equity < 0 **e** net debt / EBITDA > 4,0 | advisory, conteggiato, non in pipeline |

## 9. Flag di contesto — non entrano in nessun punteggio

[flags.py:221](form4_scanner/flags.py#L221) e
[flags.py:264](form4_scanner/flags.py#L264). Ognuno è un fatto e nessuno somma
niente.

| flag | che cosa dice |
|---|---|
| fascia di capitalizzazione | `market cap $X` sopra 10B o sotto 50M, e basta |
| `survivability` | da cassa, debito e free cash flow dello snapshot |
| depository institution | il SIC, e la qualità dell'attivo se verificabile |
| BDC / REIT a gestione esterna | il tipo di veicolo |

### Le tre glosse riscritte come campi

Erano interpretazioni. Adesso sono i campi da cui l'interpretazione si
ricavava, che è ciò che il vincolo in `CLAUDE.md` chiede.

**Compratore routine.** Era «historically no signal», cioè un giudizio senza
misura citata. Adesso il flag dice solo il fatto: il compratore è `routine`
secondo la classificazione di Cohen, Malloy e Pomorski
([classify.py](form4_scanner/classify.py)). Nessun effetto è affermato.

**10% owner.** Era «fund accumulation», che leggeva l'intenzione del compratore
da una casella. Adesso: la casella (`isTenPercentOwner`), se il nome è
un'**entità** secondo la regola sotto, e **quanti dei suoi acquisti cadono in
una finestra di 30 giorni** (`max_window_count`, stessa forma di
`max_window_buyers` ma conta transazioni).

> **Regola dell'entità** — `looks_like_entity`, [flags.py](form4_scanner/flags.py).
> Il Form 4 non ha un campo che distingua persona fisica da entità: la
> distinzione viene dal nome. Un nome è entità se contiene uno di
> `LLC, L.L.C, LP, L.P, INC, CORP, LTD, PLC, TRUST, FUND, PARTNERS, CAPITAL,
> MANAGEMENT, ADVISORS, ADVISERS, HOLDINGS, GROUP, ASSOCIATES, VENTURES, GP,
> & CO`. Un nome che non ne contiene nessuno **non viene chiamato persona**:
> viene solo non chiamato entità. È la lettura fail-closed.

**Prezzo di riempimento identico.** Era «offering price, not open market», cioè
la conclusione. Adesso: il codice della transazione (`open_market_buys` ammette
solo `P`), quante transazioni hanno esattamente lo stesso prezzo, e il prezzo
dello snapshot con l'ora in cui è stato preso.

> **Il prezzo di mercato del giorno della transazione non c'è.** Sul percorso
> live `MarketSnapshot` porta una quotazione spot, non una serie storica — non
> esiste un campo con il prezzo alla data dell'acquisto, e il flag non lo
> afferma. Il confronto prezzo-di-riempimento contro prezzo-del-giorno diventa
> possibile solo estendendo il percorso live a una serie giornaliera, che oggi
> esiste solo nel panel di backfill.

## 10. Il registro dei verdetti — input umano, non output

`data/verdicts.jsonl`, append-only. **Il verdetto è dell'operatore.** Lo scanner ha
due diritti su questo file e nessun altro:

| può | non può |
|---|---|
| scriverlo quando glielo si detta, dalla CLI | scriverlo da solo, in una run |
| misurarlo nel mensile | aggiornarlo, interpretarlo, dedurlo |

Sta in `data/` e non in `state/` perché `state/` si può azzerare. Questo no: non
si ricostruisce da EDGAR, perché non viene da EDGAR. Il file non fa parte del
repository (è in `.gitignore`): ogni operatore ha il suo, e senza file il
registro è vuoto.

```
form4 verdict add --ticker AAA --verdict HOLD --thesis "..."                   --invalidation "..." [--upgrade-trigger ...] ...
form4 verdict list
```

**Nessun default su `verdict`, `thesis`, `invalidation`**: se mancano, la CLI
rifiuta. Un verdetto senza tesi e senza condizione di smentita è un'opinione, e
lo scanner non ne inventa una.

Un cambio di verdetto è una **riga nuova** con `supersedes` che punta all'id
della precedente sullo stesso CIK. Mai una modifica: la storia dei ripensamenti
è metà del valore del registro.

### Che cosa misura il mensile

`reports/verdicts_YYYY-MM.md`, una riga per verdetto in vigore: giorni
trascorsi, prezzo di allora, prezzo di ora, rendimento, eccesso contro il
benchmark, invalidazione scattata, revisione scaduta. Aggregato per classe: n,
mediana dell'eccesso, quante invalidazioni sono scattate. **Nessun commento.**

> **Il benchmark, dichiarato.** *EW sub-2e9* = media semplice dei rendimenti,
> sullo stesso intervallo, degli emittenti dell'ultimo file di observations con
> data ≤ quella del verdetto la cui `cap_bucket` sta in `{micro, small}` e per i
> quali il panel prezzi copre entrambi gli estremi. Sotto i 20 membri la
> funzione restituisce `None` invece di un numero costruito su mezzo paniere.

> **Le invalidazioni le verifica solo dove sono un confronto fra un prezzo e un
> numero.** «close below 18.50» sì. «close below 18.50 **without news**» **no**:
> è una congiunzione, e chiudere la prima metà ignorando la seconda sarebbe lo
> scanner che decide al posto dell'operatore che «senza notizie» vale. In quel caso
> riporta il fatto sul prezzo *e* la parte che resta da verificare a mano, senza
> dichiarare l'invalidazione scattata. «Q3 segment growth < 7%» non è una domanda
> che un file di prezzi possa chiudere, ed è marcata non verificabile.

## Che cosa NON c'è, e non deve rientrare

Il rubric a 11 punti è stato rimosso perché sette criteri di merito erano stati
scelti a intuito, uno solo è stato misurato, ed è risultato di segno invertito.
Non rientrano senza una misura sul corpus e il
consenso esplicito dell'utente:

- pesi diversi da 1 su un criterio
- una soglia di passaggio su `score_v3`
- criteri di merito su dimensione dell'acquisto, drawdown, copertura degli
  analisti, sovrapposizione con una watchlist — tutti misurati e piatti
- qualunque aggettivo in un report che non sia riconducibile a una riga qui
  sopra
