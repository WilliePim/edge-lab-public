"""La chiave di cache, e il modo replay."""

import pytest

from edgar_llm.cache import RECORD, REPLAY, Cache, CacheMiss, key_for


def test_stesso_input_stessa_chiave():
    assert key_for("testo", "v1", "m") == key_for("testo", "v1", "m")


def test_un_prompt_diverso_e_una_chiave_diversa():
    #  ADR-005. Senza questo, cambiare prompt e rilanciare le evals
    #  restituirebbe i risultati del prompt vecchio senza una chiamata, e la
    #  regola "nessun prompt cambia senza rieseguire le evals" sarebbe
    #  inapplicabile proprio mentre sembra rispettata.
    assert key_for("testo", "v1", "m") != key_for("testo", "v2", "m")


def test_un_modello_diverso_e_una_chiave_diversa():
    assert key_for("testo", "v1", "sonnet") != key_for("testo", "v1", "opus")


def test_i_componenti_non_si_incollano():
    #  ("ab","c") e ("a","bc") devono restare distinti.
    assert key_for("ab", "c", "m") != key_for("a", "bc", "m")


def test_scrittura_e_rilettura(tmp_path):
    c = Cache(tmp_path, mode=RECORD)
    k = key_for("t", "v1", "m")
    assert c.get(k) is None
    c.put(k, {"payload": {"tipo": 1}})
    assert c.get(k)["payload"]["tipo"] == 1
    assert c.stats == {"hit": 1, "miss": 1, "write": 1}


def test_replay_alza_invece_di_chiamare(tmp_path):
    c = Cache(tmp_path, mode=REPLAY)
    with pytest.raises(CacheMiss):
        c.get(key_for("t", "v1", "m"))


def test_file_corrotto_e_un_miss_non_un_crash(tmp_path):
    c = Cache(tmp_path, mode=RECORD)
    k = key_for("t", "v1", "m")
    p = c.path(k)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ non json", encoding="utf-8")
    assert c.get(k) is None


def test_i_file_si_sparpagliano_in_sottodirectory(tmp_path):
    #  Una cartella piatta con decine di migliaia di file e' lenta ovunque.
    c = Cache(tmp_path)
    k = key_for("t", "v1", "m")
    assert c.path(k).parent.parent.name == k[:2]
    assert c.path(k).parent.name == k[2:4]
