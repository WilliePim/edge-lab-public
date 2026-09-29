"""Il file che si legge e il testo che riceve il modello devono coincidere.

Se divergessero, chi etichetta risponderebbe a un testo diverso da quello
estratto, e l'attribuzione dentro/fuori finestra delle evals -- che confronta
il valore vero con le finestre inviate -- misurerebbe la differenza fra due
tagli invece della qualita' di uno.
"""

from pathlib import Path

import pytest

from edgar_llm import sessione as sess
from edgar_llm.fetch import ELISION, to_text, windows
from edgar_llm.filings import Filing

F = Filing(cik="1234567", accession="0001234567-26-000001", form="424B5",
           filed="2026-01-13", primary_document="aaa_424b5.htm")


def esporta(tmp_path, testo, finestre, filing=F, n=3):
    return sess.esporta(n, filing, "AAA", "AAA CORP",
                        testo, finestre, tmp_path)


# ------------------------------------------------ identita' del contenuto --
def test_il_file_restituisce_esattamente_cio_che_e_stato_esportato(tmp_path):
    finestre = "riga uno\nriga due\n\nriga quattro"
    p = esporta(tmp_path, "x" * 5000, finestre)
    assert sess.finestre_da_file(p) == finestre


def test_sopravvivono_i_ritorni_a_capo_in_coda(tmp_path):
    #  Il caso che una lettura ingenua rovina: il testo finisce con un a capo
    #  e il delimitatore ne aggiunge un altro.
    finestre = "una riga\n\n\n"
    p = esporta(tmp_path, "x" * 100, finestre)
    assert sess.finestre_da_file(p) == finestre


def test_sopravvive_un_testo_vuoto(tmp_path):
    p = esporta(tmp_path, "", "")
    assert sess.finestre_da_file(p) == ""


def test_sopravvivono_gli_spazi_in_testa(tmp_path):
    finestre = "   indentato\n\tcon tabulazione"
    p = esporta(tmp_path, "x" * 100, finestre)
    assert sess.finestre_da_file(p) == finestre


def test_sopravvive_l_unicode_dei_filing(tmp_path):
    #  U+202F e le virgolette tipografiche: cio' che ha fatto esplodere la
    #  console alla prima sessione.
    finestre = "$20.29 per share “Closing Date” — fine"
    p = esporta(tmp_path, "x" * 100, finestre)
    assert sess.finestre_da_file(p) == finestre


def test_i_marcatori_di_elisione_restano_visibili(tmp_path):
    #  Chi etichetta deve vedere dove manca del documento, o dedurra' da un
    #  accostamento che nel documento non esiste.
    finestre = "prima" + ELISION + "dopo"
    p = esporta(tmp_path, "x" * 100, finestre)
    letto = sess.finestre_da_file(p)
    assert letto == finestre
    assert "testo omesso" in p.read_text(encoding="utf-8")


def test_un_testo_che_contiene_i_delimitatori_si_rifiuta(tmp_path):
    #  Non e' mai successo su un filing vero. Se succedesse, il file si
    #  rileggerebbe troncato senza dirlo, ed e' esattamente la classe di
    #  guasto silenzioso che questo progetto ha gia' pagato una volta.
    with pytest.raises(sess.FinestreNonEsportabili):
        esporta(tmp_path, "x" * 100, "prima " + sess.INIZIO + " dopo")
    with pytest.raises(sess.FinestreNonEsportabili):
        esporta(tmp_path, "x" * 100, "prima " + sess.FINE + " dopo")


# ------------------------------------------- l'identita' sul percorso vero --
def test_il_file_coincide_con_cio_che_riceverebbe_il_modello(tmp_path):
    """La catena intera, con un documento vero ma servito da un finto client.

    `windows(to_text(html))` e' esattamente cio' che `extract_filing` manda al
    modello: se questa asserzione cade, il file e il prompt hanno smesso di
    essere la stessa cosa.
    """
    html = ("<html><body>"
            + "".join("<p>Riga {} con del testo di riempimento.</p>".format(i)
                      for i in range(4000))
            + "<p>Use of Proceeds</p><p>General corporate purposes.</p>"
            + "</body></html>")
    testo = to_text(html)
    inviato = windows(testo)
    assert len(inviato) < len(testo), "il caso interessante e' con un taglio"
    assert ELISION in inviato

    p = esporta(tmp_path, testo, inviato)
    assert sess.finestre_da_file(p) == inviato


# --------------------------------------------------------------- il nome --
def test_il_nome_del_file_e_leggibile():
    assert sess.nome_file(3, F, "AAA") == \
        "03_424B5_AAA_0001234567-26-000001.md"


def test_un_emittente_senza_ticker_ripiega_sul_cik():
    assert sess.nome_file(1, F, "").startswith("01_424B5_1234567_")


def test_la_forma_di_un_8k_di_acquisizione_e_riconoscibile_nel_nome():
    otto = Filing(cik="1", accession="0000000001-26-000001", form="8-K",
                  filed="2026-03-02", primary_document="a.htm",
                  items="1.01,2.01")
    assert sess.nome_file(7, otto, "ITT") == "07_8-K-2.01_ITT_0000000001-26-000001.md"


def test_il_nome_non_contiene_caratteri_da_filesystem():
    strano = Filing(cik="1", accession="0000000001-26-000001", form="424B3/A",
                    filed="2026-01-01", primary_document="a.htm")
    nome = sess.nome_file(1, strano, "A/B")
    assert "/" not in nome and "\\" not in nome


# -------------------------------------------------------------- l'indice --
def voce(n, stato, nota=""):
    return (n, F, "AAA", sess.nome_file(n, F, "AAA"), stato, nota)


def test_l_indice_elenca_gli_stati(tmp_path):
    p = sess.scrivi_indice(tmp_path, [
        voce(1, sess.ETICHETTATO), voce(2, sess.SALTATO),
        voce(3, sess.DA_FARE), voce(4, sess.ILLEGGIBILE, "EDGAR non l'ha dato"),
    ])
    s = p.read_text(encoding="utf-8")
    for stato in (sess.ETICHETTATO, sess.SALTATO, sess.DA_FARE, sess.ILLEGGIBILE):
        assert stato in s
    assert "**1 etichettati** su 4" in s


def test_l_indice_rimanda_ai_file_con_link_relativi(tmp_path):
    p = sess.scrivi_indice(tmp_path, [voce(1, sess.DA_FARE)])
    s = p.read_text(encoding="utf-8")
    nome = sess.nome_file(1, F, "AAA")
    assert "[{}]({})".format(nome, nome) in s
    assert ".." not in s, "l'indice non deve uscire dalla sua directory"


def test_l_indice_si_riscrive_e_non_si_accumula(tmp_path):
    sess.scrivi_indice(tmp_path, [voce(1, sess.DA_FARE)])
    p = sess.scrivi_indice(tmp_path, [voce(1, sess.ETICHETTATO)])
    s = p.read_text(encoding="utf-8")
    assert s.count("| 1 |") == 1
    assert sess.DA_FARE not in s


# ------------------------------------------------------------ il posto --
def test_le_sessioni_vivono_FUORI_dal_package():
    """Contengono testo di depositi: non devono poter finire in un mirror."""
    package = Path(sess.__file__).resolve().parent
    assert package not in sess.BASE.parents and sess.BASE != package
    assert "state" in sess.BASE.parts


def test_la_directory_porta_la_data(tmp_path):
    from datetime import date
    d = sess.dir_sessione(tmp_path, date(2026, 9, 2))
    assert d.name == "2026-09-02"
    assert d.parent == tmp_path
