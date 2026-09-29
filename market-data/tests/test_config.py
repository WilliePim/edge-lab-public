from pathlib import Path

import pytest

from market_data import config as C


def test_archivio_dentro_il_repo_rifiutato():
    with pytest.raises(C.ConfigError, match="dentro il repo"):
        C.archivio(str(C.REPO_ROOT / "market-data" / "data"))


def test_radice_del_repo_rifiutata():
    with pytest.raises(C.ConfigError):
        C.archivio(str(C.REPO_ROOT))


def test_archivio_dentro_un_altro_repo_git_rifiutato(tmp_path):
    (tmp_path / "altro" / ".git").mkdir(parents=True)
    with pytest.raises(C.ConfigError, match="dentro un repo git"):
        C.archivio(str(tmp_path / "altro" / "dati" / "eodhd"))


def test_archivio_fuori_accettato_anche_se_non_esiste(tmp_path):
    assert C.archivio(str(tmp_path / "invest-data")) == (tmp_path / "invest-data").resolve()


def test_archivio_mancante_o_relativo_rifiutato(monkeypatch, tmp_path):
    monkeypatch.delenv("MARKET_DATA_DIR", raising=False)
    with pytest.raises(C.ConfigError, match="non impostata"):
        C.archivio(env_file=tmp_path / "nessuno.env")
    with pytest.raises(C.ConfigError, match="assoluto"):
        C.archivio("invest-data")


def test_ambiente_prima_di_env_file(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("# commento\nEODHD_API_KEY='dal-file'\nEODHD_DAILY_LIMIT=20\n", encoding="utf-8")
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    monkeypatch.delenv("EODHD_DAILY_LIMIT", raising=False)
    assert C.chiave_eodhd(env_file=env) == "dal-file"
    monkeypatch.setenv("EODHD_API_KEY", "da-ambiente")
    assert C.chiave_eodhd(env_file=env) == "da-ambiente"
    assert C.limiti(env_file=env).al_giorno == 20


def test_chiave_mancante(monkeypatch, tmp_path):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    with pytest.raises(C.ConfigError):
        C.chiave_eodhd(env_file=tmp_path / "nessuno.env")


def test_margine_del_dieci_per_cento():
    lim = C.Limiti(100_000, 1_000)
    assert (lim.giorno_utile, lim.minuto_utile) == (90_000, 900)
    assert C.Limiti(20, 1).giorno_utile == 18
