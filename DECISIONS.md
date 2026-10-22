# DECISIONS

> **Note on this public version.** The ADRs below are a selection from the project's working decision log,
> renumbered in sequence from ADR-001. Entries about studies that are not part of this repository were left out;
> within the selected entries, references to those studies, local paths and external private repositories were
> removed or made generic, and per-security values derived from licensed price data were dropped. Notes added for this
> version are marked «Nota della versione pubblica». Cross-references between ADRs use the new numbers. The entries
> are kept in their original language (Italian).

Registro delle decisioni non ovvie dei backtest, stile ADR. Ogni voce: contesto, decisione,
alternative scartate, conseguenze, verifica. **Le voci non si riscrivono**: una modifica dopo
il congelamento di una pre-registrazione è una voce nuova, datata, riportata accanto ai
risultati.

Le decisioni di `edgar_llm/` stanno in `edgar_llm/docs/adr/` e quelle di `market-data/` in
`market-data/docs/adr/`, perché quei package sono autosufficienti. Questo file riguarda i test sul corpus.

---

## ADR-001 — 2026-09-15 — Criterio di verdetto del ri-test 50–300M: primario e secondario

**Contesto.** Il prompt del ri-test chiede un criterio «uguale a quello svedese» e poi lo
scrive: NON REGGE se media vs peer ≤ 0, oppure IC 95% include 0 e placebo non ≈ 0; REGGE solo
con media > 0, IC che esclude 0, placebo ≈ 0. Il criterio svedese vero
(pre-registrazione della replica svedese, https://github.com/WilliePim/fi-insider-scanner) è diverso: placebo
descrittivo, t CR1 ≥ 2 sia vs indice sia vs peer, scenario S0, clausola MDE, e copertura
< 60% → INCONCLUSIVO. Il testo del prompt lascia anche due casi senza esito.

**Decisione.** Primario = testo del prompt. Secondario = criterio svedese copiato. I due casi
scoperti (media > 0 con IC che esclude 0 e placebo non ≈ 0; media > 0 con IC che include 0 e
placebo ≈ 0) sono INCONCLUSIVO, con l'etichetta del motivo. Si riportano entrambi i verdetti.

**Alternative scartate.** Solo il criterio svedese: la sua clausola di copertura rende il
verdetto INCONCLUSIVO già oggi (copertura 54,4%, massimo 57,1%) e il test non direbbe niente
sul matching. Solo il testo del prompt: si perderebbe il confronto con la Svezia che il prompt
stesso chiede.

**Conseguenze.** Il secondario è determinato dalla copertura prima di qualunque rendimento, ed
è scritto così nella pre-registrazione. Se l'utente vuole un altro primario, va cambiato prima
del passo 1 in un file nuovo.

**Verifica.** Il report del verdetto cita testualmente §3.1 e §3.2 della pre-registrazione e
applica solo quelle regole.

## ADR-002 — 2026-09-15 — Statistica: CR1 per emittente

**Contesto.** L'originale riporta una t iid (`tools/backtest_event_time.py::tstat`) e un IC
bootstrap iid. Nella cella P ci sono 3.276 eventi su 1.110 emittenti, 2,95 per emittente, e il
cooldown di 126 giorni di calendario lascia sovrapposizione residua con un orizzonte di 126
sessioni (~180 giorni).

**Decisione.** Inferenza primaria con **CR1 per emittente**: per una media
V = G/(G−1) · Σ_g (Σ_{i∈g} (x_i − x̄))² / N², lo stesso fattore di
`tools/table3_regression.py::ols_cluster` (riga 92) con K = 1. IC 95% = media ± t(G−1; 0,975)·SE.
Si riportano accanto t iid e IC bootstrap iid (1.000 draw, seed 12345) per continuità con
l'originale. MDE = 2,80 · sd/√n · √DEFF.

**Alternative scartate.** Bootstrap per cluster come primario: più lento e per una media dà
quasi lo stesso numero; resta disponibile come controllo. Two-way cluster emittente × mese:
non chiesto, e con ~130 mesi ha pochi cluster temporali.

**Conseguenze.** Le t di questo test saranno più basse di quelle dell'originale anche a parità
di media. Non è un peggioramento del risultato: è la t che l'originale avrebbe dovuto avere.

**Verifica.** Test sulla funzione CR1: con un cluster per osservazione deve coincidere con la
t iid moltiplicata per √(G/(G−1)).

## ADR-003 — 2026-09-15 — Evento identico all'originale, riproduzione col codice originale

**Contesto.** Il prompt chiede di ripescare la definizione dal codice. Il codice e il prompt
divergono in tre punti: la t non è clusterizzata, i delistati escono dall'orizzonte invece di
restare all'ultimo prezzo, e la soglia $25k non è nel backtest ma a monte nel corpus.

**Decisione.** L'insieme degli eventi dei passi 2–4 è **identico** a quello dell'originale:
corpus con soglia per riga a monte, evento per (emittente, data di deposito), veto di diluizione
point-in-time come nell'originale (un predicato della definizione dell'evento, non un filtro validato),
fascia da `marketcap_rows.jsonl`, ordine cancello → fascia → variante (b). Il
passo 1 esegue `tools/backtest_event_time.py` senza modifiche e deve riprodurre n 3.213,
+3,50%, −1,94%, t 4,30 ai decimali stampati; altrimenti il test si ferma.

**Alternative scartate.** Correggere l'originale prima di riprodurlo: non si saprebbe più se
una differenza viene dai dati o dalla correzione.

**Conseguenze.** Nessuna modifica a `tools/`, ai cancelli o a `flags.py`. Il nuovo codice sta in
`backtest/` e importa i moduli esistenti in sola lettura.

## ADR-004 — 2026-09-15 — Calendario comune dal passo 2

**Contesto.** L'originale misura l'uscita come ingresso + h **barre della serie del titolo**; il
`matched_control.py` esistente fa lo stesso su ciascuna gamba. Due serie con buchi diversi
finiscono in date di calendario diverse, e la scomposizione
(r_e − r_IWM) = (r_e − r_peer) + (r_peer − r_IWM) smette di essere un'identità.

**Decisione.** Dal passo 2 le sessioni sono le barre di IWM. Ingresso = prima sessione dopo il
deposito; uscita = ingresso + h sessioni; prezzo di ogni gamba = ultimo close ≤ sessione entro
5 sessioni. Il passo 1 riporta anche lo stesso insieme di eventi sul calendario comune, come
ponte.

**Alternative scartate.** Barre del titolo per ogni gamba: scomposizione solo approssimata.

**Conseguenze.** Un titolo illiquido con buchi lunghi può perdere l'ingresso (`NO_ENTRY_BAR`,
contato).

## ADR-005 — 2026-09-15 — Pool dei controlli

**Contesto.** Il prompt chiede peer «dello stesso universo 10-K». In cache ci sono azioni XBRL
per 8.098 CIK e prezzi per i ticker di 4.766 emittenti del corpus; nessun dato per le società
che non hanno mai avuto un acquisto insider nel corpus, e yfinance non serve i delistati.

**Decisione.** Pool = emittenti del corpus con file in `state/backfill/shares/` e serie in
`state/backfill/prices/` (4.765 CIK), escluso l'emittente dell'evento.

**Alternative scartate.** Costruire l'universo 10-K dagli indici EDGAR: gli identificativi si
trovano, ma i prezzi dei delistati no, e un universo con i soli sopravvissuti è peggio di un
pool dichiarato.

**Conseguenze.** I peer sono società i cui insider comprano in qualche momento fra il 2015 e il
2026, solo non in quello. È il limite §15.1 della pre-registrazione.

## ADR-006 — 2026-09-15 — Market cap dei controlli

**Contesto.** `marketcap_rows.jsonl` ha un market cap solo alle date di transazione insider di
ciascun emittente. Per un peer senza acquisti nei 12 mesi precedenti, l'ultima riga è vecchia
di almeno un anno.

**Decisione.** Cap del candidato a D = azioni XBRL con `filed` ≤ D × ultimo close ≤ D entro 5
sessioni: la regola di `tools/marketcap_build.py` al commit `ef0ff29`, reimplementata perché il
file è stato rimosso con la potatura v3. D = data del market cap dell'evento. Anche la cap
dell'evento si ricalcola con questa funzione **per la sola distanza di matching**;
l'appartenenza alla fascia resta quella originale.

**Alternative scartate.** Usare `marketcap_rows` anche per i peer: dimensione di un anno prima.
Riclassificare gli eventi con la nuova funzione: cambierebbe la popolazione rispetto al finding.

**Conseguenze.** Si riporta quanti eventi hanno cap ricalcolata fuori fascia, come diagnostica.

**Verifica.** Sugli eventi, la cap ricalcolata deve coincidere con `marketcap_rows` alla stessa
data salvo gli split noti; le discordanze si contano.

## ADR-007 — 2026-09-15 — Finestra quiet: point-in-time come primaria

**Contesto.** Il prompt chiede peer «senza acquisti insider nei 12 mesi precedenti e
successivi». La parte successiva usa informazione che alla data dell'evento non esiste.
CLAUDE.md: «Point-in-time ovunque … Il lookahead invalida tutto».

**Decisione.** Primaria: nessuna riga del corpus con `transaction_date` in [D − 365, D] e
`filed_date` ≤ D. Sensibilità descrittiva: [D − 365, D + 365].

**Alternative scartate.** ±365 come primaria. Se gli acquisti insider contengono informazione,
togliere i peer i cui insider comprano nei 12 mesi dopo toglie i peer con le notizie migliori:
il rendimento del peer scende e l'excess sale. Il bias va **a favore di REGGE**.

**Conseguenze.** La differenza fra primaria e sensibilità misura quanto pesa quel bias.

## ADR-008 — 2026-09-15 — Matching: dimensione, dimensione + momentum, pareggi, riuso

**Contesto.** Il prompt chiede nearest neighbour sul market cap e, se il placebo fallisce,
anche sul rendimento a 12 mesi. Il matched control del 2026-09-01 mostra l'excess concentrato
nel terzile di rendimento passato peggiore (+6,49%, t iid 2,79).

**Decisione.**
- **M_size**: minima |log cap − log cap evento|.
- **M_mom**: minima distanza euclidea su (log cap, r12) standardizzati con media e sd dei
  candidati di quella data e fascia. r12 = close(D)/close(D − 252 sessioni) − 1, |r12| ≤ 500%.
- **Entrambi calcolati sempre**; quale sia primario lo decide ADR-009.
- **Pareggi**: CIK numerico minore. Nessun seme.
- **Riuso** di un peer consentito, contato e riportato.
- Il peer si sceglie senza guardare i suoi prezzi futuri; se la serie finisce prima
  dell'uscita, ultimo close piatto come per l'evento.

**Alternative scartate.** Calcolare M_mom solo se il placebo di M_size fallisce: la scelta di
cosa mostrare dipenderebbe da un risultato. Uso unico dei peer: sui giorni con molti eventi
esaurisce il pool vicino e peggiora il matching senza togliere la correlazione.

**Conseguenze.** I controlli sono correlati fra loro quanto gli eventi; il CR1 per emittente
dell'evento non lo assorbe del tutto. Dichiarato.

## ADR-009 — 2026-09-15 — Placebo: due finestre

**Contesto.** Il placebo del prompt è (−252, −126] sessioni contro lo stesso peer. M_mom
appaia sul rendimento (−252, 0], che contiene quella finestra: il placebo di M_mom tende a zero
per costruzione. La regola del prompt «il matching corretto è quello con placebo più vicino a
zero» favorirebbe M_mom anche con un bias intatto.

**Decisione.** P1 = (−252, −126], valido per M_size. P2 = (−504, −378], valido per entrambi.
M_size è primario se P1 ≈ 0 e P2 ≈ 0; altrimenti è primario il matching con |media P2|
minore, a parità |t CR1| minore. «Placebo ≈ 0» = IC 95% CR1 include 0; per M_size servono P1 e
P2, per M_mom P2.

**Alternative scartate.** Solo P1: contaminato per M_mom. M_mom con r12 su (−126, 0]: cambia il
matching chiesto dal prompt. «Più vicino a zero» come |t| minore: premierebbe il matching più
rumoroso.

**Conseguenze.** P2 richiede 504 sessioni di storia: coperti oggi 2.767 eventi su 3.276.

## ADR-010 — 2026-09-15 — Delistati, censura, scenari

**Contesto.** L'originale fa uscire dall'orizzonte ogni evento la cui serie finisce prima
(`PARTIAL`). Il prompt chiede di tenerli all'ultimo prezzo e di riportare S0 = −100% e S1 =
+15% «come nel test svedese», dove però S0 era excess 0. Il buco vero è a monte: 29.356 eventi
con veto su 61.609 non hanno fascia, 17.581 senza nessuna serie.

**Decisione.** Dal passo 2: serie finita prima dell'uscita e più di 10 sessioni prima della
fine della cache → delistato, ultimo close piatto (`ENDED_IN_WINDOW`); uscita oltre la fine
della cache → `TOO_RECENT`, escluso. Scenari con nomi senza ambiguità: **S_−100**, **S_+15**,
**S_zero**. Applicati ai `ENDED_IN_WINDOW` della cella e agli eventi senza fascia attesi in
cella, stimati per anno sulla quota di fascia degli eventi con cap dello stesso anno.
Excess non osservabile = rendimento di scenario − gamba media osservata dello stesso anno.

**Alternative scartate.** Chiamarli S0 e S1 come nel prompt: S0 significherebbe due cose diverse
nei due repo.

**Conseguenze.** Il passo 1 e il passo 2 hanno insiemi di coppie leggermente diversi; il ponte
di ADR-004 li riconcilia.

## ADR-011 — 2026-09-15 — Date dei report per il closed period

**Contesto.** Il test svedese aveva date di report solo per il 53% degli eventi, da Yahoo. Il
prompt chiede EDGAR. Per i 1.110 emittenti della cella le submissions sono in cache; 425 hanno
storia in shard, di cui 373 da scaricare.

**Decisione.** Forme 10-Q, 10-K, 10-KT, senza `/A`. R = ultima `filingDate` ≤ T, con T = la
data di transazione più vecchia dell'evento. k = sessioni IWM in (R, T]. Dentro W ⟺ k ≤ W, W =
10 principale, 5 e 20 sensibilità. UNKNOWN se nessun R nei 200 giorni prima di T. Descrittivo:
R = ultimo 8-K con item 2.02.

**Alternative scartate.** T = data di deposito: misurerebbe quando l'insider ha dichiarato, non
quando ha comprato. Solo 10-Q/10-K: «dopo i risultati» vuol dire dopo il comunicato, che
precede il 10-Q.

**Conseguenze.** Gli shard scaricati si registrano con impronta nel report del passo 4.

## ADR-012 — 2026-09-15 — Celle «cluster»

**Contesto.** Il prompt chiede una cella «cluster 4/4». In Svezia 4/4 era il punteggio della
colonna B; qui `score_v3` = cluster + director + no_10pct + terreno, e `terreno` è vero su 5
eventi su 3.276 della cella P.

**Decisione.** Due celle descrittive: **4/4** letterale e **cluster** da solo. Ricostruite con
`form4_scanner/flags.py` invariato su transazioni costruite dal corpus, deposito ≤ data
dell'evento e transazione nei 60 giorni prima, etichette CMP di `build_labels` come
nell'originale.

**Alternative scartate.** Ridefinire 4/4 senza `terreno`: sarebbe un punteggio che lo scanner
non ha.

**Conseguenze.** La cella 4/4 è non informativa per costruzione e lo si dice nel report.

## ADR-013 — 2026-09-15 — Costo API

**Decisione.** Nessuna chiamata a modelli linguistici in nessun passo del ri-test. Token e
costo per run = 0, registrati nei report.

---

*Le voci seguenti vengono dalla revisione dell'utente della pre-registrazione `130b0fe`,
scritte nell'addendum `backtest/2026-09-15_preregistration-addendum-1.md` prima di qualunque
rendimento.*

## ADR-014 — 2026-09-15 — Intervallo clusterizzato: decide il CR1

**Contesto.** L'utente chiede che l'intervallo del verdetto sia clusterizzato per emittente,
«cluster bootstrap per emittente o CI da t CR1, non bootstrap semplice». Due metodi ammessi
possono dare risposte diverse sullo zero.

**Decisione.** Decide l'IC 95% da t CR1 (ADR-002). Il bootstrap per emittente (ricampionamento
degli emittenti con reinserimento, 1.000 draw, seed 12345) si riporta accanto; un disaccordo
sullo zero si scrive nel report ma non cambia il verdetto. Il bootstrap semplice compare solo
nella replica del passo 1.

**Alternative scartate.** Scegliere dopo, o richiedere che entrambi escludano lo zero: la prima è
una biforcazione sul risultato, la seconda aggiunge una regola che l'utente non ha dato.

## ADR-015 — 2026-09-15 — «Placebo ≈ 0»

**Decisione.** Placebo ≈ 0 ⟺ IC 95% CR1 include 0 **e** |media| < 1,5 punti percentuali.

**Conseguenze.** Un placebo largo e non significativo ma con media ampia (per esempio +3% con IC
[−1%, +7%]) non è ≈ 0. È la condizione che il test svedese avrebbe mancato: placebo +4,54%.

## ADR-016 — 2026-09-15 — Verdetto primario come tabella ordinata

**Contesto.** Tre istruzioni devono stare insieme: la regola «il matching col placebo più vicino a
zero», il matching con momentum «decisivo», e «sopravvive per dimensione, muore con momentum →
effetto reversal, NON REGGE». Con la nuova definizione di ≈ 0 la selezione dell'ADR-009 (per
|media P2| fra tutti i matching) poteva eleggere un matching col placebo fallito.

**Decisione.** Tabella ordinata R0–R6 dell'addendum, §4. Il placebo sceglie sel **solo fra i
matching con placebo ≈ 0**; il momentum ha diritto di veto: REGGE richiede che l'effetto
sopravviva anche a M_mom e che M_mom sia credibile. «Muore» = non sopravvive, incluso il caso con
media positiva e IC che include lo zero; la differenza evento per evento M_size − M_mom si riporta
per mostrare quanto è grande il calo. Questa voce **sostituisce la regola di scelta dell'ADR-009**;
le finestre P1 e P2 dell'ADR-009 restano.

**Alternative scartate.** Rendere M_mom sempre il matching di riferimento: contraddirebbe la regola
del placebo che l'utente ha confermato. Lasciare la scelta dell'ADR-009 invariata: permetterebbe un
REGGE su un matching col placebo fallito.

## ADR-017 — 2026-09-15 — Popolazione primaria: un evento per emittente ogni 365 giorni

**Contesto.** La cella originale ha 3.276 eventi su 1.110 emittenti: il cooldown di 126 giorni non
la rende «uno per emittente». L'utente chiede il primo evento per emittente per finestra di 12
mesi, «come in Svezia».

**Decisione.** `cooldown_filter(eventi, days=365)` di `tools/backtest_event_time.py`, invariato,
applicato dopo cancello e fascia. 2.340 eventi, 1.110 emittenti, 2,11 per emittente, 2.300
misurabili. La variante (b) a 126 giorni resta solo nella replica.

**Conseguenze.** In Svezia la variante (b) era a 126 giorni: questa regola è più severa, e lo si
scrive. Con 2,11 eventi per emittente il CR1 serve ancora. L'MDE sale a 3,84–4,24%, sopra il
finding.

## ADR-018 — 2026-09-15 — Sopravvivenza: S0 e S1 obbligatori, e cosa ne segue

**Contesto.** L'utente rende obbligatori S0 (−100%) e S1 (+15%) per i 17.581 eventi senza serie
prezzi, e fissa: se il segno del risultato cambia fra S0 e S1, il verdetto è INCONCLUSIVO.

**Decisione.** Scenari applicati agli `ENDED_IN_WINDOW` della popolazione primaria e ai delistati
attesi in cella, stimati per anno con ρ_y (addendum §5.2). Gli eventi con prezzi ma senza market
cap non entrano negli scenari. La regola R0 è la prima della tabella.

**Conseguenze, calcolate prima dei rendimenti.** n_u/n_o = 0,486. Il segno sotto S0 resta positivo
solo con un eccesso osservato sopra +48,6% (+51,1% se i peer rendono +5%); sotto S1 diventa
negativo solo sotto −7,3% (−4,9%). **REGGE non è raggiungibile in pratica, e fra circa −5% e +49%
il verdetto è INCONCLUSIVO per sopravvivenza.** La regola si applica come scritta; una modifica va
fatta prima del passo 2 in un file nuovo.

**Alternative scartate.** Applicare gli scenari ai soli 3 `ENDED_IN_WINDOW`: non è la regola data.
Applicarli anche agli 11.775 eventi con prezzi e senza cap: non sono delistati.

## ADR-019 — 2026-09-15 — Note della revisione

**Decisione.** Il verdetto secondario (criterio svedese) è INCONCLUSIVO per copertura (54,4% < 60%)
ed è scritto nell'addendum prima dei rendimenti. La cella 4/4 è non testabile (al più 5 eventi).
Il taglio a $25.000 per riga è una proprietà del corpus, non una scelta del test.

## ADR-020 — 2026-09-15 — Ingresso sul calendario comune: mai un prezzo anteriore

**Contesto.** L'ADR-004 e il §7 della pre-registrazione prendono il prezzo di ogni gamba come
«ultimo close ≤ sessione entro 5 sessioni». All'ingresso, per un titolo che non scambia nella prima
sessione dopo il deposito, è il close del giorno del deposito o di prima: un prezzo che precede la
pubblicazione. Trovato scrivendo il ponte del passo 1, prima di calcolare un rendimento sul
calendario comune.

**Decisione.** Gamba dell'evento: ingresso = prima barra del titolo con data ≥ prima sessione dopo
il deposito, entro 5 sessioni; la sua sessione è e0; uscita a e0 + h con ultimo close ≤ sessione
entro 5 sessioni. Peer e IWM: ultimo close ≤ sessione entro 5 sessioni, alle stesse e0 ed e0 + h.
Addendum 2.

**Alternative scartate.** Ultimo close ≤ sessione anche all'ingresso dell'evento: lookahead.
Ingresso del peer in avanti come per l'evento: le tre gambe partirebbero da sessioni diverse e la
scomposizione non sarebbe più esatta, per evitare un rischio che sul peer non c'è.

**Verifica.** Nel codice del ponte: nessun ingresso dell'evento ha data ≤ data di deposito.

## ADR-021 — 2026-09-15 — Correzione della verifica dell'ADR-002

**Contesto.** L'ADR-002 dice che con un cluster per osservazione la t CR1 «deve coincidere con la t
iid moltiplicata per √(G/(G−1))». È sbagliato.

**Decisione.** Con cluster singoli Σ_g u_g² = Σ_i u_i² = (N − 1)·s², quindi
V = G/(G−1) · (N−1)·s² / N² con G = N, cioè V = s²/N: **la t CR1 coincide esattamente con la t
iid.** La verifica corretta è l'uguaglianza; il codice del passo 1 la asserisce prima di usare la
funzione.

**Conseguenze.** Nessuna sui numeri: la formula dell'ADR-002 era giusta, era sbagliata solo la
proprietà con cui verificarla.

---

*Le voci seguenti vengono dall'addendum 3, `backtest/2026-09-15_preregistration-addendum-3.md`,
scritto dopo la revisione dell'utente e prima di qualunque rendimento del passo 2.*

## ADR-022 — 2026-09-15 — Prima la mappatura dei ticker; nessuna seconda fonte

**Contesto.** Dei 2.425 emittenti senza serie prezzi, 161 hanno ancora un ticker su EDGAR: sono
guasti di mappatura (per esempio FNTE → IMXI, CSAL), non
società terminate. L'utente chiede di risolverli prima di qualunque classificazione.

**Decisione.** Serie cercata per i ticker di oggi in `prices/` e in `prices_resolved/`, scaricata
il 2026-09-15 in una directory separata per non toccare l'impronta di `prices/`. RISOLTO se c'è
una barra entro 5 sessioni dall'ingresso; VIVO_SENZA_STORIA se la serie comincia dopo;
GUASTO_FONTE se non c'è serie. Osservati con serie finita in finestra: giuntura a rapporto 1 se
il CIK ha una serie che riprende entro 5 sessioni.

**Alternative scartate.** Una soglia di continuità sulla giuntura: il giorno di una fusione può
avere un salto vero. Una seconda fonte: non esiste nel repo (verificato su codice, directory e
storia git).

**Conseguenze.** 21 eventi della cella P restano in GUASTO_FONTE su ticker che quotano: è un
guasto di yfinance, non un fatto sulle società.

## ADR-023 — 2026-09-15 — Fascia dei non osservati dal prezzo insider

**Contesto.** Un evento senza serie non ha market cap e quindi non ha fascia: gli scenari
dell'addendum 1 lo stimavano per quota annua. Il prezzo d'esecuzione dell'insider esiste per tutti
e 2.425 gli emittenti senza serie.

**Decisione.** Cap = azioni XBRL point-in-time × prezzo medio ponderato delle righe dell'evento.
Popolazione per fascia sull'unione di osservati e non osservati.

**Verifica.** Sugli osservati la stessa fascia della cap del backfill nell'88,9% di 31.501 eventi.

**Conseguenze.** Gli eventi non osservati diventano contabili uno per uno invece che stimati.
Senza azioni XBRL (5.441 eventi) restano senza fascia.

## ADR-024 — 2026-09-15 — Classificatore d'uscita, e la finestra che lo rende pertinente

**Contesto.** Una classe d'uscita dice qualcosa sul rendimento di un evento solo se l'uscita cade
dentro la sua finestra: per un acquisto del 2015 su una società acquisita nel 2019, i 126 giorni
del 2015 hanno avuto un rendimento normale, solo non osservato. Nella misura esplorativa, 852 dei
16.390 eventi residui (5,2%) hanno la terminazione in finestra.

**Decisione.** Classe per precedenza fallimento (8-K 1.03) > liquidazione (nome) > acquisizione
(DEFM14A, DEFM14C, SC TO-T, SC 13E3, SC 13E-3, SC TO-C, più SC 14D9 e 8-K 5.01) > volontario/OTC > non risolto, su
W = [T_end − 365, T_end + 30]. Scenari solo per `TERMINATO_IN_FINESTRA`; `USCITO_PRIMA` fuori dal
campione; `USCITO_DOPO` vivi non osservati.

**Alternative scartate.** Applicare la classe d'uscita a tutti gli eventi dell'emittente: avrebbe
dato −100% o un prezzo di deal a finestre in cui la società era viva.

## ADR-025 — 2026-09-15 — Validazione del classificatore: 40 emittenti, soglia 90%

**Decisione.** Campione a seme 20260915 costruito sui terminati in finestra della cella P;
etichette vere lette sui documenti con la classe del classificatore in un file separato, non
aperto prima; concordanza sotto il 90% → classificatore non usato, terminati in finestra a S_zero.

**Conseguenze.** Il verdetto non dipende dal classificatore in nessun caso: si legge su osservati
e risolti. Il classificatore decide soltanto la tabella degli scenari.

## ADR-026 — 2026-09-15 — S_acq dal prezzo del deal, solo contanti

**Contesto.** L'utente chiedeva per S_acq «l'ultimo prezzo disponibile, che già incorpora il
deal». Per un delistato quel prezzo non esiste in nessuna fonte del repo.

**Decisione.** Prezzo per azione del deal letto dal filing (8-K 5.01/2.01/8.01, DEFM14A/C,
SC TO-T) con regex dichiarate; solo contanti; misti, azioni, ambigui a S_zero con flag. Ingresso
al prezzo insider, flag `INGRESSO_NON_ALLA_DATA_DI_DEPOSITO`. Guardia: rapporto deal / prezzo
insider fuori da [0,05; 20] → S_zero, flag `IMPLAUSIBILE`.

**Alternative scartate.** Un premio forfettario (+15%): rifiutato dall'utente. Il valore dei deal
in azioni col prezzo dell'acquirente: una catena di assunzioni per pochi eventi.

## ADR-027 — 2026-09-15 — R0′ al posto di R0; S1 abolito

**Decisione.** Il test di segno riguarda solo i terminati in finestra senza classe (S_zero → S0).
Nella cella P, esplorativo, sono 1 evento: **R0′ non vincola il verdetto**, e lo si scrive.

**Conseguenze.** Con la R0 dell'addendum 1 REGGE era irraggiungibile (n_u/n_o = 0,486); con R0′ il
verdetto dipende dai dati osservati, come chiesto dall'utente.

## ADR-028 — 2026-09-15 — Vivi non osservati fuori dal verdetto, con il limite k

**Decisione.** USCITO_DOPO, VIVO_SENZA_STORIA e GUASTO_FONTE fuori dal verdetto, riportati come
copertura. Limite descrittivo sui soli USCITO_DOPO: media_k = m − k · n_u / (n_v + n_u) per k in
{0, 5, 10, 20}, e k\* = m · (n_v + n_u) / n_u accanto al verdetto.

**Conseguenze.** Il lettore vede di quanti punti dovrebbero aver fatto peggio gli usciti perché
il risultato sparisca, invece di un aggiustamento inventato.

## ADR-029 — 2026-09-15 — Tetto di 200 chiamate EDGAR, applicato nel codice

**Decisione.** Contatore persistente in `step2_prep/edgar_calls.json` sommato fra le esecuzioni;
la chiamata oltre il tetto non parte e il documento mancante manda l'evento a S_zero con flag
`NON_SCARICATO`. Sequenziale, 0,15 s fra le richieste, User-Agent dichiarato.

**Alternative scartate.** Un tetto solo dichiarato: un budget che dipende dal ricordarsene non è
un budget.

---

*Le voci seguenti vengono dall'esecuzione del passo 2 e del passo 4.*

## ADR-030 — 2026-09-15 — Passo 2: scelte d'implementazione non fissate dalle pre-registrazioni

**Contesto.** Scrivendo `backtest/rematch_50_300m/step2_analysis.py` sono emersi punti che la
pre-registrazione e i tre addenda non fissano. Vanno decisi prima del primo rendimento, non dopo.

**Decisione.** Scritte nel docstring e committate con il codice (`8777757`) dopo un giro
`--diagnostica` che conta pool, abbinamenti e stati delle gambe senza calcolare una media:
- ticker del peer: fra i ticker del CIK nel corpus con serie in `prices/`, il più recente
  (pool di 4.819 emittenti contro i 4.765 dell'ADR-005, che contava i ticker per un'altra via);
- D non di borsa: close all'ultima sessione ≤ D, azioni XBRL con `filed` ≤ D esatto;
- standardizzazione di M_mom con sd di popolazione;
- cap dell'evento non ricalcolabile (226 eventi su tre celle): distanza con la cap della fascia;
- peer finito prima dell'uscita: ultimo close piatto; fermo più di 5 sessioni: coppia esclusa;
- terminati in finestra: nessun r12, quindi negli scenari di entrambi i matching entra il peer
  M_size scelto con la cap insider; cambio EUR alla sessione s0;
- giuntura: primo ticker di oggi, nell'ordine delle submissions, che riprende entro 5 sessioni.

**Conseguenze.** Dopo il primo giro sono state corrette due frasi del report, solo testo (R0′
senza sel, n della cella 4/4): `numbers.json` identico byte per byte (`82754b8`). Esito: **R1,
INCONCLUSIVO** — P2 non ≈ 0 né per M_size (+4,53%, t CR1 2,92) né per M_mom (+3,31%, t CR1 2,33).

## ADR-031 — 2026-09-15 — Passo 4 senza matching di riferimento; solo gli shard necessari

**Contesto.** Il §8 chiede il closed period «contro il matching primario», e il passo 2 ha dato
R1: sel non esiste. Degli shard delle submissions della cella P, 379 non sono in cache, ma molti
coprono anni precedenti al corpus (per esempio 1996–2009).

**Decisione.** Si riportano tutti e tre i confronti — vs IWM, vs M_size, vs M_mom — per ciascun W.
Si scaricano solo gli shard il cui intervallo [filingFrom, filingTo] interseca [T − 200 giorni,
T] di almeno un evento, con tetto nel codice pari ai 373 dichiarati al §0 della pre-registrazione;
l'evento il cui shard non arriva va a UNKNOWN con flag `SHARD_NON_SCARICATO`.

**Alternative scartate.** Promuovere M_size a primario per il passo 4: sarebbe una scelta fatta
dopo aver visto i risultati. Scaricare tutti gli shard mancanti: chiamate su anni che nessun
evento tocca.

## ADR-032 — 2026-09-15 — Addendum 4: correzione §15.4, post-hoc, validata prima dell'uso

**Contesto.** Nel passo 2 il rendimento del peer contro IWM scende con la fascia. Misura
descrittiva con f = prezzo del Form 4 / `Adj Close` alla stessa sessione: nella cella P hanno
f < 0,67, cioè un reverse split successivo, il 14,8% dei peer contro il 6,8% degli eventi, e
quei peer rendono −13,86% contro IWM. L'utente: «La correzione §15.4 rientra nel budget
sopravvivenza residuo».

**Decisione.** cap corretta = azioni as-reported × `Adj Close` × F(D), con F dagli split
rilevati nelle riesposizioni XBRL delle `companyfacts` in cache e accettati con la regola
dell'addendum 4 §4. Validazione su 40 split letti nei documenti, soglia 90%, dentro le 97
chiamate residue del tetto dell'addendum 3. Il ricalcolo è **POST-HOC**: il verdetto di
registro resta R1 e la sostituzione è una decisione dell'utente. Ci si ferma dopo la
validazione.

**Alternative scartate.** Togliere dal pool i candidati con uno split futuro: condiziona sul
futuro, un lookahead di segno opposto. Rilevare gli split dai salti delle azioni as-reported:
216 confermati contro 273 discordi. Scaricare gli split da yfinance: nessuna chiamata
autorizzata oltre quella del 2026-09-15.

**Conseguenze.** Restano non corretti gli split non rilevati e la rettifica per dividendi
dell'`Adj Close`. I casi con finestra a cavallo di D si contano.

## ADR-033 — 2026-09-15 — Addendum 4: rilevatore di split non valido, nessuna correzione §15.4

**Contesto.** Validazione pre-registrata (addendum 4 §5): 40 split estratti a seme 20260915,
etichette lette sui documenti e committate (`878445a`) prima di aprire il rapporto del
rilevatore.

**Esito.** 33 su 40 = **82,5%**, sotto la soglia del 90%. Discordanze:
- 5 etichette diverse da SPLIT: 4 NON_DETERMINABILE (un caso senza documenti, un rapporto non
  scritto, una sola forchetta, split fuori finestra) e 1 NESSUNO_SPLIT (clausola generica);
- 2 rapporti diversi: Calyxt 0,2 contro 0,1 letto, EzFill 49,9 contro 0,4 letto.

**Decisione.** Come pre-registrato, la correzione non si applica e il ricalcolo non si fa. §15.4
resta un limite dichiarato: non si corregge con i dati in cache e con questo rilevatore.
`step2c_prep/split.json` **non va usato come F(D)**, né dal ri-test né da altri backtest.

**Osservato dopo, descrittivo e senza effetto.** Almeno tre falsi positivi (Reservoir Media 7,96,
EzFill 49,9, InspireMD 50,0) sono riesposizioni legate a fusioni o de-SPAC, con rapporti che il
filtro accetta come puliti (≈8, ≈50). Stringere adesso la lista o il limite di 50 vorrebbe dire
calibrare sulla validazione; si fa solo con un nuovo addendum e un nuovo campione.

**Conseguenze.** Il verdetto di registro resta R1. Il difetto misurato (peer con f < 0,67 nel
14,8% dei casi contro il 6,8% degli eventi) resta un'ipotesi quantificata, non corretta.
Chiamate EDGAR del tetto dell'addendum 3: 182 su 200.

## ADR-034 — 2026-09-15 — Correzione dello split lookahead con la tabella di Yahoo

**Contesto.** L'utente chiede la correzione §15.4 una volta sola. Il rilevatore
XBRL ha fallito la validazione (ADR-033) e non si ritocca senza un nuovo campione. Scelta dell'utente fra
tabella di Yahoo, nuovo addendum XBRL e nessuna correzione: **Yahoo**.

**Decisione.** Addendum 5 del ri-test: F = prodotto degli split della tabella fra la data delle azioni e
l'ultima barra; validazione senza rete col prezzo insider (regola dell'addendum 4 §4), soglia 90% dei
verificabili; ticker senza tabella a F = 1 con flag.

**Alternative scartate.** Ritoccare il filtro XBRL dopo aver visto la validazione fallita: calibrazione
sulla validazione. Una validazione documentale a campione: costa chiamate EDGAR e verifica meno split di
quella sui prezzi insider, che li prende tutti quelli verificabili.

**Conseguenze.** 1.777 ticker su 5.835 restano senza tabella: Yahoo non li serve più (404 sull'endpoint dei
prezzi, verificato). Fonte integrativa scelta dall'utente fra EDGAR mirato, FINRA + EDGAR, un fornitore a
pagamento e nessuna: **EDGAR mirato** (addendum 5 §2.1) sui soli ticker usati che mostrano un salto del
rapporto insider, split accettato solo se il rapporto letto spiega il salto, tetto 500 chiamate. Gli altri
restano a F = 1, contati.

## ADR-035 — 2026-09-15 — Ri-test: ricalcolo post hoc, R1 resta, filone insider chiuso

**Decisione dell'utente.** R1 resta INCONCLUSIVO; il ricalcolo con la correzione dell'addendum 5 è post hoc
e descrittivo; dopo, il filone insider è chiuso. Nessun passo 4 o 5 corretto.

## ADR-036 — 2026-09-15 — Chiusure: E2, E3, sessione parallela

**Decisione dell'utente.** E2 ed E3 per ora non si fanno.
La sessione parallela sul ri-test è stata chiusa su richiesta dell'utente; il suo lavoro è nei commit
`0a11a4d`, `4d6228d`, `ade3092`, `878445a`, `dad7fcd`, `c4563f1` e negli ADR-032 e 033.

## ADR-037 — 2026-09-15 — Tabella degli split di Yahoo non valida: nessuna correzione, filone insider chiuso

**Esito** (`backtest/splits_validazione.md`, addendum 5 §4, zero chiamate): **590 confermati, 31 piatti, 65
discordi su 686 verificabili = 86,0%**, sotto la soglia del 90%; 1.204 split non verificabili.

**Decisione, come pre-registrato.** La correzione dello split lookahead **non si applica da nessuna parte**. L'integrazione EDGAR dell'addendum 5 §2.1 non si esegue (**zero chiamate**; la selezione
dei salti, 356 ticker e 855 finestre, resta in `state/backfill/splits_salti.json`). Il ricalcolo post hoc del
ri-test non si fa: **R1 resta, e il filone insider è chiuso** (ADR-035).

**Osservato dopo, descrittivo.** Con acquisti e vendite la selezione trova 356 ticker con un salto, contro i
154 della misura con i soli acquisti fatta prima dell'addendum. Le discordanze non sono state lette una per una:
possono venire dalla tabella o dal prezzo insider (classi di azioni, prezzi non di mercato). Né la soglia né la
regola si toccano dopo l'esito.

**Conseguenze.** §15.4 resta un limite dichiarato, ora con due tentativi di correzione
falliti (ADR-033, ADR-037).

## ADR-038 — 2026-09-17 — Russell 2000, uscite verso il basso: fermata 1, tre problemi e tre decisioni aperte

**Contesto.** Direttiva dell'utente del 16 settembre; nel piano l'utente ha scelto partecipazioni SEC trimestrali per la
composizione e Yahoo per prezzi e volumi. Ramo `feat/russell-exits`, cartella `backtest/russell_exits/`. **Nessun
rendimento extra calcolato o guardato.**

**Fatto (fase 0).**
- Date 2015-2025 e dicembre 2026 con fonte (`date_ricostituzione.csv`): ufficiali 2017, 2019-2025; 2015 e 2018 testo
  ufficiale da estratto o ristampa; 2016 solo fonti terze. Tutte sedute del calendario di IWM.
- File storici iShares: non disponibili. Depositi SEC di iShares Trust letti per IWM (S000004344) e IWB (S000004347):
  42 istantanee su 44 (31 marzo da N-CSR voce 6 o N-PORT-P; 30 giugno da N-Q o N-PORT-P). **30 giugno 2019 assente.**
  Tre formati HTML gestiti. Chiamate EDGAR per il Russell: 1.012 su un tetto di 3.000.
- Identità nome → CIK con verifica del prezzo implicito (valore / azioni del fondo contro la chiusura Yahoo, entro 3%):
  verificate dal 46% delle righe di IWM (marzo 2015) all'88% (marzo 2025); quasi tutte le altre senza prezzi Yahoo.
- Prova parallela FTSE Russell di novembre 2025: interna, liste pubbliche non trovate.
- Test: `test_ingressi.py` (troncamento, 360 prove), `test_filtri.py`, tutti superati.

**Problema 1 — la definizione trimestrale perde le uscite quando la ricostituzione è vicina al 30 giugno.** Controllo
esterno contro la lista ufficiale FTSE Russell delle cancellazioni 2025 (`controllo_2025.md`): con «assente a giugno»
si ritrovano **33 delle 147** cancellazioni ufficiali presenti in IWM a marzo. Motivo: nel N-PORT del 30 giugno 2025 le
società cancellate ci sono ancora con **posizioni residue** (GoPro 9% delle azioni di marzo, Chegg 7%, iRobot 2%).
Con «assente, oppure azioni ≤ 50% di marzo» si ritrovano **134 su 135** abbinate per nome (99%); 176 segnate, 134 nella
lista. Nel 2015-2023 le posizioni residue sono 1-6 all'anno: la differenza fra le due regole è piccola.

**Problema 2 — il 30 giugno 2024 è una fotografia di prima della ricostituzione.** Ricostituzione venerdì 28 giugno
2024, regolamento a un giorno lunedì 1 luglio: nell'istantanea del 30 giugno 2024 le società entrate sono 17 contro le
190-285 degli altri anni, le uscite 41. Il 2024, come il 2019, non ha un file «dopo» utilizzabile.

**Problema 3 — senza delistati si perde più di metà delle uscite.** Con la regola attuale 1.640 uscite verso il basso;
**952 escluse per identità**, di cui 898 senza prezzi Yahoo (in gran parte società delistate dopo); 558 escluse dai
filtri (il flusso di cassa operativo positivo esclude 350 delle 671 uscite che arrivano ai filtri). Restano **113 casi**
in 9 anni, vicino alla soglia di 100 della direttiva, e i casi rimasti sono selezionati fra chi sopravvive.

**Descrittivo, già utile.** Regola d'ingresso: in nessuno scaglione più della metà degli ingressi cade agli estremi
(B1 30%, B2 31%, B3 33%); mediana d'ingresso 21, 28 e 53 sedute dopo la ricostituzione.

**Decisioni aperte (dell'utente, prima di fissare regole e verdetti).** (1) Definizione dell'uscita: «assente» oppure
«assente o azioni ≤ 50% di marzo». (2) 2019 e 2024: esclusi, oppure istantanea del 30 settembre come «dopo». (3) Prezzi:
restare su Yahoo con la perdita dichiarata, oppure una fonte con i delistati (per esempio EODHD, €19,99 al mese).

**Scelte tecniche fatte in esecuzione.** File dei prezzi con nome riservato di Windows (`CON.csv` è la console): prefisso
«_»; serie in array compatti e filtri XBRL calcolati una volta per società (i companyfacts in memoria bloccavano la
macchina); `backfill_gates.four_quarters` non usato (somma trimestri duplicati o non consecutivi).

## ADR-039 — 2026-09-17 — Russell 2000, uscite verso il basso: falsi positivi 2025 sopra il 10%, fermo per la decisione dell'utente

**Contesto.** Decisione dell'utente sul problema 1 di ADR-038: uscita = «assente o al massimo il 50% delle azioni di
marzo, e non in IWB», azioni rettificate per frazionamenti e raggruppamenti, altrimenti quota del capitale detenuta da
IWM; falsi positivi 2025 contro la lista ufficiale; **oltre il 10% dei casi di un anno ci si ferma e si chiede**.
Nessun rendimento calcolato. Addendum non ancora scritto.

**Misura (`risultati/falsi_positivi_2025.md`).** Lista ufficiale: 152 cancellazioni dal Russell 3000; 141 trovate in IWM
al 31 marzo (ticker verificato o nome).

| | CUSIP esatto | per emittente |
|---|---:|---:|
| ritrovate | 140 su 141 | 139 su 141 |
| uscite segnate | 174 | 165 |
| falsi positivi | 32 (18,4%) | 24 (14,5%) |
| … stesso emittente con un CUSIP nuovo | 8 | 0 |
| … acquisite, in fusione o delistate fra il 31 marzo e la ricostituzione | 23 | 23 |
| … senza spiegazione | 1 | 1 |
| falsi positivi senza le acquisite nel trimestre | 9 (5,2%) | 1 (0,6%) |

Le 23 acquisite o delistate nel trimestre hanno Form 25 o 15-12 e 8-K voce 2.01 (una 1.03) fra il 31 marzo e il 27
giugno: la fase 1 le esclude già prima dei filtri. Senza spiegazione: Solo Brands (assente da IWM a giugno, non nella
lista). Non ritrovate: Ramaco classe B (la lista cancella la classe B, qui abbinata alla A) e X4 Pharmaceuticals (60,9%
delle azioni di marzo rettificate).

**Date (`risultati/controllo_date_giugno.md`).** Il periodo di giugno (30 giugno) è successivo alla ricostituzione in
tutti gli anni con deposito. Sedute dopo la ricostituzione: 2-5 nel 2015-2018 e 2020-2023, **1 nel 2025, 0 nel 2024**.
Posizioni residue fra le uscite: 0-12 all'anno, 6 nel 2024, 111 nel 2025.

**Scelte tecniche (non previste dalla direttiva).**
1. *Abbinamento per emittente* fra marzo e giugno: una riga di giugno assente a marzo corrisponde a un titolo di marzo
   se ha le stesse prime sei cifre del CUSIP, lo stesso nome normalizzato o lo stesso CIK (candidato unico). Motivo:
   raggruppamenti, cambi di sede e fusioni inverse cambiano il CUSIP (Easterly, Scilex, MarketWise, Forge Global,
   Forward Air, Aerovate/Jade, Lions Gate/Starz): con il CUSIP esatto risultano uscite 8 titoli rimasti.
2. *Quota del capitale*: azioni di IWM di tutte le righe con lo stesso CIK / azioni in circolazione XBRL (dei, poi
   us-gaap, classi sommate) dell'ultimo deposito con `filed` non oltre la data dell'istantanea. Usata per 13 titoli.
3. *CIK ambiguo* (più candidati per lo stesso nome): vale il solo candidato con depositi di fine quotazione nel
   trimestre, se è uno (First Bancshares, SolarWinds).

**Decisione aperta (dell'utente).** La soglia del 10% è superata con il conteggio letterale (14,5% per emittente); è
sotto (0,6%) se si tolgono le acquisite nel trimestre, che non diventano casi. Chiamate EDGAR del Russell: 1.041 su 3.000.

## ADR-040 — 2026-09-17 — Prezzi EODHD: market-data come libreria, solo per i backtest nuovi

**Contesto.** L'utente ha sottoscritto un mese di EOD Historical Data (All World). L'archivio locale e il codice vivono
allora nel package `market-data` di un repo esterno (ADR 001-004 in `market-data/docs/adr/`). Questo repo non conosce
quel repo.

**Decisione dell'utente.**
1. `market-data` si installa **come libreria** nell'ambiente di questo repo; il codice di questo repo dipende solo da
   **`market_data.api`**, mai dai file dell'archivio né dal repo esterno.
2. **I backtest già pre-registrati restano con i prezzi Yahoo congelati** (`state/backfill/prices/`, impronte nelle
   pre-registrazioni, ADR-022).
3. **Solo i backtest nuovi usano EODHD, a partire dal Russell** (`feat/russell-exits`).

**Conseguenze.** Installazione quando `market_data.api` restituisce dati. Un test verificherà sull'AST che nessun
modulo importi `market_data` se non tramite `market_data.api`. Le liste di dipendenze (`requirements.txt`) aggiungono
`market-data` come dipendenza opzionale, come `yfinance`.

## ADR-041 — 2026-09-22 — Russell 2000, uscite verso il basso: la fermata 1 rifatta su EODHD

*Nota sulla numerazione.* La pre-registrazione del 16 settembre citava per filtri di qualità, peer, ingressi e
placebo quattro numeri di ADR che non erano mai stati scritti in questo registro (il primo era poi diventato la
decisione sui prezzi EODHD, ADR-040). *Sistemato il 22-09:* le quattro decisioni sono state scritte come
ADR-042 (filtri), ADR-043 (peer), ADR-044 (ingressi), ADR-045 (placebo), e la pre-registrazione ha una riga di errata
che rimanda a quei numeri.

**Contesto.** Il §9 della pre-registrazione diceva di rifare i conteggi «dopo le decisioni dell'utente sulla
definizione, sul 2024 e sulla fonte dei prezzi». Sono state prese tutte e tre, e il controllo dei falsi positivi
contro le liste ufficiali è passato (addendum del 21 settembre, aggiornato il 22): nessun anno sopra il 10% sulla
misura che decide.

**Decisioni dell'utente applicate.**
1. *Definizione* di ADR-039: assente o al massimo il 50% delle azioni di marzo rettificate, e non in IWB, con
   l'abbinamento per emittente.
2. *Istantanea «dopo» del 30 settembre* per il 2019 e il 2024, e per il 2024 gli eventi societari della fase 1
   contati fino a quella data, a condizione che ogni sparizione estiva esclusa abbia il suo deposito EDGAR
   (verificato: il 6,0% era 7,6%).
3. *Identità e prezzi dall'archivio EODHD* (ADR-040), letti solo tramite `market_data.api`.

**Scelte tecniche, non previste.**
1. *Il classificatore delle uscite è quello validato.* `analisi.py` usa `falsi_positivi.Anno.classe`, lo stesso che
   è stato confrontato con le liste ufficiali, quindi i casi sono esattamente quelli che hanno passato il controllo.
   Le righe si raggruppano per società (CIK dell'identità verificata) e la società esce solo se escono tutte le sue
   classi (§3).
2. *La chiusura rettificata per i soli frazionamenti si ricostruisce* (`serie_eodhd.py`). Il §6 prescrive la `Close`
   di Yahoo, che EODHD non ha: si divide la chiusura grezza per i frazionamenti con data successiva. Verificato su
   Apple (frazionamento del 28-08-2020: la chiusura ricostruita coincide con quella di Yahoo). I frazionamenti sono quelli della tabella del fornitore più le note
   `split_del_fornitore` dell'archivio, dove la rettificata del fornitore attraversa il salto ma la tabella non ha il
   frazionamento; senza, la chiusura ricostruita salterebbe dove il titolo non ha fatto niente. Il volume EODHD è già
   rettificato per i frazionamenti, come quello Yahoo.
3. *Prezzi puliti* (`clean=True`): fuori i periodi esclusi dai controlli di qualità dell'archivio e le chiusure a
   zero. Un buco conta nella regola dell'80% di barre presenti.
4. *L'8-K voce 2.01 non esclude.* I due classificatori dei falsi positivi la usavano; il §3 elenca solo la voce
   1.03. La 2.01 la deposita anche chi compra o chi sopravvive a una fusione inversa. `analisi.py` era già giusto.
5. *Il 2019 con la stessa finestra del 2024.* Confermato dall'utente il 22-09: era già nella regola generale, gli
   eventi societari contano fra le due istantanee confrontate. Per il 2019 e il 2024 l'istantanea «dopo» è il 30
   settembre, quindi la finestra arriva lì.
6. *Tetto EDGAR invariato a 3.000* per tutto il Russell. `classifica_extra.py` era stato scritto con 6.000 ed è
   stato riportato a 3.000.

**Esito della fermata 1** (`risultati/conteggi.md`, addendum `2026-09-22_addendum_fermata1.md`). 230 casi in 11 anni
(24, 10, 5, 11, 35, 26, 61, 26, 9, 11, 12 dal 2015 al 2025), 227 sulla cella del verdetto B2 × 252: il criterio 1 di
REGGE (almeno 100 casi e 9 anni) è raggiunto. Con Yahoo e la definizione vecchia erano 113. Identità fra le uscite
88,5-95,8%, prezzi sufficienti 73,6-89,5%. Il collo di bottiglia è il filtro del flusso di cassa operativo (635
bocciati e 150 non verificabili su 1.364). Ingressi agli estremi 33-36% per scaglione, nessuno non decidibile.
230 falsi eventi per il placebo. 2.045 chiamate EDGAR su 3.000. **Nessun rendimento calcolato**: si aspetta la
conferma dell'utente.

## ADR-042 — 2026-09-16 (registrata il 2026-09-22) — Russell 2000, uscite verso il basso: filtri di qualità

*Decisione della pre-registrazione del 16 settembre (§4), che la citava con il numero poi usato per la decisione sui
prezzi EODHD (ADR-040); questa non era mai stata scritta. Contenuto preso dalla pre-registrazione, senza cambiamenti.*

*Nota della versione pubblica: sono i filtri di popolazione di questo test, fissati prima dei rendimenti; non sono
filtri validati né regole d'uso.*

Solo fatti con `filed` < Rank Day. Il titolo resta se tutti e quattro sono veri; un filtro non verificabile esclude, ed
è contato a parte da «non passa» (la direttiva dice «resta se»). Codice `filtri_xbrl.py`, test `test_filtri.py`.
1. Flusso di cassa operativo 12 mesi > 0: `NetCashProvidedByUsedInOperatingActivities` → `…ContinuingOperations`.
2. Cassa netta, oppure debito netto / EBITDA < 3; EBITDA ≤ 0 con debito netto > 0 = escluso. Debito e cassa con i tag
   di `tools/backfill_gates.py`; un debito mancante vale zero solo se il bilancio è letto (attivo o patrimonio alla
   stessa data della cassa); EBITDA = `OperatingIncomeLoss` + `DepreciationDepletionAndAmortization` →
   `DepreciationAndAmortization`.
3. Azioni in circolazione +5% o meno in 12 mesi: `dei:EntityCommonStockSharesOutstanding` → `us-gaap:
   CommonStockSharesOutstanding`, classi dello stesso deposito sommate, deposito più recente contro quello più vicino a
   365 giorni prima (fra 270 e 460), corrette per i frazionamenti fra le due date.
4. Nessuna fusione o acquisizione annunciata alle liste preliminari: nessun PREM14A/C, DEFM14A/C, SC TO-T/C, SC 13E3,
   SC 14D9 nei 365 giorni prima della data delle liste.

12 mesi = ultimo anno fiscale + progressivo corrente − progressivo dello stesso periodo dell'anno prima (senza anno
fiscale: quattro trimestri consecutivi); dati più vecchi di 270 giorni = non verificabile.
`backfill_gates.four_quarters` non si usa (somma trimestri duplicati o non consecutivi).

*Stato:* i frazionamenti del filtro 3 vengono dall'archivio EODHD invece che da Yahoo (ADR-041).

## ADR-043 — 2026-09-16 (registrata il 2026-09-22) — Russell 2000, uscite verso il basso: peer

*Decisione della pre-registrazione del 16 settembre (§5), che la citava con un numero mai scritto qui.
Contenuto preso dalla pre-registrazione, senza cambiamenti.*

- Universo: titoli **rimasti** in IWM che superano identità, esclusioni e gli stessi quattro filtri.
- Terzili del rendimento (chiusura rettificata) delle 126 sedute che finiscono al Rank Day, calcolati sull'universo
  dell'anno; il titolo in uscita va nel terzile delle stesse soglie.
- Capitalizzazione al Rank Day = valore della posizione di IWM al 31 marzo × chiusura al Rank Day / chiusura al 31
  marzo (stessa serie, rettificata per split). È proporzionale alla capitalizzazione flottante e non risente degli
  split; le azioni XBRL × prezzo sono scartate (azioni non rettificate per split; correzione non validata, ADR-033 e
  ADR-037).
- I 5 dello stesso terzile con capitalizzazione più vicina (distanza in logaritmo, pareggi al CIK minore); uscite con
  meno di 3 peer escluse e contate.
- Rendimento peer = media semplice dei peer **sulle stesse date di ingresso e uscita del titolo**; un peer senza prezzo
  all'ingresso esce dalla media (servono almeno 3). Peer o titolo delistato nella finestra: ultimo prezzo disponibile;
  prezzo dell'offerta in contanti quando il documento dell'offerta è in cache (`survival.leggi_deal`). Casi contati.

## ADR-044 — 2026-09-16 (registrata il 2026-09-22) — Russell 2000, uscite verso il basso: ingressi

*Decisione della pre-registrazione del 16 settembre (§6), che la citava con un numero mai scritto qui.
Contenuto preso dalla pre-registrazione, senza cambiamenti. Codice `ingressi.py`, test `test_ingressi.py`.*

Chiusure rettificate per i soli frazionamenti e volumi, sul calendario delle sedute.
- **A**: chiusura della ricostituzione (seduta r). **C**: r + 32.
- **B1, B2, B3** = (N, limite) (10, 60), (20, 126), (40, 189). Primo t con r + N ≤ t ≤ r + limite in cui:
  (1) nessuna chiusura delle sedute t−N+1 … t è sotto il minimo di chiusura dalle liste preliminari alla seduta t−N;
  (2) media del volume delle ultime 10 sedute ≤ mediana del volume delle 60 sedute che finiscono al Rank Day.
  Altrimenti ingresso forzato a r + limite. Una seduta con meno dell'80% delle barre nella finestra non decide. Nessun
  ingresso se manca il volume di riferimento o se i dati finiscono prima.
- Test obbligatorio superato: nessun prezzo o volume dopo la seduta d'ingresso cambia l'ingresso (360 prove).

*Stato:* la pre-registrazione diceva `Close` e `Volume` di Yahoo; ora sono quelli dell'archivio EODHD, con la
`Close` ricostruita dalla chiusura grezza (ADR-041).

## ADR-045 — 2026-09-16 (registrata il 2026-09-22) — Russell 2000, uscite verso il basso: placebo

*Decisione della pre-registrazione del 16 settembre (§8), che la citava con un numero mai scritto qui.
Contenuto preso dalla pre-registrazione, senza cambiamenti.*

- **Placebo falsi eventi** (per il verdetto della domanda 1, tenuta di un anno): per ogni anno, i rimasti dell'universo con la
  capitalizzazione più bassa non usati come peer, in numero pari alle uscite dell'anno con almeno 3 peer; stessi
  filtri, ingresso B2, peer dagli altri rimasti dell'universo (esclusi i falsi eventi stessi); rendimento extra a 252
  sedute.
- **Placebo di dicembre** (per il verdetto della domanda 2, le prime settimane dopo la ricostituzione): stesse uscite, finestra di 32 sedute che inizia 63 sedute
  dopo la ricostituzione.

**Un falso evento per caso, per costruzione.** Il numero dei falsi eventi di un anno è il numero delle uscite di
quell'anno con almeno 3 peer, per definizione: non è una coincidenza, ed è per questo che nei conteggi della fermata 1
le due colonne coincidono anno per anno (230 e 230). Il conteggio riportato è quello dei falsi eventi che a loro volta
hanno almeno 3 peer: se in un anno i rimasti candidati fossero stati meno delle uscite, o un falso evento avesse avuto
meno di 3 peer, le colonne sarebbero diverse. Non è successo in nessun anno.

*Correzione del 22-09, prima di qualunque rendimento.* Un difetto di lettura della cache EDGAR compressa (commit
`f4a7042`) nascondeva i depositi di 356 società; corretto, la fermata 1 passa da 230 a **234 casi** (+1 nel 2015,
+3 nel 2021), 231 sulla cella B2 × 252, e l'universo dei peer cresce (2015: da 355 a 411). Falsi positivi rifatti:
nessun anno sopra il 10%, il 2024 al 6,5%. Il codice dei rendimenti è congelato al commit `83456b7`, scritto prima di
questa correzione e prima di qualunque rendimento.

## ADR-046 — 2026-09-22 — E3: i due zip in blocco della SEC (companyfacts, submissions)

**Decisione dell'utente** (direttiva E3 del 22 settembre, fase 3). Il tetto di 3.000 chiamate EDGAR non basta per i
bilanci di migliaia di peer letti uno per uno, né per i loro elenchi di depositi. Si usano quindi i due file in
blocco della SEC, `companyfacts.zip` e `submissions.zip`, che costano una chiamata ciascuno.

Le condizioni dell'utente sono quattro:
1. **Point-in-time sulla data `filed`** del deposito, non sul periodo di bilancio. Un fatto depositato dopo la data di
   ingresso non esiste per il backtest, anche se sta nello zip.
2. **Manifest** in `state/backfill/sec_bulk/manifest.json`, con data di scaricamento e impronta sha256 dei due file.
3. **Si conservano** in `state/backfill/sec_bulk/` (ignorato da git) per i backtest successivi.
4. **8 GB liberi su C:**, controllati prima e durante lo scaricamento. Sotto la soglia ci si ferma e il file parziale
   si cancella.

**Esecuzione.** Scaricati il 22-09-2026:

| file | scaricato (UTC) | dimensione | sha256 |
|---|---|---:|---|
| `companyfacts.zip` | 09:18:03 | 1.409.282.747 byte | `5c41e1c2…20ea9b9` |
| `submissions.zip` | 09:19:47 | 1.564.856.408 byte | `b90668ca…2983523` |

Si leggono dentro lo zip, senza estrarli (`backtest/ipo_e3/bulk.py`). Le submissions delle società con molti depositi
sono divise in frammenti `CIK##########-submissions-NNN.json`, e si uniscono come faceva `survival.submissions`.

## ADR-047 — 2026-09-22 — E3: l'universo delle IPO dagli indici EDGAR

Regole in `backtest/ipo_e3/universo.py`, fase 0 punto 1 della direttiva.

**Candidati.** Ogni CIK con un 424B4 o un 424B1 depositato dal 2012 al 2024, preso dagli indici trimestrali
`form.idx`. Il 424B3 entra solo per i CIK che nella finestra non hanno né 424B4 né 424B1, e solo se cade vicino alla
prima barra.

**Quale prospetto è l'IPO.** Fra quelli del CIK, il primo che ha una prima barra di azioni ordinarie nell'archivio
EODHD entro 10 sedute, prima o dopo. Se nessuno ce l'ha, vale il primo prospetto del CIK nella finestra, e l'IPO si
conta «senza serie».

**Classe già quotata** (un'offerta secondaria scambiata per IPO). Il CIK ha nell'archivio un codice di azioni
ordinarie con barre più di 10 sedute prima del prospetto, ancora scambiato entro 10 sedute dal prospetto. Una classe
ferma da anni non conta.

**Esclusioni dalle submissions in blocco** (ADR-046), nell'ordine:
- SPAC (SIC 6770);
- REIT (SIC 6798);
- banche e casse di risparmio (SIC 6021, 6022, 6029, 6035, 6036);
- fondi chiusi (un deposito N-2);
- emittenti esteri o ADR (un F-1, F-6, 20-F, 40-F o 6-K prima del prospetto o entro un anno);
- entità non operative.

Le società costituite fuori dagli Stati Uniti che depositano come domestiche (10-K, 10-Q) restano, e si contano a parte.

**Conteggi.** I CIK con un prospetto sono 5.285. Gli esclusi:
- 1.178 con una classe già quotata;
- 607 SPAC;
- 604 esteri o ADR;
- 420 entità non operative;
- 75 REIT;
- 71 banche;
- 41 fondi chiusi.

Restano **2.289** IPO, di cui 1.804 con una serie di prezzi entro 10 sedute.

## ADR-048 — 2026-09-22 — E3 riaperto dalla direttiva dell'utente

L'ADR-036 chiudeva E2 ed E3, e una decisione successiva aveva già riaperto E2 come backtest sulle uscite dal Russell 2000. Con la
direttiva del 22 settembre, «Backtest E3: IPO rotte e IPO forti (USA, 2012-2024)», l'utente riapre E3. Questa decisione
supera l'ADR-036 per E3.

Regole della direttiva:
- **Due fermate:** la pre-registrazione con i conteggi e nessun rendimento extra, poi il verdetto.
- **Tetto EDGAR di 3.000 chiamate**, con un contatore proprio in `backtest/ipo_e3/edgar_calls.json`. È lo stesso
  `Budget` del Russell, a cui `sec.py` ora passa il file del contatore.
- **Nessuna spesa LLM.**
- **Prezzi** solo tramite `market_data.api` (ADR-040), con `serie_seguita` per i cambi di ticker.
- **Codice** in `backtest/ipo_e3/`; dati in `state/backfill/ipo_e3/`.

## ADR-049 — 2026-09-22 — E3: il prospetto letto con regole, le date e il lock-up

Fase 0, punti 2 e 4. I campi si leggono con espressioni regolari dal testo del documento principale del 424B4 o 424B1
(`backtest/ipo_e3/prospetto.py`), senza modello linguistico. Costa una chiamata per prospetto. Ogni campo porta la
citazione da cui viene.

**Prezzo di collocamento.** Le frasi della copertina nell'ordine, poi la riga della tabella. Un intervallo senza prezzo
vuol dire un prospetto non definitivo, e il campo resta vuoto.

**Data di collocamento.** La data della copertina. Se la copertina non la dice, la seduta prima della prima barra. Nel
pilota le due coincidono in 9 casi su 9 dove ci sono entrambe. Si contano i casi in cui distano più di 5 sedute.

**Durata del lock-up.** Contano due forme di frase, purché vicine a «lock-up», amministratori, dirigenti o azionisti:
- «N days after/following/from the date of this prospectus», anche con la virgola prima di «from»;
- «N-day lock-up/restricted period».

Se ne scartano due tipi:
- quelle sull'opzione dei collocatori;
- quelle sulla Rule 144 e sulle azioni vendibili: la tabella «90 days after the date of this prospectus» non è il
  lock-up.

Vale la durata più frequente; a parità, la più corta, che è la prima scadenza. Le altre durate si registrano come
eccezioni.

**Azioni offerte.** L'offerta base della copertina: società più eventuali azionisti venditori, senza l'opzione dei
collocatori. Si cerca prima la cifra del titolo, poi le frasi.

**Azioni in circolazione dopo l'offerta.** La riga «outstanding after this offering» del riepilogo. Fra la frase e il
numero non devono esserci parole come «includes», «excludes» o «based on».

**Esclusioni dal testo.** SPAC (trust account), unit, REIT dichiarato, nessun prezzo di collocamento, prezzo sotto $5.
Le società in accomandita e le LLC che offrono «common units» si segnano e si contano, ma **non si escludono**: la
decisione spetta all'utente alla fermata 1.

**Scadenza del lock-up.** Data di collocamento più la durata, in giorni di calendario come la scrivono i prospetti,
portata sulla prima seduta da quella data in poi: la seduta S. La data di controllo è S + 10.

**Pilota prima della lettura completa.** Su 24 prospetti a caso, due per anno (seme 20260922), le regole trovavano:

| campo | trovati su 24 |
|---|---:|
| prezzo | 22 |
| data | 11 |
| lock-up | 23 |
| azioni offerte | 7 |
| azioni dopo l'offerta | 11 |

Da lì vengono le correzioni descritte sopra:
- la virgola prima di «from»;
- la forma con il trattino;
- lo scarto delle frasi sulla Rule 144;
- la cifra del titolo per le azioni offerte;
- le parole vietate prima del numero delle azioni in circolazione.

Sono state tutte fatte **prima** di leggere l'universo, senza guardare prezzi o rendimenti.

**Verifica a mano.** Si fa su 30 prospetti estratti a caso dopo la lettura completa, con le regole ferme. Se la
precisione di un campo scende sotto il 90%, ci si ferma.

## ADR-050 — 2026-09-22 — E3: filtri di qualità, peer e ingressi

Fasi 2, 3 e 4. Il codice sta in `backtest/ipo_e3/filtri.py`, `peer.py` e `casi.py`.

*Nota della versione pubblica: i filtri sotto sono la definizione della popolazione del test, fissata prima dei
rendimenti; non sono filtri validati né regole d'uso.*

**Filtri delle rotte, alla data di ciascun ingresso (A, B, C).** Una rotta entra nella cella di un ingresso solo se a
quella data passa tutti e quattro i filtri. Un filtro «non verificabile», perché il dato manca, non passa, e si conta
a parte.

1. **Flusso di cassa operativo degli ultimi 12 mesi > 0.** `filtri_xbrl.f1_flusso_cassa`, sul companyfacts in blocco.
   I bilanci del prospetto non sono in XBRL, quindi vale il primo 10-Q o 10-K depositato prima dell'ingresso.
2. **Leva.** `filtri_xbrl.f2_leva`, invariato.
3. **Nessuna emissione dall'IPO**, due condizioni:
   - dal collocamento + 15 giorni all'ingresso, nessun deposito fra S-1 e S-3 (con le varianti),
     424B1/B2/B3/B4/B5/B7 e 8-K con la voce 3.02. Il 424B5 copre gli ATM, la voce 3.02 i convertibili e i
     collocamenti privati;
   - azioni cresciute al massimo del 5% dal primo deposito dopo il collocamento all'ultimo prima dell'ingresso,
     corrette per i frazionamenti.
4. **Nessuna fusione o acquisizione annunciata** fra il collocamento e l'ingresso: le forme di `survival.ACQ`, più
   PREM14A, PREM14C e 425.

Le forti passano solo il filtro 4, alla data di controllo.

**Universo dei peer.**
- Azioni ordinarie americane con CIK, quotate su una borsa: NASDAQ, NYSE, NYSE MKT/AMEX, BATS, NYSE ARCA.
- Quotate da almeno 3 anni, contati dalla prima barra del CIK su qualunque suo codice.
- Con una barra all'ingresso e una 126 sedute prima.
- Che passano i filtri 1 e 2 alla data d'ingresso.

**Scelta dei peer.**
- Terzile del rendimento a 6 mesi (`adjusted_close`), con i tagli calcolati sull'universo del giorno.
- Fra i titoli del terzile del caso, i 5 più vicini per capitalizzazione: chiusura grezza per azioni dell'ultimo
  deposito, con la distanza sul logaritmo.

I casi con meno di 126 sedute di storia all'ingresso (i lock-up corti) non hanno un terzile calcolabile: restano senza
peer, e si contano. Nessuna sostituzione: la decisione spetta all'utente alla fermata 1.

**Ingressi.**
- **A:** la prima seduta dopo la data di scadenza.
- **B:** `russell_exits/ingressi.ingresso_b`, con riferimento del volume e inizio del minimo in S, partenza dalla
  data di controllo, finestra di 20 sedute. Il primo giorno possibile è quindi S + 30, l'ingresso forzato S + 126.
- **C:** S + 63.
- **Forti:** entrano alla data di controllo.

**Copertura.** Servono almeno l'80% di barre fra la prima barra e la data di controllo, altrimenti l'IPO esce e si
conta.

## ADR-051 — 2026-09-22 — E3: la serie deve essere coerente con il prezzo di collocamento

**Contesto.** Il primo caso d'esempio della fermata 1, Barracuda Networks (CIK 1348334), usciva con un crollo quasi
totale dal collocamento. L'anagrafica dell'archivio è giusta: Barracuda, NYSE, CIK giusto, date di quotazione giuste.
I prezzi collegati invece non sono di Barracuda: la prima chiusura della serie è una piccola frazione del prezzo di
collocamento, e il primo giorno si scambiano poche migliaia di azioni invece di milioni. In più la serie ha un
raggruppamento datato dopo l'uscita di Barracuda dalla borsa, e nessuna segnalazione di qualità. Si tratta di un altro
titolo con lo stesso ticker.

Misurato sulle prime 406 IPO con prezzo e serie, il rapporto fra prima chiusura e prezzo di collocamento sta per 388
fra 0,5 e 3 volte. Gli altri sono di due specie:
- **titoli diversi:** Barracuda, Blackhawk;
- **serie già rettificate dal fornitore per raggruppamenti successivi:** Zosano, Heat Biologics, Biocept (con un
  prezzo segnaposto assurdo). `serie_eodhd` le rettificherebbe una seconda volta.

In tutti e due i casi la classificazione come rotta o forte sarebbe un artefatto.

**Decisione.** Un'IPO esce, contata come «prima chiusura incoerente con il prezzo di collocamento», se la prima
chiusura (entro 5 sedute dalla prima barra) divisa per il prezzo di collocamento sta fuori da **0,5-3**. Il rapporto
si calcola sulle stesse grandezze della classificazione (`casi.py`) ed è in `casi.csv` per ogni IPO.

La soglia alta può escludere un vero rialzo del primo giorno oltre il 200%. Nel campione misurato l'unico candidato
plausibile è Dicerna, appena sopra 3. I casi esclusi sono elencati per nome in `risultati/conteggi.md`, così chi legge li può
controllare.

**Da confermare dall'utente alla fermata 1**, come regola che non era nella direttiva.

**Limite.** La stessa incoerenza può toccare un peer. I peer non hanno un prezzo di riferimento con cui fare il
controllo: resta un limite dichiarato.

## ADR-052 — 2026-09-22 — E3: chiusura dell'ADR-051 e frazionamenti prima dell'IPO

**Contesto.** Alla fermata 1 l'utente ha confermato l'ADR-051, a una condizione: prima di chiuderlo andava guardata
la lista dei 20 esclusi, per non buttare un vero balzo o crollo del primo giorno. Sulle chiusure grezze, i volumi e
i frazionamenti dell'archivio, i 20 sono di tre specie:
- **15 errori di dato:**
  - serie già rettificate dal fornitore: Cempra, Ceres, Heat Biologics, Ardelyx, Roka, MaxPoint,
    ProNAi, Nant Health, FTS International, Charah, Kodiak;
  - titoli diversi con lo stesso ticker, con poche migliaia di azioni scambiate il primo giorno: Barracuda,
    SG Blocks, iPower;
  - Tenon Medical, senza nessuna chiusura pulita nelle prime 5 sedute;
- **3 balzi veri**, con chiusura grezza uguale alla rettificata, nessun frazionamento in archivio e volume da IPO:
  - Dicerna;
  - BigCommerce;
  - Code Rebel;
- **2 errori del codice:** William Lyon Homes e Nevro. L'archivio registra il raggruppamento fatto prima dell'IPO
  alla data della prima barra, e `casi.py` lo applicava una seconda volta al prezzo di collocamento, che lo contiene
  già. Con il rapporto corretto rientrano nella fascia.

**Decisione** (dell'utente, 22-09-2026):
1. soglia 0,5-3 invariata, con **eccezioni nominate** per i tre balzi veri (`casi.ECCEZIONI_051`, per CIK). Non si
   sposta la soglia: sarebbe tarata a posteriori su questa lista;
2. il prezzo di collocamento si riporta nelle unità della serie dividendo solo per i frazionamenti con data dopo la
   prima barra. È la regola del §4 della pre-registrazione, scritta giusto.

Le altre decisioni della fermata 1 stanno in `backtest/ipo_e3/2026-09-22_addendum_fermata1.md`.

## ADR-053 — 2026-09-23 — filtri_xbrl.py: plausibilità del fallback us-gaap:CommonStockSharesOutstanding

**Contesto.** In E3, `azioni_per_deposito` cade su `us-gaap:CommonStockSharesOutstanding` quando
`dei:EntityCommonStockSharesOutstanding` non è ancora disponibile alla data di riferimento. Il fallback può
restituire un numero non rappresentativo del totale azioni: il valore nominale di un guscio
pre-riorganizzazione (100, 1.000 azioni) o una sola classe di una società a classi multiple — l'API companyfacts
della SEC toglie l'informazione di dimensione/classe, quindi le due cause non si distinguono dal tag. Trovato
sui 331 casi «forti» di E3 (Taylor Morrison, Chewy, Lyft e altri 8), poi verificato sull'intero universo dei
peer (8.987 CIK, 179 con lo stesso fallback).

**Decisione — tre controlli in ordine, il primo disponibile decide (funzione pubblica `stato_plausibilita`):**
1. **rapporto vs `dei` futuro**: se un fatto `dei:EntityCommonStockSharesOutstanding` esiste depositato dopo la
   data di riferimento, il valore attuale deve essere almeno il 20% di quello — sotto, scartato;
2. **prezzo implicito dal flottante**: in mancanza di un `dei` futuro, se `dei:EntityPublicFloat` (val > 0) è
   disponibile vicino alla data di riferimento, `flottante $ / azioni` deve stare fra **$0,01 e $1.000** —
   fuori da questa fascia, scartato;
3. **soglia assoluta**: in mancanza di entrambi, sotto 100.000 azioni scartato; sopra, accettato ma marcato
   **`non_verificato`** (nessuna doppia conferma trovata).

Un valore scartato è tolto da `per` come se il dato non ci fosse — nessuna sostituzione silenziosa, stesso
criterio già in uso altrove nella pipeline per i dati mancanti.

**Calibrazione del tetto del punto 2** (23/09/2026, prima soglia provata: $100.000/azione). Sui peer con
flottante disponibile, i valori senza motivo di sospetto arrivano fino a $801,62; il minimo dei valori noti
sbagliati (Associated Capital Group, e la stessa Houlihan Lokey quando ricompare come peer ad anni di
distanza dalla sua data di caso, col flottante cresciuto nel frattempo) è $4.155,69. Margine pulito da $802 a
$4.155: scelto $1.000, con scarto su entrambi i lati. Il pavimento $0,01 resta invariato: nessun caso in tutta
questa indagine produce un prezzo implicito troppo *basso* — sottostimare le azioni alza sempre il prezzo
implicito, non lo abbassa mai, quindi non c'è un meccanismo osservato che giustifichi di stringere il minimo.

**Limite dichiarato, dimostrato prima di committare, non un errore di calibrazione.** Tre casi noti sbagliati
per confronto col prospetto — Houlihan Lokey ($447/azione alla sua data di caso E3), Aziyo ($44), Nuvalent
($76) — restano `ok`/`non_verificato` con qualunque tetto ragionevole: il loro errore (sottostima delle azioni,
10-450× circa) alza il prezzo implicito, ma non abbastanza da superare una soglia che non tagli fuori anche
titoli legittimi con prezzi altrettanto alti. Un controllo sul prezzo può intercettare solo gli errori
abbastanza grandi da produrre un prezzo assurdo (i gusci a 100-1.000 azioni, o un bug di scala): non può,
per costruzione, distinguere un errore moderato da un titolo vero che tratta a un prezzo comparabile.

**Scoperta collaterale.** Associated Capital Group (CIK 0001642122) non è un caso «classe parziale» come gli
altri: i depositi grezzi mostrano `us-gaap:CommonStockSharesOutstanding` corretto (~22 milioni) fino al 10-Q di
maggio 2023, poi un crollo a 22.015 nel 10-Q di agosto 2023 (÷1000, stesso pattern di errore di scala già
osservato su Chipotle nella verifica dei falsi positivi) — con la differenza che qui l'errore non si
autocorregge: si ripete in ogni deposito successivo fino all'ultimo disponibile. Causa diversa dal bug
originale, stessa via di accesso (fallback us-gaap senza `dei`), intercettato dallo stesso controllo di livello 2.

**Verifica.** 10 test di regressione in `backtest/russell_exits/test_filtri.py`, un caso per livello più i due
scarti attesi; tutti passano. Confronto sulle 190 unità che passano dal fallback in tutto E3 (11 casi + 179
peer): 47 righe passano da «accettate senza controllo» a «scartate» (azioni non disponibili); le altre 143
restano accettate con lo stesso valore di prima, ora tracciate come `ok` o `non_verificato`.

**Conseguenze.** Il referto E3 (`backtest/ipo_e3/risultati/`) non è toccato: la correzione riguarda
l'estrazione futura, non ricalcola nessun verdetto già chiuso. Nota per i backtest futuri che riusano
`filtri_xbrl.py`: il limite «classe parziale a prezzo implicito moderato» resta aperto, per costruzione — chi
userà questo codice su un nuovo universo dovrebbe aspettarsi lo stesso tipo di falso negativo silenzioso e,
dove possibile, incrociare con una fonte indipendente specifica del proprio caso (come il prospetto per E3),
non affidarsi al solo controllo del prezzo implicito.

## ADR-054 — 2026-09-27 — edge-lab non dipende da un repo esterno

**Contesto.** Fino a oggi `CLAUDE.md` diceva che un repo esterno conosce questo
repo e non il contrario, ma valeva solo per lo scanner. L'inventario del 27-09-2026 (in entrambe le direzioni: codice,
script, task, test, configurazione, dati) ha trovato quattro dipendenze vive da edge-lab verso il repo esterno:
`market_data` installato da lì; `market_data.config` che leggeva `MARKET_DATA_DIR` dal **`.env` del repo esterno**
(dipendenza nascosta: `REPO_ROOT = parents[2]` puntava lì); uno script di controllo che leggeva un file di stato del
repo esterno; lo User-Agent EDGAR impostato dagli script di lancio del repo esterno. In più un task pianificato partiva
da uno script del repo esterno.

**Decisione dell'utente.** edge-lab è un repo a sé e non dipende dal repo esterno in alcun modo. La regola «i dati si
leggono tramite market-data» resta; cambia solo dove vive market-data (ADR-055).

**Alternative scartate:** tenere market-data nel repo esterno e installarlo come pacchetto versionato (lo usa solo
edge-lab: verificato, nessun import nel repo esterno, nessun altro ambiente lo installa); leggere il file di stato come
file dall'archivio dati.

**Conseguenze.**
1. Un test di confine sull'AST fallisce se un modulo importa un package del repo esterno, se una stringa di codice
   (docstring escluse) nomina il repo esterno o i suoi file di stato, se uno script (`.sh`, `.cmd`, `.bat`, `.ps1`,
   righe di commento escluse) o un `requirements*.txt`/`pyproject.toml` (commenti compresi) lo nomina, o se il
   `market-data` installato non viene da `./market-data`. Tre eccezioni esplicite, ciascuna col motivo; un'eccezione
   che non serve più fa fallire il test.
2. Il lato del repo esterno si pulisce in un suo branch, non qui.
3. **Debiti registrati, non sistemati in questo passo:**
   - alcuni script con un vecchio percorso assoluto scritto nel codice, che non esiste più;
   - `market-data/market_data/quality/calendario.py:24` importa `exchange_calendars`, che il `pyproject.toml` di
     market-data non ha mai dichiarato (nel repo esterno era installato a parte): nel venv di edge-lab i test che lo
     toccano non girano. Da decidere con l'utente (nuova dipendenza).
   - `market-data/tests/test_update.py::test_barre_in_blocco_aggiunte_dopo_la_serie` falliva già nel repo esterno,
     prima del trasloco (verificato con l'interprete di quel repo): guasto preesistente, non introdotto qui.

**Verifica.** Il test di confine passa (19 controlli) con market-data reinstallato da `./market-data`. Letto: uscita
del test e `direct_url.json` del pacchetto installato.

## ADR-055 — 2026-09-27 — market-data vive dentro edge-lab, con la sua storia

**Contesto.** ADR-040 aveva deciso market-data come libreria installata dal repo esterno. L'unico consumatore è edge-lab
(6 moduli in `backtest/russell_exits` e `backtest/ipo_e3`); il repo esterno non lo importa e il suo venv non lo ha
nemmeno installato.

**Decisione dell'utente.**
1. market-data si sposta in `market-data/` di questo repo, **con la sua storia**: `git subtree split
   --prefix=market-data` nel repo esterno (43 commit) e `git subtree add --prefix=market-data` qui. Si installa in
   sviluppo dal repo stesso: `pip install -e ./market-data[archivio]`.
2. **ADR-040 resta valido nella sostanza**: il codice di edge-lab fuori da `market-data/` usa solo `market_data.api`
   (`tests/test_market_data_confine.py`, che ora esclude la cartella `market-data/` stessa: dentro il pacchetto i moduli
   si importano fra loro).
3. **Dipendenze facoltative** approvate dall'utente: duckdb, pyarrow, pandas (extra `archivio`; pandas aggiunto
   perché `api.py` restituisce DataFrame tramite `.df()`). Lo scanner gira senza.
4. **pytest per i test di market-data**: seconda eccezione alla regola delle suite piatte, dopo `edgar_llm/`
   (`edgar_llm/docs/adr/007-pytest-solo-qui.md`). `test.sh` li lancia come quelli di `edgar_llm`.
5. La protezione dei commit di market-data (`market-data/docs/adr/002-protezioni-git.md`) si porta qui:
   `.githooks/guard.py` e `.githooks/pre-commit`, attivati con `git config core.hooksPath .githooks` (anche in
   `setup.sh`); i suoi test in `tests/test_guard_precommit.py`.
6. `REPO_ROOT = parents[2]` in `market_data/config.py` ora punta a edge-lab: il `.env` letto è quello di edge-lab.
   Nessun cambio di logica; il rifiuto di un archivio «dentro il repo» vale per edge-lab.

**Alternative scartate:** copiare i file senza storia (si perdono 43 commit di decisioni); repo a sé versionato
(nessun secondo consumatore oggi: se il repo esterno avrà bisogno di prezzi, market-data diventerà allora un repo a sé
installato in entrambi, con versione).

**Conseguenze.** La copia nel repo esterno si toglie nel suo branch di pulizia. Le ADR di
market-data restano nella sua cartella (`market-data/docs/adr/`), come quelle di `edgar_llm/`: nuova ADR 007
(trasloco), aggiornate la 001, la 002 e la 004. `api.fred()` (con versioni storiche ALFRED) si costruirà qui, in
`market-data/market_data/`, e gli studi futuri lo useranno da qui senza scrivere un secondo lettore FRED.

**Verifica.** Il secondo genitore del merge del subtree è il commit dello split (43 commit dal primo scaffolding);
file tracciati e blob identici alla copia nel repo esterno (letti con `git ls-tree` nei due repo). Dopo la
reinstallazione `direct_url.json` punta a `edge-lab/market-data` e `api.trading_days("US", ...)` legge l'archivio.

## ADR-056 — 2026-09-27 — I task pianificati di edge-lab vivono in edge-lab

**Contesto.** Un task pianificato di edge-lab partiva da uno script di un repo esterno, con il percorso di edge-lab e
lo User-Agent (nome ed email) scritti dentro. Ogni nuovo task avrebbe avuto lo stesso problema.

**Decisione dell'utente.** I lanciatori stanno in una cartella di edge-lab (`pianificazione/`, lavoro operativo non
incluso in questa versione pubblica). Si collocano da soli (`cd /d "%~dp0.."`): nessun percorso assoluto, nessun nome o
email, lo User-Agent viene da `EDGAR_USER_AGENT` nel `.env` di edge-lab. Uno script PowerShell registra o aggiorna il
task di Windows; senza un parametro esplicito fa solo la prova a secco.

**Conseguenze.** **I task di Windows non si toccano fino a dopo la loro prossima esecuzione**: prima si legge il log di
quell'esecuzione, poi, con l'ok dell'utente, il task punta al nuovo script. `.gitattributes` fissa `*.cmd` a CRLF.

**Verifica.** Prova a secco dello script di registrazione: il task esiste e oggi punta allo script del repo esterno;
verrebbe aggiornato allo script di edge-lab. Letto: uscita della prova a secco, che interroga lo scheduler con
`Get-ScheduledTask`.

## ADR-057 — 2026-09-27 — Il percorso dell'archivio dati solo da configurazione

**Decisione dell'utente.** `MARKET_DATA_DIR` sta nel `.env` di edge-lab (ignorato da git; i nomi delle variabili in
`.env.example`), l'ambiente del processo vince sul file, nessun valore predefinito nel codice. Restano i rifiuti di
`market_data.config.archivio()`: percorso relativo, dentro edge-lab, dentro qualunque repo git.

**Conseguenze.** L'archivio deve stare in una cartella che non è dentro nessun repo git (per esempio una cartella
dedicata nella home dell'utente). Il repo esterno non ha più bisogno di `MARKET_DATA_DIR` né di `EODHD_API_KEY` (la
chiave c'era già nel `.env` di edge-lab).

**Verifica.** `market_data.config.archivio()` restituisce il percorso configurato leggendo il `.env` di edge-lab
(`REPO_ROOT` = edge-lab). Letto: uscita di Python con il venv di edge-lab.

## ADR-058 — 2026-10-07 — Debito: la qualità dei prezzi delle piccole società nell'archivio va verificata anche negli studi chiusi

**Contesto.** Lavorando a un backtest su un universo di piccole società USA si sono trovati nei prezzi puliti
dell'archivio (`api.prices(clean=True)`) due problemi che i controlli esistenti non vedono. (1) **Titoli persi per un
fatto successivo.** I prezzi puliti tolgono tutta la storia di un codice prima di un `salto_sospetto` non verificato:
uno studio che sceglie i titoli a una data perde quelli che **dopo** quella data hanno avuto un crollo vero vicino a un
rapporto di split (la metà, due terzi, tre quarti), e dal 2019 la verifica sui bilanci non è più possibile. (2)
**Prezzi sbagliati rimasti dentro.** Barre isolate (una chiusura che passa da qualche decina di centesimi a centinaia di dollari e torna al prezzo di prima il giorno dopo, con una manciata di titoli scambiati), serie che cambiano livello
perché sullo stesso codice proseguono azioni nuove dopo una riorganizzazione o un raggruppamento non rettificato, e
serie concatenate dopo un cambio di codice che non erano lo stesso titolo (warrant, privilegiate, altre classi). I
conteggi stanno in `market-data/docs/adr/011-barre-isolate.md` e `012-salti-di-livello.md`; il racconto in
`docs/method/data-quality.md`.

**Decisione.** In market-data sono nate tre opzioni esplicite, ciascuna con ADR e test: la verifica dei salti con le
azioni in circolazione depositate alla SEC (ADR 010 di market-data), lo scarto delle barre isolate (ADR 011) e
l'elenco dei salti di livello non spiegati (ADR 012). **Il default dei prezzi puliti non è cambiato**, perché cambiarlo
avrebbe cambiato in silenzio i numeri degli studi già chiusi; la prova che il default è identico riga per riga sta in
ciascuno dei tre ADR. Il prezzo di questa scelta è un debito, registrato qui: **gli studi chiusi non hanno usato
nessuna delle tre opzioni.**

**Gli studi pubblicati che leggono i prezzi puliti dell'archivio** (elenco meccanico: `grep` di `.prices(` e di
`clean=` nei sorgenti di `backtest/`; dice chi legge i prezzi puliti, non se ha perso o sbagliato qualcosa):

| studio | dove legge i prezzi puliti |
|---|---|
| E2, uscite dal Russell 2000 | `backtest/russell_exits/serie_eodhd.py`; da lì `analisi.py`, `rendimenti.py` |
| E3, IPO (peer dall'archivio) | `backtest/ipo_e3/peer.py`, `comune.py`; da lì `analisi.py`, `casi.py`, `filtri.py` |

Leggono solo i prezzi grezzi (`clean=False`), quindi fuori dal debito: `backtest/ipo_e3/salti.py`,
`backtest/russell_exits/verifica_identita_eodhd.py`. Il ri-test sugli insider non legge l'archivio (usa un panel di
prezzi diverso). Gli studi di eventi su società piccole o in difficoltà sono quelli in cui questi errori sono più
probabili, e in uno studio di eventi la direzione dell'errore dipende da quando cade la barra rispetto alla finestra:
**non è nota in anticipo.**

**Stato: aperto.** Nessuno studio chiuso è stato verificato né rieseguito, e nessun effetto è stato stimato. I
verdetti pubblicati di E2 ed E3 restano quelli registrati, con questa riserva dichiarata.

**Che cosa serve per chiuderlo.** Per ogni studio, sui titoli e sulle finestre che ha usato: i titoli senza chiusura
pulita alla data di scelta per un salto successivo, classificati con `api.salti_classificati()`; le barre che
`api.barre_isolate()` scarterebbe dentro le finestre; i salti di `api.salti_di_livello()`; i cambi di codice
concatenati, dove lo studio ne concatena. Solo conteggi, prima; poi la decisione se rieseguire, che sarebbe una voce
nuova e datata, mai una riscrittura del verdetto.

**Verifica.** Letto: l'uscita del `grep` sui sorgenti di `backtest/` di questo repo; i tre ADR di market-data citati.

---

## ADR-059 — 2026-09-30 — Test E chiuso: superato dal Test F (segnali precoci)

**Contesto.** Il Test E del filone drawdown (`backtest/drawdown_alpha/2026-09-23_preregistrazione.md`, sezione «Test E»)
non è mai stato pre-registrato davvero: cinque righe che rimandano la regola a «una finestra di ritardo derivata dalla
differenza di lead time osservata nei Test A/B/C stessi». Nessuna regola fissata, nessun verdetto, mai eseguito. Il
Test F (segnali precoci: credito, curva a breve, permessi, sussidi, petrolio; composito da 0 a 5, verdetto
pre-registrato) copre la stessa domanda — combinare segnali che anticipano il ribasso — con regole fissate prima.

**Decisione dell'utente.** Il Test E è chiuso come «superato dal Test F». I Test A e B restano com'erano, descrittivi,
con i loro risultati in `risultati_ab.md`; il Test F ha la sua pre-registrazione e il suo verdetto. Due famiglie di
segnali del Test F (curva, credito) sono le stesse di A e B, misurate diversamente (near-term forward spread al posto
di 10a-3m; excess bond premium al posto di BAA10Y).

**Conseguenze.** Il Test F lavora sul branch `feat/early-signals`, creato da `develop`. *(Nota della versione pubblica: tolto il nome di un branch di uno studio non pubblicato.)* Per il verdetto il Test F misura il ribasso dal massimo delle chiusure degli ultimi 12
mesi, non dal massimo storico della definizione comune del filone (decisione dell'utente: con il massimo storico il
ribasso del 1980 non è un evento nuovo); il massimo storico resta come colonna descrittiva per il confronto con A-E.
La regola esatta di inizio di un nuovo evento si fissa alla fermata 1.

**Verifica.** Letto: la sezione «Test E» della pre-registrazione del 23-09 (righe 231-236) e la voce del registro che apriva il filone, che non
fissano regole per E. *(Nota della versione pubblica: quella voce non è in questa versione.)*

## ADR-060 — 2026-09-30 — Test F: regola degli eventi (massimo a 12 mesi), periodo, recessioni, stato di ogni evento

**Contesto.** ADR-059: il Test F misura il ribasso dal massimo delle chiusure degli ultimi 12 mesi, non dal massimo
storico della definizione comune del filone, e la regola esatta di inizio di un nuovo evento si fissa alla fermata 1.
L'utente indica «un nuovo evento solo dopo che l'indice ha fatto un nuovo massimo a 12 mesi dopo il minimo del precedente».

**Decisione (proposta, da confermare).** Regola operativa in `backtest/drawdown_alpha/eventi_f.py`:
1. **Massimo mobile** M_t = massimo delle chiusure nei 12 mesi di calendario che finiscono in t, t compresa e il giorno
   t − 1 anno escluso (circa 252 sedute). Serve un anno intero di storia prima di t.
2. **Inizio**: la prima seduta T con chiusura ≤ 0,85 × M_T mentre nessun evento è aperto. **Massimo dell'evento** = la
   seduta P della chiusura M_T (la prima, a parità), fissato a T. Nessuna chiusura fra P e T può stare sotto 0,85 × M_T
   (avrebbe fatto partire l'evento prima), quindi il fondo si cerca da T in poi.
3. **Chiusura**: la prima seduta R > T con chiusura strettamente superiore a tutte le chiusure dei 12 mesi precedenti
   (nuovo massimo a 12 mesi). **Fondo** = chiusura minima fra P e R. Senza R entro la fine della serie: evento aperto,
   fondo provvisorio.
4. **Niente doppi conteggi**: mentre un evento è aperto non ne parte un altro; a R la chiusura supera tutto l'anno prima,
   quindi nessuna seduta prima di R può essere il massimo a 12 mesi di una seduta dopo R: il massimo del nuovo evento è
   sempre ≥ R.
5. **Periodo 1973-2025**: entra un evento con massimo ≥ 1973-01-01 e data del −15% ≤ 2025-12-31.
6. **Recessioni NBER** da `USRECM` (FRED; 1 dal mese del picco al mese del minimo compreso, verificato contro la tabella
   NBER `nber.org/research/data/us-business-cycle-expansions-and-contractions`: 1973-11→1975-03, 1980-01→1980-07,
   1981-07→1982-11, 1990-07→1991-03, 2001-03→2001-11, 2007-12→2009-06, 2020-02→2020-04). **Inizio = mese del picco
   NBER**; ribasso da recessione se il mese del massimo è fra inizio − 12 mesi (compreso) e il mese del minimo. Con la
   convenzione NBER «la recessione inizia il mese dopo il picco» (USREC) l'evento del 2000 (massimo 2000-03-24, picco
   NBER marzo 2001) uscirebbe per otto giorni: caso al limite segnalato, la scelta spetta all'utente.
7. **Stato**: *verdetto* se da recessione e massimo ≥ 1975-01-01 (24 mesi interi di tutti e cinque i segnali: l'EBP parte
   dal gennaio 1973); *descrittivo* se senza recessione o con meno di 24 mesi di dati (1973); *non incluso* fuori dal
   periodo (1966, 1968, mostrati per contesto). Per il composito a quattro segnali senza EBP la finestra completa parte
   dal 1970-01-01 (ICSA dal 1967-01-07, media a 52 settimane dal gennaio 1968).
8. Il **massimo storico** (definizione comune, `episodi.py` non modificato) resta la lista B, affiancata alla A nella
   pre-registrazione; differenze: A aggiunge 1976-12, 1980-02 (il caso che motiva la regola), 2010-04, 2011-04, e chiude
   gli eventi prima (nuovo massimo a 12 mesi invece che storico).

**Risultato della lista** (chiusure di `GSPC.INDX`, 24.794 sedute 1927-12-30 → 2026-09-16, `api.prices`): 17 eventi in A
dal 1966, 13 in B; **6 eventi da recessione per il verdetto** (massimi 1980-02-13, 1980-11-28, 1990-07-16, 2000-03-24 al
limite, 2007-10-09, 2020-02-19), 1973-01-11 descrittivo per i 24 mesi, 8 senza recessione. Nessun segnale calcolato.

**Verifica.** Letto: l'uscita di `python backtest/drawdown_alpha/eventi_f.py`; le righe di `USRECM` intorno a ogni
recessione (stesse date della tabella NBER); `api.flags(["GSPC.INDX"])` vuoto e `prices(clean=True)` = `clean=False`.

## ADR-061 — 2026-09-30 — Test F: indice dall'archivio EODHD (`GSPC.INDX` dal 1927), niente Shiller; Russell 2000 tolto

**Contesto.** Il Test F copre il 1973-2025; il calendario dei backtest parte dal 2011 ma l'archivio può avere storia più
lunga. Robustezza descrittiva chiesta sul Russell 2000 dal 1979.

**Decisione.** L'indice è `GSPC.INDX` letto con `api.prices` (prezzi puliti): **24.794 chiusure dal 1927-12-30 al
2026-09-16**, nessuna segnalazione dei controlli, nessuna chiusura nulla o zero, puliti = grezzi. Copre il 1972 e i 24
mesi prima di ogni massimo del periodo: **i dati mensili di Shiller non servono e non si usano**. Le chiusure mensili per
la regola di Faber sono l'ultima seduta del mese della stessa serie.

**Russell 2000: tolto dal Test F** (decisione dell'utente del 01-10-2026, ADR-066). La robustezza «dal 1979» chiesta
all'inizio non aveva una fonte verificabile: `RUT.INDX` è nell'archivio con zero barre (EODHD ha risposto 200 con un corpo
di 2 byte il 2026-09-17, registro `chiamate.jsonl`) e FRED non ha più `RU2000PR`. Nessuna fonte alternativa entra nel test.

**Verifica.** Letto: `api.listings()` (nessuna riga in `INDX` nell'anagrafica: gli indici non stanno nelle liste dei
titoli, ma i prezzi ci sono), `api.prices("GSPC.INDX", clean=False)` e `clean=True`, `api.flags`, il registro delle
chiamate per `eod/RUT.INDX`, la risposta di `fredgraph.csv?id=RU2000PR`.

## ADR-062 — 2026-09-30 — Test F, segnale 2: near-term forward spread dalla curva GSW (parametri di Svensson)

**Contesto.** Engstrom e Sharpe, «(Don't Fear) The Yield Curve», FEDS Notes 2018-06-28: «the difference between the
current implied forward rate (on Treasury bills) six quarters from now and the current yield on a three-month Treasury
bill», forward «inferred from the yields to maturity on Treasury notes maturing 6 quarters from now and 7 quarters from
now», dati trimestrali 1972:Q1-2018:Q1, fonte «Federal Reserve Bank of New York; Federal Reserve Board staff estimates».
«(Don't Fear) The Yield Curve, Reprise», FEDS Notes 2022-03-25: ntfs_t = fwd^6_t − y^1_t, «All Treasury yield data are
constructed from smoothed zero-coupon yield curves following the procedure of Gurkaynak, Sack, and Wright (2007)».
Il working paper FEDS 2018-055 (PDF) non si è potuto leggere: nessuna libreria PDF nel venv, nessuna dipendenza nuova.

**Decisione.** Dalla curva GSW (`api.gsw()`, file `feds200628.csv`), con i parametri di Svensson del giorno:
y(n) = β0 + β1·(1−e^{−n/τ1})/(n/τ1) + β2·[(1−e^{−n/τ1})/(n/τ1) − e^{−n/τ1}] + β3·[(1−e^{−n/τ2})/(n/τ2) − e^{−n/τ2}]
(zero-coupon, composizione continua, per cento; β3 = 0 e τ2 assente prima del 1980-01-02: Nelson-Siegel).
**Forward a 3 mesi fra 18 mesi** f = [1,75·y(1,75) − 1,5·y(1,5)] / 0,25; **tasso a 3 mesi** y(0,25) dalla stessa curva;
**ntfs = f − y(0,25)**, acceso se < 0. Frequenza: valore dell'ultima osservazione disponibile alla fine del mese (ADR-063),
non media trimestrale.
> **Superata in parte da ADR-067 (01-10-2026, decisione dell'utente):** il tasso a 3 mesi primario è il buono DTB3
> convertito nella convenzione della curva; la versione tutta GSW (y(0,25)) resta come confronto descrittivo. Il forward
> e la formula della curva restano questi.

**Dove replica e dove no.** Replica: la fonte (GSW), la scadenza del forward (6 → 7 trimestri), la forma (differenza fra
forward e tasso a breve). Non replica: (a) il tasso a 3 mesi da y(0,25) è un'estrapolazione della curva GSW sotto l'anno
(il file pubblico parte da `SVENY01`; GSW stimano senza i buoni), mentre il Note 2018 parla di «three-month Treasury
bill»: il confronto descrittivo userà `DTB3` (FRED, dal 1954-01-04) come tasso a breve alternativo; (b) mensile invece di
trimestrale; (c) le stime «Board staff» del paper possono differire dal file pubblico. Il confronto con i grafici del
paper si fa alla fermata 2, sulla serie calcolata, non prima.

**Verifica della formula.** La y(n) e la f(n) istantanea ricostruite dai parametri riproducono le colonne del file
`SVENY01`, `SVENY02`, `SVENF01`, `SVENF02` su 16.286 giorni con scarto massimo 6·10⁻⁵ e 2,3·10⁻⁴ punti percentuali
(script di prova nello scratchpad, letto l'output). Scadenze nel file: 1-7 anni dal 1961-06-14, 10 dal 1971-08-16, 15 dal
1971-11-15, 20 dal 1981-07-02, 30 dal 1985-11-25: il forward a 1,5-1,75 anni è dentro la parte stimata dal 1961.

## ADR-063 — 2026-09-30 — Test F: ritardi di pubblicazione per serie (ALFRED dove c'è, altrimenti prudenti e dichiarati)

**Regola generale.** A ogni fine mese t si usano solo dati pubblicati entro t. Le versioni storiche ALFRED sono la
regola dove esistono; altrove si usa la serie di oggi con un ritardo prudente, e si dichiara che le revisioni non sono
riprodotte.

| serie | versioni ALFRED | alla fine del mese t si usa | fonte del calendario |
|---|---|---|---|
| PERMIT (mensile) | dal 1999-08-17 | il mese t − 1 (il mese t esce il 12° giorno lavorativo di t + 1; agosto 2026 → 17-09-2026); con ALFRED la versione nota il giorno t | Census, `census.gov/construction/soc/schedule.html`; ALFRED «Release Dates» |
| ICSA (settimanale, sabato) | dal 2009-05-28 | le settimane con sabato ≤ t − 5 giorni (giovedì 8:30 della settimana dopo: ultima osservazione 2026-09-19, versione ALFRED 2026-09-24); con ALFRED la versione nota il giorno t | DOL, versioni ALFRED |
| WTISPLC (mensile, media dei prezzi spot) | dal 2016-10-13 (prima nessuna) | il mese t − 1 (FRED ha aggiornato agosto 2026 il 2026-09-02); serie di oggi: è una media di prezzi di mercato, non rivista | pagina FRED della serie |
| EBP (mensile) | nessuna, ristimato ogni volta | il mese t − 1 (esce «after 10:00 a.m. on the fourth business day of each month»: luglio 2026 → file del 2026-08-06); serie di oggi, l'intera storia può cambiare a ogni aggiornamento | pagina Fed «Updating the Recession Risk and the Excess Bond Premium» |
| curva GSW (giornaliera) | nessuna | l'ultima osservazione con data ≤ t − 11 giorni (il file esce «on Tuesday for the period up to the Friday of the previous week»: caso peggiore 11 giorni; **11 giorni fissi, deciso il 01-10, ADR-066**) | pagina Fed `data/nominal-yield-curve.htm` |
| DTB3 (giornaliera) | — (tasso di mercato, non rivisto) | il valore del giorno dell'osservazione GSW usata: H.15 pubblicato ogni giorno lavorativo alle 16:15 con i dati del giorno prima (ADR-067) | pagina Fed H.15 |
| S&P 500 | — | chiusura del giorno | — |
| USRECM | — | solo per classificare gli eventi a posteriori; le date NBER sono annunciate con mesi di ritardo e non entrano in nessun segnale | NBER |

**Conseguenze.** Senza la chiave ALFRED (ADR-064) PERMIT e ICSA restano alla serie di oggi con i ritardi della tabella:
per il 1973-1999 (PERMIT) e il 1973-2009 (ICSA) è comunque l'unica strada, e la pre-registrazione lo dichiara come
limite. Il ritardo di 11 giorni sulla curva è prudente e costa fino a due settimane di anticipo: alternativa, il
calendario esplicito «venerdì prima dell'ultimo martedì ≤ t» (4-10 giorni). Decisione dell'utente.

**Verifica.** Letto: `Last-Modified` dei file EBP (2026-08-06) e GSW (2026-09-29); ultima data di ogni serie letta con il
lettore nuovo; le pagine ALFRED e Census citate; la pagina FRED di WTISPLC («Last Updated: September 2, 2026»).

## ADR-064 — 2026-09-30 — Test F: la chiave ALFRED manca; bloccante per la fermata 2, nessun ripiego

**Fatto.** Il `.env` di edge-lab non ha la riga `FRED_API_KEY` (letti i soli nomi delle variabili del file) *(Nota della versione pubblica: tolto l'elenco dei nomi delle variabili d'ambiente.)*.
`api.fred("PERMIT", al_giorno="2010-01-29")` si ferma con `ConfigError: FRED_API_KEY non impostata` prima di qualunque
richiesta; la chiamata diretta all'API senza chiave risponde 400 «Variable api_key is not set».

**Decisione.** Le versioni storiche non si sostituiscono con i dati di oggi in silenzio. **Bloccante per la fermata 2**
per i segnali 3 (PERMIT dal 1999-08-17) e 4 (ICSA dal 2009-05-28): senza chiave quei periodi userebbero la serie di oggi,
e il risultato andrebbe etichettato «senza versioni storiche» in ogni tabella. **Cosa serve**: una chiave gratuita da
`fred.stlouisfed.org/docs/api/api_key.html` (account FRED), riga `FRED_API_KEY=` nel `.env` (ambiente > `.env`, mai nel
repo: `.env.example` ha il nome vuoto). Il codice è pronto e testato con rete finta (`market-data/tests/test_fred.py`);
la prima chiamata vera ad ALFRED si fa quando la chiave c'è, e va verificata leggendo la risposta (formato, `count`).

**Aggiornamento del 01-10-2026: non più bloccante.** La chiave è nel `.env` (riga `FRED_API_KEY=` presente, 32 caratteri;
valore mai letto né stampato). Chiamata reale `api.fred("PERMIT", al_giorno="2010-06-15")` fatta dall'utente: la versione
storica torna con ultima osservazione 2010-04 = 610 contro 637 della serie di oggi; la chiave non compare nel grezzo
(`fred/manifest/grezzo.jsonl`, endpoint `alfred/PERMIT`). Il controllo pre-commit riconosce la chiave FRED (commit
`cfa1cdf`). Per la fermata 2 le versioni a ogni fine mese (PERMIT dal 1999-08-31, ICSA dal 2009-05-31) si scaricano una
volta nel grezzo e si rileggono da lì.

**Verifica.** Letto: `grep -o "^FRED_API_KEY=" .env` (solo il nome), il manifest del grezzo `fred/` (endpoint
`alfred/PERMIT` presente), `git log` per `cfa1cdf`.

## ADR-065 — 2026-09-30 — market-data: `api.fred()`, `api.ebp()`, `api.gsw()` e il grezzo `fred/` (specchio di market-data ADR 008)

**Decisione.** Un solo lettore, in market-data (`market_data/fred.py`, funzioni in `api.py`): FRED senza chiave, ALFRED
con `FRED_API_KEY`, EBP e curva GSW dai file della Fed; livello grezzo per fornitore (`store/raw.py` prende il fornitore,
`fred/raw/<giorno>/…` e `fred/manifest/grezzo.jsonl`), `api_key` fra i segreti mai scritti, riscarico al massimo una volta
al giorno e mai una sovrascrittura, versioni ALFRED immutabili. Solo `urllib`: nessuna dipendenza nuova. Nessun altro
lettore FRED: `backtest/drawdown_alpha/dati.py` resta il debito registrato, non si tocca. Dettagli, fonti e prima data
letta di ogni serie in `market-data/docs/adr/008-fred-alfred-ebp-gsw.md`.

**Verifica.** Letto: il log di `bash test.sh` del 30-09 (ALL SUITES PASSED, exit 0, 54 s; market-data 146 passed in 42 s;
la prima esecuzione, 63 s, aveva `test_adr_citati` rosso perché ADR-060 era citata e non ancora scritta), l'uscita della prova
con chiamate reali (PERMIT dal 1960-01-01, ICSA dal 1967-01-07, WTISPLC dal 1946-01-01, EBP dal 1973-01-01, GSW dal
1961-06-14), il manifest `fred/manifest/grezzo.jsonl` (9 righe, nessuna chiave).

## ADR-066 — 2026-10-01 — Test F: decisioni dell'utente sulla fermata 1 (recessioni, eventi, Russell, ritardo GSW, falsi eventi)

**Decisioni dell'utente, vincolanti, prese prima di qualunque calcolo.**
1. **Inizio della recessione = mese del picco NBER** (USRECM): il 2000 è dentro, **6 ribassi da recessione per il verdetto,
   servono almeno 4 colpiti** (2/3). Robustezza descrittiva: recessione dal mese dopo il picco (USREC, 5 eventi).
2. **Regola degli eventi** come proposta in ADR-060. 1980-02 e 1980-11 restano due eventi nel verdetto e lo stesso segnale
   può contare per entrambi; **robustezza descrittiva con i due fusi**: massimo = il primo (1980-02-13), finestra unica dal
   1978-02-13 alla data del −10% del secondo evento (unione delle due finestre), fondo = il minimo dei due.
3. **Russell 2000 tolto** dal Test F: dalla pre-registrazione e dalle ADR dove era una robustezza (ADR-061 aggiornata).
4. Tasso a 3 mesi: **DTB3 per il tasso di oggi, forward dalla curva GSW** (formula e ritardo in ADR-067); la versione tutta
   GSW resta come confronto descrittivo.
5. **Ritardo sulla curva GSW: 11 giorni fissi.**
6. **Falsi eventi**: 1000 serie, episodi non sovrapposti, date di inizio uniformi fra le fini mese 1975-01 → 2025-12,
   finestre lunghe come quelle degli eventi reali, **seme fisso 20261001** scritto nella pre-registrazione.

**Conseguenze.** Pre-registrazione aggiornata nelle sezioni toccate (datate 01-10); da qui le regole non cambiano. La
fermata 2 (`backtest/drawdown_alpha/test_f.py`) calcola tutto come scritto e produce un referto in bozza in `drafts/`, non
committato finché l'utente non lo rivede. Il registro dei verdetti non si tocca.

## ADR-067 — 2026-10-01 — Test F, segnale 2: tasso a 3 mesi dal buono DTB3 convertito a capitalizzazione continua; ritardo di DTB3

**Contesto.** ADR-066 punto 4. La curva GSW è in rendimenti zero-coupon a capitalizzazione continua (riga «Zero-coupon
yield, Continuously Compounded, SVENYXX» dell'intestazione di `feds200628.csv`, letta). DTB3 (FRED, H.15) è «3-Month
Treasury Bill Secondary Market Rate, Discount Basis»: un tasso di sconto su base 360, non un rendimento.

**Decisione: la conversione.** Prezzo dal tasso di sconto d (per cento), buono a 13 settimane = 91 giorni:
P = 1 − (d/100)·91/360 (TreasuryDirect, «Understanding pricing and interest rates»: «Price = Face value (1 – (discount
rate x time)/360)», con l'esempio del buono a 26 settimane su 182 giorni). Rendimento zero-coupon a capitalizzazione
continua su base 365, nella stessa convenzione della curva: **y3m = (365/91)·ln(1/P)**, in per cento. Non si passa per il
rendimento «investment rate» (semplice, (1/P − 1)·365/91): la conversione va diretta al continuo, che è ciò che la curva
riporta. Il forward a 3 mesi fra 18 mesi resta quello di ADR-062; **ntfs = f − y3m**, acceso se < 0. DTB3 si prende nel
giorno dell'osservazione GSW usata (ultimo valore entro 7 giorni prima, altrimenti il segnale non è disponibile).
Implementazione: `dtb3_continuo()` in `backtest/drawdown_alpha/test_f.py`.

**Ritardo di pubblicazione di DTB3.** L'H.15 «is posted daily Monday through Friday at 4:15pm» con i dati del giorno
lavorativo precedente (pagina `federalreserve.gov/releases/h15/`, letta); FRED aggiorna DTB3 lo stesso giorno (pagina
della serie: «Last Updated: Sep 30, 2026 3:16 PM CDT»; il 30-09 l'ultima osservazione letta era del 2026-09-28). Ritardo
di 1-2 giorni lavorativi, coperto dagli 11 giorni del ritardo sulla curva: il valore DTB3 del giorno dell'osservazione
GSW è sempre già pubblicato alla fine del mese.

**Limiti.** 91 giorni è la scadenza nominale del buono a 13 settimane, non quella effettiva del titolo quotato quel
giorno; la quotazione H.15 è il denaro del mercato secondario. Il paper prende anche il tasso a breve dalla curva lisciata
(Reprise 2022): la versione tutta GSW (y(0,25)) è il confronto descrittivo.

I numeri 068, 069 e 070 non sono assegnati in questa versione: la pre-registrazione del Russell li cita per errore (errata del 22-09) e una voce con quei numeri ne cambierebbe il senso.

## ADR-071 — 2026-10-04 — Test F: correzione di un errore di lettura della curva GSW (riga `NA` nei festivi → ultimo giorno valido precedente)

**Contesto.** Preparando il Test G (fermata 1) è risultato che il composito a 5 mancava in 23 delle 432 fini mese del
periodo 1990-2025, sempre per il segnale dei tassi. Causa: `segnale_ntfs` (`backtest/drawdown_alpha/test_f.py`)
prendeva l'ultima riga del file GSW con data ≤ t − 11 giorni (ADR-063) senza guardare se fosse valida, e il file della
Fed ha una riga anche nei giorni festivi, con `NA` al posto dei parametri (verificato su 1992-01-20, 2008-02-18,
2020-01-20, 2025-06-19). In quei mesi il segnale risultava mancante e il composito con lui. Non era una regola
pre-registrata: la pre-registrazione dice «l'ultima osservazione con data ≤ t − 11 giorni», e una riga `NA` non è
un'osservazione. È un errore di lettura.

**I mesi toccati.** 30 fini mese fra il 1973-02 e il 2025-12 (il referto contava 605 fini mese con il composito su
635): 1975-02, 1978-01, 1980-02, 1981-04, 1986-01, 1986-02, 1987-04 e, nel periodo del Test G, **i 23**: 1992-01,
1992-04, 1992-12, 1993-01, 1993-04, 1995-03, 1997-01, 1997-02, 2003-01, 2003-02, 2003-04, 2008-02, 2014-01, 2014-02,
2014-04, 2019-04, 2020-01, 2023-06, 2024-06, 2025-01, 2025-02, 2025-04, 2025-06. In più il 2026-06, fuori dal periodo.

**Decisione (dell'utente, 04-10-2026: «per la curva, ultimo giorno valido precedente»).** `test_f.riga_gsw`: l'ultima
riga **valida** (BETA0 presente) con data ≤ t − 11 giorni; **mai una riga successiva**; se la riga valida è più vecchia
di **7 giorni** rispetto a t − 11 (`MAX_GIORNI_CURVA`, lo stesso limite già usato per DTB3 in ADR-067) il segnale resta
mancante, fail-closed. Nei 31 casi la riga usata è più vecchia di 1-4 giorni. Il DTB3 resta quello del giorno della
riga usata (ADR-067). La versione tutta GSW (y(0,25)) passa per la stessa funzione ed è corretta insieme. Le altre
letture della curva: la 10 anni − 3 mesi del confronto usa GS10 e TB3MS mensili da FRED, non il file GSW, e non ha il
difetto. Test: `tests/test_f_curva.py`.

**Effetto misurato sul Test F** (uscita di `test_f.py` prima e dopo, stessi dati del 04-10-2026): fini mese con il
composito da 605 a **635** (nessuna mancante); eventi colpiti **6/6, invariati**, con le stesse date di prima
accensione; falsi allarmi **4, invariati**, non giudicabili da 2 a 1; episodi da 24 a 23 (i due del 2025 si fondono);
falsi allarmi severi **7 e 9, invariati**; quota dei falsi eventi sotto il reale **0,885, invariata**; criteri (a)
vero, (b) vero, (c) falso. **Il verdetto resta INCONCLUSIVO.** Cambia una riga dello stato attuale: il composito della
fine mese 2026-06-30, prima mancante, è 3 (acceso per quel solo mese), quindi «spento dal 2026-07» e non «dal 2025-11».

**Conseguenze.** Il referto chiuso `backtest/drawdown_alpha/2026-10-01_referto_test_f.md` non è riscritto: ha in fondo una nota datata
04-10-2026 con la tabella prima/dopo. La pre-registrazione del Test F non cambia. Il registro dei verdetti non si
tocca. Il Test G usa il composito corretto.

## ADR-072 — 2026-10-04 — Test G (scadenza delle put spread): dati, strumento e prezzo Black-Scholes con dividendo al 2%

**Contesto.** Seguito del Test F: comprare put spread sull'S&P 500 protegge il portafoglio a un costo accettabile, con
quale scadenza (3, 6, 9, 12 mesi) e con quale regola di ingresso. Non ci sono quotazioni di opzioni nell'archivio: i
prezzi sono stimati. Pre-registrazione `backtest/drawdown_alpha/2026-10-04_preregistrazione_test_g.md`, approvata
dall'utente il 04-10-2026 prima di qualunque rendimento.

**Decisione.** Dati: chiusure di `GSPC.INDX` (`eventi_f.chiusure()`), `VIXCLS` e `DTB3` con `api.fred()`; periodo
1990-01-02 → 2025-12-31 (9.067 sedute). Strumento: put comprata con strike 0,95 × la chiusura del giorno di ingresso,
put venduta a 0,75 ×, non arrotondati, tenute fino a scadenza. Prezzo Black-Scholes: volatilità VIX/100 per la comprata
e (VIX + 5)/100 per la venduta, per tutte le scadenze, inclinazione attaccata allo strike; tasso
`test_f.dtb3_continuo(DTB3)` (ADR-067) per tutte le scadenze; tempo = giorni di calendario / 365; scadenza = N mesi di
calendario, seduta precedente se non è una seduta; valore a scadenza sulla chiusura. **Dividendi: q = 2% continuo nel
prezzo delle put (scelta principale, decisione dell'utente); q = 0 sensibilità descrittiva; il portafoglio resta senza
dividendi.** Sensibilità descrittive di inclinazione: 0 e +10 punti. Buchi: nelle sedute senza VIX (3) o senza DTB3
(75) l'ultimo valore noto prima della seduta, mai in avanti, non più vecchio di 7 giorni (età massima osservata: 1 e 3
giorni). Codice: `backtest/drawdown_alpha/test_g_dati.py`; test `tests/test_g_prezzi.py` (valori di manuale con e
senza dividendo, parità put-call, limiti).

**Verifica.** Prezzo di apertura di prova del 2008-09-02 a 12 mesi calcolato passo per passo: 58,1780 punti indice
(4,5538% della chiusura) con q = 2%, uguale alla funzione del codice; 52,0141 con q = 0.

**Limiti.** Prezzi stimati, non di mercato: le put vere sotto stress costano di più. VIX a 30 giorni usato per
scadenze fino a 12 mesi; inclinazione fissa; dividendo fisso; tasso a 3 mesi per tutte le scadenze; nessun costo di
transazione.

## ADR-073 — 2026-10-04 — Test G: due versioni di budget, due verdetti indipendenti, 32 combinazioni e 160 serie guardate

**Contesto.** La specifica iniziale («premio 3% per operazione, tetto 6% l'anno», verdetto sulla sola cella regola 3 ×
12 mesi) rendeva le scadenze corte non confrontabili: a 3 mesi il tetto lasciava scoperta metà dell'anno. L'utente ha
deciso il 04-10-2026, prima dei risultati, due versioni di budget, ciascuna con il suo verdetto.

**Decisione.** *Versione A (budget annuo uguale)*: premio per operazione = 6% × mesi/12, massimo 3% (3 mesi 1,5%; 6, 9
e 12 mesi 3%; a 9 mesi quindi al più 4% l'anno, dichiarato); tetto 6% **sui 360 giorni precedenti**, nuova operazione
compresa (360 e non 365 perché i rinnovi trimestrali non slittino). Cella del verdetto: **regola 3 × 12 mesi**.
*Versione B (premio fisso)*: 3% per operazione a tutte le scadenze, nessun tetto. Cella del verdetto: **regola 3 × 3
mesi**. In entrambe: premio in percentuale del valore corrente del portafoglio, pagato vendendo quote dell'indice; una
sola operazione aperta alla volta; nessun raddoppio; incasso a scadenza reinvestito nell'indice; spread aperto valutato
ogni giorno a modello; nessun limite alla parte coperta. **Soglie uguali per i due verdetti**: REGGE se la riduzione
media dei tre ribassi peggiori è ≥ 1/3 e il costo ≤ 1,5 punti di rendimento annuo; NON REGGE se la riduzione è < 1/5 o
il costo > 3 punti; INCONCLUSIVO altrimenti. I due verdetti non si fondono. Le altre 30 combinazioni (4 regole × 4
scadenze × 2 versioni, meno le due celle) sono descrittive, con il premio annuo effettivamente speso accanto.

**Conto dichiarato prima dei risultati.** 32 combinazioni; sensibilità su tutte le 32, una variazione alla volta:
inclinazione 0 e +10 (64 serie), spread aperto al valore intrinseco (32), q = 0 (32): **160 serie guardate**. Il
referto scrive che i verdetti sono due e il totale guardato, e verifica con i numeri la coincidenza attesa fra la cella
A e la cella regola 3 × 12 mesi di B (stesso premio, tetto che non dovrebbe mai bloccare).

**Conseguenze.** La vecchia scelta «due operazioni per anno solare» è superata. La simulazione si scrive solo ora.

## ADR-074 — 2026-10-04 — Test G: regole di ingresso, composito corretto (ADR-071), misure e riduzione massima teorica

**Contesto.** Le quattro regole della specifica (sempre accesa; composito del Test F ≥ 3; composito ≥ 3 e VIX sotto la
mediana a 12 mesi; Faber) vanno tradotte in ingressi senza sguardo in avanti, e le misure vanno definite prima dei
numeri.

**Decisione: ingressi.** Segnali mensili letti all'ultimo giorno del mese t, ingresso alla chiusura della prima seduta
di t + 1, se non c'è uno spread aperto e il tetto lo permette (432 letture, 1989-12 → 2025-11). Regola 1: si apre in
ogni seduta senza spread aperto (rinnovo nella seduta di scadenza). Regola 2: `composito5` di `test_f.calcola_mesi`
≥ 3, **con la lettura della curva corretta da ADR-071: 0 letture mancanti su 432** (erano 23); dove mancasse comunque,
fail-closed. Regola 3: in più, ultimo VIX noto a fine mese strettamente sotto la mediana delle chiusure giornaliere dei
12 mesi di calendario fino a t; la finestra è intera dal 1990-12-31, quindi **la regola 3 entra dal 1991-01-02**.
Regola 4: `test_f.faber`.

**Decisione: misure.** Portafoglio 100 nell'indice dal 1990-01-02 al 2025-12-31. Tre ribassi peggiori = i tre episodi
più profondi del portafoglio senza protezione (`episodi.py`); con protezione, valore al fondo / valore al picco sulle
stesse date; riduzione media = media semplice delle tre; costo = differenza dei rendimenti annui composti; premio annuo
effettivamente speso; guadagno delle put sui 10 eventi della lista A del Test F con massimo dal 1990.

**Riduzione massima teorica, calcolata prima di ogni simulazione** (richiesta dell'utente; solo prezzi di apertura alla
seduta del massimo, q = 2%): parte coperta = premio / costo dello spread; guadagno massimo = 20% × parte coperta;
riduzione massima = guadagno massimo / profondità. Media dei tre ribassi (2000-03-24, 2007-10-09, 2020-02-19): versione
A 55,7% a 3 mesi, 62,7% a 6, 49,5% a 9, **43,7% a 12 (cella del verdetto)**; versione B **111,5% a 3 mesi (cella del
verdetto)**, poi come A. Nessun tetto è sotto un terzo: REGGE non è escluso per costruzione in nessuna delle due celle.
La parte coperta supera il 100% in 15 casi su 24 (fino al 306%): nessun limite.

**Limiti.** Il tetto teorico vale per una sola operazione aperta al massimo e pagata per intero; non limita la somma di
più operazioni nello stesso ribasso e non è un risultato. Il composito eredita i limiti del Test F (EBP ristimato) e le
sue soglie sono state fissate sugli stessi anni. Ciascun verdetto poggia su tre ribassi e su una storia di 36 anni.
