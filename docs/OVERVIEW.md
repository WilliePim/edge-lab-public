# edge-lab: lo scanner Form 4 — sintesi

Versione in inglese, per chi arriva da fuori: [README.md](../README.md). Qui c'è il
razionale, in italiano, e la cronaca di cosa ha rotto la pipeline e come.

## Cosa fa, in breve

È un **filtro** sugli acquisti insider depositati alla SEC (Form 4), non uno screener.
Il valore sta in quello che butta via: grant, esercizi di opzioni, ritenute fiscali,
piani 10b5-1 e acquisti di calendario — cioè il ~90% di ciò che i siti retail
chiamano «insider buying». Quel che resta arriva a un umano con quattro booleani e le
prove sotto.

Tre passaggi fanno il lavoro vero:

1. **Acquisto genuino** (`parse.py`) — solo codice `P`, acquisito, non derivato, non
   10b5-1, sopra una soglia in dollari. Un grant non è una scommessa: all'insider non
   è costato niente.

2. **Veto diluizione** (`dilution.py`) — la trappola è l'insider che compra $200k una
   settimana prima di un collocamento da $50M. È un Form 4 vero, codice P vero, soldi
   veri: passa ogni altro filtro. Conta **l'ordine**: un 424B5 *dopo* l'acquisto
   significa che l'acquisto era marketing per il deal → `BLOCKED`; *prima*, l'insider
   sta entrando sul prezzo scontato post-deal → solo una nota. Ed è un veto, non una
   penalità: una penalità la si assorbe, un veto no.
   È un predicato definito a priori nello scanner, **non un filtro validato**: nessuno
   studio in questo repo ha misurato che migliori i rendimenti. **Implementato, disattivato
   finché non è validato:** per default (`EDGE_LAB_DILUTION_VETO` non acceso) il verdetto
   si calcola e compare come flag, ma nessun nome è fermato né nascosto dai rapporti.

3. **Routine contro opportunistico** (`classify.py`, da Cohen–Malloy–Pomorski) — chi
   compra ogni anno nello stesso mese sta eseguendo un calendario, non un giudizio: i
   suoi acquisti non contengono informazione. Il classificatore cammina lo storico del
   CIK *dell'insider*, non dell'emittente, perché l'essere routinario è una proprietà
   della persona.

Quel che resta viene **ordinato**, non promosso: `score_v3` conta quattro booleani di
peso 1 e non ha soglia di superamento, perché nessuna soglia è stata misurata. Il
rubric a 12 punti che c'era prima è stato misurato e cancellato: nessuno dei suoi
criteri aveva una misura che giustificasse il peso che riceveva.

## Pipeline

```
daily-index EDGAR → XML Form 4 → filtro acquisti → cluster per emittente
   → gate market cap → predicato diluizione (veto spento per default) → classificazione insider
   → quattro booleani → CSV + rapporto + archivio
```

| modulo | ruolo |
|---|---|
| `edgar.py` | client SEC: ~7 richieste al secondo, cache su disco compressa, User-Agent obbligatorio |
| `parse.py` | XML ownership → `Transaction`; filing congiunti, `<value>` opzionali, righe derivate |
| `cluster.py` | raggruppa per emittente, unisce i co-firmatari, finestra mobile di 30 giorni |
| `dilution.py` | veto shelf / takedown / crescita azioni |
| `classify.py` | routine / opportunistic / novel / sparse / unseasoned |
| `flags.py` | `score_v3` e i flag di contesto; la `Card` |
| `bank.py`, `vehicle.py` | qualità dell'attivo delle banche; BDC/REIT e sponsor comuni |
| `observations.py` | archivio append-only di ogni emittente valutato |
| `report.py` | i due file che legge un umano |
| `scan.py`, `cli.py` | orchestrazione ed entrypoint |

## Uso

```bash
./smoke.sh "Nome tua@email.com"   # un paio di giorni, soglia alta — check connettività
./run.sh   "Nome tua@email.com"   # la scansione
./test.sh                          # suite offline, nessuna rete
```

Il primo giro è lento — misurato: ~85 minuti a freddo su 30 giorni, ~6 a caldo. Quasi
tutto è la camminata a 3 anni di storico per ogni insider. Non è bloccato: sta
rispettando il limite di richieste della SEC.

Su Windows i comandi vanno lanciati con `.venv/Scripts/python.exe`: gli script `.sh`
cercano il layout POSIX, e `venv.sh` risolve l'interprete per entrambi.

## Tre difetti trovati dalla prima prova dal vivo — corretti

**1. I filing congiunti moltiplicano i valori.** `parse.py` emette una `Transaction`
per *ogni coppia* (operazione × reporting owner). Corretto per l'attribuzione,
sbagliato per ogni aggregato a valle. Caso reale, accession `0001193125-26-340528`:
2 operazioni vere (1.920.000 + 1.680.000 azioni a $18 = **$64,8M**) × 4 entità
affiliate = 8 Transaction, **$259,2M**. Esattamente 4 volte gonfiato. Stesso errore
sul conteggio dei compratori: 4 veicoli della stessa gestione contavano come 4
decisioni.
*Correzione:* `parse.py` numera le righe (`txn_index`), così `(accession, txn_index)`
identifica l'operazione economica a prescindere da chi la firma;
`cluster.economic_txns` deduplica prima di sommare; `buyer_groups` fonde con union-find
gli owner che co-firmano, ed essendo transitivo chi firma da solo in un filing e in
gruppo in un altro conta comunque una volta.

**2. Le allocazioni in IPO passavano come acquisti di mercato.** Due casi: prezzo
**identico** per tutti i compratori nello stesso giorno ($18,00 e $17,00 — un prezzo
tondo e uniforme è il prezzo del collocamento, non un eseguito di mercato), 424B4 il
giorno prima, primo filing dell'emittente pochi mesi prima. Il gate li marcava
`CAUTION` con la nota «potrebbe entrare sul prezzo post-deal»: qui è esattamente il
contrario, stanno comprando *dentro* il deal.
*Correzione:* finestra di partecipazione, speculare a quella della trappola. Un
takedown entro **5 giorni prima** dell'acquisto ⇒ `BLOCKED`. Oltre i 5 giorni resta la
lettura favorevole. In più `cluster.uniform_price` segnala, su prova indipendente da
EDGAR, quando tutti i compratori sono riempiti allo stesso centesimo.

**3. `NOVEL` finiva a CIK appena creati.** Quattro veicoli prendevano il credito del
«primo acquisto dopo tre anni» con CIK registrato cinque giorni prima dell'acquisto.
L'etichetta vuole dire «un veterano rompe un silenzio»; lì significava solo «non
esisteva».
*Correzione:* `UNSEASONED`, etichetta a parte. `first_filing_date()` legge la data dal
JSON submissions già in cache: zero richieste in più. Se la data non è nota **non** si
declassa — in assenza di prove non si inventa una penalità.

Dopo le correzioni, lo stesso giorno: da 5 emittenti ordinati e 1 vetato a 3 ordinati e
3 vetati, e i due casi IPO bloccati con la ragione scritta. Che non passi più niente è
il risultato giusto: quel giorno non restava niente da mostrare.

## Limiti dichiarati

La finestra di 60 giorni è un tetto, non un filtro: quel che resta fuori non si
recupera · `score_v3` ordina e non classifica, perché la soglia non è misurata ·
yfinance è dato scrapato · il veto diluizione non vede deal negoziati ma non ancora
depositati · il 10b5-1 si rileva dalla casella solo dopo le modifiche di dicembre 2022,
prima serve il ripiego sulle note · il percorso live filtra i fatti XBRL su `end` e non
su `filed`, quindi non è point-in-time (lo è il percorso di backfill) · **è un filtro,
non una tesi**.
