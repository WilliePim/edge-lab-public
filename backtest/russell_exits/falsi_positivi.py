"""Russell 2000, uscite verso il basso — falsi positivi della definizione dell'addendum 1 contro una lista ufficiale.

Per un anno con la lista ufficiale FTSE Russell delle cancellazioni dal Russell 3000: uscite segnate con la regola
«assente o ≤ 50% delle azioni di marzo (rettificate), e non in IWB», abbinate alla lista per ticker verificato, nome
normalizzato, prefisso del nome o somiglianza ≥ 0,85. **Falso positivo** = segnata qui, non nella lista.

Ogni falso positivo è classificato con una regola, nell'ordine:
1. **stesso emittente con un CUSIP nuovo**: a giugno c'è in IWM o in IWB una riga assente a marzo con le stesse prime sei
   cifre del CUSIP (codice dell'emittente), oppure lo stesso nome normalizzato, oppure lo stesso CIK (abbinamento per
   nome esatto e unico). Succede con raggruppamenti, cambi di sede e fusioni inverse;
2. **acquisita, in fusione o delistata nel trimestre**: depositi in cache fra il 31 marzo e la ricostituzione (Form 25,
   15-12, DEFM14A, SC TO-T, PREM14A, 8-K voce 1.03), oppure serie Yahoo finita prima della ricostituzione. La
   fase 1 le esclude comunque;
3. **senza spiegazione**.

Quota residua: azioni rettificate per i frazionamenti della serie Yahoo; senza serie, **quota del capitale detenuta da
IWM** (azioni di IWM di tutte le righe con lo stesso CIK / azioni in circolazione XBRL dell'ultimo deposito con `filed`
non oltre la data dell'istantanea). Depositi e companyfacts mancanti scaricati con il tetto di `analisi.py`.

Poi la stessa definizione con l'abbinamento per emittente (regola 1 applicata a tutte le righe di marzo): uscite segnate,
ritrovate e falsi positivi. Soglia dell'utente: oltre il 10% dei casi dell'anno ci si ferma.

    python backtest/russell_exits/falsi_positivi.py 2025
"""
from __future__ import annotations

import collections
import csv
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", HERE):
    sys.path.insert(0, str(p))

import identita as I  # noqa: E402
import lista_ftse_pdf as L  # noqa: E402
import filtri_xbrl as F  # noqa: E402
import scarica_ohlcv as O  # noqa: E402
import sec  # noqa: E402
import survival as SV  # noqa: E402
import uscite as U  # noqa: E402
import verifica_identita as V  # noqa: E402

STATE = ROOT / "state" / "backfill" / "russell"
HOLD = STATE / "holdings"
#  Le liste ufficiali finali, una per anno. Il 2025 e' quello scaricato a mano a settembre; gli altri li porta
#  `scarica_liste_ftse.py`, che verifica su ogni file che sia la finale della ricostituzione e non una preliminare.
#  2018, 2019 e 2020 non hanno una lista finale pubblica: quegli anni restano non controllati.
LISTE = {2025: STATE / "ru3000-deletions-20250627.pdf"}
LISTE.update({anno: STATE / "liste" / "ru3000-deletions-{}.pdf".format(anno)
              for anno in (2016, 2017, 2021, 2022, 2023, 2024)})
ANNI_SENZA_LISTA = (2018, 2019, 2020)
#  Anni in cui l'istantanea del 30 giugno **precede** l'effetto della ricostituzione: zero sedute in mezzo, quindi
#  le uscite non ci sono ancora (nel 2024 si contano 17 entrate invece delle 190-285 degli altri anni; il 2019 non
#  ha proprio il file). Misurare i falsi positivi su quell'istantanea non misura la definizione, misura il buco.
#  Per quegli anni il file «dopo» e' il 30 settembre (decisione dell'utente del 17-09-2026).
#  Tabella: risultati/controllo_date_giugno.md.
ISTANTANEA_DOPO = {
    2019: ("2019-09-30", "il 30 giugno non esiste: cade di domenica, zero sedute dopo la ricostituzione del 28"),
    2024: ("2024-09-30", "il 30 giugno cade di domenica, zero sedute dopo la ricostituzione del 28: "
                         "solo 17 entrate contro 190-285"),
}

#  **Fin dove arrivano gli eventi societari che la fase 1 esclude.** La pre-registrazione (§3, esclusione 2) dice
#  «fra il 31 marzo e la ricostituzione», e la finestra parte dal 31 marzo proprio perche' l'istantanea e'
#  trimestrale. Con l'istantanea «dopo» spostata a settembre lo stesso ragionamento porterebbe a spostare anche la
#  fine: un titolo acquisito in agosto e' assente a settembre per una ragione societaria, non perche' e' uscito
#  dall'indice. Le due letture danno numeri diversi e la scelta e' dell'utente, quindi si calcolano tutte e due e
#  si riportano entrambe.
FINE_EVENTI = ("ricostituzione", "istantanea dopo")
SOGLIA_FP = 0.10
MODULI_TRIMESTRE = SV.TERM | SV.ACQ | frozenset({"PREM14A", "PREM14C"})
TETTO_EDGAR = 3000                # lo stesso di analisi.py


def carica(k):
    p = HOLD / "{}.csv".format(k)
    return list(csv.DictReader(p.open(encoding="utf-8", newline=""))) if p.exists() else []


def chiave(r):
    return r["cusip"] if r.get("cusip") else "N:" + I.norm(r.get("titolo") or r["nome"])


def nomi_riga(r):
    return {I.norm(n) for n in (r.get("nome"), r.get("titolo")) if n} - {""}


def date_anno(anno):
    with (HERE / "date_ricostituzione.csv").open(encoding="utf-8", newline="") as fh:
        return next(r for r in csv.DictReader(fh) if r["anno"] == str(anno))


def candidati_per_chiave(istantanea):
    """{chiave: [CIK candidati]} dall'abbinamento per nome."""
    out = {}
    with (STATE / "identita_candidati.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["istantanea"] == istantanea and r["candidati"]:
                out[chiave(r)] = [c for c in r["candidati"].split(";") if c.isdigit()]
    return out


def cik_per_chiave(istantanea):
    """{chiave: CIK} per i soli abbinamenti con un candidato unico."""
    return {k: v[0] for k, v in candidati_per_chiave(istantanea).items() if len(v) == 1}


class Anno:
    def __init__(self, anno, con_capitale=True):
        self.anno, self.con_capitale = anno, con_capitale
        self.da = "{}-03-31".format(anno)
        self.a = ISTANTANEA_DOPO[anno][0] if anno in ISTANTANEA_DOPO else "{}-06-30".format(anno)
        self.man = json.loads(O.MANIFEST.read_text(encoding="utf-8"))
        self.ident = {}
        with (STATE / "identita.csv").open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["istantanea"] == "IWM_" + self.da:
                    self.ident[chiave(r)] = r
        self.cik_m, self.cik_g = cik_per_chiave("IWM_" + self.da), cik_per_chiave("IWM_" + self.a)
        self.cand_m = candidati_per_chiave("IWM_" + self.da)
        self.righe_m = {}
        self.az_m = collections.defaultdict(float)
        for r in carica("IWM_" + self.da):
            self.righe_m.setdefault(chiave(r), r)
            self.az_m[chiave(r)] += float(r["azioni"] or 0)
        self.az_g = {"IWM": collections.defaultdict(float), "IWB": collections.defaultdict(float)}
        self.righe_g = {"IWM": {}, "IWB": {}}
        for f in ("IWM", "IWB"):
            for r in carica("{}_{}".format(f, self.a)):
                self.righe_g[f].setdefault(chiave(r), r)
                self.az_g[f][chiave(r)] += float(r["azioni"] or 0)
        self.in_b_nomi = set().union(*(nomi_riga(r) for r in self.righe_g["IWB"].values()))
        self.nuove = [(f, k, r) for f in ("IWM", "IWB") for k, r in self.righe_g[f].items() if k not in self.az_m]
        self.b = sec.Budget(tetto=TETTO_EDGAR)
        self._cf = {}

    def cik(self, k):
        return self.ident.get(k, {}).get("cik") or self.cik_m.get(k)

    def depositi(self, cik):
        url = SV.SUB + "CIK{:010d}.json".format(int(cik))
        if not SV.in_cache(url):
            self.b.get(url)
        return SV.submissions(cik)

    def azioni_xbrl(self, cik, giorno):
        """Azioni in circolazione dell'ultimo deposito con filed <= giorno, o None."""
        if cik not in self._cf:
            txt = self.b.get("https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json".format(int(cik)))
            try:
                cf = json.loads(txt) if txt else None
            except ValueError:
                cf = None
            self._cf[cik] = F.azioni_per_deposito(cf, "9999-12-31")[0] if cf else {}
        per = {k: v for k, v in self._cf[cik].items() if k[0] <= giorno}
        return per[max(per)] if per else None

    def quota_capitale(self, k, kg, fondo_g="IWM"):
        """(quota di IWM a marzo, quota di IWM a giugno) sul capitale XBRL, sommando le righe con lo stesso CIK."""
        cm = self.cik(k)
        cg = self.cik_g.get(kg) or cm
        if not cm or not cg:
            return None
        tot_m = self.azioni_xbrl(cm, self.da)
        tot_g = self.azioni_xbrl(cg, self.a)
        if not tot_m or not tot_g:
            return None
        az_m = sum(v for kk, v in self.az_m.items() if self.cik(kk) == cm)
        az_g = sum(v for kk, v in self.az_g[fondo_g].items() if (self.cik_g.get(kk) or (cm if kk == kg else None)) == cg)
        return az_m / tot_m, az_g / tot_g

    def split(self, k):
        t = self.ident.get(k, {}).get("ticker")
        if t and (self.man.get(t) or {}).get("esito") == "OK":
            return V.serie_allineata(O.percorso(t), [])[3]
        return None

    def stesso_emittente(self, k):
        """(fondo, chiave nuova, motivo) della riga di giugno assente a marzo che corrisponde a k, o None."""
        r = self.righe_m[k]
        cu, nomi, cik = r.get("cusip") or "", nomi_riga(r), self.cik_m.get(k)
        for f, kn, rn in self.nuove:
            cun = rn.get("cusip") or ""
            if cu and cun and cu[:6] == cun[:6]:
                return f, kn, "codice emittente"
        for f, kn, rn in self.nuove:
            if nomi & nomi_riga(rn):
                return f, kn, "nome"
        for f, kn, rn in self.nuove:
            if f == "IWM" and cik and self.cik_g.get(kn) == cik:
                return f, kn, "CIK"
        return None

    def classe(self, k, per_emittente):
        """(stato, quota, metodo, abbinamento giugno)."""
        corr = self.stesso_emittente(k) if per_emittente and k not in self.az_g["IWM"] and k not in self.az_g["IWB"] else None
        if corr and corr[0] == "IWB":
            return "alto", None, None, corr
        kg = corr[1] if corr else k
        dopo = self.az_g["IWM"].get(kg, 0.0)
        in_b = k in self.az_g["IWB"] or bool(nomi_riga(self.righe_m[k]) & self.in_b_nomi)
        split = self.split(k)
        qc = self.quota_capitale(k, kg) if split is None and dopo and self.con_capitale else None
        quota, metodo = U.quota_residua(self.az_m[k], dopo, split=split, da=self.da, a=self.a, quota_capitale=qc)
        if quota is None and dopo:
            quota, metodo = dopo / self.az_m[k], "azioni non rettificate (né serie né azioni XBRL)"
        return U.classifica(bool(dopo), in_b, quota), quota, metodo, corr

    def nel_trimestre(self, k, fine):
        idr = self.ident.get(k, {})
        cik = self.cik(k)
        forme = set()
        #  CIK ambiguo (più candidati per lo stesso nome): vale il solo candidato con depositi nel trimestre, se è uno
        per_cik = {}
        for c in ([cik] if cik else self.cand_m.get(k, [])):
            _d, dep = self.depositi(c)
            per_cik[c] = set()
            for z in dep:
                if self.da < z[0] <= fine:
                    if z[1] in MODULI_TRIMESTRE:
                        per_cik[c].add(z[1])
                    #  Solo la voce 1.03 (fallimento), come nella pre-registrazione (§3, esclusione 2). La 2.01
                    #  («completamento di un'acquisizione o cessione di beni») la deposita anche chi compra o
                    #  chi sopravvive a una fusione inversa -- Bowlero, Cross Country Healthcare, Dril-Quip
                    #  diventata Innovex International -- quindi non prova che il titolo sia sparito. Quando
                    #  la società acquisita sparisce davvero, accanto alla 2.01 c'è sempre un Form 25 o 15.
                    elif z[1].startswith("8-K") and "1.03" in z[2]:
                        per_cik[c].add("8-K 1.03")
        con = [c for c, f in per_cik.items() if f]
        if len(con) == 1:
            if not cik:
                forme.add("CIK {} su {} candidati".format(con[0], len(per_cik)))
            cik = con[0]
            forme |= per_cik[con[0]]
        t = idr.get("ticker")
        ultima = (self.man.get(t) or {}).get("a", "") if t else ""
        if ultima and ultima < fine:
            forme.add("serie finita il " + ultima)
        return cik, sorted(forme)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("anno", nargs="?", type=int, default=2025)
    ap.add_argument("--fine-eventi", choices=FINE_EVENTI, default="ricostituzione",
                    help="fin dove valgono gli eventi societari che la fase 1 esclude: fino alla ricostituzione "
                         "(lettera della pre-registrazione) o fino all'istantanea «dopo» (stessa logica, quando "
                         "l'istantanea e' spostata a settembre)")
    a = ap.parse_args(argv)
    anno = a.anno
    #  I due impedimenti sono indipendenti e possono valere tutti e due (il 2019): si dicono tutti e due,
    #  altrimenti chi legge crede che togliendo il primo l'anno diventi misurabile.
    impedimenti = []
    if anno in ISTANTANEA_DOPO:
        dopo, perche = ISTANTANEA_DOPO[anno]
        if not (HOLD / "IWM_{}.csv".format(dopo)).exists():
            impedimenti.append("{}; il file «dopo» sarebbe {}, che non e' stato scaricato".format(perche, dopo))
    if anno in ANNI_SENZA_LISTA:
        impedimenti.append("nessuna lista ufficiale finale delle cancellazioni con cui confrontarsi")
    if impedimenti:
        print("{}: non misurabile.".format(anno))
        for i in impedimenti:
            print("    - {}".format(i))
        return 2
    if not LISTE[anno].exists():
        print("{}: manca {} -- lanciare prima scarica_liste_ftse.py".format(anno, LISTE[anno].name))
        return 2
    ricostituzione = date_anno(anno)["ricostituzione"]
    uff = L.righe(LISTE[anno])
    sim_uff = {u["simbolo"].replace(".", "-") for u in uff}
    nomi_uff = {I.norm(u["societa"]) for u in uff}
    A = Anno(anno)
    fine_eventi = ricostituzione if a.fine_eventi == "ricostituzione" else A.a

    def trova(k):
        t = A.ident.get(k, {}).get("ticker")
        if t and t in sim_uff:
            return "ticker"
        nomi = nomi_riga(A.righe_m[k])
        if nomi & nomi_uff:
            return "nome"
        if any(nn[:12] == n[:12] for n in nomi if len(n) >= 8 for nn in nomi_uff):
            return "prefisso"
        migliore = max((difflib.SequenceMatcher(None, n, nn).ratio() for n in nomi for nn in nomi_uff), default=0)
        return "simile {:.2f}".format(migliore) if migliore >= 0.85 else None

    esiti = {}
    for per_emittente in (False, True):
        segnate = []
        for k in A.az_m:
            stato, quota, metodo, corr = A.classe(k, per_emittente)
            if stato == "basso":
                x = {"chiave": k, "nome": A.righe_m[k].get("titolo") or A.righe_m[k]["nome"],
                     "ticker": A.ident.get(k, {}).get("ticker", ""), "identita": A.ident.get(k, {}).get("esito", ""),
                     "quota": quota, "metodo": metodo, "abbinamento": trova(k)}
                segnate.append(x)
        fp = [x for x in segnate if not x["abbinamento"]]
        for x in fp:
            corr = A.stesso_emittente(x["chiave"]) if x["chiave"] not in A.az_g["IWM"] else None
            x["cik"], forme = A.nel_trimestre(x["chiave"], fine_eventi)
            if corr:
                rn = A.righe_g[corr[0]][corr[1]]
                x["classe"] = "stesso emittente con un CUSIP nuovo"
                x["nota"] = "{} a giugno: {} ({}, per {})".format(corr[0], rn.get("titolo") or rn["nome"], rn.get("cusip") or "—", corr[2])
            elif forme:
                x["classe"] = "acquisita, in fusione o delistata nel trimestre"
                x["nota"] = ", ".join(forme)
            else:
                x["classe"] = "senza spiegazione"
                x["nota"] = "depositi letti: " + ("sì" if x["cik"] and SV.submissions(x["cik"])[0] else "no")
        esiti[per_emittente] = (segnate, fp)

    righe = ["# Falsi positivi della definizione dell'addendum 1 — {}".format(anno), "",
             "Generato da `python backtest/russell_exits/falsi_positivi.py {}`. Lista ufficiale FTSE Russell: {} "
             "cancellazioni dal Russell 3000 (ricostituzione del {}). ".format(anno, len(uff), ricostituzione)
             + "Istantanea «dopo»: {}{}. Eventi societari contati fino al {} ({}). ".format(
                 A.a, " (spostata: {})".format(ISTANTANEA_DOPO[anno][1]) if anno in ISTANTANEA_DOPO else "",
                 fine_eventi, a.fine_eventi)
             + "Nessun rendimento calcolato.", "",
             "Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.", "",
             "| | abbinamento per CUSIP esatto | abbinamento per emittente |", "|---|---:|---:|"]
    s0, f0 = esiti[False]
    s1, f1 = esiti[True]
    #  ritrovate: cancellazioni ufficiali presenti in IWM a marzo (ticker verificato o nome normalizzato) segnate come uscite
    tick_m = {r.get("ticker"): k for k, r in A.ident.items() if r.get("ticker")}
    nome_m = {n: k for k, r in A.righe_m.items() for n in nomi_riga(r)}
    presenti = {}
    for u in uff:
        k = tick_m.get(u["simbolo"].replace(".", "-")) or nome_m.get(I.norm(u["societa"]))
        if k:
            presenti[u["simbolo"]] = k
    rit0 = {x["chiave"] for x in s0}
    rit1 = {x["chiave"] for x in s1}
    mancate = [(s, A.righe_m[k].get("titolo") or A.righe_m[k]["nome"], A.classe(k, True)) for s, k in presenti.items() if k not in rit1]
    righe.append("| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | {} | {} |".format(len(presenti), len(presenti)))
    righe.append("| … segnate come uscite verso il basso (**ritrovate**) | {} ({:.1%}) | {} ({:.1%}) |".format(
        sum(k in rit0 for k in presenti.values()), sum(k in rit0 for k in presenti.values()) / len(presenti),
        sum(k in rit1 for k in presenti.values()), sum(k in rit1 for k in presenti.values()) / len(presenti)))
    righe.append("| uscite segnate | {} | {} |".format(len(s0), len(s1)))
    righe.append("| nella lista ufficiale | {} | {} |".format(len(s0) - len(f0), len(s1) - len(f1)))
    righe.append("| **falsi positivi** | **{} ({:.1%})** | **{} ({:.1%})** |".format(len(f0), len(f0) / len(s0), len(f1), len(f1) / len(s1)))
    for c in ("stesso emittente con un CUSIP nuovo", "acquisita, in fusione o delistata nel trimestre", "senza spiegazione"):
        n0, n1 = sum(x["classe"] == c for x in f0), sum(x["classe"] == c for x in f1)
        righe.append("| … {} | {} | {} |".format(c, n0, n1))
    tr0 = sum(x["classe"] != "acquisita, in fusione o delistata nel trimestre" for x in f0)
    tr1 = sum(x["classe"] != "acquisita, in fusione o delistata nel trimestre" for x in f1)
    righe.append("| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | {} ({:.1%}) | {} ({:.1%}) |".format(
        tr0, tr0 / len(s0), tr1, tr1 / len(s1)))
    righe += ["", "Metodo della quota residua (abbinamento per emittente): " + ", ".join(
        "{} {}".format(k, v) for k, v in collections.Counter(x["metodo"] for x in s1).most_common()) + ".", "",
        "**Soglia dell'utente (10% dei casi dell'anno): {}.**".format(
            "superata" if max(len(f0) / len(s0), len(f1) / len(s1)) > SOGLIA_FP else "rispettata"), ""]
    righe += ["## Cancellazioni ufficiali non ritrovate (abbinamento per emittente)", "",
              "| simbolo | società | stato | quota residua | metodo |", "|---|---|---|---:|---|"]
    righe += ["| {} | {} | {} | {} | {} |".format(s, n, c[0], "—" if c[1] is None else "{:.1%}".format(c[1]), c[2] or "—")
              for s, n, c in mancate]
    righe.append("")
    for titolo, fp in (("Falsi positivi con l'abbinamento per CUSIP esatto", f0), ("Falsi positivi con l'abbinamento per emittente", f1)):
        righe += ["## " + titolo, "", "| società | ticker | identità | quota residua | classe | nota |", "|---|---|---|---:|---|---|"]
        righe += ["| {} | {} | {} | {:.1%} | {} | {} |".format(x["nome"], x["ticker"] or "—", x["identita"] or "—", x["quota"],
                                                             x["classe"], x["nota"]) for x in sorted(fp, key=lambda z: z["classe"])]
        righe.append("")
    suffisso = "" if a.fine_eventi == "ricostituzione" else "_eventi_fino_all_istantanea"
    (HERE / "risultati" / "falsi_positivi_{}{}.md".format(anno, suffisso)).write_text("\n".join(righe), encoding="utf-8")
    with (HERE / "risultati" / "uscite_segnate_{}{}.csv".format(anno, suffisso)).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["abbinamento_giugno", "chiave", "nome", "ticker", "identita", "quota", "metodo",
                                           "abbinamento", "classe", "nota"], extrasaction="ignore")
        w.writeheader()
        for per_emittente, (segnate, _fp) in esiti.items():
            for x in segnate:
                w.writerow(dict(x, abbinamento_giugno="emittente" if per_emittente else "CUSIP esatto"))
    righe_fine = "Chiamate EDGAR del Russell: {} su {}.".format(A.b.usate, TETTO_EDGAR)
    sys.stdout.reconfigure(encoding="utf-8")
    print(righe_fine)
    print("\n".join(righe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
