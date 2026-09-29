"""Il verdetto diluizione, point-in-time, per ogni evento dello storico.

PERCHE' UN CLIENT CHE NASCONDE IL FUTURO, invece di correggere `dilution.py`.

`check_dilution` accetta un `as_of`, ma due cose al suo interno guardano oltre:

  * `_all_filings` restituisce TUTTI i depositi dell'emittente, e le liste
    `takedowns_after` / `takedowns_before` non sono tagliate ad `as_of`: un
    424B depositato dopo la data di valutazione entrerebbe nel verdetto;
  * `_share_facts` filtra su `end <= as_of`, cioe' sulla data di CHIUSURA del
    periodo contabile, non su `filed`. Un 10-Q con `end` a marzo ma depositato
    a maggio risulterebbe visibile a marzo. E' il difetto gia' scritto in
    CLAUDE.md — «il percorso live filtra su `end`, non su `filed`».

Un veto che vede il futuro invaliderebbe il run. Correggere `dilution.py`
cambierebbe pero' il comportamento della pipeline viva, che non e' quello che
questo strumento deve fare. Quindi il taglio sta QUI: un client che avvolge
quello vero e restituisce solo cio' che esisteva alla data. `check_dilution`
resta identico e diventa point-in-time per costruzione, perche' non ha modo di
vedere altro.

Ogni riga di output porta `as_of`, e la regola con cui e' stata prodotta:
depositi con `filingDate <= as_of`, fatti XBRL con `filed <= as_of`.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from form4_scanner.dilution import check_dilution
from form4_scanner.edgar import EdgarClient

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "backfill"
CORPUS = STATE / "form4_raw"
OUT = STATE / "dilution.jsonl"
CKPT = STATE / "dilution_checkpoint.json"

SHARE_TAGS = ("EntityCommonStockSharesOutstanding",)


class PointInTime:
    """Il client vero, con una benda sugli occhi alla data `as_of`."""

    def __init__(self, inner, as_of: date):
        self.inner = inner
        self.as_of = as_of.isoformat()
        self._sub = None
        self._cc = {}

    #  --- cio' che dilution.py usa davvero -------------------------------
    def submissions(self, cik):
        raw = self.inner.submissions(cik)
        if not raw:
            return raw
        return self._trim_submissions(raw)

    def get_json(self, url):
        raw = self.inner.get_json(url)
        if not raw:
            return raw
        if "/submissions/" in url:
            return self._trim_submissions(raw)
        if "companyconcept" in url:
            return self._trim_concept(raw)
        return raw

    def company_concept(self, cik, taxonomy, tag):
        raw = self.inner.company_concept(cik, taxonomy, tag)
        return self._trim_concept(raw) if raw else raw

    #  --- il taglio -------------------------------------------------------
    def _trim_submissions(self, raw):
        out = json.loads(json.dumps(raw)) if not isinstance(raw, dict) else dict(raw)
        fil = (out.get("filings") or {}).get("recent") or {}
        dates = fil.get("filingDate") or []
        keep = [i for i, d in enumerate(dates) if d and d <= self.as_of]
        trimmed = {k: [v[i] for i in keep] for k, v in fil.items()
                   if isinstance(v, list) and len(v) == len(dates)}
        out["filings"] = {"recent": trimmed, "files": []}
        return out

    def _trim_concept(self, raw):
        units = {}
        for unit, arr in (raw.get("units") or {}).items():
            #  `filed`, non `end`: e' la data in cui il numero e' diventato
            #  pubblico, ed e' l'unica che un backtest possa usare.
            units[unit] = [r for r in arr
                           if r.get("filed") and r["filed"] <= self.as_of]
        out = dict(raw)
        out["units"] = units
        return out


def load_events():
    """(issuer_cik, as_of, ultimo acquisto) -- as_of = data di deposito."""
    by = {}
    for f in sorted(CORPUS.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                cik, filed = (r.get("issuer_cik") or "").lstrip("0"), r.get("filed_date")
                td = r.get("transaction_date")
                if not cik or not filed or not td:
                    continue
                k = (cik, filed)
                cur = by.get(k)
                if cur is None or td > cur:
                    by[k] = td
    return sorted((c, f, t) for (c, f), t in by.items())


def main() -> int:
    ua = " ".join(sys.argv[1:])
    if not ua:
        raise SystemExit('uso: backfill_dilution.py "Nome Cognome email@dominio"')
    client = EdgarClient(ua)

    events = load_events()
    done = set()
    if CKPT.exists() and OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            done.add((r["issuer_cik"], r["as_of"]))
    print("eventi: {:,}   gia' fatti: {:,}".format(len(events), len(done)), flush=True)

    fh = OUT.open("a", encoding="utf-8")
    n = 0
    last_cik = None
    for cik, as_of, last_buy in events:
        if (cik, as_of) in done:
            continue
        pit = PointInTime(client, date.fromisoformat(as_of))
        try:
            rep = check_dilution(pit, cik, date.fromisoformat(last_buy),
                                 as_of=date.fromisoformat(as_of))
            row = {"issuer_cik": cik, "as_of": as_of, "last_buy": last_buy,
                   "verdict": rep.verdict, "blocked": bool(rep.blocked),
                   "shares_growth_pct": rep.shares_growth_pct,
                   "reasons": list(rep.reasons)}
        except Exception as e:                                  # noqa: BLE001
            row = {"issuer_cik": cik, "as_of": as_of, "last_buy": last_buy,
                   "verdict": "ERROR", "blocked": False, "error": str(e)[:120]}
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        n += 1
        if cik != last_cik:
            last_cik = cik
        if n % 500 == 0:
            fh.flush()
            CKPT.write_text(json.dumps({"done": n + len(done)}), encoding="utf-8")
            print("  {:,}/{:,}  (rete {:,}, cache {:,})".format(
                n + len(done), len(events), client.stats["network"],
                client.stats["cache"]), flush=True)
    fh.close()
    CKPT.write_text(json.dumps({"done": n + len(done)}), encoding="utf-8")
    print("\nscritto {}  ({:,} righe nuove)".format(OUT, n))
    print("EDGAR: {:,} di rete, {:,} dalla cache".format(
        client.stats["network"], client.stats["cache"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
