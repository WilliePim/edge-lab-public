# 7 · I dati che lo scanner conserva

> Nessun database: solo file su disco. Le «tabelle» qui sotto sono file JSONL, JSON e CSV, e si collegano per valore:
> il codice della società, il codice del deposito, il giorno del giro.

<!-- diagramma: 07-modello-dei-dati.mmd -->
**[▶  Apri il diagramma nell'editor Mermaid](https://mermaid.live/edit#pako:eNqNV81y2zYQfhWMeujFnolrJ219k23Kw4ljpqKiQ0YzHIhYUahJgAFA-U9-lx576Kmv4BfrAiRFiqTs-iKT3AUW3-5-3-J5FEsGo3MyOj4-XgjDTQrnxCeMGk7iNZBUEh1TIUCRWAoNakMXAv9b8eR8IQgxa8jQY0k17B7nVHG6TEE7C0JWUpiQP6HZYnRylj8sRuX7XPGMqsdLmUplv_3keZNfJpPO5wupGKjG6NPpp0-Tk47RDB5MY3LinVycXdQmKRfQcj_79ey33TcDyvD9GK683yde_Z0ao_iyMHBB47tEyUIwZxow5qwnHyenTcSHrL0NiM7iDm5QV5wmimalexhc-t5sTLbb42P5TIIw9Kbz8Xc_uPWIdX_9m2xoWhhqKOGi3rTjNfemV95sFjgPxWPYwAHLMJjOvesbf3z7fVyvr6XaQJJyuwWjg45bMvGtVxR-9W-DycS55sXrvwQ01gcccJp7_mVwE0Rfxrffxjde14toSITdNZbZoYCn_vU4mo0vvJubMmC0zSn6NmBc-9PgIH65kqyIYcg2RMh8DG1cw4YlS3uG2y35doN2QeRelaZU60IY2Qpib2Pn90zGl39888MqLXZ1DmIXyZX3NQj9WRCF3mUd0Z6D4rlUTUD-behfedNBU0AgizdW3jbvrjGJX4JwNh1XvmUOZCcHrSqpN5zP_bD0v6p915RYfKUx8s1jDbjG3NA9AHc1vJVV7bRqWkuNNFVwXWZyv1Key0f7p7EXRUJifucQZ9gKxAbCIE0pFnrMwbz-VW_50kp1fxFViAgpEcjXz7hYwqUS0i5EEq52x23Zy6VlSmARNaUL14YK9H_Dp6LZKOEm0ojmYrQBpbkUpVd5grYfF4bcc8HkPcb2qNFhhUyHq1l2IC5I3rb_U0tBVgVukqLtjwIDQo6nmhNKZCI4ybGUZc8Dd4CHKKMidg7V8Tk2rHiyO9mwjkiOApFJwzeyg-heM_SR5dg9eGibJQfUQGoO5oH3sVxKmZJlKuM7YGhh_4tLLrNJZzwt-JOFtIujjqWCaHPqSAkTleAh0Yl8QGzOehtsTiMUDgVYBJilQmLxaiAOIpL-XEJCdM7FsVyteoDa7ke5sq4UxQHTy3FZpelRK8AjK8HQwXLX6H0caRwjkaJnJIpsicmoEWKQS82N7J7YPIjIpXaHu-IJJbY4hlzqwr4X7WzFa27JIld0wBYLUWgaGxuUS1pZdGxv3VUqsUesrEFTlExithQfWDPO8iilS1fBSDcrjvMJs5PKUBwuV1xHJx-WH6MTx29oAmRFU90t00YA-tjeA9xF2MCqaua0EMBe_6mZBIzBGUTQ_1uv5VxFyZ7G1Gkp-0FHy-LRLmDpruwGa45Z_oHEZ3gfQSMNTa1XVGhb-RWEFSqNR3Xctoy9QXd2-42iOlYceb3miUMEhixe6AZmedc9nID79olEITe9TlSQAzVtMxQ_MEWvGYZl7I3OKJNQFzeeAtfeIJpDZ1lxpZGGAYQrNJ5JUrF-Ji3Dmm797CRqgOJYlX4GdsDGXZklJIP9Xp_xCAdRPVTvVRZaioOiwMAMBm0_8dgRCyAH4aI4ZOBPWQP1L47jysBQv64xBl1yQTecSgmwT7m9GkjhNFVTdz_I7LkULJdDq-oCpUEDA00mn0tRc_GTWsd7UO5NHIfhFDik7MS8mlpRkQZCuEOeazLPiez1Uc2vneFkgAqoiddRHcL7W3eKr8XH5cCb9iupM10PTzRdrSSiVjk5KDytcooY1-U1pUxjU1uOzHCgpnsSuSvw_fl9IK41p5uK6lrzliSiNU7ueBkVEBQCkD7a2YImTq8TsDXhlBe_PnXzs3cBODTqHZggDqn8EEqowjtwCmYF2YpMf3p4GZhz3yUg22TY1Bovhm7QJuUU0FmzHvGf35Pg95cbHZFRBiqjnNmL_vNi5G7pi5Gdpt3FffRibWhhZPgoYnxvVIETyKjIbcFUd9TmNV5skzU-Wh21zzkV36WsDV7-A1sFMbI)**

## Cosa racconta

Le entità che il giro quotidiano scrive e legge, con le chiavi e le relazioni. DEPOSITO_SEC e INSIDER non hanno un
file: esistono solo come valori dentro gli acquisti.

## Dove sta ogni tabella

| entità | file | chi lo scrive | come |
|---|---|---|---|
| GIRO, OSSERVAZIONE, ACQUISTO | `state/observations/form4/{giorno}.jsonl` | `observations.py` → `write` | si aggiunge in fondo; due giri nello stesso giorno sono due blocchi |
| SETTIMANA | `state/breadth/form4/{giorno}.jsonl` | `breadth.py` → `write_weeks` | si aggiunge; in lettura vale il giro più recente |
| DEPOSITO_GIA_MOSTRATO | `state/daily/seen.jsonl` | `report.py` → `record_seen` | si aggiunge, un deposito una volta sola |
| AVVISO_GIA_DATO | `state/watch/seen.jsonl` | `watch.py` → `record_seen` | si aggiunge; il file ancora non esiste |
| ULTIMO_GIRO | `state/daily/last_run.json` | `lastrun.py` → `write` | sovrascritto a ogni giro |
| VERDETTO | `data/verdicts.jsonl` (non incluso in questo repo; il codice tollera l'assenza) | `verdicts.py` → `add` | si aggiunge, mai modificato |
| FIGLIA_SPINOFF | `data/spinoffs_index.json` (non incluso; si ricostruisce con lo strumento) | `tools/spinoffs.py` | rifatto dallo strumento, lo scanner lo legge e basta |
| SORVEGLIANZA | `config/watch.json` (modello: `config/watch.example.json`) | a mano | solo lettura |
| VEICOLO_MANUALE | `config/vehicles.json` | a mano | solo lettura, oggi senza voci attive |
| RIGA_TABELLA | `out/scan_{giorno}.csv` | `cli.py` | sovrascritta; la legge il confronto `--compare` |

I nomi dei campi li ho controllati sui file veri, tranne `state/watch/seen.jsonl`, che non esiste ancora.

## Note

- **Il codice SEC della società non ha un formato unico.**
  - Nell'archivio e fra i depositi già mostrati è senza zeri iniziali.
  - Nei verdetti gli zeri si tolgono apposta.
  - Nella mappa dei simboli è a 10 cifre.

  Per un collegamento va normalizzato.
- **Campi sempre vuoti.** L'origine e l'ora dei dati di mercato sono sempre vuote nell'archivio, anche se il commento
  del modulo dice il contrario. Il campo «piano programmato» degli acquisti è sempre falso.
- **Docstring di `observations.py` non aggiornata.** Descrive un campo `components` che non esiste più e parla di una
  versione 2 dello schema, mentre la versione è 1.
- **Un collegamento non garantito.** Fra le righe settimanali e il giro che le ha scritte il collegamento è per giorno
  e versione del codice: è una convenzione, non una chiave garantita. È un'ipotesi.
- **File che lo scanner non usa.** `config/comp.json` è fuori dal giro quotidiano (non incluso nella versione pubblica).
- **Gli studi di ricerca hanno archivi propri,** in `state/backfill/` e in `backtest/<studio>/risultati/`.
