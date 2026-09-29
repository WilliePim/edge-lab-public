"""Il solo punto del package che parla con un modello.

Sottile per scelta (ADR-003): un documento, una chiamata, uno schema. Non c'e'
catena, non c'e' agente, non c'e' retrieval, e un framework qui nasconderebbe
l'unica cosa che vale la pena mostrare.

L'output strutturato passa da un tool forzato: si dichiara un attrezzo il cui
schema E' lo schema dell'estrazione, e si obbliga il modello a chiamarlo. Cosi'
la risposta non e' testo da cui sperare di ricavare del JSON — e' gia' JSON, e
la validazione in `schema.validate` lavora su un dizionario, non su una stringa.

Che il modello non risponda e' un esito previsto, non un guasto: `extract`
alza, e chi chiama degrada a UNKNOWN. Lo scanner deve girare identico con
l'API spenta.
"""

from __future__ import annotations

import logging

from .config import get as env_get

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 1500

#  NIENTE TEMPERATURE. Non e' una scelta: `messages.create` non lo accetta piu'
#  in anthropic 1.3.0 -- il parametro e' sparito dall'API, e passarlo alza
#  TypeError. Qui c'era `temperature=0.0` con un commento che diceva di togliere
#  "l'unica variabilita' che si puo' togliere". Non si puo' togliere nemmeno
#  quella.
#
#  Il che non cambia il progetto, lo conferma: un'estrazione non e'
#  riproducibile, ed e' per questo che non puo' fare da cancello (ADR-004). Cio'
#  che rende stabile il risultato a valle e' la CACHE -- lo stesso documento con
#  lo stesso prompt e lo stesso modello restituisce la stessa risposta perche' e'
#  la stessa risposta, non perche' il modello la rigeneri identica.


#  Header richiesto dalle chiavi legate a un'identita': senza, l'API risponde
#  400 «anthropic-workspace-id is required when authenticating with an
#  identity-linked API key». Non tutte le chiavi ne hanno bisogno, quindi si
#  manda solo quando c'e' -- mandarne uno vuoto sarebbe peggio che non mandarlo.
WORKSPACE_HEADER = "anthropic-workspace-id"


class MissingApiKey(RuntimeError):
    pass


class ModelUnavailable(RuntimeError):
    """L'API non ha risposto, o ha risposto qualcosa che non e' un'estrazione."""


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL,
                 max_tokens: int = DEFAULT_MAX_TOKENS,
                 api_key: str | None = None, max_retries: int = 3,
                 workspace_id: str | None = None):
        self.model = model
        self.max_tokens = max_tokens
        #  env_get carica il .env la prima volta, senza sovrascrivere cio'
        #  che l'ambiente ha gia'.
        self._api_key = api_key or env_get("ANTHROPIC_API_KEY")
        self._workspace_id = workspace_id or env_get("ANTHROPIC_WORKSPACE_ID")
        self._max_retries = max_retries
        self._client = None
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise MissingApiKey(
                "ANTHROPIC_API_KEY non impostata, ne' nell'ambiente ne' in un "
                "file .env risalendo dal package. `python -m edgar_llm.config` "
                "dice cosa vede. Senza chiave si gira in EDGAR_LLM_MODE=replay, "
                "servendosi dalla cache.")
        try:
            import anthropic
        except ImportError as e:                                # pragma: no cover
            raise ModelUnavailable(
                "il pacchetto `anthropic` non e' installato: pip install anthropic"
            ) from e
        headers = ({WORKSPACE_HEADER: self._workspace_id}
                   if self._workspace_id else None)
        self._client = anthropic.Anthropic(api_key=self._api_key,
                                           max_retries=self._max_retries,
                                           default_headers=headers)
        return self._client

    def ping(self) -> dict:
        """Una chiamata minima, solo per sapere se le credenziali funzionano.

        Serve perche' `pytest -m llm` NON lo dimostra: l'estrazione di ITT e'
        in cache, quindi quel test passa anche con una chiave revocata. Una
        verifica che puo' riuscire senza toccare cio' che deve verificare non
        e' una verifica -- lo stesso difetto di PM-001, in un'altra veste.

        Costa qualche decina di token. Alza ModelUnavailable come `extract`.
        """
        client = self._ensure()
        try:
            msg = client.messages.create(
                model=self.model, max_tokens=8,
                messages=[{"role": "user", "content": "ok"}])
        except Exception as e:                                  # noqa: BLE001
            if WORKSPACE_HEADER in str(e) and not self._workspace_id:
                raise ModelUnavailable(
                    "la chiave e' legata a un'identita' e l'API vuole anche "
                    "l'id dello spazio di lavoro: ANTHROPIC_WORKSPACE_ID."
                ) from e
            raise ModelUnavailable("{}: {}".format(type(e).__name__, e)) from e
        u = getattr(msg, "usage", None)
        return {"model": getattr(msg, "model", self.model),
                "input_tokens": getattr(u, "input_tokens", 0) or 0,
                "output_tokens": getattr(u, "output_tokens", 0) or 0}

    def extract(self, system: str, user_text: str, tool_name: str,
                tool_schema: dict) -> tuple[dict, dict]:
        """(payload del tool, usage). Alza ModelUnavailable su qualsiasi guaio."""
        client = self._ensure()
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=[{
                    "name": tool_name,
                    "description": "Registra l'evento di emissione descritto "
                                   "dal documento.",
                    "input_schema": tool_schema,
                }],
                #  Forzato: senza, il modello puo' rispondere in prosa e la
                #  meta' dei casi difficili -- quelli in cui esita -- tornerebbe
                #  come testo invece che come estrazione da validare.
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user_text}],
            )
        except Exception as e:                                  # noqa: BLE001
            #  Un errore di configurazione non deve arrivare travestito da
            #  guasto passeggero: dice cosa manca e dove si mette.
            if WORKSPACE_HEADER in str(e) and not self._workspace_id:
                raise ModelUnavailable(
                    "la chiave e' legata a un'identita' e l'API vuole anche "
                    "l'id dello spazio di lavoro. Aggiungi "
                    "ANTHROPIC_WORKSPACE_ID=... al .env (Console Anthropic -> "
                    "Settings -> Workspaces, e' l'id che comincia per "
                    "`wrkspc_`)."
                ) from e
            raise ModelUnavailable("{}: {}".format(type(e).__name__, e)) from e

        payload = None
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use" and block.name == tool_name:
                payload = block.input
                break
        if payload is None:
            raise ModelUnavailable(
                "nessun blocco tool_use nella risposta (stop_reason={})".format(
                    getattr(msg, "stop_reason", "?")))

        u = getattr(msg, "usage", None)
        usage = {"input_tokens": getattr(u, "input_tokens", 0) or 0,
                 "output_tokens": getattr(u, "output_tokens", 0) or 0}
        self.usage["input_tokens"] += usage["input_tokens"]
        self.usage["output_tokens"] += usage["output_tokens"]
        self.usage["calls"] += 1
        return payload, usage
