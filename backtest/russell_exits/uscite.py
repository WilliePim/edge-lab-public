"""Russell 2000, uscite verso il basso — definizione dell'addendum 1 (decisione dell'utente del 17 settembre).

**Uscita verso il basso** = in IWM nell'istantanea «prima» (31 marzo) e, nell'istantanea «dopo», assente oppure con al
massimo il 50% delle azioni di marzo, e non in IWB. Le azioni si confrontano **rettificate per frazionamenti e
raggruppamenti** avvenuti fra le due date (tabella dei frazionamenti della serie di prezzi del titolo); se la rettifica
non è possibile (nessuna serie), si confronta la **quota del capitale detenuta da IWM** (azioni di IWM / azioni in
circolazione XBRL alla data più vicina). **Quota residua** = azioni dopo / azioni prima, rettificate: dato descrittivo,
non entra nei filtri né nel verdetto.

Funzioni pure, testate in `test_uscite.py`.
"""
from __future__ import annotations

SOGLIA_RESIDUA = 0.5


def fattore_split(split, da, a):
    """Prodotto dei frazionamenti con data in (da, a]: 2.0 per un 2:1, 0.1 per un raggruppamento 1:10."""
    f = 1.0
    for d, s in split or ():
        if da < d <= a and s and s > 0:
            f *= s
    return f


def quota_residua(azioni_prima, azioni_dopo, split=None, da="", a="", quota_capitale=None):
    """(quota, metodo). Metodo: "assente", "azioni rettificate", "quota del capitale", o None se non calcolabile."""
    if not azioni_dopo:
        return 0.0, "assente"
    if split is not None:
        f = fattore_split(split, da, a)
        if azioni_prima and f > 0:
            return azioni_dopo / (azioni_prima * f), "azioni rettificate"
    if quota_capitale is not None:
        q_prima, q_dopo = quota_capitale
        if q_prima and q_prima > 0 and q_dopo is not None:
            return q_dopo / q_prima, "quota del capitale"
    return None, None


def classifica(in_iwm_dopo, in_iwb_dopo, quota):
    """"basso", "alto", "rimasto" o None (quota non calcolabile per un titolo ancora presente)."""
    if in_iwb_dopo:
        return "alto"
    if not in_iwm_dopo:
        return "basso"
    if quota is None:
        return None
    return "basso" if quota <= SOGLIA_RESIDUA else "rimasto"
