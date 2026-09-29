# Pre-registrazione — ri-test del finding $50–300M

Scritta il **2026-09-15, prima di calcolare qualunque rendimento successivo agli eventi.**
Nessun numero di rendimento in questo file è stato prodotto per questo test: i soli
rendimenti citati vengono da report del 2026-09-01 o dal test svedese, e sono dichiarati
come conoscenza pregressa al §2.

> **Nota della copia pubblica (2026-09-28).** Il testo sotto è la pre-registrazione com'era, salvo i
> rimandi indicati qui. Il veto di diluizione (`dilution.jsonl`, «cancello») è un predicato **definito per
> questo test e per il report originale, non validato**: qui delimita la popolazione, non è un filtro che
> abbia dimostrato di funzionare. Il test svedese citato come «criterio svedese» sta in un repo separato,
> <https://github.com/WilliePim/fi-insider-scanner> (esito NON REGGE). I due ADR svedesi citati
> sotto (ADR-032 e ADR-043 di fi-insider-scanner) sono di quel repo, non di questo; gli altri numeri
> ADR sono quelli di [`DECISIONS.md`](../DECISIONS.md) nella numerazione della copia pubblica.
> L'indice degli spin-off (`data/spinoffs_index.json`) non è incluso in questa copia: senza, `terreno`
> non si calcola (None) e la cella 4/4 resta vuota.

Codice al commit `8da1e07228b9923659be58d4b098a0f90ae3e3af`; il commit che contiene
questo file lo congela. Le decisioni non ovvie stanno in [`DECISIONS.md`](../DECISIONS.md),
ADR-001 … ADR-013. Una modifica a questo file dopo il primo rendimento calcolato è un
nuovo file datato, mai una riscrittura.

---

## 0. Impronte dei dati

I dati stanno sotto `state/`, ignorato da git: l'impronta è l'unico modo di congelarli.
Per le directory: sha256 della sequenza ordinata `nome file + sha256 del contenuto`.

| input | sha256 | dimensione |
|---|---|---:|
| `state/backfill/form4_raw/` | `90ca49b9ff342cf49a83b2ccd914c75242102ef4e6168428981c73274660946a` | 45 file, 112 MB |
| `state/backfill/dilution.jsonl` | `d5659327ac456dea8bdd1ec19276416ffcf46abbb70fb2ae4ed997a037f0c4d4` | 17,0 MB |
| `state/backfill/marketcap_rows.jsonl` | `c572837c7ecfe0c8558cf2af845885de3a41e3798de52adea75562fe8654851b` | 56,9 MB |
| `state/backfill/purchase_history.json` | `9f5b9e8d0940e8f3e6aaf9b201264ae34191ba297ff66f5c0cdb1948f4376950` | 4,7 MB |
| `state/backfill/shares/` | `46ad4e78bf7377b66023b4d9e90a6d44298e537e9d88c203f8c914cc6343226f` | 8.098 file, 30 MB |
| `state/backfill/prices/` | `6db4fa721d9964ca8d4255cf1624377af64d5bdf6f66834b365bad4ac43ec300` | 5.765 file, 410 MB |
| `state/backfill/prices/IWM.csv` | `317989bcd5d2c29595c21ce7bfd09b738542c84e0144d81a06ebd00c19cea1d4` | ultima barra 2026-08-28 |
| `state/backfill/prices/EURUSD=X.csv` | `702b3ceed8b32d77252e6fd6871b06c230306f7a2494ece2b2d68105c111c2c3` | |
| `data/spinoffs_index.json` (non incluso nella copia pubblica) | `11b52be4b7daa8e7b089c49c85e1eabd40eb2e05ab7435056802ee02b980bc8d` | |

Le date dei report (§8) si leggono dalle submissions EDGAR. 425 dei 1.110 emittenti della
cella P hanno storia in shard, e 373 di quegli shard non sono in cache: saranno scaricati al
passo 4 e le loro impronte riportate nel report.

---

## 1. L'evento — ripescato dal codice, non riscritto

Tutti i riferimenti sono a `tools/backtest_event_time.py` al commit sopra, salvo dove indicato.

| elemento | definizione | dove |
|---|---|---|
| universo | corpus `state/backfill/form4_raw/`, 2015Q1–2026Q1, 237.833 righe | docstring, `CORPUS` |
| riga | acquisto open-market codice P, non derivato; **valore ≥ $25.000 per riga, applicato a monte** nel corpus: minimo osservato $25.000, zero righe sotto | corpus |
| 10b5-1 | nessuna riga con `is_10b5_1 = true`; `null` 182.863 (77%, non parsate), `false` 54.970 | corpus |
| evento | (emittente, data di deposito del Form 4); più righe dello stesso giorno si sommano | `load_events`, :201 |
| periodo | `filed_date` ≥ 2015-01-01 | :212 |
| cancello | veto diluizione point-in-time, `state/backfill/dilution.jsonl`, chiave (CIK, `as_of` = deposito); si esclude solo `BLOCKED`. Eventi senza verdetto: 0 | :664–679 |
| fascia | ultimo `mcap` di `marketcap_rows.jsonl` con `trans` ≤ deposito, intervallo **[$50M, $300M)** | :681–706 |
| market cap | azioni XBRL con **`filed` ≤ D, mai `end`**, × prezzo split-adjusted | `tools/marketcap_build.py` al commit `ef0ff29` |
| ordine dei filtri | cancello → fascia → variante (b) | :664, :681, :722 |
| variante (b) | per emittente il primo evento, il successivo solo oltre 126 giorni di calendario | `cooldown_filter`, :239 |
| ingresso | prima barra del titolo **strettamente successiva** al deposito. Mai la data di transazione | :267–275 |
| uscita | ingresso + h barre **della serie del titolo** | :284 |
| rendimento | titolo e IWM portati in euro con `EURUSD=X` a ciascun estremo; excess = r − r_IWM; lordo | :294–307 |
| artefatti | \|r\| o \|r_IWM\| > 500% → escluso da quell'orizzonte | :302 |
| serie finita prima dell'uscita | `PARTIAL`: l'evento **esce** da quell'orizzonte | :285–287 |
| t | iid, media / (sd/√n) — **non clusterizzata** | `tstat`, :170 |
| IC | bootstrap iid percentile, 1.000 draw, seed 12345 | `bootstrap_ci`, :178 |

**Popolazione ricostruita oggi, senza leggere un rendimento.** 72.190 eventi → 61.609
dopo il veto → **7.811 in fascia** (identico al report originale) → **3.276 in variante (b)**,
su **1.110 emittenti**, 2,95 eventi per emittente. Di questi 12 non hanno serie prezzi e
3.218 hanno una serie che arriva a +126 sessioni. Il market cap usato per la fascia ha età
mediana 1 giorno (p90 4, massimo 1.008).

---

## 2. Cosa è già noto, e quindi non è cieco

1. **Il finding**, [`reports/backtest-event-time-2026-09-01-dilution-50-300M.md`](../reports/backtest-event-time-2026-09-01-dilution-50-300M.md) riga 39 (44 nella copia pubblica, dopo la nota iniziale):
   variante (b), 126 sessioni, n 3.213, **+3,50%**, mediana −1,94%, sd 46,07%, **t iid 4,30**,
   IC bootstrap iid [+1,95%, +5,19%].
2. **Un controllo appaiato per dimensione esiste già**, del 2026-09-01:
   [`reports/matched-control-2026-09-01.md`](../reports/matched-control-2026-09-01.md). Cella
   50–300M a 126 sessioni: n 3.009, **+2,41%, t iid 2,02**, IC [+0,04%, +4,58%]. Differisce da
   questo test in quattro punti: quiet di 60 giorni solo all'indietro, ordine cancello →
   cooldown → fascia, t iid, nessun placebo.
3. Nello stesso report, terzili di rendimento passato a 12 mesi dentro 50–300M: peggiore
   **+6,49% (t 2,79)**, centrale −1,70%, migliore +2,16%. È l'indizio che il matching per sola
   dimensione trascini un effetto di reversal, ed è il motivo per cui il matching con
   momentum qui si calcola sempre (§5).
4. Svezia, 2026-09-14, dal prompt: vs peer −0,58% (t −0,34); placebo a −252 contro peer
   +4,54% (t 2,23). Repo: <https://github.com/WilliePim/fi-insider-scanner>.

Questa pre-registrazione è scritta conoscendo 1–4.

---

## 3. Criterio di verdetto

### 3.1 Primario — il testo del prompt del 2026-09-15

Cella P, variante (b), 126 sessioni, contro il matching primario (§6):

- **REGGE** se media > 0 **e** IC 95% esclude 0 **e** placebo ≈ 0.
- **NON REGGE** se media ≤ 0, **oppure** IC 95% include 0 **e** placebo non ≈ 0.
- **INCONCLUSIVO** nei due casi che il testo non copre, dichiarati adesso:
  - media > 0, IC esclude 0, placebo non ≈ 0 → *matching con bias*: il positivo non si legge;
  - media > 0, IC include 0, placebo ≈ 0 → *sotto potenza*.

Operazionalizzazione (ADR-001, ADR-002):

- **IC 95%** = media ± t(G−1; 0,975) · SE_CR1, cluster = emittente.
- **SE_CR1** di una media: V = G/(G−1) · Σ_g (Σ_{i∈g} (x_i − x̄))² / N². È il fattore di
  `tools/table3_regression.py::ols_cluster` (riga 92) con K = 1.
- **placebo ≈ 0** ⟺ l'IC 95% CR1 del placebo include 0. Per il matching primario devono essere
  ≈ 0 **tutti** i placebo validi per quel matching (§6).
- La media si calcola su tutte le coppie valide a 126 sessioni; il placebo sulle coppie con
  storia sufficiente; la media ristretta alle coppie col placebo si riporta accanto.

### 3.2 Secondario — il criterio svedese, copiato

Da `backtest/preregistration.md` del repo svedese (<https://github.com/WilliePim/fi-insider-scanner>), righe 34–42, senza modifiche
salvo i nomi delle colonne:

- **REGGE** se media P (vs IWM) > 0 con t CR1 ≥ 2; media C (vs peer) > 0 con t CR1 ≥ 2; e la
  media di P nello scenario S_zero ha lo stesso segno di P.
- **NON REGGE** se media C ≤ 0, oppure MDE di P ≤ 3,5% e IC bootstrap 95% di P include 0.
- **INCONCLUSIVO** altrimenti. **Copertura < 60% → INCONCLUSIVO, qualunque sia il resto.**
- Copertura = eventi variante (b), tutte le bande, con rendimento a 126 sessioni in stato OK ÷
  tutti gli eventi variante (b) del periodo.

**Copertura misurata oggi, senza rendimenti: 54,4%** — 13.667 eventi con fascia nota e serie
che copre l'uscita, su 25.107. Anche togliendo dal denominatore tutti i 1.164 eventi del 2026,
il massimo possibile è 57,1%. Per anno: 2015 40%, 2016 43%, 2017 46%, 2018 49%, 2019 50%,
2020 56%, 2021 55%, 2022 62%, 2023 67%, 2024 69%, 2025 75%.

**Il verdetto secondario è quindi INCONCLUSIVO per copertura, qualunque cosa diano i
rendimenti.** Si calcola lo stesso e si riporta.

### 3.3 Divergenza fra i due, dichiarata

Il prompt chiama il criterio primario «uguale a quello svedese». Non lo è: nel test svedese il
placebo era **descrittivo** («Nessuna di queste celle può cambiare il verdetto»), c'era una
clausola di copertura, e REGGE chiedeva t CR1 ≥ 2 anche contro l'indice. Si applica il testo
esplicito del prompt come primario perché è l'istruzione più specifica; il criterio svedese
resta come secondario, calcolato per intero. Se il primario va cambiato, va fatto **prima**
del passo 1, in un nuovo file datato.

---

## 4. Popolazione, copertura e sopravvivenza

### 4.1 Il buco che il test non può chiudere

Dei 61.609 eventi che passano il veto (variante (a)), **29.356 (48%) non hanno una fascia**:

| anno | <50M | 50–300M | >300M | senza cap, con serie | senza cap, senza serie |
|---|---:|---:|---:|---:|---:|
| 2015 | 172 | 487 | 1.742 | 1.480 | 2.761 |
| 2016 | 212 | 469 | 1.568 | 1.141 | 2.200 |
| 2017 | 180 | 451 | 1.524 | 916 | 1.755 |
| 2018 | 142 | 423 | 1.923 | 1.050 | 2.020 |
| 2019 | 153 | 525 | 1.970 | 903 | 1.790 |
| 2020 | 205 | 897 | 2.369 | 1.242 | 1.894 |
| 2021 | 155 | 538 | 1.694 | 851 | 1.389 |
| 2022 | 214 | 1.034 | 2.564 | 1.095 | 1.440 |
| 2023 | 328 | 1.036 | 2.289 | 958 | 1.064 |
| 2024 | 277 | 861 | 1.718 | 989 | 678 |
| 2025 | 232 | 902 | 2.182 | 886 | 507 |
| 2026 | 55 | 188 | 574 | 264 | 83 |
| **tot** | **2.325** | **7.811** | **22.117** | **11.775** | **17.581** |

Gli eventi **senza serie** scendono da 2.761 nel 2015 a 83 nel 2026: è la firma dei delistati,
che yfinance non serve. Quelli **con serie ma senza cap** sono in larga parte emittenti senza
azioni XBRL leggibili (multi-classe invisibili, `marketcap_build.py`).

Stimando per anno la quota in 50–300M sugli eventi con fascia dello stesso anno (metodo
dell'ADR-032 di fi-insider-scanner), **ci si attendono 6.709 eventi senza fascia nella cella P**, contro i 7.811
osservati: la cella vede circa il **54%** della sua popolazione.

### 4.2 Trattamento (ADR-010)

- Passo 1: il codice originale, invariato — `PARTIAL` esce dall'orizzonte.
- Passi 2–4, sul calendario comune (§7): serie finita prima dell'uscita e più di 10 sessioni
  prima della fine della cache (2026-08-28) → **delistato**, uscita all'ultimo close tenuto
  piatto (`ENDED_IN_WINDOW`). Uscita oltre la fine della cache → `TOO_RECENT`, escluso.
- Scenari, applicati (i) ai `ENDED_IN_WINDOW` della cella e (ii) agli eventi senza fascia
  attesi in cella, stimati come in 4.1 sulla variante (b):
  - **S_−100**: rendimento del titolo −100% (lo «S0» del prompt);
  - **S_+15**: +15%, acquisizione (lo «S1» del prompt);
  - **S_zero**: excess 0 (lo «S0» del test svedese, usato dal criterio secondario).
- Per un evento non osservato l'excess vs peer è rendimento di scenario − rendimento medio dei
  peer osservati dello stesso anno di deposito; vs IWM, − gamba IWM media degli eventi
  osservati dello stesso anno.

---

## 5. Il controllo appaiato (ADR-005, 006, 007, 008)

- **Pool**: emittenti del corpus con azioni in `shares/` e serie in `prices/` — 4.765 CIK —
  escluso l'emittente dell'evento. **Non è l'universo 10-K**: non è in cache, e i delistati non
  avrebbero comunque prezzi. È il limite principale del test ed è dichiarato qui.
- **Data del matching** D = data del market cap dell'evento (`trans` della riga che ha deciso
  la fascia).
- **Market cap del candidato** a D: azioni con `filed` ≤ D × ultimo close ≤ D entro 5 sessioni —
  la stessa regola di `marketcap_build.py`. Anche la cap dell'evento, **per la sola distanza**,
  si ricalcola con questa funzione; l'appartenenza alla fascia resta quella originale.
- **Stessa fascia** [$50M, $300M) a D.
- **Quiet, primario**: nessuna riga del corpus con `transaction_date` in [D − 365, D] e
  `filed_date` ≤ D. Point-in-time.
- **Quiet, sensibilità**: [D − 365, D + 365], come nel prompt. Non è primario perché condiziona
  sul futuro: esclude i peer i cui insider comprano nei 12 mesi dopo, cioè — se gli acquisti
  insider contengono informazione — proprio i peer con le notizie migliori. Il bias spinge il
  rendimento del peer in basso e l'excess in alto, **a favore di REGGE**. CLAUDE.md: «Il
  lookahead invalida tutto».
- **Nessuna selezione sul futuro dei prezzi del peer**: il peer si sceglie senza guardare se la
  sua serie arriva all'uscita; se esce prima, ultimo close piatto come per l'evento. Peer senza
  barra all'ingresso entro 5 sessioni → coppia scartata e contata.

**Due matching, calcolati sempre entrambi** (il prompt chiede il secondo solo se il placebo del
primo fallisce; calcolarli sempre toglie una biforcazione che dipende da un risultato):

| | distanza |
|---|---|
| **M_size** | \|log cap candidato − log cap evento\| |
| **M_mom** | distanza euclidea su (log cap, r12) standardizzati con media e sd **dei candidati di quella data e fascia**; r12 = close(D) / close(D − 252 sessioni) − 1, \|r12\| ≤ 500%; candidati senza r12 fuori dal pool di M_mom, non da quello di M_size |

- **Pareggi**: vince il CIK numerico minore. Deterministico, nessun seme.
- **Riuso**: un peer può servire più eventi; il riuso si conta e si riporta.

---

## 6. Placebo, e quale matching è primario (ADR-009)

| placebo | finestra (sessioni, rispetto all'ingresso) | valido per |
|---|---|---|
| **P1** | (−252, −126] | M_size. Per M_mom è **compresso per costruzione**: r12 contiene P1 |
| **P2** | (−504, −378] | entrambi |

P1 è quello del prompt. Con M_mom il matching avviene su una variabile che contiene la finestra
del placebo, e il placebo tende a zero anche se il bias c'è: la regola «vince il matching col
placebo più vicino a zero» favorirebbe M_mom meccanicamente. Per questo si aggiunge P2, fuori
dalla finestra di matching di entrambi.

Placebo = rendimento evento − rendimento peer sulla finestra, stesso peer scelto alla data
dell'evento, calendario comune. Copertura oggi: 3.113 eventi hanno storia fino a −252, 2.767
fino a −504.

**Regola, fissata ora:**

1. Se M_size ha P1 ≈ 0 **e** P2 ≈ 0 → **M_size è primario**.
2. Altrimenti è primario il matching con **|media P2| minore** (a parità, |t CR1| minore).
3. «Placebo ≈ 0» per il verdetto: M_size → P1 e P2 ≈ 0; M_mom → P2 ≈ 0.

---

## 7. Calendario comune e scomposizione (ADR-004)

- Sessioni = barre di IWM. Ingresso t0 = prima sessione IWM **dopo** il deposito; uscita =
  t0 + h sessioni.
- Prezzo di ciascuna gamba a una sessione = ultimo close del titolo con data ≤ sessione, entro
  5 sessioni; altrimenti mancante.
- Euro come nell'originale. \|r\| > 500% su qualunque gamba → coppia esclusa e contata.
- Sullo stesso calendario la scomposizione è **esatta** per evento:
  **(r_e − r_IWM) = (r_e − r_peer) + (r_peer − r_IWM)**.
- Per anno di deposito, cella P, matching primario: n, media delle tre differenze, e quota
  (r_peer − r_IWM) / (r_e − r_IWM) dell'aggregato. **«La maggior parte» = quota > 50%**; se
  vale, lo si dice in una riga.
- Il passo 1 usa il calendario dell'originale (barre del titolo). Si riporta anche lo stesso
  insieme di eventi sul calendario comune, come ponte fra i due.

---

## 8. Closed period (ADR-011)

- **Date**: submissions EDGAR (`recent` + shard), forme **10-Q, 10-K, 10-KT**, emendamenti `/A`
  esclusi. R = ultima `filingDate` ≤ T.
- **T** = la `transaction_date` più vecchia fra le righe dell'evento (il prompt dice «acquisti
  entro … dal report»: conta quando l'insider ha comprato, non quando l'ha depositato).
- k = sessioni IWM in (R, T]. **Dentro W** ⟺ k ≤ W, con **W = 10 principale**, 5 e 20 sensibilità.
- **UNKNOWN** se nessun R nei 200 giorni di calendario prima di T (analogo dell'ADR-043 di fi-insider-scanner).
  Si riporta la quota UNKNOWN.
- Per ciascun W, cella P, contro il matching primario: n, media, t CR1, IC 95%, dentro e fuori.
- **Sensibilità descrittiva**: R = ultimo 8-K con item 2.02 ≤ T. Il 10-Q arriva giorni o
  settimane dopo il comunicato sugli utili, e «dopo gli utili» vuol dire dopo il
  comunicato: col solo 10-Q un acquisto post-comunicato ma pre-10-Q finirebbe «fuori».

---

## 9. Le celle

| cella | definizione | ruolo |
|---|---|---|
| **P** | 50–300M, variante (b), 126 sessioni | verdetto |
| <50M | come P, fascia [0, $50M) | descrittiva |
| >300M | come P, fascia [$300M, ∞) | descrittiva |
| **4/4** | P con `score_v3` = 4, cioè `cluster`, `director`, `no_10pct`, `terreno` tutti veri | descrittiva |
| cluster | P con `cluster` = vero | descrittiva |

La cella **4/4** si ricostruisce con le funzioni di `form4_scanner/flags.py` **invariate**
(`score_v3`, `in_spinoff_window`), su transazioni costruite dalle righe del corpus con deposito
≤ data dell'evento e transazione nei 60 giorni prima (la finestra dello scanner), etichette CMP
di `build_labels` come nell'originale. **Oggi `terreno` è vero su 5 eventi su 3.276**: la cella
4/4 ne ha al più 5 ed è non informativa per costruzione. «cluster» da solo è l'analogo della
colonna B svedese e si riporta per questo (ADR-012).

Per ogni cella: vs IWM, vs M_size, vs M_mom × {n, media, mediana, t iid, t CR1, IC 95% CR1,
IC bootstrap iid}, più P1 e P2 per ciascun matching. Per P anche per anno.

---

## 10. Potenza attesa

MDE = (1,96 + 0,84) · sd/√n · √DEFF, DEFF ≈ 1 + (m − 1)ρ con m = 2,95 eventi per emittente e
ρ correlazione intra-emittente ignota. Le sd vengono dai report del 2026-09-01 (§2), non da
questo test.

| confronto | n | sd | ρ = 0 | ρ = 0,1 | ρ = 0,2 |
|---|---:|---:|---:|---:|---:|
| P vs peer | 3.000 | 65,70% | **3,36%** | 3,67% | 3,96% |
| P vs IWM | 3.213 | 46,07% | 2,28% | 2,49% | 2,68% |
| closed period, un lato | 1.500 | 65,70% | 4,75% | 5,20% | 5,60% |
| closed period, un lato | 1.000 | 65,70% | 5,82% | 6,36% | 6,86% |
| closed period, un lato | 500 | 65,70% | 8,23% | 9,00% | 9,71% |

**L'MDE contro peer è 3,4–4,0%, cioè la dimensione dell'effetto originale.** Il test ha potenza
per vedere un +3,5% vero, non per vedere un +1–2% vero: un «NON REGGE» o un «INCONCLUSIVO»
non dimostrano che l'effetto sia zero. Il closed period, spezzato in due, è sotto potenza per
qualunque effetto sotto il 5%.

---

## 11. Riproduzione del test originale (passo 1)

```
python tools/backtest_event_time.py --horizons 21,63,126 --benchmark iwm --cost-bps 100 \
    --start 2015-01-01 --gate dilution --cap-bucket 50-300M --out <directory del test>
```

**Riprodotto** ⟺ variante (b), 126 sessioni: n = **3.213** esatto, e media, mediana, t identici
ai due decimali stampati (+3,50%, −1,94%, 4,30). Altrimenti **ci si ferma** e si cerca il
perché prima di andare avanti.

Si riportano: n, media, mediana, t iid, **t CR1**, IC bootstrap iid, IC CR1, e per anno. L'output
va in una directory del test, non in `reports/`.

---

## 12. Sensibilità sulle soglie (passo 5) — solo se il primario è REGGE

- Soglia per riga **$37.500**. **$12.500 non è eseguibile**: il corpus è tagliato a $25.000 a
  monte, e le righe sotto non sono mai state raccolte.
- Fascia **$30–200M** e **$75–500M**.
- Orizzonte **63** e **252** sessioni.
- Contro il matching primario. Se il segno cambia con la soglia, il risultato è la soglia.

---

## 13. Elenco completo di ciò che si calcola

Nient'altro, e tutto questo anche se i numeri non piacciono.

1. Passo 1: codice originale; t CR1 e IC CR1 sugli stessi numeri; ponte sul calendario comune.
2. Passo 2: celle P, <50M, >300M, 4/4, cluster × {vs IWM, M_size, M_mom}, 126 sessioni; per
   anno su P; scomposizione per anno su P.
3. Passo 2, sensibilità descrittive su P: quiet ±365; sottoperiodo 2022–2025 (gli unici anni
   con copertura ≥ 60%); scenari S_−100, S_+15, S_zero.
4. Passo 3: P1 e P2 per M_size e M_mom, su tutte le celle del passo 2.
5. Passo 4: closed period W = 5, 10, 20 con 10-Q/10-K; W = 10 con 8-K item 2.02; quota UNKNOWN.
6. Passo 5: §12, condizionato.
7. Verdetto primario §3.1 e secondario §3.2.

**Non si calcolano**: orizzonti 21 e 63 fuori dal passo 1; variante (a) fuori dal passo 1;
portafoglio calendar-time; netto dei costi fuori dal passo 1; qualunque altra fascia, soglia o
finestra.

---

## 14. Deviazioni dal prompt, dichiarate prima dei risultati

| punto del prompt | cosa si fa | perché |
|---|---|---|
| criterio «uguale a quello svedese» | testo del prompt primario, criterio svedese secondario | i due non coincidono (§3.3) |
| t originale «clustered per emittente» | si riproduce la t iid dell'originale e si aggiunge la CR1 | nel codice la t è iid (`tstat`, :170) |
| peer senza acquisti «nei 12 mesi precedenti e successivi» | primario [D−365, D]; ±365 come sensibilità | la parte futura è lookahead e gonfia l'excess (§5) |
| placebo −252…−126 con matching su momentum 12 mesi | P1 tenuto; P2 (−504…−378) aggiunto e usato per scegliere il matching | P1 è dentro la variabile di matching di M_mom (§6) |
| peer «dello stesso universo 10-K» | emittenti del corpus con azioni XBRL e prezzi | l'universo 10-K non è in cache e i delistati non hanno prezzi |
| delistati «con l'ultimo prezzo disponibile» | sì dal passo 2; il passo 1 resta l'originale | l'originale li esclude (`PARTIAL`) e la riproduzione deve essere esatta |
| S0 = −100%, S1 = +15% «come nel test svedese» | S_−100, S_+15, e S_zero | nel test svedese S0 era excess 0 |
| «cluster 4/4» | letterale (`score_v3` = 4, n ≤ 5) più `cluster` da solo | con `terreno` la cella è quasi vuota |
| «il test corretto non è mai stato fatto» | il matched control del 2026-09-01 è dichiarato al §2 | per dimensione esisteva; mancavano placebo, momentum, CR1, quiet lungo |
| soglia $25k ±50% | solo $37.500 | $12.500 non esiste nel corpus |
| date report da 10-Q/10-K | primarie come chiesto; 8-K item 2.02 aggiunto come descrittivo | il 10-Q segue il comunicato sugli utili |

---

## 15. Cosa questo test non può fare, saputo in anticipo

1. **Un controllo neutro.** I peer vengono da società i cui insider comprano in qualche momento
   fra il 2015 e il 2026.
2. **I delistati senza serie.** 17.581 eventi con cancello non hanno prezzi: entrano solo negli
   scenari.
3. **Gli emittenti multi-classe**, invisibili agli endpoint XBRL delle azioni.
4. **Gli split**: le azioni sono as-reported, il prezzo è split-adjusted; su un emittente che ha
   splittato la cap sbaglia del fattore di split, in silenzio.
5. **La potenza per effetti piccoli** (§10).
6. **Una data di utili vera**: il 10-Q è un proxy; l'8-K item 2.02 è più vicino ma non tutti i
   comunicati passano da lì.

---

## 16. Costo

Nessuna chiamata a modelli linguistici in nessun passo. Token e costo attesi: **0**. Le sole
chiamate di rete previste sono gli shard delle submissions EDGAR del passo 4.
