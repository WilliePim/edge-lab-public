"""Russell 2000, uscite verso il basso — controllo esterno del 2025 contro la lista ufficiale FTSE Russell.

La lista ufficiale è «Russell 3000 Index – Deletions» della ricostituzione del 27 giugno 2025 (PDF, `lista_ftse_pdf.py`):
contiene le società tolte dal Russell 3000, cioè soprattutto le uscite verso il basso dal Russell 2000, più poche
cancellazioni dal Russell 1000. Le uscite ricavate qui vengono dalle istantanee SEC del 31 marzo e del 30 giugno 2025.

Due quote:
- **ritrovate**: cancellazioni ufficiali presenti in IWM al 31 marzo 2025 che il confronto trimestrale segna come uscite
  verso il basso;
- **fuori lista**: uscite verso il basso trovate qui che non sono nella lista ufficiale (tipicamente acquisite o delistate
  nel trimestre, oppure falsi segnali del confronto trimestrale).

Abbinamento per ticker verificato, poi per nome normalizzato. Nessuna rete.

    python backtest/russell_exits/controllo_2025.py
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import identita as I  # noqa: E402
import lista_ftse_pdf as L  # noqa: E402

STATE = HERE.parents[1] / "state" / "backfill" / "russell"
OUT = HERE / "risultati" / "controllo_2025.md"


def main() -> int:
    uff = L.righe()
    sim_uff = {r["simbolo"].replace(".", "-") for r in uff}
    nomi_uff = {I.norm(r["societa"]) for r in uff}
    marzo = []
    with (STATE / "identita.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["istantanea"] == "IWM_2025-03-31":
                marzo.append(r)
    tick_marzo = {r["ticker"] for r in marzo if r["ticker"]}
    nomi_marzo = {I.norm(r["titolo"] or r["nome"]) for r in marzo}
    uscite = []
    with (HERE / "risultati" / "uscite_tutte.csv").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["anno"] == "2025" and r["direzione"] == "basso":
                uscite.append(r)

    def in_ufficiale(r):
        return (r["ticker"] and r["ticker"] in sim_uff) or I.norm(r["nome"]) in nomi_uff

    uff_in_iwm = [u for u in uff if u["simbolo"].replace(".", "-") in tick_marzo or I.norm(u["societa"]) in nomi_marzo]
    tick_usc = {r["ticker"] for r in uscite if r["ticker"]}
    nomi_usc = {I.norm(r["nome"]) for r in uscite}
    ritrovate = [u for u in uff_in_iwm if u["simbolo"].replace(".", "-") in tick_usc or I.norm(u["societa"]) in nomi_usc]
    fuori = [r for r in uscite if not in_ufficiale(r)]
    motivi_fuori = collections.Counter((r["esclusione"].split(":")[0] if r["esclusione"] else "nessuna esclusione") for r in fuori)
    mancate = [u for u in uff_in_iwm if u not in ritrovate]
    L2 = ["# Controllo esterno 2025 — uscite trimestrali contro la lista ufficiale FTSE Russell", "",
          "Generato da `python backtest/russell_exits/controllo_2025.py`. Lista ufficiale: {} cancellazioni dal Russell 3000 "
          "(ricostituzione del 27 giugno 2025). Uscite verso il basso trovate qui per il 2025: {}.".format(len(uff), len(uscite)), "",
          "| | n | quota |", "|---|---:|---:|",
          "| cancellazioni ufficiali presenti in IWM al 31 marzo 2025 | {} | |".format(len(uff_in_iwm)),
          "| … segnate qui come uscite verso il basso (**ritrovate**) | {} | {:.1%} |".format(len(ritrovate), len(ritrovate) / len(uff_in_iwm) if uff_in_iwm else 0),
          "| uscite trovate qui che non sono nella lista ufficiale (**fuori lista**) | {} | {:.1%} |".format(len(fuori), len(fuori) / len(uscite) if uscite else 0), ""]
    L2 += ["Uscite fuori lista, per esclusione applicata nel backtest: " + ", ".join("{} {}".format(k, v) for k, v in motivi_fuori.most_common()) + ".", ""]
    L2 += ["Cancellazioni ufficiali in IWM non ritrovate: " + (", ".join("{} ({})".format(u["societa"], u["simbolo"]) for u in mancate) or "nessuna") + ".", ""]
    L2 += ["Uscite fuori lista **senza esclusione** (entrerebbero nel backtest): " +
           (", ".join("{} ({})".format(r["nome"], r["ticker"]) for r in fuori if not r["esclusione"]) or "nessuna") + ".", ""]
    OUT.write_text("\n".join(L2) + "\n", encoding="utf-8")
    (HERE / "risultati" / "controllo_2025.json").write_text(json.dumps({
        "ufficiali": len(uff), "ufficiali_in_iwm": len(uff_in_iwm), "ritrovate": len(ritrovate), "uscite": len(uscite),
        "fuori_lista": len(fuori), "fuori_lista_senza_esclusione": sum(1 for r in fuori if not r["esclusione"])}, indent=1), encoding="utf-8")
    print("\n".join(L2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
