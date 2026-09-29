"""E3, fase 0 — l'universo delle IPO dagli indici EDGAR, con le esclusioni che si decidono senza aprire il prospetto.

Regole (pre-registrazione E3, fase 0, punto 1; ADR-047):

1. **Candidati**: ogni CIK con un 424B4 o 424B1 depositato fra il 2012 e il 2024 (indici trimestrali `form.idx`). Il
   424B3 entra solo per i CIK che nella finestra non hanno né 424B4 né 424B1, e solo se cade vicino alla prima barra
   (punto 3): il 424B3 è quasi sempre un prospetto di rivendita, e l'IPO vera la dice il prospetto (`prospetto.py`,
   prezzo di collocamento dichiarato).
2. **Quale prospetto è l'IPO**: fra quelli del CIK, il primo che ha una prima barra di azioni ordinarie nell'archivio
   entro 10 sedute (prima o dopo: il 424B4 si deposita di solito il giorno dopo il prezzo, quando il titolo già
   scambia). Se nessuno ce l'ha, il primo del CIK nella finestra, e l'IPO si conta «senza serie».
3. **Classe già quotata** (offerta secondaria scambiata per IPO): il CIK ha, nell'archivio EODHD, un codice di azioni
   ordinarie con barre più di 10 sedute prima del prospetto **e ancora scambiato** entro 10 sedute dal prospetto. Vale
   anche per il passaggio da fuori borsa a una borsa. Una classe ferma da anni (una società tornata privata e
   riquotata) non conta: «ha già», al presente.
4. **Esclusioni dalle submissions della SEC** (zip in blocco, nessuna chiamata), nell'ordine, ciascuna contata:
   SPAC (SIC 6770), REIT (SIC 6798), banche e casse di risparmio (SIC 6021, 6022, 6029, 6035, 6036), fondi chiusi
   (un deposito N-2 del CIK), emittenti esteri o ADR (un F-1, F-6, 20-F, 40-F o 6-K del CIK prima o nell'anno dopo
   il prospetto: l'emittente privato estero come lo definisce la SEC), entità non operative (tipo di entità diverso
   da «operating»: co-registranti e garanti di prestiti obbligazionari). Le società costituite fuori dagli Stati
   Uniti che depositano come domestiche (10-K, 10-Q: Ambarella, Cayman) **restano** e si contano a parte.
   Le esclusioni che richiedono il testo — unit, prezzo sotto $5, fiducia in trust dichiarata, REIT dichiarato —
   stanno in `prospetto.py`.
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json

import comune as C
import bulk

FORME_IPO = ("424B4", "424B1")
SEDUTE_PRIMA_BARRA = 10
SIC_ESCLUSI = {"6770": "SPAC (SIC 6770)", "6798": "REIT (SIC 6798)",
               **{s: "banca o cassa di risparmio (SIC {})".format(s) for s in ("6021", "6022", "6029", "6035", "6036")}}
FORME_FONDO = ("N-2", "N-2/A", "N-2ASR")
FORME_ESTERO = ("F-1", "F-1/A", "F-6", "20-F", "40-F", "20-F/A", "40-F/A", "6-K")
STATI_USA = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND "
                "OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR".split())
USCITA = C.STATO / "universo.csv"


def codici_per_cik() -> dict[str, list[tuple[str, str, str, str]]]:
    """CIK a 10 cifre -> [(codice, prima barra, ultima barra, mercato)] delle azioni ordinarie americane."""
    from market_data import api
    df = api.listings(exchange="US")
    fuori = collections.defaultdict(list)
    for code, cik, tipo, fd, ld, venue in zip(df["code"], df["cik"], df["type"], df["first_date"], df["last_date"],
                                             df["venue"]):
        if cik and tipo == "Common Stock" and fd is not None and fd == fd:
            fuori[str(cik).zfill(10)].append((code, str(fd)[:10], str(ld)[:10], venue or ""))
    return fuori


def distanza(ids: list[str], a: str, b: str) -> int:
    """Sedute da a a b (negativo se b viene prima)."""
    return bisect.bisect_left(ids, b) - bisect.bisect_left(ids, a)


def costruisci() -> list[dict]:
    ids = C.ids()
    righe = C.righe_indice(FORME_IPO + ("424B3",))
    per_cik = collections.defaultdict(list)
    for forma, cik, data, nome, percorso in righe:
        per_cik[cik].append((data, forma, nome, percorso))
    codici = codici_per_cik()
    fuori = []
    for cik, dep in per_cik.items():
        dep.sort()
        ipo = [x for x in dep if x[1] in FORME_IPO]
        tre = [x for x in dep if x[1] == "424B3"]
        cod = codici.get(cik, [])

        def vicino(x):
            m = [(abs(distanza(ids, x[0], c[1])), distanza(ids, x[0], c[1]), c) for c in cod]
            m = [z for z in m if z[0] <= SEDUTE_PRIMA_BARRA]
            return min(m, key=lambda z: (z[0], z[2][1]))[1:] if m else None

        scelti = [(x, vicino(x)) for x in ipo] or [(x, vicino(x)) for x in tre if vicino(x)]
        if not scelti:
            continue
        con_serie = [(x, v) for x, v in scelti if v]
        x, v = con_serie[0] if con_serie else scelti[0]
        data = x[0]
        prima = [c for c in cod if distanza(ids, c[1], data) > SEDUTE_PRIMA_BARRA
                 and distanza(ids, c[2], data) <= SEDUTE_PRIMA_BARRA]
        r = {"cik": cik, "nome": x[2], "forma": x[1], "data_prospetto": data, "percorso_indice": x[3],
             "anno": int(data[:4]), "prospetti_nella_finestra": len(ipo) or len(tre),
             "codice": v[1][0] if v else "", "prima_barra": v[1][1] if v else "", "distanza_sedute": v[0] if v else "",
             "mercato": v[1][3] if v else "", "motivo": ""}
        if prima:
            r["motivo"] = "classe già quotata ({} dal {})".format(prima[0][0], prima[0][1])
        fuori.append(r)
    for r in fuori:
        if not r["motivo"]:
            r["motivo"] = motivo_submissions(r["cik"], r["data_prospetto"])
        r["sic"] = _sic.get(r["cik"], "")
        r["stato_costituzione"] = _stato.get(r["cik"], "")
        r["costituita_fuori_usa"] = bool(r["stato_costituzione"]) and r["stato_costituzione"] not in STATI_USA
    fuori.sort(key=lambda r: (r["data_prospetto"], r["cik"]))
    return fuori


_sic: dict[str, str] = {}


def motivo_submissions(cik: str, data: str) -> str:
    testa, dep = bulk.submissions(cik)
    if testa is None:
        return ""                                        # senza submissions: nessuna esclusione da qui (contato)
    sic = str(testa.get("sic") or "")
    _sic[cik] = sic
    stato = (testa.get("stateOfIncorporation") or "").upper()
    _stato[cik] = stato
    if sic in SIC_ESCLUSI:
        return SIC_ESCLUSI[sic]
    if any(f in FORME_FONDO for _d, f, *_ in dep):
        return "fondo chiuso (N-2)"
    limite = (dt.date.fromisoformat(data) + dt.timedelta(days=365)).isoformat()
    if any(f in FORME_ESTERO and d <= limite for d, f, *_ in dep):
        return "emittente estero o ADR"
    if (testa.get("entityType") or "operating") != "operating":
        return "entità non operativa (co-registrante o garante)"
    return ""


_stato: dict[str, str] = {}


if __name__ == "__main__":
    C.STATO.mkdir(parents=True, exist_ok=True)
    tutte = costruisci()
    campi = ["cik", "nome", "forma", "data_prospetto", "anno", "prospetti_nella_finestra", "codice", "prima_barra",
             "distanza_sedute", "mercato", "sic", "stato_costituzione", "costituita_fuori_usa", "motivo", "percorso_indice"]
    with USCITA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campi, extrasaction="ignore")
        w.writeheader()
        w.writerows(tutte)
    per_motivo = collections.Counter(r["motivo"].split(" (")[0] if r["motivo"].startswith("classe") else r["motivo"]
                                     for r in tutte)
    print(len(tutte), "CIK con prospetto;", json.dumps(per_motivo.most_common(), ensure_ascii=False))
    restano = [r for r in tutte if not r["motivo"]]
    print("restano", len(restano), "per anno", dict(sorted(collections.Counter(r["anno"] for r in restano).items())))
    print("  con serie", sum(1 for r in restano if r["codice"]), "senza", sum(1 for r in restano if not r["codice"]))
