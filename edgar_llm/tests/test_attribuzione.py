"""Dentro o fuori finestra: due guasti opposti, e non vanno confusi."""

from edgar_llm.attribuzione import (ASSENTE, DENTRO, FUORI,
                                    NON_DETERMINABILE, dove_sta, varianti)

TESTO = (
    "On March 2, 2026 the Acquisition was consummated. Consideration was "
    "approximately $2.3 billion in cash and $0.7 billion in shares, issued to "
    "LSF11 Redwood Parent, L.P. The Registration Rights Agreement follows."
)
CODA = " Later, buried on page 300, the aggregate was $700,000,000."


def test_dentro_quando_l_informazione_era_nel_prompt():
    assert dove_sta("data_efficacia", "2026-03-02", TESTO, TESTO) == DENTRO


def test_fuori_quando_stava_solo_nel_documento():
    #  Il caso che giustifica il modulo: nessuna istruzione fa leggere al
    #  modello una frase che non gli e' stata mandata.
    assert dove_sta("importo_usd", 700_000_000.0, "un estratto corto",
                    TESTO + CODA) == FUORI


def test_assente_quando_non_c_e_da_nessuna_parte():
    assert dove_sta("importo_usd", 42.0, TESTO, TESTO) == ASSENTE


def test_tipo_e_condizioni_non_sono_determinabili():
    #  Non e' una lacuna da riempire con un'euristica: `tipo` e' una
    #  classificazione e `condizioni` una sintesi. Nel testo non hanno una
    #  forma da cercare.
    assert dove_sta("tipo", "M&A_issuance", TESTO, TESTO) == NON_DETERMINABILE
    assert dove_sta("condizioni", "lock-up", TESTO, TESTO) == NON_DETERMINABILE


def test_un_valore_nullo_non_si_attribuisce():
    assert dove_sta("importo_usd", None, TESTO, TESTO) == NON_DETERMINABILE


# ---------------------------------------------------------- le varianti --
def test_un_importo_si_riconosce_anche_scritto_in_lettere():
    #  «$0.7 billion» e «$700,000,000» sono lo stesso numero e un documento ne
    #  usa una sola. Cercare solo le cifre direbbe "fuori finestra" su un
    #  documento che lo scriveva in lettere due righe sopra.
    assert dove_sta("importo_usd", 700_000_000.0, TESTO, TESTO) == DENTRO


def test_un_importo_si_riconosce_anche_in_cifre():
    assert dove_sta("importo_usd", 700_000_000.0, CODA, CODA) == DENTRO


def test_una_data_si_riconosce_nella_forma_americana():
    assert "March 2, 2026" in varianti("data_efficacia", "2026-03-02")
    assert "2026-03-02" in varianti("data_efficacia", "2026-03-02")


def test_una_data_illeggibile_non_esplode():
    assert varianti("data_efficacia", "non una data") == ["non una data"]


def test_un_nome_si_riconosce_senza_la_glossa_fra_parentesi():
    #  L'etichetta umana e' «LSF11 Redwood Parent, L.P. (Seller)»; il documento
    #  scrive il nome senza la glossa. Cercare la stringa intera direbbe "fuori
    #  finestra" su un documento che la nomina in ogni pagina.
    assert dove_sta("controparte", "LSF11 Redwood Parent, L.P. (Seller)",
                    TESTO, TESTO) == DENTRO


def test_una_parola_corta_non_basta_a_dichiarare_una_presenza():
    v = varianti("controparte", "The Bank")
    assert "The" not in v, "una parola di tre lettere combacia con tutto"


def test_gli_spazi_non_contano():
    assert dove_sta("controparte", "Redwood   Parent",
                    "LSF11 Redwood Parent, L.P.", TESTO) == DENTRO


def test_un_importo_non_numerico_non_si_attribuisce():
    assert dove_sta("importo_usd", "circa mezzo miliardo",
                    TESTO, TESTO) == NON_DETERMINABILE
