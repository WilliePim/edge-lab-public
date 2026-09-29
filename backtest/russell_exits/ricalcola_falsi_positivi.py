"""Russell 2000 — falsi positivi ricalcolati unendo la classificazione automatica e quella a mano.

`falsi_positivi.py` lascia «senza spiegazione» i casi di cui non riesce a leggere EDGAR, perché l'identità non è
risolta. `classifica_extra.py` li riprende uno per uno partendo dal nome con la ricerca di EDGAR, che conosce anche
i nomi precedenti, e li divide in tre: evento societario nel trimestre (la fase 1 li toglie, non sono falsi
positivi), falso positivo vero, non risolta.

Qui si rimettono insieme le due cose, con la definizione di ADR-039:

> **falso positivo** = titolo segnato come uscita dalla definizione, presente nel campione dopo le esclusioni della
> fase 1, ma assente dalla lista ufficiale.

I «non risolti» si riportano **a parte e in tutti e due i modi**: contati e non contati. Non sappiamo che cosa
siano, e metterli d'ufficio da una parte sceglierebbe il risultato.

    python backtest/russell_exits/ricalcola_falsi_positivi.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RISULTATI = HERE / "risultati"
SOGLIA = 0.10

#  (anno, suffisso del file). Il 2024 compare due volte, una per finestra degli eventi: con l'istantanea «dopo»
#  spostata a settembre le due letture danno numeri diversi e la scelta e' dell'utente, quindi si riportano
#  entrambe invece di sceglierne una in silenzio.
ANNI = [(2016, ""), (2017, ""), (2021, ""), (2022, ""), (2023, ""),
        (2024, ""), (2024, "_eventi_fino_all_istantanea"), (2025, "")]
#  Quale misura decide la soglia, per gli anni che ne hanno due. Il 2024: finestra degli eventi fino all'istantanea
#  di settembre, decisione dell'utente del 21-09-2026, a condizione che ogni sparizione estiva esclusa abbia il suo
#  deposito EDGAR (verificato: vedi l'addendum). L'altra misura resta nel rapporto, solo non decide.
DECIDE = {2024: "_eventi_fino_all_istantanea"}


def segnate(anno: int, suffisso: str) -> list[dict]:
    p = RISULTATI / "uscite_segnate_{}{}.csv".format(anno, suffisso)
    with p.open(encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["abbinamento_giugno"] == "emittente"]


def a_mano(anno: int, suffisso: str) -> dict[str, str]:
    """nome -> esito della classificazione a mano, se c'è stata."""
    p = RISULTATI / "extra_classificati_{}{}.csv".format(anno, suffisso)
    if not p.exists():
        return {}
    with p.open(encoding="utf-8", newline="") as fh:
        return {r["nome"]: r["esito"] for r in csv.DictReader(fh)}


def ufficiali(anno: int, suffisso: str) -> int:
    """Quante cancellazioni ufficiali la definizione ha ritrovato, dal rapporto già scritto."""
    p = RISULTATI / "falsi_positivi_{}{}.md".format(anno, suffisso)
    m = re.search(r"ritrovate\*\*\) \| [\d.]+ \([\d.]+%\) \| (\d+) \(([\d.]+)%\)", p.read_text(encoding="utf-8"))
    return (int(m.group(1)), float(m.group(2))) if m else (0, 0.0)


def conta(anno: int, suffisso: str) -> dict:
    righe = segnate(anno, suffisso)
    mano = a_mano(anno, suffisso)
    tolte_fase1 = veri = non_risolti = cusip_nuovo = 0
    for r in righe:
        if r["abbinamento"]:                                   # sta nella lista ufficiale: non è un falso positivo
            continue
        classe = r["classe"]
        if classe == "acquisita, in fusione o delistata nel trimestre":
            tolte_fase1 += 1
        elif classe == "stesso emittente con un CUSIP nuovo":
            cusip_nuovo += 1
        elif classe == "senza spiegazione":
            esito = mano.get(r["nome"], "")
            if esito == "evento nel trimestre":
                tolte_fase1 += 1
            elif esito == "non risolta":
                non_risolti += 1
            else:                                              # falso positivo vero, o mai classificato a mano
                veri += 1
    n = len(righe)
    ritrovate, quota_ritrovate = ufficiali(anno, suffisso)
    fp = cusip_nuovo + veri
    return {"anno": anno, "finestra": "istantanea dopo" if suffisso else "ricostituzione",
            "decide": DECIDE.get(anno, "") == suffisso,
            "uscite_segnate": n, "ufficiali_ritrovate": ritrovate, "quota_ritrovate": quota_ritrovate,
            "tolte_dalla_fase1": tolte_fase1, "cusip_nuovo": cusip_nuovo, "falsi_positivi_veri": veri,
            "non_risolti": non_risolti,
            "falsi_positivi": fp, "quota": round(fp / n, 4) if n else None,
            "quota_con_non_risolti": round((fp + non_risolti) / n, 4) if n else None,
            "classificati_a_mano": bool(mano)}


def main(argv=None) -> int:
    fuori = []
    for anno, suffisso in ANNI:
        if not (RISULTATI / "uscite_segnate_{}{}.csv".format(anno, suffisso)).exists():
            continue
        fuori.append(conta(anno, suffisso))

    print("%-5s %-16s %7s %9s %8s %8s %8s %8s" % (
        "anno", "finestra", "segnate", "ritrovate", "fase1", "veri", "quota", "+non ris."))
    sopra = []
    for r in fuori:
        print("%-5d %-16s %7d %8.1f%% %8d %8d %7.1f%% %8.1f%%" % (
            r["anno"], r["finestra"], r["uscite_segnate"], r["quota_ritrovate"], r["tolte_dalla_fase1"],
            r["falsi_positivi"], 100 * r["quota"], 100 * r["quota_con_non_risolti"]))
        if r["decide"] and r["quota"] > SOGLIA:
            sopra.append(r["anno"])
    print()
    print("anni sopra la soglia del {:.0%}, sulla misura che decide: {}".format(SOGLIA, sopra or "nessuno"))

    righe = ["# Falsi positivi ricalcolati, dopo la classificazione a mano", "",
             "Generato da `python backtest/russell_exits/ricalcola_falsi_positivi.py`. Definizione di ADR-039: "
             "falso positivo = titolo segnato come uscita, presente nel campione dopo le esclusioni della fase 1, "
             "assente dalla lista ufficiale. Nessun rendimento calcolato.", "",
             "Moduli che escludono in fase 1: quelli della pre-registrazione (§3, esclusione 2), senza l'8-K voce "
             "2.01 -- la deposita anche chi compra o sopravvive a una fusione inversa, e non prova una sparizione.", "",
             "| anno | finestra eventi | decide | uscite segnate | ufficiali ritrovate | tolte dalla fase 1 | falsi positivi | quota | con i non risolti |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in fuori:
        righe.append("| {} | {} | {} | {} | {:.1f}% | {} | {} | **{:.1f}%** | {:.1f}% |".format(
            r["anno"], r["finestra"], "sì" if r["decide"] else "no", r["uscite_segnate"], r["quota_ritrovate"],
            r["tolte_dalla_fase1"], r["falsi_positivi"], 100 * r["quota"], 100 * r["quota_con_non_risolti"]))
    righe += ["", "Anni sopra la soglia del 10%, sulla misura che decide: **{}**.".format(
        ", ".join(str(x) for x in sopra) if sopra else "nessuno"), ""]
    (RISULTATI / "falsi_positivi_ricalcolati.md").write_text("\n".join(righe) + "\n", encoding="utf-8")
    (RISULTATI / "falsi_positivi_ricalcolati.json").write_text(json.dumps(fuori, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
