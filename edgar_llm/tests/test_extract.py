"""Il percorso completo, e le sue quattro uscite di guasto."""

from edgar_llm.cache import RECORD, REPLAY, Cache
from edgar_llm.client import ModelUnavailable
from edgar_llm.extract import extract_filing, render
from edgar_llm.filings import Filing
from edgar_llm.schema import CAMPI, Field, OfferingEvent
from conftest import FakeEdgar, FakeLLM, campo

DOC = (
    "<html><body>"
    "<p>Item 2.01 Completion of Acquisition of Assets.</p>"
    "<p>The Company completed the acquisition of SPX FLOW, issuing "
    "8,000,000 shares of common stock as consideration.</p>"
    "</body></html>"
)

F = Filing(cik="216228", accession="0000216228-26-000020", form="8-K",
           filed="2026-03-02", primary_document="itt.htm", items="1.01,2.01")

BUONO = {c: campo(None, "high", "") for c in CAMPI}
BUONO["tipo"] = campo("M&A_issuance", "high",
                      "issuing 8,000,000 shares of common stock as consideration")


def edgar_con_documento():
    return FakeEdgar(texts={F.url: DOC})


def test_percorso_felice(tmp_path):
    ev = extract_filing(F, edgar_con_documento(), llm=FakeLLM(BUONO),
                        cache=Cache(tmp_path, RECORD))
    assert ev.tipo.value == "M&A_issuance"
    assert ev.tipo.usable
    assert ev.notes == ()
    assert ev.source_url == F.url
    assert ev.issuer_cik == "216228"
    assert render(ev) == "M&A_issuance (high)"


def test_la_seconda_volta_non_chiama_il_modello(tmp_path):
    cache = Cache(tmp_path, RECORD)
    llm = FakeLLM(BUONO)
    extract_filing(F, edgar_con_documento(), llm=llm, cache=cache)
    extract_filing(F, edgar_con_documento(), llm=llm, cache=cache)
    assert llm.calls == 1
    assert cache.stats["hit"] == 1


def test_la_validazione_non_e_in_cache(tmp_path):
    #  In cache va la risposta grezza; la validazione rigira a ogni lettura,
    #  cosi' una correzione al validatore vale subito su tutto lo storico.
    cache = Cache(tmp_path, RECORD)
    cattivo = dict(BUONO)
    cattivo["tipo"] = campo("M&A_issuance", "high", "una frase che non c'e' nel testo")
    ev1 = extract_filing(F, edgar_con_documento(), llm=FakeLLM(cattivo), cache=cache)
    assert ev1.tipo.confidence == "low"
    #  Riletta dalla cache: stessa risposta grezza, stesso declassamento.
    ev2 = extract_filing(F, edgar_con_documento(), llm=FakeLLM(BUONO), cache=cache)
    assert ev2.tipo.confidence == "low"
    assert any("non presente" in n for n in ev2.notes)


# ------------------------------------------------- le quattro uscite --
def test_edgar_non_da_il_documento(tmp_path):
    ev = extract_filing(F, FakeEdgar(), llm=FakeLLM(BUONO),
                        cache=Cache(tmp_path, RECORD))
    assert not ev.tipo.known
    assert any("non ha restituito" in n for n in ev.notes)
    assert render(ev) == "UNKNOWN"


def test_documento_illeggibile(tmp_path):
    ev = extract_filing(F, FakeEdgar(texts={F.url: "<" * 5}), llm=FakeLLM(BUONO),
                        cache=Cache(tmp_path, RECORD))
    assert any("illeggibile" in n for n in ev.notes)


def test_api_giu_non_ferma_niente(tmp_path):
    ev = extract_filing(F, edgar_con_documento(),
                        llm=FakeLLM(raise_=ModelUnavailable("503")),
                        cache=Cache(tmp_path, RECORD))
    assert not ev.tipo.known
    assert any("ModelUnavailable" in n for n in ev.notes)
    assert render(ev) == "UNKNOWN"


def test_replay_senza_cache_e_un_esito_non_un_crash(tmp_path):
    ev = extract_filing(F, edgar_con_documento(), llm=FakeLLM(BUONO),
                        cache=Cache(tmp_path, REPLAY))
    assert not ev.tipo.known
    assert any("replay" in n for n in ev.notes)


def test_risposta_vuota_da_evento_vuoto_con_note(tmp_path):
    ev = extract_filing(F, edgar_con_documento(), llm=FakeLLM({}),
                        cache=Cache(tmp_path, RECORD))
    assert all(not getattr(ev, c).known for c in CAMPI)
    assert len(ev.notes) == len(CAMPI)


# ------------------------------------------------------------- render --
def test_render_non_scrive_un_tipo_sotto_soglia():
    ev = OfferingEvent(issuer_cik="1", accession="a", form="424B5",
                       filed="2026-01-01", source_url="u",
                       tipo=Field("ATM", "low", "x" * 20))
    assert render(ev) == "UNKNOWN"


def test_render_di_niente():
    assert render(None) == "—"
