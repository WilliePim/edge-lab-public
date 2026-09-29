"""Le evals: quanto spesso l'estrazione dice cio' che c'e' scritto.

    python -m edgar_llm.eval                    # dal golden set, modo da env
    python -m edgar_llm.eval --replay           # senza chiave, dalla cache
    python -m edgar_llm.eval --prompt v2 --out docs/evals

NESSUN PROMPT SI CAMBIA SENZA RIESEGUIRE QUESTO. La regola e' applicabile
perche' la chiave di cache include `prompt_version` (ADR-005): un prompt nuovo
non puo' riusare le risposte del vecchio nemmeno per sbaglio.

COME SI CONFRONTANO CINQUE CAMPI DI NATURA DIVERSA. `tipo` e `data_efficacia`
sono chiusi e si confrontano per uguaglianza. `importo_usd` e' un numero: si
riporta l'errore assoluto mediano e la quota di corrispondenze esatte.
`controparte` e' testo libero e si confronta per contenimento normalizzato, che
e' generoso e va detto. `condizioni` NON si punteggia: e' prosa, due sintesi
corrette possono non avere una parola in comune, e un punteggio inventato su di
esse sarebbe peggio di nessun punteggio. Se ne riporta solo la copertura.
"""

from __future__ import annotations

import argparse
import collections
import re
import statistics
import sys
from datetime import date
from pathlib import Path

from .attribuzione import (ASSENTE, DENTRO, FUORI, NON_DETERMINABILE,
                           dove_sta)
from .cache import RECORD, REPLAY, Cache
from .client import LLMClient
from .edgar import EdgarClient
from .extract import PROMPT_VERSION, extract_filing
from .fetch import document_text, windows
from .goldens import GoldenChanged, load, rehydrate
from .schema import TIPI

CHIUSI = ("tipo", "data_efficacia")
NUMERICI = ("importo_usd",)
TESTUALI = ("controparte",)
NON_PUNTEGGIATI = ("condizioni",)

DOCS = Path(__file__).resolve().parent / "docs" / "evals"

#  Soglia di produzione, dall'handoff. E' il solo numero di merito in questo
#  file, ed e' un requisito dichiarato, non una scoperta.
SOGLIA_TIPO = 0.90

_WS = re.compile(r"\s+")


def _norm(s):
    return _WS.sub(" ", str(s or "")).strip().lower()


def _contiene(atteso, avuto) -> bool:
    a, b = _norm(atteso), _norm(avuto)
    if not a or not b:
        return False
    return a in b or b in a


def confronta(golden, ev):
    """{campo: ('ok'|'ko'|'entrambi_null'|'mancante'|'inventato', atteso, avuto)}."""
    out = {}
    for campo in CHIUSI + NUMERICI + TESTUALI + NON_PUNTEGGIATI:
        atteso = golden.labels.get(campo)
        f = getattr(ev, campo)
        avuto = f.value if f.usable else None

        if atteso is None and avuto is None:
            esito = "entrambi_null"
        elif atteso is None:
            esito = "inventato"          # il documento non lo dice, il modello si'
        elif avuto is None:
            esito = "mancante"
        elif campo in NUMERICI:
            esito = "ok" if abs(float(atteso) - float(avuto)) < 1.0 else "ko"
        elif campo in TESTUALI:
            esito = "ok" if _contiene(atteso, avuto) else "ko"
        elif campo in NON_PUNTEGGIATI:
            esito = "entrambi_pieni"
        else:
            esito = "ok" if _norm(atteso) == _norm(avuto) else "ko"
        out[campo] = (esito, atteso, avuto)
    return out


def accuracy(esiti) -> tuple:
    """(giusti, valutabili). `entrambi_null` conta come giusto: dire 'non c'e''
    quando non c'e' e' la risposta corretta, non un'astensione."""
    giusti = sum(1 for e, _, _ in esiti if e in ("ok", "entrambi_null"))
    valutabili = sum(1 for e, _, _ in esiti
                     if e in ("ok", "ko", "entrambi_null", "mancante", "inventato"))
    return giusti, valutabili


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prompt", default=PROMPT_VERSION)
    ap.add_argument("--replay", action="store_true",
                    help="solo cache: nessuna chiamata, nessuna chiave")
    ap.add_argument("--out", default=str(DOCS))
    ap.add_argument("--store", default=None)
    a = ap.parse_args(argv)

    goldens = load(Path(a.store) if a.store else None)
    if not goldens:
        print("golden set vuoto. Etichetta con `python -m edgar_llm.label`.")
        return 2

    edgar = EdgarClient()
    llm = LLMClient()
    cache = Cache(mode=REPLAY if a.replay else None)
    print("golden: {}   prompt: {}   modo: {}".format(
        len(goldens), a.prompt, cache.mode))

    righe, cambiati = [], []
    for g in goldens:
        try:
            rehydrate(g, edgar)
        except GoldenChanged as e:
            #  Un golden il cui documento e' cambiato non si valuta in
            #  silenzio: si dichiara e si toglie dal campione.
            cambiati.append(str(e))
            continue
        ev = extract_filing(g.filing, edgar, llm=llm, cache=cache,
                            prompt_version=a.prompt)
        conf = confronta(g, ev)
        #  Per ogni errore: l'informazione stava nelle finestre o no. E' la
        #  differenza fra "il modello non l'ha letta" e "non gliel'abbiamo
        #  mandata", e si correggono in modi opposti.
        testo = document_text(edgar, g.filing)
        sent = windows(testo)
        dove = {}
        for campo, (esito, atteso, _avuto) in conf.items():
            dove[campo] = (dove_sta(campo, atteso, sent, testo)
                           if esito in ("ko", "mancante") else None)
        righe.append((g, ev, conf, dove, len(sent), len(testo)))

    if not righe:
        print("nessun golden valutabile.")
        return 1

    run_date = date.today().isoformat()
    L = ["# Evals — prompt `{}`".format(a.prompt), "",
         "Generato il {} da `python -m edgar_llm.eval --prompt {}`. "
         "Campione: **{} golden** su {} nel set.".format(
             run_date, a.prompt, len(righe), len(goldens)), "",
         "Modello: `{}`. Modo cache: `{}`.".format(llm.model, cache.mode), ""]

    # --- per campo ---
    L += ["## Per campo", "",
          "| campo | giusti | valutabili | accuracy |", "|---|---:|---:|---:|"]
    tipo_acc = None
    for campo in CHIUSI + NUMERICI + TESTUALI:
        esiti = [c[campo] for r in righe for c in [r[2]]]
        g_, v_ = accuracy(esiti)
        acc = g_ / v_ if v_ else 0.0
        if campo == "tipo":
            tipo_acc = acc
        L.append("| `{}` | {} | {} | **{:.1%}** |".format(campo, g_, v_, acc))
    for campo in NON_PUNTEGGIATI:
        pieni = sum(1 for r in righe for c in [r[2]] if c[campo][2] is not None)
        L.append("| `{}` | — | — | copertura {}/{} |".format(
            campo, pieni, len(righe)))
    L += ["", "`condizioni` non si punteggia: e' prosa libera, due sintesi "
          "corrette possono non avere una parola in comune. `controparte` si "
          "confronta per contenimento normalizzato, che e' generoso.", ""]

    # --- la soglia ---
    if tipo_acc is not None:
        esito = "RAGGIUNTA" if tipo_acc >= SOGLIA_TIPO else "NON raggiunta"
        L += ["## Soglia di produzione", "",
              "Accuracy su `tipo` **{:.1%}** contro la soglia dichiarata del "
              "{:.0%}: **{}**.".format(tipo_acc, SOGLIA_TIPO, esito), ""]

    # --- errori del tipo ---
    matrice = collections.Counter()
    for r in righe:
        e, atteso, avuto = r[2]["tipo"]
        if e in ("ko", "mancante", "inventato"):
            matrice[(atteso, avuto)] += 1
    conf = matrice
    if conf:
        L += ["## Dove `tipo` sbaglia", "",
              "| atteso | estratto | n |", "|---|---|---:|"]
        for (atteso, avuto), n in conf.most_common():
            L.append("| {} | {} | {} |".format(atteso or "—", avuto or "—", n))
        L.append("")

    # --- importo ---
    scarti = [abs(float(c["importo_usd"][1]) - float(c["importo_usd"][2]))
              for r in righe for c in [r[2]]
              if c["importo_usd"][0] in ("ok", "ko")]
    if scarti:
        L += ["## `importo_usd`", "",
              "Errore assoluto mediano **${:,.0f}** su {} confronti; esatti "
              "entro $1: {}.".format(statistics.median(scarti), len(scarti),
                                     sum(1 for s in scarti if s < 1.0)), ""]

    # --- per forma ---
    per_forma = collections.defaultdict(list)
    for r in righe:
        g, c = r[0], r[2]
        per_forma["8-K/2.01" if g.form == "8-K" else g.form].append(c["tipo"])
    L += ["## Per forma di deposito", "",
          "La resa della troncatura non e' uniforme (`docs/costs.md`): un 8-K "
          "entra quasi intero, un 424B3 lungo entra all'1%. Qui si vede se si "
          "paga.", "",
          "| forma | n | accuracy su `tipo` |", "|---|---:|---:|"]
    for forma, esiti in sorted(per_forma.items()):
        g_, v_ = accuracy(esiti)
        L.append("| {} | {} | {:.1%} |".format(forma, len(esiti),
                                               g_ / v_ if v_ else 0.0))
    L.append("")

    # --- di chi e' la colpa: del modello o del taglio ---
    quota = collections.Counter()
    per_campo = collections.defaultdict(collections.Counter)
    dettaglio = []
    for r in righe:
        g, c, dove = r[0], r[2], r[3]
        for campo, d in dove.items():
            if d is None:
                continue
            quota[d] += 1
            per_campo[campo][d] += 1
            if d == FUORI:
                dettaglio.append((g, campo, c[campo][1], r[4], r[5]))

    L += ["---", "", "## Di chi e' l'errore: del modello o del taglio", "",
          "Per ogni campo sbagliato o mancante si cerca la forma superficiale "
          "del valore VERO prima nelle finestre inviate, poi nel documento "
          "intero. **`dentro`** vuol dire che l'informazione c'era e il modello "
          "non l'ha usata: si lavora sul prompt. **`fuori`** vuol dire che non "
          "gliel'abbiamo mandata: nessuna istruzione fa leggere una frase che "
          "non e' nel prompt, e va allargato il taglio. Sono guasti opposti e "
          "si correggono in modi opposti.", "",
          "`assente` e' il valore che non si trova ne' qui ne' la': "
          "un'etichetta che non e' una citazione, o un numero che la "
          "conversione HTML->testo ha smontato. `n.d.` sono `tipo` e "
          "`condizioni`, che nel documento non hanno una forma scritta da "
          "cercare — il primo e' una classificazione, il secondo una sintesi.",
          ""]
    if not quota:
        L += ["Nessun errore da attribuire.", ""]
    else:
        L += ["| esito | n | quota |", "|---|---:|---:|"]
        tot = sum(quota.values())
        for k in (DENTRO, FUORI, ASSENTE, NON_DETERMINABILE):
            if quota[k]:
                L.append("| `{}` | {} | {:.0%} |".format(k, quota[k],
                                                         quota[k] / tot))
        L += ["", "| campo | dentro | fuori | assente | n.d. |",
              "|---|---:|---:|---:|---:|"]
        for campo in CHIUSI + NUMERICI + TESTUALI + NON_PUNTEGGIATI:
            c_ = per_campo[campo]
            if sum(c_.values()):
                L.append("| `{}` | {} | {} | {} | {} |".format(
                    campo, c_[DENTRO], c_[FUORI], c_[ASSENTE],
                    c_[NON_DETERMINABILE]))
        L.append("")

    if dettaglio:
        L += ["### Fuori finestra, uno per uno", "",
              "Se una forma domina questa tabella, il problema e' il taglio su "
              "quella forma e non il modello.", "",
              "| forma | campo | valore atteso | finestre | documento | resa |",
              "|---|---|---|---:|---:|---:|"]
        for g, campo, atteso, n_sent, n_testo in dettaglio:
            L.append("| {} | `{}` | {} | {:,} | {:,} | {:.1%} |".format(
                "8-K/2.01" if g.form == "8-K" else g.form, campo,
                str(atteso)[:40], n_sent, n_testo,
                n_sent / n_testo if n_testo else 0))
        L.append("")

    # --- declassamenti nostri ---
    declassati = sum(1 for r in righe
                     if any("non presente nel testo" in n for n in r[1].notes))
    L += ["## Declassamenti della validazione", "",
          "Estrazioni in cui `source_excerpt` non si trovava nel testo "
          "inviato: **{}** su {}. Sono errori del modello che la validazione ha "
          "intercettato, non errori di misura.".format(declassati, len(righe)),
          ""]

    if cambiati:
        L += ["## Golden esclusi", "",
              "Il documento e' cambiato dopo l'etichettatura: l'etichetta non "
              "vale piu' e il golden esce dal campione.", ""]
        L += ["- {}".format(c) for c in cambiati] + [""]

    L += ["## Costo di questa corsa", "",
          "{} chiamate, {:,} token di input, {:,} di output. "
          "Cache: {} hit, {} miss.".format(
              llm.usage["calls"], llm.usage["input_tokens"],
              llm.usage["output_tokens"], cache.stats["hit"],
              cache.stats["miss"]), ""]

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "results-{}.md".format(a.prompt)
    p.write_text("\n".join(L), encoding="utf-8")
    print("scritto {}".format(p))
    if tipo_acc is not None:
        print("accuracy su tipo: {:.1%} (soglia {:.0%})".format(
            tipo_acc, SOGLIA_TIPO))
        return 0 if tipo_acc >= SOGLIA_TIPO else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
