"""L'esito dell'ultimo giro, in un file che una macchina puo' leggere.

PERCHE' ESISTE. Il report finisce in una cartella che nessuno apre e nessuno
avvisa che c'e'. Uno scheduler che lancia lo scanner ne cattura l'output,
quindi anche cio' che il giro stampa non lo vede nessuno fino alla fine. Il risultato e' che quindici nomi da leggere restano su un disco
senza che nulla lo dica.

Questo file e' l'aggancio per chi vuole dirlo: una notifica, un collegamento,
un'altra macchina. Non decide niente e non notifica niente lui stesso -- scrive
dei fatti e se ne va.

COSA NON E'. Non e' l'archivio: `state/observations/` e' append-only e conserva
tutto, questo si RISCRIVE a ogni giro e contiene solo l'ultimo. Perdere questo
file non perde nulla, si rifa' al giro dopo.

Un percorso qui e' ASSOLUTO, apposta: chi lo legge -- uno script di notifica,
un collegamento sul desktop -- non gira necessariamente nella cartella del
repository, e un percorso relativo lo obbligherebbe a indovinare da dove.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

PATH = ("daily", "last_run.json")


def _watch_hits_today(state_dir, run_date: date) -> int:
    """Quante sorveglianze hanno scattato in questo giro.

    Si conta dal registro invece di farsi passare il numero: il registro e' un
    fatto gia' scritto su disco, e chiederlo al report significherebbe
    cambiare la firma di chi lo produce per un dato che si puo' leggere.
    """
    p = Path(state_dir) / "watch" / "seen.jsonl"
    if not p.exists():
        return 0
    iso = run_date.isoformat()
    n = 0
    for line in p.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            if json.loads(line).get("first_seen") == iso:
                n += 1
        except ValueError:
            continue
    return n


def write(state_dir, run_date: date, *, report=None, spinoff_watch=None,
          verdicts=None, csv=None, new=None, repeat=None,
          issuers_evaluated=None, seconds=None, missing_index=None,
          sha: str = "", status: str = "ok") -> Path:
    """Scrive `state/daily/last_run.json`. Ritorna il percorso."""
    from . import secdays

    st = Path(state_dir)
    out = st.joinpath(*PATH)
    out.parent.mkdir(parents=True, exist_ok=True)

    groups = secdays.classify(missing_index or [], run_date)

    def abspath(p):
        return str(Path(p).resolve()) if p else None

    doc = {
        "run_date": run_date.isoformat(),
        "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scanner_git_sha": sha,
        "status": status,
        #  I file che una persona apre.
        "report": abspath(report),
        "spinoff_watch": abspath(spinoff_watch),
        "verdicts": abspath(verdicts),
        "csv": abspath(csv),
        #  I numeri che stanno in una notifica di due righe.
        "new": new,
        "repeat": repeat,
        "issuers_evaluated": issuers_evaluated,
        "seconds": round(seconds, 1) if seconds is not None else None,
        "watch_hits": _watch_hits_today(st, run_date),
        #  Solo i buchi VERI: un festivo non e' una cosa di cui avvisare.
        "index_unreadable": [d for d, _ in groups[secdays.ILLEGGIBILE]],
        "index_not_filing_day": [
            {"date": d, "reason": w}
            for d, w in groups[secdays.FESTIVO] + groups[secdays.CHIUSURA]
        ],
    }
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    return out


def read(state_dir):
    """L'ultimo giro, o None se non c'e'."""
    p = Path(state_dir).joinpath(*PATH)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def summary(doc) -> str:
    """Una riga sola, per una notifica o un log. Fatti, nessun aggettivo."""
    if not doc:
        return "nessun giro registrato"
    bits = []
    if doc.get("new") is not None:
        bits.append("{} nuovi".format(doc["new"]))
    if doc.get("repeat") is not None:
        bits.append("{} gia' visti".format(doc["repeat"]))
    if doc.get("issuers_evaluated") is not None:
        bits.append("{} valutati".format(doc["issuers_evaluated"]))
    line = " · ".join(bits)
    if doc.get("watch_hits"):
        line += " · SORVEGLIANZA: {}".format(doc["watch_hits"])
    unread = doc.get("index_unreadable") or []
    if unread:
        line += " · {} giorni non osservati".format(len(unread))
    return line
