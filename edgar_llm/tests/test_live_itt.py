"""Il caso studio, contro l'API vera.

    pytest -m llm

Escluso dal run di default: serve una chiave e costa una chiamata (~$0,02 la
prima volta, zero dopo — la risposta finisce in cache).

E' l'asserzione che giustifica l'esistenza del modulo. L'8-K di ITT del
2026-03-02, item 2.01, e' il documento che l'euristica non poteva leggere e per
cui ha marcato `share count +15% in 12m` su un'acquisizione. Se questo test non
passa, il modulo non serve a niente, per bene che vadano le altre metriche.
"""

import pytest

from edgar_llm.cache import Cache
from edgar_llm.client import LLMClient
from edgar_llm.config import get as env_get
from edgar_llm.edgar import EdgarClient
from edgar_llm.extract import extract_filing
from edgar_llm.fetch import document_text, windows
from edgar_llm.filings import Filing

#  CIK ed accession sono un fatto pubblico e verificabile su EDGAR, non una
#  posizione: l'unico nome ammesso dentro il perimetro (README, AMMESSI).
ITT_8K = Filing(cik="216228", accession="0000216228-26-000020", form="8-K",
                filed="2026-03-02", primary_document="itt-20260302.htm",
                items="1.01,2.01,2.02,7.01,9.01")

pytestmark = pytest.mark.llm


@pytest.fixture(scope="module")
def edgar():
    #  env_get, NON os.environ: la prima versione leggeva l'ambiente grezzo e
    #  saltava sempre, perche' al momento della condizione di skip nessuno
    #  aveva ancora letto il .env. Una condizione di skip che non passa dal
    #  caricatore rende il test verde per assenza -- il modo piu' silenzioso
    #  che un test ha di non esistere.
    if not (env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")):
        pytest.skip("EDGAR_USER_AGENT non impostata")
    return EdgarClient()


@pytest.fixture(scope="module")
def evento(edgar):
    llm = LLMClient()
    if not llm.available and Cache().mode != "replay":
        pytest.skip("ANTHROPIC_API_KEY non impostata e la cache non e' in replay")
    return extract_filing(ITT_8K, edgar, llm=llm, cache=Cache())


def test_il_documento_si_legge(edgar):
    testo = document_text(edgar, ITT_8K)
    assert "2.01" in testo
    assert len(testo) > 5_000, "un 8-K di quella dimensione non e' quasi vuoto"


def test_e_una_emissione_per_acquisizione(evento):
    assert evento.notes == (), str(evento.notes)
    assert evento.tipo.value == "M&A_issuance", (
        "estratto {!r} con citazione {!r}".format(
            evento.tipo.value, evento.tipo.source_excerpt))
    assert evento.tipo.usable


def test_la_citazione_viene_davvero_dal_documento(edgar, evento):
    #  La validazione lo ha gia' controllato; qui si verifica che il controllo
    #  sia stato fatto sul testo giusto, e non su una stringa vuota.
    inviato = windows(document_text(edgar, ITT_8K)).lower()
    frammento = " ".join(evento.tipo.source_excerpt.lower().split())
    assert len(frammento) >= 12
    assert frammento in " ".join(inviato.split())


def test_la_controparte_e_nominata(evento):
    #  Non e' un requisito di produzione -- la soglia e' su `tipo` -- ma se il
    #  modello legge l'item 2.01 e non trova chi e' stato acquisito, il taglio
    #  del documento sta perdendo la parte che conta.
    assert evento.controparte.known, str(evento.controparte)
