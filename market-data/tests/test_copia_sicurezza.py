import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("copia", Path(__file__).resolve().parents[1] / "scripts" / "copia_sicurezza.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)
NESSUNO = lambda a: None  # noqa: E731


def test_copia_incrementale_verificata_e_a_specchio(tmp_path):
    arch, disco = tmp_path / "invest-data", tmp_path / "esterno"
    (arch / "eodhd" / "raw").mkdir(parents=True)
    (arch / "eodhd" / "parquet" / "prezzi" / "exchange=US").mkdir(parents=True)
    (arch / "eodhd" / "raw" / "a.csv.gz").write_bytes(b"abc")
    (arch / "eodhd" / "parquet" / "prezzi" / "exchange=US" / "part-00001.parquet").write_bytes(b"vecchia")
    (arch / "catalog.duckdb").write_bytes(b"x" * 10)
    (arch / "eodhd" / "manifest").mkdir(parents=True)
    (arch / "eodhd" / "manifest" / "STOP").write_text("", encoding="utf-8")
    c1 = S.copia(arch, disco, log=lambda *_: None, in_corso=NESSUNO)
    assert (c1["file"], c1["copiati"], c1["uguali"]) == (3, 3, 0) and not c1["errori"]
    assert not (disco / "invest-data" / "eodhd" / "manifest" / "STOP").exists()                 # temporanei esclusi
    #  ricostruzione: la parte 00001 sparisce, arriva un file nuovo
    (arch / "eodhd" / "parquet" / "prezzi" / "exchange=US" / "part-00001.parquet").unlink()
    (arch / "eodhd" / "raw" / "b.csv.gz").write_bytes(b"nuovo")
    c2 = S.copia(arch, disco, log=lambda *_: None, in_corso=NESSUNO)
    assert (c2["copiati"], c2["uguali"], c2["tolti_dalla_copia"]) == (1, 2, 1)
    assert not (disco / "invest-data" / "eodhd" / "parquet" / "prezzi" / "exchange=US" / "part-00001.parquet").exists()
    c3 = S.copia(arch, disco, verifica_completa=True, log=lambda *_: None, in_corso=NESSUNO)
    assert (c3["copiati"], c3["uguali"]) == (0, 3)


def test_errore_su_un_file_non_ferma_la_copia(tmp_path, monkeypatch):
    arch, disco = tmp_path / "invest-data", tmp_path / "esterno"
    arch.mkdir()
    (arch / "a.bin").write_bytes(b"a")
    (arch / "b.bin").write_bytes(b"b")
    vera = S.impronta

    def impronta_rotta(p):
        if p.name == "a.bin" and "esterno" not in str(p):
            raise PermissionError("aperto da un altro processo")
        return vera(p)

    monkeypatch.setattr(S, "impronta", impronta_rotta)
    c = S.copia(arch, disco, log=lambda *_: None, in_corso=NESSUNO)
    assert c["copiati"] == 1 and len(c["errori"]) == 1 and "PermissionError" in c["errori"][0]["errore"]


def test_rifiuti(tmp_path):
    arch = tmp_path / "invest-data"
    (arch / "eodhd" / "parquet" / "prezzi" / ".tmp_exchange=US").mkdir(parents=True)
    with pytest.raises(SystemExit, match="ricostruzione"):
        S.copia(arch, tmp_path / "esterno", log=lambda *_: None)
    with pytest.raises(SystemExit, match="download o aggiornamento"):
        S.copia(arch, tmp_path / "esterno", log=lambda *_: None, in_corso=lambda a: "download o aggiornamento in corso")
    with pytest.raises(SystemExit, match="dentro l'archivio"):
        S.copia(arch, arch, log=lambda *_: None, in_corso=NESSUNO)
