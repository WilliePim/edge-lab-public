# Copertura della capitalizzazione ricostruita

Descrittivo. La ricostruzione e' point-in-time: per un'osservazione al giorno D si usa **l'ultimo conteggio azioni con `filed` <= D**, mai uno con deposito successivo.


> **`companyconcept` al posto di `companyfacts`.** Misurato su cinque emittenti, `companyfacts` pesa 1,81 MB medi: su 8.098 CIK sarebbero **13,4 GB** in una cache che ne ha gia' ~16. `companyconcept` serve gli stessi identici record dei due tag a ~50 KB per chiamata. La sostituzione costa una seconda e terza richiesta per la minoranza che non risponde al tag primario e risparmia circa 25 volte lo spazio.


## Sintesi

| | |
|---|---|
| acquisti nel corpus | 296,759 |
| con capitalizzazione | 150,845 (**50.8%**) |
| con rendimento forward a 12m | 184,710 |
| **con entrambi** | 139,354 (**75.4%**) |
| CIK con serie azioni | 6,848 |
| CIK multi-classe (float senza conteggio) | 521 |
| CIK senza alcun dato | 729 |

## Copertura per anno

| anno | acquisti | con cap | copertura | con cap **e** rendimento | copertura |
|---|---:|---:|---:|---:|---:|
| 2013 | 432 | 0 | 0.0% | 0 | 0.0% |
| 2014 | 2,616 | 858 | 32.8% | 858 | 51.2% |
| 2015 | 32,739 | 11,157 | 34.1% | 11,129 | 70.3% |
| 2016 | 29,797 | 11,157 | 37.4% | 11,135 | 74.2% |
| 2017 | 24,423 | 11,063 | 45.3% | 10,979 | 76.1% |
| 2018 | 27,727 | 12,482 | 45.0% | 12,441 | 76.4% |
| 2019 | 26,532 | 12,398 | 46.7% | 12,231 | 73.5% |
| 2020 | 29,338 | 14,301 | 48.7% | 14,078 | 72.7% |
| 2021 | 22,743 | 11,741 | 51.6% | 11,695 | 72.6% |
| 2022 | 30,976 | 17,962 | 58.0% | 17,915 | 79.2% |
| 2023 | 25,594 | 16,506 | 64.5% | 16,397 | 81.6% |
| 2024 | 20,246 | 13,683 | 67.6% | 13,462 | 76.8% |
| 2025 | 19,473 | 14,358 | 73.7% | 7,034 | 79.1% |
| 2026 | 4,123 | 3,179 | 77.1% | 0 | 0.0% |

## Copertura per bucket di valore dell'acquisto

| valore | acquisti | con cap | copertura |
|---|---:|---:|---:|
| < $10k | 81,121 | 45,845 | 56.5% |
| $10k-50k | 68,765 | 36,685 | 53.3% |
| $50k-250k | 67,497 | 33,132 | 49.1% |
| $250k-1M | 36,388 | 16,932 | 46.5% |
| >= $1M | 42,988 | 18,251 | 42.5% |

## Copertura per esito

| gruppo | acquisti | con cap | copertura |
|---|---:|---:|---:|
| con rendimento forward 12m | 184,710 | 139,354 | 75.4% |
| senza rendimento forward | 112,049 | 11,491 | 10.3% |

**Le due righe non sono confrontabili, ed e' importante non leggerle come se lo fossero.** La capitalizzazione e' azioni **per** prezzo: un nome senza serie prezzi non puo' averla, quindi il 5,3% della seconda riga e' meccanico e non misura una selezione in piu'. L'unico numero informativo e' il primo: **fra le osservazioni che un prezzo ce l'hanno, il 75.4% ha anche il conteggio azioni**, e il 24.6% che manca e' colpa del conteggio, non del prezzo.


E quel deficit **non e' distribuito nel tempo**: 73.1% di copertura fino al 2021 contro 79.3% dal 2022. Il tagging XBRL della copertina si e' generalizzato tardi fra i piccoli filer, quindi la capitalizzazione manca soprattutto nel periodo **in-sample** — che e' esattamente dove servirebbe per rifare i test per dimensione.


## Distanza fra deposito del conteggio e osservazione

| | giorni |
|---|---:|
| mediana | **31** |
| p25 | 12 |
| p75 | 65 |
| p95 | 283 |
| oltre un anno | 4.6% |

E' l'eta' del conteggio, non un ritardo di elaborazione: per un emittente che ha diluito nel frattempo la capitalizzazione e' sbagliata **esattamente di quanto ha diluito** — che e' cio' che questo scanner cerca.


## Multi-classe

**521** emittenti depositano una copertina strutturata (taggano `dei:EntityPublicFloat`) ma non hanno alcun conteggio azioni senza dimensioni: il loro conteggio e' sull'asse della classe, che entrambe le API scartano. **Non hanno capitalizzazione qui e non e' stata indovinata.**


Primi 40 CIK: `1001250`, `1001288`, `1002135`, `100493`, `1005731`, `1006269`, `1012019`, `1012620`, `1014739`, `1021860`, `1031308`, `1031316`, `103379`, `1037038`, `1041657`, `1042776`, `1043509`, `1047127`, `104889`, `105016`, `1050446`, `1050606`, `1053507`, `1056087`, `1056288`, `1058290`, `1065837`, `1067837`, `1069202`, `1069530`, `1084869`, `1089872`, `1090425`, `1091801`, `1094831`, `1099160`, `1109116`, `1121788`, `1126328`, `1162556`


Altri **729** CIK non hanno ne' conteggio ne' float: filer esteri (20-F, 40-F), fondi, o CIK che non depositano XBRL.


## Sospetti di split non allineato

**2,152** CIK hanno un salto del conteggio azioni di almeno 4x o al massimo 0,25x fra due depositi consecutivi. `price` nel panel e' rettificato per split, il conteggio di copertina no: su questi la moltiplicazione e' sbagliata del fattore di split, in modo silenzioso e plausibile. **Segnalati, non corretti.**


Primi 30 CIK: `1000045`, `1000683`, `1000694`, `1000753`, `1001316`, `1001601`, `1001614`, `1001907`, `1002047`, `1002590`, `1003201`, `1004411`, `1004724`, `1004980`, `1005101`, `1005210`, `1006028`, `1006281`, `1006837`, `1006840`, `1008579`, `1008586`, `1008848`, `1009759`, `1009829`, `1009891`, `1009976`, `1011060`, `1011509`, `1012477`


---

## Tre passi tentati per chiudere il divario


### Passo 0 — prezzi per i ticker vivi mai chiesti

`backfill_prices.py` costruiva la lista dal corpus **dopo** la soglia dei $25.000, quindi 2.575 ticker di societa' ancora attive non erano mai stati chiesti. Scaricati con la stessa fonte e la stessa finestra.


| | |
|---|---|
| ticker tentati | 2.468 (99 scartati: simboli malformati, un CIK) |
| riusciti al primo colpo | **1.050** |
| falliti | 1.418 (**57,5%**, sopra la soglia del 20%) |
| di cui **ticker cambiato** | **912 (64%)** — AAXN->AXON, ABC->COR |
| di cui senza ticker corrente in EDGAR | 458 |
| recuperati riscaricando col simbolo corrente | **892** |
| serie prezzi totali | da 3.582 a **5.524** (+54%) |

**Il 64% dei fallimenti era un cambio di simbolo**, non un delisting: societa' vive che quotano sotto un altro ticker. E' la quantificazione del difetto che `rubric_discrimination.md` dichiarava "il piu' serio dopo il survivorship, in direzione ignota". Riscaricando dal ticker corrente e salvando col nome storico se ne recuperano 892.


Effetto sulla copertura dei **rendimenti**: da **44,5% a 62,2%** degli acquisti del corpus. Effetto sulla copertura della **capitalizzazione**: quasi nullo — i nomi recuperati sono piccoli e per lo piu' non hanno neanche il conteggio azioni.


### Passo 2 — i 729 CIK senza alcun dato azioni

Classificati per SIC dalle `submissions` dell'emittente, non indovinati dai tipi di forma.


| categoria | CIK |
|---|---:|
| non deposita 10-K/10-Q | 665 |
| operativa | 43 |
| shell / blank check | 16 |
| estero (20-F / 40-F) | 5 |

**Il 91% non deposita affatto 10-K o 10-Q, e il 97% di quelli non ha nemmeno un codice SIC.** Non sono societa' operative che sfuggono al tagging: sono entita' che compaiono come emittente su un Form 4 senza essere registranti con obblighi periodici. **Proposta: escluderle dal corpus**, non cercare di prezzarle. Effetto sul denominatore: tolgono osservazioni che non potranno mai avere una capitalizzazione, quindi la copertura sale per costruzione — ed e' il tipo di aumento che va dichiarato, non incassato in silenzio.


Le categorie da tenere sono le **43 operative** e le **5 estere**; le **16 shell / blank check** sono una decisione dell'utente, perche' una SPAC ha una capitalizzazione vera ma non e' cio' che questo scanner cerca.


### Passo 3 — la copertina dei 10-K/10-Q, stimato su 50

Ogni 10-K e 10-Q dichiara il numero di azioni in prosa sulla prima pagina, che il filer l'abbia taggato in XBRL o no. E' l'unica strada aperta per i **521 multi-classe**, il cui fatto porta la dimensione di classe che entrambe le API scartano.


**Tasso di aggancio: 26/50 (52%).** Su un campione di 25 multi-classe e 25 operative senza dati.


Un regex su testo libero al 52% non e' una fonte: e' un recupero parziale con un tasso d'errore non misurato. Prima di usarlo servirebbe verificare **cosa** aggancia — se il numero letto e' quello giusto, non solo se un numero c'e'.


---

## Cancello

Copertura sulle osservazioni con rendimento forward: **75.4%**, **sotto la soglia dell'80%**. **Ci si ferma qui**: nessun test per quintili e' stato eseguito.


Un controllo per dimensione costruito su 75% del campione non e' un controllo per dimensione: e' una nuova selezione, di cui nessuno ha misurato la forma. Le tabelle sopra dicono dove manca — per anno, per taglia dell'acquisto, per esito — e il modo di alzarla e' aggiungere i tag di ripiego, non abbassare la soglia.

