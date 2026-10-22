# Pre-registrazione — Test G, scadenza delle put spread (fermata 1)

**4 ottobre 2026.** Filone drawdown_alpha, metodo standard del progetto: due fermate, nessuna misura guardata prima
della fermata 2, dato mancante dichiarato e mai sostituito, nessuna spesa LLM — regole deterministiche. Branch
`feat/test-g`. Decisioni in `DECISIONS.md` **ADR-072..074**; la correzione del composito è ADR-071. Script di questa
fermata: `backtest/drawdown_alpha/test_g_dati.py` (lettura dei dati, prezzo Black-Scholes, controlli, riduzione massima
teorica) e `tests/test_g_prezzi.py`. La simulazione del portafoglio **non esiste ancora**.

**Approvata dall'utente il 04-10-2026, prima di qualunque rendimento, con queste correzioni** (le sezioni toccate lo
dicono): due versioni di budget con due verdetti; tetto della versione A sui **360 giorni** precedenti; rendimento da
dividendo **q = 2%** nel prezzo delle put (q = 0 come sensibilità); composito del Test F **corretto** (ADR-071: nessun
mese mancante nel periodo); riduzione massima teorica dei tre ribassi peggiori calcolata prima di ogni simulazione.

**In questa fermata non è stato calcolato nessun rendimento di portafoglio, nessun ribasso con protezione, nessun costo
dei premi, nessun guadagno delle put, nessuna cella delle due griglie 4 × 4.** Sono stati letti i dati, contati i buchi,
verificato da quando esistono i segnali e calcolati **solo prezzi di apertura**: quello di prova del 2008-09-02 e quelli
alla seduta del massimo dei tre ribassi più profondi (per il tetto teorico). Nessun valore a scadenza.

## Domanda — testo dell'utente

Comprare put spread sull'S&P 500 protegge il portafoglio a un costo accettabile? Con quale scadenza (3, 6, 9, 12 mesi)
e con quale regola di ingresso?

È il seguito del Test F (`2026-09-30_preregistrazione_test_f.md`): lì si misurava se il composito anticipa i ribassi;
qui si misura quanto costa e quanto rende la protezione comprata con quel segnale, contro tre regole di confronto.
**Nessun risultato di questo test va tradotto in regola di portafoglio senza una decisione dell'utente.**

## Specifica dell'utente — fissata, non modificata

*Testo originale. Le righe «Portafoglio» (premio e tetto) e «Verdetto» sono sostituite dalla decisione dell'utente
del 04-10-2026 nella sezione successiva; il resto vale com'è.*

- **Dati**: S&P 500 giornaliero dall'archivio (`GSPC.INDX`), VIX da FRED (`VIXCLS`, dal 1990), tasso a 3 mesi da FRED
  (`DTB3`). Periodo 1990-2025. Composito del Test F e regola di Faber dal codice esistente (`test_f.py`, `eventi_f.py`).
- **Strumento**: put comprata 5% sotto il prezzo, put venduta 25% sotto. Black-Scholes, volatilità = VIX per la
  comprata e VIX + 5 punti per la venduta. Tenuta fino a scadenza, nessuna gestione intermedia. Sensibilità
  descrittiva: inclinazione 0 e +10 punti.
- **Portafoglio**: 100 investito nell'S&P 500, premio speso 3% del portafoglio per operazione, tetto 6% l'anno. Nessun
  raddoppio dopo premi persi.
- **Regole di ingresso** (tutte e quattro, per ogni scadenza): 1) sempre accesa, rinnovo continuo; 2) composito del
  Test F ≥ 3; 3) composito ≥ 3 e VIX sotto la sua mediana a 12 mesi; 4) Faber: chiusura mensile sotto la media a 10 mesi.
- **Misure** per regola × scadenza: rendimento annuo, ribasso massimo, i tre ribassi peggiori del portafoglio con e
  senza protezione, costo annuo medio dei premi, guadagno delle put nei ribassi del Test F (2000, 2007, 2020 e gli altri).
- **Verdetto pre-registrato sulla sola combinazione regola 3 × 12 mesi**: **REGGE** se riduce in media di almeno un
  terzo la profondità dei tre ribassi peggiori **e** costa al massimo 1,5 punti di rendimento annuo; **NON REGGE** se
  riduce meno di un quinto **o** costa più di 3 punti; **INCONCLUSIVO** altrimenti. Le altre 15 combinazioni sono
  descrittive.
- **Limite da dichiarare**: prezzi stimati, non di mercato; le put vere sotto stress costano di più.

## Due versioni di budget, decise prima dei risultati — 04-10-2026

Testo dell'utente, riportato com'è. **Sostituisce, nella specifica qui sopra, la riga del portafoglio («premio speso 3%
… tetto 6% l'anno») e la riga del verdetto («sola combinazione regola 3 × 12 mesi … le altre 15 descrittive»).** A
questa data la simulazione non esiste e nessun rendimento è stato calcolato.

> Due versioni di budget, entrambe con verdetto, decise ora prima dei risultati:
> - Versione A (budget annuo uguale): premio per operazione = 6% × (mesi/12), massimo 3%; tetto 6% sui 12 mesi mobili.
>   Cella del verdetto: regola 3, scadenza 12 mesi.
> - Versione B (premio fisso): 3% per ogni operazione per tutte le scadenze, nessun tetto annuo (3 mesi → 12% l'anno,
>   6 → 6%, 9 → 4%, 12 → 3%). Cella del verdetto: regola 3, scadenza 3 mesi.
>
> Stesse soglie per entrambe (riduzione media di almeno un terzo dei tre ribassi peggiori, costo massimo 1,5 punti di
> rendimento annuo). Ogni versione ha il suo verdetto, REGGE / NON REGGE / INCONCLUSIVO. Tutte le altre combinazioni
> delle due griglie (4 regole × 4 scadenze) sono descrittive, con il premio annuo effettivamente speso accanto. Nel
> referto scrivi che i verdetti sono due e quante combinazioni sono state guardate in totale.

### Le due versioni, fissate

| | Versione A — budget annuo uguale | Versione B — premio fisso |
|---|---|---|
| premio per operazione, in % del valore corrente del portafoglio | 6% × (mesi/12), massimo 3%: **3 mesi 1,5%; 6 mesi 3%; 9 mesi 3%** (4,5% limitato a 3%); **12 mesi 3%** | **3%** per tutte le scadenze |
| tetto | **6% sui 12 mesi mobili, contati come 360 giorni** | **nessuno** |
| massimo teorico nella regola «sempre accesa» | 6% l'anno a 3 e 6 mesi; **4% a 9 mesi**; 3% a 12 mesi | 12% a 3 mesi, 6% a 6, 4% a 9, 3% a 12 |
| cella del verdetto | **regola 3 × 12 mesi** | **regola 3 × 3 mesi** |

- **Tetto della versione A — 360 giorni** (correzione dell'utente del 04-10-2026: «calcolalo sui 360 giorni
  precedenti (nuova operazione compresa), non 365, così i rinnovi trimestrali non slittano»). Nel giorno D si sommano i
  premi delle operazioni con ingresso nei 360 giorni precedenti (date > D − 360 giorni), ciascuno in percentuale del
  portafoglio nel suo giorno di ingresso, **più il premio della nuova operazione**; se la somma supererebbe il 6% **non
  si entra**. Il 6% esatto è ammesso (4 × 1,5%, 2 × 3%). Un ingresso bloccato non si recupera con un premio più grande:
  nella regola 1 si riprova alla seduta successiva, nelle regole 2-4 alla lettura mensile successiva.
- **9 mesi nella versione A: 4% l'anno, non 6%** (approvato dall'utente: «ok, dichiaralo»). Il premio è 3% (4,5%
  limitato a 3%) e in un anno ci sta al più un rinnovo e un terzo: il «budget annuo uguale» vale a 3 e a 6 mesi (6%),
  non a 9 (4%) né a 12 (3%).
- **In entrambe le versioni restano**: una sola operazione aperta alla volta, nessun raddoppio (la percentuale del
  premio non cambia mai, qualunque sia l'esito delle operazioni precedenti). **Tutto il resto è identico** nelle due
  griglie: prezzo, strike, calendario degli ingressi, regola dei buchi, valutazione giornaliera, misure, soglie.
- Le percentuali annue sono il **massimo teorico nella regola «sempre accesa»**; nelle regole 2, 3 e 4 la spesa
  effettiva dipende da quante volte il segnale è acceso senza uno spread aperto e si legge solo alla fermata 2.

### Coincidenze prevedibili fra A e B — dichiarate ora, verificate nel referto con i numeri

È un ragionamento sulle regole, non un calcolo. **Il referto le verifica con i numeri**: per ogni scadenza scrive se le
celle di A e di B coincidono (stesse operazioni, stessi valori) e, dove non coincidono, perché.

- **12 mesi e 9 mesi**: il premio è lo stesso (3%) e, con una sola operazione aperta alla volta, tre ingressi in 360
  giorni non ci stanno; due fanno il 6%, che è ammesso. Il tetto non dovrebbe bloccare mai e le otto celle dovrebbero
  dare gli stessi numeri in A e in B. **Quindi la cella del verdetto di A (regola 3 × 12 mesi) dovrebbe coincidere con
  la cella descrittiva regola 3 × 12 mesi di B** (approvato dall'utente: «ok, verificala nel referto con i numeri»).
- **6 mesi**: il premio è lo stesso (3%); le due versioni differiscono solo se il tetto blocca, cioè se il terzo
  ingresso cade a meno di 360 giorni dal primo. Nelle regole 2-4 gli ingressi sono la prima seduta di un mese e fra la
  prima seduta dello stesso mese in due anni consecutivi passano almeno 362 giorni: il tetto non dovrebbe bloccare.
  Nella regola 1 può succedere solo se due scadenze anticipate alla seduta precedente tolgono insieme più di cinque
  giorni; in quel caso l'ingresso slitta di qualche seduta.
- **3 mesi**: diverse per costruzione (1,5% contro 3%). Con la finestra a 360 giorni il quinto ingresso della versione
  A non slitta nelle regole 2-4 (almeno 362 giorni dal primo); nella regola 1 può slittare di qualche seduta solo se le
  scadenze anticipate tolgono insieme più di cinque giorni in un anno.
- Le celle che coincidono **restano contate** fra le combinazioni guardate: il conto qui sotto non scende.

### Quante combinazioni si guardano — contate ora

| insieme | serie | ruolo |
|---|---:|---|
| versione A, 4 regole × 4 scadenze, inclinazione +5, valutazione a modello | 16 | 1 con verdetto (regola 3 × 12 mesi) + 15 descrittive |
| versione B, 4 regole × 4 scadenze, inclinazione +5, valutazione a modello | 16 | 1 con verdetto (regola 3 × 3 mesi) + 15 descrittive |
| **combinazioni regola × scadenza × versione** | **32** | **2 con verdetto, 30 descrittive** |
| sensibilità di inclinazione 0 e +10, su tutte le 32 (q = 2%) | 64 | descrittive |
| spread aperto valutato al valore intrinseco, su tutte le 32, inclinazione +5, q = 2% | 32 | descrittiva |
| dividendo q = 0 nel prezzo delle put, su tutte le 32, inclinazione +5 | 32 | descrittiva |
| **totale delle serie guardate** | **160** | |

La specifica diceva «sensibilità descrittiva: inclinazione 0 e +10» senza dire su quali celle: **valgono per tutte le
32 combinazioni**, e così la valutazione al valore intrinseco e la sensibilità q = 0 (aggiunta dall'utente il
04-10-2026). Le sensibilità cambiano una cosa alla volta rispetto alla scelta principale (inclinazione +5, q = 2%,
valutazione a modello) e non si incrociano fra loro. **Il referto dichiara che i verdetti sono due e scrive il totale
guardato: 32 combinazioni, 160 serie.** Se alla fermata 2 se ne guarda una in più, il referto lo dice e aggiorna il
totale. Accanto a ognuna delle 32 celle sta il **premio annuo effettivamente speso** (misura «costo annuo medio dei
premi»).

## Fonti — lette davvero il 04-10-2026

Uscita di `python backtest/drawdown_alpha/test_g_dati.py --segnali --tetto` (riportata nelle sezioni dei controlli,
del prezzo di prova e della riduzione massima teorica).

| serie | lettore | prima data (valore) | ultima | osservazioni 1990-2025 |
|---|---|---|---|---:|
| S&P 500, chiusure | `eventi_f.chiusure()` → `api.prices("GSPC.INDX")` | 1927-12-30 (17,66) | 2026-10-02 | 9.067 sedute (1990-01-02 → 2025-12-31) |
| VIX | `api.fred("VIXCLS")` | 1990-01-02 (17,24) | 2026-10-01 | 9.092 |
| tasso a 3 mesi | `api.fred("DTB3")` | 1954-01-04 (1,33) | 2026-10-01 | 9.005 |
| composito a 5 segnali | `test_f.calcola_mesi`, con la lettura della curva corretta (ADR-071) | fine mese 1973-02-28 | 2025-12-31 | 432 letture su 432 |
| Faber | `test_f.faber` sulle chiusure mensili di GSPC | presente in tutte le fini mese calcolate (dal 1967-01-31) | 2025-12-31 | 432 letture su 432 |

`GSPC.INDX` è un **indice di prezzo**: non contiene i dividendi (nel prezzo delle put entrano con q = 2%). `VIXCLS` è la volatilità implicita a **30 giorni**.
`DTB3` è il buono a 13 settimane quotato a **sconto bancario** (base 360).

## Il prezzo — Black-Scholes, ogni dettaglio

    put(S, K, T, r, σ, q) = K·e^(−rT)·N(−d2) − S·e^(−qT)·N(−d1)
    d1 = [ln(S/K) + (r − q + σ²/2)·T] / (σ·√T)        d2 = d1 − σ·√T
    spread = put(S, K1, T, r, VIX/100) − put(S, K2, T, r, (VIX + 5)/100)

- **S**: chiusura di `GSPC.INDX` del giorno. **Strike**: K1 = 0,95 × chiusura del giorno di ingresso, K2 = 0,75 × la
  stessa chiusura, **non arrotondati**; restano fissi fino a scadenza.
- **Volatilità**: VIX del giorno diviso 100 per la put comprata, (VIX + 5)/100 per la venduta. La stessa regola vale
  per **tutte le scadenze** (3, 6, 9, 12 mesi) e per ogni valutazione successiva all'apertura: l'inclinazione è
  attaccata allo strike, non alla distanza dal prezzo. Sensibilità descrittiva: +0 e +10 punti al posto di +5.
- **Tasso r**: `DTB3` del giorno convertito con `test_f.dtb3_continuo` (riusata così com'è, ADR-067): prezzo
  P = 1 − d·91/360, r = (365/91)·ln(1/P), capitalizzazione continua su base 365. Il tasso a 3 mesi vale anche per le
  scadenze a 6, 9 e 12 mesi. Un tasso zero o negativo si usa così com'è.
- **Dividendi: q = 2% l'anno, continuo, nel prezzo delle put** (decisione dell'utente del 04-10-2026: «rendimento da
  dividendo fisso al 2% nel prezzo delle put come scelta principale; zero come sensibilità descrittiva. Portafoglio
  senza dividendi in entrambe le versioni»). Vale all'apertura e in ogni valutazione successiva. **Il portafoglio resta
  senza dividendi**: l'indice simulato è l'indice di prezzo, con e senza protezione. Sensibilità descrittiva: q = 0.
- **Tempo**: T = giorni di calendario fra il giorno e la scadenza, diviso 365.
- **Scadenza**: giorno di ingresso + N mesi di calendario (stesso giorno del mese; l'ultimo del mese se non esiste,
  `eventi_f.mesi_prima`); se non è una seduta di `GSPC.INDX`, **la seduta precedente**. Mai la successiva.
- **Valore a scadenza**: max(K1 − S_T, 0) − max(K2 − S_T, 0) sulla chiusura della seduta di scadenza, regolato in
  denaro. È `put_spread` con T = 0.
- **Nessun costo di transazione**, nessuna forbice denaro-lettera, quantità frazionarie.

### Prezzo di prova, calcolato passo per passo (solo apertura) — q = 2%

Spread a 12 mesi aperto alla prima seduta di settembre 2008. Il valore a scadenza e l'esito **non** sono stati calcolati.

    Dati letti: chiusura GSPC del 2008-09-02 = 1277,58 ; VIXCLS del 2008-09-02 = 21,99 ; DTB3 del 2008-09-02 = 1,69 (sconto, %)
    Scadenza: 2008-09-02 + 12 mesi = 2009-09-02, che è una seduta ; 365 giorni di calendario ; T = 365/365 = 1
    Tasso: P = 1 − 0,0169·91/360 = 0,99572806 ; r = (365/91)·ln(1/P) = 0,01717143 (1,7171%)
    Dividendo: q = 0,02 ; S·e^(−qT) = 1277,58 × 0,98019867 = 1252,2822
    Strike: K1 = 0,95 × 1277,58 = 1213,7010 ; K2 = 0,75 × 1277,58 = 958,1850

    put comprata — K1 = 1213,7010, σ = 0,2199
      ln(S/K) = 0,05129329 ; (r − q + σ²/2)·T = 0,02134943 ; σ·√T = 0,21990000
      d1 = (0,05129329 + 0,02134943) / 0,2199 = 0,330344 ; d2 = 0,110444
      N(d1) = 0,629430 ; N(d2) = 0,543972 ; N(−d1) = 0,370570 ; N(−d2) = 0,456028
      K1·e^(−rT) = 1193,0379 ; put = 1193,0379 × 0,456028 − 1252,2822 × 0,370570 = 80,0012 punti (6,262% di S)

    put venduta — K2 = 958,1850, σ = 0,2699
      ln(S/K) = 0,28768207 ; (r − q + σ²/2)·T = 0,03359443 ; σ·√T = 0,26990000
      d1 = (0,28768207 + 0,03359443) / 0,2699 = 1,190354 ; d2 = 0,920454
      N(d1) = 0,883046 ; N(d2) = 0,821332 ; N(−d1) = 0,116954 ; N(−d2) = 0,178668
      K2·e^(−rT) = 941,8721 ; put = 941,8721 × 0,178668 − 1252,2822 × 0,116954 = 21,8232 punti (1,708% di S)

    spread = 80,0012 − 21,8232 = 58,1780 punti indice = 4,5538% della chiusura
    funzione del codice put_spread(...) = 58,1780 ; differenza 0
    sensibilità descrittiva: inclinazione 0 → 69,0666 punti (5,4060%) ; inclinazione +10 → 44,7700 punti (3,5043%)
    sensibilità descrittiva: q = 0 → 52,0141 punti (4,0713%) ; put comprata 71,0580, put venduta 19,0439

Il valore con q = 0 è quello della prima stesura di questa pre-registrazione: con q = 2% lo stesso spread costa
6,16 punti in più (58,1780 contro 52,0141).

## Regola dei buchi

Nelle sedute di `GSPC.INDX` senza VIX o senza DTB3 vale **l'ultimo valore noto prima della seduta, mai uno successivo**.
Se quel valore è più vecchio di 7 giorni di calendario il programma si ferma (`DatoMancante`): nessun dato sostituito.
Nel periodo il caso non si presenta (età massima 1 giorno per il VIX, 3 per DTB3: tabella dei controlli). Le
osservazioni di VIX e DTB3 in giorni che non sono sedute di GSPC non si usano.

## Il portafoglio

- **Partenza**: 100 investito nell'indice alla chiusura del **1990-01-02** (prima seduta del periodo). **Fine**:
  chiusura del **2025-12-31**. Portafoglio senza protezione: 100 × chiusura / chiusura del 1990-01-02.
- **Valore giornaliero del portafoglio con protezione**: quote dell'indice × chiusura + numero di spread × valore dello
  spread. Nessuna liquidità: tutto ciò che non è nello spread è nell'indice.
- **Premio**: a ogni operazione si spende una **percentuale fissa del valore corrente del portafoglio** alla chiusura
  del giorno di ingresso (dopo l'eventuale incasso di uno spread che scade quel giorno): nella versione A 1,5% a 3
  mesi e 3% a 6, 9 e 12 mesi; nella versione B 3% sempre. Il denaro esce **vendendo quote dell'indice** a quella
  chiusura; numero di spread = premio / prezzo dello spread.
- **Incasso a scadenza**: il valore a scadenza si **reinveste nell'indice** alla chiusura della seduta di scadenza.
- **Una operazione alla volta**: non si apre un nuovo spread mentre uno è aperto. Uno spread che scade il giorno D è
  chiuso alla chiusura di D, e alla stessa chiusura se ne può aprire un altro.
- **Tetto**: versione A, 6% sui 360 giorni precedenti (somma dei premi degli ingressi con data > D − 360 giorni più la
  nuova operazione; oltre il 6% non si entra); versione B, nessun tetto. Dettagli nella sezione «Due versioni di
  budget». *La prima stesura fissava il tetto ad anno solare (due operazioni l'anno al 3%): superata dalla decisione
  dell'utente del 04-10-2026.*
- **Parte coperta senza limite**: numero di spread = premio / prezzo dello spread, qualunque sia il risultato. Quando
  lo spread costa meno del premio in percentuale dell'indice, la parte coperta supera il 100% del portafoglio (vedi
  «Riduzione massima teorica»): la specifica fissa il premio, non la quota coperta, e **non si mette nessun limite**.
- **Nessun raddoppio**: la percentuale del premio è sempre quella della sua versione e della sua scadenza, qualunque
  sia l'esito delle operazioni precedenti.
- **Valutazione giornaliera dello spread aperto: a modello** (approvato dall'utente), con la stessa formula dell'apertura, chiusura, VIX e DTB3
  del giorno (regola dei buchi compresa) e tempo residuo; nel giorno di ingresso il valore coincide con il premio,
  quindi l'acquisto non muove il valore del portafoglio. Il ribasso si misura su questi valori. Alla fine del periodo
  (2025-12-31) gli spread ancora aperti restano al valore di modello di quel giorno; per uno spread che scade oltre
  l'ultima seduta dell'archivio (2026-10-02) la scadenza è la data di calendario, senza lo spostamento alla seduta
  precedente. Robustezza descrittiva: spread aperto valutato al solo valore intrinseco.

## Le quattro regole di ingresso — quando si entra

Segnali mensili: si **leggono all'ultimo giorno di calendario del mese t** e l'ingresso avviene **alla chiusura della
prima seduta del mese t + 1** (la seduta successiva alla lettura). Nessuno sguardo in avanti: la lettura usa solo dati
con data ≤ t. Prima lettura 1989-12-31 (ingresso 1990-01-02), ultima 2025-11-30: 432 letture.

1. **Sempre accesa, rinnovo continuo.** Ingresso alla prima seduta del periodo (1990-01-02); poi, alla chiusura di
   ogni seduta in cui non c'è uno spread aperto e il tetto lo permette, se ne apre uno. In pratica: rinnovo nella
   seduta di scadenza; se il tetto mobile della versione A blocca, alla prima seduta in cui non blocca più.
2. **Composito del Test F ≥ 3.** `composito5` di `test_f.calcola_mesi` alla fine del mese t (dati pubblicati entro t,
   ritardi e versioni ALFRED del Test F, lettura della curva corretta con ADR-071; niente di ricalcolato qui). Se è ≥ 3, non c'è uno spread aperto e il tetto lo
   permette, si entra alla prima seduta di t + 1. Finché la condizione resta accesa, alla scadenza si riapre al primo
   ingresso mensile utile.
3. **Composito ≥ 3 e VIX sotto la sua mediana a 12 mesi.** Come la 2, e in più: ultimo VIX noto alla fine del mese t
   **strettamente inferiore** alla mediana delle chiusure giornaliere del VIX nei 12 mesi di calendario che finiscono
   in t (t compresa, t − 1 anno escluso — la stessa finestra di M_t nel Test F). La finestra deve essere intera: la
   prima lettura possibile è il **1990-12-31**, il primo ingresso il **1991-01-02**. Nel 1990 la regola 3 non entra
   (approvato dall'utente: «regola 3 dal 1991-01-02: ok, dichiaralo»): le due celle del verdetto partono dal 1991.
4. **Faber.** `test_f.faber`: chiusura dell'ultima seduta del mese t sotto la media delle ultime 10 chiusure mensili
   (t compresa). Se è accesa, non c'è uno spread aperto e il tetto lo permette, si entra alla prima seduta di t + 1.

**Mesi senza composito: nessuno, dopo la correzione.** Alla prima stesura il composito mancava in 23 delle 432
letture, sempre per il segnale dei tassi: la riga della curva GSW a t − 11 giorni cadeva in un festivo e nel file è
`NA`. L'utente ha deciso di correggere la lettura nel codice condiviso («per la curva, ultimo giorno valido
precedente»): **ADR-071**, `test_f.riga_gsw`, ultimo giorno valido precedente, mai in avanti, non più vecchio di 7
giorni. **Il Test G usa il composito corretto.** Riletto dopo la correzione: **432 letture su 432 con il composito**
(635 fini mese su 635 dal 1973-02 al 2025-12). Se a una lettura il composito mancasse comunque (nessuna riga valida
entro 7 giorni, o un altro segnale mancante), **resta fail-closed**: le regole 2 e 3 non entrano, non si usa il
composito del mese prima; uno spread già aperto resta aperto. Faber: nessuna lettura mancante. L'effetto della
correzione sul Test F (verdetto invariato) è nella nota in fondo a `backtest/drawdown_alpha/2026-10-01_referto_test_f.md`.

## Controlli sui dati — eseguiti il 04-10-2026

Comando: `python backtest/drawdown_alpha/test_g_dati.py --segnali --tetto` (interprete del venv del repo), rieseguito
dopo la correzione ADR-071 e con q = 2%: i numeri di questa tabella non sono cambiati.

| controllo | GSPC.INDX | VIXCLS | DTB3 |
|---|---|---|---|
| prima data (valore) | 1927-12-30 (17,66) | 1990-01-02 (17,24) | 1954-01-04 (1,33) |
| ultima data | 2026-10-02 | 2026-10-01 | 2026-10-01 |
| osservazioni totali | 24.806 | 9.286 | 18.179 |
| prima / ultima nel periodo | 1990-01-02 / 2025-12-31 | 1990-01-02 / 2025-12-31 | 1990-01-02 / 2025-12-31 |
| osservazioni 1990-2025 | 9.067 | 9.092 | 9.005 |
| sedute di GSPC senza il dato | — | **3** | **75** |
| buchi più lunghi | — | 1 seduta: 1991-03-01, 1997-01-31, 1997-11-26 | 1 seduta ciascuno (75 buchi; i primi: 1990-01-15, 1990-10-08, 1990-11-12, 1991-01-21, 1991-10-14) |
| osservazioni in giorni senza seduta di GSPC | — | 28 (2004-06-11 → 2025-11-27) | 13 (1996-04-05 → 2025-01-09) |
| età massima dell'ultimo valore noto | — | 1 giorno (seduta 1991-03-01, valore del 1991-02-28) | 3 giorni (seduta 1990-01-15, valore del 1990-01-12) |
| sedute senza valore entro 7 giorni | — | 0 su 9.067 | 0 su 9.067 |
| valori ≤ 0 | 0 | 0 | 13 uguali a zero (2008-12-10 → 2015-10-22), 8 negativi (2015-09-18 → 2020-03-26, il più basso −0,05) |
| minimo / massimo | 295,46 (1990-10-11) / 6.932,05 (2025-12-24) | 9,14 (2017-11-03) / 82,69 (2020-03-16) | −0,05 (2020-03-26) / 7,99 (1990-03-09) |
| anomalie | variazione giornaliera più ampia +11,58% (2008-10-13) e −11,98% (2020-03-16); nessuna oltre il 15% | nessun valore fuori da [5, 100], nessuno non finito | nessun valore fuori da [−1, 20], nessuno non finito |

Sedute senza DTB3 per anno: 3 l'anno nel 1990-1994 e nel 1996-1997; 1 nel 2000, 2006, 2017, 2023; 2 in tutti gli altri
(le prime date — 1990-01-15, 1990-10-08, 1990-11-12 — sono festività del mercato obbligazionario con la Borsa aperta;
le altre non sono state classificate una per una). Sedute senza VIX: 1 nel 1991, 2 nel 1997. La
tabella anno per anno è nell'uscita dello script.

**Da quando esistono i segnali** (da `test_f.calcola_mesi`, calcolo dal 1967-01-31 al 2025-12-31): composito a 5 dalla
fine mese 1973-02-28 al 2025-12-31, **635 fini mese** (605 prima della correzione ADR-071); Faber disponibile in tutte
le fini mese calcolate (708); la serie GSPC parte dal 1927-12-30. Letture del Test G (1989-12 → 2025-11): 432, di cui
**0 senza composito** (23 prima della correzione) e 0 senza Faber.
**Mediana a 12 mesi del VIX**: prima fine mese con la finestra intera 1990-12-31 (253 osservazioni).

## Misure — definizioni fissate ora, da calcolare solo alla fermata 2

Per ogni regola × scadenza, in ciascuna delle due versioni di budget (16 + 16 = 32 combinazioni), con inclinazione +5
e q = 2%:

- **Rendimento annuo**: (valore finale / 100)^(365 / giorni di calendario dal 1990-01-02 al 2025-12-31) − 1.
- **Ribasso**: discesa dal massimo precedente al minimo successivo sulle **chiusure giornaliere del valore del
  portafoglio**. **Ribasso massimo**: il più profondo dell'intero periodo, per ciascun portafoglio sulla propria serie.
- **I tre ribassi peggiori**: quelli del portafoglio **senza protezione**, con la definizione comune del filone
  (`episodi.py`: il picco è il massimo mobile dal 1990-01-02, un nuovo massimo chiude l'episodio, il fondo è il minimo
  nell'intervallo); si prendono i tre episodi più profondi. Per ognuno, P = data del picco, F = data del fondo.
  **Con protezione si misura sulle stesse due date**: profondità con protezione = valore(F) / valore(P) − 1 del
  portafoglio protetto. Descrittivo accanto: il ribasso massimo del portafoglio protetto dentro la finestra P → F.
  (Dalla lista B già pubblicata nella pre-registrazione del Test F, gli episodi più profondi dell'indice dal 1990
  hanno massimo 2007-10-09, 2000-03-24 e 2020-02-19: la fermata 2 li ricalcola, non li assume.)
- **Riduzione media**: per ciascuno dei tre, riduzione = 1 − profondità con protezione / profondità senza; la
  **media aritmetica semplice delle tre riduzioni** (non il rapporto fra le medie).
- **Costo**: rendimento annuo senza protezione − rendimento annuo con protezione, sull'intero periodo, in punti
  percentuali. Può essere negativo.
- **Costo annuo medio dei premi**: somma dei premi pagati, ciascuno in percentuale del valore del portafoglio nel suo
  giorno di ingresso (1,5% o 3% l'uno, secondo versione e scadenza), divisa per gli anni del periodo; accanto, il numero
  di operazioni. È il «premio annuo effettivamente speso» del testo dell'utente e sta accanto a ogni cella.
- **Guadagno delle put in un ribasso del Test F**: fra il massimo P e il fondo F dell'evento, incassi a scadenza
  ricevuti + valore di modello dello spread aperto in F − valore di modello dello spread aperto in P − premi pagati
  dopo P, il tutto diviso per il valore del portafoglio protetto in P.

**Ribassi del Test F usati** — lista A di `eventi_f.eventi_12_mesi`, eventi con massimo ≥ 1990-01-01 e −15% entro il
2025-12-31 (riletti dal codice il 04-10-2026; sono fatti dell'indice, già pubblicati nella pre-registrazione del Test F):

| # | massimo | data −15% | fondo | profondità dell'indice | recessione NBER |
|---|---|---|---|---:|---|
| 1 | 1990-07-16 (368,95) | 1990-08-23 | 1990-10-11 (295,46) | −19,9% | sì |
| 2 | 1998-07-17 (1.186,75) | 1998-08-31 | 1998-08-31 (957,28) | −19,3% | no |
| 3 | 2000-03-24 (1.527,46) | 2000-12-20 | 2002-10-09 (776,76) | −49,1% | sì |
| 4 | 2007-10-09 (1.565,15) | 2008-01-18 | 2009-03-09 (676,53) | −56,8% | sì |
| 5 | 2010-04-23 (1.217,28) | 2010-06-30 | 2010-07-02 (1.022,58) | −16,0% | no |
| 6 | 2011-04-29 (1.363,61) | 2011-08-08 | 2011-10-03 (1.099,23) | −19,4% | no |
| 7 | 2018-09-20 (2.930,75) | 2018-12-20 | 2018-12-24 (2.351,10) | −19,8% | no |
| 8 | 2020-02-19 (3.386,15) | 2020-03-09 | 2020-03-23 (2.237,40) | −33,9% | sì |
| 9 | 2022-01-03 (4.796,56) | 2022-05-09 | 2022-10-12 (3.577,03) | −25,4% | no |
| 10 | 2025-02-19 (6.144,15) | 2025-04-04 | 2025-04-08 (4.982,77) | −18,9% | no |

## Riduzione massima teorica dei tre ribassi peggiori — calcolata prima di ogni simulazione

Chiesta dall'utente il 04-10-2026: «aggiungi alla pre-registrazione, prima di qualsiasi simulazione, la riduzione
massima teorica dei tre ribassi peggiori con questo spread (guadagno massimo 20% della parte coperta), per entrambe le
versioni». **È un tetto teorico, non un risultato**: usa solo il prezzo di apertura dello spread alla seduta del
massimo. Nessun valore a scadenza reale, nessuna simulazione, nessuna regola di ingresso.

**Formula.**

    parte coperta      = premio (% del portafoglio) / costo dello spread (% dell'indice)
    guadagno massimo   = 20% × parte coperta, in % del portafoglio        (20% = strike comprato 95% − strike venduto 75%)
    riduzione massima teorica di un ribasso di profondità d = guadagno massimo / d

**Lo scenario del tetto**: l'operazione si apre esattamente alla seduta del massimo, con il VIX e il tasso di quel
giorno, e lo spread scade al fondo con l'indice a −25% o peggio dal prezzo di ingresso, cioè paga tutto. **Le
approssimazioni**, tutte a favore del tetto: il guadagno si somma al valore del portafoglio al fondo senza togliere il
premio pagato (né la parte di indice venduta per pagarlo); prima della scadenza lo spread vale meno del suo massimo;
le regole di ingresso vere non entrano al massimo e, entrando dopo, hanno strike più bassi e un VIX più alto.
**Dove non è un tetto**: è il tetto di **una sola operazione**. In un ribasso lungo più operazioni successive possono
pagare una dopo l'altra (dal massimo al fondo passano circa 30 mesi nel 2000-02 e 17 nel 2007-09; nel 2020 poco più di
un mese, e lì l'operazione è una). La somma di più operazioni non è limitata da questa tabella.

Tre ribassi più profondi dell'indice dal 1990 (`eventi_f.eventi_12_mesi`, già a referto nel Test F): massimo 2000-03-24
(1.527,46), fondo 2002-10-09, −49,1%; massimo 2007-10-09 (1.565,15), fondo 2009-03-09, −56,8%; massimo 2020-02-19
(3.386,15), fondo 2020-03-23, −33,9%. Uscita di `python backtest/drawdown_alpha/test_g_dati.py --tetto` del 04-10-2026,
q = 2%, inclinazione +5:

| massimo (VIX; DTB3) | scadenza | costo dello spread, % dell'indice | A: premio | A: parte coperta | A: guadagno massimo | A: riduzione massima | B: premio | B: parte coperta | B: guadagno massimo | B: riduzione massima |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2000-03-24 (23,31; 5,74) | 3 mesi | 2,062% | 1,5% | 73% | 14,5% | 30% | 3% | **145%** | 29,1% | 59% |
| | 6 mesi | 3,010% | 3% | 100% | 19,9% | 41% | 3% | 100% | 19,9% | 41% |
| | 9 mesi | 3,454% | 3% | 87% | 17,4% | 35% | 3% | 87% | 17,4% | 35% |
| | 12 mesi | 3,677% | 3% | 82% | 16,3% | 33% | 3% | 82% | 16,3% | 33% |
| 2007-10-09 (16,12; 3,96) | 3 mesi | 1,115% | 1,5% | **134%** | 26,9% | 47% | 3% | **269%** | 53,8% | 95% |
| | 6 mesi | 1,927% | 3% | **156%** | 31,1% | 55% | 3% | **156%** | 31,1% | 55% |
| | 9 mesi | 2,412% | 3% | **124%** | 24,9% | 44% | 3% | **124%** | 24,9% | 44% |
| | 12 mesi | 2,713% | 3% | **111%** | 22,1% | 39% | 3% | **111%** | 22,1% | 39% |
| 2020-02-19 (14,38; 1,55) | 3 mesi | 0,980% | 1,5% | **153%** | 30,6% | 90% | 3% | **306%** | 61,2% | 180% |
| | 6 mesi | 1,908% | 3% | **157%** | 31,4% | 93% | 3% | **157%** | 31,4% | 93% |
| | 9 mesi | 2,551% | 3% | **118%** | 23,5% | 69% | 3% | **118%** | 23,5% | 69% |
| | 12 mesi | 3,008% | 3% | 100% | 19,9% | 59% | 3% | 100% | 19,9% | 59% |

| versione | scadenza | riduzione massima teorica media dei tre (2000; 2007; 2020) | contro la soglia di 1/3 | contro 1/5 |
|---|---|---:|---|---|
| A | 3 mesi | 55,7% (30%; 47%; 90%) | sopra | sopra |
| A | 6 mesi | 62,7% (41%; 55%; 93%) | sopra | sopra |
| A | 9 mesi | 49,5% (35%; 44%; 69%) | sopra | sopra |
| **A** | **12 mesi — cella del verdetto** | **43,7%** (33%; 39%; 59%) | sopra | sopra |
| **B** | **3 mesi — cella del verdetto** | **111,5%** (59%; 95%; 180%) | sopra | sopra |
| B | 6 mesi | 62,7% (41%; 55%; 93%) | sopra | sopra |
| B | 9 mesi | 49,5% (35%; 44%; 69%) | sopra | sopra |
| B | 12 mesi | 43,7% (33%; 39%; 59%) | sopra | sopra |

**Cosa implica.**

- **In nessuna delle otto celle il tetto è sotto un terzo**: REGGE non è escluso per costruzione in nessuna delle due
  celle del verdetto. Se un tetto fosse stato sotto un terzo, REGGE sarebbe stato impossibile con una sola operazione
  per ribasso, e andava dichiarato qui: non è il caso.
- **Cella A (12 mesi): il margine è stretto.** Il tetto medio è 43,7%: per arrivare a un terzo la regola 3 deve
  ottenere circa tre quarti (76%) di quello che otterrebbe un ingresso perfetto al massimo con pagamento pieno, oppure
  far pagare più di un'operazione nello stesso ribasso. Nel 2000 il tetto di una singola operazione è 33%, sulla soglia.
- **Cella B (3 mesi): il tetto è largo** (111,5%; una riduzione oltre il 100% vorrebbe dire portafoglio in guadagno al
  fondo), ma lo spread a 3 mesi scade presto: nei ribassi lunghi lo scenario «scade al fondo» è il più lontano dal vero.
- A 6, 9 e 12 mesi i tetti di A e di B coincidono perché il premio è lo stesso; a 3 mesi B copre il doppio di A.
- **La parte coperta supera il 100%** (in grassetto) in 15 casi su 24: nella versione B a 3 mesi in tutti e tre i
  casi (145%, 269%, 306%), e in entrambe le versioni a 6, 9 e 12 mesi quando il VIX è basso (2007, 2020). Vuol dire
  spread su un nozionale più grande del portafoglio. **Non si mette nessun limite**: la specifica fissa il premio, non
  la quota coperta. Se l'utente vuole un limite al 100% va detto prima della fermata 2.

## Verdetti — due, indipendenti, uno per versione

| versione | cella del verdetto | budget |
|---|---|---|
| **A** — budget annuo uguale | **regola 3 × 12 mesi** | premio 3%, tetto 6% sui 360 giorni precedenti |
| **B** — premio fisso | **regola 3 × 3 mesi** | premio 3%, nessun tetto |

Stesse soglie per tutte e due, inclinazione +5, q = 2%, valutazione a modello, stessi tre ribassi peggiori (quelli del
portafoglio senza protezione):

- **REGGE** se riduzione media ≥ 1/3 **e** costo ≤ 1,5 punti di rendimento annuo.
- **NON REGGE** se riduzione media < 1/5 **o** costo > 3 punti.
- **INCONCLUSIVO** in ogni altro caso (riduzione fra 1/5 e 1/3 con costo ≤ 3; oppure riduzione ≥ 1/3 con costo fra
  1,5 e 3).

Le soglie si confrontano sui numeri non arrotondati. **Ogni versione ha il suo verdetto e nessuno dei due dipende
dall'altro**: non si fondono in un verdetto unico e uno non corregge l'altro. Il referto li scrive affiancati e
dichiara che **i verdetti sono due** e che le combinazioni guardate sono **32 (160 serie con le sensibilità)**; verifica
con i numeri se la cella A coincide con la cella regola 3 × 12 mesi di B.

**Le altre 30 combinazioni sono descrittive**, ciascuna con il premio annuo effettivamente speso accanto; così le
inclinazioni 0 e +10, la valutazione al valore intrinseco e il dividendo q = 0. Nessuna descrittiva riceve
un'etichetta, nessuna entra in un verdetto e nessuna può cambiarlo.

## Limiti

- **Prezzi stimati, non di mercato; le put vere sotto stress costano di più** (limite dell'utente). Qui non ci sono
  quotazioni di opzioni: ogni premio e ogni valore intermedio è un numero di Black-Scholes.
- **VIX a 30 giorni usato per 3, 6, 9 e 12 mesi.** La volatilità implicita a scadenze lunghe non è il VIX: di norma è
  più alta del VIX nei periodi calmi e più bassa nei periodi di stress. Il test non la osserva.
- **Inclinazione fissa.** Nel mercato la put 5% sotto il prezzo ha una volatilità implicita diversa dal VIX e
  l'inclinazione cambia nel tempo e con la scadenza; qui è +5 punti sempre, attaccata allo strike.
- **Dividendo fisso al 2%.** Il rendimento da dividendo dell'S&P 500 non è stato costante nel periodo (più alto nei
  primi anni Novanta, più basso intorno al 2000 e dopo il 2020): q = 2% è una media di comodo, e q = 0 è la
  sensibilità. Il portafoglio non incassa dividendi: i rendimenti annui dei due portafogli sono più bassi del
  rendimento totale, e il «costo», che è la differenza fra i due, ne risente poco.
- **Tasso a 3 mesi per scadenze fino a 12 mesi**, con la conversione che assume 91 giorni alla scadenza del buono.
- **Valore intermedio a modello.** Il ribasso con protezione dipende dal valore dello spread prima della scadenza, che
  è stimato con il VIX del giorno: nei giorni di stress il VIX alto alza sia la put comprata sia la venduta.
- **Nessun costo di transazione**, nessuna forbice, quantità frazionarie, regolamento sulla chiusura.
- **Tetto della versione A a 360 giorni**: non sono 12 mesi di calendario. Serve a non far slittare i rinnovi
  trimestrali; nella regola 1 un ingresso può comunque slittare di qualche seduta se le scadenze anticipate tolgono
  più di cinque giorni in un anno.
- **Parte coperta oltre il 100%**: con il VIX basso lo spread costa poco e il premio fisso compra un nozionale più
  grande del portafoglio (fino al 306% nella versione B a 3 mesi il 2020-02-19). Nessun limite è stato messo.
- **Il tetto teorico non è un limite matematico della strategia**: vale per una sola operazione aperta al massimo.
- **Due verdetti e 32 combinazioni sugli stessi tre ribassi e sugli stessi 36 anni.** Le celle non sono prove
  indipendenti; a 9 e a 12 mesi le due versioni dovrebbero coincidere. La cella B (3 mesi, fino al 12% l'anno di
  premi) e la cella A (12 mesi, 3% l'anno) rispondono a due domande diverse con le stesse soglie.
- **Composito**: eredita i limiti del Test F (EBP ristimato, serie di oggi prima delle versioni ALFRED); la lettura
  della curva è quella corretta con ADR-071 e nel periodo non manca nessuna lettura. Le soglie del composito sono state fissate nel Test F sugli stessi
  anni: la regola 3 non è provata su dati nuovi.
- **Tre ribassi.** Ciascun verdetto poggia sulla media di tre episodi e su una sola storia di 36 anni.
- **VIX prima del 2003**: `VIXCLS` è la serie ricalcolata con il metodo attuale; nel 1990 la regola 3 non ha la mediana.

## Scelte dell'esecutore — approvate dall'utente il 04-10-2026, con correzioni

Ogni punto era l'opzione più semplice e convenzionale dove la specifica lasciava aperto un dettaglio. Nessuna è stata
scelta guardando un risultato. **L'utente le ha approvate il 04-10-2026 prima di qualunque rendimento, correggendo i
punti 1, 9, 12 e 21** (segnati sotto) e aggiungendo i punti 26-27. Registrate in `DECISIONS.md`, ADR-072..074.

1. **Dividendi — corretta dall'utente**: ~~q = 0 nel prezzo e nel portafoglio~~ → **q = 2% continuo nel prezzo delle
   put come scelta principale, q = 0 come sensibilità descrittiva; portafoglio senza dividendi in entrambe le versioni**.
2. **Tasso = `dtb3_continuo(DTB3)` del giorno, per tutte le scadenze** — è la funzione già approvata nel Test F
   (ADR-067) e la specifica nomina solo il 3 mesi.
3. **Volatilità = VIX del giorno per ogni scadenza; inclinazione attaccata allo strike** — è la lettera della
   specifica; nessuna correzione per la struttura a termine.
4. **Ingresso alla chiusura; strike = 0,95 e 0,75 × la chiusura del giorno di ingresso, non arrotondati** — un solo
   prezzo per seduta nell'archivio.
5. **Tempo = giorni di calendario / 365; scadenza = N mesi di calendario, seduta precedente se non è una seduta** —
   convenzione indicata nel compito.
6. **Valore a scadenza sulla chiusura della seduta di scadenza, incasso reinvestito nell'indice quel giorno** — nessuna
   liquidità da remunerare.
7. **Segnali mensili letti a fine mese, ingresso alla prima seduta del mese dopo; se la condizione è accesa e non c'è
   uno spread aperto si entra, altrimenti si aspetta la lettura successiva** — nessuno sguardo in avanti e un solo
   calendario per le regole 2, 3 e 4.
8. **Regola 1: si apre in ogni seduta senza spread aperto, quindi rinnovo nella seduta di scadenza** — è «rinnovo
   continuo» alla lettera.
9. ~~Tetto 6% = al massimo due operazioni per anno solare, ciascuna al 3%.~~ **Superata dalla decisione dell'utente
   del 04-10-2026**: versione A con tetto sui 360 giorni precedenti, versione B senza tetto (vedi punti 21-22).
10. **Una sola operazione aperta alla volta, in entrambe le versioni** — confermato nella decisione del 04-10-2026.
11. **Premio = percentuale fissa del valore corrente del portafoglio (A: 1,5% a 3 mesi, 3% a 6, 9 e 12; B: 3%),
    pagato vendendo quote dell'indice** — «nessun raddoppio» letto come: la percentuale non cambia mai.
12. **Mesi senza composito — corretta dall'utente**: ~~23 su 432, le regole 2 e 3 non entrano~~ → **si usa il
    composito corretto con ADR-071 (ultimo giorno valido precedente della curva): 0 letture mancanti su 432**; se una
    lettura mancasse comunque, lì resta fail-closed.
13. **Mediana del VIX sulle chiusure giornaliere dei 12 mesi di calendario fino alla fine del mese, confronto stretto
    con l'ultimo VIX noto; la regola 3 parte dal 1991-01-02** — il VIX comincia il 1990-01-02 e una finestra parziale
    sarebbe un'altra regola. Approvata espressamente: «ok, dichiaralo».
14. **Buchi: ultimo valore noto, mai in avanti, non più vecchio di 7 giorni** — stesso limite di 7 giorni di
    `test_f.segnale_ntfs`; nel periodo l'età massima è 3 giorni.
15. **Spread aperto valutato ogni giorno a modello** — valutarlo solo a scadenza lo terrebbe a zero proprio al fondo
    dei ribassi; il valore intrinseco resta come robustezza descrittiva. Approvata espressamente: «ok».
16. **Tre ribassi peggiori = i tre episodi più profondi del portafoglio senza protezione (`episodi.py`); con
    protezione, valore al fondo / valore al picco sulle stesse date** — una sola coppia di date per episodio.
17. **Riduzione media = media semplice delle tre riduzioni; costo = differenza dei rendimenti annui composti sull'intero
    periodo** — come scritto nel compito.
18. **In ciascuno dei due verdetti NON REGGE vince se una delle sue due condizioni è vera; soglie sui numeri non
    arrotondati** — è la lettura di «o» nel testo dell'utente.
19. **Periodo: 1990-01-02 → 2025-12-31; spread aperti alla fine valutati a modello** — non si usa il 2026 per chiudere
    le operazioni.
20. **Guadagno delle put su 10 eventi della lista A del Test F, dal massimo al fondo, in percentuale del portafoglio
    protetto al massimo** — la lista viene dal codice, non da un elenco scritto a mano.

Aggiunte il 04-10-2026 con le due versioni di budget (prima di ogni rendimento):

21. **Tetto della versione A — corretta dall'utente**: ~~365 giorni~~ → **premi degli ingressi nei 360 giorni
    precedenti (date > D − 360 giorni) più la nuova operazione, ciascuno in % del portafoglio nel suo giorno di
    ingresso; oltre il 6% non si entra, il 6% esatto è ammesso** — «così i rinnovi trimestrali non slittano».
22. **Ingresso bloccato dal tetto: regola 1 riprova alla seduta successiva, regole 2-4 alla lettura mensile
    successiva; mai un premio ridotto per stare nel tetto** — lo stesso calendario degli ingressi già fissato.
23. **A 9 mesi il premio della versione A è 3% (4,5% limitato a 3%), quindi al più 4% l'anno** — è «massimo 3%» alla
    lettera; il budget annuo «uguale» a 9 mesi non arriva al 6%. Approvata espressamente: «ok, dichiaralo».
24. **Inclinazione 0 e +10, valore intrinseco e q = 0 su tutte le 32 combinazioni, una variazione alla volta: 160
    serie guardate in totale** — la specifica non diceva su quali celle; tutte è la lettura più semplice e il totale
    va dichiarato per intero (erano 128 prima della sensibilità q = 0).
25. **Le celle in cui A e B coincidono restano contate (32), e i due verdetti restano separati anche se la cella A
    coincide con una cella descrittiva di B** — il conto e i ruoli sono fissati prima di sapere quali coincidono; il
    referto verifica la coincidenza con i numeri (richiesta dell'utente).

Aggiunte il 04-10-2026 con l'approvazione:

26. **Sensibilità q = 0: sulle 32 combinazioni, inclinazione +5, valutazione a modello; q = 2% vale anche nelle
    sensibilità di inclinazione e nel valore intrinseco** — una variazione alla volta, nessun incrocio.
27. **Riduzione massima teorica = 20% × premio / costo dello spread alla seduta del massimo, divisa per la profondità
    dell'indice; nessun limite alla parte coperta** — è la formula indicata dall'utente; è il tetto di una sola
    operazione e non della somma di più operazioni nello stesso ribasso, dichiarato nella sezione.

## Cosa resta fissato dopo questa fermata

Il prezzo e le sue convenzioni, con q = 2%; la regola dei buchi; il portafoglio, il premio e il tetto a 360 giorni; il
calendario degli ingressi delle quattro regole, con il composito corretto (ADR-071); le definizioni delle misure; la
lista dei ribassi; le due versioni di budget con i loro due verdetti (A: regola 3 × 12 mesi; B: regola 3 × 3 mesi); il
conto delle combinazioni guardate (32, di cui 30 descrittive; 160 serie); il tetto teorico come riferimento, non come
risultato. **Approvato dall'utente il 04-10-2026 (ADR-072..074): da qui le regole non cambiano più e si scrive la
simulazione.**
