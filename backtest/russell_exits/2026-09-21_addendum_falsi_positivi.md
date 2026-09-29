# Addendum del 21 settembre 2026 — che cosa conta come falso positivo

Addendum alla pre-registrazione del 16 settembre (`2026-09-16_preregistrazione.md`), §3. Scritto **prima di calcolare
o guardare qualunque rendimento extra**, come il documento che modifica. Decisione dell'utente del 21 settembre,
registrata in `DECISIONS.md` sotto ADR-039.

## La regola

> **Falso positivo** = titolo segnato come uscita dalla definizione, **presente nel campione dopo le esclusioni della
> fase 1**, ma assente dalla lista ufficiale FTSE Russell delle cancellazioni di quell'anno.

Le società che la **fase 1 toglie** non contano come falsi positivi, perché non sono uscite che la pipeline produce:
non arrivano mai a essere un caso. Il motivo per cui si tolgono è dichiarato nella pre-registrazione, §3, esclusione 2
— **acquisita, in fusione o delistata fra il 31 marzo e la ricostituzione** — e ciascuna porta il deposito che lo
prova: un Form 25 o 15-12, oppure un 8-K con voce 2.01 (una con la 1.03), depositato in quella finestra.

Questo è il conteggio che misura la definizione delle uscite. Il conteggio letterale — ogni titolo segnato e assente
dalla lista, comprese le acquisite — misura qualcosa che la pipeline non produce, e resta riportato accanto per
trasparenza, non come criterio.

## La soglia, invariata

Oltre il **10% dei casi di un anno** ci si ferma e si chiede all'utente, come nella direttiva del 17 settembre. La
soglia vale su ogni anno controllato, non sulla media.

## Che cosa si riporta, per ogni anno controllato

| voce | significato |
|---|---|
| uscite segnate | titoli che la definizione segna come uscita, dopo le esclusioni della fase 1 |
| uscite ufficiali ritrovate | cancellazioni della lista ufficiale che la definizione trova |
| uscite ufficiali mancate | cancellazioni della lista ufficiale che la definizione **non** trova, con il motivo |
| falsi positivi | secondo la regola sopra, con la quota sulle uscite segnate |
| falsi positivi letterali | il conteggio che include le acquisite nel trimestre, per confronto |

## 2025, già misurato

`risultati/falsi_positivi_2025.md`. Lista ufficiale: 152 cancellazioni dal Russell 3000, 141 ritrovate in IWM al 31
marzo. Con l'abbinamento per emittente: 165 uscite segnate, 139 delle 141 ritrovate.

| | per emittente | per CUSIP esatto |
|---|---:|---:|
| falsi positivi secondo questa regola | **1 (0,6%)** | 9 (5,2%) |
| falsi positivi letterali | 24 (14,5%) | 32 (18,4%) |

**L'unico falso positivo 2025 è Solo Brands.** Assente da IWM nell'istantanea del 30 giugno e assente dalla lista
ufficiale delle cancellazioni: la definizione la segna come uscita, FTSE Russell no. Non ha depositi di fine
quotazione né di fusione nel trimestre, quindi la fase 1 non la toglie, e resta senza spiegazione.

Le due cancellazioni ufficiali non ritrovate, con il motivo: **Ramaco** (simbolo `METCB`, quota residua 121,0%: la
lista cancella una classe che qui è abbinata all'altra, perché più righe della stessa società valgono come una sola,
§3) e **X4 Pharmaceuticals** (`XFOR`, 60,9% delle azioni di marzo rettificate, sopra la soglia del 50%).

## Gli anni controllati (aggiornamento del 22 settembre 2026)

Liste ufficiali finali scaricate e verificate per 2016, 2017, 2021, 2022, 2023 e 2024 (`scarica_liste_ftse.py`): ogni
file è riconosciuto come finale dalla **data di creazione nei metadati**, che coincide col giorno della ricostituzione,
ed è disgiunto dalle aggiunte dello stesso giorno. **2018 e 2020** non hanno una lista finale pubblica e restano **non
controllati**; il **2019** non ha lista e serve solo a costruire il campione, dichiarato non verificato.

Le uscite «senza spiegazione» sono state riprese a mano una per una (`classifica_extra.py`), risolvendo il nome con
la ricerca per società di EDGAR, nomi precedenti compresi. Risultati in `risultati/falsi_positivi_ricalcolati.md`:

| anno | finestra degli eventi | uscite segnate | ufficiali ritrovate | falsi positivi | quota |
|---|---|---:|---:|---:|---:|
| 2016 | ricostituzione | 156 | 100% | 7 | 4,5% |
| 2017 | ricostituzione | 145 | 97,8% | 9 | 6,2% |
| 2021 | ricostituzione | 298 | 99,2% | 12 | 4,0% |
| 2022 | ricostituzione | 304 | 100% | 15 | 4,9% |
| 2023 | ricostituzione | 185 | 100% | 15 | 8,1% |
| **2024** | **istantanea di settembre** | 184 | 100% | 14 | **7,6%** |
| 2025 | ricostituzione | 165 | 98,6% | 1 | 0,6% |

**Nessun anno sopra il 10%.** Il 2023 arriva al 10,8% solo contando come falsi positivi tutti e cinque i casi che non
si sono potuti risolvere per nome: è il caso peggiore, riportato e non usato.

## Il 2024, due misure

Il 30 giugno 2024 cade di domenica con zero sedute dopo la ricostituzione del 28: quell'istantanea non ha ancora
recepito il cambio di indice (17 entrate contro 190-285 degli altri anni) e ritrova 3 cancellazioni ufficiali su 122.
Per il 2024 l'istantanea «dopo» è il **30 settembre** (decisione del 17-09-2026), che ne ritrova 122 su 122.

Con l'istantanea spostata, la finestra degli eventi societari che la fase 1 esclude può finire alla ricostituzione
(lettera del §3) o all'istantanea (stessa logica che ha spostato l'istantanea). **Decisione dell'utente del
22-09-2026: fino all'istantanea di settembre**, a condizione che ogni sparizione estiva esclusa abbia il suo deposito
EDGAR. Entrambi i numeri restano qui:

| finestra degli eventi | tolte dalla fase 1 | falsi positivi | quota | |
|---|---:|---:|---:|---|
| fino alla ricostituzione (28 giugno) | 30 | 24 | 13,0% | non usata |
| fino all'istantanea (30 settembre), **prima** della verifica | 44 | 11 | 6,0% | superata |
| fino all'istantanea (30 settembre), **dopo** la verifica | 41 | 14 | **7,6%** | **decide** |

**La verifica.** Le sparizioni estive — escluse con la finestra lunga e non con quella corta — sono 13. Dieci hanno
un **Form 25-NSE** fra il 28 giugno e il 30 settembre, cioè la cancellazione dal listino: Hawaiian Holdings, Cerevel
Therapeutics, Atrion, Silk Road Medical, Diamond Offshore, Everbridge, National Western Life, Morphic, Cambridge
Bancorp; SunPower ha l'8-K voce 1.03 (fallimento, 6 agosto) e il 25-NSE del 20 settembre. Tre no:

- **Dril-Quip** aveva solo un 8-K voce 2.01, e non è sparita: la fusione con Innovex del 6 settembre è inversa,
  Dril-Quip è l'entità che sopravvive col nome di **Innovex International**, che nell'istantanea di settembre c'è
  (CUSIP 457651107). È lo stesso emittente con un CUSIP nuovo, cioè un falso positivo.
- **Bowlero** aveva solo un 8-K voce 2.01 del 5 settembre, senza Form 25 né 15: nessuna prova di sparizione.
- **Desktop Metal** aveva solo la proxy di fusione (PREM14A del 1° agosto, DEFM14A del 15 agosto); la fusione con
  Nano Dimension si è chiusa nel 2025. Resta esclusa, perché il DEFM14A è fra i moduli della fase 1 elencati nel
  §3, ma il deposito documenta una fusione annunciata, non una cancellazione dal listino.

**Da qui una correzione per tutti gli anni.** I due classificatori usavano l'8-K voce 2.01 come prova di uscita,
ma il §3 della pre-registrazione elenca solo la voce **1.03**. La 2.01 la depositano anche l'acquirente e chi
sopravvive a una fusione inversa: Central Valley Community Bancorp (diventata Community West), Cross
Country Healthcare, Bowlero, Dril-Quip. Tolta la 2.01, i numeri di tutti gli anni sono quelli della prima tabella:
cambia al più un titolo per anno, tre nel 2024 con la finestra lunga. Quando una società acquisita sparisce davvero,
accanto alla 2.01 c'è sempre un Form 25 o 15, quindi l'esclusione regge lo stesso.

## Il campione, dopo la verifica d'identità su EODHD

L'identità di un titolo è risolta quando il prezzo implicito nella posizione del fondo coincide con la chiusura
grezza entro il 3% (§3). Con i prezzi Yahoo la verifica falliva soprattutto perché Yahoo non conserva i titoli
delistati, cioè proprio quelli che diventano casi. Rifatta sull'archivio EODHD (`verifica_identita_eodhd.py`, che
legge solo `market_data.api`), la copertura fra i casi è:

| anno | casi | identità con Yahoo | con EODHD |
|---|---:|---:|---:|
| 2015 | 182 | 23% | **89%** |
| 2016 | 155 | 23% | **95%** |
| 2017 | 144 | 32% | **95%** |
| 2018 | 136 | 29% | **95%** |

Sopra il 50% in tutti e quattro gli anni: il campione 2015-2018 **non** si assottiglia. Tabella completa, casi e peer
per ogni anno, in `risultati/copertura_identita.md`.

## Correzione del 22 settembre, prima di qualunque rendimento

Le misure sopra sono state rifatte dopo la correzione della cache compressa (commit `f4a7042`, dettagli
nell'addendum della fermata 1). Tutte scendono o restano uguali: 2016 4,5%, 2017 **4,8%**, 2021 **3,4%**, 2022
**4,6%**, 2023 8,1%, 2024 con la finestra di settembre **6,5%** (12,5% con quella alla ricostituzione, non usata), 2025
0,6%. Nessun anno sopra il 10%. Le sparizioni estive del 2024 escluse sono 12: 11 con un Form 25, 15-12 o 8-K 1.03,
Desktop Metal con la sola proxy di fusione.
