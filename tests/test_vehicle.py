"""Tests for BDC/REIT vehicle detection and sponsor linking.

The case that prompted this: Chicago Atlantic BDC and Chicago Atlantic Real
Estate Finance both surfaced in the 2026-08-22 scan. Two rows, two scores, one
manager. The rubric reads them as two independent insider signals; they are not.

The second thing the module must get right is what it does NOT claim. External
management lives in 10-K prose, not in a tagged fact, so the flag reports the
vehicle class it can prove and says the management structure is inferred.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.vehicle import (BDC, REAL_ESTATE, REIT, classify_vehicle,
                                   link_sponsors, name_tokens, shared_sponsor)


class FakeClient:
    def __init__(self, sic="", forms=()):
        self._sic = sic
        self._forms = list(forms)

    def submissions(self, cik):
        return {"sic": self._sic,
                "filings": {"recent": {"form": self._forms,
                                       "filingDate": ["2026-01-01"] * len(self._forms)}}}


# --------------------------------------------------------------------------
print("[vehicle] BDC election is definitive")
r = classify_vehicle(FakeClient("", ["N-54A", "10-K"]), "1", "Some Fund LP")
check("N-54A makes it a BDC", r.kind == BDC, r.kind)
check("the reason names the form", "N-54A" in r.flag(), r.flag())
check("it is recognised as a vehicle", r.is_vehicle)

r = classify_vehicle(FakeClient("", ["N-54A", "N-54C"]), "1", "Lapsed Fund LP")
check("election plus withdrawal is reported, not resolved",
      "may have lapsed" in r.flag(), r.flag())

print("[vehicle] REIT and real estate come from the SIC code")
r = classify_vehicle(FakeClient("6798", ["10-K"]), "1", "Some Property Trust")
check("SIC 6798 is a REIT", r.kind == REIT, r.kind)
r = classify_vehicle(FakeClient("6500", ["10-K"]), "1", "Some Lending Co LP")
check("SIC 6500 is real estate", r.kind == REAL_ESTATE, r.kind)

print("[vehicle] an operating company is not a vehicle and gets no flag")
for sic, what in (("3714", "auto parts"), ("2834", "pharma"),
                  ("6022", "a bank"), ("", "no SIC")):
    r = classify_vehicle(FakeClient(sic, ["10-K", "8-K"]), "1", "Normal Corp")
    check(f"SIC {sic or '(empty)'} ({what}) is not a vehicle",
          not r.is_vehicle, r.kind)
    check(f"...and produces no flag line", r.flag() == "", r.flag())

print("[vehicle] what the module refuses to claim")
r = classify_vehicle(FakeClient("6798", ["10-K"]), "1", "Some Property Trust")
check("external management is UNKNOWN by default",
      r.externally_managed is None, str(r.externally_managed))
check("the flag says the structure is inferred, not verified",
      "inferred, unverified" in r.flag(), r.flag())
check("...and still says why it matters operationally",
      "manager buying its own vehicle" in r.flag(), r.flag())
check("the flag stays short enough to read in a report line",
      len(r.flag()) < 160, f"{len(r.flag())} chars")
check("it does not assert 'externally-managed' unverified",
      not r.flag().startswith("externally-managed"), r.flag())

print("[vehicle] a hand-confirmed structure is stated plainly")
ov = {"1": {"externally_managed": True, "sponsor": "Chicago Atlantic"}}
r = classify_vehicle(FakeClient("6798", ["10-K"]), "1",
                     "Chicago Atlantic Real Estate Finance", overrides=ov)
check("confirmed external management is asserted",
      r.externally_managed is True, str(r.externally_managed))
check("the flag leads with it",
      r.flag().startswith("externally-managed REIT"), r.flag())
check("the confirmation is attributed", "vehicles.json" in r.flag(), r.flag())
check("the hand-set sponsor is used", r.sponsor == "Chicago Atlantic",
      r.sponsor)

ov = {"1": {"externally_managed": False}}
r = classify_vehicle(FakeClient("6798", ["10-K"]), "1", "Internal REIT Inc",
                     overrides=ov)
check("a confirmed INTERNAL manager is stated too",
      r.flag().startswith("internally-managed REIT"), r.flag())
check("...and the manager caveat is dropped for it",
      "manager buying its own vehicle" not in r.flag(), r.flag())

ov = {"1": True}
r = classify_vehicle(FakeClient("6798", ["10-K"]), "1", "Bare Bool REIT",
                     overrides=ov)
check("a bare boolean override also works",
      r.externally_managed is True, str(r.externally_managed))

print("[vehicle] name normalisation")
check("legal wrappers are stripped",
      name_tokens("Chicago Atlantic BDC, Inc.") == ("CHICAGO", "ATLANTIC", "BDC"),
      str(name_tokens("Chicago Atlantic BDC, Inc.")))
check("punctuation and case do not matter",
      name_tokens("chicago-atlantic  BDC LLC") == ("CHICAGO", "ATLANTIC", "BDC"),
      str(name_tokens("chicago-atlantic  BDC LLC")))
check("'The' and 'Trust' are noise",
      name_tokens("The Mack Trust") == ("MACK",),
      str(name_tokens("The Mack Trust")))

print("[vehicle] THE case: two vehicles, one sponsor")
sponsor = shared_sponsor("Chicago Atlantic BDC, Inc.",
                         "Chicago Atlantic Real Estate Finance, Inc.")
check("Chicago Atlantic is recognised as the shared sponsor",
      sponsor == "Chicago Atlantic", sponsor)

check("one shared word is NOT a shared sponsor",
      shared_sponsor("Chicago Atlantic BDC", "Chicago Bridge and Iron") == "",
      shared_sponsor("Chicago Atlantic BDC", "Chicago Bridge and Iron"))
check("unrelated names share nothing",
      shared_sponsor("Byrna Technologies", "Mesa Laboratories") == "")
check("an empty name is survivable", shared_sponsor("", "Anything Corp") == "")

lien = classify_vehicle(FakeClient("", ["N-54A"]), "111",
                        "Chicago Atlantic BDC, Inc.")
refi = classify_vehicle(FakeClient("6798", ["10-K"]), "222",
                        "Chicago Atlantic Real Estate Finance, Inc.")
byrn = classify_vehicle(FakeClient("3690", ["10-K"]), "333",
                        "Byrna Technologies Inc.")
link_sponsors([lien, refi, byrn], {"111": "LIEN", "222": "REFI", "333": "BYRN"})

check("LIEN is linked to REFI", lien.sponsor_peers == ("REFI",),
      str(lien.sponsor_peers))
check("REFI is linked back to LIEN", refi.sponsor_peers == ("LIEN",),
      str(refi.sponsor_peers))
check("both carry the sponsor name", lien.sponsor == refi.sponsor
      == "Chicago Atlantic", f"{lien.sponsor} / {refi.sponsor}")
check("the flag spells out what the overlap means",
      "one manager, not independent signals" in lien.flag(), lien.flag())
check("the flag names the peer ticker", "REFI" in lien.flag(), lien.flag())
check("a non-vehicle is not linked to anything",
      byrn.sponsor_peers == () and byrn.sponsor == "", str(byrn))
check("...and the linker leaves non-vehicles alone entirely",
      byrn.flag() == "", byrn.flag())

print("[vehicle] a lone vehicle has no peers")
solo = classify_vehicle(FakeClient("6798", ["10-K"]), "1", "Lonely REIT Inc")
link_sponsors([solo], {"1": "SOLO"})
check("no peers when it is the only one", solo.sponsor_peers == (),
      str(solo.sponsor_peers))
check("the flag omits the sponsor clause",
      "same sponsor as" not in solo.flag(), solo.flag())

print("[vehicle] three from one sponsor all see each other")
a = classify_vehicle(FakeClient("6798", ["10-K"]), "1", "Apollo Alpha Trust")
b = classify_vehicle(FakeClient("6798", ["10-K"]), "2", "Apollo Alpha Income")
c = classify_vehicle(FakeClient("", ["N-54A"]), "3", "Apollo Alpha Lending")
link_sponsors([a, b, c], {"1": "AAA", "2": "AAB", "3": "AAC"})
check("each sees the other two", a.sponsor_peers == ("AAB", "AAC"),
      str(a.sponsor_peers))
check("peers are sorted and deduplicated",
      b.sponsor_peers == ("AAA", "AAC"), str(b.sponsor_peers))

print("[vehicle] a dead client does not break the run")


class DeadClient:
    def submissions(self, cik):
        return None


r = classify_vehicle(DeadClient(), "1", "Whatever Inc")
check("no submissions -> not a vehicle, no crash", not r.is_vehicle, r.kind)
check("...and no flag is emitted", r.flag() == "", r.flag())

if __name__ == "__main__":
    sys.exit(report("ALL VEHICLE TESTS PASSED"))
