"""Controllo degli split mancanti e confronto del calendario, su serie finte."""
from market_data.quality import calendario as K
from market_data.quality import checks as Q


def serie(prezzi, volumi=None):
    return [{"date": "2020-{:02d}-{:02d}".format(1 + i // 28, 1 + i % 28), "close": p,
             "volume": (volumi[i] if volumi else None)} for i, p in enumerate(prezzi)]


def test_rapporto_tipico():
    assert Q.rapporto_tipico(0.1) == 0.1 and Q.rapporto_tipico(0.1046) == 0.1 and Q.rapporto_tipico(2.09) == 2.0
    assert Q.rapporto_tipico(0.106) is None and Q.rapporto_tipico(1.5) is None and Q.rapporto_tipico(0) is None
    assert Q.rapporto_tipico(0.1046, tolleranza=0.03) is None               # con il ±3% iniziale Iconix restava fuori


def test_bordo_esatto_della_tolleranza_resta_dentro():
    for k in Q.CANDIDATI:
        assert Q.rapporto_tipico(k * 1.05) == k and Q.rapporto_tipico(k * 0.95) == k


def test_split_mancante_segnalato_con_volume_coerente():
    prezzi = [60.0] * 25 + [6.1] * 25                         # rapporto 0,1017: dentro il ±5% di 1/10
    volumi = [100_000] * 25 + [1_000_000] * 25
    s = Q.salti_split_mancanti(serie(prezzi, volumi), set())
    assert len(s) == 1 and s[0]["rapporto_tipico"] == 0.1 and s[0]["volume_coerente"] is True


def test_split_registrato_non_segnalato_ma_riportato_col_volume():
    b = serie([60.0] * 25 + [30.2] * 25, [100] * 25 + [210] * 25)
    esito = Q.esamina_salti(b, {b[25]["date"]})
    assert esito["segnalati"] == [] and len(esito["split_registrati"]) == 1
    assert esito["split_registrati"][0]["volume_coerente"] is True
    assert len(Q.salti_split_mancanti(b, set())) == 1


def test_prezzo_che_torna_indietro_non_segnalato():
    prezzi = [60.0] * 25 + [6.0] * 5 + [59.0] * 20            # barra sbagliata per 5 giorni, poi il livello vero
    assert Q.salti_split_mancanti(serie(prezzi), set()) == []


def test_prezzo_che_si_allontana_ancora_resta_segnalato():
    prezzi = [60.0] * 25 + [6.0] + [5.0, 4.0, 3.0, 2.5] + [2.0] * 16   # dopo il salto in giù scende ancora
    assert len(Q.salti_split_mancanti(serie(prezzi), set())) == 1


def test_rapporto_non_tipico_non_segnalato():
    assert Q.salti_split_mancanti(serie([60.0] * 25 + [6.9] * 25), set()) == []   # 0,115: fuori dal ±5%


def test_volume_nello_stesso_senso_del_prezzo():
    s = Q.salti_split_mancanti(serie([60.0] * 25 + [6.0] * 25, [100_000] * 25 + [50_000] * 25), set())
    assert len(s) == 1 and s[0]["volume_coerente"] is False


def test_senza_volume_e_non_valutabili():
    s = Q.salti_split_mancanti(serie([60.0] * 25 + [6.0] * 25), set())
    assert s[0]["volume_coerente"] is None
    corto = Q.esamina_salti(serie([60.0] * 25 + [6.0] * 10), set())
    assert corto["segnalati"] == [] and corto["non_valutabili"][0]["motivo"] == "meno di 20 sedute dopo"
    buco = Q.esamina_salti(serie([60.0] * 25 + [6.0] * 10 + [None] + [6.0] * 14), set())
    assert buco["segnalati"] == [] and buco["non_valutabili"][0]["motivo"] == "chiusura mancante nelle 20 sedute dopo"


def test_accettazione_iconix():
    """Forma del caso Iconix del 17-12-2015 su numeri finti: chiusura divisa per 10 e rialzo del 4,6% nello stesso
    giorno, volume moltiplicato, nessun ritorno. Test di accettazione dell'utente: deve essere segnalato."""
    prezzi = [50.0] * 25 + [5.23, 5.35, 5.5, 5.7] + [5.6] * 17          # 5,23 / 50 = 0,1046, come Iconix
    volumi = [150_000] * 25 + [1_800_000] * 21
    assert len(Q.salti_split_mancanti(serie(prezzi, volumi), set())) == 1


def test_confronto_calendario():
    lib = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    tit = ["2020-01-03", "2020-01-04", "2020-01-06", "2020-01-07", "2020-01-08"]
    r = K.confronta(lib, tit)
    assert r["periodo"] == ("2020-01-03", "2020-01-07")
    assert r["solo_libreria"] == [] and r["solo_titolo"] == ["2020-01-04"]
    r2 = K.confronta(lib, ["2020-01-02", "2020-01-07"])
    assert r2["solo_libreria"] == ["2020-01-03", "2020-01-06"]


def test_fasce_di_prezzo():
    assert Q.fascia_prezzo({"chiusura_prima": 0.04, "chiusura": 0.4}) == "sotto 0,05"
    assert Q.fascia_prezzo({"chiusura_prima": 5.0, "chiusura": 0.5}) == "fra 0,05 e 1"
    assert Q.fascia_prezzo({"chiusura_prima": 50.0, "chiusura": 5.0}) == "sopra 1"
    assert Q.fascia_prezzo({"chiusura_prima": 1.0, "chiusura": 10.0}) == "sopra 1"


def test_volume_zero_ripetuto():
    b = [{"date": "d{:03d}".format(i), "close": 10.0, "volume": 500} for i in range(5)]
    b += [{"date": "d{:03d}".format(i), "close": 11.0, "volume": 0} for i in range(5, 30)]      # 25 sedute piatte
    b += [{"date": "d{:03d}".format(i), "close": 11.5, "volume": 0} for i in range(30, 40)]     # 10: troppo poche
    b += [{"date": "d{:03d}".format(i), "close": 12.0, "volume": 0} for i in range(40, 60)]     # 20 esatte, fino in fondo
    assert Q.sequenze_volume_zero(b) == [{"da": "d005", "a": "d029", "sedute": 25}, {"da": "d040", "a": "d059", "sedute": 20}]


def test_volume_zero_con_prezzo_che_cambia_o_volume_mancante():
    cambia = [{"date": str(i), "close": 10.0 + i, "volume": 0} for i in range(30)]
    assert Q.sequenze_volume_zero(cambia) == []
    buco = [{"date": str(i), "close": 10.0, "volume": (None if i == 15 else 0)} for i in range(30)]
    assert Q.sequenze_volume_zero(buco) == []                                   # 15 + 14: nessuna arriva a 20

