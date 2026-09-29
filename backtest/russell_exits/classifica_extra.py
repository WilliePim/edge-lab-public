"""Russell 2000, uscite verso il basso — classifica a mano le uscite in più di un anno sopra soglia.

Le uscite segnate che non stanno nella lista ufficiale FTSE Russell e che `falsi_positivi.py` ha lasciato «senza
spiegazione» sono quasi sempre società di cui **non si è potuto leggere EDGAR**, perché l'identità non era risolta:
nelle istantanee dei fondi vecchie manca il CUSIP e l'abbinamento riesce solo per nome. Il 79% dei casi senza
spiegazione del 2016 e il 72% del 2017 hanno «depositi letti: no».

Qui l'identità si risolve **partendo dal nome, con la ricerca di EDGAR**, che conosce anche i nomi precedenti di
ogni società. Trovato il CIK, si guarda se nel trimestre fra il 31 marzo e la ricostituzione c'è un evento
societario che toglie il titolo dall'indice:

- **Form 25, 25-NSE, 15-12B, 15-12G, 15-15D** — fine della quotazione o della registrazione;
- **8-K con voce 1.03** (fallimento). Non la 2.01: la deposita anche chi compra o chi sopravvive a una fusione
  inversa, e non prova che il titolo sia sparito;
- **DEFM14A/C, PREM14A/C, SC TO-T/C, SC 13E3, SC 14D9** — documenti di fusione o offerta pubblica.

Sono gli stessi moduli della fase 1 della pre-registrazione (§3, esclusione 2). Una società con uno di questi
depositi nel trimestre **non è un falso positivo**: la fase 1 la toglie prima dei filtri, quindi non diventa mai un
caso. Una società senza nessun evento è un **falso positivo vero**: la definizione la segna come uscita e FTSE
Russell no, senza una ragione societaria.

Chi non si risolve nemmeno per nome resta **non risolta** e si conta a parte: non è né l'uno né l'altro, e dirlo è
più onesto che metterla da una delle due parti.

    python backtest/russell_exits/classifica_extra.py 2016
"""
from __future__ import annotations

import csv
import datetime as dt
import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", HERE):
    sys.path.insert(0, str(p))

import identita as I  # noqa: E402
import sec  # noqa: E402
import survival as SV  # noqa: E402

RISULTATI = HERE / "risultati"
TETTO_EDGAR = 3000                # il tetto del Russell nella pre-registrazione (§2), cumulativo
RICERCA = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={nome}"
           "&type=&dateb=&owner=include&count=40&output=atom")
MODULI_FINE = SV.TERM
MODULI_FUSIONE = SV.ACQ | frozenset({"PREM14A", "PREM14C"})
VOCI_8K = ("1.03",)            # come la pre-registrazione, §3 esclusione 2: la 2.01 non prova una sparizione
SOMIGLIANZA_NOME = 0.72

#  Parole che nei nomi dei fondi non aiutano la ricerca di EDGAR e vanno tolte dalla chiave di ricerca.
CODA = re.compile(r"\b(class [a-z]|cl [a-z]|inc|inc\.|corp|corp\.|corporation|co|co\.|company|ltd|ltd\.|llc|plc|"
                  r"holdings?|group|the|&|and|new|sa|nv|reit|trust)\b", re.I)


def chiave_ricerca(nome: str) -> str:
    """Le prime parole significative del nome, come le vuole la ricerca di EDGAR (che cerca per prefisso)."""
    pulito = CODA.sub(" ", nome.replace(",", " ").replace(".", " "))
    parole = [p for p in pulito.split() if len(p) > 1]
    return "+".join(parole[:3]) or nome.split()[0]


def nomi_del_cik(d: dict) -> list[str]:
    """Nome attuale e nomi precedenti registrati alla SEC."""
    return [d.get("name") or ""] + [x.get("name") or "" for x in (d.get("formerNames") or [])]


def somiglianza(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, I.norm(a), I.norm(b)).ratio()


class Ricerca:
    def __init__(self, budget):
        self.b = budget
        self.visti: dict[str, dict | None] = {}

    def candidati(self, nome: str) -> list[str]:
        """I CIK che EDGAR propone per quel nome, dal suo indice (che copre anche i nomi precedenti)."""
        testo = self.b.get(RICERCA.format(nome=chiave_ricerca(nome)))
        if not testo:
            return []
        return list(dict.fromkeys(re.findall(r"CIK=(\d{10})", testo)))[:8]

    def submissions(self, cik: str) -> dict | None:
        if cik not in self.visti:
            testo = self.b.get(SV.SUB + "CIK{:010d}.json".format(int(cik)))
            try:
                self.visti[cik] = json.loads(testo) if testo else None
            except ValueError:
                self.visti[cik] = None
        return self.visti[cik]

    def risolvi(self, nome: str) -> tuple[str | None, str, float]:
        """(CIK, nome trovato, somiglianza) del candidato che somiglia di più, o (None, '', 0)."""
        migliore = (None, "", 0.0)
        for cik in self.candidati(nome):
            d = self.submissions(cik)
            if not d:
                continue
            for n in nomi_del_cik(d):
                s = somiglianza(nome, n)
                if s > migliore[2]:
                    migliore = (cik, n, s)
        return migliore if migliore[2] >= SOMIGLIANZA_NOME else (None, migliore[1], migliore[2])


def eventi_nel_trimestre(d: dict, da: str, a: str) -> list[str]:
    """I depositi fra `da` e `a` che tolgono il titolo dall'indice, come «forma (data)»."""
    fuori = []
    blocchi = [d.get("filings", {}).get("recent", {})]
    for b in blocchi:
        n = len(b.get("form", []))
        forme = b.get("form") or []
        date = b.get("filingDate") or []
        voci = b.get("items") or [""] * n
        for i in range(min(len(forme), len(date))):
            if not (da <= date[i] <= a):
                continue
            f = forme[i]
            item = voci[i] if i < len(voci) else ""
            if f in MODULI_FINE or f in MODULI_FUSIONE:
                fuori.append("{} ({})".format(f, date[i]))
            elif f.startswith("8-K") and any(v in (item or "") for v in VOCI_8K):
                voce = next(v for v in VOCI_8K if v in (item or ""))
                fuori.append("8-K voce {} ({})".format(voce, date[i]))
    return sorted(set(fuori))


def data_ricostituzione(anno: int) -> str:
    with (HERE / "date_ricostituzione.csv").open(encoding="utf-8", newline="") as fh:
        return next(r for r in csv.DictReader(fh) if r["anno"] == str(anno))["ricostituzione"]


def da_classificare(anno: int, suffisso: str = "") -> list[dict]:
    p = RISULTATI / "uscite_segnate_{}{}.csv".format(anno, suffisso)
    with p.open(encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh)
                if r["abbinamento_giugno"] == "emittente" and r["classe"] == "senza spiegazione"]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("anno", type=int)
    #  Il 2024 ha due misure, una per finestra degli eventi: si classifica quella che si vuole ricalcolare.
    ap.add_argument("--suffisso", default="", help="suffisso del file delle uscite segnate, se non e' quello base")
    opz = ap.parse_args(argv)
    anno, suffisso = opz.anno, opz.suffisso
    a = data_ricostituzione(anno)
    da = "{}-03-31".format(anno)
    casi = da_classificare(anno, suffisso)
    budget = sec.Budget(tetto=TETTO_EDGAR)
    ricerca = Ricerca(budget)

    esiti = []
    for r in casi:
        nome = r["nome"]
        cik, trovato, s = ricerca.risolvi(nome)
        if not cik:
            esiti.append({"nome": nome, "cik": "", "nome_edgar": trovato, "somiglianza": round(s, 2),
                          "esito": "non risolta", "eventi": ""})
            continue
        d = ricerca.submissions(cik)
        eventi = eventi_nel_trimestre(d, da, a)
        esiti.append({"nome": nome, "cik": cik, "nome_edgar": trovato, "somiglianza": round(s, 2),
                      "esito": "evento nel trimestre" if eventi else "falso positivo vero",
                      "eventi": "; ".join(eventi)})

    conti = {k: sum(1 for e in esiti if e["esito"] == k)
             for k in ("evento nel trimestre", "falso positivo vero", "non risolta")}
    print("{}: {} casi senza spiegazione".format(anno, len(casi)))
    for k, v in conti.items():
        print("   {:<24} {}".format(k, v))
    print("   chiamate EDGAR usate: {}".format(budget.usate))

    righe = ["# Uscite in più del {} classificate a mano".format(anno), "",
             "Generato da `python backtest/russell_exits/classifica_extra.py {}`. ".format(anno)
             + "Identità risolta partendo dal nome con la ricerca di EDGAR, che conosce anche i nomi precedenti. "
             + "Finestra degli eventi: {} → {} (ricostituzione). Nessun rendimento calcolato.".format(da, a), "",
             "| esito | casi |", "|---|---:|"]
    righe += ["| {} | {} |".format(k, v) for k, v in conti.items()]
    righe += ["| **totale** | **{}** |".format(len(casi)), "",
              "## Caso per caso", "",
              "| nome nell'istantanea | CIK | nome su EDGAR | somiglianza | esito | depositi nel trimestre |",
              "|---|---|---|---:|---|---|"]
    for e in sorted(esiti, key=lambda x: (x["esito"], x["nome"])):
        righe.append("| {} | {} | {} | {} | {} | {} |".format(
            e["nome"], e["cik"] or "—", e["nome_edgar"] or "—", e["somiglianza"], e["esito"], e["eventi"] or "—"))
    (RISULTATI / "extra_classificati_{}{}.md".format(anno, suffisso)).write_text("\n".join(righe) + "\n", encoding="utf-8")
    with (RISULTATI / "extra_classificati_{}{}.csv".format(anno, suffisso)).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(esiti[0]))
        w.writeheader()
        w.writerows(esiti)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
