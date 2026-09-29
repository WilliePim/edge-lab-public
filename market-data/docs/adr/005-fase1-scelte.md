# ADR 005 — Fase 1: calendari, controllo degli split mancanti, conteggio delle chiamate, correzioni della revisione

**Data:** 2026-09-17 · **Stato:** accettata, con un punto aperto per l'utente (Iconix)

## Contesto

Decisioni dell'utente del 17 settembre: fase 1 con la chiave a pagamento; soglia dei salti al 90%; controllo nuovo degli
split mancanti con Iconix come test di accettazione; calendario delle sedute da una libreria di calendari di borsa;
identità per codice EODHD più ISIN; verifiche su dati in blocco con i delistati e su Milano, Tokyo, Hong Kong.

## Decisioni e motivi

1. **`exchange_calendars` 4.13.2** installata nell'ambiente di sviluppo (libreria indicata dall'utente). Mappa borsa →
   calendario in `quality/calendario.py`. **TSX Venture usa il calendario di Toronto** (la libreria non ne ha uno suo).
   Il calendario parte dal primo giorno della serie confrontata, o dal limite della libreria (Tokyo: 1997).
2. **Titolo liquido per borsa** scelto a mano (SPY, ERIC-B, NOKIA, NOVO-B, EQNR, HSBA, SAP, MC, ASML, ABI, EDP, NESN, SAN,
   un titolo di Vienna, RY, BHP, 0700); se manca dalla lista degli attivi, ripiego sul titolo del campione con più barre recenti,
   dichiarato nel risultato. Nessuna chiamata in blocco per il calendario.
3. **Controllo degli split mancanti, lettura della regola:**
   - ±3% **relativo** al rapporto tipico (`|r/k − 1| ≤ 3%`), con una tolleranza numerica di 1e-9 sul bordo;
   - «non torna indietro» = nessuna chiusura delle 20 sedute dopo torna verso il livello di prima oltre il punto medio in
     logaritmo; allontanarsi ancora non è un ritorno (correzione dopo la revisione);
   - «Se c'è, controlla anche il volume»: ambiguo (il volume o lo split registrato). Il volume si riporta per tutti i salti,
     anche per quelli con uno split registrato; non decide la segnalazione;
   - salti con meno di 20 sedute dopo o con chiusure mancanti: **non valutabili**, elencati a parte (dato mancante =
     sconosciuto, mai pulito).
4. **Iconix non è segnalato dalla regola letta così** (rapporto 0,1046, 4,6% da 1/10: quel giorno il titolo è salito del
   4,6% oltre la divisione per 10). Il conflitto con il test di accettazione non si risolve nel codice: il test
   `test_accettazione_iconix` è marcato «fallimento atteso» (rigoroso) e la scelta va all'utente alla fermata 2.
5. **Costo delle chiamate misurato, non solo documentato**: differenza del contatore `apiRequests` di `user` (costo 0)
   prima e dopo ogni prova. Le risposte **401, 403 e 404 non sono addebitate** (misurato: 14 risposte 403 e 6 risposte
   404, contro la documentazione che dà le 404 come addebitate): il registro locale le conta a zero, anche per le righe già
   scritte. Anche `user` costa 0 (misurato in fase 0: il contatore passa da 0 a 8 con 8 chiamate e 2 letture).
6. **Prova dei dati in blocco**: `eod-bulk-last-day/US` del 2016-06-15 contro le serie per titolo di sei società delistate
   dopo (Monsanto, Aetna, Pandora, Stein Mart, Iconix, Papa Murphy's), cercando **ogni** codice che comincia con il ticker
   di allora (correzione dopo la revisione: con due codici fissi Stein Mart risultava assente, compare come `SMRTQ`).
7. **Campioni per borsa**: 20 azioni ordinarie attive, 20 delistate, 5 ETF attivi, 5 delistati, scelti per impronta
   sha256 del codice (riproducibili, niente caso). Tetto della fase 1: 5.000 chiamate addebitate, controllato sul
   contatore del fornitore ogni 100 richieste; se il contatore non si legge, lo script si ferma.
8. **Errori definitivi e temporanei**: 401, 403, 404 si registrano e non si ripetono; rete, 429 e 5xx si ripetono alla
   prossima esecuzione (correzione dopo la revisione).
9. **`pyarrow` 25.0.1 e `duckdb` 1.5.5 installati ora** (chiesti dalla direttiva per la fase 3): servono già alla stima
   della fase 2 per misurare lo spazio vero in Parquet sui campioni.
10. **Correzioni di sicurezza dopo la revisione**: il controllo pre-commit legge anche i file UTF-16, controlla i cambi di
    tipo, blocca sottomoduli e repo annidati, legge `.env` in modo tollerante come la configurazione; l'hook è eseguibile
    anche su Linux e macOS; il client registra ogni eccezione del trasporto con la chiave oscurata e codifica il percorso
    dell'endpoint; i registri si scrivono in ASCII.
11. **Nessun prezzo di EODHD nei documenti versionati**: il resoconto della fase 0 riporta rapporti e scarti, non prezzi.
    Il commit `e1c18b0` ne conteneva alcuni; il repo di allora non ha un remote, la storia resta locale e non si riscrive.
