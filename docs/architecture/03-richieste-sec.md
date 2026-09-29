# 3 · Come si chiede un documento alla SEC

> Prima si guarda la copia su disco, poi si chiede alla SEC con calma: una richiesta ogni 0,15 secondi, al massimo 3
> tentativi. Chi ha chiesto decide cosa fare se non arriva niente.

<!-- diagramma: 03-richieste-sec.mmd -->
**[▶  Apri il diagramma nell'editor Mermaid](https://mermaid.live/edit#pako:eNqFVttu4zYQ_RVCedhdwEYtybcIxRa2LkBRIE3jbRfoqg80RdtEZFIgKe82i_xLHwts_6BvyY91eJHsOCmiB8MiZ86cmTlD6mtAREWDBAXD4bDkmumaJigVe4oUQ2THaEVRy1ElSLunXAuE6xqjVZ6WnAi-Yduk5AjpHd2D3xor2r_-hiXD65oqa4HQRnC9YndgVgbhpPlSBm69ZpymohbSbFxMx7PxfNntkbpVmsrl7dZuFpMiLorzTSEr6pwXs_myWLj9TS0-kx2W2ocnrTw4iky5lQZXFeOAHI5LbtPvfdCHzNn88vZTGawouD6tQkW7MgR_vEuShHF2x4T3QcPhe5R-LYP0zePfaMse_wJnjIhoGP5-Lb97z603wWQHZW5RxRQRP5TBPQBVlDDFBKcOKwUspB7_sZC_WjIMtQqj-imeUiaCZKZjSmPEOJJUU89O3J6glQEXAySappUUAb_6DeMVIxRoILHdMotomHHBrQgEV1AAXAaWxMeSOzDVrrcSNzv0AVgVjIM0UIw0lAdrdmAQ2tmZ56MjjlVDNbDDNVRRoNEgnCBFIUDlolZWXMcsGkkJCJDbRCCPjdeXB7V8bhy0l2qnTgsH7srQ4ZVweUBKIGxaIbrHrH4J88Zi5qZ3Ym-6B85Y45ebY57cldQUGxpatbqr03UIxK6x6dVa0oPPgAswOHfWErpB-7zpAGFCoKUCcbrFWthkBDJdMCpDgpC2gfUuUtRHghZGAzQeoGlX15fCXofWbwFZ3pg6cxehb93_Z3sdOc_jyuJUoB_dOuVVJ5Iuw1bD0KwpYDnOq09vbdsUrg_4OB3wuzddU8_mpAzemUSwhBoduklbWayffzqZC1Yfp_RM_Z7LqYXVOIUTQXfErkYG7MoOFKq64hszKKe2BEFBUgrZDdextj4ArqGh3sYcFLZxVPoABcDnbs8i-ggg1Dsj_UaKA5ZeLUqLxkHbMsPIWIToGcS5eeFyCc9y8YxP7CJv-GyoM_BMdzCyBwoNcsI0xx5hlYkKld5gn97DN34M8fDvk8HPzBT86M8XsN0yISGNPeYEw1gnNnfWr8OYYm4K6ur88M2VxR1QFvqZmDNTjULIPRo_h92Lqq0tLAjNjOYL_rERjxZwWflTXQnCqIZD-ynclrWVHT9gBWUXirDW5DtAPv11DYMpzmPYYTB_rka21v5iuQq7t-4yw0pldIPcTYI2rK6Ti2WRLYt8oEBQtzS5iCbTOF8OiL0tL8I8XswXfnP4mVV6l0Rwrz7FM-ebR8tH-awoerRpPJ0WYYcWh1E-D19D688ED1lk-bTnkFxkl7PZaNpBzubxZFS8Bmnb7QkChWLUo12OF_Fyfkw3uoyXr6EZbXfc8nSRnnBLo2l05FaEWZi9hiZuu0Ysi1l2ZBZOF_F40TMbT-LoVazu6PKIaVosi7BHHGWX4_kx13icj19qbTBAwZ5KuL4q89EGJ7j91ioD8_1jP7-Ce2ODQZqrPzmBdS1buFGCtoHxpBnDMN_747IU7XYHrxtcK_PeYP67EJ3B_X_wFzyR)**

## Cosa racconta

Ogni richiesta del giro quotidiano passa da qui: indici, moduli, storia delle società e, se è accesa, la colonna
LLM. Lo stesso client lo usano anche gli strumenti e gli studi di ricerca, che ci aggiungono un contatore con un
tetto.

## Passo per passo

1. **Cache su disco.** Se c'è una copia, si usa quella. Fa eccezione l'indice di oggi, che non si conserva perché può
   ancora cambiare.
2. **Richiesta.** Si aspetta almeno 0,15 secondi dalla richiesta precedente e ci si presenta con nome ed email.
3. **Risposta.**
   - Tutto bene: si salva la copia compressa.
   - Documento inesistente: nessun dato, e non conta come errore.
   - Troppe richieste, accesso negato o servizio occupato: pausa di 2, 4, 6 secondi e nuovo tentativo.
   - Altri errori del server: nessun nuovo tentativo.
4. **Se non arriva niente**, decide chi ha chiesto:
   - un giorno senza indice si annota;
   - un modulo introvabile si salta;
   - senza la storia della società il giudizio è «sconosciuto».

## Dove sta nel codice

| passo | file e funzione |
|---|---|
| cache, pause, tentativi | `form4_scanner/edgar.py` → `EdgarClient.get` (riga 91) |
| indice del giorno | `EdgarClient.daily_master_index` (riga 146) |
| modulo Form 4 | `EdgarClient.ownership_xml` (riga 175) |
| contatore con tetto degli studi | `backtest/russell_exits/sec.py` → `Budget` |

## Note

- **Errori non ritentati.** Un errore 500 o 502 non si ritenta. Si riprova solo su 403, 429 e 503.
- **Cadute di rete non contate.** I nuovi tentativi dopo una caduta di rete non entrano nel contatore delle pause
  mostrato nel rapporto.
- **Un client che il giro non usa.** `edgar_llm` ha un client suo, con la stessa cache. Nel giro quotidiano però i
  rapporti gli passano quello dello scanner, quindi il suo si usa solo negli strumenti di `edgar_llm`.
