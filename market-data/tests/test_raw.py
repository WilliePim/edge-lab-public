import gzip
import hashlib
from datetime import datetime, timezone

from market_data.store.raw import Grezzo

ADESSO = datetime(2026, 9, 17, 8, tzinfo=timezone.utc)
FINTA = "0123456789abcd" + "." + "12345678"   # spezzata: il controllo pre-commit blocca la forma intera


def test_salva_compresso_e_ripartenza(tmp_path):
    g = Grezzo(tmp_path)
    corpo = b'[{"date": "2020-01-02", "close": 1.0}, {"date": "2020-01-03", "close": 1.1}]'
    params = {"fmt": "json", "from": "2020-01-01", "api_token": FINTA}
    v = g.salva("eod/X.US", params, 200, corpo, adesso=ADESSO)
    assert v["file"].startswith("eodhd/raw/2026-09-17/eod_X.US__") and v["file"].endswith(".json.gz")
    assert gzip.decompress((tmp_path / v["file"]).read_bytes()) == corpo
    assert v["sha256"] == hashlib.sha256(corpo).hexdigest() and v["righe"] == 2
    assert "api_token" not in v["parametri"]
    assert "0123456789abcd" not in (tmp_path / "eodhd" / "manifest" / "grezzo.jsonl").read_text(encoding="utf-8")
    g2 = Grezzo(tmp_path)                                  # nuovo processo: la ripartenza legge il manifest
    assert g2.gia_scaricato("eod/X.US", {"fmt": "json", "from": "2020-01-01"})["sha256"] == v["sha256"]
    assert g2.leggi(g2.gia_scaricato("eod/X.US", {"from": "2020-01-01", "fmt": "json"})) == corpo


def test_errore_non_conta_come_scaricato(tmp_path):
    g = Grezzo(tmp_path)
    g.salva("fundamentals/X.US", {"fmt": "json"}, 403, b"Forbidden", adesso=ADESSO)
    assert Grezzo(tmp_path).gia_scaricato("fundamentals/X.US", {"fmt": "json"}) is None


def test_stesso_giorno_non_sovrascrive(tmp_path):
    g = Grezzo(tmp_path)
    v1 = g.salva("user", {"fmt": "json"}, 200, b'{"apiRequests": 1}', adesso=ADESSO)
    v2 = g.salva("user", {"fmt": "json"}, 200, b'{"apiRequests": 8}', adesso=ADESSO)
    assert v1["file"] != v2["file"] and v2["file"].endswith("__2.json.gz")
    assert g.leggi(v1) == b'{"apiRequests": 1}' and g.leggi(v2) == b'{"apiRequests": 8}'
    assert Grezzo(tmp_path).gia_scaricato("user", {"fmt": "json"})["sha256"] == v2["sha256"]
