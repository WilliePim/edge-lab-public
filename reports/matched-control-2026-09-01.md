# Controllo appaiato per fascia, e terzili di rendimento passato

> **Public copy note.** Descriptive report of 2026-09-01, not pre-registered: the starting point of the US
> insider re-test, which ended **INCONCLUSIVE** once size-matched peers and placebos were added. Read it together
> with `backtest/rematch_50_300m/STUDY.md`. Where a dilution gate appears, it is a predicate defined for these
> reports and the re-test, **not a validated filter**.

Generato il 2026-09-01. `python tools/matched_control.py --gate dilution`.

## Che cos'e' il controllo

Per ogni evento si prende un titolo della **stessa fascia di capitalizzazione**, alla **stessa data**, **senza acquisti insider nei 60 giorni precedenti**, appaiato sul log-cap piu' vicino. La misura e' la differenza fra i due rendimenti in euro sullo stesso intervallo. Il benchmark si elide: non c'e' piu' un indice di mezzo, e con esso sparisce la distanza di dimensione fra una nano-cap e il Russell 2000.

> **Da che pool escono i controlli.** Dagli emittenti che hanno un market cap e una serie prezzi in cache, cioe' **societa' i cui insider comprano in qualche momento** -- solo non in quel momento. Non e' l'universo small cap generale: e' gia' selezionato. Il confronto e' percio' piu' stretto su una dimensione (stesso tipo di societa') e meno generale su un'altra. Un universo neutro richiederebbe prezzi e capitalizzazioni per migliaia di titoli senza attivita' Form 4, che non sono in cache.

| | |
|---|---:|
| eventi con fascia e prezzi | 13,901 |
| di cui appaiati | 13,867 |
| veto diluizione | dilution |

---

## 1. Evento meno controllo

### Tutte le fasce

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 13,862 | +0.33% | +0.65% | +26.66% | 52% | 1.46 | -0.11% – +0.81% |
| **63 giorni** | 13,839 | +1.27% | +1.47% | +44.25% | 52% | 3.39 | +0.54% – +2.00% |
| **126 giorni** | 13,586 | +2.38% | +2.01% | +58.70% | 52% | 4.73 | +1.31% – +3.34% |

### Fascia <50M

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 1,132 | +0.59% | +1.40% | +46.03% | 52% | 0.43 | -1.87% – +2.95% |
| **63 giorni** | 1,122 | +1.20% | +3.27% | +70.02% | 54% | 0.58 | -3.06% – +5.35% |
| **126 giorni** | 1,095 | +0.98% | +0.02% | +81.75% | 50% | 0.40 | -3.87% – +5.95% |

### Fascia 50-300M

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 3,059 | -0.29% | +0.28% | +27.43% | 51% | -0.57 | -1.33% – +0.65% |
| **63 giorni** | 3,056 | +1.47% | +1.81% | +47.26% | 52% | 1.72 | -0.20% – +3.06% |
| **126 giorni** | 3,009 | +2.41% | +2.46% | +65.70% | 52% | 2.02 | +0.04% – +4.58% |

### Fascia >300M

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 9,671 | +0.49% | +0.67% | +23.08% | 52% | 2.10 | +0.02% – +0.96% |
| **63 giorni** | 9,661 | +1.22% | +1.30% | +39.11% | 52% | 3.07 | +0.48% – +1.99% |
| **126 giorni** | 9,482 | +2.53% | +2.02% | +52.88% | 53% | 4.66 | +1.42% – +3.52% |

---

## 2. Terzili di rendimento a 12 mesi precedente, dentro 50-300M

Se l'excess sta tutto nel terzile peggiore, il meccanismo e' il reversal e l'insider e' il marcatore, non la causa.

### Terzile peggiore (<= -29.6%)

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 1,016 | -0.18% | -0.80% | +29.85% | 49% | -0.19 | -1.94% – +1.51% |
| **63 giorni** | 1,016 | +2.96% | +0.57% | +51.79% | 50% | 1.82 | -0.06% – +6.11% |
| **126 giorni** | 991 | +6.49% | +1.36% | +73.30% | 51% | 2.79 | +2.06% – +11.41% |

### Terzile centrale

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 1,015 | -1.27% | +0.21% | +26.34% | 50% | -1.54 | -3.00% – +0.25% |
| **63 giorni** | 1,013 | -1.51% | +0.70% | +44.64% | 51% | -1.08 | -4.45% – +1.23% |
| **126 giorni** | 1,005 | -1.70% | +1.47% | +58.78% | 51% | -0.92 | -5.23% – +1.69% |

### Terzile migliore (> +4.4%)

| | n | media | mediana | dev.std | hit rate | t | IC 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| **21 giorni** | 1,014 | +0.60% | +0.99% | +25.81% | 54% | 0.74 | -0.99% – +2.33% |
| **63 giorni** | 1,013 | +2.82% | +3.37% | +44.99% | 54% | 1.99 | +0.15% – +5.58% |
| **126 giorni** | 999 | +2.16% | +3.79% | +63.77% | 54% | 1.07 | -1.72% – +6.05% |

_Terzili sui 3,045 eventi 50-300M con rendimento passato calcolabile. Tagli: -29.6% e +4.4%._

---

## Limiti

1. **Il pool di controllo non e' un universo neutro** (vedi sopra).
2. **L'appaiamento e' su fascia, data e log-cap.** Non su settore, non su book-to-market, non su liquidita'. Due titoli della stessa fascia possono avere spread denaro-lettera molto diversi, e su questo universo lo spread e' la voce di costo piu' grande.
3. **Il controllo puo' essere lo stesso titolo per eventi diversi**: non c'e' vincolo di uso unico, quindi i controlli sono correlati fra loro quanto gli eventi.
4. **Sopravvivenza**: un evento entra solo se ESSO e il suo controllo hanno prezzi a entrambi gli estremi. Chi e' fallito non e' qui, ne' da un lato ne' dall'altro.
5. **Nessun costo applicato**: sono rendimenti lordi. La differenza fra due gambe pagherebbe due volte lo spread.
