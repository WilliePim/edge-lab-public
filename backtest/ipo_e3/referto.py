"""E3, fermata 2 — il referto: la pagina 1 scritta a mano (`risultati/pagina1.md`) più l'appendice generata da
`risultati/verdetto.json`. Scrive `risultati/referto.md`.

    python backtest/ipo_e3/referto.py
"""
from __future__ import annotations

import json
import subprocess

import comune as C

ANNI = [str(a) for a in C.ANNI]


def pc(x) -> str:
    return "—" if x is None else "{:+.1%}".format(x)


def tt(x) -> str:
    return "—" if x is None else "{:.2f}".format(x)


def tabella(testata, righe) -> list[str]:
    fuori = ["| " + " | ".join(testata) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(testata))) + "|"]
    return fuori + ["| " + " | ".join(str(c) for c in r) + " |" for r in righe]


def main() -> int:
    v = json.loads((C.RISULTATI / "verdetto.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "log", "-1", "--format=%h"], capture_output=True, text=True,
                            cwd=C.HERE).stdout.strip()
    L = (C.RISULTATI / "pagina1.md").read_text(encoding="utf-8").rstrip().splitlines() + ["", "---", "",
         "# Appendice", "",
         "Generata da `backtest/ipo_e3/analisi.py` e `referto.py` (codice al commit `{}`). Regole: "
         "`2026-09-22_preregistrazione.md` e `2026-09-22_addendum_fermata1.md`; decisioni ADR-046 … ADR-052. "
         "Conteggi e imbuto: `risultati/conteggi.md`.".format(commit), ""]

    # ----------------------------------------------------------------------------------------------- verdetti ---
    L += ["## A. Verdetti", ""]
    righe = []
    for d, x in v["verdetti"].items():
        c = v["celle"][x["cella"]]
        p = v["celle"][x["cella"].split(" × ")[0] + " × placebo"]
        sub = c["sottoperiodi"]
        righe.append([d, x["cella"], c["casi"], c["anni"], pc(c["mediana"]), pc(c["media_delle_medie"]),
                      "{} ({})".format(tt(c["t"]), c["gradi"] if c["gradi"] is not None else "—"),
                      pc(sub["2012-2018"]["media_delle_medie"]), pc(sub["2019-2024"]["media_delle_medie"]),
                      "{}, t {}".format(pc(p["media_delle_medie"]), tt(p["t"])), "**{}**".format(x["esito"])])
    L += tabella(["domanda", "cella", "casi", "anni", "mediana", "media delle medie annuali", "t (gradi)",
                  "2012-18", "2019-24", "placebo: media, t", "esito"], righe) + [""]
    for d, x in v["verdetti"].items():
        L += ["**{} — {}.** Criteri, nell'ordine:".format(d, x["esito"]), ""]
        L += ["- {} — {}".format("vero" if ok else "**falso**", k) for k, ok in x["criteri"].items()] + [""]

    # ------------------------------------------------------------------------------------------ medie per anno ---
    L += ["## B. Medie per anno di coorte, celle del verdetto e placebo", ""]
    nomi = ["B × 252", "B × placebo", "forte × 252", "forte × placebo", "base × 252"]
    righe = []
    for a in ANNI:
        r = [a]
        for n in nomi:
            c = v["celle"][n]
            k = c["casi_per_anno"].get(a, 0)
            r += [k, pc(c["medie_per_anno"].get(a)) if k else "—"]
        righe.append(r)
    L += tabella(["anno"] + [x for n in nomi for x in (n + ": casi", "media")], righe) + [""]

    # ------------------------------------------------------------------------------------ cella del verdetto 1 ---
    L += ["## C. I casi della cella del verdetto 1 (rotte, B × 252)", ""]
    L += tabella(["nome", "anno", "ingresso B", "rendimento extra a 252 sedute", "esito"],
                 [[r["nome"], r["anno"], r["ingresso"], pc(float(r["extra"])), r["esito"]]
                  for r in sorted(v["cella_verdetto_1"], key=lambda r: r["ingresso"])]) + [""]

    # --------------------------------------------------------------------------------------- celle descrittive ---
    L += ["## D. Tutte le celle (descrittive, tranne le due del verdetto)", ""]
    righe = [[n, c["casi"], c["anni"], pc(c["media"]), pc(c["mediana"]),
              "—" if c["quota_positivi"] is None else "{:.0%}".format(c["quota_positivi"]),
              pc(c["media_delle_medie"]), tt(c["t"])] for n, c in v["celle"].items()]
    righe += [[n, c["casi"], c["anni"], pc(c["media"]), pc(c["mediana"]),
               "—" if c["quota_positivi"] is None else "{:.0%}".format(c["quota_positivi"]),
               pc(c["media_delle_medie"]), tt(c["t"])] for n, c in v["coorte_2020_2021"].items()]
    L += tabella(["cella", "casi", "anni", "media", "mediana", "positivi", "media delle medie annuali", "t"],
                 righe) + [""]

    # ---------------------------------------------------------------------------------- esiti e delistati ---
    L += ["## E. Chi entra, chi esce, e come sono trattati i delistati", ""]
    tipi = sorted({k for e in v["esiti"].values() for k in e})
    L += tabella(["cella"] + tipi, [[n] + [e.get(k, 0) for k in tipi] for n, e in v["esiti"].items()]) + [""]
    L += ["Prezzo dell'offerta in contanti trovato per {} titoli delistati su {} cercati. Esiti dei peer: {}.".format(
        v["offerte_trovate"], v["offerte_cercate"], "; ".join("{}: {}".format(k, n) for k, n in v["peer"].items())),
        ""]

    # --------------------------------------------------------------------------------- finestre descrittive ---
    L += ["## F. Finestre descrittive delle rotte (rendimento del titolo, non extra)", ""]
    righe = [[pop, n, d["casi"], pc(d["mediana"]), pc(d["media"])]
             for pop, x in v["finestre_descrittive"].items() for n, d in x.items()]
    L += tabella(["popolazione", "finestra", "casi", "mediana", "media"], righe) + [""]

    # --------------------------------------------------------------------------------------------- insider ---
    L += ["## G. Spaccato insider (cella B × 252, descrittivo)", "",
          "Attesa registrata prima dei rendimenti: il gruppo con vendite di dirigenti o amministratori fra la "
          "scadenza del lock-up e l'ingresso fa peggio.", ""]
    L += tabella(["gruppo", "casi", "mediana", "media", "casi (nome, extra, vendite)"],
                 [[g, d["casi"], pc(d["mediana"]), pc(d["media"]),
                   "; ".join("{} {} ({})".format(n, pc(e), k) for n, e, k in d["nomi"])]
                  for g, d in sorted(v["insider"].items())]) + [""]

    # ---------------------------------------------------------------------------------------------- sensibilità ---
    sp = C.RISULTATI / "sensibilita.json"
    if sp.exists():
        z = json.loads(sp.read_text(encoding="utf-8"))
        L += ["## H. Sensibilità post hoc: capitalizzazioni XBRL assurde (non decide niente)", "",
              "Trovata dopo i rendimenti, guardando i valori estremi (`sensibilita.py`). Per {} IPO le azioni in "
              "XBRL danno una capitalizzazione sotto un decimo di quella del prospetto, a volte di poche migliaia di "
              "dollari, e i peer scelti sono microsocietà con serie rotte. Le celle rifatte senza quei casi:"
              .format(len({e["nome"] for e in z["esclusi"]})), ""]
        L += tabella(["cella", "casi", "mediana", "media delle medie annuali", "t"],
                     [[n, c["casi"], pc(c["mediana"]), pc(c["media_delle_medie"]), tt(c["t"])]
                      for n, c in z["celle"].items()]) + [""]
        L += ["Verdetti con le stesse regole: " + "; ".join("{} {}".format(d, x["esito"])
                                                           for d, x in z["verdetti"].items()) + ". Casi tolti: " +
              ", ".join(sorted({"{} ({:.4f}×)".format(e["nome"], e["rapporto"]) for e in z["esclusi"]})) + ".", ""]

    L += ["## I. Limiti dichiarati", "",
          "- **IPO tolte per `salto_sospetto`** (addendum, punto 7): 204 IPO escono perché l'archivio toglie la loro "
          "storia fino a un salto non verificato. Sulle chiusure grezze sarebbero state 58 rotte e 31 forti: il "
          "campione delle rotte perde soprattutto le peggiori.",
          "- **Giorno B degenere** (punto 8): oltre metà delle rotte entra al primo giorno possibile o all'ingresso "
          "forzato (`conteggi.md` §4).",
          "- **Peer:** la coerenza della serie con un prezzo di riferimento (ADR-051) non si può controllare; il SIC "
          "usato per togliere banche e REIT è quello di oggi.",
          "- **Capitalizzazioni XBRL** assurde per alcune IPO: sezione H.",
          ""]
    L += ["## J. Chiamate EDGAR", "", "{} su {}.".format(v["chiamate_edgar"]["network"],
                                                          v["chiamate_edgar"].get("tetto", C.TETTO)), ""]
    (C.RISULTATI / "referto.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("scritto", C.RISULTATI / "referto.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
