# Popolazione del passo 2

Generato da `python backtest/rematch_50_300m/survival.py popolazione`. Solo cache, nessuna chiamata di rete, nessun rendimento. Regole: addendum 3.

## Cella <50M

| stato | classe | eventi |
|---|---|---:|
| `GUASTO_FONTE` | — | 5 |
| `OSSERVATO` | — | 920 |
| `RISOLTO` | — | 26 |
| `TERMINATO_IN_FINESTRA` | ACQUISIZIONE | 18 |
| `TERMINATO_IN_FINESTRA` | FALLIMENTO | 4 |
| `TERMINATO_IN_FINESTRA` | NON_RISOLTO | 1 |
| `TERMINATO_IN_FINESTRA` | VOLONTARIO_OTC | 13 |
| `TOO_RECENT` | — | 12 |
| `USCITO_DOPO` | ACQUISIZIONE | 230 |
| `USCITO_DOPO` | FALLIMENTO | 85 |
| `USCITO_DOPO` | NON_RISOLTO | 64 |
| `USCITO_DOPO` | VOLONTARIO_OTC | 135 |
| `USCITO_PRIMA` | ACQUISIZIONE | 2 |
| `USCITO_PRIMA` | FALLIMENTO | 2 |
| `USCITO_PRIMA` | VOLONTARIO_OTC | 21 |
| `VIVO_SENZA_STORIA` | — | 10 |
| **totale** | | **1,548** |

Valutabili (senza `TOO_RECENT` e `USCITO_PRIMA`): **1,511**. Osservati + risolti: **946**, copertura **62.6%**.

## Cella 50-300M

| stato | classe | eventi |
|---|---|---:|
| `GUASTO_FONTE` | — | 21 |
| `OSSERVATO` | — | 2,297 |
| `RISOLTO` | — | 33 |
| `TERMINATO_IN_FINESTRA` | ACQUISIZIONE | 32 |
| `TERMINATO_IN_FINESTRA` | FALLIMENTO | 3 |
| `TERMINATO_IN_FINESTRA` | NON_RISOLTO | 1 |
| `TERMINATO_IN_FINESTRA` | VOLONTARIO_OTC | 2 |
| `TOO_RECENT` | — | 32 |
| `USCITO_DOPO` | ACQUISIZIONE | 911 |
| `USCITO_DOPO` | FALLIMENTO | 195 |
| `USCITO_DOPO` | LIQUIDAZIONE | 3 |
| `USCITO_DOPO` | NON_RISOLTO | 16 |
| `USCITO_DOPO` | VOLONTARIO_OTC | 139 |
| `USCITO_PRIMA` | VOLONTARIO_OTC | 4 |
| `VIVO_SENZA_STORIA` | — | 20 |
| **totale** | | **3,709** |

Valutabili (senza `TOO_RECENT` e `USCITO_PRIMA`): **3,673**. Osservati + risolti: **2,330**, copertura **63.4%**.

## Cella >300M

| stato | classe | eventi |
|---|---|---:|
| `GUASTO_FONTE` | — | 45 |
| `OSSERVATO` | — | 6,863 |
| `RISOLTO` | — | 57 |
| `TERMINATO_IN_FINESTRA` | ACQUISIZIONE | 54 |
| `TERMINATO_IN_FINESTRA` | LIQUIDAZIONE | 1 |
| `TERMINATO_IN_FINESTRA` | VOLONTARIO_OTC | 3 |
| `TOO_RECENT` | — | 109 |
| `USCITO_DOPO` | ACQUISIZIONE | 1,502 |
| `USCITO_DOPO` | FALLIMENTO | 191 |
| `USCITO_DOPO` | LIQUIDAZIONE | 2 |
| `USCITO_DOPO` | NON_RISOLTO | 15 |
| `USCITO_DOPO` | VOLONTARIO_OTC | 88 |
| `USCITO_PRIMA` | ACQUISIZIONE | 1 |
| `USCITO_PRIMA` | FALLIMENTO | 2 |
| `USCITO_PRIMA` | VOLONTARIO_OTC | 5 |
| `VIVO_SENZA_STORIA` | — | 11 |
| **totale** | | **8,949** |

Valutabili (senza `TOO_RECENT` e `USCITO_PRIMA`): **8,832**. Osservati + risolti: **6,920**, copertura **78.4%**.
