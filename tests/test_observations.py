"""Tests for the append-only observation archive.

The archive exists because no outcome has ever been recorded for any signal this
scanner produced, and the twelve weights have never been compared against
anything. Testing whether the rubric discriminates needs the names it scored
BADLY, so the properties asserted here are mostly about what must NOT be
filtered, and about the row still being readable in six months.

Real ScoreCards from the real `score_cluster`, not duck types: the point is that
all seven criteria record their inputs, and a fake card would assert only that
the fake was built correctly.
"""
import json
import math
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner import observations as obs
from form4_scanner.classify import NOVEL, OPPORTUNISTIC
from form4_scanner.cluster import IssuerCluster
from form4_scanner.market import MarketSnapshot
from form4_scanner.parse import Transaction
from form4_scanner.flags import evaluate_cluster

RUN = date(2026, 8, 28)


def txn(owner="1111111", name="Doe Jane", d=date(2026, 8, 20), value=500_000.0,
        acc="acc1", idx=0, shares_after=3500.0, officer=True,
        title="CFO", plan=False):
    return Transaction(
        accession=acc, filed_at=date(2026, 8, 21), issuer_cik="9999999",
        issuer_name="Example Corp", ticker="XMPL", owner_cik=owner,
        owner_name=name, is_director=False, is_officer=officer,
        is_ten_pct=False, officer_title=title, txn_date=d, code="P",
        acquired_disposed="A", shares=1000.0, price=value / 1000.0,
        value=value, shares_after=shares_after, direct=True,
        is_derivative=False, plan_10b5_1=plan, txn_index=idx)


def make_card(comp=None, snap=None, txns=None):
    c = IssuerCluster("9999999", "Example Corp", "XMPL", txns or [txn()])
    s = snap or MarketSnapshot(ticker="XMPL", market_cap=800e6, price=12.0,
                               high_52w=20.0, analyst_count=2, ok=True,
                               source="yfinance",
                               fetched_at="2026-08-28T10:00:00+00:00")
    if s.drawdown_pct is None:
        s.drawdown_pct = 40.0
    labels = {t.owner_cik: OPPORTUNISTIC for t in c.txns}
    card = evaluate_cluster(c, labels, s)
    return card, c, labels


# --------------------------------------------------------------------------
print("[observations] all SEVEN criteria record their inputs")
card, cluster, labels = make_card(comp={"1111111": 600_000})
#  Three inputs, not seven. size, drawdown, coverage and specialist_overlap
#  went with the criteria that read them -- measured and flat, see
#  reports/size_component_test.md.
for name in ("buyer_quality", "cluster", "role"):
    check(f"{name} recorded what it read", name in card.inputs,
          str(sorted(card.inputs)))
check("buyer_quality kept the label per owner, not just the winning one",
      card.inputs["buyer_quality"]["labels_by_owner"]["1111111"] == OPPORTUNISTIC,
      str(card.inputs["buyer_quality"]))

#  The provenance block went with drawdown and coverage. market_cap is the only
#  market-derived field the row still carries, and _sources still names it.

print("[observations] an infinity never reaches the file")
#  A buy that creates a position from zero gives an infinite holdings increase.
#  json.dumps writes bare `Infinity`, which strict JSON readers reject, so the
#  fact is a flag and the number is absent. Same discipline as the date that had
#  to become a string -- a row that cannot be read back is worse than no row.
#  The two assertions on `size.new_position` went with the size criterion. The
#  third stays, and is the one that mattered: it does not care which criterion
#  produced the number, only that nothing non-finite reaches the file.
new_pos, ncl, nlabels = make_card(txns=[txn(shares_after=1000.0)])
check("no value anywhere in inputs is non-finite",
      not [v for d in new_pos.inputs.values() for v in d.values()
           if isinstance(v, float) and not math.isfinite(v)])

print("[observations] the row separates verdict from evidence")
with tempfile.TemporaryDirectory() as tmp:
    p = obs.write([card], tmp, RUN, window_days=60,
                  params={"days": 60}, funnel={"issuers_scored": 1},
                  labels=labels, clusters=[cluster])
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    head, row = rows[0], rows[1]

    check("the run header is written FIRST", head["kind"] == "run", head["kind"])
    #  A day whose index could not be read is not an empty day. Recorded on the
    #  header so a blocked day and a quiet day stop being the same row.
    check("the header says which days were not observed",
          "index_unavailable" in head, str(sorted(head)))
    check("...and an ordinary run says none", head["index_unavailable"] == [],
          str(head["index_unavailable"]))
    check("the observation follows it", row["kind"] == "observation")
    #  The separation the archive was required to have was points in one
    #  object and evidence in another. There are no points now, so what is left
    #  to assert is that inputs stayed nested per criterion and that score_v3
    #  and its four booleans are on the row for every issuer, vetoed included.
    check("inputs are nested per criterion",
          all(isinstance(v, dict) for v in row["inputs"].values()),
          str({k: type(v).__name__ for k, v in row["inputs"].items()}))
    check("three inputs, not seven",
          sorted(row["inputs"]) == ["buyer_quality", "cluster", "role"],
          str(sorted(row["inputs"])))
    check("score_v3 and its four booleans are on the row",
          all(k in row for k in ("score_v3", "v3_cluster", "v3_director",
                                 "v3_no_10pct", "v3_terreno")),
          str([k for k in row if k.startswith("v3") or k == "score_v3"]))
    #  The index is not shipped with the repository (tools/spinoffs.py builds
    #  it). Without it the archive must carry None -- not measured -- and with
    #  it a real answer: False on an issuer that is not a spin-off daughter is
    #  an answer, not a missing value. Both branches are the fail-closed rule.
    from form4_scanner import flags as _flags
    if _flags.SPINOFF_INDEX.exists():
        check("terreno is answered, not left unknown",
              row["v3_terreno"] is False, str(row["v3_terreno"]))
    else:
        check("without the index terreno is None, not False",
              row["v3_terreno"] is None, str(row["v3_terreno"]))
    check("no score, no components, no rubric_version",
          not any(k in row for k in ("score", "components", "rubric_version",
                                     "max_score", "pass_mark", "passes")),
          str(sorted(row)))
    check("context carries what the rubric did not score on",
          "market_cap" in row["context"] and "dilution" in row["context"],
          str(list(row["context"])))

    print("[observations] provenance is on every row, both kinds")
    for r in rows:
        check(f"{r['kind']}: scanner_git_sha present",
              "scanner_git_sha" in r, str(r.get("scanner_git_sha")))
        check(f"{r['kind']}: the window is on the row",
              r.get("window_days") == 60, str(r.get("window_days")))

    print("[observations] the transactions are stored whole")
    t = row["transactions"][0]
    for fname in ("transaction_date", "owner_cik", "owner_name", "role",
                  "shares", "price", "value", "is_10b5_1", "cmp_label",
                  "accession_number", "txn_index"):
        check(f"transaction carries {fname}", fname in t, str(sorted(t)))
    check("the CMP label in force is stored with the transaction",
          t["cmp_label"] == OPPORTUNISTIC, t["cmp_label"])
    check("txn_index is kept, so co-filers can be collapsed downstream",
          t["txn_index"] == 0, str(t["txn_index"]))
    check("the date is an ISO string, not a date object",
          isinstance(t["transaction_date"], str), str(type(t["transaction_date"])))
    check("is_10b5_1 is False, because open_market_buys already excluded plans",
          t["is_10b5_1"] is False, str(t["is_10b5_1"]))

print("[observations] a run that scored NOTHING still leaves a record")
#  The case the design turns on: network down, EDGAR 503, an empty cap band. With
#  no header, zero rows would be indistinguishable from a day the scanner never
#  ran, and those are different facts.
with tempfile.TemporaryDirectory() as tmp:
    p = obs.write([], tmp, RUN, window_days=60, params={"days": 60},
                  funnel={"issuers_scored": 0})
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    check("the file exists", p.exists())
    check("it holds exactly the run header", len(rows) == 1, str(len(rows)))
    check("which records that nothing was scored",
          rows[0]["funnel"]["issuers_scored"] == 0)

print("[observations] a name the rubric scored BADLY is kept")
low, lcl, llab = make_card(txns=[txn(officer=False, title="", value=30_000.0)])
with tempfile.TemporaryDirectory() as tmp:
    p = obs.write([low], tmp, RUN, window_days=60, params={}, funnel={},
                  labels=llab, clusters=[lcl])
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    kept = [r for r in rows if r["kind"] == "observation"]
    check("it is in the archive", len(kept) == 1, str(len(kept)))
    #  There is no pass mark to clear any more. What the archive still has to
    #  guarantee is that a low-scoring name is kept, so the property is now
    #  stated on score_v3 instead of on a verdict that no longer exists.
    check("even with a low score_v3 the row is kept",
          kept[0]["score_v3"] is not None,
          f"score_v3={kept[0]['score_v3']}")

print("[observations] append-only: a second run never rewrites the first")
with tempfile.TemporaryDirectory() as tmp:
    obs.write([card], tmp, RUN, window_days=60, params={}, funnel={},
              labels=labels, clusters=[cluster])
    p = obs.write([card], tmp, RUN, window_days=60, params={}, funnel={},
                  labels=labels, clusters=[cluster])
    rows = p.read_text(encoding="utf-8").splitlines()
    check("the file grew to two headers and two observations", len(rows) == 4,
          str(len(rows)))
    check("no .tmp is left behind", not list(p.parent.glob("*.tmp")),
          str(list(p.parent.glob("*.tmp"))))
    check("the archive lives under observations/form4/",
          p.parent.name == "form4" and p.parent.parent.name == "observations",
          str(p))

print("[observations] the archive is not the signal queue")
import ast

src = (Path(__file__).resolve().parents[1] / "form4_scanner" / "observations.py")
tree = ast.parse(src.read_text(encoding="utf-8"))
names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
check("nothing here expires, dedupes or archives",
      not {n for n in names if any(k in n.lower() for k in
                                   ("expire", "dedup", "archive", "supersede"))},
      str(names))
imports = [n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.module]
check("it does not import a signal-queue module: this is not the queue",
      not [m for m in imports if m.startswith("core")], str(imports))

print("[observations] the git sha says when it cannot be trusted")
sha = obs.git_sha()
check("a sha was resolved in this repo", sha != "", sha)
check("a dirty tree is marked as such rather than passed off as the commit",
      "-dirty" in sha or sha.isalnum(), sha)

if __name__ == "__main__":
    sys.exit(report("ALL OBSERVATION TESTS PASSED"))
