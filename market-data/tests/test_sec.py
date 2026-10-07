"""Lettori dei file in blocco della SEC su due zip finti costruiti qui: nessuna rete, nessuno dei file veri."""
import json
import zipfile

import pandas as pd
import pytest

from market_data import api
from market_data import sec as S

ALFA, BETA, ASSENTE = 1111, 2222, 9999


def fatto(end, val, filed, accn, form="10-Q", start=None, fy=2020, fp="Q1", frame=None):
    f = {"end": end, "val": val, "accn": accn, "fy": fy, "fp": fp, "form": form, "filed": filed}
    if start:
        f["start"] = start
    if frame:
        f["frame"] = frame
    return f


COMPANYFACTS = {
    ALFA: {"cik": ALFA, "entityName": "Alfa Inc", "facts": {
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
            fatto("2020-04-20", 1000000, "2020-05-01", "a-1"), fatto("2020-07-20", 1000000000000, "2020-08-01", "a-2", fp="Q2")]}},
            "EntityPublicFloat": {"units": {"USD": [fatto("2019-06-28", 5.5e7, "2020-02-20", "a-0", form="10-K", fp="FY", fy=2019)]}}},
        "us-gaap": {
            "CommonStockSharesOutstanding": {"units": {"shares": [fatto("2020-03-31", 990000, "2020-05-01", "a-1")]}},
            "WeightedAverageNumberOfSharesOutstandingBasic": {"units": {"shares": [
                fatto("2020-03-31", 985000, "2020-05-01", "a-1", start="2020-01-01")]}},
            "Revenues": {"units": {"USD": [
                fatto("2020-03-31", 10.0, "2020-05-01", "a-1", start="2020-01-01", frame="CY2020Q1"),
                fatto("2020-03-31", 11.0, "2021-05-03", "a-5", start="2020-01-01", fy=2021),       # riesposto un anno dopo
                {"end": "2020-06-30", "accn": "a-2", "form": "10-Q", "filed": "2020-08-01"},        # senza valore: saltato
                fatto("2020-06-30", 21.5, "2020-08-01", "a-2", start="2020-01-01", fp="Q2")],
                "EUR": [fatto("2020-03-31", 9.0, "2020-05-01", "a-1", start="2020-01-01")]}},
            "NetIncomeLoss": {"units": {"USD": [fatto("2020-03-31", -2.0, "2020-05-01", "a-1", start="2020-01-01")]}}}}},
    BETA: {"cik": BETA, "entityName": "Beta Bank", "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [fatto("2020-03-31", 7.0, "2020-05-05", "b-1", start="2020-01-01")]}}}}},
}
SUBMISSIONS = {
    ALFA: {"cik": "1111", "name": "Alfa Inc", "sic": "3571", "sicDescription": "Computers", "entityType": "operating",
           "category": "Large accelerated filer", "stateOfIncorporation": "DE", "fiscalYearEnd": "1231", "tickers": ["ALFA"],
           "exchanges": ["Nasdaq"], "filings": {
               "recent": {"accessionNumber": ["a-9", "a-8", "a-7"], "filingDate": ["2021-03-01", "2021-02-10", "2020-08-01"],
                          "reportDate": ["2021-02-26", "", "2020-06-30"], "form": ["8-K", "25", "10-Q"],
                          "items": ["1.03,9.01", "", ""]},
               "files": [{"name": "CIK0000001111-submissions-001.json", "filingCount": 1}]}},
    BETA: {"cik": "2222", "name": "Beta Bank", "sic": 6022, "tickers": [], "exchanges": [None], "filings": {"recent": {}}},
}
VECCHI = {"accessionNumber": ["a-1"], "filingDate": ["2012-05-01"], "reportDate": ["2012-03-31"], "form": ["10-Q"], "items": [""]}


def scrivi(cartella, dati_manifest=None, senza=()):
    cartella.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for nome, corpo in (("companyfacts", COMPANYFACTS), ("submissions", SUBMISSIONS)):
        if nome in senza:
            continue
        f = cartella / S.FILE[nome]
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
            for cik, d in corpo.items():
                z.writestr("CIK{:010d}.json".format(cik), json.dumps(d))
            if nome == "submissions":
                z.writestr("CIK0000001111-submissions-001.json", json.dumps(VECCHI))
        manifest[nome] = {"file": f.name, "byte": f.stat().st_size, "sha256": "impronta-" + nome,
                          "scaricato_utc": "2026-10-03T15:48:43+00:00"}
    manifest.update(dati_manifest or {})
    (cartella / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    scrivi(tmp_path / S.CARTELLA)
    S.dimentica()
    yield tmp_path
    S.dimentica()


def test_bilancio_voci_unita_deposito_e_fatti_senza_valore(archivio):
    df = api.sec_bilancio(ALFA, ["Revenues", "us-gaap:NetIncomeLoss"])
    assert list(df.columns) == list(S.COLONNE_FATTI)
    ric = df[(df["voce"] == "us-gaap:Revenues") & (df["unita"] == "USD")]
    assert len(ric) == 3                                              # il fatto senza valore non c'è
    primo = ric[ric["fine"] == "2020-03-31"].sort_values("depositato")
    assert list(primo["valore"]) == [10.0, 11.0]                      # lo stesso periodo una volta per deposito: sceglie chi legge
    assert list(primo["depositato"].dt.strftime("%Y-%m-%d")) == ["2020-05-01", "2021-05-03"]
    assert list(primo["inizio"].dt.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-01-01"]
    assert list(primo["modulo"]) == ["10-Q", "10-Q"] and list(primo["accn"]) == ["a-1", "a-5"]
    assert list(primo["esercizio"]) == [2020, 2021] and primo.iloc[0]["periodo"] == "Q1" and primo.iloc[0]["frame"] == "CY2020Q1"
    assert set(df["unita"]) == {"USD", "EUR"}                         # tutte le unità, nessuna scelta
    assert list(df[df["voce"] == "us-gaap:NetIncomeLoss"]["valore"]) == [-2.0]


def test_voce_con_tassonomia_e_valori_istantanei(archivio):
    df = api.sec_bilancio(ALFA, "dei:EntityPublicFloat")
    assert len(df) == 1 and df.iloc[0]["valore"] == 5.5e7 and pd.isna(df.iloc[0]["inizio"]) and df.iloc[0]["modulo"] == "10-K"
    with pytest.raises(ValueError):
        api.sec_bilancio(ALFA, [])


def test_azioni_tre_voci_senza_correggere_gli_errori_di_scala(archivio):
    df = api.sec_azioni(ALFA)
    assert set(df["voce"]) == set(S.VOCI_AZIONI)
    dei = df[df["voce"] == S.VOCI_AZIONI[0]].sort_values("depositato")
    assert list(dei["valore"]) == [1000000.0, 1000000000000.0]        # l'errore di scala del deposito resta com'è
    media = df[df["voce"] == S.VOCI_AZIONI[2]].iloc[0]
    assert media["inizio"] == pd.Timestamp("2020-01-01") and media["fine"] == pd.Timestamp("2020-03-31")


def test_piu_societa_cik_come_testo_e_cik_assente(archivio):
    df = api.sec_bilancio(["0000001111", BETA, ASSENTE], ["Revenues"])
    assert set(df["cik"]) == {ALFA, BETA}                             # il CIK assente non dà righe e non dà errore
    assert len(api.sec_bilancio(ASSENTE, ["Revenues"])) == 0
    assert list(api.sec_bilancio(ASSENTE, ["Revenues"]).columns) == list(S.COLONNE_FATTI)
    assert api.sec_cik() == frozenset({ALFA, BETA}) and api.sec_cik("submissions") == frozenset({ALFA, BETA})
    with pytest.raises(ValueError):
        api.sec_bilancio("non un cik", ["Revenues"])


def test_societa_e_depositi(archivio):
    soc = api.sec_societa([ALFA, BETA, ASSENTE])
    assert list(soc["cik"]) == [ALFA, BETA] and list(soc["sic"]) == ["3571", "6022"]
    assert soc.iloc[0]["ticker"] == "ALFA" and soc.iloc[0]["altri_file"] == 1 and soc.iloc[1]["borse"] == ""
    dep = api.sec_depositi(ALFA)
    assert list(dep["modulo"]) == ["10-Q", "25", "8-K"]               # in ordine di data
    assert dep.iloc[2]["voci_8k"] == "1.03,9.01" and pd.isna(dep.iloc[1]["data_rapporto"])
    assert list(api.sec_depositi(ALFA, ["8-K", "25"])["modulo"]) == ["25", "8-K"]
    assert len(api.sec_depositi(ALFA, tutti=True)) == 4               # anche il file dei depositi più vecchi
    assert len(api.sec_depositi(BETA)) == 0 and len(api.sec_depositi(ASSENTE)) == 0


def test_cache_nella_cartella_dei_dati_stesso_risultato_senza_rileggere(archivio):
    lettore = S.lettore(archivio)
    senza = api.sec_bilancio([ALFA, BETA, ASSENTE], ["Revenues"])
    letti = lettore.letture
    con = api.sec_bilancio([ALFA, BETA, ASSENTE], ["Revenues"], cache=True)
    pd.testing.assert_frame_equal(senza, con)
    assert lettore.letture == letti + 2                               # ALFA e BETA; il CIK assente non ha un file da leggere
    ancora = api.sec_bilancio([ALFA, ASSENTE], ["Revenues"], cache=True)
    assert lettore.letture == letti + 2 and set(ancora["cik"]) == {ALFA}     # tutto dalla cache, anche «assente»
    file = sorted(p.name for p in (archivio / S.CARTELLA / "cache").iterdir())
    assert len(file) == 2 and file[0].startswith("fatti_") and file[1].endswith(".parquet")
    altre = api.sec_bilancio(ALFA, ["NetIncomeLoss"], cache=True)      # altre voci: un'altra cache
    assert list(altre["valore"]) == [-2.0] and len(list((archivio / S.CARTELLA / "cache").iterdir())) == 4
    pd.testing.assert_frame_equal(api.sec_societa([ALFA, BETA]), api.sec_societa([ALFA, BETA], cache=True))
    pd.testing.assert_frame_equal(api.sec_depositi(ALFA, ["8-K"]), api.sec_depositi(ALFA, ["8-K"], cache=True))


def test_file_mancante_errore_chiaro_nessun_download(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    S.dimentica()
    with pytest.raises(S.FileMancante, match="manifest"):
        api.sec_bilancio(ALFA, ["Revenues"])                          # cartella vuota: nemmeno il manifest
    scrivi(tmp_path / S.CARTELLA, senza=("submissions",))
    S.dimentica()
    assert len(api.sec_bilancio(ALFA, ["Revenues"])) == 4
    with pytest.raises(S.FileMancante, match="submissions.zip"):
        api.sec_societa(ALFA)
    S.dimentica()                                                     # chiude lo zip: su Windows un file aperto non si toglie
    (tmp_path / S.CARTELLA / S.FILE["companyfacts"]).unlink()
    with pytest.raises(S.FileMancante, match="companyfacts.zip"):
        api.sec_azioni(ALFA)
    assert not any(p.suffix == ".zip" for p in (tmp_path / S.CARTELLA).iterdir())   # niente è stato scaricato al suo posto
    S.dimentica()


def test_dimensione_diversa_dal_manifest_non_si_legge(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    scrivi(tmp_path / S.CARTELLA, dati_manifest={"companyfacts": {"file": "companyfacts.zip", "byte": 12, "sha256": "x"}})
    S.dimentica()
    with pytest.raises(S.FileMancante, match="troncato o sostituito"):
        api.sec_bilancio(ALFA, ["Revenues"])
    S.dimentica()


def test_nessun_modulo_di_rete_nel_lettore():
    import ast
    from pathlib import Path
    albero = ast.parse(Path(S.__file__).read_text(encoding="utf-8"))
    importati = {a.name for n in ast.walk(albero) if isinstance(n, ast.Import) for a in n.names} | \
                {n.module for n in ast.walk(albero) if isinstance(n, ast.ImportFrom) and n.module}
    assert not importati & {"urllib", "urllib.request", "requests", "http.client", "socket"}
