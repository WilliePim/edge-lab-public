# ADR 010 — Verifica dei salti sospetti con le azioni in circolazione: opzione esplicita `verifica_salti="azioni"`, default invariato

**Data:** 2026-10-06 · **Stato:** accettata · **Specchio:** `DECISIONS.md` di edge-lab, ADR-058 (debito sugli studi chiusi)

## Contesto

Un `salto_sospetto` (ADR 006; `quality/checks.py`) è un salto giornaliero vicino a un rapporto di split, senza split
registrato e senza ritorno nelle 20 sedute dopo. Finché non è verificato, i prezzi puliti tolgono **tutta la storia del
codice prima del salto**. La verifica con i massimi dichiarati nel 10-K (`quality/bilanci.py`) copre solo i salti prima
del 2019, sopra 1 dollaro, in borsa: dal 2019 la SEC non chiede più quei massimi.

Contando un universo di società costruito a una data (solo conteggi, prima di qualunque rendimento) si è visto che
cosa questo significa: **un titolo che dopo quella data ha un crollo vero di circa la metà (o due terzi, tre quarti…)
in una seduta non ha una chiusura pulita alla data e non entra nell'universo.** L'esclusione dipende da un fatto
successivo. In un universo di circa 2.000 piccole società USA erano da 23 a 172 società per data di formazione.
Decisione: correggere in market-data, con una verifica nuova fatta sulle azioni in circolazione prima e dopo il salto,
**come opzione esplicita, senza cambiare il comportamento di default**.

## Decisioni

1. **La regola** (`quality/salti_azioni.py`). Per un salto del giorno G con rapporto tipico k, per ognuna delle tre voci
   di `api.sec_azioni` (frontespizio, stato patrimoniale, media ponderata; unità `shares`):
   - **prima** = l'osservazione con la data di riferimento più recente fra quelle con `fine < G` **e** `depositato < G`,
     non più vecchia di **200 giorni**. Depositata prima del salto: un comparativo riesposto dopo uno split porta la
     data vecchia e il numero nuovo, e scambierebbe uno split per un movimento vero;
   - **dopo** = l'osservazione con la data di riferimento più vicina fra quelle con `fine >= G`, entro **200 giorni**
     (per la media ponderata il periodo deve iniziare da G in poi, e valgono solo periodi fino a 125 giorni);
   - q = azioni dopo / azioni prima. La voce dice **movimento vero** se |ln q| ≤ ln 1,25 (azioni ferme entro ±25%);
     **split vero** se |ln(q·k)| ≤ ln 1,25 (azioni cambiate dell'inverso del salto, entro ±25%); altrimenti niente.
     Con k ≤ 0,5 o k ≥ 2 i due intervalli non si toccano.
   - Esito del salto = quello della prima voce, nell'ordine, che dice qualcosa. **Non determinabile** se nessuna voce
     dice qualcosa, se due voci dicono cose opposte, se mancano il CIK, le osservazioni dentro la finestra, o giorno e
     rapporto nel testo della segnalazione.
   Perché ±25% e 200 giorni: fra due bilanci trimestrali le azioni di una società si muovono di pochi punti (riacquisti,
   piani ai dipendenti); un aumento di capitale oltre il 25% insieme a un crollo resta «non determinabile», che è il lato
   prudente. Duecento giorni coprono il buco più lungo fra due depositi consecutivi (un trimestre saltato) e non di più.
2. **Che cosa fa l'opzione.** `api.prices(simboli, clean=True, verifica_salti="azioni")`: i periodi tolti per un
   `salto_sospetto` classificato **movimento vero** tornano nei prezzi puliti, esattamente come se ci fosse una riga
   nel file delle verifiche. **Split vero**: la storia prima del salto è davvero su un'altra scala e il fornitore non
   lo sa: resta esclusa. **Non determinabile**: resta esclusa, come oggi.
   `api.salti_classificati(simboli=None)` restituisce l'elenco con esito, voce, le due osservazioni e il motivo.
3. **Il default non cambia.** Senza l'argomento, `prices()` esegue la stessa interrogazione di prima, non legge i file
   SEC e non calcola niente; `flags()`, `verifications()`, la vista `prezzi_puliti`, il catalogo su disco, i controlli
   e l'aggiornamento non sono toccati. L'opzione non scrive niente nell'archivio dei prezzi.
4. **Calcolata al volo, mai salvata fra le verifiche.** La classificazione è una funzione di due cose che stanno già
   nell'archivio (le segnalazioni e i file SEC): si ricalcola quando serve, con la cache dei lettori SEC (ADR 009) e
   una memoria per processo che `refresh()` azzera. Non entra in `verifiche.jsonl`, che resta il file delle verifiche
   **fatte a mano con un'altra fonte**: mescolarle farebbe perdere la distinzione fra «verificato da una persona» e
   «classificato da una regola», e renderebbe il default dipendente da un file che cambia. Un file di risultati a
   parte sarebbe un secondo stato da tenere allineato alle segnalazioni a ogni aggiornamento: scartato.
5. **Solo titoli USA con CIK.** Fuori dagli USA non c'è un deposito alla SEC da leggere.

## Punto nel tempo: perché non è uno sguardo in avanti, e che cosa resta

Classificare un salto del 2021 usa azioni depositate **dopo** il salto. È informazione successiva alla data del salto,
ma serve a una domanda sola: **la serie storica dei prezzi prima del salto è corretta?** È una domanda sulla qualità
del dato, come uno split che il fornitore registra a posteriori o un periodo verificato a mano anni dopo: la risposta
non dice niente su dove andrà il prezzo, dice se i prezzi che c'erano erano veri. Un backtest che la usa non conosce il
futuro del titolo; al contrario, **smette** di usare il futuro per decidere chi sta nell'universo.

**Rischio residuo.** Un titolo con un salto «non determinabile» dopo la data di formazione di un universo resta
escluso: è ancora un'esclusione che dipende dal futuro. Chi usa l'opzione deve **contarli e dichiararli**, per data di
formazione. Sull'archivio del 06-10-2026: 76.708 salti segnalati su 17.305 titoli USA; 5.530
movimento vero, 241 split vero, 70.937 non determinabili (22.057 senza CIK, 26.600 senza azioni nei file SEC — in gran
parte titoli OTC e salti precedenti ai depositi XBRL —, 20.446 senza osservazioni dentro la finestra, 1.755 con azioni
né ferme né cambiate dell'inverso, 79 con voci in disaccordo). Fra i soli `Common Stock` di borsa: 10.321 salti su
4.240 titoli, 1.226 movimento vero (655 al ribasso, 571 al rialzo), 52 split vero, 9.043 non determinabili; dal 2019:
2.471 salti, 680 movimento vero, 38 split vero, 1.753 non determinabili. Gli emittenti esteri (un solo deposito l'anno) e
le società con più classi di azioni (ADR 009) cadono quasi sempre in «non determinabile».

Secondo rischio: la regola può sbagliare. Un raggruppamento accompagnato da un'emissione che riporta le azioni vicino
al numero di prima sembrerebbe un movimento vero; un errore di scala nel deposito (ADR 009) dà «non determinabile»,
non un esito sbagliato, perché mille volte non è né 1 né 1/k.

## Alternative scartate

- **Cambiare il default dei prezzi puliti**: gli studi già chiusi hanno usato quel default; cambiarlo cambierebbe i loro
  numeri in silenzio. Resta un debito: verificare quali di quegli studi possono aver perso titoli crollati
  (`DECISIONS.md` di edge-lab, ADR-058).
- **Scrivere i «movimento vero» in `verifiche.jsonl`**: punto 4.
- **Usare i prezzi grezzi nel backtest per i titoli esclusi**: rimetterebbe dentro anche gli split mancanti veri.
- **Decidere dal volume** (già riportato nella segnalazione): non distingue abbastanza, e non è una seconda fonte.

## Verifica

`market-data/tests/test_salti_azioni.py`, 9 test su un archivio finto (nessuna rete): tolleranze, testo della
segnalazione, prima e dopo con comparativo riesposto, finestra, classi sommate, media ponderata, ordine delle voci e
disaccordo; sull'archivio: crollo vero, rialzo vero, split vero, non determinabile (senza osservazione dopo; senza
CIK); **default identico riga per riga prima e dopo aver usato l'opzione, e funzionante senza i file SEC**; opzione
sconosciuta o con `clean=False` → errore; verifica a mano ancora valida e separata.

Confronto su un campione reale, lanciato prima e dopo la modifica (06-10-2026): `prices(clean=True)` dal 2010 su 1.517
codici `Common Stock` di borsa (uno ogni 15 in ordine alfabetico), 1.783.377 righe, impronta sha256 delle righe
`107e34c2fbd54112…` **identica**.
