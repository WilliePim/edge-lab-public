# Copertura dell'identità risolta, per anno: Yahoo e archivio EODHD

Generato da `python backtest/russell_exits/copertura_identita.py 2015 2025`. Identità risolta = nome → CIK e prezzo implicito coerente con la chiusura grezza entro il 3% (pre-registrazione §3). Senza identità il titolo non ha prezzi né bilanci: esce dal campione. Casi = uscite verso il basso con la definizione di ADR-039. Nessun rendimento calcolato.

| anno | istantanea «dopo» | casi | identità con Yahoo | con EODHD | peer | identità con Yahoo | con EODHD |
|---|---|---:|---:|---:|---:|---:|---:|
| 2015 | 2015-06-30 | 182 | 42 (23%) | **162 (89%)** | 1817 | 874 (48%) | **1693 (93%)** |
| 2016 | 2016-06-30 | 155 | 36 (23%) | **147 (95%)** | 1804 | 935 (52%) | **1711 (95%)** |
| 2017 | 2017-06-30 | 144 | 46 (32%) | **137 (95%)** | 1805 | 1007 (56%) | **1715 (95%)** |
| 2018 | 2018-06-30 | 136 | 39 (29%) | **129 (95%)** | 1839 | 1094 (60%) | **1761 (96%)** |
| 2019 | 2019-09-30 | 266 | 106 (40%) | **246 (92%)** | 1724 | 1114 (65%) | **1664 (96%)** |
| 2020 | 2020-06-30 | 164 | 69 (42%) | **156 (95%)** | 1731 | 1172 (68%) | **1664 (96%)** |
| 2021 | 2021-06-30 | 297 | 170 (57%) | **280 (94%)** | 1674 | 1194 (71%) | **1608 (96%)** |
| 2022 | 2022-06-30 | 302 | 180 (60%) | **287 (95%)** | 1640 | 1237 (75%) | **1582 (96%)** |
| 2023 | 2023-06-30 | 186 | 92 (50%) | **171 (92%)** | 1655 | 1323 (80%) | **1591 (96%)** |
| 2024 | 2024-09-30 | 181 | 95 (52%) | **170 (94%)** | 1674 | 1437 (86%) | **1618 (97%)** |
| 2025 | 2025-06-30 | 169 | 125 (74%) | **162 (96%)** | 1682 | 1508 (90%) | **1607 (96%)** |
