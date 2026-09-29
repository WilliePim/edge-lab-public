"""E3, fase 0 punto 2 — verifica a mano di 30 prospetti a caso. Precisione per campo; sotto il 90% ci si ferma.

Due passi, **alla cieca**:

    python backtest/ipo_e3/verifica.py campione    # estrae i 30 (seme fisso) e stampa SOLO il testo, non i valori
    python backtest/ipo_e3/verifica.py confronta   # legge verifica_30_verita.json e confronta con il parsing

Il campione si estrae fra le IPO rimaste dopo le esclusioni del testo (prospetto letto, nessun motivo di
esclusione), con le regole di `prospetto.py` già ferme. Per ogni prospetto si mostrano la copertina, il riepilogo
dell'offerta e le frasi sul lock-up, senza i valori estratti: chi legge scrive i valori veri in
`verifica_30_verita.json` senza vedere quelli del parsing. Solo dopo, `confronta` li mette a fianco.

**Campi e confronto.**
- *prezzo*: uguale al centesimo;
- *data*: la data di collocamento come la usa il backtest (copertina, o seduta prima della prima barra); giusta se
  coincide con la data di copertina o di pricing letta nel documento;
- *lock-up*: la durata in giorni del lock-up di amministratori, dirigenti e azionisti;
- *azioni offerte*: l'offerta base della copertina (società più azionisti venditori, senza opzione);
- *azioni dopo l'offerta*: il totale «outstanding after this offering» della classe offerta.

Precisione = giusti / estratti. Un campo che il parsing non ha trovato non entra nella precisione: si conta a parte
come «non trovato» (è copertura, non precisione).
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys

import comune as C

SEME = 20260923
N = 30
CAMPIONE = C.HERE / "verifica_30_campione.json"
VERITA = C.HERE / "verifica_30_verita.json"
ESITO = C.HERE / "verifica_30.json"
DETTAGLIO = C.HERE / "verifica_30.md"
CAMPI = ("prezzo", "data", "lockup", "offerte", "dopo")


def _testo(url: str) -> str:
    import survival as SV
    return re.sub(r"[\s ​﻿]+", " ", SV.testo(C.budget().get(url)))


def campione() -> int:
    casi = {x["cik"]: x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8"))}
    pros = [json.loads(r) for r in (C.STATO / "prospetti.jsonl").open(encoding="utf-8") if r.strip()]
    candidati = sorted((p for p in pros if p["esito"] == "letto" and not p["motivo_testo"]), key=lambda p: p["cik"])
    scelti = random.Random(SEME).sample(candidati, N)
    CAMPIONE.write_text(json.dumps([{"cik": p["cik"], "url": p["url"]} for p in scelti], indent=1), encoding="utf-8")
    for i, p in enumerate(scelti, 1):
        t = _testo(p["url"])
        x = casi.get(p["cik"], {})
        print("=" * 100)
        print("#{} CIK {} — {} — prima barra {}".format(i, p["cik"], x.get("nome", ""), x.get("prima_barra", "")))
        print("COPERTINA:", t[:1800])
        #  Dove sta la data: frasi esplicite, poi le date isolate nella fine della copertina.
        for m in list(re.finditer(r"date\s+of\s+this\s+prospectus\s+is|prospectus\s+dated", t[:40000], re.I))[:2]:
            print("DATA:", t[max(0, m.start() - 60):m.end() + 40])
        for m in list(re.finditer(r"[A-Z][a-z]+ \d{1,2}, 20\d\d", t[1500:6000]))[:4]:
            print("DATA ISOLATA:", t[1500 + max(0, m.start() - 60):1500 + m.end() + 10])
        for m in list(re.finditer(r"outstanding\s+(?:immediately\s+)?(?:after|following)\s+(?:this|the)\s+offering",
                                  t, re.I))[:3]:
            print("DOPO:", t[max(0, m.start() - 120):m.end() + 180])
        #  Le frasi del lock-up con una durata, dalla sezione dei collocatori in poi (seconda metà) e poi ovunque.
        frasi = [m for m in re.finditer(r"[^.]{0,400}lock[\s-]?up[^.]{0,400}\bdays?\b[^.]{0,200}|"
                                        r"[^.]{0,400}\bdays?\b[^.]{0,200}lock[\s-]?up[^.]{0,200}", t, re.I)]
        viste = 0
        for m in [m for m in frasi if m.start() > len(t) * 0.5] + [m for m in frasi if m.start() <= len(t) * 0.5]:
            print("LOCK-UP:", m.group(0)[:700])
            viste += 1
            if viste == 4:
                break
    print("\nScrivi i valori veri in", VERITA)
    return 0


def _uguale(campo: str, vero, estratto) -> bool:
    if campo == "prezzo":
        return abs(float(vero) - float(estratto)) < 0.005
    if campo in ("lockup", "offerte", "dopo"):
        return int(vero) == int(estratto)
    return str(vero) == str(estratto)


def confronta() -> int:
    casi = {x["cik"]: x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8"))}
    pros = {json.loads(r)["cik"]: json.loads(r) for r in (C.STATO / "prospetti.jsonl").open(encoding="utf-8") if r.strip()}
    verita = json.loads(VERITA.read_text(encoding="utf-8"))
    campi = {c: {"estratti": 0, "giusti": 0, "non_trovati": 0, "non_determinabili": 0} for c in CAMPI}
    righe = ["# E3 — verifica a mano di 30 prospetti", "",
             "Campione: seme {}, fra le IPO rimaste dopo le esclusioni del testo. Valori veri letti alla cieca "
             "(`verifica.py campione`), poi confrontati (`verifica.py confronta`).".format(SEME), "",
             "| # | CIK | nome | campo | vero | parsing | esito |", "|---:|---|---|---|---|---|---|"]
    for i, v in enumerate(verita, 1):
        p, x = pros[v["cik"]], casi.get(v["cik"], {})
        estratto = {"prezzo": p.get("prezzo"), "data": x.get("data_collocamento") or p.get("data_copertina"),
                    "lockup": p.get("lockup_giorni"), "offerte": p.get("azioni_offerte"), "dopo": p.get("azioni_dopo")}
        for c in CAMPI:
            vero = v.get(c)
            if vero is None:
                campi[c]["non_determinabili"] += 1
                esito = "non determinabile a mano"
            elif estratto[c] is None:
                campi[c]["non_trovati"] += 1
                esito = "non trovato"
            else:
                campi[c]["estratti"] += 1
                ok = _uguale(c, vero, estratto[c])
                campi[c]["giusti"] += ok
                esito = "giusto" if ok else "**sbagliato**"
            righe.append("| {} | {} | {} | {} | {} | {} | {} |".format(i, v["cik"], x.get("nome", "")[:30], c, vero,
                                                                     estratto[c], esito))
    sotto = [c for c, d in campi.items() if d["estratti"] and d["giusti"] / d["estratti"] < 0.9]
    ESITO.write_text(json.dumps({"seme": SEME, "campi": campi, "sotto_90": sotto}, indent=1), encoding="utf-8")
    righe += ["", "| campo | estratti | giusti | precisione | non trovati | non determinabili |",
              "|---|---:|---:|---:|---:|---:|"]
    for c, d in campi.items():
        righe.append("| {} | {} | {} | {} | {} | {} |".format(
            c, d["estratti"], d["giusti"], "{:.1%}".format(d["giusti"] / d["estratti"]) if d["estratti"] else "—",
            d["non_trovati"], d["non_determinabili"]))
    righe += ["", "**Esito**: " + ("precisione sotto il 90% su: " + ", ".join(sotto) + " — FERMO."
                                   if sotto else "tutti i campi al 90% o sopra.")]
    DETTAGLIO.write_text("\n".join(righe) + "\n", encoding="utf-8")
    print("\n".join(righe[-9:]))
    return 1 if sotto else 0


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "campione":
        raise SystemExit(campione())
    if comando == "confronta":
        raise SystemExit(confronta())
    raise SystemExit("uso: verifica.py campione | confronta")
