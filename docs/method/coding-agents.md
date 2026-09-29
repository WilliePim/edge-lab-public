# Working with coding agents

Most of the code, tests and documents in this repository were written by coding agents (Claude Code) working under
standing instructions in `CLAUDE.md`. This page describes those instructions and the checks that make them
enforceable. The principle behind all of them: an agent is fast and fluent, so every rule that matters is either
checked by code or verified against the real state of the repository, never taken on the agent's word.

## 1. Delegation and model routing

The main session plans and delegates; it does not do the work itself. Each task goes to a sub-agent, and the model is
chosen for the task:

| model (at the time of writing) | used for |
|---|---|
| Fable 5.1 | architecture, hard bugs, review |
| Opus 5 | edits, tests, documentation, refactors |
| Haiku 4.5 | lookups and summaries |

The strongest model is not the default: routine edits go to the cheaper one.

- The model is passed explicitly on every sub-agent call.
- One sub-agent per task, with a plan first.
- Independent sub-agents run in parallel (for example: one on infrastructure, one on the studies, one on the
  documentation, each with its own files and its own change log).
- The main session reads the sub-agent's report, not the files it touched; the report must therefore say what was
  checked and where.

## 2. The verification rule

> Every verification reads the real state: the content of the file, the output of the command, the registered task.
> Never a value written by the agent itself (a path typed by hand, an expected string copied into the check). In the
> report, for every verification, say what was read and from where.

The rule was written after a real failure: a fix was declared done because a check tested a path typed by hand,
while the file it was supposed to change had not changed. Related standing instructions:

- **Before stating how things are** in the repository or the data, check and say where you looked.
- **If a decision belongs to the owner, stop and ask**: do not take the most convenient path.
- **No new dependency without asking.** Frozen dataclasses and JSONL; no pydantic, no database.

## 3. Facts and judgements

The scanner computes **facts**: booleans and numbers derived from EDGAR by join or count, each with a declared,
reproducible rule. It does not produce **judgements**: no sentence that weighs, interprets or recommends, no merit
adjective, no ordering other than the declared one, no threshold that divides "good" from "bad" beyond declared
gates.

- A report delivers material, not conclusions: the text of the filing, numbers, dates, links. A summary is a
  compressed translation; if it contains an opinion the original does not, it is wrong.
- Control rule: if a sentence of a report cannot be traced to a field of a filing or to a rule in `RULES.md`, it does
  not belong there.
- No weight, criterion or threshold enters the score without a measurement on the corpus first and the owner's
  explicit consent afterwards.
- Missing data is `UNKNOWN`, never a pass; `UNKNOWN` stays distinguishable from "checked and clean".
- Extraction with an LLM is not a fact (it is not reproducible): every field carries a confidence and a verbatim
  source excerpt that must be found literally in the text sent; the extraction appears next to the facts and never
  changes them.

## 4. Rules turned into tests

Rules that an agent could break silently are checked on the syntax tree or on the documents, so that breaking them
fails the suite:

- **The LLM column cannot decide.** `tests/test_issuance_column.py` checks that the extraction never touches the
  blocking decision, the score or the ordering (`edgar_llm/docs/adr/004-mai-un-cancello.md`).
- **One door to the price archive.** `tests/test_market_data_confine.py` walks the AST of every module and allows only
  `market_data.api` as an import from the archive package, and no string pointing at archive files.
- **No dependency on external repositories.** A boundary test on the AST fails if a module imports, names or reads an
  external repository, with explicit exceptions that each state their reason; an exception that is no longer needed
  fails the test too.
- **Documents are tested.** `tests/test_citazioni.py` re-reads every `path#Lnn` citation in the rule documents and
  fails when the line no longer holds the symbol the sentence names.
- **Decision records exist.** A test checks that every ADR number cited in the repository exists in `DECISIONS.md`.
- **A public perimeter.** `edgar_llm/tools/perimeter_check.py` scans the `edgar_llm/` package for absolute paths,
  e-mail addresses, key-like strings, links outside the package and a deny-list of terms.

## 5. Guards before a commit

`.githooks/guard.py` runs as a pre-commit hook (`git config core.hooksPath .githooks`) and looks at the staging area,
that is at what the commit would actually contain. It blocks data files (`.parquet`, `.duckdb`, `.gz`, …), `.env`,
files over 5 MB, strings shaped like the price provider's API key (and the real key read from the environment),
and nested repositories. The message names the file and the reason, never the string found.

## 6. Pre-registration before returns

Research runs follow [preregistration.md](preregistration.md). For agents, the practical consequences are:

- the agent writes the pre-registration and the code, runs the counts, and **stops** at stop 1 without computing
  returns;
- the owner takes the open decisions; the agent writes them as a dated addendum and an ADR before going on;
- after the returns, the agent applies the registered criteria as written; any later idea is labelled post hoc and
  does not change the registered verdict;
- every non-obvious choice made while writing code is recorded as an ADR in `DECISIONS.md`, with context, decision,
  rejected alternatives, consequences and verification.

## 7. What agents are not trusted with

- choosing a threshold, a weight or a verdict criterion;
- deciding whether a failed validation can be "fixed";
- declaring a check passed without showing what was read;
- adding a dependency, pushing, or publishing.
