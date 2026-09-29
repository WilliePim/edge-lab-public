# 4 · Come nascono i rapporti del giorno

> Il rapporto separa le società nuove da quelle già viste e arricchisce solo le nuove. Mette in cima i nomi
> sorvegliati a mano. Poi scrive, oltre al rapporto del giorno, quello sugli spin-off e quello sui verdetti del mese.

<!-- diagramma: 04-rapporto-giornaliero.mmd -->
**[▶  Apri il diagramma nell'editor Mermaid](https://mermaid.live/edit#pako:eNp9VkuOGzcQvQqhLJwAGsTz0cgWkjHmI80iEy9GwSwCbagW1SqEzephk4o9hoEcIgfIMoAPkIV345vkJHnF7p7WZ5yNPqwiWfXq1WN96GW8ML2R6h0cHMxcoGDNSF1yYZTTVcaOFSmvy5J9ILUwVuXE3vHMwbakfDRzSoWVKbBrrivz9PdOe9Jza6rkodSSXZjSA9xmvcNB-W7Wq9d1Fthf_JbL-jfj8eRoMtk2sV8Yn6ynx6enk8Mt6y_mXbhky7XD4fjw4uSidXAcDA7uzJPx5PhyuGVOh3ceV6-Hw5enrUdFudO2s54MB4PT19vW7QBeTg6HR-e1R2Xuo3GZafIvyHv25xJ0NVJLbWus4Lfi36eN79tYzI3Yg48wp5K051yRzr0u6k2lRjkyKrUL6lrpSl2T533TrZhu6-o9Y75LZpNTFTyrtQEYIdC-31T8puzXJrek3YPed7kRlzHO0QEZGnVz8_Mz54wv00njy33buVjOXVh5Linbt1-JfULWqCqqBYGaM1d7eZMF5fP5t0fHr_rq6OQIH4PBd7XxLaqsGKmp6_7VSB2qx3_U5YrUl7-Vi7xmxXneZHx9cHZ2O1LgdWVQWiVXcUYmfPlLrbWNQYemZLfwvBup-6gtPcEGZ2kWp9aUA4E3tesdXHGvNXluFFkE26C9MLSD-O2mq31hLKpe-y1MyRXhipwQS8EJZtpNELFLSkb9KDkobQuDgKJrt7MqNO7E9fzD3H9_5qk0IQbxxxe-kbC2wZtk3cx-bjnLkD16xoH3TQSuYZRxi_1SDAZSiiE-jofPl-IolQKt44D14ydTUFURO_P4uY-bLaOB0OOZqbQy9UKJrQgrJdlogA1APBjvY027qjQucF9ZmnsDAQJpKqzgXpWtSAOcQrsMfGoOqHFvC1_Hso4cJKJ___jz8XOTom2D4W6fZS5TTJw76sCS8HTn1Vb2puaLEM--iDZQgbzanEFopR_wi95s77zBTrQLgjM-0-1OQOEZqSJnJPbq4CeUGJ2pkpHU4ORlrdL0lcOqDOKM48DHBWexEMwAMuLwFLT0uOCcuk_FQHbnHEHdUwVSAadESbA-09nKbPvVd9a5e4oopNXdxkrbtQ47SCWgSy_grNnuWtskzkdSTbNAR-HeoqRE-Ai2VwgCe3k-t5TrwPv7z58CauMIQp7o9dduA1dTrFvR5948POwGL42wlzyYFahkKXFXb4kXx1URDF0uaaHnQBns6afe47KMIPPjp_QAVxnFwC0Vty7a_rEnh6eihMfSiF-Rw2PpwU1hT3LjGCSqMgM2KS0Nw51ATZNAQsAswm9cMRV0ciWdsPtQTFviSW9syBk3Czq7j5CllvzTBnSwFEjj9bO2kb4kzBba11faOWlTqo_Y08I-AgWVpOUyBvPWUmh5BRHhGnzXoIuUM9dpqGkmHK7xp25B5K7KPPYg7yK6-2j-D_EkeIL44OR5xE8S4jgwUW5L-J-u3JyyNuxNxpnMZqLipDagbB-F_fesyySKRlQluQNeLpWGdO08PZuV6xxNgko6a6GT3mHsE4lIj0xTuedvhLBU8mJvvnVpG6HH0T8kdOkC3sdhY5uAUph2aLpuAsabzDX_GmHMMQf165dCy4hHSwjdRsV6fdUrjMdLuJCh98Osl6bVWU_mtzTA9j6Kj0bLTd-7rFfPYliJ5QJPYDOFdcueY77qNRMd_mNY-ZW5dfj4H5vzt2A)**

## Cosa racconta

Qui conta l'ordine delle letture e delle scritture, per questo il diagramma è una sequenza. I quattro riquadri
colorati sono le quattro fasi. La colonna «emissione», riempita da un modello di Anthropic, è facoltativa e non cambia
mai il giudizio né l'ordine.

## Passo per passo

1. **Chi è nuovo oggi.** Nuova è una società con almeno un deposito mai mostrato prima. Le società bloccate non si
   mostrano: succede solo col veto sulla diluizione acceso, che per default è spento (implementato, disattivato
   finché non è validato).
2. **Colonna «emissione».** Si calcola solo per le società nuove e solo se l'interruttore è acceso. Per ognuna si
   prende l'ultimo prospetto o 8-K degli ultimi 540 giorni e si chiede al modello il tipo di emissione. La risposta si
   conserva e si riusa. Se l'affidabilità è bassa, la colonna dice «sconosciuto».
3. **Sorveglianza.** Per i nomi scelti a mano si cercano nuovi depositi o nuovi acquisti, e si segnala solo ciò che
   non era già stato segnalato. Un errore qui diventa una riga del rapporto, non un giro fallito.
4. **Scrittura.** Nell'ordine:
   - il rapporto del giorno, e i depositi mostrati si annotano come visti;
   - gli spin-off aperti;
   - i verdetti del mese, con i prezzi di oggi;
   - lo stato dell'ultimo giro, che legge la notifica.

## Dove sta nel codice

| passo | file e funzione |
|---|---|
| nuove e ripetute | `form4_scanner/report.py` → `write_daily` (riga 307), `load_seen`, `record_seen` |
| colonna «emissione» | `report.py` → `issuance_column` (riga 173); `edgar_llm/extract.py` → `latest_issuance`, `extract_filing`, `render` |
| sorveglianza | `report.py` → `_righe_sorveglianza`; `form4_scanner/watch.py`; `config/watch.json` (modello in `config/watch.example.json`) |
| spin-off | `report.py` → `write_spinoff_watch` (riga 552), `write_daughter` (riga 474) |
| verdetti del mese | `form4_scanner/verdicts.py` → `current`; `report.py` → `ew_sub2e9_return`, `write_verdict_report` |
| stato del giro | `form4_scanner/lastrun.py` → `write` |

## Note

- **«sconosciuto» o «—».** `requirements.txt` dice che senza la libreria di Anthropic la colonna «reads UNKNOWN». In
  realtà mostra «—». «UNKNOWN» compare solo quando l'estrazione è avvenuta ma è poco affidabile.
- **Quattro rapporti, non due.** I commenti di `report.py` e `cli.py` parlano di «due file». I rapporti scritti sono
  quattro: giornaliero, sorveglianza spin-off, schede delle figlie, verdetti.
- **Docstring non aggiornata.** La descrizione di un parametro di `write_verdict_report` non corrisponde più a quello
  che `cli.py` gli passa.
- **Interruttore della colonna LLM.** Sta nel file `.env` (`EDGAR_LLM_DAILY`); senza, la colonna resta vuota.
