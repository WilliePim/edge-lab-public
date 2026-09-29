# Pre-registrazione — Russell 2000, uscite verso il basso (giugno 2015-2025)

Scritta il **16 settembre 2026, prima di calcolare o guardare qualunque rendimento extra.** Direttiva dell'utente del
16 settembre; decisioni dell'utente sulle fonti prese nel piano (partecipazioni SEC trimestrali, prezzi Yahoo). Ramo
`feat/russell-exits`. **Fermata 1**: questo file, `inventario_dati.md` e `risultati/conteggi.md`. Dopo la conferma
dell'utente regole, soglie e verdetti non cambiano; una modifica è un addendum datato, mai una riscrittura.
Decisioni tecniche: `DECISIONS.md`, ADR-038 e seguenti.

> **Stato al 17 settembre: BOZZA, in attesa di tre decisioni dell'utente (ADR-038).** I conteggi di
> `risultati/conteggi.md` usano la definizione «assente a giugno» del §3, che il controllo esterno 2025 ha smentito:
> ritrova 33 cancellazioni ufficiali su 147. Regole e verdetti si fissano solo dopo le decisioni.

> **Stato al 22 settembre: fermata 1 confermata dall'utente.** Le tre decisioni sono state prese; cosa cambia rispetto
> a questo testo sta negli addenda del 21 settembre (`2026-09-21_addendum_falsi_positivi.md`) e del 22 settembre
> (`2026-09-22_addendum_fermata1.md`). Il testo sotto non è stato riscritto.

> **Errata del 22 settembre 2026** (numeri riscritti nella copia pubblica, dove gli ADR sono rinumerati). I rimandi
> ad **ADR-040** (§4, filtri), **ADR-068** (§5, peer), **ADR-069** (§6, ingressi) e **ADR-070** (§8, placebo) sono
> sbagliati: quando il documento fu scritto le decisioni su filtri, peer, ingressi e placebo non erano ancora in
> `DECISIONS.md`; l'ADR-040 è la decisione sui prezzi EODHD, e i numeri 068, 069 e 070 non corrispondono a nessuna
> decisione, né nella numerazione originale né in questa. I numeri giusti sono **ADR-042** (filtri), **ADR-043**
> (peer), **ADR-044** (ingressi), **ADR-045** (placebo), scritti il 22 settembre col contenuto di questo documento. I
> rimandi nel testo sotto restano com'erano, salvo la rinumerazione della copia pubblica.

---

## 1. Domande e verdetti (testo della direttiva)

1. **Investimento**: se entro quando la vendita forzata è finita, e tengo un anno, batto società simili?
2. **Scheda di dicembre 2026**: c'è un recupero nelle prime settimane dopo la ricostituzione?

Criteri uguali per entrambi:
- **REGGE** se tutte vere:
  1. almeno 100 casi e almeno 9 anni con casi;
  2. mediana del rendimento extra > 0;
  3. media delle medie annuali > 0, con t per anno ≥ 2;
  4. media > 0 sia in 2015-2019 sia in 2020-2025;
  5. placebo con |t| < 2 e media più bassa della cella del verdetto.
- **INCONCLUSIVO** se la 2 e la media delle medie annuali > 0 sono vere, ma il t per anno è tra 1 e 2, oppure non si
  raggiunge il punto 1.
- **NON REGGE** in tutti gli altri casi.

| domanda | cella del verdetto | placebo |
|---|---|---|
| 1. Investimento | ingresso B2 × 252 sedute | falsi eventi |
| 2. Scheda di dicembre | ingresso A × +32 sedute | finestra spostata di 63 sedute |

**Ordine di applicazione, fissato ora.** Si controlla prima REGGE (1-5 tutte vere). Altrimenti INCONCLUSIVO se la 2 è vera
e la media delle medie annuali è > 0 e (il t per anno è ≥ 1 e < 2, oppure il punto 1 non è raggiunto). Altrimenti NON
REGGE. Conseguenze lette alla lettera: con t ≥ 2 ma il punto 4 o 5 falso l'esito è NON REGGE; «anni con casi» = anni con
almeno un caso nella cella; il t per anno è quello delle medie annuali con gradi di libertà = anni − 1; nel punto 5 la
«media» del placebo si confronta con la media delle medie annuali della cella del verdetto.

B1, B3, A, C e tutte le celle fuori dalle due del verdetto sono **descrittive**.

## 2. Dati (fase 0) — dettagli in `inventario_dati.md`

| dato | fonte | stato |
|---|---|---|
| date per anno | comunicati FTSE Russell (`date_ricostituzione.csv`) | ufficiali 2017, 2019-2025, dicembre 2026; 2015 e 2018 testo ufficiale da estratto o ristampa; **2016 solo fonti terze** |
| composizione di IWM e IWB | **depositi SEC di iShares Trust** (CIK 1100663; IWM serie S000004344, IWB S000004347): 31 marzo da N-CSR (2015-2019) o N-PORT-P (2020-2025), 30 giugno da N-Q (2015-2018) o N-PORT-P (2020-2025) | **30 giugno 2019 assente per entrambi i fondi**: l'anno 2019 non ha casi. File storici iShares: non disponibili (riverificato) |
| prezzi e volumi | Yahoo (`yfinance`, `Close`, `Adj Close`, `Volume`, `Stock Splits`) dal 2014-01-01; calendario delle sedute di IWM fino al 2026-08-28 | **i delistati mancano** (decisione dell'utente): esclusi e contati |
| bilanci | companyfacts XBRL di EDGAR, solo fatti con `filed` < Rank Day | cache del repo più scaricamenti sul tetto di 3.000 chiamate |
| prova parallela FTSE Russell di novembre 2025 | [LSEG](https://www.lseg.com/en/ftse-russell/research/insights-from-the-november-2025-russell-us-indexes-parallel-run) | **no**: prova interna (data di rango 30 settembre), liste pubbliche non trovate |

## 3. I casi — addendum alla definizione (decisione dell'utente)

- **Uscita verso il basso** = presente in IWM nell'istantanea del **31 marzo**, assente sia da IWM sia da IWB
  nell'istantanea del **30 giugno** dello stesso anno. La direttiva chiede l'ultimo file prima e il primo dopo la
  ricostituzione; i file giornalieri non esistono, quindi la definizione è trimestrale e dichiarata.
- **Verso l'alto** = in IWM al 31 marzo, in IWB al 30 giugno: solo conteggio. **Rimasto** = in IWM in entrambe.
- Confronto fra istantanee: CUSIP dove c'è (2020-2025), altrimenti nome normalizzato; in più il CIK verificato (cambi di
  nome). Più righe della stessa società (classi di azioni) valgono come una sola; esce solo se escono tutte.
- **Identità** (ADR-039): nome → CIK con indice di nomi (corpus Form 4, ticker SEC di oggi, elenco storico SEC dei
  nomi), poi **verifica col prezzo**: valore / azioni della posizione del fondo = chiusura non rettificata del ticker
  alla data, entro il 3%. Non verificata = esclusa, con il motivo (nessun candidato, prezzo diverso, nessun prezzo Yahoo).
- **Esclusioni, in ordine, contate per motivo**:
  1. identità non verificata;
  2. **acquisita, in fusione o delistata fra il 31 marzo e la ricostituzione** (la finestra è allargata dal 31 marzo
     perché l'istantanea è trimestrale): serie Yahoo finita prima di 5 sedute dopo la ricostituzione, oppure nel periodo
     un Form 25, 15-12B/G, 15-15D, DEFM14A/C, PREM14A/C, SC TO-T/C, SC 13E3, SC 14D9 o un 8-K con voce 1.03;
  3. prezzi e volumi insufficienti: meno dell'80% di chiusure o volumi nelle sedute da 126 prima del Rank Day alla
     ricostituzione, o rendimento a 6 mesi / capitalizzazione non calcolabili;
  4. SPAC: SIC 6770 dai depositi EDGAR.

## 4. Filtri di qualità (ADR-040)

Solo fatti con `filed` < Rank Day. Il titolo resta se tutti e quattro sono veri; un filtro non verificabile esclude, ed
è contato a parte da «non passa» (la direttiva dice «resta se»). Codice `filtri_xbrl.py`, test `test_filtri.py`.
1. Flusso di cassa operativo 12 mesi > 0: `NetCashProvidedByUsedInOperatingActivities` → `…ContinuingOperations`.
2. Cassa netta, oppure debito netto / EBITDA < 3; EBITDA ≤ 0 con debito netto > 0 = escluso. Debito e cassa con i tag di
   `tools/backfill_gates.py`; un debito mancante vale zero solo se il bilancio è letto (attivo o patrimonio alla stessa
   data della cassa); EBITDA = `OperatingIncomeLoss` + `DepreciationDepletionAndAmortization` → `DepreciationAndAmortization`.
3. Azioni in circolazione +5% o meno in 12 mesi: `dei:EntityCommonStockSharesOutstanding` → `us-gaap:
   CommonStockSharesOutstanding`, classi dello stesso deposito sommate, deposito più recente contro quello più vicino a
   365 giorni prima (fra 270 e 460), **corrette per i frazionamenti Yahoo fra le due date**.
4. Nessuna fusione o acquisizione annunciata alle liste preliminari: nessun PREM14A/C, DEFM14A/C, SC TO-T/C, SC 13E3,
   SC 14D9 nei 365 giorni prima della data delle liste.

12 mesi = ultimo anno fiscale + progressivo corrente − progressivo dello stesso periodo dell'anno prima (senza anno
fiscale: quattro trimestri consecutivi); dati più vecchi di 270 giorni = non verificabile. `backfill_gates.four_quarters`
**non si usa** (somma trimestri duplicati o non consecutivi).

## 5. Peer (ADR-068)

- Universo: titoli **rimasti** in IWM che superano identità, esclusioni e gli stessi quattro filtri.
- Terzili del rendimento (chiusura rettificata) delle 126 sedute che finiscono al Rank Day, calcolati sull'universo
  dell'anno; il titolo in uscita va nel terzile delle stesse soglie.
- **Capitalizzazione al Rank Day** = valore della posizione di IWM al 31 marzo × chiusura al Rank Day / chiusura al 31
  marzo (stessa serie, rettificata per split). È proporzionale alla capitalizzazione flottante e non risente degli split;
  le azioni XBRL × prezzo sono scartate (azioni non rettificate per split; correzione del repo non validata, ADR-033 e
  ADR-037).
- I 5 dello stesso terzile con capitalizzazione più vicina (distanza in logaritmo, pareggi al CIK minore); uscite con
  meno di 3 peer escluse e contate.
- Rendimento peer = media semplice dei peer **sulle stesse date di ingresso e uscita del titolo**; un peer senza prezzo
  all'ingresso esce dalla media (servono almeno 3). Peer o titolo delistato nella finestra: ultimo prezzo disponibile;
  prezzo dell'offerta in contanti quando il documento dell'offerta è in cache (`survival.leggi_deal`). Casi contati.

## 6. Ingressi (ADR-069) — codice `ingressi.py`, test `test_ingressi.py`

Chiusure = `Close` Yahoo (rettificata per split); volumi = `Volume` Yahoo; indici sul calendario delle sedute.
- **A**: chiusura della ricostituzione (seduta r). **C**: r + 32.
- **B1, B2, B3** = (N, limite) (10, 60), (20, 126), (40, 189). Primo t con r + N ≤ t ≤ r + limite in cui:
  (1) nessuna chiusura delle sedute t−N+1 … t è sotto il minimo di chiusura dalle liste preliminari alla seduta t−N;
  (2) media del volume delle ultime 10 sedute ≤ mediana del volume delle 60 sedute che finiscono al Rank Day.
  Altrimenti ingresso forzato a r + limite. Una seduta con meno dell'80% delle barre nella finestra non decide. Nessun
  ingresso se manca il volume di riferimento o se i dati finiscono prima.
- Test obbligatorio superato: nessun prezzo o volume dopo la seduta d'ingresso cambia l'ingresso (360 prove).

## 7. Orizzonti e finestre

- Rendimento extra = rendimento del titolo (chiusura rettificata) − rendimento medio dei peer, a 63, 126 e 252 sedute
  dall'ingresso, per ogni ingresso.
- Finestre di dicembre: anticipo (Rank Day → liste preliminari), vendita (liste → ricostituzione), coda (ricostituzione →
  +13), recupero (+13 → +32), sempre chiusura su chiusura.
- Casi senza la finestra completa (ultima seduta disponibile 2026-08-28): esclusi da quella cella e contati.

## 8. Statistica

Per ogni cella: casi, media, mediana, quota positivi. **Medie per anno**, poi t sulle medie annuali (errore standard
delle medie annuali / √anni, gradi di libertà anni − 1). Tabella per anno sempre riportata. Tutto anche per 2015-2019 e
2020-2025.
- **Placebo falsi eventi** (ADR-070): per ogni anno, i rimasti dell'universo con la capitalizzazione più bassa non usati
  come peer, in numero pari alle uscite dell'anno con almeno 3 peer; stessi filtri, ingresso B2, peer dagli altri
  rimasti dell'universo (esclusi i falsi eventi stessi); rendimento extra a 252 sedute.
- **Placebo di dicembre**: stesse uscite, finestra di 32 sedute che inizia 63 sedute dopo la ricostituzione.
- **Approssimazione di dicembre** (descrittiva): uscite che passano i filtri e all'ultima seduta di ottobre sono a −30% o
  peggio dall'ultima seduta dell'anno prima; rendimento extra dal secondo venerdì di dicembre all'ultima seduta di
  gennaio dell'anno dopo; stessi peer.

## 9. Conteggi prima dei rendimenti

Preliminari, con la definizione del §3 («assente a giugno»): `risultati/conteggi.md`. Da rifare dopo le decisioni
dell'utente sulla definizione, sul 2024 e sulla fonte dei prezzi (ADR-038).
