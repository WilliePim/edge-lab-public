"""Il golden set e il confronto delle evals."""

import pytest

from edgar_llm.eval import accuracy, confronta
from edgar_llm.filings import Filing
from edgar_llm.goldens import (Golden, GoldenChanged, append, load, make,
                               rehydrate, sha_of)
from edgar_llm.schema import Field, OfferingEvent
from conftest import FakeEdgar

DOC = "<html><body><p>ATM sales agreement, $50,000,000.</p></body></html>"
F = Filing(cik="1", accession="0000000001-26-000001", form="424B5",
           filed="2026-01-05", primary_document="a.htm")
TESTO = "ATM sales agreement, $50,000,000."


def golden_di_prova(**over):
    labels = {"tipo": "ATM", "controparte": "Jefferies LLC",
              "importo_usd": 50_000_000.0, "condizioni": None,
              "data_efficacia": "2026-01-05"}
    labels.update(over.pop("labels", {}))
    g = make(F, TESTO, labels)
    return Golden(**{**g.__dict__, **over})


def evento(**campi):
    base = {c: Field() for c in ("tipo", "controparte", "importo_usd",
                                 "condizioni", "data_efficacia")}
    base.update(campi)
    return OfferingEvent(issuer_cik="1", accession=F.accession, form="424B5",
                         filed="2026-01-05", source_url=F.url, **base)


# --------------------------------------------------------------- store --
def test_scrittura_e_rilettura(tmp_path):
    p = tmp_path / "labels.jsonl"
    append(golden_di_prova(), p)
    got = load(p)
    assert len(got) == 1
    assert got[0].labels["tipo"] == "ATM"
    assert got[0].text_sha256 == sha_of(TESTO)


def test_una_correzione_e_una_riga_nuova_e_vince(tmp_path):
    p = tmp_path / "labels.jsonl"
    append(golden_di_prova(), p)
    append(golden_di_prova(labels={"tipo": "secondary_offering"}), p)
    got = load(p)
    assert len(got) == 1, "stessa accession: l'ultima vince"
    assert got[0].labels["tipo"] == "secondary_offering"


def test_una_riga_rotta_non_ferma_la_lettura(tmp_path):
    p = tmp_path / "labels.jsonl"
    append(golden_di_prova(), p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{ mezza riga\n")
    assert len(load(p)) == 1


def test_un_campo_fuori_schema_non_si_salva():
    with pytest.raises(ValueError):
        make(F, TESTO, {"tipo": "ATM", "giudizio": "buono"})


def test_lo_store_inesistente_e_una_lista_vuota(tmp_path):
    assert load(tmp_path / "non-esiste.jsonl") == []


# ----------------------------------------------------------- rehydrate --
def test_il_testo_si_riscarica_e_combacia():
    g = make(F, "ATM sales agreement, $50,000,000.", {"tipo": "ATM"})
    edgar = FakeEdgar(texts={F.url: DOC})
    assert rehydrate(g, edgar) == TESTO


def test_un_documento_cambiato_alza():
    #  Il golden set non deve adattarsi in silenzio a cio' che il codice fa
    #  adesso: se il testo e' un altro, l'etichetta non vale piu'.
    g = make(F, "un testo del tutto diverso", {"tipo": "ATM"})
    with pytest.raises(GoldenChanged):
        rehydrate(g, FakeEdgar(texts={F.url: DOC}))


def test_non_strict_lascia_passare():
    g = make(F, "un testo del tutto diverso", {"tipo": "ATM"})
    assert rehydrate(g, FakeEdgar(texts={F.url: DOC}), strict=False) == TESTO


# ------------------------------------------------------------ confronto --
def test_tutto_giusto():
    g = golden_di_prova()
    ev = evento(tipo=Field("ATM", "high", "x" * 20),
                controparte=Field("Jefferies LLC", "high", "x" * 20),
                importo_usd=Field(50_000_000.0, "high", "x" * 20),
                data_efficacia=Field("2026-01-05", "high", "x" * 20))
    c = confronta(g, ev)
    assert c["tipo"][0] == "ok"
    assert c["importo_usd"][0] == "ok"
    assert c["data_efficacia"][0] == "ok"
    assert c["controparte"][0] == "ok"
    assert c["condizioni"][0] == "entrambi_null"


def test_un_campo_low_conta_come_mancante():
    #  Sotto soglia il campo non e' usabile, quindi per le evals non c'e'.
    g = golden_di_prova()
    c = confronta(g, evento(tipo=Field("ATM", "low", "x" * 20)))
    assert c["tipo"][0] == "mancante"


def test_dire_che_non_c_e_quando_non_c_e_e_giusto():
    g = golden_di_prova(labels={"controparte": None})
    c = confronta(g, evento())
    assert c["controparte"][0] == "entrambi_null"
    giusti, valutabili = accuracy([c["controparte"]])
    assert (giusti, valutabili) == (1, 1)


def test_inventare_e_diverso_da_sbagliare():
    g = golden_di_prova(labels={"controparte": None})
    c = confronta(g, evento(controparte=Field("Goldman", "high", "x" * 20)))
    assert c["controparte"][0] == "inventato"
    assert accuracy([c["controparte"]]) == (0, 1)


def test_la_controparte_si_confronta_per_contenimento():
    g = golden_di_prova(labels={"controparte": "Jefferies"})
    c = confronta(g, evento(controparte=Field("Jefferies LLC", "high", "x" * 20)))
    assert c["controparte"][0] == "ok"


def test_l_importo_tollera_meno_di_un_dollaro():
    g = golden_di_prova()
    assert confronta(g, evento(
        importo_usd=Field(50_000_000.4, "high", "x" * 20)))["importo_usd"][0] == "ok"
    assert confronta(g, evento(
        importo_usd=Field(49_000_000.0, "high", "x" * 20)))["importo_usd"][0] == "ko"


def test_la_data_non_tollera_niente():
    g = golden_di_prova()
    c = confronta(g, evento(data_efficacia=Field("2026-01-06", "high", "x" * 20)))
    assert c["data_efficacia"][0] == "ko"
