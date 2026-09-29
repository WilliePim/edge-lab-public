"""E3, fermata 1 — conteggi, coperture, disponibilità per cella, giorno d'ingresso B. **Nessun rendimento extra.**

Legge i file prodotti dai passi (`universo.csv`, `prospetti.jsonl`, `casi.csv`, `filtri.csv`, `peer.csv`,
`verifica_30.json` se c'è) e scrive `backtest/ipo_e3/risultati/conteggi.md`. Non apre prezzi dopo l'ingresso: la
disponibilità di una finestra si giudica sul calendario (l'ingresso più l'orizzonte deve stare nell'archivio).

    python backtest/ipo_e3/conteggi.py
"""
from __future__ import annotations

import bisect
import collections
import csv
import json
import statistics

import comune as C

ORIZZONTI = (63, 126, 252)
PLACEBO = 126
ANNI = [str(a) for a in C.ANNI]
USCITA = C.RISULTATI / "conteggi.md"


def leggi_csv(nome: str) -> list[dict]:
    p = C.STATO / nome
    return list(csv.DictReader(p.open(encoding="utf-8"))) if p.exists() else []


def tabella(testata: list[str], righe: list[list]) -> list[str]:
    fuori = ["| " + " | ".join(testata) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(testata))) + "|"]
    fuori += ["| " + " | ".join(str(c) for c in r) + " |" for r in righe]
    return fuori


def per_anno(righe: list[dict], chiave=lambda r: True) -> list:
    c = collections.Counter(r["anno"] for r in righe if chiave(r))
    return [c.get(a, 0) for a in ANNI] + [sum(c.values())]


def main() -> int:
    ids = C.ids()
    ultima = len(ids) - 1
    universo = leggi_csv("universo.csv")
    casi = leggi_csv("casi.csv")
    filtri = leggi_csv("filtri.csv")
    peer = leggi_csv("peer.csv")
    pros = [json.loads(r) for r in (C.STATO / "prospetti.jsonl").open(encoding="utf-8") if r.strip()]
    L = ["# E3 — conteggi, con le decisioni della fermata 1", "",
         "Nessun rendimento extra calcolato o guardato. Generato da `backtest/ipo_e3/conteggi.py`.", ""]

    # ---------------------------------------------------------------------------------------------- imbuto ---
    L += ["## 1. Imbuto per anno", ""]
    testata = ["passo"] + ANNI + ["totale"]
    motivo_uni = lambda r: (r["motivo"].split(" (")[0] if r["motivo"].startswith("classe") else r["motivo"])
    righe = [["CIK con un prospetto 424B4/B1 (o B3)"] + per_anno(universo)]
    for m in [m for m, _ in collections.Counter(motivo_uni(r) for r in universo if r["motivo"]).most_common()]:
        righe.append(["− " + m] + per_anno(universo, lambda r, m=m: r["motivo"] and motivo_uni(r) == m))
    righe.append(["**restano dopo le esclusioni senza testo**"] + per_anno(universo, lambda r: not r["motivo"]))
    motivi_casi = collections.Counter(x["motivo"] for x in casi if x["esito"] == "fuori")
    for m, _n in motivi_casi.most_common():
        righe.append(["− " + m] + per_anno(casi, lambda x, m=m: x["esito"] == "fuori" and x["motivo"] == m))
    righe.append(["**classificate alla data di controllo**"] + per_anno(casi, lambda x: x["esito"] == "classificata"))
    for g in ("rotta", "forte", "intermedia"):
        righe.append(["· " + g] + per_anno(casi, lambda x, g=g: x["gruppo"] == g))
    for ing in ("A", "B", "C"):
        righe.append(["rotte che passano i filtri all'ingresso " + ing] +
                     per_anno(filtri, lambda r, ing=ing: r["gruppo"] == "rotta" and r["ingresso"] == ing
                              and r["passa"] == "sì"))
    righe.append(["forti senza fusioni annunciate"] +
                 per_anno(filtri, lambda r: r["gruppo"] == "forte" and r["passa"] == "sì"))
    L += tabella(testata, righe) + [""]
    lp = [x for x in casi if x["lp_unita"] == "sì"]
    L += ["**Società in accomandita e LLC con «common units»** (escluse, decisione dell'utente alla fermata 1): {} "
          "segnate nel prospetto.".format(len(lp)), "",
          "**Serie incoerenti con il prezzo di collocamento** (ADR-051-052: prima chiusura fuori da 0,5-3 volte il prezzo "
          "di collocamento, escluse): " + (", ".join("{} `{}` ({}×)".format(
              x["nome"][:30], x["codice"], x["rapporto_prima_chiusura"] or "—")
              for x in casi if x["motivo"] == "prima chiusura incoerente con il prezzo di collocamento") or "nessuna")
          + ".", "",
          "**Costituite fuori dagli Stati Uniti ma domestiche** (restano, contate): {} classificate.".format(
              sum(1 for x in casi if x["costituita_fuori_usa"] == "True" and x["esito"] == "classificata")), ""]
    salti = leggi_csv("salti.csv")
    if salti:
        es = collections.Counter(r["esito"] for r in salti)
        gr = [r for r in salti if r["gruppo"]]
        L += ["**Escluse per le barre a causa di un `salto_sospetto`** (`salti.py`; restano fuori, decisione dell'utente alla fermata 1): delle {} IPO "
              "con meno dell'80% di barre, {}. Le classificabili sulle chiusure grezze, con il salto dopo la data di "
              "controllo, sarebbero:".format(len(salti), ", ".join("{} {}".format(k, v) for k, v in es.most_common())),
              ""]
        L += tabella(testata, [["· " + g] + per_anno(gr, lambda r, g=g: r["gruppo"] == g)
                               for g in ("rotta", "forte", "intermedia")]) + [""]

    # -------------------------------------------------------------------------------------------- coperture ---
    L += ["## 2. Coperture per anno", ""]
    letti = {p["cik"]: p for p in pros}
    dopo_testo = [x for x in casi if x["motivo"] != "" or x["esito"] == "classificata"]
    uni_rest = [r for r in universo if not r["motivo"]]
    righe = [
        ["prospetto letto"] + per_anno(uni_rest, lambda r: letti.get(r["cik"], {}).get("esito") == "letto"),
        ["serie di prezzi entro 10 sedute (identità per CIK)"] + per_anno(uni_rest, lambda r: bool(r["codice"])),
        ["prezzo di collocamento trovato"] + per_anno(uni_rest, lambda r: letti.get(r["cik"], {}).get("prezzo") is not None),
        ["lock-up trovato"] + per_anno(uni_rest, lambda r: letti.get(r["cik"], {}).get("lockup_giorni") is not None),
        ["data dalla copertina"] + per_anno(casi, lambda x: x["fonte_data"] == "copertina"),
        ["data dalla seduta prima della prima barra"] + per_anno(casi, lambda x: x["fonte_data"].startswith("seduta")),
        ["data della copertina a più di 5 sedute dalla prima barra"] + per_anno(casi, lambda x: x["data_incoerente"] == "sì"),
    ]
    L += tabella(testata, righe) + [""]
    durate = collections.Counter(int(x["lockup_giorni"]) for x in casi if x["esito"] == "classificata")
    L += ["**Durate del lock-up** fra le classificate: " + ", ".join(
        "{} giorni: {}".format(d, n) for d, n in sorted(durate.items())) + ".", ""]
    eccezioni = sum(1 for x in casi if x["esito"] == "classificata" and len(json.loads(x["lockup_durate"] or "{}")) > 1)
    L += ["Prospetti con più di una durata nelle frasi di lock-up (eccezioni registrate): {}.".format(eccezioni), ""]
    L += ["**Filtri delle rotte**, per ingresso: passa / non passa / non verificabile.", ""]
    righe = []
    for ing in ("A", "B", "C", "forte"):
        for f in ("f1", "f2", "f3", "f4"):
            sel = [r for r in filtri if r["ingresso"] == ing and r.get(f)]
            if not sel:
                continue
            c = collections.Counter(r[f] for r in sel)
            righe.append([ing, f, c.get("passa", 0), c.get("non passa", 0), c.get("non verificabile", 0)])
    L += tabella(["ingresso", "filtro", "passa", "non passa", "non verificabile"], righe) + [""]
    L += ["Filtro 1 con l'opzione (b) scelta alla fermata 1: dove i 12 mesi non sono calcolabili, il flusso di cassa "
          "operativo progressivo di 6-12 mesi deve essere positivo (addendum §1).", ""]

    # ------------------------------------------------------------------------------------- disponibilità ---
    L += ["## 3. Casi disponibili per orizzonte e per cella", "",
          "Un caso è disponibile per un orizzonte se l'ingresso più l'orizzonte sta nell'archivio (ultima seduta {}). "
          "Il placebo sposta la finestra di 252 sedute in avanti di 126. Con peer = i 5 peer sono stati trovati."
          .format(ids[ultima]), ""]
    ok_peer = {(p["cik"], p["ingresso"]) for p in peer if p["esito"] == "ok"}
    righe = []
    for ing in ("A", "B", "C", "forte"):
        sel = [r for r in filtri if r["ingresso"] == ing and r["passa"] == "sì"]
        if not sel:
            continue
        riga = [ing, len(sel), sum(1 for r in sel if (r["cik"], ing) in ok_peer)]
        for h in ORIZZONTI:
            riga.append(sum(1 for r in sel if (r["cik"], ing) in ok_peer
                            and bisect.bisect_left(ids, r["data_ingresso"]) + h <= ultima))
        riga.append(sum(1 for r in sel if (r["cik"], ing) in ok_peer
                        and bisect.bisect_left(ids, r["data_ingresso"]) + PLACEBO + 252 <= ultima))
        righe.append(riga)
    L += tabella(["ingresso", "passano i filtri", "con peer", "63", "126", "252", "placebo 252"], righe) + [""]
    esiti_peer = collections.Counter((p["ingresso"], p["esito"]) for p in peer)
    L += ["**Peer**, esito per ingresso: " + "; ".join("{} {}: {}".format(i, e, n)
                                                       for (i, e), n in sorted(esiti_peer.items())) + ".", ""]
    for cella, ing in (("verdetto 1 (rotte, B × 252)", "B"), ("verdetto 2 (forti × 252)", "forte")):
        sel = [r for r in filtri if r["ingresso"] == ing and r["passa"] == "sì" and (r["cik"], ing) in ok_peer
               and bisect.bisect_left(ids, r["data_ingresso"]) + 252 <= ultima]
        anni = collections.Counter(r["anno"] for r in sel)
        L += ["**{}**: {} casi in {} anni di coorte ({}). Criterio 1 del verdetto: almeno 80 casi e 8 anni.".format(
            cella, len(sel), len(anni), ", ".join("{} {}".format(a, anni[a]) for a in ANNI if anni.get(a))), ""]

    # ----------------------------------------------------------------------------------- giorno B e controllo ---
    L += ["## 4. Giorno d'ingresso B e controllo di degenerazione", ""]
    rotte = [x for x in casi if x["gruppo"] == "rotta"]
    off = sorted(int(x["offset_B"]) for x in rotte if x["offset_B"])
    if off:
        primo = sum(1 for o in off if o == 30)
        forz = sum(1 for x in rotte if x["esito_B"] == "FORZATO")
        q = statistics.quantiles(off, n=4)
        L += ["Sedute dalla scadenza del lock-up all'ingresso B, sulle {} rotte con un ingresso B: primo giorno "
              "possibile (S + 30) {} ({:.1%}), forzati (S + 126) {} ({:.1%}), quartili {:.0f} / {:.0f} / {:.0f}."
              .format(len(off), primo, primo / len(off), forz, forz / len(off), *q), ""]
        L += ["**Degenerazione**: {} dei casi agli estremi ({}).".format(
            "{:.1%}".format((primo + forz) / len(off)),
            "più di metà: DICHIARATO" if primo + forz > len(off) / 2 else "meno di metà"), ""]
        motivi_b = collections.Counter(x["esito_B"] for x in rotte)
        L += ["Esiti della regola B: " + ", ".join("{} {}".format(k, v) for k, v in motivi_b.most_common()) + ".", ""]

    # ------------------------------------------------------------------------------------------- verifica ---
    L += ["## 5. Verifica a mano di 30 prospetti", ""]
    ver = C.HERE / "verifica_30.json"
    if ver.exists():
        v = json.loads(ver.read_text(encoding="utf-8"))
        righe = [[k, d["estratti"], d["giusti"], "{:.1%}".format(d["giusti"] / d["estratti"]) if d["estratti"] else "—",
                  d["non_trovati"]] for k, d in v["campi"].items()]
        L += tabella(["campo", "estratti", "giusti", "precisione", "non trovati"], righe) + [""]
        L += ["Dettaglio caso per caso: `backtest/ipo_e3/verifica_30.md`.", ""]
    else:
        L += ["*Non ancora fatta.*", ""]

    # ------------------------------------------------------------------------------------------------ esempi ---
    L += ["## 6. Un caso completo per gruppo (senza rendimenti)", "",
          "Il primo caso in ordine di data con i 5 peer trovati. Si mostrano date, filtri, peer e i numeri prima "
          "dell'ingresso (rendimento a 6 mesi e capitalizzazione che hanno scelto i peer); nessun rendimento dopo "
          "l'ingresso.", ""]
    per_cik = {x["cik"]: x for x in casi}
    f_di = {(r["cik"], r["ingresso"]): r for r in filtri}
    for gruppo, ing in (("rotta", "B"), ("forte", "forte")):
        cand = sorted((p for p in peer if p["gruppo"] == gruppo and p["ingresso"] == ing and p["esito"] == "ok"),
                      key=lambda p: p["data_ingresso"])
        if not cand:
            L += ["*Nessuna {} con peer.*".format(gruppo), ""]
            continue
        p = cand[0]
        x, f = per_cik[p["cik"]], f_di[(p["cik"], ing)]
        L += ["### {}: {} (CIK {})".format(gruppo.capitalize(), x["nome"], x["cik"]), "",
              "- collocamento {} a ${} ({}), prima barra {}, codice {}".format(
                  x["data_collocamento"], x["prezzo"], x["fonte_data"], x["prima_barra"], x["codice"]),
              "- lock-up {} giorni (frasi: {}); scadenza {} → seduta S {}; data di controllo {}".format(
                  x["lockup_giorni"], x["lockup_durate"], x["scadenza"], x["S"], x["controllo"]),
              "- alla data di controllo: {:+.1%} dal collocamento; minimo dalla prima barra {:+.1%}".format(
                  float(x["rendimento_controllo"]), float(x["minimo_su_collocamento"]))]
        if gruppo == "rotta":
            L += ["- ingressi: A {}, **B {}** (S + {}, {}), C {}".format(
                x["ingresso_A"], x["ingresso_B"], x["offset_B"], x["esito_B"], x["ingresso_C"])]
        L += ["- filtri all'ingresso: " + "; ".join("{} {} ({})".format(k, f[k], f[k + "_nota"])
                                                     for k in ("f1", "f2", "f3", "f4") if f.get(k)),
              "- terzile del rendimento a 6 mesi: {} (caso {:+.1%}); capitalizzazione del caso {:,.0f} $ "
              "(azioni da {}); universo dei peer quel giorno: {}".format(
                  p["terzile"], float(p["rend_6m"]), float(p["cap"]), p["fonte_azioni"], p["universo"]), ""]
        L += tabella(["peer", "CIK", "capitalizzazione $", "rendimento 6 mesi prima"],
                     [[v["codice"], v["cik"], "{:,.0f}".format(v["cap"]), "{:+.1%}".format(v["rend_6m"])]
                      for v in json.loads(p["peer"])]) + [""]

    # --------------------------------------------------------------------------------------------- chiamate ---
    stato = json.loads(C.CALLS.read_text(encoding="utf-8"))
    L += ["## 7. Chiamate EDGAR", "", "{} su {} (i due zip in blocco contano una chiamata ciascuno).".format(
        stato["network"], stato.get("tetto", C.TETTO)), ""]
    C.RISULTATI.mkdir(exist_ok=True)
    USCITA.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("scritto", USCITA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
