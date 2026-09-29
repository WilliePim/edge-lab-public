"""E3, fasi 0 (punti 3-5), 1 e 4 — date, rotte / forti / intermedie, ingressi. **Nessun rendimento extra.**

Legge `universo.csv` (esclusioni senza testo) e `prospetti.jsonl` (campi del prospetto). Scrive
`state/backfill/ipo_e3/casi.csv`: una riga per IPO dell'universo, con l'esito di ogni passo e il motivo quando esce.

**Date** (pre-registrazione E3, fase 0 punto 4; ADR-049):
- *data di collocamento*: la data della copertina del prospetto; se la copertina non la dice, la seduta prima della
  prima barra (un'IPO si prezza la sera e scambia dal giorno dopo). Dove ci sono tutte e due si contano quelle che
  distano più di 5 sedute;
- *scadenza del lock-up*: data di collocamento + durata dichiarata, in giorni di calendario come la scrivono i
  prospetti («180 days after the date of this prospectus»), portata sulla prima seduta di borsa da quella data in poi
  (seduta S);
- *data di controllo*: S + 10 sedute.

**Classificazione** (fase 1), sulle chiusure rettificate per i frazionamenti (`serie_eodhd`, la `Close` di Yahoo) e
sul prezzo di collocamento riportato nelle stesse unità (diviso per i frazionamenti successivi al collocamento):
- *rotta*: chiusura alla data di controllo ≤ −30% dal prezzo di collocamento;
- *forte*: nessuna chiusura sotto il prezzo di collocamento dalla prima barra alla data di controllo;
- *intermedia*: tutte le altre, contate.
Servono almeno l'80% delle barre fra la prima barra e la data di controllo (la regola dell'80% del Russell): con
meno, una chiusura sotto il collocamento potrebbe mancare, e l'IPO esce contata.

**Ingressi** (fase 4), solo per le rotte, sulle sedute del calendario comune:
- *A*: la chiusura della prima seduta dopo la data di scadenza del lock-up;
- *B*: `russell_exits/ingressi.ingresso_b` con sessione di riferimento del volume e inizio del minimo = S, partenza
  dalla data di controllo (S + 10), finestra di 20 sedute, quindi primo giorno possibile S + 30 e ingresso forzato a
  S + 126 — la regola B della direttiva, parola per parola;
- *C*: S + 63.
Le forti entrano alla data di controllo.

    python backtest/ipo_e3/casi.py
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json
import math
import statistics

import comune as C

SOGLIA_ROTTA = -0.30
CONTROLLO = 10                     # sedute dopo la scadenza
B_FINESTRA, B_PRIMA, B_FORZATO = 20, 30, 126
C_SEDUTE = 63
COPERTURA = 0.8
STALE = 5                          # sedute di tolleranza per l'ultima barra disponibile, come nel Russell
DATA_INCOERENTE = 5                # sedute fra la data della copertina e la prima barra
COERENZA = (0.5, 3.0)              # prima chiusura / prezzo di collocamento (ADR-051)
#  Balzi veri del primo giorno sopra 3 volte, verificati a mano alla fermata 1 (ADR-051, decisione dell'utente): chiusura
#  grezza uguale alla rettificata, nessun frazionamento in archivio, volume da IPO. Dicerna, Code Rebel, BigCommerce.
ECCEZIONI_051 = frozenset({"0001399529", "0001613011", "0001626450"})
ORIZZONTI = (63, 126, 252)
PLACEBO_SPOSTAMENTO = 126

USCITA = C.STATO / "casi.csv"


def _nan(x) -> bool:
    return x is None or x != x


def come_lista(arr) -> list:
    return [None if _nan(x) else float(x) for x in arr]


def ultimo_prima(xs: list, s: int, stale: int = STALE) -> float | None:
    for i in range(s, max(-1, s - stale - 1), -1):
        if 0 <= i < len(xs) and xs[i] is not None:
            return xs[i]
    return None


def copertura(xs: list, a: int, b: int) -> float:
    if b < a:
        return 0.0
    tratto = xs[max(0, a):b + 1]
    return sum(1 for x in tratto if x is not None) / (b - a + 1)


def prospetti() -> dict[str, dict]:
    fuori = {}
    for riga in (C.STATO / "prospetti.jsonl").open(encoding="utf-8"):
        if riga.strip():
            d = json.loads(riga)
            fuori[d["cik"]] = d
    return fuori


def fattore_dopo(splits: list[tuple[str, float]], giorno: str) -> float:
    f = 1.0
    for d, s in splits:
        if d > giorno:
            f *= s
    return f


def valuta(r: dict, p: dict | None, ids: list[str], ser_di) -> dict:
    """Aggiorna e ritorna la riga del caso. `ser_di(codice)` dà (serie, codici seguiti)."""
    x = {k: r[k] for k in ("cik", "nome", "anno", "forma", "data_prospetto", "codice", "prima_barra", "mercato",
                           "costituita_fuori_usa")}
    x.update({"esito": "", "motivo": "", "lp_unita": "", "prezzo": "", "data_collocamento": "", "fonte_data": "",
              "data_incoerente": "", "lockup_giorni": "", "lockup_durate": "", "azioni_offerte": "",
              "azioni_dopo": "", "scadenza": "", "S": "", "controllo": "", "rendimento_controllo": "",
              "minimo_su_collocamento": "", "gruppo": "", "ingresso_A": "", "ingresso_B": "", "esito_B": "",
              "offset_B": "", "ingresso_C": "", "ingresso_forte": "", "seguiti": "", "ultima_barra": "",
              "rapporto_prima_chiusura": ""})
    if p is None or p.get("esito") != "letto":
        x["esito"], x["motivo"] = "fuori", "prospetto non letto ({})".format((p or {}).get("esito", "assente"))
        return x
    x["lp_unita"] = "sì" if p.get("lp_unita") else ""
    if p.get("motivo_testo"):
        x["esito"], x["motivo"] = "fuori", p["motivo_testo"]
        return x
    if p.get("lp_unita"):
        #  Decisione dell'utente alla fermata 1: le «common units» non sono azioni ordinarie (K-1, distribuzioni).
        x["esito"], x["motivo"] = "fuori", "società in accomandita o LLC con «common units»"
        return x
    x["prezzo"] = p["prezzo"]
    x["lockup_giorni"] = p.get("lockup_giorni") or ""
    x["lockup_durate"] = json.dumps(p.get("lockup_durate") or {}, sort_keys=True)
    x["azioni_offerte"], x["azioni_dopo"] = p.get("azioni_offerte") or "", p.get("azioni_dopo") or ""
    if not r["codice"]:
        x["esito"], x["motivo"] = "fuori", "senza serie di prezzi entro 10 sedute"
        return x
    #  data di collocamento
    i_barra = bisect.bisect_left(ids, r["prima_barra"])
    if p.get("data_copertina"):
        x["data_collocamento"], x["fonte_data"] = p["data_copertina"], "copertina"
        dist = i_barra - bisect.bisect_left(ids, p["data_copertina"])
        x["data_incoerente"] = "sì" if abs(dist) > DATA_INCOERENTE else ""
    else:
        x["data_collocamento"], x["fonte_data"] = ids[i_barra - 1], "seduta prima della prima barra"
    if not p.get("lockup_giorni"):
        x["esito"], x["motivo"] = "fuori", "durata del lock-up non trovata"
        return x
    scad = (dt.date.fromisoformat(x["data_collocamento"]) + dt.timedelta(days=int(p["lockup_giorni"]))).isoformat()
    s = bisect.bisect_left(ids, scad)
    x["scadenza"] = scad
    if s + CONTROLLO >= len(ids):
        x["esito"], x["motivo"] = "fuori", "data di controllo oltre l'archivio"
        return x
    x["S"], x["controllo"] = ids[s], ids[s + CONTROLLO]
    ser, seguiti = ser_di(r["codice"])
    if ser is None:
        x["esito"], x["motivo"] = "fuori", "serie non caricata"
        return x
    close, _adj, vol, splits, ultima = ser
    close, vol = come_lista(close), come_lista(vol)
    x["seguiti"], x["ultima_barra"] = seguiti or "", ultima
    c = s + CONTROLLO
    if ultima < ids[c]:
        x["esito"], x["motivo"] = "fuori", "serie finita prima della data di controllo"
        return x
    if copertura(close, i_barra, c) < COPERTURA:
        x["esito"], x["motivo"] = "fuori", "meno dell'80% di barre fra la prima barra e il controllo"
        return x
    #  Solo i frazionamenti dopo la prima barra: uno con data alla prima barra (o prima) è il raggruppamento fatto
    #  prima dell'IPO, già dentro il prezzo del prospetto (William Lyon Homes, Nevro; ADR-052).
    offerta = float(p["prezzo"]) / fattore_dopo(splits, r["prima_barra"])
    #  Coerenza della serie (ADR-051): la prima chiusura deve stare fra 0,5 e 3 volte il prezzo di collocamento, sulle
    #  stesse grandezze della classificazione. Fuori, la serie non è quella dell'IPO (un titolo diverso con lo stesso
    #  ticker) o è già rettificata dal fornitore per frazionamenti successivi e qui lo sarebbe due volte.
    prima = next((v for v in close[i_barra:i_barra + STALE + 1] if v is not None), None)
    x["rapporto_prima_chiusura"] = round(prima / offerta, 4) if prima else ""
    if prima is None or (not (COERENZA[0] <= prima / offerta <= COERENZA[1]) and r["cik"] not in ECCEZIONI_051):
        x["esito"], x["motivo"] = "fuori", "prima chiusura incoerente con il prezzo di collocamento"
        return x
    cc = ultimo_prima(close, c)
    if cc is None:
        x["esito"], x["motivo"] = "fuori", "nessuna chiusura alla data di controllo"
        return x
    minimo = min(v for v in close[i_barra:c + 1] if v is not None)
    x["rendimento_controllo"] = round(cc / offerta - 1.0, 6)
    x["minimo_su_collocamento"] = round(minimo / offerta - 1.0, 6)
    x["esito"] = "classificata"
    if cc / offerta - 1.0 <= SOGLIA_ROTTA:
        x["gruppo"] = "rotta"
    elif minimo >= offerta:
        x["gruppo"] = "forte"
        x["ingresso_forte"] = ids[c]
        return x
    else:
        x["gruppo"] = "intermedia"
        return x
    #  ingressi delle rotte
    import ingressi as I                                 # backtest/russell_exits/ingressi.py
    a = bisect.bisect_right(ids, scad)
    x["ingresso_A"] = ids[a] if a < len(ids) else ""
    t, esito = I.ingresso_b(close, vol, k=s, p=s, r=s + CONTROLLO, n=B_FINESTRA, limite=B_FORZATO - CONTROLLO)
    x["esito_B"] = esito
    if t is not None:
        x["ingresso_B"], x["offset_B"] = ids[t], t - s
    x["ingresso_C"] = ids[s + C_SEDUTE] if s + C_SEDUTE < len(ids) else ""
    return x


def main() -> int:
    import serie_eodhd as SE                             # backtest/russell_exits/serie_eodhd.py
    ids = C.ids()
    righe = [r for r in csv.DictReader((C.STATO / "universo.csv").open(encoding="utf-8")) if not r["motivo"]]
    pr = prospetti()
    SE.carica([r["codice"] for r in righe if r["codice"]], ids)
    fuori = [valuta(r, pr.get(r["cik"]), ids, lambda cod: SE.serie_seguita(cod, ids)) for r in righe]
    campi = list(fuori[0].keys())
    with USCITA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campi)
        w.writeheader()
        w.writerows(fuori)
    per_motivo = collections.Counter(x["motivo"] or x["gruppo"] for x in fuori)
    print(json.dumps(per_motivo.most_common(), ensure_ascii=False, indent=1))
    rotte = [x for x in fuori if x["gruppo"] == "rotta"]
    off = sorted(int(x["offset_B"]) for x in rotte if x["offset_B"] != "")
    if off:
        print("offset B:", len(off), "primo possibile", sum(1 for o in off if o == B_PRIMA), "forzati",
              sum(1 for x in rotte if x["esito_B"] == "FORZATO"), "quartili", statistics.quantiles(off, n=4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
