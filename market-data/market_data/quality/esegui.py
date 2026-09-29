"""Fase 4: tutti i controlli di qualità, per borsa, con resoconto e segnalazioni per i backtest.

Per ogni borsa (viste di `store/catalog.py`, SQL di `quality/sql.py`):
- **buchi**: sedute del calendario senza barra fra la prima e l'ultima barra di ogni titolo; titoli oltre il 5%;
- **duplicati**: date ripetute nelle serie grezze (tabella `doppioni`);
- **prezzi impossibili**: chiusure a zero o negative; salti giornalieri oltre il 90% senza split registrato;
- **coerenza degli split**: chiusura grezza divisa per il fattore e rettificata continua;
- **split mancanti** (±5%): per fascia di prezzo, con il volume;
- **volume zero ripetuto**: almeno 20 sedute con volume zero e chiusura identica;
- **ticker riusati**: ticker di base con più codici; separati se i periodi non si sovrappongono e gli ISIN (quando ci
  sono) sono diversi.

Controlli con fonti esterne (seme fisso `SEME` per i campioni presi a caso, riproducibili):
- **delistati USA**: 30 azioni ordinarie delistate a caso con CIK: nome e data dell'ultimo deposito (Form 25/15, se
  manca l'ultimo deposito) su EDGAR contro nome e ultima barra EODHD;
- **salti sospetti sopra 1 dollaro (USA)**: 20 a caso, cercati negli 8-K su EDGAR; quota di split veri;
- **barre prima della quotazione (USA)**: azioni ordinarie attive con CIK; data di quotazione = primo 8-A12B, 8-A12G,
  424B1 o 424B4, per società il cui primo deposito EDGAR è dal 1997 in poi e con quel modulo entro due anni dal primo
  deposito (schema di un'IPO); barre più di 30 giorni prima segnalate. I file iShares non sono in questo package;
- **Yahoo**: 100 azioni ordinarie attive USA e 30 europee a caso; quota di chiusure rettificate con scarto oltre l'1%.

**Segnalazioni** (tabella `segnalazioni`). La colonna `esclude` divide due cose diverse:

*Periodi tolti dai prezzi puliti* (salvo verifica a mano): `salto_sospetto` dalla prima barra al giorno prima del salto;
`volume_zero` sulla sequenza; `prima_della_quotazione` dalla prima barra al giorno prima della data di quotazione.

*Note che non tolgono niente*, perché il salto è spiegato: `split_del_fornitore` quando la chiusura rettificata
attraversa il salto senza saltare (il fornitore conosce lo split, la grezza non è rettificata e basta);
`salto_confermato` quando il 10-K della società dichiara un massimo di periodo compatibile con tutte e due le chiusure,
cioè il salto è un movimento di mercato vero.

**Ordine dei tre casi di un salto** (decisione dell'utente, ADR 006 punti 65-67): prima la rettificata continua; poi,
solo per i salti nell'ambito dichiarato, il confronto con l'Item 5 del 10-K (`bilanci.py`); tutto il resto resta
escluso. L'ambito è NASDAQ, NYSE e NYSE ARCA, fascia sopra 1 dollaro, salto prima del 2019, CIK noto: altrove la
verifica **non si fa per scelta**, e questo va detto, non nascosto.

    .venv/Scripts/python.exe -m market_data.quality.esegui [--borse US,LSE] [--senza-esterni]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

import pyarrow as pa

from market_data import config as C
from market_data.quality import bilanci as B
from market_data.quality import esterni as E
from market_data.quality import sql as S
from market_data.store import catalog
from market_data.store import normalize as N

SEME = 20260917
#  L'Item 5 del 10-K riportava massimo e minimo per trimestre fino all'esercizio 2018: la SEC ha tolto
#  l'obbligo (voce 201(c) del Regulation S-K) con le modifiche FAST Act del 2018.
ANNO_SENZA_ITEM5 = 2019
VENUE_VERIFICATE = ("NASDAQ", "NYSE", "NYSE ARCA")
N_CAMPIONE_BILANCI = 10
CACHE_EDGAR_MASSIMA_GB = 8.0
N_DELISTATI, N_SALTI_EDGAR, N_YAHOO_USA, N_YAHOO_EUROPA = 30, 20, 100, 30
BORSE_EUROPA = ("ST", "HE", "CO", "OL", "LSE", "XETRA", "F", "PA", "AS", "BR", "LS", "SW", "MC", "VI")
GIORNI_COERENZA_FINE = 90
SOGLIA_NOME = 0.6
SCARTO_YAHOO = 0.01


def _giorno(x) -> dt.date:
    return x if isinstance(x, dt.date) and not isinstance(x, dt.datetime) else dt.date.fromisoformat(str(x)[:10])


def riusi(con, borsa: str) -> dict:
    righe = con.execute("""
        SELECT ticker, list(code ORDER BY first_date), list(isin ORDER BY first_date), list(first_date ORDER BY first_date),
               list(last_date ORDER BY first_date)
        FROM anagrafica WHERE exchange = ? AND downloaded GROUP BY ticker HAVING count(*) > 1 ORDER BY ticker
    """, [borsa]).fetchall()
    non_separati = []
    for ticker, codici, isin, prime, ultime in righe:
        problemi = []
        for i in range(len(codici)):
            for j in range(i + 1, len(codici)):
                if prime[j] <= ultime[i] and prime[i] <= ultime[j]:
                    problemi.append("periodi sovrapposti {}/{}".format(codici[i], codici[j]))
                if isin[i] and isin[j] and isin[i] == isin[j]:
                    problemi.append("stesso ISIN {}/{}".format(codici[i], codici[j]))
        if problemi:
            non_separati.append({"ticker": ticker, "codici": codici, "problemi": problemi})
    return {"ticker_con_piu_codici": len(righe), "codici": sum(len(r[1]) for r in righe),
            "non_separati": len(non_separati), "esempi_non_separati": non_separati[:20]}


class Controlli:
    def __init__(self, archivio: Path, log=print, edgar: E.Edgar | None = None, yahoo=E.chiusure_yahoo):
        import duckdb
        self.archivio, self.log = archivio, log
        self.con = C.applica_limiti(duckdb.connect())
        catalog.crea_viste(self.con, archivio)
        self._edgar, self._yahoo = edgar, yahoo
        self.segnalazioni: dict[str, list[dict]] = {}
        self.rng = random.Random(SEME)
        self._cache_iniziale: int | None = None

    @property
    def edgar(self) -> E.Edgar:
        if self._edgar is None:
            self._edgar = E.Edgar(self.archivio)
        return self._edgar

    def borse(self) -> list[str]:
        return [r[0] for r in self.con.execute(
            "SELECT DISTINCT exchange FROM anagrafica WHERE downloaded ORDER BY exchange").fetchall()]

    def prima_barra(self, borsa: str) -> dict[str, dt.date]:
        """Prima barra di ogni codice dai prezzi (non dall'anagrafica: un codice può avere prezzi senza record)."""
        return dict(self.con.execute("SELECT code, min(date) FROM prezzi WHERE exchange = ? GROUP BY code", [borsa]).fetchall())

    def borsa(self, borsa: str) -> tuple[dict, list[dict]]:
        r = {"buchi": S.buchi(self.con, borsa), "duplicati": S.duplicati(self.con, borsa),
             "prezzi_impossibili": S.prezzi_impossibili(self.con, borsa), "coerenza_split": S.coerenza_split(self.con, borsa),
             "ticker_riusati": riusi(self.con, borsa)}
        #  I due controlli a finestra mobile si fanno a blocchi di codici: su tutta la borsa in una volta il picco
        #  di memoria e' quello dei 113 milioni di barre americane. Ogni serie sta tutta dentro un blocco, quindi il
        #  risultato non cambia; il tempo nemmeno, perche' il lavoro e' lo stesso.
        blocchi = S.blocchi_per(self.con, borsa)
        if len(blocchi) > 1:
            self.log("   {} in {} blocchi".format(borsa, len(blocchi)))
        salti, zero = [], []
        for blocco in blocchi:
            salti += S.salti_split_mancanti(self.con, borsa, blocco=blocco)
            zero += S.sequenze_volume_zero(self.con, borsa, blocco=blocco)
        salti.sort(key=lambda x: (x["code"], x["data"]))
        zero.sort(key=lambda x: (x[0], x[1]))
        r["salti_sospetti"] = {"salti": len(salti), "titoli": len({s["code"] for s in salti}),
                               "per_fascia": dict(Counter(s["fascia"] for s in salti)),
                               "titoli_per_fascia": {f: len({s["code"] for s in salti if s["fascia"] == f}) for f in
                                                     ("sotto 0,05", "fra 0,05 e 1", "sopra 1")},
                               "volume": dict(Counter({True: "coerente", False: "non coerente", None: "assente"}[s["volume_coerente"]]
                                                      for s in salti))}
        r["volume_zero"] = {"sequenze": len(zero), "titoli": len({z[0] for z in zero}), "sedute": sum(z[3] for z in zero)}
        r["salti_sospetti"]["per_caso"] = dict(Counter(
            "rettificata continua" if s["rettificata_continua"] else "salta anche la rettificata" for s in salti))
        prime = self.prima_barra(borsa)
        seg = []
        for s in salti:
            giorno = _giorno(s["data"])
            inizio = prime.get(s["code"])
            if not inizio or inizio >= giorno:
                continue
            if s["rettificata_continua"]:
                #  Caso 1: il fornitore conosce lo split e l'ha applicato alla rettificata. La serie grezza salta
                #  perche' non e' rettificata, non perche' e' rotta: si annota il giorno, non si toglie niente.
                seg.append({"code": s["code"], "controllo": "split_del_fornitore", "from_date": giorno,
                            "to_date": giorno, "esclude": False,
                            "detail": "salto del {}: rapporto {:.4f} vicino a {:g}, ma la chiusura rettificata "
                                      "attraversa il salto ({:.4f}): split applicato dal fornitore".format(
                                          giorno, s["rapporto"], s["rapporto_tipico"], s["rapporto_rettificata"])})
                continue
            seg.append({"code": s["code"], "controllo": "salto_sospetto", "from_date": inizio,
                        "to_date": giorno - dt.timedelta(days=1), "esclude": True,
                        "detail": "salto del {}: rapporto {:.4f} vicino a {:g}, fascia {}, volume {}".format(
                            giorno, s["rapporto"], s["rapporto_tipico"], s["fascia"],
                            {True: "coerente", False: "non coerente", None: "assente"}[s["volume_coerente"]])})
        for code, da, a, sedute in zero:
            seg.append({"code": code, "controllo": "volume_zero", "from_date": _giorno(da), "to_date": _giorno(a),
                        "esclude": True, "detail": "{} sedute con volume zero e chiusura identica".format(sedute)})
        return r, seg, salti


    # ---- verifica dei salti sui bilanci (Item 5 del 10-K)
    def verifica_bilanci(self, salti_usa: list[dict]) -> tuple[dict, dict]:
        """Per i salti nell'ambito, confronta le due chiusure con il massimo dichiarato dalla societa' nel suo 10-K.

        Ambito, deciso dall'utente: NASDAQ, NYSE e NYSE ARCA, fascia sopra 1 dollaro, salto prima del 2019, CIK noto.
        Fuori da li' la verifica **non si fa per scelta** e il salto resta escluso come prima: sull'OTC e sulle borse
        estere i bilanci spesso non ci sono, e dal 2019 l'Item 5 non riporta piu' massimo e minimo trimestrali (la SEC
        ha tolto l'obbligo con le modifiche FAST Act del 2018).

        Ritorna (riepilogo, {(code, data del salto): esito}). Bilancio assente o Item 5 illeggibile -> non
        verificabile, cioe' escluso, contato per motivo."""
        righe_anagrafica = self.con.execute(
            "SELECT code, venue, cik, name FROM anagrafica WHERE exchange = 'US' AND cik IS NOT NULL").fetchall()
        anagrafica = {r[0]: (r[1], r[2]) for r in righe_anagrafica}
        nome_societa = {r[0]: r[3] for r in righe_anagrafica}
        dentro, fuori = [], Counter()
        for s in salti_usa:
            if s["rettificata_continua"]:
                fuori["caso 1: split applicato dal fornitore"] += 1
                continue
            venue, cik = anagrafica.get(s["code"], (None, None))
            if s["fascia"] != "sopra 1":
                fuori["fuori ambito: fascia " + s["fascia"]] += 1
            elif _giorno(s["data"]).year >= ANNO_SENZA_ITEM5:
                fuori["fuori ambito: salto dal 2019 in poi, l'Item 5 non riporta piu' i prezzi"] += 1
            elif venue not in VENUE_VERIFICATE:
                fuori["fuori ambito: mercato " + (venue or "ignoto")] += 1
            elif not cik:
                fuori["fuori ambito: CIK ignoto"] += 1
            else:
                dentro.append((s, cik))
        esiti, note, conti, campioni = {}, {}, Counter(), {"vero": [], "fuori scala": []}
        annuali_per_cik: dict[str, list | None] = {}
        for n, (s, cik) in enumerate(dentro, 1):
            if n % 200 == 0:
                self.log("   bilanci: {}/{}, cache {:.1f} GB".format(n, len(dentro), self._cache_edgar_gb()))
            if self._cache_edgar_gb() > CACHE_EDGAR_MASSIMA_GB:
                conti["non verificato: tetto della cache EDGAR raggiunto"] += len(dentro) - n + 1
                break
            giorno = _giorno(s["data"])
            if cik not in annuali_per_cik:
                annuali_per_cik[cik] = self.edgar.annuali(cik)
            annuali = annuali_per_cik[cik]
            if annuali is None:
                esito = "non verificabile: EDGAR non leggibile"
            elif not annuali:
                esito = "non verificabile: la societa' non ha depositato 10-K (emittente estero o quotazione breve)"
            elif not (scelto := B.annuale_per(annuali, giorno)):
                esito = "non verificabile: nessun 10-K copre l'esercizio del salto"
            elif not (corpo := self.edgar.documento(cik, scelto[3], scelto[4])):
                esito = "non verificabile: 10-K non scaricabile"
            elif not (iv := B.intervallo((testo := B.testo_pulito(corpo)), giorno.year)):
                #  L'anno sta nel dettaglio della segnalazione; nel riepilogo il motivo si conta una volta sola,
                #  altrimenti diventano trenta righe da un pugno di salti ciascuna.
                esito = ("non verificabile: il 10-K non dichiara i prezzi dell'anno del salto"
                         if B.intervallo(testo) else "non verificabile: Item 5 senza tabella dei prezzi")
                note[(s["code"], giorno)] = "il 10-K dell'esercizio {} non dichiara i prezzi del {}".format(
                    scelto[2], giorno.year)
            else:
                verdetto, fattore = B.esamina(s["chiusura_prima"], s["chiusura"], iv[0], iv[1])
                esito = ("non verificabile: nessuna delle due chiusure sta nell'intervallo dichiarato"
                         if verdetto == "incerto" else verdetto)
                note[(s["code"], giorno)] = "10-K dell'esercizio {} ({}): per il {} dichiara {:g}-{:g}, chiusure {:g} e {:g}{}".format(
                    scelto[2], scelto[3], giorno.year, iv[1], iv[0], s["chiusura_prima"], s["chiusura"],
                    "; la serie precedente sta a {:.3g} volte questa scala".format(fattore) if fattore else "")
                if verdetto in campioni:
                    campioni[verdetto].append({
                        "code": s["code"], "salto": str(giorno), "chiusura_prima": round(s["chiusura_prima"], 4),
                        "chiusura": round(s["chiusura"], 4), "rapporto": round(s["rapporto"], 4),
                        "10k_esercizio": scelto[2], "10k_deposito": scelto[0], "10k_accession": scelto[3],
                        "massimo_dichiarato": iv[0], "minimo_dichiarato": iv[1], "valori_letti": iv[2],
                        "anno_dichiarato": giorno.year,
                        "nome": nome_societa.get(s["code"], ""),
                        "fattore": round(fattore, 2) if fattore else None})
            esiti[(s["code"], giorno)] = (esito, note.get((s["code"], giorno), esito))
            conti[esito] += 1
        #  Campione, non i primi dieci in ordine alfabetico: quelli sarebbero tutti titoli che cominciano per A.
        for elenco in campioni.values():
            self.rng.shuffle(elenco)
        return {"ambito": "NASDAQ, NYSE, NYSE ARCA; fascia sopra 1 dollaro; salto prima del {}; CIK noto".format(ANNO_SENZA_ITEM5),
                "salti_nell_ambito": len(dentro), "salti_fuori_ambito": dict(fuori),
                "esiti": dict(conti), "campione_veri": campioni["vero"][:N_CAMPIONE_BILANCI],
                "campione_fuori_scala": campioni["fuori scala"][:N_CAMPIONE_BILANCI],
                "cache_edgar_gb": round(self._cache_edgar_gb(), 2)}, esiti

    def _cache_edgar_gb(self) -> float:
        """Quanto occupa la cache EDGAR, senza rileggere la cartella a ogni salto.

        Misurarla col glob costa 0,74 s su 13.165 file: chiamata due volte per ciascuno dei 1.855 salti sarebbero
        45 minuti di sola scansione. Si misura una volta e poi si somma quello che il client ha scritto."""
        if self._cache_iniziale is None:
            self._cache_iniziale = sum(f.stat().st_size for f in self.edgar.cache.glob("*.bin.gz"))
        return (self._cache_iniziale + self.edgar.byte_scritti) / 1024 ** 3

    # ---- controlli con fonti esterne
    def delistati_usa(self) -> dict:
        cand = self.con.execute("""SELECT code, name, cik, last_date FROM anagrafica WHERE exchange = 'US' AND downloaded
                                   AND status = 'delistato' AND type = 'Common Stock' ORDER BY code""").fetchall()
        popolazione, con_cik = len(cand), sum(1 for c in cand if c[2])
        self.rng.shuffle(cand)
        esiti, senza_cik = [], 0
        for code, nome, cik, ultima in cand:
            if len(esiti) >= N_DELISTATI:
                break
            if not cik:
                senza_cik += 1
                continue
            d, dep = self.edgar.depositi(cik)
            if dep is None:
                esiti.append({"code": code, "cik": cik, "esito": "non verificabile: EDGAR non leggibile"})
                continue
            nomi = [d.get("name") or ""] + [x.get("name") or "" for x in d.get("formerNames") or []]
            somiglianza = max(E.nomi_simili(nome, n) for n in nomi)
            fine = E.fine_quotazione(dep) or E.ultimo_periodico(dep)
            scarto = abs((_giorno(ultima) - _giorno(fine)).days) if fine and ultima else None
            nome_uguale_al_ticker = (nome or "").strip().upper() == code.split("_")[0].upper()
            esiti.append({"code": code, "nome_eodhd": nome, "nome_edgar": d.get("name"), "somiglianza_nome": round(somiglianza, 2),
                          "nome_eodhd_uguale_al_ticker": nome_uguale_al_ticker, "ultima_barra": str(ultima),
                          "fine_edgar": fine, "fonte_fine": "Form 25/15" if E.fine_quotazione(dep) else "ultimo bilancio periodico",
                          "giorni_di_scarto": scarto,
                          "esito": "coerente" if (somiglianza >= SOGLIA_NOME or nome_uguale_al_ticker) and scarto is not None
                          and scarto <= GIORNI_COERENZA_FINE else "da guardare"})
        return {"popolazione_delistati": popolazione, "con_cik": con_cik,
                "quota_con_cik": round(con_cik / popolazione, 3) if popolazione else None,
                "campione": len(esiti), "saltati_senza_cik_prima_di_arrivare_a_30": senza_cik,
                "non_verificabili": sum(1 for e in esiti if e["esito"].startswith("non verificabile")),
                "coerenti": sum(1 for e in esiti if e["esito"] == "coerente"), "titoli": esiti}

    def salti_edgar(self, salti_usa: list[dict]) -> dict:
        sopra = [s for s in salti_usa if s["fascia"] == "sopra 1"]
        self.rng.shuffle(sopra)
        cik = dict(self.con.execute("SELECT code, cik FROM anagrafica WHERE exchange = 'US'").fetchall())
        esiti = []
        for s in sopra[:N_SALTI_EDGAR]:
            c = cik.get(s["code"])
            e = {"code": s["code"], "data": str(s["data"]), "rapporto": round(s["rapporto"], 4), "rapporto_tipico": s["rapporto_tipico"],
                 "volume_coerente": s["volume_coerente"], "cik": c}
            e.update(self.edgar.prove_split(c, _giorno(s["data"]), s["rapporto_tipico"]) if c else {"esito": "non verificabile: senza CIK"})
            esiti.append(e)
        veri = sum(1 for e in esiti if e["esito"] == "split trovato")
        verificabili = sum(1 for e in esiti if not e["esito"].startswith("non verificabile"))
        return {"salti_sopra_1": len(sopra), "campione": len(esiti), "split_veri": veri, "verificabili": verificabili,
                "quota_split_veri": round(veri / len(esiti), 3) if esiti else None,
                "quota_sui_verificabili": round(veri / verificabili, 3) if verificabili else None, "salti": esiti}

    def prima_della_quotazione(self) -> tuple[dict, list[dict]]:
        cand = self.con.execute("""SELECT code, cik, first_date FROM anagrafica WHERE exchange = 'US' AND downloaded
                                   AND status = 'attivo' AND type = 'Common Stock' AND nullif(trim(cik), '') IS NOT NULL
                                   ORDER BY code""").fetchall()
        seg, esempi, senza_data, non_leggibili = [], [], 0, 0
        for i, (code, cik, prima) in enumerate(cand):
            if i and i % 500 == 0:
                self.log("barre prima della quotazione: {} su {}".format(i, len(cand)))
            d, dep = self.edgar.depositi(cik)
            if dep is None:
                non_leggibili += 1
                continue
            if not dep:
                senza_data += 1
                continue
            primo_deposito, quotazione = dep[0][0], E.data_ipo(dep)
            if not quotazione or primo_deposito < "1997-01-01":
                senza_data += 1
                continue
            q = _giorno(quotazione)
            if _giorno(prima) < q - dt.timedelta(days=30):
                seg.append({"code": code, "controllo": "prima_della_quotazione", "from_date": _giorno(prima),
                            "to_date": q - dt.timedelta(days=1), "esclude": True,
                            "detail": "prima barra {}, quotazione su EDGAR {} (primo deposito {})".format(prima, quotazione, primo_deposito)})
                if len(esempi) < 20:
                    esempi.append({"code": code, "cik": cik, "prima_barra": str(prima), "quotazione": quotazione})
        return {"titoli_con_cik": len(cand), "senza_data_ricavabile": senza_data, "edgar_non_leggibile": non_leggibili,
                "segnalati": len(seg), "esempi": esempi}, seg

    def yahoo(self) -> dict:
        def campione(borse, n):
            #  titoli con prezzi recenti rispetto all'ultima barra della loro borsa (non degli USA)
            righe = self.con.execute("""SELECT a.exchange, a.code FROM anagrafica a
                                        JOIN (SELECT exchange, max(last_date) AS ultima FROM anagrafica GROUP BY exchange) m USING (exchange)
                                        WHERE a.downloaded AND a.status = 'attivo' AND a.type = 'Common Stock' AND a.exchange IN ({})
                                          AND a.last_date >= m.ultima - INTERVAL 10 DAY ORDER BY a.exchange, a.code""".format(
                ",".join("?" for _ in borse)), list(borse)).fetchall()
            self.rng.shuffle(righe)
            return righe[:n]
        scelti = campione(("US",), N_YAHOO_USA) + campione(BORSE_EUROPA, N_YAHOO_EUROPA)
        simboli = {E.simbolo_yahoo(c, b): (b, c) for b, c in scelti if E.simbolo_yahoo(c, b)}
        yahoo = self._yahoo(sorted(simboli), "1990-01-01")
        per_titolo = []
        for sy, (b, c) in sorted(simboli.items()):
            #  confronto principale: chiusura EODHD divisa per gli split EODHD successivi contro la Close di Yahoo (anche lei
            #  rettificata solo per gli split). Le rettificate per i dividendi si confrontano a parte: i due fornitori
            #  rettificano i dividendi in modo diverso e lo scarto si accumula andando indietro (ADR 006 punto 64)
            righe = self.con.execute("SELECT strftime(date, '%Y-%m-%d'), close, adjusted_close FROM prezzi WHERE exchange = ? AND code = ? "
                                     "ORDER BY date", [b, c]).fetchall()
            fattori = self.con.execute("SELECT strftime(date, '%Y-%m-%d'), factor FROM split WHERE exchange = ? AND code = ? AND factor > 0",
                                       [b, c]).fetchall()
            y = yahoo.get(sy, {})
            comuni, oltre, oltre_rett, scarti_rett = 0, 0, 0, []
            for d, chiusura, rettificata in righe:
                yy = y.get(d)
                if not yy or not chiusura or not yy.get("close"):
                    continue
                fattore = math.prod(f for ds, f in fattori if ds > d)
                comuni += 1
                oltre += abs((chiusura / fattore) / yy["close"] - 1) > SCARTO_YAHOO
                if rettificata and yy.get("adj"):
                    scarto = abs(rettificata / yy["adj"] - 1)
                    oltre_rett += scarto > SCARTO_YAHOO
                    scarti_rett.append(scarto)
            per_titolo.append({"simbolo": "{}.{}".format(c, b), "yahoo": sy, "date_comuni": comuni, "oltre_1pct": oltre,
                               "quota": round(oltre / comuni, 4) if comuni else None,
                               "rettificate_oltre_1pct": oltre_rett,
                               "scarto_mediano_rettificate": round(statistics.median(scarti_rett), 4) if scarti_rett else None,
                               "gruppo": "USA" if b == "US" else "Europa"})
        def riassunto(gruppo):
            tt = [t for t in per_titolo if t["gruppo"] == gruppo]
            con_dati = [t for t in tt if t["date_comuni"]]
            date = sum(t["date_comuni"] for t in con_dati)
            scarti = [t["scarto_mediano_rettificate"] for t in con_dati if t["scarto_mediano_rettificate"] is not None]
            return {"titoli": len(tt), "con_dati_yahoo": len(con_dati), "date_confrontate": date,
                    "quota_chiusure_oltre_1pct": round(sum(t["oltre_1pct"] for t in con_dati) / date, 4) if date else None,
                    "titoli_con_oltre_il_5pct_di_date_diverse": sum(1 for t in con_dati if t["quota"] > 0.05),
                    "quota_rettificate_oltre_1pct": round(sum(t["rettificate_oltre_1pct"] for t in con_dati) / date, 4) if date else None,
                    "scarto_mediano_rettificate_per_titolo": round(statistics.median(scarti), 4) if scarti else None}
        return {"USA": riassunto("USA"), "Europa": riassunto("Europa"), "titoli": per_titolo}

    # ---- esecuzione
    def scrivi_segnalazioni(self) -> None:
        base, man = self.archivio / "eodhd" / "parquet", self.archivio / "eodhd" / "manifest"
        for borsa, righe in self.segnalazioni.items():
            part = N.Partizione(base, man, "segnalazioni", borsa)
            if righe:
                righe.sort(key=lambda r: (r["code"], r["from_date"], r["controllo"]))
                part.aggiungi(pa.Table.from_pylist(righe, schema=catalog.SCHEMA_SEGNALAZIONI))
            part.chiudi([{"file": "quality/esegui.py", "sha256": "controlli del {}".format(dt.date.today())}])

    def esegui(self, borse: list[str] | None = None, esterni: bool = True) -> dict:
        borse = borse or self.borse()
        out = {"eseguito": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seme": SEME, "borse": {}}
        salti_usa = []
        for b in borse:
            self.log("controlli {}".format(b))
            r, seg, salti = self.borsa(b)
            out["borse"][b] = r
            self.segnalazioni[b] = seg
            if b == "US":
                salti_usa = salti
        if not esterni and "US" in borse:
            #  senza fonti esterne le segnalazioni EDGAR già scritte restano: non si cancellano
            vecchie = self.con.execute("""SELECT code, controllo, from_date, to_date, detail, esclude FROM segnalazioni
                                          WHERE exchange = 'US' AND controllo = 'prima_della_quotazione'""").fetchall()
            self.segnalazioni["US"] += [dict(zip(("code", "controllo", "from_date", "to_date", "detail", "esclude"), r))
                                        for r in vecchie]
        if esterni and "US" in borse:
            self.log("EDGAR: delistati")
            out["delistati_usa_edgar"] = self.delistati_usa()
            self.log("EDGAR: salti sopra 1 dollaro")
            out["salti_sopra_1_edgar"] = self.salti_edgar(salti_usa)
            self.log("EDGAR: salti verificati sui bilanci (Item 5)")
            out["salti_sui_bilanci"], esiti = self.verifica_bilanci(salti_usa)
            self.segnalazioni["US"] = applica_esiti_bilanci(self.segnalazioni["US"], esiti)
            self.log("EDGAR: barre prima della quotazione")
            out["prima_della_quotazione"], seg = self.prima_della_quotazione()
            self.segnalazioni["US"] += seg
            self.log("Yahoo")
            out["yahoo"] = self.yahoo()
            out["chiamate_edgar"] = self.edgar.chiamate
        self.scrivi_segnalazioni()
        catalog.costruisci_catalogo(self.archivio, log=self.log)        # il catalogo su disco vede le segnalazioni nuove
        cartella = self.archivio / "eodhd" / "qualita"
        cartella.mkdir(parents=True, exist_ok=True)
        if not esterni:
            out.update(sezioni_esterne_precedenti(cartella / "qualita.json"))
        out.update(borse_precedenti(cartella / "qualita.json", out))
        (cartella / "qualita.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
        return out



def applica_esiti_bilanci(segnalazioni: list[dict], esiti: dict) -> list[dict]:
    """Riscrive le segnalazioni USA con quello che dicono i bilanci.

    Un salto che il 10-K conferma come movimento vero smette di escludere e diventa una nota sul solo giorno del
    salto. Tutti gli altri restano come sono e si portano nel dettaglio il motivo: fuori scala con i numeri del
    bilancio, oppure perche' non e' stato possibile verificarlo."""
    fuori = []
    for riga in segnalazioni:
        if riga["controllo"] != "salto_sospetto":
            fuori.append(riga)
            continue
        giorno = riga["to_date"] + dt.timedelta(days=1)
        trovato = esiti.get((riga["code"], giorno))
        if trovato is None:
            fuori.append(dict(riga, detail=riga["detail"] + "; non verificato sui bilanci per scelta (fuori ambito)"))
            continue
        esito, nota = trovato
        if esito == "vero":
            fuori.append({"code": riga["code"], "controllo": "salto_confermato", "from_date": giorno,
                          "to_date": giorno, "esclude": False,
                          "detail": "salto del {} confermato come movimento vero: {}".format(giorno, nota)})
        else:
            fuori.append(dict(riga, detail="{}; {}".format(riga["detail"], nota)))
    return fuori


SEZIONI_ESTERNE = ("delistati_usa_edgar", "salti_sopra_1_edgar", "salti_sui_bilanci", "prima_della_quotazione",
                   "yahoo", "chiamate_edgar")


def borse_precedenti(percorso: Path, nuovo: dict) -> dict:
    """Sezioni per borsa: quelle di questo giro più quelle delle borse non ricontrollate, ciascuna con la sua data."""
    try:
        vecchio = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        vecchio = {}
    vecchio = vecchio if isinstance(vecchio, dict) else {}
    date = dict(vecchio.get("borse_controllate_il") or {})
    borse = {b: r for b, r in (vecchio.get("borse") or {}).items() if b not in nuovo["borse"]}
    date = {b: d for b, d in date.items() if b in borse}
    borse.update(nuovo["borse"])
    date.update({b: nuovo["eseguito"] for b in nuovo["borse"]})
    return {"borse": borse, "borse_controllate_il": date}


def sezioni_esterne_precedenti(percorso: Path) -> dict:
    """Sezioni EDGAR e Yahoo dell'ultimo rapporto completo, con la data: un giro senza fonti esterne non le cancella."""
    try:
        vecchio = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(vecchio, dict):
        return {}
    out = {k: vecchio[k] for k in SEZIONI_ESTERNE if k in vecchio}
    if out:
        out["fonti_esterne_del"] = vecchio.get("fonti_esterne_del") or vecchio.get("eseguito")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Controlli di qualità della fase 4")
    ap.add_argument("--borse", default="")
    ap.add_argument("--senza-esterni", action="store_true")
    a = ap.parse_args(argv)
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    borse = [b.strip() for b in a.borse.split(",") if b.strip()] or None
    out = Controlli(C.archivio()).esegui(borse, esterni=not a.senza_esterni)
    print(json.dumps({b: {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if not isinstance(vv, list)})
                          for k, v in r.items()} for b, r in out["borse"].items()}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
