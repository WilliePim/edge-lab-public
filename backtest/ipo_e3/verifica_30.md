# E3 — verifica a mano di 30 prospetti

Campione: seme 20260923, fra le IPO rimaste dopo le esclusioni del testo. Valori veri letti alla cieca (`verifica.py campione`), poi confrontati (`verifica.py confronta`).

| # | CIK | nome | campo | vero | parsing | esito |
|---:|---|---|---|---|---|---|
| 1 | 0001609151 | Weave Communications, Inc. | prezzo | 24.0 | 24.0 | giusto |
| 1 | 0001609151 | Weave Communications, Inc. | data | 2021-11-10 | 2021-11-10 | giusto |
| 1 | 0001609151 | Weave Communications, Inc. | lockup | 181 | 180 | **sbagliato** |
| 1 | 0001609151 | Weave Communications, Inc. | offerte | 5000000 | 5000000 | giusto |
| 1 | 0001609151 | Weave Communications, Inc. | dopo | 62906403 | 62906403 | giusto |
| 2 | 0001555279 | 908 Devices Inc. | prezzo | 20.0 | 20.0 | giusto |
| 2 | 0001555279 | 908 Devices Inc. | data | 2020-12-17 | 2020-12-17 | giusto |
| 2 | 0001555279 | 908 Devices Inc. | lockup | 180 | 180 | giusto |
| 2 | 0001555279 | 908 Devices Inc. | offerte | 6500000 | 6500000 | giusto |
| 2 | 0001555279 | 908 Devices Inc. | dopo | 26200762 | 26200762 | giusto |
| 3 | 0001579910 | Resonant Inc | prezzo | 6.0 | 6.0 | giusto |
| 3 | 0001579910 | Resonant Inc | data | 2014-05-28 | 2014-05-28 | giusto |
| 3 | 0001579910 | Resonant Inc | lockup | 180 | 180 | giusto |
| 3 | 0001579910 | Resonant Inc | offerte | 2700000 | 2700000 | giusto |
| 3 | 0001579910 | Resonant Inc | dopo | 6487666 | 6487666 | giusto |
| 4 | 0001620702 | TERRAFORM GLOBAL, INC. | prezzo | 15.0 | 15.0 | giusto |
| 4 | 0001620702 | TERRAFORM GLOBAL, INC. | data | 2015-07-31 | 2015-07-30 | **sbagliato** |
| 4 | 0001620702 | TERRAFORM GLOBAL, INC. | lockup | 180 | 180 | giusto |
| 4 | 0001620702 | TERRAFORM GLOBAL, INC. | offerte | 45000000 | None | non trovato |
| 4 | 0001620702 | TERRAFORM GLOBAL, INC. | dopo | 117506045 | 117506045 | giusto |
| 5 | 0001554923 | Aina Le'a Inc. | prezzo | 13.75 | 13.75 | giusto |
| 5 | 0001554923 | Aina Le'a Inc. | data | 2015-11-25 | 2015-11-25 | giusto |
| 5 | 0001554923 | Aina Le'a Inc. | lockup | 180 | None | non trovato |
| 5 | 0001554923 | Aina Le'a Inc. | offerte | None | 1250000 | non determinabile a mano |
| 5 | 0001554923 | Aina Le'a Inc. | dopo | None | 10334056 | non determinabile a mano |
| 6 | 0001656328 | Sienna Biopharmaceuticals, Inc | prezzo | 15.0 | 15.0 | giusto |
| 6 | 0001656328 | Sienna Biopharmaceuticals, Inc | data | 2017-07-26 | 2017-07-26 | giusto |
| 6 | 0001656328 | Sienna Biopharmaceuticals, Inc | lockup | 180 | 180 | giusto |
| 6 | 0001656328 | Sienna Biopharmaceuticals, Inc | offerte | 4333333 | 4333333 | giusto |
| 6 | 0001656328 | Sienna Biopharmaceuticals, Inc | dopo | 19888258 | 19888258 | giusto |
| 7 | 0001717115 | Tempus AI, Inc. | prezzo | 37.0 | 37.0 | giusto |
| 7 | 0001717115 | Tempus AI, Inc. | data | 2024-06-13 | 2024-06-13 | giusto |
| 7 | 0001717115 | Tempus AI, Inc. | lockup | 180 | 180 | giusto |
| 7 | 0001717115 | Tempus AI, Inc. | offerte | 11100000 | 11100000 | giusto |
| 7 | 0001717115 | Tempus AI, Inc. | dopo | 159788821 | 159788821 | giusto |
| 8 | 0001517401 | Peak Resorts Inc | prezzo | 9.0 | 9.0 | giusto |
| 8 | 0001517401 | Peak Resorts Inc | data | 2014-11-20 | 2014-11-20 | giusto |
| 8 | 0001517401 | Peak Resorts Inc | lockup | 180 | 180 | giusto |
| 8 | 0001517401 | Peak Resorts Inc | offerte | 10000000 | 10000000 | giusto |
| 8 | 0001517401 | Peak Resorts Inc | dopo | 13982400 | 13982400 | giusto |
| 9 | 0001175505 | FIVE PRIME THERAPEUTICS INC | prezzo | 13.0 | 13.0 | giusto |
| 9 | 0001175505 | FIVE PRIME THERAPEUTICS INC | data | 2013-09-18 | 2013-09-18 | giusto |
| 9 | 0001175505 | FIVE PRIME THERAPEUTICS INC | lockup | 180 | 180 | giusto |
| 9 | 0001175505 | FIVE PRIME THERAPEUTICS INC | offerte | 4800000 | 4800000 | giusto |
| 9 | 0001175505 | FIVE PRIME THERAPEUTICS INC | dopo | 16016807 | 16016807 | giusto |
| 10 | 0001858848 | Tenaya Therapeutics, Inc. | prezzo | 15.0 | 15.0 | giusto |
| 10 | 0001858848 | Tenaya Therapeutics, Inc. | data | 2021-07-29 | 2021-07-29 | giusto |
| 10 | 0001858848 | Tenaya Therapeutics, Inc. | lockup | 180 | 180 | giusto |
| 10 | 0001858848 | Tenaya Therapeutics, Inc. | offerte | 12000000 | 12000000 | giusto |
| 10 | 0001858848 | Tenaya Therapeutics, Inc. | dopo | 39324727 | 39324727 | giusto |
| 11 | 0001212458 | PROOFPOINT INC | prezzo | 13.0 | 13.0 | giusto |
| 11 | 0001212458 | PROOFPOINT INC | data | 2012-04-19 | 2012-04-19 | giusto |
| 11 | 0001212458 | PROOFPOINT INC | lockup | 180 | 180 | giusto |
| 11 | 0001212458 | PROOFPOINT INC | offerte | 6329421 | 6329421 | giusto |
| 11 | 0001212458 | PROOFPOINT INC | dopo | 29657817 | 29657817 | giusto |
| 12 | 0001741830 | Kronos Bio, Inc. | prezzo | 19.0 | 19.0 | giusto |
| 12 | 0001741830 | Kronos Bio, Inc. | data | 2020-10-08 | 2020-10-08 | giusto |
| 12 | 0001741830 | Kronos Bio, Inc. | lockup | 180 | 180 | giusto |
| 12 | 0001741830 | Kronos Bio, Inc. | offerte | 13157895 | 13157895 | giusto |
| 12 | 0001741830 | Kronos Bio, Inc. | dopo | 53044266 | 53044266 | giusto |
| 13 | 0001523404 | JP Energy Partners LP | prezzo | None | 20.0 | non determinabile a mano |
| 13 | 0001523404 | JP Energy Partners LP | data | 2014-10-01 | 2014-10-01 | giusto |
| 13 | 0001523404 | JP Energy Partners LP | lockup | 180 | 180 | giusto |
| 13 | 0001523404 | JP Energy Partners LP | offerte | 13750000 | None | non trovato |
| 13 | 0001523404 | JP Energy Partners LP | dopo | 18213502 | None | non trovato |
| 14 | 0001739104 | Elanco Animal Health Inc | prezzo | 24.0 | 24.0 | giusto |
| 14 | 0001739104 | Elanco Animal Health Inc | data | 2018-09-19 | 2018-09-19 | giusto |
| 14 | 0001739104 | Elanco Animal Health Inc | lockup | 180 | 180 | giusto |
| 14 | 0001739104 | Elanco Animal Health Inc | offerte | 62900000 | 62900000 | giusto |
| 14 | 0001739104 | Elanco Animal Health Inc | dopo | 356190000 | 356190000 | giusto |
| 15 | 0001815776 | Graphite Bio, Inc. | prezzo | 17.0 | 17.0 | giusto |
| 15 | 0001815776 | Graphite Bio, Inc. | data | 2021-06-24 | 2021-06-24 | giusto |
| 15 | 0001815776 | Graphite Bio, Inc. | lockup | 180 | 180 | giusto |
| 15 | 0001815776 | Graphite Bio, Inc. | offerte | 14000000 | 14000000 | giusto |
| 15 | 0001815776 | Graphite Bio, Inc. | dopo | 55979002 | 55979002 | giusto |
| 16 | 0001305773 | ConforMIS Inc | prezzo | 15.0 | 15.0 | giusto |
| 16 | 0001305773 | ConforMIS Inc | data | 2015-06-30 | 2015-06-30 | giusto |
| 16 | 0001305773 | ConforMIS Inc | lockup | 180 | 180 | giusto |
| 16 | 0001305773 | ConforMIS Inc | offerte | 9000000 | 9000000 | giusto |
| 16 | 0001305773 | ConforMIS Inc | dopo | 39086637 | 39086637 | giusto |
| 17 | 0001708527 | AZIYO BIOLOGICS, INC. | prezzo | 17.0 | 17.0 | giusto |
| 17 | 0001708527 | AZIYO BIOLOGICS, INC. | data | 2020-10-07 | 2020-10-07 | giusto |
| 17 | 0001708527 | AZIYO BIOLOGICS, INC. | lockup | 180 | 180 | giusto |
| 17 | 0001708527 | AZIYO BIOLOGICS, INC. | offerte | 2941176 | 2941176 | giusto |
| 17 | 0001708527 | AZIYO BIOLOGICS, INC. | dopo | 10225899 | 7091737 | **sbagliato** |
| 18 | 0001875558 | Nuvectis Pharma, Inc. | prezzo | 5.0 | 5.0 | giusto |
| 18 | 0001875558 | Nuvectis Pharma, Inc. | data | 2022-02-04 | 2022-02-04 | giusto |
| 18 | 0001875558 | Nuvectis Pharma, Inc. | lockup | 180 | 180 | giusto |
| 18 | 0001875558 | Nuvectis Pharma, Inc. | offerte | 3200000 | 3200000 | giusto |
| 18 | 0001875558 | Nuvectis Pharma, Inc. | dopo | 12717794 | 12717794 | giusto |
| 19 | 0001974640 | Apogee Therapeutics, Inc. | prezzo | 17.0 | 17.0 | giusto |
| 19 | 0001974640 | Apogee Therapeutics, Inc. | data | 2023-07-13 | 2023-07-13 | giusto |
| 19 | 0001974640 | Apogee Therapeutics, Inc. | lockup | 180 | None | non trovato |
| 19 | 0001974640 | Apogee Therapeutics, Inc. | offerte | 17650000 | 17650000 | giusto |
| 19 | 0001974640 | Apogee Therapeutics, Inc. | dopo | 34128724 | 47615366 | **sbagliato** |
| 20 | 0001358762 | REATA PHARMACEUTICALS INC | prezzo | 11.0 | 11.0 | giusto |
| 20 | 0001358762 | REATA PHARMACEUTICALS INC | data | 2016-05-25 | 2016-05-25 | giusto |
| 20 | 0001358762 | REATA PHARMACEUTICALS INC | lockup | 180 | 180 | giusto |
| 20 | 0001358762 | REATA PHARMACEUTICALS INC | offerte | 5500000 | 5500000 | giusto |
| 20 | 0001358762 | REATA PHARMACEUTICALS INC | dopo | 6818401 | 6818401 | giusto |
| 21 | 0001322554 | Xactly Corp | prezzo | 8.0 | 8.0 | giusto |
| 21 | 0001322554 | Xactly Corp | data | 2015-06-25 | 2015-06-25 | giusto |
| 21 | 0001322554 | Xactly Corp | lockup | 180 | 180 | giusto |
| 21 | 0001322554 | Xactly Corp | offerte | 7037500 | 6853500 | **sbagliato** |
| 21 | 0001322554 | Xactly Corp | dopo | 27708158 | 27708158 | giusto |
| 22 | 0001598968 | Antero Resources Midstream LLC | prezzo | None | 25.0 | non determinabile a mano |
| 22 | 0001598968 | Antero Resources Midstream LLC | data | 2014-11-04 | 2014-11-04 | giusto |
| 22 | 0001598968 | Antero Resources Midstream LLC | lockup | 180 | 180 | giusto |
| 22 | 0001598968 | Antero Resources Midstream LLC | offerte | 40000000 | None | non trovato |
| 22 | 0001598968 | Antero Resources Midstream LLC | dopo | 75940957 | None | non trovato |
| 23 | 0001535929 | ING U.S., Inc. | prezzo | 19.5 | 19.5 | giusto |
| 23 | 0001535929 | ING U.S., Inc. | data | 2013-05-01 | 2013-05-01 | giusto |
| 23 | 0001535929 | ING U.S., Inc. | lockup | 180 | 180 | giusto |
| 23 | 0001535929 | ING U.S., Inc. | offerte | 65192307 | 65192307 | giusto |
| 23 | 0001535929 | ING U.S., Inc. | dopo | 260769230 | 260769230 | giusto |
| 24 | 0001201663 | AUDIENCE INC | prezzo | 17.0 | 17.0 | giusto |
| 24 | 0001201663 | AUDIENCE INC | data | 2012-05-09 | 2012-05-09 | giusto |
| 24 | 0001201663 | AUDIENCE INC | lockup | 180 | 180 | giusto |
| 24 | 0001201663 | AUDIENCE INC | offerte | 5270180 | 5000000 | **sbagliato** |
| 24 | 0001201663 | AUDIENCE INC | dopo | 19393758 | 19393758 | giusto |
| 25 | 0001789940 | First Watch Restaurant Group,  | prezzo | 18.0 | 18.0 | giusto |
| 25 | 0001789940 | First Watch Restaurant Group,  | data | 2021-09-30 | 2021-09-30 | giusto |
| 25 | 0001789940 | First Watch Restaurant Group,  | lockup | 180 | 180 | giusto |
| 25 | 0001789940 | First Watch Restaurant Group,  | offerte | 9459000 | 9459000 | giusto |
| 25 | 0001789940 | First Watch Restaurant Group,  | dopo | 57629596 | 57629596 | giusto |
| 26 | 0001619917 | Patriot National, Inc. | prezzo | 14.0 | 14.0 | giusto |
| 26 | 0001619917 | Patriot National, Inc. | data | 2015-01-15 | 2015-01-15 | giusto |
| 26 | 0001619917 | Patriot National, Inc. | lockup | None | 180 | non determinabile a mano |
| 26 | 0001619917 | Patriot National, Inc. | offerte | 8315700 | 8315700 | giusto |
| 26 | 0001619917 | Patriot National, Inc. | dopo | 26390415 | 26390415 | giusto |
| 27 | 0001604950 | scPharmaceuticals Inc. | prezzo | 14.0 | 14.0 | giusto |
| 27 | 0001604950 | scPharmaceuticals Inc. | data | 2017-11-16 | 2017-11-16 | giusto |
| 27 | 0001604950 | scPharmaceuticals Inc. | lockup | 180 | 180 | giusto |
| 27 | 0001604950 | scPharmaceuticals Inc. | offerte | 6400000 | 6400000 | giusto |
| 27 | 0001604950 | scPharmaceuticals Inc. | dopo | 17610151 | 17610151 | giusto |
| 28 | 0000912766 | LAUREATE EDUCATION, INC. | prezzo | None | 14.0 | non determinabile a mano |
| 28 | 0000912766 | LAUREATE EDUCATION, INC. | data | 2017-01-31 | 2017-01-31 | giusto |
| 28 | 0000912766 | LAUREATE EDUCATION, INC. | lockup | None | 90 | non determinabile a mano |
| 28 | 0000912766 | LAUREATE EDUCATION, INC. | offerte | 35000000 | 35000000 | giusto |
| 28 | 0000912766 | LAUREATE EDUCATION, INC. | dopo | 35000000 | 35000000 | giusto |
| 29 | 0001501756 | Avalanche Biotechnologies, Inc | prezzo | 17.0 | 17.0 | giusto |
| 29 | 0001501756 | Avalanche Biotechnologies, Inc | data | 2014-07-30 | 2014-07-30 | giusto |
| 29 | 0001501756 | Avalanche Biotechnologies, Inc | lockup | 180 | 180 | giusto |
| 29 | 0001501756 | Avalanche Biotechnologies, Inc | offerte | 6000000 | 6000000 | giusto |
| 29 | 0001501756 | Avalanche Biotechnologies, Inc | dopo | 21357278 | 21357278 | giusto |
| 30 | 0001787640 | Convey Holding Parent, Inc. | prezzo | 14.0 | 14.0 | giusto |
| 30 | 0001787640 | Convey Holding Parent, Inc. | data | 2021-06-15 | 2021-06-15 | giusto |
| 30 | 0001787640 | Convey Holding Parent, Inc. | lockup | 180 | None | non trovato |
| 30 | 0001787640 | Convey Holding Parent, Inc. | offerte | 13333334 | 13333334 | giusto |
| 30 | 0001787640 | Convey Holding Parent, Inc. | dopo | 73013291 | 73013291 | giusto |

| campo | estratti | giusti | precisione | non trovati | non determinabili |
|---|---:|---:|---:|---:|---:|
| prezzo | 27 | 27 | 100.0% | 0 | 3 |
| data | 30 | 29 | 96.7% | 0 | 0 |
| lockup | 25 | 24 | 96.0% | 3 | 2 |
| offerte | 26 | 24 | 92.3% | 3 | 1 |
| dopo | 27 | 25 | 92.6% | 2 | 1 |

**Esito**: tutti i campi al 90% o sopra.
