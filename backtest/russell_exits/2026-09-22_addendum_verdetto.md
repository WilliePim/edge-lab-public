# Addendum — 22 settembre 2026, dopo il verdetto: i cambi di ticker trattati come delisting

Scritto **dopo** aver visto il verdetto (`risultati/verdetto.md`, commit `8074120`). È una **nota descrittiva**: non
cambia regole, celle, soglie né esito. Decisione dell'utente del 22 settembre: il verdetto resta quello calcolato dal
codice congelato (`83456b7`, fermata 1 corretta in `b91d83a`), **NON REGGE in tutte e due le celle**; il difetto qui
sotto si registra e si corregge come lavoro ordinario separato, per i backtest futuri, senza rifare questo referto.

## Il difetto

`rendimenti.rendimento` riceve la serie di **un solo codice EODHD**. Quando una società cambia ticker, EODHD chiude il
codice vecchio e apre il nuovo sotto lo stesso CIK: il calcolo vede la fine della serie vecchia dentro la finestra e
tratta il titolo come delistato, con l'ultimo prezzo (esito «delistato: ultimo prezzo»). Il rendimento dopo il cambio
di ticker non entra.

Trovato nella diagnosi in sola lettura della media 2023 della cella dell'investimento (−45,1%, 9 casi), che per il
resto è fatta di esiti veri (un caso in fallimento; peer spinti dal rialzo di un singolo titolo).

## Quanto pesa

Titoli la cui ultima barra cade dentro la finestra di 252 sedute e il cui CIK ha nell'anagrafica EODHD un altro codice
con dati oltre quella data:

| cella | chi | cambio di ticker | delisting senza altro codice |
|---|---|---:|---:|
| investimento B2 × 252 | titolo | 6 | 12 |
| investimento B2 × 252 | peer | 1 | 28 |
| placebo, falsi eventi | titolo | 3 | 8 |
| placebo, falsi eventi | peer | 0 | 53 |

Nella cella dell'investimento i codici chiusi dentro la finestra sono 6, nel placebo 3. Quattro dei nove hanno il
suffisso Q: sono continuazioni fuori borsa dopo un fallimento, il titolo ha lasciato la borsa davvero, e l'ultimo prezzo
di borsa è una lettura difendibile. Gli altri cinque sono cambi di nome veri. (Copia pubblica: l'elenco dei codici è
stato tolto.)

## Sensibilità (descrittiva)

Rendimento extra dei titoli dell'investimento **seguendo la società sul codice nuovo** (ultimo prezzo del codice
vecchio, poi dal primo prezzo del codice nuovo all'uscita), con gli stessi peer; tutto il resto come nel referto.

Calcolabile per 4 dei 6 titoli dell'investimento (per gli altri 2 manca il rendimento troncato, quello seguito o la
media dei peer). (Copia pubblica: la tabella per titolo con i rendimenti troncati e seguiti è stata tolta.)

Media delle medie annuali della cella **+1,63% → +1,74%**, t **0,24 → 0,25**; 2023 da −45,1% a −46,4%. Non ricalcolati il peer con cambio di ticker e i
tre titoli del placebo: toccano al più il criterio 5, e la cella dell'investimento fallisce comunque il criterio 3
(t lontano da 2). La scheda di dicembre (A × 32) non ha delistati nella cella. **Il verdetto non cambia.**

## Cosa segue

- Il referto `risultati/verdetto.md` e `verdetto.json` restano come sono: sono il verdetto.
- La correzione (seguire il CIK fra i codici EODHD) si fa dopo, con test, come lavoro ordinario per i backtest futuri.
  Non si rilancia `analisi.py --verdetto` su questo terreno.
