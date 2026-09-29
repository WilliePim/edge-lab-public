import json
from datetime import datetime, timezone

import pytest

from market_data.config import Limiti
from market_data.eodhd.client import BudgetEsaurito, Client, oscura

CHIAVE = "0123456789abcd" + "." + "12345678"   # spezzata: il controllo pre-commit blocca la forma intera


class Finto:
    """Trasporto finto: risponde con una sequenza di stati e registra gli URL ricevuti."""

    def __init__(self, stati):
        self.stati, self.url = list(stati), []

    def __call__(self, url):
        self.url.append(url)
        return self.stati.pop(0), b"[1, 2, 3]"


class Tempo:
    def __init__(self):
        self.t, self.dormite = 0.0, []

    def orologio(self):
        return self.t

    def dormi(self, s):
        self.dormite.append(s)
        self.t += s


def client(tmp_path, stati, limiti=Limiti(100_000, 1_000), tempo=None):
    tempo = tempo or Tempo()
    return Client(CHIAVE, tmp_path, limiti, trasporto=Finto(stati), orologio=tempo.orologio, dormi=tempo.dormi,
                  adesso=lambda: datetime(2026, 9, 17, 12, tzinfo=timezone.utc))


def test_la_chiave_non_finisce_nel_registro_ne_nella_risposta(tmp_path):
    c = client(tmp_path, [200])
    r = c.get("eod/AAPL.US", {"from": "2020-01-01"})
    assert r.stato == 200 and CHIAVE not in r.url_oscurato
    assert CHIAVE in c._trasporto.url[0]
    testo = (tmp_path / "eodhd" / "manifest" / "chiamate.jsonl").read_text(encoding="utf-8")
    assert CHIAVE not in testo and CHIAVE not in repr(c)
    assert oscura("x?api_token={}&fmt=json".format(CHIAVE)) == "x?api_token=***&fmt=json"


def test_ripete_429_e_5xx_ma_non_402(tmp_path):
    c = client(tmp_path, [429, 503, 200])
    assert c.get("eod/X.US").stato == 200
    assert len(c._trasporto.url) == 3 and c.usate_oggi() == 3
    c2 = client(tmp_path / "b", [402])
    assert c2.get("fundamentals/X.US", costo=10).stato == 402
    assert len(c2._trasporto.url) == 1 and c2.usate_oggi() == 10


def test_tetto_del_giorno_con_margine(tmp_path):
    c = client(tmp_path, [200] * 30, limiti=Limiti(20, 1_000))
    for _ in range(18):
        c.get("eod/X.US")
    with pytest.raises(BudgetEsaurito):
        c.get("eod/X.US")
    assert len(c._trasporto.url) == 18


def test_il_consumo_sopravvive_al_riavvio(tmp_path):
    c = client(tmp_path, [200] * 5, limiti=Limiti(20, 1_000))
    for _ in range(5):
        c.get("eod/X.US")
    c2 = client(tmp_path, [200] * 20, limiti=Limiti(20, 1_000))
    assert c2.usate_oggi() == 5
    righe = [json.loads(r) for r in (tmp_path / "eodhd" / "manifest" / "chiamate.jsonl").read_text().splitlines()]
    assert {r["giorno"] for r in righe} == {"2026-09-17"}


def test_limite_al_minuto_aspetta(tmp_path):
    tempo = Tempo()
    c = client(tmp_path, [200] * 12, limiti=Limiti(100_000, 11), tempo=tempo)   # 90% di 11 = 9 al minuto
    for _ in range(10):
        c.get("eod/X.US")
    assert len(tempo.dormite) == 1 and tempo.t >= 60.0


def test_endpoint_fuori_piano_non_addebitato(tmp_path):
    c = client(tmp_path, [403, 404])
    assert c.get("fundamentals/X.US", costo=10).stato == 403 and c.usate_oggi() == 0
    assert c.get("eod/NONESISTE.US").stato == 404 and c.usate_oggi() == 0     # misurato: nemmeno le 404 costano


def test_eccezione_del_trasporto_registrata_senza_chiave(tmp_path):
    import http.client

    def rotto(url):
        raise http.client.InvalidURL("URL non valido: " + url)

    c = Client(CHIAVE, tmp_path, Limiti(100_000, 1_000), trasporto=rotto, orologio=lambda: 0.0, dormi=lambda s: None,
               adesso=lambda: datetime(2026, 9, 17, 12, tzinfo=timezone.utc))
    r = c.get("eod/A B.US")
    assert r.stato == 0 and CHIAVE.encode() not in r.corpo and b"InvalidURL" in r.corpo
    righe = (tmp_path / "eodhd" / "manifest" / "chiamate.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(righe) == 3 and all(CHIAVE not in x for x in righe)          # tre tentativi, tutti registrati
    assert "A%20B.US" in r.url_oscurato


def test_vecchie_righe_403_non_contano(tmp_path):
    reg = tmp_path / "eodhd" / "manifest" / "chiamate.jsonl"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"giorno": "2026-09-17", "costo": 10, "stato": 403}) + "\n" +
                   json.dumps({"giorno": "2026-09-17", "costo": 1, "stato": 200}) + "\n", encoding="utf-8")
    assert client(tmp_path, []).usate_oggi() == 1
