# PM-001 — The guard that couldn't speak

**Status:** resolved · **Severity:** none shipped, class critical · **Component:** pre-publication perimeter guard

## Context

This module lives inside a private repository and is published as a public
mirror. A pre-publication guard greps the public perimeter for forbidden
patterns (API key signatures, workspace identifiers, absolute local paths,
references to the private process the module feeds) and fails the mirror
pipeline on any match. The guard exists because the perimeter is a security
boundary, and a boundary that depends on someone remembering a rule is not a
boundary.

## What happened

While adding a new pattern for workspace identifiers (`wrkspc_…`), the regex
was written with a word-boundary anchor, `\b`. The pattern text passed through
one escaping layer too many before it reached the source file, so `\b` was
consumed as a *string* escape rather than surviving into the regex, and became
a literal backspace character, byte `0x08`.

The guard was now searching every file for ⟨backspace⟩`wrkspc_`: a byte
sequence that will never occur in any source file. It matched nothing,
reported nothing, and failed nothing.

## Why this is the worst failure mode for this class of code

A control character does not print. Reading the pattern in the source file,
it looked correct. Running the guard, it produced the same output as a healthy
guard finding no violations: **silence**. A broken detector and a clean
codebase are indistinguishable from the outside — a structural false negative,
invisible by construction.

For most code, a bug produces a wrong answer you can notice. For a guard,
the bug *removes the ability to notice*. The cost is not paid when the bug is
written; it is paid later, when a real secret sails through a check everyone
believes is standing.

## How it was caught

Not by the guard's own output — that was the point. It was caught because the
new pattern was exercised immediately after being added, against a synthetic
line that was *supposed* to trip it, and didn't. The discipline that found the
bug is the same one that motivates the guard: never trust a control you haven't
watched fail on purpose.

Worth stating plainly, because it is the whole lesson: the guard was added in
the same session, by the same person, minutes earlier. Reviewing it would not
have found this. Only running it against a known violation did.

## Fix

A `self_check()` now runs before every scan — inside the guard itself, not only
in the test suite, because the mirror pipeline runs the guard and not the
tests. It refuses to scan at all if any of the following holds:

1. **A pattern contains a control character.** Any byte below `0x20` in a
   pattern's source fails — this catches the entire escaping-layer class, not
   just this instance. (Whitespace that a pattern legitimately needs is written
   as an escape sequence, `\t` or `\s`, which is two printable characters, so
   the rule has no exceptions to carve out.)
2. **A pattern does not compile.** Trivial, but it turns a typo'd pattern from
   a silent no-op into a hard failure.
3. **Two checks share an identifier.** Each check carries a slug, and a
   duplicate would silently orphan one check's fixture.

In addition, **each check has a positive fixture**: a synthetic file under
`tests/fixtures/` that must trip it. Two parametrised tests assert, for every
check, that its fixture fires it — and that the fixture fires *only* it, since
a fixture tripping two checks proves neither. A guard is only trusted while its
ability to fire is demonstrated on every run.

The fixture directory is excluded from the scan; it contains deliberate
violations, so without the exclusion the mirror would never publish. That
exclusion is itself guarded: the suite asserts the directory holds exactly the
declared fixtures and nothing else, that each is under 2 KB, and that without
the exclusion every one of them would be seen. The only unscanned corner of the
perimeter cannot become a hiding place.

## What the fixtures found immediately

Two defects, in the first run after they existed:

- One pattern used `\bterm\b` and therefore did not match `TERM_TARGET` — a
  trailing underscore is a word character, so the closing boundary never
  matched. A plausible real leak the guard would have missed. Widened.
- A blanket exemption for the substring `example` — added so that placeholder
  values in the sample config file would not trip the guard — also exempted a
  key literal reading `sk-ant-EXAMPLE…`: exactly the shape a real key wears
  when someone disguises it as a fake one. Removed, leaving only the one
  declared placeholder.

  (This sentence is written with the literal truncated. Spelled in full, the
  guard stops this very document — which it did, on the first run after the
  paragraph was written. A postmortem is not exempt from the control it
  describes.)

Neither was visible by reading. Both were obvious the moment a check was made
to face something it was supposed to stop.

## Generalization

Detection code needs its own tests, and they must include tests that the
detector *fires* — not only that it stays quiet on clean input. Testing only
the negative path proves nothing: silence is also what failure looks like.
This applies to any guard, linter rule, monitor, or alert: **who watches the
watchman** is not a philosophical question here; it is three assertions and a
fixture directory.

A corollary, learned from the same incident: a pattern is data, not code, and
data that passes through a text-generation pipeline before reaching a source
file can arrive silently altered. Where a value must be exact, assert on the
value — not on the fact that you typed it correctly.
