"""The two files a person actually reads, and the dedup that keeps them short.

`reports/daily_YYYY-MM-DD.md` is the list. `reports/spinoffs/_watch.md` is the
terrain: which spun-off daughters are inside their 90-day window right now.

WHY DEDUP LIVES HERE AND NOT IN A QUEUE. `emit.py` deduplicated on the score
(`dedup: str(card.score)`), so a name whose score moved from 5 to 6 came back as
new. The score is gone, and with it that whole class of false novelty.

WHAT REPLACES IT IS THE ACCESSION, not the cluster and not a date. An accession
number identifies the filing -- the purchase actually happened, once, and has a
permanent name given by the SEC. The ledger stores accessions, and an issuer is
new on a morning when it carries **at least one accession never recorded**.

Two weaker keys were tried and measured on the 247 issuers of the first
scheduled run, sliding the window forward:

    key                              +1d    +7d   +14d
    (issuer, first buy date)          0      12     --
    (issuer, SET of accessions)       0      12     17
    any accession never seen          0       0      0

The first two fail the same way and for the same reason: both describe the
cluster as the 60-day window currently frames it. When the oldest purchase ages
out the frame changes, so the key changes, and the same purchases are printed
again under a new name. The accession does not move, because it is a fact about
the filing rather than about the window looking at it.

An issuer with a genuinely new purchase reappears, carrying its older purchases
with it for context. That is the intended behaviour: the new filing is the
news, and the reader needs to see what it lands on.

The ledger is append-only, one JSON object per line, under `state/daily/`. It is
state, not a report: losing it costs one duplicated morning, not history.

NOTHING HERE JUDGES. CLAUDE.md, confine fra scanner e giudizio: these files
carry names, dates, counts and the flags the pipeline already produced, in the
order scan.py already fixed. No adjective, no recommendation, no ranking beyond
score_v3 desc then buyers in window desc.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

#  Import in cima, non dentro le funzioni: nessuno di questi importa `report`,
#  quindi non c'era nessun ciclo da schivare. Restano locali solo `watch` (che
#  gira dentro un try: un suo errore non deve portarsi via il rapporto) e
#  `edgar_llm`, che e' una dipendenza facoltativa.
from . import secdays
from . import verdicts as verdicts_mod
from .flags import bands_for_range, cap_bucket

log = logging.getLogger(__name__)

SPINOFF_WINDOW_DAYS = 90


def _ledger_path(state_dir) -> Path:
    return Path(state_dir) / "daily" / "seen.jsonl"


def load_seen(state_dir) -> set:
    """{accession} already printed on some earlier morning."""
    p = _ledger_path(state_dir)
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue                      # a torn line costs one duplicate
        acc = r.get("accession")
        if acc:
            out.add(str(acc))
    return out


def record_seen(state_dir, rows, run_date) -> Path:
    """`rows` = (cik, accession) pairs. Append-only, one line each."""
    p = _ledger_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for cik, acc in rows:
            fh.write(json.dumps({"cik": cik, "accession": acc,
                                 "first_seen": run_date.isoformat()},
                                sort_keys=True) + "\n")
    return p


def accessions_by_cik(clusters) -> dict:
    """{issuer cik without leading zeros: {accession, ...}} from the clusters."""
    out = {}
    for c in clusters or []:
        key = str(c.issuer_cik).lstrip("0")
        out.setdefault(key, set()).update(
            t.accession for t in c.txns if t.accession)
    return out


def card_accessions(card, acc_by_cik) -> set:
    return set(acc_by_cik.get(str(card.issuer_cik).lstrip("0"), ()))


# --------------------------------------------------------------- the notice --
def standing_notice() -> str | None:
    """The line at the top, derived from the code rather than typed into it.

    It has to disappear by itself when it stops being true, so every clause is
    read off the state it describes:

      * which gates can actually set `blocked` -- today only dilution
      * whether the sign gates run in the pipeline -- they do not, they live in
        tools/sign_gates_count.py, which is a measuring tool
      * whether score_v3 has a validated threshold -- it has none, M2 in queue

    Returns None once all three stop holding, and then the notice is simply not
    printed.
    """
    import inspect

    from . import flags as flags_mod

    pkg = Path(__file__).resolve().parent
    #  What can set Card.blocked, read off the property itself.
    #  ...e solo se il veto e' acceso: spento (default) il predicato e' solo informazione.
    from .dilution import VETO_ENV, veto_attivo
    dilution_vetoes = "dilution" in inspect.getsource(flags_mod.Card.blocked.fget) and veto_attivo()
    #  Whether the sign gates run in the pipeline, or only in the measuring
    #  tool under tools/. THIS FILE is excluded from its own test: the notice
    #  names NO_EBITDA in order to say it is absent, and counting that mention
    #  as presence made the clause delete itself the moment it was written.
    sign_gates_in_pipeline = any(
        "NO_EBITDA" in f.read_text(encoding="utf-8", errors="replace")
        for f in pkg.glob("*.py") if f.name != "report.py")
    #  Whether score_v3 has a measured threshold. None, by design, until M2.
    #  Il sentinella era "PASS_MARK", il nome della soglia del rubric v2: quel
    #  nome non tornera' (una soglia nuova nascerebbe da una misura e si
    #  chiamerebbe altrimenti), quindi la condizione era per sempre falsa e
    #  l'avviso non poteva piu' auto-cancellarsi. Ora si guarda il nome che la
    #  soglia avra' davvero se M2 la produce.
    has_threshold = "SOGLIA_SCORE_V3" in (pkg / "flags.py").read_text(
        encoding="utf-8", errors="replace")

    if not dilution_vetoes and sign_gates_in_pipeline and has_threshold:
        return None

    parts = []
    if dilution_vetoes:
        parts.append("Predicato che imposta blocked: diluizione (predicato, non validato)")
    else:
        parts.append("Veto diluizione implementato e spento finche' non e' validato ({} non acceso): "
                     "il predicato e' solo informativo, nessun nome e' fermato".format(VETO_ENV))
    if not sign_gates_in_pipeline:
        #  "10% owner" IS a flag on the card. NO_EBITDA is not: it is computed
        #  only in tools/sign_gates_count.py, outside the pipeline. Saying both
        #  are "in flag" would be the one false clause in a standing notice.
        parts.append("Solo flag di contesto: 10% owner. Fuori pipeline: "
                     "NO_EBITDA (tools/sign_gates_count.py, predicato non validato)")
    if not has_threshold:
        parts.append("Punteggio non validato (M2 in coda)")
    return ". ".join(parts) + "."


# ------------------------------------------------------ la colonna emissione --
#  Quanto indietro guardare per trovare il deposito che spiega un'emissione.
#  E' la stessa finestra del cancello diluizione (`check_dilution`,
#  lookback_days=540): la colonna deve parlare degli stessi depositi su cui il
#  verdetto si e' formato, altrimenti affianca al verdetto un fatto che il
#  verdetto non ha visto.
ISSUANCE_LOOKBACK_DAYS = 540


def issuance_column(fresh, client, run_date) -> dict:
    """{cik: testo} per gli emittenti nuovi. {} se l'estrazione non e' possibile.

    ARRICCHISCE, NON DECIDE. Nessuna riga qui tocca `blocked`, `v3` o
    l'ordinamento -- vedi edgar_llm/docs/adr/004-mai-un-cancello.md. Se il
    package non c'e', se la chiave non c'e', se EDGAR non risponde: il report
    esce identico a prima, con la colonna a trattino.

    Solo i NUOVI: sono ~13 al giorno contro i ~254 in lista, e una riga gia'
    letta ieri non ha bisogno di essere ripagata oggi.
    """
    if not fresh or client is None:
        return {}
    try:
        from edgar_llm import config as llm_config
        from edgar_llm.cache import RECORD, Cache
        from edgar_llm.client import LLMClient
        from edgar_llm.extract import latest_issuance, render
    except Exception:                                          # noqa: BLE001
        return {}

    #  INTERRUTTORE ESPLICITO, e spento di default. La chiave vive in `.env`
    #  perche' serve a etichettare e a misurare; trovarla non e' il consenso a
    #  spendere ogni mattina, da uno scheduler, per mettere in un report una
    #  colonna che nessuna eval ha ancora validato. Accendere questa variabile
    #  e' una decisione separata dall'avere la chiave, e va presa quando
    #  l'accuracy su `tipo` supera la soglia dichiarata.
    llm_config.load()
    if (os.environ.get("EDGAR_LLM_DAILY") or "").strip().lower() not in (
            "1", "true", "si", "yes", "on"):
        return {}

    llm, cache = LLMClient(), Cache()
    #  Senza chiave e in `record` non c'e' niente da leggere e niente da
    #  chiedere: si esce prima di scaricare una dozzina di documenti per poi
    #  scrivere UNKNOWN su tutti. In `replay` invece si prova: la cache
    #  potrebbe avere gia' le risposte.
    if not llm.available and cache.mode == RECORD:
        return {}

    since = (run_date - timedelta(days=ISSUANCE_LOOKBACK_DAYS)).isoformat()
    out = {}
    for c in fresh:
        cik = str(c.issuer_cik).lstrip("0")
        try:
            ev = latest_issuance(client, cik, since=since,
                                 until=run_date.isoformat(),
                                 llm=llm, cache=cache)
        except Exception as e:                                 # noqa: BLE001
            log.warning("estrazione fallita su %s: %s", cik, e)
            continue
        out[cik] = render(ev)
    return out


def _righe_sorveglianza(client, run_date, state_dir) -> list:
    """I nomi sorvegliati a mano, che vanno in cima al rapporto.

    In ALTO e prima di tutto: sono nomi che l'utente ha chiesto di guardare uno
    per uno, e un alert in fondo a trenta pagine e' un alert che non esiste. Se
    non e' scattato niente non si stampa nulla: una sezione vuota ogni mattina
    si smette di leggerla. Un errore qui non puo' portarsi via il rapporto -- il
    giro vale piu' dell'alert -- ma si dice invece di sparire.
    """
    try:
        from . import watch as watch_mod
        watches = watch_mod.load_watches()
        if not (watches and client is not None):
            return []
        hits = watch_mod.run(client, watches, run_date, state_dir)
        righe = list(watch_mod.render(hits, watches))
        watch_mod.record_seen(state_dir, hits, run_date)
        return righe
    except Exception as exc:                          # noqa: BLE001
        return ["> **Sorveglianza non eseguita:** {}".format(exc), ""]


def _righe_giorni_senza_indice(missing_index, run_date) -> list:
    """I giorni della finestra il cui indice EDGAR non e' stato letto.

    Un festivo, un indice non ancora pubblicato e un indice illeggibile erano
    tutti «giorno non osservato». Sono tre cose diverse, e contarle insieme
    sporcava la conta dei buchi di festivi -- un contatore che segnala sempre
    qualcosa si smette di guardare. Tre frasi intere, una per esito, ognuna
    nelle due forme: inflettere una frase sola a segnaposti produceva «non e' un
    giorno vuoti».
    """
    if not missing_index:
        return []
    groups = secdays.classify(missing_index, run_date)
    righe = [""]

    unread = groups[secdays.ILLEGGIBILE]
    if unread:
        dates = ", ".join(d for d, _ in unread)
        if len(unread) == 1:
            righe.append("**1 giorno della finestra NON OSSERVATO** — "
                         "l'indice EDGAR non e' stato letto per {}, e non e' "
                         "un festivo. Non e' un giorno vuoto: e' un giorno di "
                         "cui non si sa niente.".format(dates))
        else:
            righe.append("**{} giorni della finestra NON OSSERVATI** — "
                         "l'indice EDGAR non e' stato letto per {}, e non "
                         "sono festivi. Non sono giorni vuoti: sono giorni di "
                         "cui non si sa niente.".format(len(unread), dates))
        righe.append("")

    closed = groups[secdays.FESTIVO] + groups[secdays.CHIUSURA]
    if closed:
        which = ", ".join("{} ({})".format(d, w) for d, w in closed)
        if len(closed) == 1:
            righe.append("1 giorno senza depositi perche' EDGAR era chiusa: "
                         "{}. Non e' un buco.".format(which))
        else:
            righe.append("{} giorni senza depositi perche' EDGAR era chiusa: "
                         "{}. Non sono buchi.".format(len(closed), which))
        righe.append("")

    pending = groups[secdays.NON_ANCORA]
    if pending:
        dates = ", ".join(d for d, _ in pending)
        if len(pending) == 1:
            righe.append("1 giorno con l'indice non ancora pubblicato quando "
                         "il giro e' partito: {}. Si legge al giro di "
                         "domani.".format(dates))
        else:
            righe.append("{} giorni con l'indice non ancora pubblicato quando "
                         "il giro e' partito: {}. Si leggono ai giri "
                         "successivi.".format(len(pending), dates))
        righe.append("")
    return righe


# ---------------------------------------------------------- the daily list --
def write_daily(cards, out_dir, run_date, state_dir, window_days,
                funnel=None, edgar=None, seconds=None,
                missing_index=None, clusters=None, ticker_status=None,
                min_cap=None, max_cap=None, client=None) -> tuple:
    """reports/daily_YYYY-MM-DD.md. Returns (path, new_rows, repeat_rows)."""
    out = Path(out_dir) / "daily_{}.md".format(run_date.isoformat())
    out.parent.mkdir(parents=True, exist_ok=True)

    verdicts = verdicts_mod.current()

    shown = [c for c in cards if not c.blocked]
    seen = load_seen(state_dir)
    acc_by_cik = accessions_by_cik(clusters)
    #  New = carries at least one accession never recorded. Not "its set of
    #  accessions changed": that key moves when the window slides past the
    #  oldest purchase, and reprints purchases already read.
    fresh = [c for c in shown if card_accessions(c, acc_by_cik) - seen]
    repeat = [c for c in shown if not (card_accessions(c, acc_by_cik) - seen)]
    issuance = issuance_column(fresh, client, run_date)

    righe = []
    notice = standing_notice()
    if notice:
        righe.append("> **{}**".format(notice))
        righe.append("")
    righe.append("# Form 4 — {}".format(run_date.isoformat()))
    righe.append("")
    if min_cap is not None and max_cap is not None:
        righe.append("Universo: fasce **{}** (cap ${:,.0f}-${:,.0f})."
                 .format(", ".join(bands_for_range(min_cap, max_cap)),
                         min_cap, max_cap))
        righe.append("")
    righe.append("Finestra {} giorni, chiusa il {}. "
             "{} emittenti valutati, {} passati i cancelli, "
             "**{} nuovi** e {} gia' visti in una mattina precedente."
             .format(window_days, run_date.isoformat(), len(cards),
                     len(shown), len(fresh), len(repeat)))
    righe.append("")

    righe.extend(_righe_sorveglianza(client, run_date, state_dir))

    if fresh:
        righe.append("## Nuovi")
        righe.append("")
        righe.append("| score_v3 | booleani | ticker | emittente | $ acquisti | "
                 "compratori 30gg | primo acquisto | cancelli | emissione | "
                 "verdetto |")
        righe.append("|---:|---|---|---|---:|---:|---|---|---|---|")
        for c in fresh:
            righe.append(_row(c, verdicts, issuance))
        righe.append("")
        for c in fresh:
            if c.flags:
                righe.append("**{}** — {}".format(c.ticker or c.issuer_cik,
                                              " · ".join(c.flags)))
                righe.append("")
    else:
        righe.append("## Nuovi")
        righe.append("")
        righe.append("Nessuno. Ogni emittente in finestra era gia' in lista.")
        righe.append("")

    if repeat:
        righe.append("## Gia' visti — stessi acquisti, ripetuti dalla finestra mobile")
        righe.append("")
        righe.append("| ticker | emittente | primo acquisto |")
        righe.append("|---|---|---|")
        for c in repeat:
            righe.append("| {} | {} | {} |".format(
                c.ticker or "—", c.issuer_name[:44],
                c.context.get("first_buy_date") or "—"))
        righe.append("")

    blocked = [c for c in cards if c.blocked]
    if blocked:
        righe.append("## Fermati dal cancello diluizione")
        righe.append("")
        for c in blocked:
            why = c.dilution.summary() if c.dilution else ""
            righe.append("- **{}** {} — {}".format(
                c.ticker or "—", c.issuer_name[:44], why))
        righe.append("")

    righe.append("---")
    righe.append("")
    righe.append("## Il giro")
    righe.append("")
    if funnel:
        righe.append("| passo | N |")
        righe.append("|---|---:|")
        for k in ("qualifying_purchases", "issuers_with_buying",
                  "issuers_in_cap_band", "issuers_past_dilution_gate",
                  "distinct_insiders_classified", "issuers_evaluated"):
            if k in funnel:
                righe.append("| {} | {:,} |".format(k.replace("_", " "), funnel[k]))
        righe.append("")
    if seconds is not None:
        righe.append("Durata **{:.0f}s** ({:.1f} min).".format(seconds, seconds / 60))
    righe.extend(_righe_giorni_senza_indice(missing_index, run_date))

    if ticker_status:
        corretti = ticker_status.get("corretto", 0)
        ambigui = ticker_status.get("ambiguo", 0)
        pezzi = []
        if corretti:
            pezzi.append("{} simbol{} aggiornat{} sul CIK".format(
                corretti, "o" if corretti == 1 else "i",
                "o" if corretti == 1 else "i"))
        if ambigui:
            #  Il CIK ha piu' di una classe quotata: correggere sarebbe
            #  scegliere fra Class A e Class B, e non si indovina.
            pezzi.append("{} non risolt{} perche' il CIK ha piu' di una classe "
                         "quotata".format(ambigui, "o" if ambigui == 1 else "i"))
        if pezzi:
            righe.append("")
            righe.append("Simboli: {}. Il ticker di un Form 4 lo scrive il "
                     "depositante e puo' essere stantio; i prezzi si cercano "
                     "per simbolo.".format(", ".join(pezzi)))
            righe.append("")

    if issuance:
        noti = sum(1 for v in issuance.values() if v not in ("—", "UNKNOWN"))
        righe.append("")
        righe.append("Colonna `emissione`: {} emittenti nuovi interrogati, {} con "
                 "un tipo sopra soglia. E' materiale, non un cancello -- non "
                 "tocca `blocked`, `score_v3` ne' l'ordine "
                 "(`edgar_llm/docs/adr/004-mai-un-cancello.md`).".format(
                     len(issuance), noti))
        righe.append("")
    if edgar:
        righe.append("EDGAR: **{:,} chiamate di rete**, {:,} servite dalla cache, "
                 "{:,} backoff, {:,} fallite.".format(
                     edgar.get("network", 0), edgar.get("cache", 0),
                     edgar.get("backoff", 0), edgar.get("fail", 0)))
    righe.append("")

    out.write_text("\n".join(righe) + "\n", encoding="utf-8")
    #  Every accession on every issuer shown, not only the new ones: an issuer
    #  that reappears for one new filing must not leave its older filings
    #  unrecorded, or they read as new the next time the frame moves.
    record_seen(state_dir,
                sorted({(str(c.issuer_cik), a) for c in shown
                        for a in card_accessions(c, acc_by_cik) - seen}),
                run_date)
    return out, len(fresh), len(repeat)


def _row(c, verdicts=None, issuance=None) -> str:
    got = [k for k in ("cluster", "director", "no_10pct", "terreno")
           if c.v3.get(k) is True]
    #  Solo visualizzazione: il verdetto e' dell'operatore, e comparire in questa
    #  colonna non lo rende un output dello scanner.
    v = (verdicts or {}).get(str(c.issuer_cik).lstrip("0"))
    vtxt = "{} ({})".format(v["verdict"], v["date"]) if v else "—"
    #  Materiale accanto al verdetto, non al posto suo: il tipo estratto dal
    #  testo del deposito e la confidence che lo accompagna. Non ordina niente.
    em = (issuance or {}).get(str(c.issuer_cik).lstrip("0"), "—")
    return "| {} | {} | {} | {} | ${:,.0f} | {} | {} | {} | {} | {} |".format(
        c.v3.get("score", 0), "+".join(got) or "—",
        c.ticker or "—", c.issuer_name[:40],
        c.context.get("total_value") or 0,
        (c.inputs.get("cluster") or {}).get("buyers_in_window", "—"),
        c.context.get("first_buy_date") or "—",
        c.context.get("dilution") or "—", em, vtxt)


# ------------------------------------------------------ the spin-off watch --
def write_daughter(daughter, cluster, snap, out_dir, run_date) -> Path:
    """reports/spinoffs/YYYY-MM-DD_TICKER.md -- material, not a conclusion.

    Every line is a field of the Form 4 or a number derived from one by a rule
    in RULES.md. No adjective, no ranking, no view.
    """

    #  Un ticker puo' contenere una barra (classi: BRK/B): la stessa sostituzione
    #  che fa il panel prezzi piu' sotto, o il percorso si spezza in due.
    tick = (cluster.ticker or daughter.get("ticker") or
            daughter.get("cik"))
    out = Path(out_dir) / "spinoffs" / "{}_{}.md".format(
        run_date.isoformat(), tick)
    out.parent.mkdir(parents=True, exist_ok=True)

    cap = getattr(snap, "market_cap", None)
    px_now = getattr(snap, "price", None)
    #  Shares outstanding implied by the snapshot. Declared as derived: the
    #  cover-page count belongs to the index, and this file is written from
    #  what the live path has in hand.
    shares_out = (cap / px_now) if (cap and px_now) else None
    d = daughter.get("date_distribution")

    righe = ["# {} — {}".format(cluster.issuer_name, tick), ""]
    righe.append("| | |")
    righe.append("|---|---|")
    righe.append("| CIK | {} |".format(cluster.issuer_cik))
    righe.append("| distribuzione | {} |".format(d))
    righe.append("| giorno della finestra | +{} di {} |".format(
        (run_date - date.fromisoformat(d)).days, SPINOFF_WINDOW_DAYS)
        if d else "| giorno della finestra | — |")
    righe.append("| capitalizzazione | {} |".format(
        "${:,.0f}".format(cap) if cap else "—"))
    righe.append("| fascia | **{}** |".format(cap_bucket(cap)))
    vd = verdicts_mod.current().get(str(cluster.issuer_cik).lstrip("0"))
    if vd:
        righe.append("| verdetto | **{}** ({}) |".format(vd["verdict"], vd["date"]))
        righe.append("| tesi | {} |".format(vd["thesis"]))
    righe.append("| azioni in circolazione (implicite) | {} |".format(
        "{:,.0f}".format(shares_out) if shares_out else "—"))
    righe.append("")

    righe.append("## Acquisti nella finestra di scansione")
    righe.append("")
    righe.append("| data | compratore | ruolo | azioni | prezzo | valore | "
             "% del capitale |")
    righe.append("|---|---|---|---:|---:|---:|---:|")
    for t in sorted(cluster.txns, key=lambda t: (t.txn_date or date.min,
                                                 t.txn_index)):
        roles = []
        if t.is_director:
            roles.append("Director")
        if t.is_officer:
            roles.append(t.officer_title or "Officer")
        if t.is_ten_pct:
            roles.append("10% Owner")
        pct = ("{:.3f}%".format(100 * t.shares / shares_out)
               if shares_out and t.shares else "—")
        righe.append("| {} | {} | {} | {:,.0f} | ${:,.2f} | ${:,.0f} | {} |".format(
            t.txn_date, t.owner_name, ", ".join(roles) or "—",
            t.shares or 0, t.price or 0, t.value or 0, pct))
    righe.append("")
    tot = sum(t.value or 0 for t in cluster.txns)
    tot_sh = sum(t.shares or 0 for t in cluster.txns)
    righe.append("Totale **${:,.0f}** su {:,.0f} azioni{}.".format(
        tot, tot_sh,
        ", pari al {:.3f}% del capitale".format(100 * tot_sh / shares_out)
        if shares_out else ""))
    righe.append("")
    righe.append("---")
    righe.append("")
    righe.append("Ancora e finestra: [RULES.md §5](../../RULES.md). Fasce: §6. "
             "Questo file riporta campi del Form 4 e numeri che ne derivano; "
             "il giudizio non e' dello scanner.")
    out.write_text("\n".join(righe) + "\n", encoding="utf-8")
    return out


def write_spinoff_watch(cards, out_dir, run_date,
                        index_path=None, window_days=SPINOFF_WINDOW_DAYS,
                        all_clusters=None, all_snaps=None) -> Path:
    """reports/spinoffs/_watch.md -- the daughters whose window is open today.

    Rewritten every run, not appended: it answers "what is open now", and a
    file that answers that has no use for last week's answer.
    """
    root = Path(__file__).resolve().parents[1]
    index_path = Path(index_path or (root / "data" / "spinoffs_index.json"))
    out = Path(out_dir) / "spinoffs" / "_watch.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    righe = ["# Terreno spin-off — finestre aperte al {}".format(run_date.isoformat()),
         ""]
    if not index_path.exists():
        righe.append("`data/spinoffs_index.json` non esiste: `terreno` vale `None` "
                 "su ogni riga e non c'e' niente da sorvegliare.")
        out.write_text("\n".join(righe) + "\n", encoding="utf-8")
        return out


    idx = json.loads(index_path.read_text(encoding="utf-8"))
    kids = idx.get("children", [])
    #  The join runs on EVERY issuer with insider buying, not on the cards the
    #  cap gate left behind. The ceiling decides the general list; it must not
    #  decide whether a spin-off daughter is looked at.
    by_cik = {str(c.issuer_cik).lstrip("0"): c for c in (all_clusters or [])}
    snaps = {str(k).lstrip("0"): v for k, v in (all_snaps or {}).items()}
    scanned = {str(c.issuer_cik).lstrip("0"): c for c in cards}

    open_now, closing, written = [], [], []
    for k in kids:
        try:
            d = date.fromisoformat(k.get("date_distribution") or "")
        except ValueError:
            continue
        age = (run_date - d).days
        if 0 <= age <= window_days:
            open_now.append((k, age))
        elif window_days < age <= window_days + 30:
            closing.append((k, age))

    righe.append("Indice: **{} figlie**, generato il {}. Finestra {} giorni dalla "
             "distribuzione.".format(len(kids), idx.get("generated", "?"),
                                     window_days))
    righe.append("")
    righe.append("## Finestra aperta oggi — {}".format(len(open_now)))
    righe.append("")
    if open_now:
        righe.append("| figlia | ticker | distribuzione | giorno | restano | "
                 "fascia | acquisti insider oggi |")
        righe.append("|---|---|---|---:|---:|---|---|")
        for k, age in sorted(open_now, key=lambda x: x[1]):
            cik = str(k.get("cik", "")).lstrip("0")
            cl = by_cik.get(cik)
            snap = snaps.get(cik)
            band = cap_bucket(getattr(snap, "market_cap", None))
            if cl is not None:
                dp = write_daughter(k, cl, snap, out_dir, run_date)
                here = "**si'** -- {} ({})".format(
                    dp.name, "in lista" if cik in scanned
                    else "fuori dal tetto della lista generale")
                written.append(dp)
            else:
                here = "no"
            righe.append("| {} | {} | {} | +{} | {} | {} | {} |".format(
                (k.get("name") or "")[:40],
                (cl.ticker if cl is not None else None) or k.get("ticker") or "—",
                k.get("date_distribution"), age, window_days - age, band, here))
    else:
        righe.append("Nessuna. La figlia piu' recente dell'indice e' stata "
                 "distribuita il {}.".format(
                     max((k.get("date_distribution") or "" for k in kids),
                         default="—")))
    righe.append("")

    if closing:
        righe.append("## Chiuse negli ultimi 30 giorni — {}".format(len(closing)))
        righe.append("")
        righe.append("| figlia | ticker | distribuzione | chiusa da |")
        righe.append("|---|---|---|---:|")
        for k, age in sorted(closing, key=lambda x: x[1]):
            righe.append("| {} | {} | {} | {} giorni |".format(
                (k.get("name") or "")[:40], k.get("ticker") or "—",
                k.get("date_distribution"), age - window_days))
        righe.append("")

    righe.append("---")
    righe.append("")
    righe.append("righe'ancora e' il primo burst Section 16, non la distribuzione "
             "effettiva: il Form 3 ha 10 giorni di termine, quindi la data puo' "
             "ritardare fino a 10gg e la finestra eredita lo scarto. "
             "[RULES.md §5](../../RULES.md).")
    out.write_text("\n".join(righe) + "\n", encoding="utf-8")
    return out


def ew_sub2e9_return(from_iso, to_date, state_dir):
    """(rendimento equipesato dell'universo sub-2e9 fra due date, numero di titoli).

    Il rendimento e' None quando il paniere non si puo' calcolare; il secondo
    valore dice su quanti titoli e' stato fatto, ed e' la copertura.

    DEFINIZIONE, dichiarata perche' un benchmark non dichiarato non e' un
    benchmark: gli emittenti dell'ultimo file di observations con data <=
    `from_iso` la cui `cap_bucket` sta in {micro, small}, per i quali il panel
    prezzi copre entrambi gli estremi. Media semplice dei rendimenti, in punti
    percentuali. Chi non ha prezzi a entrambi gli estremi esce dal paniere, e
    la copertura si legge dal numero di membri.

    Il panel e' storico e puo' essere piu' vecchio di oggi: quando non copre
    l'estremo destro la funzione restituisce None invece di un numero costruito
    su meta' paniere.
    """
    obs_dir = Path(state_dir) / "observations" / "form4"
    prices = Path(state_dir) / "backfill" / "prices"
    if not obs_dir.exists() or not prices.exists():
        return None, 0
    files = sorted(f for f in obs_dir.glob("*.jsonl") if f.stem <= from_iso)
    if not files:
        return None, 0
    tickers = set()
    for line in files[-1].read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("kind") != "observation":
            continue
        if (r.get("context") or {}).get("cap_bucket") in ("micro", "small"):
            t = (r.get("ticker") or "").upper()
            if t and t not in ("NONE", "N/A"):
                tickers.add(t)

    rets = []
    for t in sorted(tickers):
        f = prices / "{}.csv".format(t.replace("/", "_"))
        if not f.exists():
            continue
        #  Il panel e' scritto in ordine di data da tools/fetch_missing_prices.py:
        #  `a` e' la prima riga dall'estremo sinistro, `b` l'ultima fino al destro.
        a = b = None
        with f.open(encoding="utf-8") as fh:
            next(fh, None)
            for line in fh:
                d, _, val = line.partition(",")
                d = d.strip()
                try:
                    px = float(val)
                except ValueError:
                    continue
                if a is None and d >= from_iso:
                    a = px
                if d <= to_date.isoformat():
                    b = px
        if a and b and a > 0:
            rets.append((b / a - 1.0) * 100.0)
    #  Sotto i 20 titoli il paniere non e' l'universo, e' un campione: si dice
    #  None invece di pubblicare una media di quattro nomi come se fosse il mercato.
    if len(rets) < 20:
        return None, len(rets)
    return sum(rets) / len(rets), len(rets)



# ------------------------------------------------ il mensile sui verdetti --
def write_verdict_report(out_dir, run_date, snapshot_for, universe_caps=None,
                         path=None) -> Path:
    """reports/verdicts_YYYY-MM.md -- l'unico posto dove lo scanner tocca i
    verdetti, e li tocca solo per misurarli.

    `snapshot_for(ticker)` restituisce la fotografia di mercato di oggi;
    `universe_caps` e' {ticker: (prezzo di allora, prezzo di oggi)} per gli
    emittenti sub-2e9 che fanno da benchmark equipesato.

    Nessun commento, nessun aggettivo. Giorni, prezzi, rendimenti, e se una
    condizione di invalidazione si e' avverata.
    """

    cur = verdicts_mod.current(path)
    out = Path(out_dir) / "verdicts_{}.md".format(run_date.strftime("%Y-%m"))
    out.parent.mkdir(parents=True, exist_ok=True)

    righe = ["# Verdetti — {}".format(run_date.strftime("%Y-%m")), ""]
    if not cur:
        righe.append("Nessun verdetto in vigore.")
        out.write_text("\n".join(righe) + "\n", encoding="utf-8")
        return out

    righe.append("{} verdetti in vigore al {}. Il verdetto e' dell'operatore; questa "
             "pagina lo misura e basta.".format(len(cur), run_date.isoformat()))
    righe.append("")
    righe.append("| ticker | verdetto | data | giorni | prezzo allora | prezzo ora "
             "| rendimento | eccesso vs EW sub-2e9 | invalidazione | rivedere |")
    righe.append("|---|---|---|---:|---:|---:|---:|---:|---|---|")

    rows = []
    for cik, r in sorted(cur.items(), key=lambda kv: kv[1]["date"]):
        d0 = date.fromisoformat(r["date"])
        days = (run_date - d0).days
        p0 = r.get("price_at_verdict")
        snap = snapshot_for(r.get("ticker"))
        p1 = getattr(snap, "price", None)
        ret = ((p1 / p0 - 1.0) * 100.0) if (p0 and p1) else None
        bench = (universe_caps or {}).get(r["date"])
        exc = (ret - bench) if (ret is not None and bench is not None) else None

        hits, partial, unknown = [], [], []
        for cond in r.get("invalidation", []):
            ok, why = verdicts_mod.check_invalidation(cond, p1)
            if ok is True:
                hits.append("«{}» — {}".format(cond, why))
            elif ok is None and "resta da verificare" in why:
                partial.append("«{}» — {}".format(cond, why))
            elif ok is None:
                unknown.append("«{}»".format(cond))
        if hits:
            inval = "**si'** — {}".format("; ".join(hits))
        elif partial:
            inval = "; ".join(partial)
        elif unknown:
            inval = "non verificabile — {}".format("; ".join(unknown))
        else:
            inval = "no"

        rev = r.get("review_date")
        overdue = "**si'**" if (rev and rev < run_date.isoformat()) else "no"

        righe.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r.get("ticker") or cik, r["verdict"], r["date"], days,
            "${:.2f}".format(p0) if p0 else "—",
            "${:.2f}".format(p1) if p1 else "—",
            "{:+.1f}%".format(ret) if ret is not None else "—",
            "{:+.1f}pp".format(exc) if exc is not None else "—",
            inval, overdue))
        rows.append((r["verdict"], exc, bool(hits)))

    righe.append("")
    righe.append("## Per classe")
    righe.append("")
    righe.append("| classe | n | mediana eccesso | invalidazioni scattate |")
    righe.append("|---|---:|---:|---:|")
    for cls in verdicts_mod.CLASSES:
        sel = [r for r in rows if r[0] == cls]
        if not sel:
            continue
        exs = sorted(x for _, x, _ in sel if x is not None)
        med = (exs[len(exs) // 2] if len(exs) % 2 else
               (exs[len(exs) // 2 - 1] + exs[len(exs) // 2]) / 2.0) if exs else None
        righe.append("| {} | {} | {} | {}/{} |".format(
            cls, len(sel),
            "{:+.1f}pp".format(med) if med is not None else "—",
            sum(1 for _, _, h in sel if h), len(sel)))
    righe.append("")
    righe.append("---")
    righe.append("")
    righe.append("Le condizioni di invalidazione sono scritte da un essere umano. "
             "Lo scanner ne verifica solo quelle che confrontano un prezzo con "
             "un numero; «senza notizie» o «crescita di un segmento < 7%» sono marcate "
             "**non verificabili** e riportate alla lettera, perche' "
             "interpretarle sarebbe il giudizio che allo scanner e' vietato "
             "([CLAUDE.md](../CLAUDE.md)).")
    out.write_text("\n".join(righe) + "\n", encoding="utf-8")
    return out
