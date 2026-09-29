# edge-lab

Filtro sugli acquisti insider depositati alla SEC (Form 4), piu' l'infrastruttura
di ricerca che ci sta intorno. Il valore del filtro sta in cosa scarta: grant,
esercizi, ritenute, acquisti sotto piano 10b5-1.

Sfondo e razionale: [docs/OVERVIEW.md](docs/OVERVIEW.md), misure in
[reports/](reports/), regole dello scanner in [RULES.md](RULES.md).
Qui c'e' solo cio' che non cambia.

## Struttura

```
form4_scanner/
  edgar.py       client HTTP: throttle 0,15s, cache su disco, backoff 403/429/503
  parse.py       ownership XML -> Transaction; open_market_buys() e' il filtro
  cluster.py     group_by_issuer, finestra mobile, dedup co-firmatari
  classify.py    routine / opportunistic / novel / sparse (Cohen-Malloy-Pomorski)
  flags.py       Card, evaluate_cluster, score_v3. NESSUN peso: quattro
                 booleani da 1, nessuna soglia, terreno=None finche' manca
                 data/spinoffs_index.json (lo costruisce tools/spinoffs.py).
                 Il rubric a 11 punti e' stato rimosso dopo la misura
  dilution.py    predicato diluizione (S-3, 424B, conteggio azioni), non validato
  bank.py        flag sulle depository institutions
  vehicle.py     BDC/REIT a gestione esterna, link fra sponsor
  xbrl.py        strato condiviso: Metric, net_debt, ebitda, leverage
  observations.py archivio append-only di ogni emittente valutato
  breadth.py     conteggi settimanali grezzi (Fase 1)
  scan.py        orchestrazione; DEFAULT_LOOKBACK_DAYS 60, MAX_MARKET_CAP 2e9
  cli.py         entrypoint
tools/           strumenti, non pipeline: statistica (table3_regression,
                 backtest_event_time, matched_control),
                 ricostruzione point-in-time (backfill_*, fetch_missing_prices,
                 sign_gates_count), terreno spin-off
                 (spinoffs, audit_spinoff_net), notify.ps1
tests/           suite piatte, convenzione harness.check/report

edgar_llm/       estrazione strutturata dal TESTO dei filing, con un LLM.
                 Perimetro con la sua guardia: client EDGAR suo, niente CIK
                 cablati, niente path assoluti, User-Agent da env. Arricchisce e
                 non decide mai. Vive con pytest e ha le sue ADR in
                 edgar_llm/docs/adr/.
market-data/     archivio locale dei prezzi EODHD e unico punto di accesso
                 (`market_data.api`). I dati stanno fuori da ogni repo git, in
                 MARKET_DATA_DIR. Vive con pytest e ha le sue ADR in
                 market-data/docs/adr/.
```

## Comandi

```bash
./daily.sh "Nome Cognome email@dominio"   # giro giornaliero: scan + archivio
./run.sh   "Nome Cognome email@dominio"   # scan e basta
./test.sh                                  # tutte le suite, offline
```

**edge-lab non dipende da nessun repo esterno.** Nessun import, nessun
percorso, nessun file letto, nessun lanciatore che viva fuori dal repo:
`tests/test_confine_repo.py` lo verifica sull'AST (ogni import risolve in
libreria standard, modulo del repo o dipendenza dichiarata). Il percorso
dell'archivio dati arriva solo dal `.env` (modello in `.env.example`).

## Stato su disco

| | |
|---|---|
| `state/observations/form4/` | append-only, una riga per emittente scorato |
| `state/breadth/form4/` | conteggi settimanali, riosservati a ogni run |
| `out/` | CSV delle scansioni |
| `logs/`, `.edgar_cache/` | ignorati da git |
| `state/backfill/` | corpus, panel prezzi, `sales.jsonl` — ignorati da git |
| `market-data/` | package dell'archivio prezzi; i dati stanno in `MARKET_DATA_DIR`, fuori da ogni repo |

---

# VINCOLI

**Confine fra scanner e giudizio.** Vale per tutta la v3.

Lo scanner calcola **FATTI**: booleani e numeri derivati da EDGAR per join o
conteggio, ciascuno con una regola dichiarata e riproducibile. «figlia di
spin-off distribuita il D», «acquisto insider entro 90gg da D», «>=2 gruppi di
compratori in 30gg», «director senza officer ne' 10%», «NO_EBITDA con net debt
> 0», «13D sul CIK entro +-90gg». Questi possono entrare in `score_v3`, nei
predicati, nei flag.

Lo scanner **NON produce GIUDIZI**: nessuna riga che valuti, pesi, interpreti o
raccomandi. Vietati «spin-off promettente», «vendita forzata probabile»,
«cluster convinto», «reasons credibili», «opportunita'», «attenzione», «da
approfondire», qualsiasi aggettivo di merito, e qualsiasi ordinamento che non
sia `score_v3` desc poi numero di compratori. Vietato anche l'implicito:
nessuna soglia numerica che divida «buono» da «cattivo» oltre a quelle
dichiarate in [RULES.md](RULES.md), ciascuna con la sua provenienza.

Il report per figlia — e ogni report futuro per terreno — consegna
**materiale, non conclusioni**: testo integrale delle sezioni rilevanti del
filing, numeri, date, link. Un riassunto e' una traduzione compressa, non una
valutazione: se contiene un'opinione che il testo originale non contiene, e'
sbagliato.

> **Regola di controllo:** se una frase di un report non puo' essere ricondotta
> a un campo di un filing o a una regola in [RULES.md](RULES.md), non ci sta.

**Il verdetto e' un campo di input umano.** Vive in `data/verdicts.jsonl`
(fuori dal repository, in `.gitignore`), append-only, e lo scanner ha due soli
diritti su quel file: **scriverlo quando glielo si detta** dalla CLI, campo per
campo, e **misurarlo** nel mensile `reports/verdicts_YYYY-MM.md`. Non lo scrive
mai da solo, non lo aggiorna, non lo interpreta. Un cambio di verdetto e' una
riga nuova con `supersedes`, mai una modifica. Vedi [RULES.md §10](RULES.md).

Il perche' e' il rubric v2, morto esattamente cosi': sette criteri di merito
scelti a intuito, uno solo misurato, e misurato al contrario. Ogni giudizio che
rientra nello scanner rientra senza test. **Il giudizio e' dell'utente. Lo
scanner gli da' nomi, date e testo.**

**Dipendenze:** nessuna nuova senza chiedere. Dataclass frozen + JSONL.
No pydantic, no database.
> `anthropic` e' opzionale (come yfinance — senza, lo scanner gira identico) e
> `pytest` gira **solo** su `edgar_llm/` e `market-data/`, non sulle suite
> piatte. Il divieto su pydantic resta, edgar_llm compreso: lo schema per il
> tool-use e' un dict JSON-Schema scritto a mano —
> `edgar_llm/docs/adr/002-niente-pydantic.md`.

**score_v3 (`flags.py`):** quattro booleani, peso 1, nessuna soglia. Aggiungere
un criterio, un peso o una soglia richiede prima una misura sul corpus e poi il
consenso esplicito dell'utente.

**Fail-closed:** dato mancante = UNKNOWN, mai PASS. UNKNOWN non blocca, ma deve
restare distinguibile da "verificato pulito".

**Nessuna soglia ne' peso senza misura.** Prima la distribuzione sulla
popolazione reale, poi la decisione — e la decisione e' dell'utente. Produrre
tabelle, non raccomandazioni. Un predicato che colpisce un solo settore e' un
filtro settoriale, non un predicato: controllare sempre i SIC.

**Point-in-time ovunque:** fatti XBRL filtrati su `filed <= as_of_date`, prezzi
alla data. Il lookahead invalida tutto.
> Oggi vale solo in `tools/backfill_gates.py` e `tools/backfill_dilution.py`. Il
> percorso live filtra su `end`, non su `filed` — `dilution.py:150`. La regola e'
> l'obiettivo, non lo stato.

**Tre livelli separati, mai mescolati:**
```
veto/     predicati binari, solo test di segno, nessun peso
dossier/  contesto per la lettura umana, nessun numero sommabile
flags.py  score_v3: quattro booleani, tocca solo con consenso
```
Se un predicato non puo' mai produrre FAIL, e' materiale da dossier.
> `veto/` e `dossier/` **non esistono**. I due predicati di segno vivono in
> `tools/sign_gates_count.py`, che e' uno strumento di conteggio e non gira nella
> pipeline. Il predicato diluizione e' l'unico che puo' impostare `blocked`, e solo
> col veto acceso (`EDGE_LAB_DILUTION_VETO=1`): e' implementato, disattivato finche' non
> e' validato. Nessuno dei
> tre e' validato.

**observations/** e' append-only ed e' l'unica memoria del sistema. Le
observations non si azzerano. Ogni riga porta `scanner_git_sha` e
`window_days`. `rubric_version` e' caduto con il rubric: lo schema ridotto
porta `score_v3` e i quattro booleani.

**Estrazione con LLM** (proxy, testi liberi): ogni campo con `confidence`,
`source_excerpt` e `source_url`. Sotto soglia -> review queue, mai
auto-popolamento silenzioso.
> Esiste in `edgar_llm/`. La regola e' rispettata con **una deviazione
> dichiarata**: `source_url` sta sull'evento e non sul campo, perche' i cinque
> campi escono tutti dallo stesso documento e ripeterlo direbbe che potrebbero
> venire da documenti diversi. `confidence` e `source_excerpt` sono per campo,
> e la citazione viene cercata **letteralmente nel testo inviato**: se non c'e',
> il campo scende a `low` e non e' piu' usabile.
>
> **E l'estrazione non e' un fatto ai sensi del CONFINE**, perche' non e'
> riproducibile. Per questo non tocca `blocked`, non entra in `score_v3`, non
> cambia l'ordinamento: compare in colonna con la citazione che la giustifica, e
> basta. Verificato sull'AST in `tests/test_issuance_column.py`. Farla decidere
> richiede prima una misura sul corpus e poi il consenso esplicito dell'utente —
> `edgar_llm/docs/adr/004-mai-un-cancello.md`.

**Prima di affermare come stanno le cose** nel repo o nei dati, verifica e di'
dove hai guardato. Se una decisione spetta all'utente, fermati e chiedi — non
scegliere la strada piu' comoda.

**Regola di verifica.** Ogni verifica legge lo stato reale: il contenuto del
file, l'output del comando, il task registrato. Mai un valore scritto da te
(un percorso digitato a mano, una stringa attesa ricopiata nel controllo). Nel
resoconto, per ogni verifica, di' cosa hai letto e da dove.
> Nata da un caso vero: una correzione di percorso in uno script era stata data
> per fatta controllando con `Test-Path` un percorso digitato a mano invece della
> riga del file, che non era cambiata.

---

# DELEGA AI SUB-AGENT

Never do the work yourself.
Always dispatch a sub-agent.
Don't always use Fable.
Use Opus 5 for easier tasks.

## Model routing
- Fable 5.1: architecture, hard bugs, review
- Opus 5: edits, tests, docs, refactors
- Haiku 4.5: lookups and summaries
- Pass `model` on every Agent call

## Delegation
- One sub-agent per task, plan first
- Run independent sub-agents in parallel
- Read the report, never the files
