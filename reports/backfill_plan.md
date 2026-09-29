# Backfill storico — piano e stime

Scritto prima di iniziare, come richiesto. I numeri di volume sono **misurati**,
non estrapolati: ho scaricato cinque indici trimestrali reali e contato.

---

## Volume misurato

| trimestre | righe Form 4 | |
|---|---:|---|
| 2015Q1 | 135.156 | |
| 2018Q1 | 127.245 | |
| 2021Q1 | 136.682 | |
| 2024Q1 | 128.580 | |
| 2026Q1 | 117.989 | |
| **media** | **~129.000** | ~66.000 accession distinte dopo dedup |

Il rapporto di dedup è 0,49: metà delle righe del master index sono co-firmatari
dello stesso filing.

**47 trimestri × 66.000 = ~3,1 milioni di filing.**

## Perché il percorso XML è stato scartato

A 6,7 req/s sono **128 ore**. `ownership_xml()` costa due richieste per filing
(`index.json` più l'XML), quindi 6,2 milioni di richieste. Anche passando per il
path `.txt` del full-index — una richiesta sola, XML inline — restano 128 ore.

La domanda è scritta in [backfill_open_questions.md](backfill_open_questions.md)
Q1 e la strada presa è quella conservativa: **SEC bulk insider datasets**,
45 download per 2015q1–2026q1, ~500 MB, verificati disponibili.

`parse.py` **non è stato riscritto**: `_PLAN_RE` è importato e usato per
l'esclusione 10b5-1, e `tools/backfill_validate.py` rigioca un campione
attraverso `parse_ownership_xml()` + `open_market_buys()` per misurare la
divergenza fra i due percorsi invece di darla per trascurabile.

**Copertura effettiva: 2015Q1 → 2026Q1.** 2026Q2 e Q3 non sono ancora pubblicati
dalla SEC. Non contribuirebbero comunque alla Fase 4: non hanno un rendimento
forward a 12 mesi.

## Stime per fase

| fase | costo dominante | stima |
|---|---|---|
| 1 — acquisizione | 45 download + parsing | **~30 minuti** |
| 2 — replay scoring | XBRL point-in-time per emittente | ore, dipende dai CIK distinti |
| 3 — esiti forward | prezzi yfinance per ticker | ore, un ticker per richiesta |
| 4 — analisi | locale | minuti |

La Fase 1 costa trenta minuti invece di cinque giorni. È il senso della scelta.

## Il limite principale, dichiarato in anticipo

**Due componenti su sette non sono ricostruibili point-in-time** e non vengono
inventati:

- `coverage` — yfinance dà `analyst_count` solo al valore corrente
- `specialist_overlap` — la watchlist storica non esiste

Ogni osservazione porta `partial_rubric: true`, `missing_components`, e due
punteggi: `score_partial` (i 5 ricostruibili) e `score_max_possible`.

`score_max_possible` è sempre `score_partial + 3`, perché i due mancanti valgono
al massimo 1 e 2. Essendo una costante additiva **ordina i nomi esattamente come
`score_partial`**: i bucket della Fase 4 usano `score_partial`. Vedi Q2 nelle
domande aperte.

## Cosa NON produce questo lavoro

Nessuna soglia, nessun peso nuovo, nessuna raccomandazione, nessun giudizio sul
fatto che il rubric funzioni. Tabelle e distribuzioni.

E nessun test di significatività: le osservazioni sono **sovrapposte** — lo stesso
cluster genera una riga ogni lunedì per tutta la finestra — quindi gli N sono
gonfiati e le righe non sono indipendenti. La Fase 4 lo scrive nei limiti.
