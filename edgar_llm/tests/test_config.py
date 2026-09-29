"""Da dove arriva un segreto, e chi vince quando arriva da due posti."""

import os

import pytest

from edgar_llm import config


@pytest.fixture(autouse=True)
def ambiente_pulito(monkeypatch):
    #  Il flag di idempotenza e' globale: senza azzerarlo, il primo test che
    #  carica impedisce a tutti gli altri di caricare.
    monkeypatch.setattr(config, "_caricato", False)
    for n in ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID", "EDGAR_USER_AGENT",
              "EDGAR_LLM_MODE", "FORM4_USER_AGENT"):
        monkeypatch.delenv(n, raising=False)

    #  E soprattutto: nessuna ricerca implicita risale fino al `.env` VERO
    #  della macchina. Senza questo, `test_lo_stato_dice_anche_cosa_manca`
    #  passava su una postazione senza credenziali e falliva sulla stessa
    #  postazione il giorno dopo, perche' nel frattempo qualcuno aveva
    #  configurato la chiave. Un test che dipende da come e' configurato il
    #  computer non sta misurando il codice.
    vero = config.trova
    monkeypatch.setattr(config, "trova",
                        lambda start=None: vero(start) if start else None)


def scrivi_env(d, testo):
    (d / ".env").write_text(testo, encoding="utf-8")
    return d


# ------------------------------------------------------------- parsing --
def test_coppie_semplici():
    assert config.parse("A=1\nB=due\n") == {"A": "1", "B": "due"}


def test_commenti_e_righe_vuote_si_ignorano():
    assert config.parse("# nota\n\nA=1\n  \n") == {"A": "1"}


def test_gli_apici_sono_di_chi_scrive_non_del_valore():
    assert config.parse("A='x y'\nB=\"z\"\n") == {"A": "x y", "B": "z"}


def test_export_davanti_si_tollera():
    assert config.parse("export A=1\n") == {"A": "1"}


def test_un_valore_con_uguale_dentro_resta_intero():
    #  Una chiave API puo' contenere '='. Spezzare sull'ultimo la troncherebbe.
    assert config.parse("K=sk-ant-a=b=c\n") == {"K": "sk-ant-a=b=c"}


def test_una_riga_senza_uguale_non_e_una_coppia():
    assert config.parse("robaccia\nA=1\n") == {"A": "1"}


# ------------------------------------------------------------ ricerca --
def test_si_risale_fino_a_trovarlo(tmp_path):
    radice = scrivi_env(tmp_path, "A=1\n")
    profondo = tmp_path / "pkg" / "sub"
    profondo.mkdir(parents=True)
    assert config.trova(profondo) == radice / ".env"


def test_niente_file_niente_errore(tmp_path):
    assert config.trova(tmp_path) is None
    assert config.load(tmp_path) == []


def test_il_piu_vicino_vince(tmp_path):
    scrivi_env(tmp_path, "A=lontano\n")
    vicino = tmp_path / "pkg"
    vicino.mkdir()
    scrivi_env(vicino, "A=vicino\n")
    assert config.trova(vicino) == vicino / ".env"


# ----------------------------------------------------------- priorita' --
def test_il_file_popola_l_ambiente(tmp_path, monkeypatch):
    scrivi_env(tmp_path, "ANTHROPIC_API_KEY=dal-file\n")
    assert config.load(tmp_path) == ["ANTHROPIC_API_KEY"]
    assert os.environ["ANTHROPIC_API_KEY"] == "dal-file"


def test_l_ambiente_vince_sempre_sul_file(tmp_path, monkeypatch):
    #  Uno scheduler o una CI devono poter scavalcare un .env vecchio rimasto
    #  su disco. Il contrario e' un pomeriggio perso su un 401.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dall-ambiente")
    scrivi_env(tmp_path, "ANTHROPIC_API_KEY=dal-file\n")
    assert config.load(tmp_path) == []
    assert os.environ["ANTHROPIC_API_KEY"] == "dall-ambiente"


def test_un_valore_vuoto_nel_file_non_cancella_niente(tmp_path):
    scrivi_env(tmp_path, "ANTHROPIC_API_KEY=\n")
    config.load(tmp_path)
    assert not os.environ.get("ANTHROPIC_API_KEY")


def test_caricare_due_volte_non_rilegge(tmp_path):
    scrivi_env(tmp_path, "A=1\n")
    assert config.load(tmp_path) == ["A"]
    assert config.load(tmp_path) == []


# ------------------------------------------------------------- stato --
#  Non ha la forma `sk-ant-...` di proposito: la guardia del perimetro segnala
#  anche le chiavi finte, e ha ragione -- a occhio non si distinguono.
FINTA = "una-chiave-finta-segretissima"


def test_lo_stato_non_rivela_il_valore(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FINTA)
    righe = dict((n, (p, l)) for n, p, l in config.stato())
    assert righe["ANTHROPIC_API_KEY"] == (True, len(FINTA))

    config.main([])
    uscita = capsys.readouterr().out
    assert FINTA not in uscita
    #  E nemmeno un pezzo: troncare un segreto non e' nasconderlo.
    assert FINTA[:8] not in uscita
    assert "presente" in uscita
    assert "pronto" in uscita


def test_lo_stato_dice_anche_cosa_manca(capsys):
    config.main([])
    uscita = capsys.readouterr().out
    assert "ASSENTE" in uscita
    assert "replay" in uscita


# ------------------------------------------------- integrazione client --
def test_il_client_prende_la_chiave_dal_file(tmp_path, monkeypatch):
    from edgar_llm.client import LLMClient

    scrivi_env(tmp_path, "ANTHROPIC_API_KEY=dal-file\n")
    monkeypatch.setattr(config, "trova", lambda start=None: tmp_path / ".env")
    assert LLMClient().available


def test_senza_chiave_il_client_non_e_disponibile(monkeypatch):
    from edgar_llm.client import LLMClient

    monkeypatch.setattr(config, "trova", lambda start=None: None)
    assert not LLMClient().available


# --------------------------------------------------------------- la prova --
def test_senza_prova_non_si_chiama_niente(capsys):
    #  Il comportamento predefinito non deve costare: chi lancia `config` per
    #  vedere cosa c'e' non si aspetta una chiamata a pagamento.
    assert config.main([]) == 0
    assert "chiamata di prova" not in capsys.readouterr().out


def test_la_prova_senza_chiave_fallisce(capsys):
    assert config.main(["--prova"]) == 1
    assert "PROVA SALTATA" in capsys.readouterr().out


def test_la_prova_riporta_il_fallimento_senza_esplodere(monkeypatch, capsys):
    from edgar_llm import client as mod

    monkeypatch.setenv("ANTHROPIC_API_KEY", "una-chiave-che-non-vale")

    def rotto(self):
        raise mod.ModelUnavailable("401 authentication_error")

    monkeypatch.setattr(mod.LLMClient, "ping", rotto)
    assert config.main(["--prova"]) == 1
    uscita = capsys.readouterr().out
    assert "FALLITA" in uscita and "401" in uscita


def test_la_prova_riuscita_dice_cosa_ha_risposto(monkeypatch, capsys):
    from edgar_llm import client as mod

    monkeypatch.setenv("ANTHROPIC_API_KEY", "una-chiave-che-vale")
    monkeypatch.setattr(mod.LLMClient, "ping",
                        lambda self: {"model": "un-modello",
                                      "input_tokens": 8, "output_tokens": 8})
    assert config.main(["--prova"]) == 0
    assert "un-modello ha risposto" in capsys.readouterr().out
