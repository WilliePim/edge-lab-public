"""Build the spin-off index, and the funnel that says whether it is worth having.

WHY THIS TERRAIN. The intersection of spin-offs and insider buying is one the
literature has tested: Allen (2001) documents
that insiders of spun-off subsidiaries are strong net buyers and that their
purchases anticipate long-run positive abnormal returns; a 2019 prospectus-tone
study puts 85,5% of open-market insider transactions in the first three months.
That 3-month figure is where SPINOFF_WINDOW_DAYS = 90 comes from -- it is
borrowed from the literature, not measured here, which is exactly why this
funnel exists.

WHAT A "SPIN-OFF DAUGHTER" IS, OPERATIONALLY. A US subsidiary being spun off and
listed registers its shares on **Form 10-12B**. That form is the net. It is a
registration, not a distribution, so the filing date is not the date the shares
start trading and cannot be the window anchor.

THE ANCHOR. Section 16 requires every officer, director and 10% owner to file a
**Form 3** by the time the registration becomes effective. In a spin-off they
all file at once, on the distribution, which leaves a signature no other event
produces: a burst of Form 3s from several distinct owners on the same day for an
issuer that has never had a Section 16 filer before. That burst is both the
evidence that the registration became a real listing and the date it happened.

    anchor  = the date of the burst
    reason  = >= MIN_BURST distinct owners filing Form 3 within BURST_DAYS

A registration that never lists -- withdrawn, abandoned, merged away -- has no
burst, and correctly drops out. This is the whole of the "reason" test: nothing
here reads prose, and nothing here guesses.

WHAT THIS DELIBERATELY DOES NOT DO. No returns. The funnel counts, and counting
is what decides whether a 90-day window has anything in it. Measuring what the
window earns is M1, and M1 does not start until the funnel says the terrain is
populated.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from form4_scanner.edgar import EdgarClient

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "backfill"
ZIPS = STATE / "zips"
PRICES = STATE / "prices"
SHARES = STATE / "shares"
CANDIDATES = STATE / "spinoff_candidates.jsonl"
BURSTS = STATE / "spinoff_bursts.json"
INDEX = ROOT / "data" / "spinoffs_index.json"
REPORT = ROOT / "reports" / "spinoffs_funnel.md"

FULL_INDEX = "https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx"
FIRST_YEAR = 2015
REG_FORMS = ("10-12B", "10-12B/A", "10-12G", "10-12G/A")

#  The burst. Three is the smallest number that cannot be one person filing an
#  amendment and a colleague filing late; five days covers a distribution that
#  straddles a weekend without reaching into the next week's ordinary filings.
MIN_BURST = 3
BURST_DAYS = 5

WINDOW_DAYS = 90
CAP = 2e9

#  form.idx is whitespace-aligned but the header offsets do not match the data
#  rows -- the date sits five columns right of where the header says. Matching
#  on shape rather than on position: a form type that may itself contain spaces,
#  then two-or-more spaces, then a name, then the CIK, then the date.
ROW_RE = re.compile(
    r"^(?P<form>.*?)\s{2,}(?P<name>.*?)\s{2,}(?P<cik>\d+)\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<path>\S+)\s*$")

MONTHS_ABBR = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _bulk_date(s):
    try:
        d, m, y = s.strip().split("-")
        return date(int(y), MONTHS_ABBR[m.upper()], int(d))
    except (ValueError, KeyError, AttributeError):
        return None


def quarters(through: date):
    for y in range(FIRST_YEAR, through.year + 1):
        for q in (1, 2, 3, 4):
            if y == through.year and (q - 1) * 3 + 1 > through.month:
                return
            yield y, q


# ------------------------------------------------------------ 1. candidates --
def stage_candidates(client, through: date) -> int:
    """Every 10-12B / 10-12G filing since 2015, from the quarterly form.idx."""
    seen, rows = set(), []
    for y, q in quarters(through):
        txt = client.get(FULL_INDEX.format(y=y, q=q))
        if not txt:
            print("  {}Q{}: INDICE NON SCARICATO".format(y, q), flush=True)
            continue
        n = 0
        for line in txt.splitlines():
            #  Cheap prefilter: regexing 500k lines a quarter to keep 30 is the
            #  kind of cost that turns a five-minute job into an hour.
            if not line.startswith("10-12"):
                continue
            m = ROW_RE.match(line)
            if not m or m.group("form").strip() not in REG_FORMS:
                continue
            cik = m.group("cik").lstrip("0")
            key = (cik, m.group("form").strip(), m.group("date"))
            if key in seen:
                continue
            seen.add(key)
            rows.append({"cik": cik, "form": m.group("form").strip(),
                         "name": m.group("name").strip(),
                         "filed": m.group("date"), "path": m.group("path"),
                         "quarter": "{}Q{}".format(y, q)})
            n += 1
        print("  {}Q{}: {} registrazioni".format(y, q, n), flush=True)

    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES.open("w", encoding="utf-8") as fh:
        for r in sorted(rows, key=lambda r: (r["filed"], r["cik"])):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print("\nscritto {}  ({:,} righe)".format(CANDIDATES, len(rows)))
    return 0


# ---------------------------------------------------------------- 2. burst --
def zip_rows(z, name):
    with z.open(name) as fh:
        yield from csv.DictReader(
            io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
            delimiter="\t")


def stage_bursts() -> int:
    """First Section 16 burst per issuer, from the 45 quarterly form345 ZIPs.

    One pass over every SUBMISSION.tsv, keeping only Form 3. The result is
    {issuer_cik: [[date, n_owners], ...]} -- every burst, not just the first,
    because an issuer can be spun off twice and the funnel should not silently
    pick one.
    """
    by_issuer: dict = {}
    for zp in sorted(ZIPS.glob("*.zip")):
        with zipfile.ZipFile(zp) as z:
            names = set(z.namelist())
            if not {"SUBMISSION.tsv", "REPORTINGOWNER.tsv"} <= names:
                continue
            acc_meta = {}
            for r in zip_rows(z, "SUBMISSION.tsv"):
                if (r.get("DOCUMENT_TYPE") or "").strip() != "3":
                    continue
                d = _bulk_date(r.get("FILING_DATE") or "")
                cik = (r.get("ISSUERCIK") or "").strip().lstrip("0")
                if d and cik:
                    acc_meta[r["ACCESSION_NUMBER"]] = (cik, d)
            if not acc_meta:
                continue
            for r in zip_rows(z, "REPORTINGOWNER.tsv"):
                meta = acc_meta.get(r["ACCESSION_NUMBER"])
                if not meta:
                    continue
                cik, d = meta
                owner = (r.get("RPTOWNERCIK") or "").strip().lstrip("0")
                by_issuer.setdefault(cik, {}).setdefault(
                    d.isoformat(), set()).add(owner)
        print("  {}".format(zp.name), flush=True)

    out = {}
    for cik, per_day in by_issuer.items():
        days = sorted(per_day)
        bursts, i = [], 0
        while i < len(days):
            start = date.fromisoformat(days[i])
            owners, j = set(per_day[days[i]]), i + 1
            while j < len(days) and (
                    date.fromisoformat(days[j]) - start).days <= BURST_DAYS:
                owners |= per_day[days[j]]
                j += 1
            if len(owners) >= MIN_BURST:
                bursts.append([days[i], len(owners)])
            i = j if j > i + 1 else i + 1
        if bursts:
            out[cik] = bursts
    BURSTS.write_text(json.dumps(out, sort_keys=True), encoding="utf-8")
    print("\nscritto {}  ({:,} emittenti con almeno un burst)".format(
        BURSTS, len(out)))
    return 0


# --------------------------------------------------------------- 3. match --
def load_candidates():
    """{cik: {"reg": earliest 10-12B/G filing date, "kind": "B"|"G", ...}}"""
    out = {}
    for line in CANDIDATES.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        cik, kind = r["cik"], r["form"][5]          # "10-12B/A" -> "B"
        cur = out.setdefault(cik, {"reg": r["filed"], "kind": kind,
                                   "name": r["name"], "forms": []})
        cur["forms"].append(r["form"])
        if r["filed"] < cur["reg"]:
            cur["reg"] = r["filed"]
        #  A CIK that filed both keeps B: the exchange registration is the
        #  stronger claim, and 43 CIKs filed both.
        if kind == "B":
            cur["kind"] = "B"
    return out


def stage_match() -> int:
    """Anchor each registrant, then collect its insiders' open-market buys."""
    cand = load_candidates()
    bursts = json.loads(BURSTS.read_text(encoding="utf-8"))

    for cik, c in cand.items():
        reg = date.fromisoformat(c["reg"])
        #  The distribution follows the registration. Thirty days of slack
        #  backwards, because a CIK whose original Form 10 predates 2015 enters
        #  this list on an amendment filed after its own distribution.
        after = [b for b in bursts.get(cik, [])
                 if date.fromisoformat(b[0]) >= reg - timedelta(days=30)]
        c["anchor"] = after[0][0] if after else None
        c["anchor_owners"] = after[0][1] if after else None

    #  One pass for both things the funnel still needs from the bulk data: the
    #  ticker (the price panel is keyed by ticker, the SEC by CIK) and every
    #  open-market purchase by an insider of a candidate.
    want = set(cand)
    buys: dict = {}
    tickers: dict = {}
    last_zip = None
    for zp in sorted(ZIPS.glob("*.zip")):
        last_zip = zp.name
        with zipfile.ZipFile(zp) as z:
            names = set(z.namelist())
            if not {"SUBMISSION.tsv", "REPORTINGOWNER.tsv",
                    "NONDERIV_TRANS.tsv"} <= names:
                continue
            sub = {}
            for r in zip_rows(z, "SUBMISSION.tsv"):
                cik = (r.get("ISSUERCIK") or "").strip().lstrip("0")
                if cik not in want:
                    continue
                t = (r.get("ISSUERTRADINGSYMBOL") or "").strip().upper()
                if t and t not in ("NONE", "N/A", "[NONE]", ""):
                    tickers.setdefault(cik, t)
                sub[r["ACCESSION_NUMBER"]] = cik
            if not sub:
                continue
            owners = {}
            for r in zip_rows(z, "REPORTINGOWNER.tsv"):
                if r["ACCESSION_NUMBER"] in sub:
                    rel = r.get("RPTOWNER_RELATIONSHIP") or ""
                    owners.setdefault(r["ACCESSION_NUMBER"], []).append(
                        ((r.get("RPTOWNERCIK") or "").strip().lstrip("0"),
                         "Director" in rel, "Officer" in rel,
                         "TenPercent" in rel))
            for r in zip_rows(z, "NONDERIV_TRANS.tsv"):
                a = r["ACCESSION_NUMBER"]
                if a not in sub or a not in owners:
                    continue
                if (r.get("TRANS_CODE") or "").strip().upper() != "P":
                    continue
                if (r.get("TRANS_ACQUIRED_DISP_CD") or "").strip().upper() != "A":
                    continue
                td = _bulk_date(r.get("TRANS_DATE") or "")
                if td is None:
                    continue
                try:
                    sh = float(r.get("TRANS_SHARES") or 0)
                    px = float(r.get("TRANS_PRICEPERSHARE") or 0)
                except ValueError:
                    continue
                for own, is_dir, is_off, is_ten in owners[a]:
                    buys.setdefault(sub[a], []).append(
                        {"d": td.isoformat(), "owner": own, "v": sh * px,
                         "dir": is_dir, "off": is_off, "ten": is_ten,
                         "acc": a})
        print("  {}".format(zp.name), flush=True)

    out = {"generated": date.today().isoformat(), "last_zip": last_zip,
           "candidates": cand, "tickers": tickers, "buys": buys}
    (STATE / "spinoff_enriched.json").write_text(
        json.dumps(out, sort_keys=True), encoding="utf-8")
    anch = sum(1 for c in cand.values() if c["anchor"])
    print("\n{:,} registranti, {:,} con ancora, {:,} con ticker, "
          "{:,} con almeno un acquisto".format(
              len(cand), anch, len(tickers), len(buys)))
    return 0


# --------------------------------------------------------------- 4. funnel --
#  The bulk ZIPs stop at 2026Q1, so a distribution in 2026Q2 has no observable
#  90-day window. Counting it in the denominator would report "no purchases"
#  for issuers whose purchases simply have not been downloaded.
LAST_DATA = date(2026, 3, 31)
FLOOR = 25_000.0


def price_at(ticker, when, slack=10):
    """First close on or after `when`. A daughter has no price before it lists."""
    p = PRICES / "{}.csv".format((ticker or "").replace("/", "_"))
    if not ticker or not p.exists():
        return None
    lo, hi = when.isoformat(), (when + timedelta(days=slack)).isoformat()
    best = None
    with p.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            if lo <= d <= hi:
                try:
                    best = float(v)
                except ValueError:
                    best = None
                break
    return best


def shares_at(cik, when):
    """(value, "pit"|"first-after"|None).

    Point-in-time first: the newest count already FILED on the anchor date. A
    company distributed last week has filed nothing, so the fallback is its
    first report after listing -- a lookahead on the share count, declared, and
    used only to size the universe, never inside a return.
    """
    p = SHARES / "{}.json".format(cik)
    if not p.exists():
        return None, None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None, None
    recs = [r for r in (d.get("primary") or []) + (d.get("fallback") or [])
            if r.get("filed") and r.get("val")]
    if not recs:
        return None, None
    iso = when.isoformat()
    pit = [r for r in recs if r["filed"] <= iso]
    if pit:
        return max(pit, key=lambda r: r["filed"])["val"], "pit"
    after = [r for r in recs if r["filed"] > iso]
    if after:
        return min(after, key=lambda r: r["filed"])["val"], "first-after"
    return None, None


def window_stats(rows, anchor, days, floor=0.0):
    """Buys inside [anchor, anchor+days], deduped the way cluster.py does it."""
    lo, hi = anchor, anchor + timedelta(days=days)
    keep = [b for b in rows
            if lo <= date.fromisoformat(b["d"]) <= hi and b["v"] >= floor]
    if not keep:
        return None
    return {
        "n": len(keep),
        "owners": len({b["owner"] for b in keep}),
        "accessions": len({b["acc"] for b in keep}),
        "usd": sum(b["v"] for b in keep),
        "director": any(b["dir"] and not b["off"] and not b["ten"] for b in keep),
        "ten_pct": any(b["ten"] for b in keep),
    }


def stage_funnel() -> int:
    data = json.loads((STATE / "spinoff_enriched.json").read_text(encoding="utf-8"))
    cand, tickers, buys = data["candidates"], data["tickers"], data["buys"]

    rows = []
    for cik, c in cand.items():
        r = {"cik": cik, "name": c["name"], "kind": c["kind"],
             "reg": c["reg"], "anchor": c["anchor"],
             "anchor_owners": c["anchor_owners"],
             "ticker": tickers.get(cik)}
        if c["anchor"]:
            a = date.fromisoformat(c["anchor"])
            px = price_at(r["ticker"], a)
            sh, how = shares_at(cik, a)
            r["price"] = px
            r["shares_src"] = how
            r["cap"] = px * sh if (px and sh) else None
            r["observable"] = a + timedelta(days=WINDOW_DAYS) <= LAST_DATA
            mine = buys.get(cik, [])
            for tag, days, floor in (("w90", 90, 0.0), ("w90f", 90, FLOOR),
                                     ("w180", 180, 0.0), ("w180f", 180, FLOOR)):
                r[tag] = window_stats(mine, a, days, floor)
        rows.append(r)

    (STATE / "spinoff_funnel_rows.json").write_text(
        json.dumps(rows, sort_keys=True, default=str), encoding="utf-8")
    print("scritte {:,} righe di funnel".format(len(rows)))
    return 0

# -------------------------------------------------------------- 5. refresh --
#  The bulk ZIPs stop at 2026Q1. A daughter distributed after that has its
#  Form 3 burst on EDGAR and nowhere in the corpus, so an index built from the
#  ZIPs alone is blind for as long as the quarterly file is late -- up to five
#  months, on exactly the names a live scan would be looking at. Sixteen CIKs
#  is a cheap price for an index that is current.
REFRESH_FROM = "2025-01-01"


def stage_refresh(client) -> int:
    """Anchor the recent registrants the ZIPs cannot see yet, from EDGAR."""
    from form4_scanner.edgar import submission_rows

    data = json.loads((STATE / "spinoff_enriched.json").read_text(encoding="utf-8"))
    cand = data["candidates"]
    todo = [cik for cik, c in cand.items()
            if not c["anchor"] and c["reg"] >= REFRESH_FROM]
    print("da risolvere via submissions: {}".format(len(todo)), flush=True)

    found = 0
    for cik in sorted(todo):
        rows = submission_rows(client, cik) or []
        #  One Form 3 accession is one filing, and a joint filing is rare
        #  enough that counting accessions instead of owners moves nothing.
        days = sorted({r["filed"] for r in rows
                       if (r.get("form") or "").strip() == "3" and r.get("filed")})
        #  Same guard as the bulk path: the distribution FOLLOWS the
        #  registration. Without it a CIK that has been a Section 16 filer
        #  since 1999 anchors on its 1999 burst and the window lands a quarter
        #  of a century before the spin-off it was supposed to describe.
        floor_day = (date.fromisoformat(cand[cik]["reg"])
                     - timedelta(days=30)).isoformat()
        days = [d for d in days if d >= floor_day]
        anchor = owners = None
        i = 0
        while i < len(days):
            start = date.fromisoformat(days[i])
            j, n = i, 0
            while j < len(days) and (
                    date.fromisoformat(days[j]) - start).days <= BURST_DAYS:
                n += sum(1 for r in rows
                         if (r.get("form") or "").strip() == "3"
                         and r.get("filed") == days[j])
                j += 1
            if n >= MIN_BURST:
                anchor, owners = days[i], n
                break
            i += 1
        if anchor:
            cand[cik]["anchor"] = anchor
            cand[cik]["anchor_owners"] = owners
            cand[cik]["anchor_source"] = "submissions"
            found += 1
            print("  {} {}  {} ({} Form 3)".format(
                cik, cand[cik]["name"][:38], anchor, owners), flush=True)

    data["candidates"] = cand
    (STATE / "spinoff_enriched.json").write_text(
        json.dumps(data, sort_keys=True), encoding="utf-8")
    print("\nancorati {} su {}".format(found, len(todo)))
    return 0


# ---------------------------------------------------------------- 6. index --
def stage_index() -> int:
    """data/spinoffs_index.json -- what turns `terreno` from None into a test.

    Only 10-12B. The 10-12G bucket triples the population and halves the
    anchoring rate (the funnel report this tool writes, `REPORT`), and a terrain defined by a
    form that shells also use is not a terrain.
    """
    data = json.loads((STATE / "spinoff_enriched.json").read_text(encoding="utf-8"))
    cand, tickers = data["candidates"], data["tickers"]

    children = []
    for cik, c in sorted(cand.items(), key=lambda kv: kv[0]):
        if c["kind"] != "B" or not c["anchor"]:
            continue
        children.append({
            "cik": cik,
            "name": c["name"],
            "ticker": tickers.get(cik),
            "date_distribution": c["anchor"],
            "anchor_owners": c["anchor_owners"],
            "anchor_source": c.get("anchor_source", "bulk"),
            "registration": c["reg"],
        })

    out = {
        "generated": date.today().isoformat(),
        "window_days": WINDOW_DAYS,
        "definition": ("Form 10-12B registrants since {}, anchored on the first "
                       "Section 16 burst: >= {} Form 3 within {} days. See "
                       "the funnel report written by tools/spinoffs.py".format(
                           FIRST_YEAR, MIN_BURST, BURST_DAYS)),
        "children": children,
    }
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print("scritto {}  ({} figlie, la piu' recente {})".format(
        INDEX, len(children),
        max((c["date_distribution"] for c in children), default="-")))
    return 0

# ---------------------------------------- 7. la rete, SOLO dai metadati ----
#  EDGAR does not carry the exhibit DESCRIPTION anywhere structured. Sampled on
#  six known spin-offs, in the -index.htm table and in the SGML header:
#
#      TYPE=EX-99.1     DESCRIPTION=EX-99.1
#      TYPE=EX-10.2     DESCRIPTION=EX-10.2
#
#  "Information Statement" and "Separation and Distribution Agreement" exist
#  only in the exhibit index INSIDE the Form 10 body. The pipeline therefore
#  nets on the exhibit NUMBER, which is metadata; the two phrases are measured
#  once by tools/audit_spinoff_net.py, which decides nothing.
IDX_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
IDX_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
NET = STATE / "spinoff_net.json"


def exhibit_types(client, cik, path):
    acc = path.split("/")[-1].replace(".txt", "")
    url = ("https://www.sec.gov/Archives/edgar/data/{}/{}/{}-index.htm"
           .format(cik, acc.replace("-", ""), acc))
    html = client.get(url)
    if not html:
        return []
    out = []
    for m in IDX_ROW.finditer(html):
        cells = [re.sub(r"<[^>]+>", " ", x).strip()
                 for x in IDX_CELL.findall(m.group(1))]
        if len(cells) >= 4 and cells[0].strip().isdigit():
            out.append(cells[3].strip().upper())
    return out


def stage_net(client) -> int:
    cand = load_candidates()
    b = {k: v for k, v in cand.items() if v["kind"] == "B"}
    raw = [json.loads(l) for l in
           CANDIDATES.read_text(encoding="utf-8").splitlines()]
    filings = {}
    for r in raw:
        if r["form"].startswith("10-12B"):
            filings.setdefault(r["cik"], []).append(r)

    out = {}
    for i, (cik, c) in enumerate(sorted(b.items())):
        types = set()
        for f in sorted(filings.get(cik, []), key=lambda r: r["filed"]):
            types |= set(exhibit_types(client, cik, f["path"]))
        sub = client.get_json(
            "https://data.sec.gov/submissions/CIK{:010d}.json".format(int(cik)))
        tk = (sub or {}).get("tickers") or []
        out[cik] = {"name": c["name"], "reg": c["reg"],
                    "exhibits": sorted(types),
                    #  EX-99.1 oppure EX-99 nudo: lo stesso documento, senza
                    #  sotto-numero quando e' l'unico allegato 99. Cercare solo
                    #  "EX-99.1" perdeva Aptevo Therapeutics e American Outdoor
                    #  Brands, che sono spin-off veri.
                    "has_ex991": any(t == "EX-99" or t.startswith("EX-99.1")
                                     for t in types),
                    "ticker": (tk[0] if tk else None),
                    "sic": (sub or {}).get("sic")}
        if i % 25 == 0:
            print("  {}/{}".format(i, len(b)), flush=True)

    NET.write_text(json.dumps(out, sort_keys=True), encoding="utf-8")
    print("\n10-12B: {}   con EX-99.1: {}   con ticker: {}".format(
        len(out), sum(1 for v in out.values() if v["has_ex991"]),
        sum(1 for v in out.values() if v["ticker"])))
    return 0


# ------------------------------------------------------------- 8. prezzi ----
def stage_prices() -> int:
    """Serie complete per i ticker delle figlie, dalla stessa fonte del panel."""
    import yfinance as yf

    net = json.loads(NET.read_text(encoding="utf-8"))
    want = sorted({v["ticker"] for v in net.values() if v["ticker"]})
    todo = [t for t in want
            if not (PRICES / "{}.csv".format(t.replace("/", "_"))).exists()]
    print("ticker figlie: {}   gia' nel panel: {}   da scaricare: {}".format(
        len(want), len(want) - len(todo), len(todo)), flush=True)
    ok = 0
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        try:
            df = yf.download(chunk, start="2013-01-01", auto_adjust=False,
                             progress=False, threads=True, group_by="ticker")
        except Exception:                                       # noqa: BLE001
            continue
        for t in chunk:
            try:
                sub = df[t] if len(chunk) > 1 else df
                col = "Adj Close" if "Adj Close" in sub.columns else "Close"
                ser = sub[col].dropna()
            except (KeyError, TypeError):
                continue
            if ser is None or len(ser) < 5:
                continue
            out = PRICES / "{}.csv".format(t.replace("/", "_"))
            tmp = out.with_suffix(".csv.tmp")
            ser.to_csv(tmp, header=["adj_close"])
            os.replace(tmp, out)
            ok += 1
        print("  {}/{}  ok {}".format(i + len(chunk), len(todo), ok), flush=True)
    print("scaricate {} serie".format(ok))
    return 0


def price_dates(ticker):
    """Tutte le date della serie, ordinate. [] se non c'e' serie."""
    if not ticker:
        return []
    p = PRICES / "{}.csv".format(ticker.replace("/", "_"))
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d = line.split(",", 1)[0].strip()
            if len(d) == 10:
                out.append(d)
    return sorted(out)


def price_on(ticker, day):
    """Chiusura del giorno `day`, o del primo giorno successivo entro 7."""
    p = PRICES / "{}.csv".format((ticker or "").replace("/", "_"))
    if not ticker or not p.exists():
        return None
    lo = day.isoformat()
    hi = (day + timedelta(days=7)).isoformat()
    with p.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            if lo <= d.strip() <= hi:
                try:
                    return float(v)
                except ValueError:
                    return None
    return None


# ------------------------------------------------ 9. ancora v3 e universo --
#  IL PRIMO PREZZO NON E' L'ANCORA. E' when-issued: due figlie distribuite a
#  luglio 2026 hanno entrambe la prima barra il 2026-06-26, e le distribuzioni
#  vere cadono 5 e 10 giorni dopo. Un anticipo di 5-10 giorni su una finestra
#  di 90 non e' un dettaglio quando la finestra e' l'unica cosa che definisce il terreno.
#
#  L'ancora e' invece il momento in cui il GENITORE si spoglia: in uno scorporo
#  la capogruppo possiede il 100% della figlia e poi lo distribuisce, e quel
#  gesto lascia un Form 4 sulla figlia, depositato da un 10% owner, con codice J
#  e azioni residue ZERO. E' un fatto nell'XML, non una lettura.
#
#  Verificato su casi reali del 2026: in uno la capogruppo deposita una sola
#  cessione a zero; in un altro la cessione della capogruppo e' preceduta di un
#  giorno da quella di una controllata intermedia. Si prende l'ULTIMA cessione a
#  zero della catena: in una distribuzione a due stadi l'ultimo passo e' quello che
#  arriva agli azionisti.
PARENT_WINDOW_DAYS = 60
VOL_JUMP = 5.0


def parent_zero_date(client, cik, imminent):
    """Ultima cessione a zero da un 10% owner entro 60gg dall'efficacia."""
    from form4_scanner.edgar import submission_rows
    from form4_scanner.parse import parse_ownership_xml

    eff = date.fromisoformat(imminent)
    best = None
    for r in sorted(submission_rows(client, cik) or [],
                    key=lambda r: r.get("filed") or ""):
        if (r.get("form") or "").strip() not in ("4", "4/A"):
            continue
        xml = client.ownership_xml(cik, r["accession"])
        if not xml:
            continue
        try:
            txns = parse_ownership_xml(xml, accession=r["accession"],
                                       filed_at=date.fromisoformat(r["filed"]))
        except Exception:                                       # noqa: BLE001
            continue
        for t in txns:
            if not t.is_ten_pct or not t.txn_date:
                continue
            if not (t.shares_after == 0 or t.code == "J"):
                continue
            if abs((t.txn_date - eff).days) > PARENT_WINDOW_DAYS:
                continue
            if best is None or t.txn_date > best[0]:
                best = (t.txn_date, t.owner_name)
    return best


def first_8k_change_of_control(client, cik, imminent):
    """Data di deposito del primo 8-K con Item 5.01 dopo l'efficacia.

    L'elenco degli item e' metadato (`filings.recent.items`), non testo. Si usa
    la data di DEPOSITO e non `reportDate`: reportDate e' il primo evento
    coperto dall'8-K, che in uno scorporo e' la firma del separation agreement,
    non la distribuzione. Sui due casi con un Form 4 del genitore la data di
    deposito coincide con la cessione a zero, e questa e' la ragione per
    preferirla.
    """
    d = client.get_json(
        "https://data.sec.gov/submissions/CIK{:010d}.json".format(int(cik)))
    rec = (d or {}).get("filings", {}).get("recent", {})
    out = []
    for f, fd, it in zip(rec.get("form", []), rec.get("filingDate", []),
                         rec.get("items", [])):
        if f.startswith("8-K") and "5.01" in (it or "") and fd >= imminent:
            out.append(fd)
    return min(out) if out else None


def volume_jump_date(ticker, after_iso):
    """Primo giorno con volume > 5x la mediana dei precedenti. Da verificare."""
    p = PRICES / "{}.vol.csv".format((ticker or "").replace("/", "_"))
    if not ticker or not p.exists():
        return None
    rows = []
    with p.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            try:
                rows.append((d.strip(), float(v)))
            except ValueError:
                continue
    hist = []
    for d, v in rows:
        if hist and d >= after_iso:
            s = sorted(hist[-20:])
            med = s[len(s) // 2] if s else 0
            if med > 0 and v > VOL_JUMP * med:
                return d
        hist.append(v)
    return None


def stage_anchor(client) -> int:
    net = json.loads(NET.read_text(encoding="utf-8"))
    enr = json.loads((STATE / "spinoff_enriched.json").read_text(encoding="utf-8"))
    zt = enr.get("tickers", {})
    sub_anchor = {k: v.get("anchor") for k, v in enr["candidates"].items()}

    out = {}
    for i, (cik, v) in enumerate(sorted(net.items())):
        rec = dict(v)
        #  Il ticker: submissions da' quello CORRENTE, e una figlia acquisita o
        #  delistata non ne ha piu'. I ZIP Form 4 conservano quello storico.
        rec["ticker"] = v.get("ticker") or zt.get(cik)
        rec["date_imminent"] = sub_anchor.get(cik)
        rec["date_distribution"] = None
        rec["date_source"] = None
        rec["needs_review"] = False
        rec["drop_reason"] = None

        if not v["has_ex991"]:
            rec["drop_reason"] = "no EX-99/EX-99.1"
            out[cik] = rec
            continue
        if not rec["date_imminent"]:
            rec["drop_reason"] = "no Section 16 burst"
            out[cik] = rec
            continue

        got = parent_zero_date(client, cik, rec["date_imminent"])
        if got:
            rec["date_distribution"] = got[0].isoformat()
            rec["date_source"] = "form4-parent"
            rec["parent_name"] = got[1]
        else:
            fb = first_8k_change_of_control(client, cik, rec["date_imminent"])
            if fb:
                rec["date_distribution"] = fb
                rec["date_source"] = "8k-item-5.01"
            else:
                vj = volume_jump_date(rec["ticker"], rec["date_imminent"])
                if vj:
                    rec["date_distribution"] = vj
                    rec["date_source"] = "volume"
                    rec["needs_review"] = True
                else:
                    rec["drop_reason"] = "nessuna data di distribuzione"
        out[cik] = rec
        if i % 25 == 0:
            print("  {}/{}".format(i, len(net)), flush=True)

    (STATE / "spinoff_anchored.json").write_text(json.dumps(out, sort_keys=True),
                                                 encoding="utf-8")
    from collections import Counter
    kept = [v for v in out.values() if v["date_distribution"]]
    print("\ncon distribuzione: {} / {}".format(len(kept), len(out)))
    print("fonte:", dict(Counter(v["date_source"] for v in kept)))
    print("cadute:", dict(Counter(v["drop_reason"] for v in out.values()
                                  if v["drop_reason"])))
    return 0


# ---------------------------------------------------- 10. cap e indice ------
def stage_cap(client) -> int:
    """cap_at_distribution = azioni di copertina del primo 10-Q/10-K x prezzo."""
    sys.path.insert(0, str(ROOT))
    from form4_scanner.flags import cap_bucket

    anch = json.loads((STATE / "spinoff_anchored.json").read_text(encoding="utf-8"))
    todo = [(c, v) for c, v in sorted(anch.items()) if v["date_distribution"]]
    print("da dimensionare: {}".format(len(todo)), flush=True)

    for i, (cik, v) in enumerate(todo):
        d = date.fromisoformat(v["date_distribution"])
        #  dei:EntityCommonStockSharesOutstanding IS the cover-page count of the
        #  10-Q/10-K. The first one FILED after the distribution is the first
        #  time the daughter states its own share count.
        facts = client.company_concept(
            cik, "dei", "EntityCommonStockSharesOutstanding") or {}
        recs = []
        for unit, arr in (facts.get("units") or {}).items():
            for r in arr:
                if r.get("filed") and r.get("val") and r.get("form", "").startswith(
                        ("10-Q", "10-K")):
                    recs.append(r)
        after = sorted([r for r in recs if r["filed"] >= v["date_distribution"]],
                       key=lambda r: r["filed"])
        px = price_on(v["ticker"], d)
        v["shares_cover"] = after[0]["val"] if after else None
        v["shares_form"] = after[0].get("form") if after else None
        v["shares_filed"] = after[0].get("filed") if after else None
        v["price_at_distribution"] = px
        v["cap_at_distribution"] = (px * after[0]["val"]) if (px and after) else None
        v["cap_bucket"] = cap_bucket(v["cap_at_distribution"])
        #  <= 2e9 at distribution is the universe of the live scan. Daughters
        #  above it stay in the index -- the terrain is a fact about them --
        #  with universe False, so the two questions stay separable.
        v["universe"] = bool(v["cap_at_distribution"]
                             and v["cap_at_distribution"] < 2e9)
        if i % 25 == 0:
            print("  {}/{}".format(i, len(todo)), flush=True)

    (STATE / "spinoff_anchored.json").write_text(json.dumps(anch, sort_keys=True),
                                                 encoding="utf-8")
    sized = [v for _, v in todo if v["cap_at_distribution"]]
    print("\ndimensionate {} / {}   in universo (<2e9): {}".format(
        len(sized), len(todo), sum(1 for v in sized if v["universe"])))
    return 0

def main() -> int:
    ua = sys.argv[1] if len(sys.argv) > 1 else ""
    stage = sys.argv[2] if len(sys.argv) > 2 else "all"
    if not ua:
        raise SystemExit('uso: spinoffs.py "Nome Cognome email@dominio" [stage]')
    client = EdgarClient(ua)
    today = date.today()
    if stage in ("candidates", "all"):
        stage_candidates(client, today)
    if stage in ("bursts", "all"):
        stage_bursts()
    if stage in ("match", "all"):
        stage_match()
    if stage in ("funnel", "all"):
        stage_funnel()
    if stage in ("refresh", "all"):
        stage_refresh(client)
    if stage in ("net", "all"):
        stage_net(client)
    if stage in ("prices", "all"):
        stage_prices()
    if stage in ("anchor", "all"):
        stage_anchor(client)
    if stage in ("cap", "all"):
        stage_cap(client)
    if stage in ("index", "all"):
        stage_index()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
