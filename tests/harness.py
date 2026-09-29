"""The assertion helper every suite in this repo uses.

It lived in eleven files as eleven identical copies. Extracting it is worth
doing not because five duplicated lines cost anything to run, but because the
copies had already begun to drift in the details that matter -- what counts as a
failure, what gets printed on one -- and a test harness that behaves differently
depending on which file you are reading is a harness you cannot trust to be
telling you the same thing twice.

Deliberately not pytest, matching the existing convention: these are flat
scripts that execute on import and run to completion. `check` records a failure
and carries on rather than raising, so one broken assertion does not hide the
fifty after it.

Usage, from any file under tests/:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # or .parent.parent
    from harness import check, report

    check("the thing holds", actual == expected, str(actual))

    if __name__ == "__main__":
        sys.exit(report("ALL WIDGET TESTS PASSED"))
"""

from __future__ import annotations

import sys

#  Module-level, like the copies it replaces. Each suite runs in its own
#  process, so there is no cross-file accumulation to worry about.
FAILURES: list = []


def check(name: str, cond, detail: str = "") -> bool:
    """Record one assertion. Returns the outcome so a caller can branch on it."""
    ok = bool(cond)
    suffix = f"  -- {detail}" if detail and not ok else ""
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{suffix}")
    if not ok:
        FAILURES.append(name)
    return ok


def section(title: str) -> None:
    """A heading, blank line above, matching the existing output shape."""
    print(f"\n[{title}]")


def raises(fn, exc=Exception) -> bool:
    """True when `fn()` raises `exc`. Any other exception is not a pass.

    A bare `except Exception` here would let a typo in the test masquerade as
    the error it was meant to provoke.
    """
    try:
        fn()
    except exc:
        return True
    except BaseException:
        return False
    return False


def near(got, want, tol=0.5) -> bool:
    """Absolute-tolerance float comparison that treats None as a failure."""
    return got is not None and abs(got - want) <= tol


def report(banner: str) -> int:
    """Print the epilogue, return the exit code."""
    n = len(FAILURES)
    if n:
        print(f"\n{n} FAILURES: {FAILURES}")
    else:
        print(f"\n{banner}")
    return 1 if n else 0


def main(banner: str) -> None:
    """Convenience for `if __name__ == '__main__':` at the foot of a suite."""
    sys.exit(report(banner))
