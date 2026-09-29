# ADR 003 — Prova della fase 0: scelte fatte durante l'esecuzione

**Data:** 2026-09-17 · **Stato:** accettata

## Contesto

La direttiva chiede la fase 0 col piano gratuito (20 chiamate al giorno). Esito completo nel resoconto della fase 0, non pubblicato in questo repository perchÃ© riporta misure per singolo titolo su dati EODHD.

## Decisioni e motivi

1. **Tetto di 20 chiamate imposto dallo script**, anche se la chiave è di un abbonamento a pagamento (scoperto al primo
   passo, endpoint `user`). La prova resta quella chiesta; le chiamate usate sono 8 per il fornitore.
2. **Prezzi di riferimento dai depositi SEC dei fondi iShares** (valore / azioni di IWM e IWB), non da Yahoo: sono
   indipendenti dal fornitore da provare e da quello da sostituire. Ricalcolati dai file del backtest Russell e scritti
   nello script come costanti con la fonte.
3. **Codici scelti a mano per due società, con il motivo scritto nello script.** Papa Murphy's non ha il nome nella lista
   (nome = «FRSH»): scelto `FRSH_old` per ISIN e ticker; Stein Mart ha due codici (`SMRT_old`, `SMRTQ`): scaricati tutti
   e due. L'identità la decidono i prezzi, non la scelta.
4. **`user` non addebitato**: registrato comunque nel registro locale con costo 1 (stima prudente); il confronto col
   fornitore lo mostra (10 contro 8).
5. **Livello grezzo mai sovrascritto**: la seconda lettura di `user` nello stesso giorno avrebbe riscritto il file.
   Corretto: un nuovo scaricamento crea `__2`, `__3`; test in `tests/test_raw.py`.
6. La risposta di `user` contiene nome ed email dell'account: resta solo nel livello grezzo locale, mai a schermo né
   nei documenti.
