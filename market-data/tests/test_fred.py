"""FRED, ALFRED, EBP e curva GSW con una rete finta: grezzo datato, chiave mai scritta, errori espliciti. Nessuna chiamata vera."""
import gzip
import json
from datetime import datetime, timezone

import pytest

from market_data import api
from market_data import config as C
from market_data import fred as F

CHIAVE = "abcdef0123456789" + "abcdef0123456789"   # 32 esadecimali come quelle di FRED; finta
FREDGRAPH = b"observation_date,UNRATE\n1960-01-01,5.2\n1960-02-01,.\n1960-03-01,5.4\n2026-08-01,4.3\n"
ALFRED_OK = json.dumps({"realtime_start": "2010-01-29", "realtime_end": "2010-01-29", "count": 2, "offset": 0, "limit": 100000,
                        "observations": [{"realtime_start": "2010-01-29", "realtime_end": "2010-01-29", "date": "2009-11-01", "value": "10.0"},
                                         {"realtime_start": "2010-01-29", "realtime_end": "2010-01-29", "date": "2009-12-01", "value": "."}]}).encode()
EBP = b"date,gz_spread,ebp,est_prob\n1/1/1973,1.13,-0.046,0.18\n2/1/1973,1.07,-0.057,0.18\n7/1/2026,0.84,-0.319,0.108\n"
GSW = (b'"Note: This is not an official Federal Reserve statistical release."\n\nSeries,Compounding Convention,Mnemonic(s)\n'
       b"Zero-coupon yield,Continuously Compounded,SVENYXX\n\nDate,BETA0,BETA1,BETA2,BETA3,SVENY01,SVENY10,TAU1,TAU2\n"
       b"1961-06-14,3.9176,-1.2779,-1.9493,0,3.8067,NA,0.9,NA\n2026-09-25,2.2e-14,3.978,5.142,-4.1,4.5623,4.9,1.1,5.2\n")


class Rete:
    """Risponde per URL e registra le richieste; nessuna chiamata vera."""

    def __init__(self, risposte=None):
        self.url, self.risposte = [], risposte or {}

    def __call__(self, url):
        self.url.append(url)
        for pezzo, (stato, corpo) in self.risposte.items():
            if pezzo in url:
                return stato, corpo
        if "fredgraph.csv" in url:
            return 200, FREDGRAPH
        if "ebp_csv.csv" in url:
            return 200, EBP
        if "feds200628.csv" in url:
            return 200, GSW
        if "api.stlouisfed.org" in url:
            return 200, ALFRED_OK
        return 404, b""


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    rete = Rete()
    monkeypatch.setattr(F, "trasporto_urllib", rete)
    return tmp_path, rete


def manifest(archivio):
    return (archivio / "fred" / "manifest" / "grezzo.jsonl").read_text(encoding="utf-8")


def test_fred_senza_chiave_csv_pubblico_e_grezzo_datato(archivio):
    arch, rete = archivio
    df = api.fred("UNRATE")
    assert list(df.columns) == ["date", "value"] and list(df["value"]) == [5.2, 5.4, 4.3]   # il "." è tolto
    assert str(df["date"].iloc[0])[:10] == "1960-01-01"
    assert rete.url == ["https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE"]
    righe = [json.loads(r) for r in manifest(arch).splitlines()]
    assert righe[0]["endpoint"] == "fredgraph/UNRATE" and righe[0]["stato"] == 200 and righe[0]["righe"] == 4
    file = arch / righe[0]["file"]
    assert file.as_posix().startswith((arch / "fred" / "raw").as_posix()) and file.name.endswith(".csv.gz")
    assert gzip.decompress(file.read_bytes()) == FREDGRAPH
    # stesso giorno: si rilegge il file, nessuna seconda richiesta; il filtro sulle date taglia in memoria
    df2 = api.fred("UNRATE", inizio="1960-02-01", fine="1960-12-31")
    assert list(df2["value"]) == [5.4] and len(rete.url) == 1


def test_fred_si_riscarica_il_giorno_dopo_senza_sovrascrivere(archivio):
    arch, rete = archivio
    l1 = F.Lettore(arch, trasporto=rete, adesso=lambda: datetime(2026, 9, 30, 8, tzinfo=timezone.utc))
    l1.serie("UNRATE")
    l2 = F.Lettore(arch, trasporto=rete, adesso=lambda: datetime(2026, 10, 1, 8, tzinfo=timezone.utc))
    l2.serie("UNRATE")
    assert len(rete.url) == 2
    file = sorted((arch / "fred" / "raw").rglob("*.csv.gz"))
    assert [f.parent.name for f in file] == ["2026-09-30", "2026-10-01"]


def test_alfred_senza_chiave_si_ferma_prima_della_rete(archivio, tmp_path):
    arch, rete = archivio
    with pytest.raises(C.ConfigError, match="FRED_API_KEY"):
        F.Lettore(arch, trasporto=rete, env_file=tmp_path / "nessuno.env").serie("UNRATE", al_giorno=__import__("datetime").date(2010, 1, 29))
    assert rete.url == []
    assert not (arch / "fred" / "manifest" / "grezzo.jsonl").exists() or manifest(arch) == ""


def test_alfred_con_chiave_versione_storica_e_chiave_mai_scritta(archivio, monkeypatch):
    arch, rete = archivio
    monkeypatch.setenv("FRED_API_KEY", CHIAVE)
    df = api.fred("UNRATE", al_giorno="2010-01-29")
    assert list(df["value"]) == [10.0] and str(df["date"].iloc[0])[:10] == "2009-11-01"
    url = rete.url[0]
    assert url.startswith("https://api.stlouisfed.org/fred/series/observations?")
    assert "realtime_start=2010-01-29" in url and "realtime_end=2010-01-29" in url and "api_key=" + CHIAVE in url
    testo = manifest(arch)
    assert CHIAVE not in testo and "alfred/UNRATE" in testo
    assert not any(CHIAVE in p.name for p in (arch / "fred").rglob("*"))
    # una versione storica è immutabile: la seconda lettura, anche in un altro giorno, non chiama la rete
    F.Lettore(arch, trasporto=rete, adesso=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc)).serie(
        "UNRATE", al_giorno=__import__("datetime").date(2010, 1, 29))
    assert len(rete.url) == 1


def test_alfred_errore_esplicito_se_la_serie_non_ha_versioni(archivio, monkeypatch):
    arch, rete = archivio
    monkeypatch.setenv("FRED_API_KEY", CHIAVE)
    vuoto = json.dumps({"count": 0, "observations": []}).encode()
    errore = json.dumps({"error_code": 400, "error_message": "Bad Request.  Variable realtime_start is not valid."}).encode()
    rete.risposte["series_id=CPIAUCSL"] = (200, vuoto)
    with pytest.raises(F.ErroreFonte, match="nessuna versione"):
        api.fred("CPIAUCSL", al_giorno="1990-01-31")
    rete.risposte["series_id=GDPC1"] = (400, errore)
    with pytest.raises(F.ErroreFonte, match="HTTP 400"):
        api.fred("GDPC1", al_giorno="1990-01-31")
    rete.risposte["series_id=UNRATE"] = (200, errore)
    with pytest.raises(F.ErroreFonte, match="Variable realtime_start"):
        api.fred("UNRATE", al_giorno="1990-01-31")
    testo = manifest(arch)
    assert CHIAVE not in testo and '"stato": 400' in testo                  # anche l'errore resta nel grezzo, senza chiave


def test_fred_serie_inesistente_o_risposta_senza_colonna(archivio):
    arch, rete = archivio
    rete.risposte["id=NONESISTE"] = (404, b"")
    with pytest.raises(F.ErroreFonte, match="HTTP 404"):
        api.fred("NONESISTE")
    rete.risposte["id=STRANA"] = (200, b"observation_date,ALTRA\n2020-01-01,1\n")
    with pytest.raises(F.ErroreFonte, match="colonna"):
        api.fred("STRANA")
    with pytest.raises(ValueError):
        api.fred("UNRATE&x=1")


def test_ebp_date_americane_e_download_datati(archivio):
    arch, rete = archivio
    df = api.ebp()
    assert list(df.columns) == ["date", "gz_spread", "ebp", "est_prob"]
    assert [str(d)[:10] for d in df["date"]] == ["1973-01-01", "1973-02-01", "2026-07-01"]
    assert df["ebp"].iloc[-1] == pytest.approx(-0.319)
    assert api.ebp(inizio="1973-02-01", fine="1973-02-28")["ebp"].tolist() == pytest.approx([-0.057])
    assert len(rete.url) == 1
    l2 = F.Lettore(arch, trasporto=rete, adesso=lambda: datetime(2026, 11, 5, tzinfo=timezone.utc))
    l2.ebp()
    file = sorted((arch / "fred" / "raw").rglob("ebp__*.csv.gz"))
    assert len(file) == 2 and len({f.parent.name for f in file}) == 2 and len(rete.url) == 2


def test_gsw_salta_le_note_e_na(archivio):
    df = api.gsw()
    assert "BETA0" in df.columns and "SVENY01" in df.columns and "TAU2" in df.columns
    assert str(df["date"].iloc[0])[:10] == "1961-06-14" and df["SVENY10"].isna().iloc[0] and df["TAU2"].isna().iloc[0]
    assert df["SVENY01"].iloc[1] == pytest.approx(4.5623)
    assert len(api.gsw(inizio="2000-01-01")) == 1


def test_chiave_fred_ambiente_prima_del_file(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("FRED_API_KEY='dal-file'\n", encoding="utf-8")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert C.chiave_fred(env_file=env) == "dal-file"
    monkeypatch.setenv("FRED_API_KEY", "da-ambiente")
    assert C.chiave_fred(env_file=env) == "da-ambiente"
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(C.ConfigError, match="FRED_API_KEY"):
        C.chiave_fred(env_file=tmp_path / "nessuno.env")
