"""La guardia deve trovare cio' che cerca, e non deve trovare cio' che non c'e'.

Un controllo di perimetro che passa sempre e' peggio di nessun controllo: da'
la stessa fiducia e nessuna copertura. La meta' di queste asserzioni verifica
che la guardia SCATTI, non che taccia.

Il motivo sta in `docs/postmortems/PM-001-the-silent-guard.md`.
"""

import re
from pathlib import Path

import pytest

from edgar_llm.tools.perimeter_check import (FIXTURES_DIR, ROOT, SLUG_LINK,
                                             STRUTTURALI, PatternRotto,
                                             leggi_deny, scan, self_check,
                                             slugs)


def scrivi(tmp_path: Path, nome: str, testo: str) -> Path:
    p = tmp_path / nome
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo, encoding="utf-8")
    return tmp_path


# ------------------------------------------- chi sorveglia il sorvegliante --
def test_nessun_pattern_contiene_caratteri_invisibili():
    """Un pattern corrotto non fallisce: semplicemente non trova mai niente.

    Successo davvero: `\\b` scritto attraverso un livello di escape di troppo
    era diventato un carattere di BACKSPACE letterale dentro la stringa raw, e
    la guardia cercava un byte 0x08 seguito da `wrkspc_`. Nel file non si
    vedeva -- un carattere di controllo non si stampa -- e il pattern era muto.
    Una guardia che non segnala niente e una guardia che passa hanno lo stesso
    aspetto, ed e' precisamente il fallimento contro cui esiste questo modulo.
    """
    self_check()          # alza PatternRotto su controllo o regex non valida


def test_il_self_check_riconosce_un_backspace(monkeypatch):
    #  La forma esatta del guasto di PM-001, ricostruita.
    rotto = (("finto", "\bwrkspc_[0-9]+", "prova"),)
    monkeypatch.setattr("edgar_llm.tools.perimeter_check.STRUTTURALI", rotto)
    with pytest.raises(PatternRotto) as e:
        self_check()
    assert "carattere di controllo" in str(e.value)


def test_il_self_check_riconosce_una_regex_invalida(monkeypatch):
    monkeypatch.setattr("edgar_llm.tools.perimeter_check.STRUTTURALI",
                        (("finto", "(non chiusa", "prova"),))
    with pytest.raises(PatternRotto):
        self_check()


def test_il_self_check_riconosce_uno_slug_duplicato(monkeypatch):
    monkeypatch.setattr("edgar_llm.tools.perimeter_check.STRUTTURALI",
                        (("due", "a", "x"), ("due", "b", "y")))
    with pytest.raises(PatternRotto):
        self_check()


def test_ogni_slug_e_unico():
    assert len(set(slugs())) == len(slugs())


# ------------------------------------------------------ fixture positive --
def fixture_di(slug: str) -> Path:
    trovate = sorted(FIXTURES_DIR.glob(slug + ".*"))
    assert len(trovate) == 1, (slug, [p.name for p in trovate])
    return trovate[0]


@pytest.mark.parametrize("slug", slugs())
def test_ogni_controllo_ha_una_fixture_che_lo_fa_scattare(slug, tmp_path):
    """Il cuore di PM-001: nessun controllo si crede sulla parola.

    La fixture viene copiata in una directory temporanea perche' quella vera e'
    esclusa dalla scansione -- e va esclusa, o la pubblicazione fallirebbe
    sempre.
    """
    f = fixture_di(slug)
    scrivi(tmp_path, f.name, f.read_text(encoding="utf-8"))
    colpiti = {t.slug for t in scan(tmp_path, [])}
    assert slug in colpiti, (
        "la fixture {} non fa scattare {}: il controllo e' muto".format(
            f.name, slug))


@pytest.mark.parametrize("slug", slugs())
def test_ogni_fixture_fa_scattare_solo_il_suo_controllo(slug, tmp_path):
    #  Una fixture che ne colpisce due non dimostra quale dei due funziona.
    f = fixture_di(slug)
    scrivi(tmp_path, f.name, f.read_text(encoding="utf-8"))
    colpiti = {t.slug for t in scan(tmp_path, [])}
    assert colpiti == {slug}, (f.name, sorted(colpiti))


def test_la_directory_delle_fixture_non_nasconde_altro():
    """L'unica zona non scandita del perimetro non puo' diventare un ripostiglio.

    L'esclusione delle fixture e' necessaria e per questo e' sorvegliata: qui
    dentro ci sono esattamente le fixture dichiarate piu' il file che spiega
    perche' esistono. Un file in piu' e' un posto dove un segreto potrebbe
    stare senza essere guardato da nessuno.
    """
    presenti = {p.name for p in FIXTURES_DIR.iterdir() if p.is_file()}
    attesi = {fixture_di(s).name for s in slugs()} | {"LEGGIMI.md"}
    assert presenti == attesi, sorted(presenti ^ attesi)


def test_le_fixture_sono_piccole():
    #  Una fixture e' una riga o due. Un file grosso qui dentro non e' una
    #  fixture: e' qualcos'altro parcheggiato in una zona non scandita.
    for p in FIXTURES_DIR.iterdir():
        if p.is_file():
            assert p.stat().st_size < 2048, (p.name, p.stat().st_size)


def test_le_fixture_non_fanno_fallire_la_pubblicazione():
    #  Il controllo che rende usabile tutto il resto.
    assert scan(ROOT, []) == []


def test_ma_esistono_davvero_e_verrebbero_viste_senza_l_esclusione():
    #  Se questa asserzione cade, l'esclusione sta nascondendo il nulla e le
    #  fixture non sono dove il codice crede.
    trovati = scan(ROOT, [], skip_fixtures=False)
    assert {t.slug for t in trovati} >= set(slugs())


# --------------------------------------------------- i singoli controlli --
def test_una_email_ferma_tutto(tmp_path):
    scrivi(tmp_path, "a.py", "UA = 'Mario Rossi mario.rossi@dominio.it'")
    assert any(t.slug == "email" for t in scan(tmp_path, []))


def test_un_path_assoluto_ferma_tutto(tmp_path):
    scrivi(tmp_path, "a.py", 'CACHE = "C:\\\\Users\\\\qualcuno\\\\cache"')
    assert any(t.slug == "path-windows" for t in scan(tmp_path, []))


def test_una_chiave_in_chiaro_ferma_tutto(tmp_path):
    scrivi(tmp_path, "a.py", 'KEY = "sk-ant-api03-XXXXXXXXXXXX"')
    assert any(t.slug == "chiave-api" for t in scan(tmp_path, []))


def test_una_chiave_che_dice_di_essere_finta_ferma_tutto_lo_stesso(tmp_path):
    #  C'era un'esenzione generica per la parola «example»: esentava anche
    #  `sk-ant-EXAMPLEKEY`, cioe' la forma che avrebbe una chiave vera
    #  camuffata da finta. Tolta.
    scrivi(tmp_path, "a.py", 'KEY = "sk-ant-EXAMPLEKEY"')
    assert any(t.slug == "chiave-api" for t in scan(tmp_path, []))


def test_un_id_di_workspace_ferma_tutto(tmp_path):
    scrivi(tmp_path, "a.example", "ANTHROPIC_WORKSPACE_ID=wrkspc_01ABCDEFGH")
    assert any(t.slug == "workspace-id" for t in scan(tmp_path, []))


def test_un_workspace_vuoto_va_bene(tmp_path):
    scrivi(tmp_path, "a.example", "ANTHROPIC_WORKSPACE_ID=")
    assert scan(tmp_path, []) == []


def test_i_termini_operativi_fermano_tutto(tmp_path):
    for testo, slug in (
        ("# la watchlist di settembre", "watchlist"),
        ("LEDGER = 'data/verdicts.jsonl'", "registro-verdetti"),
        ("if v == 'STRONG_BUY':", "classe-verdetto"),
    ):
        scrivi(tmp_path, "a.py", testo)
        colpiti = {t.slug for t in scan(tmp_path, [])}
        assert slug in colpiti, (testo, sorted(colpiti))


# ------------------------------------------------------- i collegamenti --
def test_un_link_che_esce_ferma_tutto(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text(
        "[vicino](../../altro/report.py)", encoding="utf-8")
    assert any(t.slug == SLUG_LINK for t in scan(tmp_path, []))


def test_un_link_interno_che_risale_va_bene(tmp_path):
    #  `docs/evals/` che rimanda a `docs/adr/` deve poterlo fare. Cercare la
    #  stringa `](../` segnalerebbe tre link legittimi di questa
    #  documentazione, e un controllo che segnala cio' che e' corretto viene
    #  disattivato dopo la seconda volta.
    (tmp_path / "docs" / "evals").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "001.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs" / "evals" / "a.md").write_text(
        "[adr](../adr/001.md)", encoding="utf-8")
    assert scan(tmp_path, []) == []


def test_un_link_assoluto_o_ancora_non_e_un_collegamento_relativo(tmp_path):
    scrivi(tmp_path, "a.md",
           "[web](https://esempio.invalid/x) e [sezione](#titolo)")
    assert not any(t.slug == SLUG_LINK for t in scan(tmp_path, []))


def test_i_link_si_controllano_solo_nel_markdown(tmp_path):
    #  In Python `](../` non e' un collegamento: e' quasi certamente una regex.
    scrivi(tmp_path, "a.py", 'PAT = r"\\]\\(\\.\\./"')
    assert not any(t.slug == SLUG_LINK for t in scan(tmp_path, []))


# ------------------------------------------------------- lista e formato --
def test_un_ticker_della_lista_ferma_tutto(tmp_path):
    scrivi(tmp_path, "a.py", "# esempio su AAA, distribuita a luglio")
    assert scan(tmp_path, []) == []
    assert any(t.slug == "ticker" for t in scan(tmp_path, ["AAA"]))


def test_la_lista_non_distingue_maiuscole(tmp_path):
    #  Un termine privato scritto in minuscolo, o con l'iniziale maiuscola, e'
    #  la stessa fuga del termine in maiuscolo.
    scrivi(tmp_path, "a.py", "# prova su aaa e sul progetto Quarzo-Uno")
    colpiti = {t.frammento for t in scan(tmp_path, ["AAA", "QUARZO-UNO"])}
    assert colpiti == {"AAA", "QUARZO-UNO"}, colpiti


def test_un_termine_privato_dal_file_scatta_in_ogni_forma(tmp_path):
    lista = tmp_path / "lista" / "deny.txt"
    lista.parent.mkdir()
    lista.write_text("termine-privato\n", encoding="utf-8")
    src = tmp_path / "src"
    for i, forma in enumerate(("termine-privato", "TERMINE-PRIVATO",
                               "Termine-Privato")):
        scrivi(src, "f{}.md".format(i), "vedi {} qui".format(forma))
    trovati = [t for t in scan(src, leggi_deny(str(lista)))
               if t.slug == "ticker"]
    assert len(trovati) == 3, trovati


def test_il_confine_di_parola_evita_i_falsi_positivi(tmp_path):
    scrivi(tmp_path, "a.py", "# gli ADCs sono farmaci coniugati")
    assert scan(tmp_path, ["ADC"]) == [], "ADC non deve scattare dentro ADCs"


def test_il_caso_studio_dichiarato_e_ammesso(tmp_path):
    scrivi(tmp_path, "a.md", "ITT ha acquisito SPX FLOW: item 2.01.")
    assert scan(tmp_path, []) == []


def test_un_placeholder_non_e_una_fuga(tmp_path):
    scrivi(tmp_path, "b.example", "EDGAR_USER_AGENT=Nome Cognome tu@dominio.tld")
    assert scan(tmp_path, []) == []


def test_un_binario_non_si_pubblica(tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")
    assert any(t.slug == "binario" for t in scan(tmp_path, []))


def test_le_directory_generate_si_saltano(tmp_path):
    scrivi(tmp_path, "__pycache__/a.py", "mario@dominio.it")
    scrivi(tmp_path, ".pytest_cache/CACHEDIR.TAG", "Signature: x")
    assert scan(tmp_path, []) == []


def test_la_lista_si_legge_da_file_non_dal_codice(tmp_path):
    p = tmp_path / "deny.txt"
    p.write_text("# commento\nAAA\n\nbbb\nITT\n", encoding="utf-8")
    #  ITT e' il caso studio ammesso e non entra nella lista, altrimenti la
    #  documentazione del modulo non si potrebbe pubblicare.
    assert leggi_deny(str(p)) == ["AAA", "BBB"]


def test_nessuna_lista_e_una_lista_vuota():
    assert leggi_deny(None) == []


def test_ogni_pattern_e_una_regex_valida():
    for _slug, pat, _perche in STRUTTURALI:
        re.compile(pat)
