"""HTML -> testo, e le finestre che finiscono nel prompt."""

import pytest

from edgar_llm.fetch import (ELISION, UnreadableDocument, to_text, windows)

#  La regressione che ha motivato meta' di questo file. Gli 8-K recenti sono
#  inline XBRL e aprono con questa dichiarazione; lxml rifiuta una `str` che la
#  contiene, e la prima versione di `to_text` restituiva "" -- cinque documenti
#  su cinque misuravano zero caratteri e la tabella dei costi lo leggeva come
#  "gli 8-K non hanno testo".
IXBRL = (
    "<?xml version='1.0' encoding='ASCII'?>\n"
    "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
    "<head><title>8-K</title></head>"
    "<body><p>Item 2.01 Completion of Acquisition of Assets.</p>"
    "<p>The Company completed its acquisition of SPX FLOW.</p></body></html>"
)


def test_ixbrl_con_dichiarazione_di_encoding_produce_testo():
    out = to_text(IXBRL)
    assert "Item 2.01" in out
    assert "SPX FLOW" in out
    assert out, "la dichiarazione XML non deve azzerare il documento"


def test_head_script_e_style_non_entrano_nel_testo():
    html = ("<html><head><title>T</title><style>p{color:red}</style></head>"
            "<body><script>var x=1</script><p>Corpo vero</p></body></html>")
    out = to_text(html)
    assert "Corpo vero" in out
    assert "color:red" not in out
    assert "var x" not in out
    assert "T" not in out


def test_testo_nudo_passa_intatto():
    assert to_text("nessun markup qui, solo prosa") == "nessun markup qui, solo prosa"


def test_vuoto_resta_vuoto():
    assert to_text("") == ""


def test_documento_incomprensibile_alza_invece_di_restituire_vuoto():
    #  Un errore che si vede, non uno zero muto.
    with pytest.raises(UnreadableDocument):
        to_text("<" * 5)


def test_nbsp_e_spazi_multipli_collassano():
    out = to_text("<p>a\xa0\xa0\xa0b     c</p>")
    assert out == "a b c"


def test_le_righe_sopravvivono_perche_le_ancore_lavorano_su_quelle():
    out = to_text("<p>Prima</p><p>Use of Proceeds</p><p>Dopo</p>")
    assert "\n" in out


# ------------------------------------------------------------- finestre --
def test_documento_corto_passa_intero_senza_elisioni():
    t = "riga\n" * 100
    assert windows(t, head_chars=10_000) == t
    assert ELISION not in windows(t, head_chars=10_000)


def test_documento_lungo_viene_tagliato_e_il_taglio_e_dichiarato():
    t = "x" * 60_000
    out = windows(t, head_chars=1_000, window_chars=200)
    assert len(out) < len(t)
    assert ELISION in out, "un salto non dichiarato lascia citare attraverso un buco"


def test_una_ancora_lontana_apre_una_finestra_su_di_se():
    t = "a" * 5_000 + "\nUse of Proceeds\nil ricavato servira' a X\n" + "b" * 5_000
    out = windows(t, head_chars=1_000, window_chars=400)
    assert "Use of Proceeds" in out
    assert "il ricavato servira' a X" in out


def test_finestre_sovrapposte_si_fondono_senza_duplicare():
    t = "a" * 1_000 + "\nUse of Proceeds\n" + "b" * 50 + "\nPlan of Distribution\n" + "c" * 5_000
    out = windows(t, head_chars=900, window_chars=2_000)
    assert out.count("Use of Proceeds") == 1
    assert out.count("Plan of Distribution") == 1


def test_il_numero_di_ancore_e_limitato():
    #  Senza tetto, un prospetto che ripete "Underwriting" cento volte
    #  rispedirebbe il documento intero e il taglio non servirebbe a niente.
    t = "a" * 2_000 + ("\nUnderwriting\n" + "z" * 100) * 50
    out = windows(t, head_chars=1_000, window_chars=200, max_anchors=3)
    assert out.count("Underwriting") <= 4


def test_testo_vuoto_da_finestre_vuote():
    assert windows("") == ""
