# edgar-llm-extraction

Estrazione strutturata dal testo dei filing SEC, con un LLM, dentro una pipeline
che non puo' permettersi di sbagliare in silenzio.

---

## Il caso che ha motivato il modulo: ITT e SPX FLOW

Una pipeline che legge i Form 4 depositati alla SEC segnala gli acquisti degli
insider e applica un veto sulla diluizione. Il 2 settembre 2026 ha marcato ITT
Inc. con questa motivazione:

```
BLOCKED: share count +15% in 12m
```

Il numero e' giusto. La serie XBRL di ITT, tag `dei:EntityCommonStockShares-
Outstanding`, tutta da 10-K e 10-Q:

| fine periodo | depositato | forma | azioni |
|---|---|---|---:|
| 2025-10-27 | 2025-10-29 | 10-Q | 78.000.000 |
| **2026-02-06** | 2026-02-09 | **10-K** | **86.000.000** |
| 2026-05-04 | 2026-05-06 | 10-Q | 89.400.000 |

+14,6%. Il verdetto e' pero' sbagliato nel significato: quelle azioni non sono
state vendute per fare cassa, sono state **emesse come corrispettivo**
dell'acquisizione di SPX FLOW. Lo dice l'8-K depositato il 2026-03-02, item
2.01, «Completion of Acquisition or Disposition of Assets».

### Perche' l'euristica non poteva farcela

Il veto ragiona su **forma e data**: quale modulo e' stato depositato, e quanti
giorni prima o dopo l'acquisto dell'insider. Non apre il documento. Con quelle
sole informazioni, un'emissione per acquisizione e un collocamento diluitivo
sono indistinguibili — stesso aumento di azioni, spesso le stesse forme
depositate nello stesso trimestre. La distinzione sta in una frase, e la frase
sta nel testo.

Nella finestra di ITT c'erano anche due 424B5 (dicembre 2025). Una regola piu'
aggressiva li avrebbe usati per confermare la diluizione, sbagliando con piu'
sicurezza.

### Cosa fa questo modulo

Legge il documento primario, ne manda al modello le sezioni che contano, e
registra un oggetto tipizzato:

Questa e' l'uscita vera su quell'8-K, non un esempio costruito
(`pytest edgar_llm -m llm`, 6.129 token di input, 506 di output):

```json
{
  "tipo":           {"value": "M&A_issuance", "confidence": "high",
                     "source_excerpt": "ITT issued the Stock Consideration to the Seller"},
  "controparte":    {"value": "LSF11 Redwood Parent, L.P. (Seller)", "confidence": "high",
                     "source_excerpt": "by and among ITT, LSF11 Redwood Parent, L.P."},
  "importo_usd":    {"value": 700000000.0, "confidence": "medium",
                     "source_excerpt": "approximately $2.3 billion in cash and $0.7 billion in shares of ITT common stock"},
  "data_efficacia": {"value": "2026-03-02", "confidence": "high",
                     "source_excerpt": "On March 2, 2026 (the “Closing Date”), the Acquisition was consummated"},
  "source_url":     "https://www.sec.gov/Archives/edgar/data/216228/..."
}
```

Tre dettagli che dicono se il taglio del documento funziona. La **controparte**
e' il veicolo che vendeva, non l'azienda comprata: il modello ha letto chi era
la parte contrattuale. L'**importo** e' 700 milioni e non 2,3 miliardi — ha
isolato la sola quota pagata in azioni, che e' l'unica che c'entri con la
diluizione, e l'ha marcata `medium` invece di `high`, il che su una lettura del
genere e' onesto. E fra le **condizioni** compaiono i diritti di registrazione:
quelle azioni potranno essere rivendute, che e' precisamente il fatto che
interessa a chi ha appena visto `+15%`.

### Prima e dopo

| | prima | dopo |
|---|---|---|
| riga nel report | `BLOCKED — share count +15% in 12m` | `BLOCKED — share count +15% in 12m` · **`M&A_issuance (high)`** |
| per capire perche' | aprire EDGAR, cercare gli 8-K, leggere gli item | leggere la riga |
| chi decide | una persona | una persona |

**Il verdetto non cambia.** L'estrazione non e' un cancello e non ne diventera'
uno senza una misura che lo giustifichi — vedi
[ADR-004](docs/adr/004-mai-un-cancello.md). Il guadagno e' che un umano legge
meno EDGAR, non che il filtro decida meglio.

> **Also worth reading:** [PM-001 — the guard that couldn't speak](docs/postmortems/PM-001-the-silent-guard.md),
> on why detection code needs tests that prove it *fires*.

---

## Com'e' fatto

```
edgar.py     client SEC: throttle, cache su disco per hash dell'URL, backoff
filings.py   quali depositi contano; primaryDocument -> una sola richiesta
fetch.py     HTML/iXBRL -> testo, e le finestre che finiscono nel prompt
schema.py    dataclass frozen, JSON-Schema del tool, validazione
client.py    l'unico punto che parla con un modello
cache.py     sha256(testo + prompt_version + model); modi record / replay
config.py    segreti: ambiente prima, .env risalendo; mai un valore stampato
extract.py   il percorso completo, e le sue quattro uscite di guasto
goldens.py   il set etichettato a mano: accession e sha, mai il testo
label.py     CLI di etichettatura
eval.py      le metriche, per campo e per forma di deposito
```

### Il taglio del documento

Un 424B5 mediano fa 208.000 caratteri di testo; un 424B3 che veicola un
prospetto di fusione ne fa 1,7 milioni. Al modello ne vanno ~21.000: la
**testa** del documento (copertina e riassunto dell'offerta) piu' una
**finestra** attorno a ciascuna sezione riconosciuta — `Use of Proceeds`,
`Plan of Distribution`, `Item 2.01`, `Underwriting`.

Ogni salto e' marcato nel testo inviato. Il modello deve poter vedere che manca
qualcosa: altrimenti cita con sicurezza attraverso un buco.

Misure e costi: [docs/costs.md](docs/costs.md). ~5.200 token di input mediani,
**$21,60 per 1.000 filing** al listino dichiarato.

### Cosa succede quando qualcosa va storto

EDGAR non risponde · il documento non si converte in testo · l'API e' giu' · la
risposta non passa la validazione. Quattro guasti, un solo esito: un evento coi
campi vuoti e una **nota che dice quale dei quattro**. Mai un valore inventato,
mai uno zero muto. Chi chiama gira identico a prima.

---

## La validazione, che e' il pezzo che conta

Uno schema tipizzato garantisce che i campi ci siano, non che siano veri. Tre
controlli che un validatore generico non farebbe:

**1. La citazione deve esistere.** `source_excerpt` viene cercato
*letteralmente* nel testo **inviato** — le finestre, non il documento intero.
Cercarlo nel documento completo perdonerebbe proprio l'errore che interessa: una
citazione presa da una parte che nel prompt non c'era. Se non si trova, il campo
scende a `low` e non e' piu' usabile.

**2. Fail-closed.** Un campo illeggibile vale `null` con una nota che dice
perche'. Non esiste il caso «assente quindi va bene»: l'assenza e' un esito e va
scritta.

**3. La validazione non sta in cache.** In cache va la risposta grezza del
modello. La validazione rigira a ogni lettura, cosi' una correzione al
validatore vale subito su tutto lo storico senza ripagare una chiamata.

---

## Uso

```bash
cp .env.example .env          # EDGAR_USER_AGENT, ANTHROPIC_API_KEY
python -m edgar_llm.config    # dice cosa vede, senza stampare i valori

# quanto testo c'e' davvero, e quanto costa
python -m edgar_llm.tools.measure_docs --ciks lista.txt --per-form 5

# etichettare a mano il golden set
python -m edgar_llm.label --ciks lista.txt --per-form 5 --limit 20

# le metriche
python -m edgar_llm.eval --prompt v1
python -m edgar_llm.eval --prompt v1 --replay     # senza chiave, dalla cache

# il perimetro, prima di pubblicare
python -m edgar_llm.tools.perimeter_check --deny-file lista.txt
```

### Segreti

Due sorgenti, in quest'ordine: **l'ambiente del processo**, e un file `.env`
cercato risalendo dalle directory sopra il package. L'ambiente vince sempre — uno
scheduler o una CI devono poter scavalcare un `.env` vecchio rimasto su disco,
non il contrario.

Se questo package vive dentro un repo piu' grande, il `.env` va alla **radice di
quel repo**, non qui dentro: `edgar_llm/` e' cio' che viene pubblicato, e un
segreto non sta nella directory che si pubblica. La guardia del perimetro
segnala una chiave trovata qui — anche una finta, perche' a occhio non si
distinguono.

`EDGAR_USER_AGENT` non e' facoltativo: la SEC blocca le richieste senza nome e
contatto reali. Non sta nel codice perche' il codice e' pubblico e il contatto
no.

### Etichettare

`label` **non stampa il testo nel terminale**: lo esporta, un file per
documento, e stampa il percorso. Una finestra e' venti-quaranta mila caratteri,
cioe' dieci-venti pagine; in una console non si torna indietro, non si cerca,
non si tiene il segno, e chi etichetta cento documenti a scorrimento non sta
leggendo ma scremando. Si legge il file in un editor e si risponde nella CLI a
fianco.

Il file contiene **esattamente** la stringa che riceve il modello, delimitatori
a parte: se i due divergessero, l'etichetta risponderebbe a un testo diverso da
quello estratto e la diagnosi dentro/fuori finestra misurerebbe la differenza
fra due tagli invece della qualita' di uno. Un test lo verifica carattere per
carattere.

Ogni sessione lascia un `INDICE.md` con lo stato di ciascun documento —
etichettato, saltato, da fare, illeggibile — riscritto a ogni passo, cosi' una
sessione interrotta a meta' dice cosa era stato fatto. I file finiscono in una
directory di stato **fuori dal package**: contengono testo di depositi SEC e
non hanno niente da fare in un mirror pubblico.

## Test

```bash
pytest                 # 93 asserzioni, senza rete e senza chiave
pytest -m llm          # i test che chiamano davvero l'API
```

I test di integrazione sono esclusi dal run di default: hanno un marker apposta,
ed e' il motivo per cui questa parte del progetto usa pytest mentre il resto no
([ADR-007](docs/adr/007-pytest-solo-qui.md)).

## Decisioni

In [docs/adr/](docs/adr/), scritte quando la decisione e' stata presa e non
ricostruite alla fine. Ci sono anche quelle negative — niente framework di
orchestrazione, mai un cancello, distillazione rimandata — con il ragionamento
che le ha prodotte.

Nessun prompt cambia senza rieseguire le evals. La regola e' applicabile perche'
la chiave di cache include `prompt_version`: un prompt nuovo non puo' riusare le
risposte del vecchio nemmeno per sbaglio ([ADR-005](docs/adr/005-chiave-di-cache.md)).
