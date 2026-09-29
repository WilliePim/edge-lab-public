"""Finti client, per non toccare rete ne' API.

I fake sono duck-typed sul minimo che il codice usa davvero -- `get`,
`get_json`, `submissions` -- e non ereditano da niente: un fake che eredita dal
client vero smette di fallire quando il vero cambia, ed e' esattamente allora
che dovrebbe fallire.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

#  Il package si importa come `edgar_llm`, quindi la radice del repo deve stare
#  su sys.path: pytest ci mette la dir dei test, non la nonna.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from edgar_llm.filings import Filing  # noqa: E402


class FakeEdgar:
    """Serve testi e JSON da due dizionari. Conta cosa gli e' stato chiesto."""

    def __init__(self, texts=None, subs=None):
        self.texts = texts or {}
        self.subs = subs or {}
        self.asked = []

    def get(self, url, use_cache=True):
        self.asked.append(url)
        return self.texts.get(url)

    def get_json(self, url, use_cache=True):
        self.asked.append(url)
        return self.subs.get(url)

    def submissions(self, cik):
        return self.subs.get(str(int(cik)))


class FakeLLM:
    """Restituisce un payload preconfezionato, o alza cio' che gli si dice."""

    model = "modello-finto"

    def __init__(self, payload=None, raise_=None, usage=None):
        self.payload = payload
        self.raise_ = raise_
        self.usage = usage or {"input_tokens": 100, "output_tokens": 20}
        self.calls = 0

    def extract(self, system, user_text, tool_name, tool_schema):
        self.calls += 1
        if self.raise_:
            raise self.raise_
        return self.payload, self.usage


def campo(value, confidence="high", excerpt=""):
    return {"value": value, "confidence": confidence, "source_excerpt": excerpt}


@pytest.fixture
def filing():
    return Filing(cik="216228", accession="0000216228-26-000020", form="8-K",
                  filed="2026-03-02", primary_document="itt-20260302.htm",
                  items="1.01,2.01,7.01")
