# Pre-registrazione — addendum 1

Scritto il **2026-09-15, dopo la revisione dell'utente e prima di calcolare qualunque
rendimento.** Integra e, dove lo dice, sostituisce
[`2026-09-15_preregistration.md`](2026-09-15_preregistration.md) (commit `130b0fe`).
Dove questo file non dice niente, vale l'originale. Decisioni: [`DECISIONS.md`](../DECISIONS.md),
ADR-014 … ADR-019.

---

## 1. Cosa cambia

| | pre-registrazione `130b0fe` | questo addendum |
|---|---|---|
| popolazione primaria | variante (b), cooldown 126 giorni | **un evento per emittente ogni 365 giorni** |
| intervallo del verdetto | IC 95% da t CR1 | IC 95% da t CR1 **decide**; bootstrap per emittente affiancato; bootstrap semplice solo nella replica |
| placebo ≈ 0 | IC CR1 include 0 | IC CR1 include 0 **e** \|media\| < 1,5 punti |
| verdetto primario | §3.1 | tabella ordinata, §4 |
| matching con momentum | uno dei due | **decisivo** (§4) |
| sopravvivenza | scenari descrittivi | S0 e S1 obbligatori; segno diverso → INCONCLUSIVO |
| verdetto secondario | INCONCLUSIVO per copertura, da riportare | **scritto ora**, §6 |

Accettate senza modifiche le quattro deviazioni del §14 originale: quiet primario solo
all'indietro con ±365 secondario; P2 (−504, −378] per scegliere il matching; cella 4/4 letterale
più `cluster` da solo; sola soglia $37.500.

---

## 2. Popolazione primaria

Cancello → fascia [$50M, $300M) → **per ciascun emittente il primo evento, il successivo solo
oltre 365 giorni di calendario dall'ultimo tenuto**: `cooldown_filter(eventi, days=365)` di
`tools/backtest_event_time.py`, invariato, con il parametro cambiato. Stesso ordine
dell'originale.

Contato oggi, senza rendimenti:

| | eventi | emittenti | eventi per emittente |
|---|---:|---:|---:|
| replica, cooldown 126 giorni | 3.276 | 1.110 | 2,95 |
| **primaria, 365 giorni** | **2.340** | **1.110** | **2,11** |

Stato a 126 sessioni sul calendario comune: 2.297 `OK`, 3 `ENDED_IN_WINDOW`, 32 `TOO_RECENT`,
8 senza serie. **Misurabili: 2.300.**

| anno | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eventi | 179 | 135 | 145 | 154 | 163 | 264 | 185 | 282 | 290 | 241 | 242 | 60 |
| misurabili | 179 | 135 | 145 | 154 | 162 | 263 | 185 | 279 | 290 | 240 | 241 | 27 |

Due note.

- «Uno per emittente» qui vuol dire **uno per emittente per finestra di 12 mesi**: restano 2,11
  eventi per emittente sull'intero periodo, e il CR1 serve ancora.
- In Svezia la variante (b) usava **126 giorni** (`preregistration.md` svedese, riga 24, nel repo
  <https://github.com/WilliePim/fi-insider-scanner>). Questa
  regola è più severa di quella svedese, non uguale.

La stessa regola vale per le celle <50M, >300M, 4/4 e cluster, e per il passo 5. La variante (b)
a 126 giorni resta **solo** nel passo 1, come replica dell'originale.

---

## 3. Definizioni

Per ciascun matching m ∈ {M_size, M_mom}, sulla popolazione primaria della cella P a 126 sessioni.

- **IC(m)** = media ± t(G−1; 0,975) · SE_CR1, cluster = emittente. Accanto, **bootstrap per
  emittente**: si ricampionano gli emittenti con reinserimento, 1.000 draw, seed 12345. Se i due
  intervalli non concordano sullo zero, lo si riporta; **decide IC(m) da CR1**.
- **S(m), «sopravvive»** ⟺ media > 0 **e** IC(m) esclude 0. **«Muore»** = non sopravvive.
- **Placebo ≈ 0** ⟺ IC CR1 del placebo include 0 **e** |media del placebo| < 1,5 punti
  percentuali. Le finestre placebo sono lunghe 126 sessioni come l'orizzonte, quindi le due medie
  sono sulla stessa scala.
- **Q(M_size)** ⟺ P1 ≈ 0 e P2 ≈ 0. **Q(M_mom)** ⟺ P2 ≈ 0 (P1 è compresso per costruzione, §6
  originale).
- **sel**, il matching di riferimento: fra i matching con Q vero, quello con |media P2| minore; a
  parità |t CR1 di P2| minore; a parità M_size. Se nessuno ha Q vero, sel non esiste.
- **Segno positivo** ⟺ media > 0.

---

## 4. Verdetto primario — tabella ordinata

Si applica la prima riga che vale, dall'alto.

| # | condizione | verdetto | motivo scritto nel report |
|---|---|---|---|
| R0 | sel esiste e il segno della media di sel cambia fra S0 e S1 (§5) | **INCONCLUSIVO** | sopravvivenza |
| R1 | sel non esiste | **INCONCLUSIVO** | placebo non ≈ 0, nessun matching lo corregge |
| R2a | S(M_size) e non S(M_mom), con Q(M_mom) | **NON REGGE** | **effetto reversal, non effetto insider** |
| R2b | S(M_size) e non S(M_mom), senza Q(M_mom) | **INCONCLUSIVO** | reversal non escludibile: il matching con momentum non è credibile |
| R3 | media di sel ≤ 0 | **NON REGGE** | |
| R4 | S(sel) e S(M_mom) e Q(M_mom) | **REGGE** | |
| R5 | S(sel), ma M_mom non è credibile | **INCONCLUSIVO** | reversal non escludibile |
| R6 | altrimenti: media di sel > 0, IC che include 0 | **INCONCLUSIVO** | sotto potenza |

### Conciliazioni dichiarate

1. **«Il matching con placebo più vicino a zero» e «il matching con momentum è decisivo»** possono
   indicare matching diversi. Si tengono entrambe: il placebo sceglie sel (§3), e il momentum ha
   diritto di veto. **REGGE richiede che l'effetto sopravviva anche a M_mom, e che M_mom sia
   credibile** (R4). Un effetto che sopravvive solo al matching per dimensione è NON REGGE (R2a).
   Il momentum non può però salvare un risultato il cui placebo è fallito ovunque (R1).
2. **sel si sceglie solo fra i matching con placebo ≈ 0.** L'ADR-009 lo sceglieva fra tutti per
   |media P2|; col nuovo significato di ≈ 0 quella regola poteva eleggere un matching col placebo
   fallito. ADR-016.
3. **«Muore» include il caso con media positiva e IC che include lo zero.** Con un MDE di 3,8–4,2%
   (§7), un calo modesto può spostare M_mom da significativo a non significativo. Il report
   riporta la differenza evento per evento M_size − M_mom con la sua t CR1, così si vede se il calo
   è grande o marginale. È descrittivo: non cambia la tabella.
4. **R6 è conservativo** anche nel caso in cui sel sia M_size sotto potenza e M_mom sopravviva: il
   matching di riferimento lo sceglie il placebo, non il risultato migliore.
5. I due casi scoperti del testo del prompt — media > 0 con IC che include lo zero e placebo ≈ 0;
   placebo non ≈ 0 senza matching che lo corregga — sono R6 e R1: **INCONCLUSIVO, non NON REGGE**.

---

## 5. Sopravvivenza

### 5.1 Scenari obbligatori

- **S0** (S_−100 nella pre-registrazione originale): rendimento del titolo **−100%**.
- **S1** (S_+15): **+15%**, acquisizione.

Applicati a due gruppi, per il matching sel:

1. gli `ENDED_IN_WINDOW` della popolazione primaria — oggi 3;
2. gli **eventi senza serie prezzi attesi nella cella**, cioè i delistati che la cache non vede.

Gli eventi *con* serie ma senza market cap (11.775 in variante (a)) **non** entrano negli scenari:
hanno prezzi, e mancano per ragioni XBRL, non di sopravvivenza. Si contano per anno.

### 5.2 Quanti non osservati

Su tutti gli eventi con veto, un evento per emittente ogni 365 giorni: per ciascun anno y,
q_y = quota in 50–300M fra gli eventi con fascia; attesi_y = q_y × eventi senza serie;
ρ_y = attesi_y / eventi con fascia in 50–300M. I non osservati della popolazione primaria sono
n_u,y = ρ_y × misurabili_y.

| anno | P con fascia | senza serie | q_y | attesi | ρ_y | misurabili | non osservati | copertura |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 159 | 821 | 18,0% | 148 | 0,93 | 179 | 167 | 51,7% |
| 2016 | 120 | 610 | 18,7% | 114 | 0,95 | 135 | 128 | 51,3% |
| 2017 | 131 | 516 | 19,7% | 101 | 0,77 | 145 | 112 | 56,4% |
| 2018 | 138 | 555 | 17,5% | 97 | 0,71 | 154 | 109 | 58,6% |
| 2019 | 144 | 479 | 20,3% | 97 | 0,67 | 162 | 109 | 59,8% |
| 2020 | 216 | 466 | 23,2% | 108 | 0,50 | 263 | 132 | 66,6% |
| 2021 | 171 | 388 | 20,0% | 78 | 0,45 | 185 | 84 | 68,8% |
| 2022 | 230 | 379 | 22,7% | 86 | 0,37 | 279 | 104 | 72,8% |
| 2023 | 259 | 301 | 25,7% | 77 | 0,30 | 290 | 87 | 76,9% |
| 2024 | 206 | 172 | 23,5% | 40 | 0,20 | 240 | 47 | 83,6% |
| 2025 | 212 | 160 | 20,3% | 32 | 0,15 | 241 | 37 | 86,7% |
| 2026 | 51 | 27 | 19,7% | 5 | 0,10 | 27 | 3 | 90,0% |
| **tot** | | | | | | **2.300** | **1.119** | **67,3%** |

Copertura qui = misurabili ÷ (misurabili + non osservati attesi). Non è la copertura svedese del
§3.2 originale (54,4%), che conta come mancante anche chi ha prezzi ma non market cap.

Media sotto uno scenario, con s = −100% o +15%:

media_s = [ Σ_osservati x_i (con gli `ENDED_IN_WINDOW` a s − r_peer,i) + Σ_y n_u,y · (s − r̄_peer,y) ] / (n_o + n_u)

dove r̄_peer,y è il rendimento medio dei peer osservati dello stesso anno di deposito.

### 5.3 Conseguenza calcolata — non una modifica della regola

**n_u / n_o = 1.119 / 2.300 = 0,486**: il 32,7% della popolazione primaria non è osservabile.

Ignorando i 3 `ENDED_IN_WINDOW`, con m = media osservata contro peer:

- **media_S0 > 0 ⟺ m > 0,486 · (1 + r̄_peer)**, cioè m > **+48,6%** con r̄_peer = 0, **+51,1%** con
  r̄_peer = +5%;
- **media_S1 ≤ 0 ⟺ m ≤ −0,486 · (0,15 − r̄_peer)**, cioè m ≤ **−7,3%** con r̄_peer = 0, **−4,9%** con
  r̄_peer = +5%.

Con la regola R0 così com'è scritta:

- per qualunque m fra circa −5% e +49% il segno cambia fra S0 e S1, e **il verdetto è
  INCONCLUSIVO per sopravvivenza**;
- **REGGE richiederebbe un eccesso osservato di almeno ~+49% a 126 sessioni**: non è raggiungibile
  in pratica;
- un verdetto diverso da INCONCLUSIVO esce solo con m sotto circa −5%, e allora la tabella prosegue
  da R1.

Si applica la regola come scritta. **Se va cambiata — per esempio limitando R0 ai soli
`ENDED_IN_WINDOW`, o sostituendo S0 con un excess 0 come in Svezia — va fatto prima del passo 2,
in un nuovo file datato.**

---

## 6. Verdetto secondario — scritto ora

Criterio svedese (§3.2 originale). Copertura, variante (b) su tutte le bande: **54,4%**, al più
57,1% escludendo il 2026, contro una soglia del 60%.

> **Verdetto secondario: INCONCLUSIVO — copertura 54,4% < 60%.**

Non dipende da nessun rendimento. Le medie P e C del criterio svedese si calcolano e si riportano
per confrontabilità con il test svedese, senza effetto su questo esito.

---

## 7. Potenza sulla popolazione primaria

n = 2.300 misurabili, m = 2,11 eventi per emittente, sd contro peer 65,70% (report del 2026-09-01):

| ρ intra-emittente | 0 | 0,1 | 0,2 |
|---|---:|---:|---:|
| MDE contro peer | **3,84%** | 4,05% | 4,24% |

**L'MDE sta sopra il +3,50% del finding.** La popolazione primaria è più piccola della replica
(2.300 contro ~3.000) e il test ha **meno** della potenza convenzionale dell'80% per vedere un
effetto della dimensione dichiarata. Un INCONCLUSIVO per R6 è quindi un esito atteso anche con
un effetto vero di +3,5%.

---

## 8. Note, come da revisione

- **La cella 4/4 non è testabile**: `terreno` è vero su al più 5 eventi della cella. Si riporta n,
  nient'altro.
- **Il taglio a $25.000 per riga è una proprietà del corpus, non una scelta di questo test**: le
  righe sotto quella soglia non sono mai state raccolte. Per questo la sensibilità a $12.500 non
  esiste.
- **Il «12 mesi dopo» del quiet** resta solo come variante secondaria, dichiarata col suo bias.

---

## 9. Passo 1, invariato

Replica dell'originale sulla variante (b) a 126 giorni, con il comando del §11 originale. Si
riportano accanto: t semplice e **t CR1**; IC bootstrap semplice (quello dell'originale), **IC da
t CR1** e **IC bootstrap per emittente**; tutto anche per anno; e il ponte sul calendario comune.
Criterio di riproduzione e arresto: §11 originale.
