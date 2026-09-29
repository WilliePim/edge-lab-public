"""La validazione: fail-closed, e la citazione deve esistere davvero."""

from edgar_llm.schema import (CAMPI, TIPI, TOOL_SCHEMA, Field, OfferingEvent,
                              validate)
from conftest import campo

TESTO = (
    "The Company entered into an Agreement and Plan of Merger. "
    "Consideration consists of 8,000,000 shares of common stock, "
    "valued at approximately $450,000,000, issued to the sellers. "
    "The transaction became effective on March 2, 2026."
)


def paga(**kw):
    base = {c: campo(None, "low", "") for c in CAMPI}
    base.update(kw)
    return base


def test_estrazione_pulita_resta_pulita():
    campi, notes = validate(paga(
        tipo=campo("M&A_issuance", "high", "Agreement and Plan of Merger"),
        importo_usd=campo(450_000_000, "high", "approximately $450,000,000"),
    ), TESTO)
    assert campi["tipo"].value == "M&A_issuance"
    assert campi["tipo"].confidence == "high"
    assert campi["tipo"].usable
    assert campi["importo_usd"].value == 450_000_000.0
    assert notes == []


def test_citazione_inventata_declassa_il_campo():
    #  Il caso per cui esiste tutto il file: un modello sicuro di se' che cita
    #  una frase che nel testo mandato non c'era.
    campi, notes = validate(paga(
        tipo=campo("IPO", "high", "the initial public offering priced at $17"),
    ), TESTO)
    assert campi["tipo"].confidence == "low"
    assert not campi["tipo"].usable
    assert any("non presente nel testo inviato" in n for n in notes)


def test_citazione_troppo_corta_declassa():
    campi, notes = validate(paga(tipo=campo("ATM", "high", "the")), TESTO)
    assert campi["tipo"].confidence == "low"
    assert any("troppo corta" in n for n in notes)


def test_la_citazione_si_confronta_a_spazi_normalizzati():
    campi, _ = validate(paga(
        tipo=campo("M&A_issuance", "high", "Agreement   and\n Plan of Merger"),
    ), TESTO)
    assert campi["tipo"].confidence == "high"


def test_tipo_fuori_enumerazione_diventa_none_con_nota():
    campi, notes = validate(paga(
        tipo=campo("spin_off", "high", "Agreement and Plan of Merger"),
    ), TESTO)
    assert campi["tipo"].value is None
    assert any("fuori dall'enumerazione" in n for n in notes)


def test_importo_non_numerico_diventa_none():
    campi, notes = validate(paga(
        importo_usd=campo("circa mezzo miliardo", "high",
                          "approximately $450,000,000"),
    ), TESTO)
    assert campi["importo_usd"].value is None
    assert any("non numerico" in n for n in notes)


def test_importo_con_virgole_e_dollaro_si_legge():
    campi, _ = validate(paga(
        importo_usd=campo("$450,000,000", "high", "approximately $450,000,000"),
    ), TESTO)
    assert campi["importo_usd"].value == 450_000_000.0


def test_data_non_iso_diventa_none():
    campi, notes = validate(paga(
        data_efficacia=campo("March 2, 2026", "high", "effective on March 2, 2026"),
    ), TESTO)
    assert campi["data_efficacia"].value is None
    assert any("non ISO" in n for n in notes)


def test_data_inesistente_diventa_none():
    campi, notes = validate(paga(
        data_efficacia=campo("2026-02-30", "high", "effective on March 2, 2026"),
    ), TESTO)
    assert campi["data_efficacia"].value is None
    assert any("inesistente" in n for n in notes)


def test_confidence_inventata_scende_a_low():
    campi, notes = validate(paga(
        tipo=campo("ATM", "certissima", "Agreement and Plan of Merger"),
    ), TESTO)
    assert campi["tipo"].confidence == "low"
    assert any("confidence non valida" in n for n in notes)


def test_campo_assente_e_un_esito_dichiarato():
    p = paga()
    del p["controparte"]
    campi, notes = validate(p, TESTO)
    assert campi["controparte"].value is None
    assert not campi["controparte"].known
    assert any("controparte: assente" in n for n in notes)


def test_payload_vuoto_non_esplode():
    campi, notes = validate({}, TESTO)
    assert set(campi) == set(CAMPI)
    assert all(not f.known for f in campi.values())
    assert len(notes) == len(CAMPI)


def test_none_non_richiede_citazione():
    #  Un campo assente dal documento non deve essere punito per non citarlo.
    campi, notes = validate(paga(controparte=campo(None, "high", "")), TESTO)
    assert campi["controparte"].confidence == "high"
    assert notes == []


def test_soglia_di_revisione_esclude_low_e_ammette_medium():
    assert Field("ATM", "high", "x" * 20).usable
    assert Field("ATM", "medium", "x" * 20).usable
    assert not Field("ATM", "low", "x" * 20).usable
    assert not Field(None, "high", "").usable


# --------------------------------------------------------------- schema --
def test_lo_schema_del_tool_copre_i_cinque_campi():
    assert set(TOOL_SCHEMA["properties"]) == set(CAMPI)
    assert TOOL_SCHEMA["required"] == list(CAMPI)
    for c in CAMPI:
        req = TOOL_SCHEMA["properties"][c]["required"]
        assert req == ["value", "confidence", "source_excerpt"]


def test_lo_schema_elenca_esattamente_i_sette_tipi():
    enum = TOOL_SCHEMA["properties"]["tipo"]["properties"]["value"]["enum"]
    assert [e for e in enum if e is not None] == list(TIPI)
    assert None in enum, "il documento puo' non descrivere un'emissione"


def test_round_trip_su_dizionario():
    ev = OfferingEvent(issuer_cik="1", accession="a", form="8-K",
                       filed="2026-03-02", source_url="u",
                       tipo=Field("M&A_issuance", "high", "x" * 20),
                       notes=("una nota",))
    back = OfferingEvent.from_dict(ev.as_dict())
    assert back.tipo.value == "M&A_issuance"
    assert back.notes == ("una nota",)
    assert back.as_dict() == ev.as_dict()
