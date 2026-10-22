"""Identificazione degli episodi di drawdown su ^GSPC -- definizione comune ai Test A, B, C.

Picco: massimo mobile (nessun guardare avanti). Un nuovo massimo storico chiude l'episodio precedente e ne apre
uno nuovo. Un episodio e' "qualificante" se il ribasso dal picco raggiunge almeno il 15% prima del prossimo
massimo storico. Il fondo e' la seduta di minimo nell'intervallo; se non e' ancora arrivato un nuovo massimo
alla fine della serie, l'episodio resta aperto (`recupero=None`, "recupero non ancora confermato").

    python backtest/drawdown_alpha/episodi.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dati import indice_gspc  # noqa: E402

SOGLIA_DRAWDOWN = 0.15


@dataclass(frozen=True, slots=True)
class Episodio:
    picco_data: str
    picco_valore: float
    fondo_data: str
    fondo_valore: float
    recupero_data: str | None  # None = non ancora recuperato alla fine della serie
    drawdown: float            # frazione positiva, es. 0.23 = -23%


def episodi_drawdown(righe: list[tuple[str, float]] | None = None,
                      soglia: float = SOGLIA_DRAWDOWN) -> list[Episodio]:
    righe = righe if righe is not None else indice_gspc()
    out: list[Episodio] = []
    picco_data, picco_val = righe[0]
    fondo_data, fondo_val = righe[0]
    for data, val in righe[1:]:
        if val >= picco_val:
            # nuovo massimo storico: chiude l'episodio corrente se qualificante
            dd = 1.0 - fondo_val / picco_val
            if dd >= soglia:
                out.append(Episodio(picco_data, picco_val, fondo_data, fondo_val, data, dd))
            picco_data, picco_val = data, val
            fondo_data, fondo_val = data, val
        elif val < fondo_val:
            fondo_data, fondo_val = data, val
    # ultimo intervallo, mai recuperato entro la fine della serie
    dd = 1.0 - fondo_val / picco_val
    if dd >= soglia:
        out.append(Episodio(picco_data, picco_val, fondo_data, fondo_val, None, dd))
    return out


if __name__ == "__main__":
    ep = episodi_drawdown()
    print(f"{len(ep)} episodi con drawdown >= {SOGLIA_DRAWDOWN:.0%} su ^GSPC, 1927-2026\n")
    for e in ep:
        rec = e.recupero_data or "non ancora recuperato"
        print(f"picco {e.picco_data} ({e.picco_valore:,.2f}) -> fondo {e.fondo_data} "
              f"({e.fondo_valore:,.2f}, -{e.drawdown:.1%}) -> recupero {rec}")
    sys.exit(0)
