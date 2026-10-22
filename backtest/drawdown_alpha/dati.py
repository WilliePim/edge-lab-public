"""Scarico e cache delle serie usate dai Test A, B, C -- FRED (tassi, spread) e Yahoo (indice).

Nessuna chiave richiesta per FRED: endpoint pubblico `fredgraph.csv`. Cache locale in `cache/`, un file per
serie, riusato se presente -- una sola chiamata di rete per serie per l'intera vita di questo studio, a meno di
cancellare la cache a mano per un refresh.

    python backtest/drawdown_alpha/dati.py
"""
from __future__ import annotations

import csv
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
# Nome ed email di chi scarica (richiesti da FRED e SEC), dall'ambiente come nel resto del repo.
USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "edge-lab research")

# id FRED -> (nome file, copertura attesa dichiarata in preregistrazione, verificata il 23/09/2026)
SERIE_FRED = {
    "DGS10": ("treasury_10a.csv", "1962-01-02"),
    "DGS3MO": ("treasury_3m.csv", "1981-09-01"),
    "DGS2": ("treasury_2a.csv", "1976-06-01"),
    "BAA10Y": ("spread_baa.csv", "1986-01-02"),
    "AAA10Y": ("spread_aaa.csv", "1983-01-03"),
}


def _scarica_fred(serie_id: str) -> str:
    req = urllib.request.Request(FRED_URL.format(id=serie_id), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fred(serie_id: str, *, forza: bool = False) -> list[tuple[str, float]]:
    """[(data ISO, valore)], righe senza valore (weekend/festivi FRED) escluse."""
    nome, attesa = SERIE_FRED[serie_id]
    path = CACHE / nome
    if forza or not path.exists():
        testo = _scarica_fred(serie_id)
        path.write_text(testo, encoding="utf-8")
    righe = []
    with path.open(encoding="utf-8") as f:
        for riga in csv.DictReader(f):
            v = riga.get(serie_id, "").strip()
            if v and v != ".":
                righe.append((riga["observation_date"], float(v)))
    if not righe:
        raise RuntimeError(f"{serie_id}: nessuna osservazione dopo il download -- fermarsi, non inventare dati")
    if righe[0][0][:4] > attesa[:4]:
        raise RuntimeError(
            f"{serie_id}: copertura reale inizia {righe[0][0]}, attesa da {attesa} -- la fonte e' cambiata "
            "rispetto a quanto verificato in preregistrazione, fermarsi prima di procedere"
        )
    return righe


def indice_gspc(*, forza: bool = False) -> list[tuple[str, float]]:
    """[(data ISO, chiusura)] di ^GSPC, storico massimo via yfinance (gia' dipendenza del repo)."""
    path = CACHE / "gspc.csv"
    if forza or not path.exists():
        import yfinance as yf

        h = yf.Ticker("^GSPC").history(period="max", interval="1d", auto_adjust=False)
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["data", "chiusura"])
            for idx, row in h.iterrows():
                w.writerow([idx.date().isoformat(), row["Close"]])
    righe = []
    with path.open(encoding="utf-8") as f:
        for riga in csv.DictReader(f):
            righe.append((riga["data"], float(riga["chiusura"])))
    if not righe:
        raise RuntimeError("^GSPC: nessuna osservazione dopo il download -- fermarsi, non inventare dati")
    return righe


if __name__ == "__main__":
    print("== FRED ==")
    for sid in SERIE_FRED:
        righe = fred(sid)
        print(f"{sid}: {len(righe)} osservazioni, {righe[0][0]} -> {righe[-1][0]}")
    print("== Yahoo ^GSPC ==")
    idx = indice_gspc()
    print(f"^GSPC: {len(idx)} sedute, {idx[0][0]} -> {idx[-1][0]}")
    sys.exit(0)
