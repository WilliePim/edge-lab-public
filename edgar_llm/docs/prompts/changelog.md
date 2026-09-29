# Prompt — changelog

Ogni versione sta in [`edgar_llm/prompts/`](../../prompts/) come file a se'.
Una modifica al prompt e' una versione nuova, mai una riscrittura in loco: la
chiave di cache include `prompt_version`, quindi due versioni non possono
contaminarsi ([ADR-005](../adr/005-chiave-di-cache.md)).

Ogni riga qui sotto lega una modifica al suo risultato di eval. **Una riga
senza risultato e' un prompt che non e' stato misurato, e non va in
produzione.**

| versione | cosa cambia | perche' | eval |
|---|---|---|---|
| `v1` | prima stesura | sette tipi, regola consideration-versus-cash, marcatori di elisione dichiarati, citazione letterale obbligatoria | ⟨da eseguire⟩ |

## v1 — le scelte, per poterle rimettere in discussione

**I marcatori di elisione sono spiegati al modello.** Il testo inviato non e' il
documento: e' la testa piu' alcune finestre, e i salti sono marcati. Il prompt
dice che sono portanti e che non si cita attraverso uno. Senza, un modello che
vede due frasi adiacenti le tratta come adiacenti, e in un prospetto tagliato
non lo sono.

**La regola che decide il caso ITT sta scritta per prima fra quelle difficili:**
se le azioni sono il prezzo pagato per qualcosa, e' `M&A_issuance`,
indipendentemente dalla forma su cui il documento e' depositato. Le forme
mentono su questo — un'acquisizione puo' comparire su un 8-K, su un 424B3 o su
un S-4 — e la forma e' proprio cio' che l'euristica gia' sa.

**«Non stimare» e' ripetuto per `importo_usd`.** Il valore di merito di
un'estrazione sbagliata su un importo e' alto: una cifra plausibile e' peggio di
nessuna cifra, perche' nessuno la va a controllare.

**L'incertezza ha un campo apposta.** Il prompt dice esplicitamente di non
risolverla indovinando un valore. Le tre confidence non sono un ornamento: sotto
`medium` il campo non e' usabile a valle.
